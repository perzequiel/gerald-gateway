"""
Unit tests for utilization service and integration tests with real transaction data.
"""
import json
import os
from datetime import datetime

from domain.entities import Transaction
from domain.services.utilizations import PaycheckInfo, UtilizationService, UtilizationConfig
from domain.services.normalization import Normalization
from domain.services.basics_features import BasicsFeatures
from domain.services.risk_calculation import RiskCalculationService


# Valid utilization labels after Gaussian scoring update
VALID_LABELS = ("healthy", "medium-risk", "high-risk", "very-high-risk", "critical-risk", "unknown")


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


def get_dynamic_paycheck(txs: list[Transaction]) -> PaycheckInfo:
    """Calculate PaycheckInfo dynamically from transaction income."""
    income_vs_spend = BasicsFeatures.calculate_monthly_income_vs_spend(txs)
    monthly_income = income_vs_spend.income
    return PaycheckInfo(
        avg_paycheck_cents=int(monthly_income) if monthly_income > 0 else 300000,
        period_days=30,
        paycheck_confidence=0.8 if monthly_income > 0 else 0.0
    )


class TestUtilizationIntegration:
    """Integration tests for utilization service using real transaction data."""

    def test_utilization_integration_user_good(self):
        """
        Test utilization calculation with user_good transactions.
        Verifies that the utilization service correctly computes utilization
        metrics for a user with healthy spending patterns using dynamic paycheck.
        """
        raw = load_transactions("transactions_user_good.json")
        txs = normalize_transactions(raw["transactions"])

        # Use dynamic paycheck calculation (like RiskCalculationService does)
        paycheck_info = get_dynamic_paycheck(txs)

        # Compute utilization using the service
        util_service = UtilizationService(txs, paycheck_info)
        util = util_service.calculate()

        # Assert utilization label is one of the valid labels
        assert util["utilization_label"] in VALID_LABELS
        
        # Verify all required fields are present
        assert "utilization_pct" in util
        assert "avg_daily_spend_cents" in util
        assert "burn_days" in util
        assert "composite_score" in util
        assert "component_scores" in util
        assert "cycle_start" in util
        assert "cycle_end" in util
        
        # Composite score should be calculated
        assert util["composite_score"] >= 0 and util["composite_score"] <= 100
        
        # Component scores should be present
        cs = util["component_scores"]
        assert "utilization_score" in cs
        assert "burn_days_score" in cs
        assert "daily_spend_score" in cs
        assert "weights" in cs


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
        assert "utilization_info" in result
        
        # Verify utilization_info has Gaussian scoring fields
        util_info = result["utilization_info"]
        assert "composite_score" in util_info
        assert "component_scores" in util_info
        assert util_info["utilization_label"] in VALID_LABELS

    def test_calculate_risk_smoke_user_gig(self):
        """
        Smoke test for risk calculation with user_gig transactions.
        User_gig represents a gig worker with irregular income.
        Validates that the scoring system handles gig economy patterns.
        """
        raw = load_transactions("transactions_user_gig.json")
        txs = normalize_transactions(raw["transactions"])
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        
        # GIG user has irregular income - verify basic structure
        assert "avg_daily_balance_cents" in result
        assert "utilization_info" in result
        
        # GIG user utilization should reflect high spending patterns
        util_info = result["utilization_info"]
        assert util_info["utilization_label"] in VALID_LABELS
        
        # Gig workers typically have tighter margins
        assert result["final_score"] <= 80  # Should not be top tier

    def test_calculate_risk_smoke_user_highutil(self):
        """
        Smoke test for risk calculation with user_highutil transactions.
        User_highutil represents a user with high credit utilization.
        """
        raw = load_transactions("transactions_user_highutil.json")
        txs = normalize_transactions(raw["transactions"])
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        
        # HIGHUTIL user has high spending - verify structure
        assert "avg_daily_balance_cents" in result
        assert "utilization_info" in result
        
        # High utilization user should not get top tier
        util_info = result["utilization_info"]
        assert util_info["utilization_label"] in VALID_LABELS
        
        # Final score reflects the high utilization risk
        assert result["final_score"] < 80  # Should not be premium tier
        
        # Verify penalties are applied
        assert "penalties_applied" in result
    
    def test_calculate_risk_smoke_user_overdraft(self):
        """
        Smoke test for risk calculation with user_overdraft transactions.
        User_overdraft represents a user with overdraft history (NSF events).
        Expected: NSF events detected, lower score.
        """
        raw = load_transactions("transactions_user_overdraft.json")
        txs = normalize_transactions(raw["transactions"])
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs)
        
        # OVERDRAFT user should have NSF events detected
        assert result["nsf_count"] > 0  # Has NSF events in data
        
        # OVERDRAFT user should have negative balance
        assert result["avg_daily_balance_cents"] < 0
        
        # NSF score should be penalized
        assert result["component_scores"]["nsf_score"] < 100
        
        # User should likely be denied or get low tier
        assert result["limit_bucket"] in ("Deny", "Tier D", "Tier C")


