"""
Unit tests for utilization service and integration tests with real transaction data.
"""
import json
import os
from datetime import datetime

from domain.entities import Transaction
from domain.services.utilizations import PaycheckInfo, UtilizationService
from domain.services.normalization import Normalization
from domain.services.risk_calculation import RiskCalculationService


def load_transactions(filename: str) -> dict:
    """Load transactions from a JSON file in the tests/data directory."""
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, "data", filename)
    with open(file_path, "r") as f:
        return json.load(f)


def normalize_transactions(raw_transactions: list[dict]) -> list[Transaction]:
    """
    Convert raw transaction dicts to Transaction entities and normalize dates.
    """
    transactions = []
    for t in raw_transactions:
        tx = Transaction(
            transaction_id=t["transaction_id"],
            date=datetime.strptime(t["date"], "%Y-%m-%d") if isinstance(t["date"], str) else t["date"],
            amount_cents=t["amount_cents"],
            type=t["type"],
            description=t.get("description", ""),
            category=t.get("category", ""),
            merchant=t.get("merchant", ""),
            balance_cents=t.get("balance_cents", 0),
            nsf=t.get("nsf", False),
        )
        transactions.append(tx)
    
    # Normalize and sort transactions by date
    return Normalization.normalize_and_sort_trxns(transactions)


class TestUtilizationIntegration:
    """Integration tests for utilization service using real transaction data."""

    def test_utilization_integration_user_good(self):
        """
        Test utilization calculation with user_good transactions.
        Verifies that the utilization service correctly computes utilization
        metrics for a user with healthy spending patterns.
        """
        raw = load_transactions("transactions_user_good.json")
        txs = normalize_transactions(raw["transactions"])

        # Create paycheck info (fallback if detect_paycheck doesn't exist)
        paycheck_info = PaycheckInfo(
            avg_paycheck_cents=300000,
            period_days=30,
            paycheck_confidence=0.8
        )

        # Compute utilization using the service
        util_service = UtilizationService(txs, paycheck_info)
        util = util_service.calculate()

        # Assert utilization label is one of the valid labels
        assert util["utilization_label"] in ("healthy", "medium-risk", "high-risk", "unknown")
        
        # For user_good with healthy spending, expect healthy or medium-risk
        # (not high-risk since they don't overspend)
        assert util["utilization_label"] in ("healthy", "medium-risk")
        
        # Verify other fields are present
        assert "utilization_pct" in util
        assert "avg_daily_spend_cents" in util
        assert "burn_days" in util
        assert "cycle_start" in util
        assert "cycle_end" in util


class TestRiskCalculationSmoke:
    """Smoke tests for RiskCalculationService using real transaction data."""

    def test_calculate_risk_smoke(self):
        """
        Smoke test for risk calculation with user_good transactions.
        Verifies that the risk calculation service returns expected fields.
        """
        raw = load_transactions("transactions_user_good.json")
        txs = normalize_transactions(raw["transactions"])

        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)

        # Verify the result contains expected risk score fields
        assert "final_score" in result or hasattr(result, "final_score")
        assert "limit_amount" in result or hasattr(result, "limit_amount")
        
        # Verify additional important fields
        assert "limit_bucket" in result
        assert "avg_daily_balance_cents" in result
        assert "monthly_income_cents" in result
        assert "monthly_spend_cents" in result
        assert "nsf_count" in result
        assert "component_scores" in result
        
        # For user_good, expect a reasonable score (not the worst case)
        assert result["final_score"] > 0
        
        # User_good should have zero NSF events
        assert result["nsf_count"] == 0

    def test_calculate_risk_smoke_user_gig(self):
        """
        Smoke test for risk calculation with user_gig transactions.
        Verifies that the risk calculation service returns expected fields.
        """
        raw = load_transactions("transactions_user_gig.json")
        txs = normalize_transactions(raw["transactions"])
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        assert result["final_score"] > 0
        assert result["avg_daily_balance_cents"] == -231075 
        assert result["utilization_info"]["utilization_pct"] == 100.0
        assert result["utilization_info"]["utilization_label"] == "high-risk"
        assert result["component_scores"]["balance_score"] == 0.0
        assert result["component_scores"]["income_spend_score"] == 26.4
        assert result["component_scores"]["nsf_score"] == 0.0
        assert result["final_score"] == 0.0
        assert result["limit_bucket"] == "0"
        assert result["limit_amount"] == 0
        assert result["reasons"] == ["avg_daily_balance_negative", "monthly_income < monthly_spend", "0 overdraft/nsf events", "high cycle utilization (user burns paycheck quickly)"]

    def test_calculate_risk_smoke_user_highutil(self):
        """
        Smoke test for risk calculation with user_highutil transactions.
        Verifies that the risk calculation service returns expected fields.
        """
        raw = load_transactions("transactions_user_highutil.json")
        txs = normalize_transactions(raw["transactions"])
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        assert result["final_score"] > 0
        assert result["avg_daily_balance_cents"] == -1218279
        assert result["utilization_info"]["utilization_pct"] == 100.0
        assert result["utilization_info"]["utilization_label"] == "high-risk"
        assert result["component_scores"]["balance_score"] == 0.0
        assert result["component_scores"]["income_spend_score"] == 26.4
        assert result["component_scores"]["nsf_score"] == 0.0
        assert result["final_score"] == 0.0
        assert result["limit_bucket"] == "0"
        assert result["limit_amount"] == 0
        assert result["reasons"] == ["avg_daily_balance_negative", "monthly_income < monthly_spend", "0 overdraft/nsf events", "high cycle utilization (user burns paycheck quickly)"]
    
    def test_calculate_risk_smoke_user_overdraft(self):
        """
        Smoke test for risk calculation with user_overdraft transactions.
        Verifies that the risk calculation service returns expected fields.
        """
        raw = load_transactions("transactions_user_overdraft.json")
        txs = normalize_transactions(raw["transactions"])
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        assert result["final_score"] > 0
        assert result["avg_daily_balance_cents"] == -1218279