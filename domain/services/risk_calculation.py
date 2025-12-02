"""
Risk Calculation Service

Main service for BNPL risk scoring. Integrates multiple signals:
- Balance and income/spend analysis
- NSF/overdraft history
- Utilization (Gaussian scoring)
- Payback capacity
- Cooldown period enforcement
"""
from typing import TypedDict, Optional

from .utilizations import PaycheckInfo, UtilizationService
from .basics_features import BasicsFeatures, MonthlyIncomeVsSpend
from .internal_transactions import InternalTransaction
from .payback_capacity import compute_payback_capacity, PaybackCapacityResult
from .cooldown import compute_cooldown, CooldownResult


class ComponentScores(TypedDict):
    balance_score: float
    income_spend_score: float
    nsf_score: float


class BNPLTier:
    """BNPL limit tiers with realistic amounts"""
    TIER_A = ("Tier A", 20000)   # Up to $200
    TIER_B = ("Tier B", 12000)   # Up to $120
    TIER_C = ("Tier C", 6000)    # Up to $60
    TIER_D = ("Tier D", 2000)    # Trial - up to $20
    DENY = ("Deny", 0)           # Denied


class RiskCalculationService:
    """
    BNPL Risk Calculation Service
    
    Evaluates user financial health and determines credit eligibility.
    
    Scoring Components:
    - balance_score (50%): Based on average daily balance
    - income_spend_score (30%): Income vs spending ratio
    - nsf_score (20%): NSF/overdraft penalty
    
    Additional Signals:
    - utilization: Gaussian-scored burn rate analysis
    - payback_capacity: Projected ability to repay
    - cooldown: Prevents rapid successive advances
    
    Penalties:
    - utilization high-risk: -15 points
    - utilization medium-risk: -7.5 points
    - payback negative: -10 points
    """
    
    def __init__(
        self,
        balance_neg_cap: int = 10_000,
        nsf_penalty: float = 25.0,
        balance_weight: float = 0.5,
        income_spend_weight: float = 0.3,
        nsf_weight: float = 0.2,
        payback_penalty: float = 10.0,
        cooldown_hours: int = 72
    ):
        self.balance_neg_cap = balance_neg_cap
        self.nsf_penalty = nsf_penalty
        self.balance_weight = balance_weight
        self.income_spend_weight = income_spend_weight
        self.nsf_weight = nsf_weight
        self.payback_penalty = payback_penalty
        self.cooldown_hours = cooldown_hours

    def _determine_bnpl_tier(
        self,
        final_score: float,
        utilization_label: str,
        payback_label: str,
        nsf_count: int,
        is_in_cooldown: bool
    ) -> tuple[str, int, str]:
        """
        Determine BNPL tier based on multiple signals.
        
        Returns: (tier_name, limit_cents, decision_reason)
        """
        # Cooldown overrides everything
        if is_in_cooldown:
            return BNPLTier.DENY[0], BNPLTier.DENY[1], "Cooldown period active - must wait before new advance"
        
        # Extreme NSF count is automatic deny (20+ events in 90 days is severe)
        if nsf_count >= 20:
            return BNPLTier.DENY[0], BNPLTier.DENY[1], f"Denied due to excessive NSF events ({nsf_count})"
        
        # Tier A: Premium - best customers (score drives decision, NSF already penalized in score)
        if (final_score >= 80 and 
            utilization_label == "healthy" and 
            payback_label == "positive" and
            nsf_count <= 2):
            return BNPLTier.TIER_A[0], BNPLTier.TIER_A[1], \
                f"Tier A approved: score={final_score:.0f}, healthy utilization, positive payback"
        
        # Tier B: Standard - good customers
        if (final_score >= 65 and 
            utilization_label in ("healthy", "medium-risk") and
            payback_label in ("positive", "neutral") and
            nsf_count <= 5):
            return BNPLTier.TIER_B[0], BNPLTier.TIER_B[1], \
                f"Tier B approved: score={final_score:.0f}, acceptable utilization and payback"
        
        # Tier C: Limited - moderate risk (rely more on score)
        if final_score >= 50 and nsf_count <= 10:
            return BNPLTier.TIER_C[0], BNPLTier.TIER_C[1], \
                f"Tier C approved: score={final_score:.0f}, limited advance recommended"
        
        # Tier D: Trial - first-time or rebuilding (most lenient)
        if final_score >= 35 and nsf_count <= 15:
            return BNPLTier.TIER_D[0], BNPLTier.TIER_D[1], \
                f"Tier D trial: score={final_score:.0f}, small trial advance only"
        
        # Deny - explain why
        deny_reasons = []
        if final_score < 35:
            deny_reasons.append(f"low score ({final_score:.0f})")
        if utilization_label in ("very-high-risk", "critical-risk"):
            deny_reasons.append(f"high utilization ({utilization_label})")
        if payback_label == "negative":
            deny_reasons.append("negative payback capacity")
        if nsf_count > 15:
            deny_reasons.append(f"high NSF count ({nsf_count})")
        
        reason = "Denied: " + ", ".join(deny_reasons) if deny_reasons else "Denied: does not meet criteria"
        return BNPLTier.DENY[0], BNPLTier.DENY[1], reason

    def calculate_risk(
        self,
        transactions: list[InternalTransaction],
        user_events: Optional[list[dict]] = None
    ) -> dict:
        """
        Calculate risk score and determine BNPL eligibility.
        
        Args:
            transactions: List of user transactions
            user_events: Optional list of user events for cooldown check
        
        Returns:
            Dict with scores, limits, and detailed explainability
        """
        if not transactions:
            return {"error": "no transactions", "approved": False}

        # === BASIC FEATURES ===
        avg_daily_balance = BasicsFeatures.calculate_avg_daily_balance(transactions)
        income_vs_spend: MonthlyIncomeVsSpend = BasicsFeatures.calculate_monthly_income_vs_spend(transactions)
        monthly_income = income_vs_spend.income
        monthly_spend = income_vs_spend.spend
        nsf_count = BasicsFeatures.calculate_nsf_count(transactions)

        # === COMPONENT SCORES ===
        balance_score = BasicsFeatures.calculate_balance_score(avg_daily_balance, self.balance_neg_cap)
        income_spend_score = BasicsFeatures.calculate_income_spend_score(monthly_income, monthly_spend)
        nsf_score = BasicsFeatures.calculate_nsf_score(nsf_count, self.nsf_penalty)

        # === PAYCHECK INFO (fallback) ===
        paycheck_info = PaycheckInfo(
            avg_paycheck_cents=int(monthly_income) if monthly_income and monthly_income > 0 else None,
            period_days=30,
            paycheck_confidence=0.8 if monthly_income and monthly_income > 0 else 0.0,
        )

        # === UTILIZATION (Gaussian scoring) ===
        utilization_info = UtilizationService(transactions, paycheck_info).calculate()
        utilization_label = utilization_info.get("utilization_label", "unknown")
        
        # Utilization penalty
        if utilization_label in ("high-risk", "very-high-risk", "critical-risk"):
            utilization_penalty = 15.0
        elif utilization_label == "medium-risk":
            utilization_penalty = 7.5
        else:
            utilization_penalty = 0.0

        # === PAYBACK CAPACITY ===
        payback_info: PaybackCapacityResult = compute_payback_capacity(
            avg_daily_balance_cents=int(avg_daily_balance),
            burn_days=utilization_info.get("burn_days"),
            avg_daily_spend_cents=utilization_info.get("avg_daily_spend_cents", 0),
            avg_paycheck_cents=paycheck_info.avg_paycheck_cents
        )
        payback_label = payback_info["payback_label"]
        
        # Payback penalty
        payback_penalty = self.payback_penalty if payback_label == "negative" else 0.0

        # === COOLDOWN CHECK ===
        cooldown_info: CooldownResult = compute_cooldown(
            user_events=user_events,
            transactions=transactions,
            cooldown_hours=self.cooldown_hours
        )
        is_in_cooldown = cooldown_info["is_in_cooldown"]

        # === FINAL SCORE ===
        base_score = BasicsFeatures.calculate_final_score(
            balance_score=balance_score,
            income_spend_score=income_spend_score,
            nsf_score=nsf_score,
            balance_weight=self.balance_weight,
            income_spend_weight=self.income_spend_weight,
            nsf_weight=self.nsf_weight,
            utilization_penalty=utilization_penalty
        )
        
        # Apply payback penalty
        final_score = max(0.0, min(100.0, base_score - payback_penalty))

        # === BNPL TIER DECISION ===
        tier_name, limit_amount, tier_reason = self._determine_bnpl_tier(
            final_score=final_score,
            utilization_label=utilization_label,
            payback_label=payback_label,
            nsf_count=nsf_count,
            is_in_cooldown=is_in_cooldown
        )

        # === EXPLAINABILITY (reasons) ===
        reasons = self._build_reasons(
            avg_daily_balance=avg_daily_balance,
            monthly_income=monthly_income,
            monthly_spend=monthly_spend,
            nsf_count=nsf_count,
            utilization_info=utilization_info,
            payback_info=payback_info,
            cooldown_info=cooldown_info,
            tier_reason=tier_reason
        )

        # === RETURN RESULT ===
        return {
            # Core metrics
            "avg_daily_balance_cents": int(avg_daily_balance),
            "monthly_income_cents": int(monthly_income),
            "monthly_spend_cents": int(monthly_spend),
            "nsf_count": nsf_count,
            
            # Component scores
            "component_scores": {
                "balance_score": round(balance_score, 1),
                "income_spend_score": round(income_spend_score, 1),
                "nsf_score": round(nsf_score, 1)
            },
            
            # Final score and decision
            "final_score": round(final_score, 1),
            "limit_bucket": tier_name,
            "limit_amount": limit_amount,
            "approved": limit_amount > 0,
            
            # Detailed signals
            "utilization_info": utilization_info,
            "payback_capacity": payback_info,
            "cooldown": cooldown_info,
            
            # Human-readable reasons
            "reasons": reasons,
            
            # Penalties applied
            "penalties_applied": {
                "utilization_penalty": utilization_penalty,
                "payback_penalty": payback_penalty
            }
        }

    def _build_reasons(
        self,
        avg_daily_balance: float,
        monthly_income: float,
        monthly_spend: float,
        nsf_count: int,
        utilization_info: dict,
        payback_info: PaybackCapacityResult,
        cooldown_info: CooldownResult,
        tier_reason: str
    ) -> list[str]:
        """Build human-readable reasons list for explainability."""
        reasons = []
        
        # Paycheck summary
        if monthly_income > 0:
            reasons.append(f"Detected monthly income: ${monthly_income/100:,.2f} (confidence: 80%)")
        else:
            reasons.append("No reliable income detected - limited confidence")
        
        # Balance summary
        if avg_daily_balance < 0:
            reasons.append(f"Negative average daily balance: ${avg_daily_balance/100:,.2f}")
        else:
            reasons.append(f"Average daily balance: ${avg_daily_balance/100:,.2f}")
        
        # Income vs spend
        if monthly_spend > monthly_income:
            deficit = monthly_spend - monthly_income
            reasons.append(f"Spending exceeds income by ${deficit/100:,.2f}/month")
        elif monthly_income > 0:
            surplus = monthly_income - monthly_spend
            reasons.append(f"Monthly surplus: ${surplus/100:,.2f}")
        
        # NSF summary
        if nsf_count > 0:
            reasons.append(f"⚠️ {nsf_count} NSF/overdraft events detected")
        else:
            reasons.append("✓ No NSF/overdraft events")
        
        # Utilization
        util_label = utilization_info.get("utilization_label", "unknown")
        util_pct = utilization_info.get("utilization_pct")
        burn_days = utilization_info.get("burn_days")
        
        if util_pct is not None:
            reasons.append(f"Utilization: {util_pct*100:.0f}% ({util_label})")
        if burn_days:
            reasons.append(f"Burn rate: paycheck lasts {burn_days:.0f} days")
        
        # Payback capacity
        reasons.append(f"Payback capacity: {payback_info['payback_label']} - {payback_info['explanation']}")
        
        # Cooldown
        if cooldown_info["is_in_cooldown"]:
            reasons.append(f"🚫 {cooldown_info['explanation']}")
        
        # Decision reason
        reasons.append(f"📋 Decision: {tier_reason}")
        
        return reasons