class TestGaussianScoring:
    """Tests for the Gaussian scoring mechanism in UtilizationService."""

    def test_gaussian_score_at_ideal(self):
        """Test that Gaussian score is 1.0 at the ideal value."""
        score = UtilizationService._gaussian_score(0.6, mu=0.6, sigma=0.3)
        assert score == 1.0

    def test_gaussian_score_drops_away_from_ideal(self):
        """Test that Gaussian score drops as value moves away from ideal."""
        ideal_score = UtilizationService._gaussian_score(0.6, mu=0.6, sigma=0.3)
        away_score = UtilizationService._gaussian_score(1.0, mu=0.6, sigma=0.3)
        far_score = UtilizationService._gaussian_score(2.0, mu=0.6, sigma=0.3)
        
        assert ideal_score > away_score > far_score
        assert ideal_score == 1.0
        assert far_score < 0.1  # Should be very low

    def test_asymmetric_gaussian_penalizes_overspending(self):
        """Test that asymmetric Gaussian penalizes overspending more than underspending."""
        under_spend = UtilizationService._asymmetric_gaussian_score(
            0.4, mu=0.6, sigma_left=0.5, sigma_right=0.25
        )
        over_spend = UtilizationService._asymmetric_gaussian_score(
            0.8, mu=0.6, sigma_left=0.5, sigma_right=0.25
        )
        
        # Both are 0.2 away from ideal, but overspending should be penalized more
        assert under_spend > over_spend

    def test_label_thresholds(self):
        """Test that labels map correctly to score thresholds."""
        service = UtilizationService.__new__(UtilizationService)
        
        assert service._score_to_label(85) == "healthy"
        assert service._score_to_label(70) == "medium-risk"
        assert service._score_to_label(50) == "high-risk"
        assert service._score_to_label(25) == "very-high-risk"
        assert service._score_to_label(10) == "critical-risk"


class TestUtilizationConfig:
    """Tests for custom configuration of UtilizationService."""

    def test_custom_config_changes_scoring(self):
        """Test that custom config parameters affect the scoring."""
        raw = load_transactions("transactions_user_good.json")
        txs = normalize_transactions(raw["transactions"])
        paycheck_info = get_dynamic_paycheck(txs)
        
        # Default config
        default_service = UtilizationService(txs, paycheck_info)
        default_result = default_service.calculate()
        
        # More lenient config - higher thresholds for healthy
        lenient_config = UtilizationConfig(
            utilization_params=(0.9, 0.4, 0.45),  # Higher ideal util
            burn_days_params=(20.0, 20.0, 0.35),  # Lower burn days ideal
            daily_spend_params=(0.05, 0.03, 0.20), # Higher daily spend ideal
            label_thresholds=[
                (60, "healthy"),        # Lower threshold for healthy
                (40, "medium-risk"),
                (20, "high-risk"),
                (10, "very-high-risk"),
                (0, "critical-risk"),
            ],
            load_from_env=False
        )
        lenient_service = UtilizationService(txs, paycheck_info, config=lenient_config)
        lenient_result = lenient_service.calculate()
        
        # Both should have valid results
        assert default_result["utilization_label"] in VALID_LABELS
        assert lenient_result["utilization_label"] in VALID_LABELS
        
        # Lenient config should produce different (possibly better) label
        # since thresholds are lower
        assert lenient_result["composite_score"] != default_result["composite_score"]

    def test_config_validates_weights(self):
        """Test that config raises error if weights don't sum to 1.0."""
        import pytest
        
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            UtilizationConfig(
                utilization_params=(0.6, 0.3, 0.5),   # weight 0.5
                burn_days_params=(30.0, 15.0, 0.5),   # weight 0.5
                daily_spend_params=(0.033, 0.02, 0.5), # weight 0.5 = total 1.5!
                load_from_env=False
            )

    def test_config_default_values(self):
        """Test that default config uses expected values."""
        config = UtilizationConfig(load_from_env=False)
        
        assert config.utilization_params == (0.6, 0.3, 0.45)
        assert config.burn_days_params == (30.0, 15.0, 0.35)
        assert config.daily_spend_params == (0.033, 0.02, 0.20)
        assert len(config.label_thresholds) == 5
        assert config.label_thresholds[0] == (80, "healthy")
