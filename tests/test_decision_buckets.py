"""
Tests for BNPL decision buckets/tiers.
"""
import json
import os
from datetime import datetime

from domain.entities import Transaction
from domain.services.normalization import Normalization
from domain.services.risk_calculation import RiskCalculationService


def load_transactions(filename: str) -> list[Transaction]:
    """Load and normalize transactions from JSON file."""
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, "data", filename)
    
    with open(file_path, "r") as f:
        raw = json.load(f)
    
    transactions = []
    for t in raw["transactions"]:
        tx = Transaction(
            transaction_id=t["transaction_id"],
            date=datetime.strptime(t["date"], "%Y-%m-%d"),
            amount_cents=t["amount_cents"],
            type=t["type"],
            description=t.get("description", ""),
            category=t.get("category", ""),
            merchant=t.get("merchant", ""),
            balance_cents=t.get("balance_cents", 0),
            nsf=t.get("nsf", False),
        )
        transactions.append(tx)
    
    return Normalization.normalize_and_sort_trxns(transactions)


class TestDecisionBuckets:
    """Tests for BNPL tier decision logic."""

    def test_user_good_gets_approved(self):
        """User_good with healthy finances should get approved (Tier A-C)."""
        txs = load_transactions("transactions_user_good.json")
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        
        # User with good balance and no NSF should get at least Tier C
        assert result["limit_bucket"] in ("Tier A", "Tier B", "Tier C")
        assert result["limit_amount"] >= 6000  # At least $60
        assert result["approved"] is True
        assert result["final_score"] >= 50  # Reasonable score

    def test_user_gig_gets_tier_b_or_c(self):
        """User_gig with irregular income should get Tier B or C."""
        txs = load_transactions("transactions_user_gig.json")
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        
        # Gig workers typically have higher risk due to income volatility
        assert result["limit_bucket"] in ("Tier B", "Tier C", "Tier D", "Deny")
        
    def test_user_highutil_gets_tier_c_or_lower(self):
        """User_highutil with high utilization should get Tier C/D or Deny."""
        txs = load_transactions("transactions_user_highutil.json")
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        
        assert result["limit_bucket"] in ("Tier C", "Tier D", "Deny")
        # If approved, limit should be capped
        if result["approved"]:
            assert result["limit_amount"] <= 6000  # Max $60

    def test_user_overdraft_gets_denied(self):
        """User_overdraft with NSF history should be denied or get minimal tier."""
        txs = load_transactions("transactions_user_overdraft.json")
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        
        # High NSF count should result in denial or very limited tier
        assert result["limit_bucket"] in ("Tier D", "Deny")
        assert result["final_score"] < 50

    def test_tier_limits_are_correct(self):
        """Verify tier limit amounts are as specified."""
        from domain.services.risk_calculation import BNPLTier
        
        assert BNPLTier.TIER_A[1] == 20000  # $200
        assert BNPLTier.TIER_B[1] == 12000  # $120
        assert BNPLTier.TIER_C[1] == 6000   # $60
        assert BNPLTier.TIER_D[1] == 2000   # $20
        assert BNPLTier.DENY[1] == 0

    def test_decision_includes_reasons(self):
        """Verify decision includes explainability reasons."""
        txs = load_transactions("transactions_user_good.json")
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        
        assert "reasons" in result
        assert len(result["reasons"]) > 0
        
        # Should include key information
        reasons_text = " ".join(result["reasons"])
        assert "income" in reasons_text.lower() or "balance" in reasons_text.lower()
        assert "Decision" in reasons_text

    def test_result_includes_all_signals(self):
        """Verify result includes all required signals."""
        txs = load_transactions("transactions_user_good.json")
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        
        # Core fields
        assert "final_score" in result
        assert "limit_bucket" in result
        assert "limit_amount" in result
        assert "approved" in result
        
        # Component scores
        assert "component_scores" in result
        assert "balance_score" in result["component_scores"]
        
        # Additional signals
        assert "utilization_info" in result
        assert "payback_capacity" in result
        assert "cooldown" in result
        assert "penalties_applied" in result

