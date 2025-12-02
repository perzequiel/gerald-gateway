from typing import TypedDict

from .utilizations import PaycheckInfo, UtilizationService
from .basics_features import BasicsFeatures, MonthlyIncomeVsSpend
from .internal_transactions import InternalTransaction
from .decision import DecisionService

class ComponentScores(TypedDict):
    balance_score: float
    income_spend_score: float
    nsf_score: float

class RiskScore(TypedDict):
    def __init__(
        self,
        avg_daily_balance_cents: int,
        monthly_income_cents: int,
        monthly_spend_cents: int,
        nsf_count: int,
        balance_score: float,
        income_spend_score: float,
        nsf_score: float,
        utilization_info: dict,
        final_score: float,
        max_amount_for_limit_bucket: int,
        limit_bucket: str,
        limit_amount: int,
        reasons: list[str],
    ):
        self.avg_daily_balance_cents = avg_daily_balance_cents
        self.monthly_income_cents = monthly_income_cents
        self.monthly_spend_cents = monthly_spend_cents
        self.nsf_count = nsf_count
        self.balance_score = balance_score
        self.income_spend_score = income_spend_score
        self.nsf_score = nsf_score
        self.final_score = final_score
        self.limit_bucket = limit_bucket
        self.limit_amount = limit_amount
        self.reasons = reasons
        self.utilization_info = utilization_info
        self.max_amount_for_limit_bucket = max_amount_for_limit_bucket
        self.component_scores = ComponentScores(
            balance_score=balance_score,
            income_spend_score=income_spend_score,
            nsf_score=nsf_score
        )

class RiskCalculationService:
    def __init__(self, balance_neg_cap: int = 10_000,
        nsf_penalty: float = 25.0,
        balance_weight: float = 0.5,
        income_spend_weight: float = 0.3,
        nsf_weight: float = 0.2,
        max_amount_for_limit_bucket: int = 100_000
    ):
        # this is the balance negative cap, if the average daily balance is less than this value, the score is 0
        self.balance_neg_cap = balance_neg_cap
        # this is the penalty for each NSF event, if the number of NSF events is greater than 0, the score is reduced by this value
        self.nsf_penalty = nsf_penalty
        # this is the weight for the balance score, if the balance score is greater than 0, the score is increased by this value
        self.balance_weight = balance_weight
        # this is the weight for the income vs spend score, if the income vs spend score is greater than 0, the score is increased by this value
        self.income_spend_weight = income_spend_weight
        # this is the weight for the NSF score, if the NSF score is greater than 0, the score is increased by this value
        self.nsf_weight = nsf_weight
        # maximum amount for the limit bucket 1000
        self.max_amount_for_limit_bucket = max_amount_for_limit_bucket

    def calculate_risk(self, transactions: list[InternalTransaction]) -> RiskScore:
        """
        Input: list of transactions (each with keys: 'date' YYYY-MM-DD, 'amount_cents', 'type' ('debit'|'credit'),
            'balance_cents' (opcional), 'nsf' (optional bool)).
        Output: dict with metrics and decision: avg_daily_balance, monthly_income_cents, monthly_spend_cents,
                nsf_count, score (0-100), limit_bucket (string) y razones básicas.
        Logic:
        - Avg daily balance: fill days without tx with the last known balance (carry-forward).
        - Income vs spend: sum credits and debits and monthlyize them according to the date range.
        - NSF/overdrafts: count events where nsf==True or where after a debit the balance (reported) is < 0.
        - Score: weighted combination of (balance, income/spend ratio, nsf_count).
        - Bucket: simple mapping of the score to predefined limits.
        """
        if not transactions:
            return {"error": "no transactions"}

        # average daily balance
        avg_daily_balance = BasicsFeatures.calculate_avg_daily_balance(transactions)

        # income vs spend (sum totals)
        income_vs_spend: MonthlyIncomeVsSpend = BasicsFeatures.calculate_monthly_income_vs_spend(transactions)
        monthly_income = income_vs_spend.income
        monthly_spend = income_vs_spend.spend

        # --- NSF / overdraft count ---
        nsf_count = BasicsFeatures.calculate_nsf_count(transactions)

        # --- scoring components ---
        # 1) balance_score: if avg >= 0 => 100, if avg <= -self.balance_neg_cap => 0, linear between medias  
        balance_score = BasicsFeatures.calculate_balance_score(avg_daily_balance, self.balance_neg_cap)

        # 2) income vs spend score: ratio = income / spend (if spend=0 => 100)
        income_spend_score = BasicsFeatures.calculate_income_spend_score(monthly_income, monthly_spend)

        # 3) nsf score: penalize quickly for each event (eg: 0 events => 100, 4+ => 0)
        nsf_score = BasicsFeatures.calculate_nsf_score(nsf_count, self.nsf_penalty)

        # 4) utilization score: calculate the utilization of the credit limit
        paycheck_info = PaycheckInfo(
            avg_paycheck_cents=int(monthly_income) if monthly_income and monthly_income > 0 else None,
            # assume monthly cycle by default if no income cycle detector is available (30 days)
            period_days=30,
            # low/high confidence based on whether income is detected
            paycheck_confidence=0.8 if monthly_income and monthly_income > 0 else 0.0,
        )
        # trnx = Normalization.normalize_and_sort_trxns(transactions)
        utilization_info = UtilizationService(transactions, paycheck_info).calculate()


        # add utilization label to early reasons
        if utilization_info.get("utilization_label") == "high-risk":
            # strong penalty if the user burns the paycheck
            # simple adjustment: subtract 15 points from the final_score later
            utilization_penalty = 15.0
        elif utilization_info.get("utilization_label") == "medium-risk":
            utilization_penalty = 7.5
        else:
            utilization_penalty = 0.0
        
        # weighted combination (adjust weights if you want)
        final_score = BasicsFeatures.calculate_final_score(
            balance_score=balance_score,
            income_spend_score=income_spend_score,
            nsf_score=nsf_score,
            balance_weight=self.balance_weight,
            income_spend_weight=self.income_spend_weight,
            nsf_weight=self.nsf_weight,
            utilization_penalty=utilization_penalty
        )

        # --- bucket mapping (simple example) ---
        limit_bucket, limit_amount = BasicsFeatures.calculate_limit_bucket(final_score, self.max_amount_for_limit_bucket)
        
        # reasons breakdown
        reasons = DecisionService(
            avg_daily_balance=avg_daily_balance, 
            monthly_income=monthly_income, monthly_spend=monthly_spend,
            nsf_count=nsf_count,
            utilization_info=utilization_info
            ).make_decision()

        reasons.append(f"utilization_label={utilization_info.get('utilization_label')}, utilization_pct={utilization_info.get('utilization_pct')}")

        return RiskScore(
            avg_daily_balance_cents=int(avg_daily_balance), 
            monthly_income_cents=int(monthly_income),
            monthly_spend_cents=int(monthly_spend),
            nsf_count=nsf_count,
            balance_score=round(balance_score, 1),
            income_spend_score=round(income_spend_score, 1),
            nsf_score=round(nsf_score, 1),
            final_score=round(final_score, 1),
            limit_bucket=limit_bucket,
            limit_amount=limit_amount,
            reasons=reasons,
            utilization_info=utilization_info,
            component_scores=ComponentScores(
                balance_score=round(balance_score, 1),
                income_spend_score=round(income_spend_score, 1),
                nsf_score=round(nsf_score, 1)
            ),
            max_amount_for_limit_bucket=self.max_amount_for_limit_bucket
        )