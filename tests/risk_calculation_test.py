"""
Tests for RiskCalculationService with BNPL tiers.
"""
from datetime import datetime
from domain.entities import Transaction
from domain.services.risk_calculation import RiskCalculationService


class TestRiskCalculationService:
    """Tests for the risk calculation service."""
    
    def test_risk_calculation_service_calculate_risk_with_transactions_zero_case(self):
        """Test with minimal transaction - should get approved."""
        risk_calculation_service = RiskCalculationService()
        transactions = [
            Transaction(
                transaction_id="1", 
                date=datetime.now(), 
                amount_cents=0, 
                type="credit", 
                description="Salary", 
                category="income", 
                merchant="Bank", 
                balance_cents=10, 
                nsf=False
            )
        ]
        risk_score = risk_calculation_service.calculate_risk(transactions)
        
        assert risk_score["avg_daily_balance_cents"] == 10
        assert risk_score["component_scores"]["balance_score"] == 100.0
        assert risk_score["component_scores"]["income_spend_score"] == 100.0
        assert risk_score["component_scores"]["nsf_score"] == 100.0
        # With new BNPL tiers, high score gets approved
        assert risk_score["approved"] is True
        assert "Tier" in risk_score["limit_bucket"] or risk_score["limit_bucket"] == "Deny"

    def test_risk_calculation_service_calculate_risk_with_transactions_good_case(self):
        """Test with balanced spending - should get approved."""
        risk_calculation_service = RiskCalculationService()
        tuple_transactions = [
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", 1000, False),
            (datetime.now(), 2000, "credit", "Salary", "income", "Bank", 3000, False),
            (datetime.now(), 3000, "debit", "Rent", "housing", "Landlord", 0, False),
        ]
        transactions = [
            Transaction(
                transaction_id=str(i), 
                date=date, 
                amount_cents=amount, 
                type=type_, 
                description=description, 
                category=category, 
                merchant=merchant, 
                balance_cents=balance, 
                nsf=nsf
            ) for i, (date, amount, type_, description, category, merchant, balance, nsf) in enumerate(tuple_transactions)
        ]
        risk_score = risk_calculation_service.calculate_risk(transactions)
        
        assert risk_score["avg_daily_balance_cents"] == 1000
        assert risk_score["component_scores"]["balance_score"] == 100.0
        assert risk_score["component_scores"]["income_spend_score"] == 50.0
        assert risk_score["component_scores"]["nsf_score"] == 100.0
        # Should be approved with reasonable tier
        assert risk_score["final_score"] > 0
        assert "utilization_info" in risk_score
        assert "payback_capacity" in risk_score

    def test_risk_calculation_service_calculate_risk_with_transactions_bad_case(self):
        """Test with NSF events - should get lower tier or denied."""
        risk_calculation_service = RiskCalculationService()
        tuple_transactions = [
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", 1000, False),
            (datetime.now(), 2000, "credit", "Salary", "income", "Bank", 3000, False),
            (datetime.now(), 3000, "debit", "Rent", "housing", "Landlord", 0, False),
            (datetime.now(), 4000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -1000, False),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -2000, True),
        ]
        transactions = [
            Transaction(
                transaction_id=str(i), 
                date=date, 
                amount_cents=amount, 
                type=type_, 
                description=description, 
                category=category, 
                merchant=merchant, 
                balance_cents=balance, 
                nsf=nsf
            ) for i, (date, amount, type_, description, category, merchant, balance, nsf) in enumerate(tuple_transactions)
        ]
        risk_score = risk_calculation_service.calculate_risk(transactions)
        
        assert risk_score["avg_daily_balance_cents"] == 1000
        assert risk_score["component_scores"]["balance_score"] == 100.0
        assert risk_score["nsf_count"] > 0
        # With NSF events, score should be lower
        assert risk_score["final_score"] < 85.0

    def test_risk_calculation_service_calculate_risk_with_transactions_very_bad_case(self):
        """Test with negative balance and only debits - should get low tier or denied."""
        risk_calculation_service = RiskCalculationService()
        tuple_transactions = [
            (datetime.now(), 2000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -4000, False),
            (datetime.now(), 2000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -6000, False),
            (datetime.now(), 2000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -8000, False),
        ]
        transactions = [
            Transaction(
                transaction_id=str(i), 
                date=date, 
                amount_cents=amount, 
                type=type_, 
                description=description, 
                category=category, 
                merchant=merchant, 
                balance_cents=balance, 
                nsf=nsf
            ) for i, (date, amount, type_, description, category, merchant, balance, nsf) in enumerate(tuple_transactions)
        ]
        risk_score = risk_calculation_service.calculate_risk(transactions)
        
        assert risk_score["avg_daily_balance_cents"] == -4000
        assert risk_score["component_scores"]["balance_score"] == 60.0
        assert risk_score["component_scores"]["income_spend_score"] == 0.0
        # With negative balance and no income, should be low tier or denied
        assert risk_score["final_score"] < 50

    def test_risk_calculation_service_calculate_risk_with_transactions_worst_case(self):
        """Test with worst case - deeply negative, NSF - should be denied."""
        risk_calculation_service = RiskCalculationService()
        tuple_transactions = [
            (datetime.now(), 4000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -10000, False),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -20000, True),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -30000, False),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -40000, False),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -50000, False),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -60000, False),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -70000, False),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -80000, False),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -90000, False),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -100000, False),
        ]
        transactions = [
            Transaction(
                transaction_id=str(i), 
                date=date, 
                amount_cents=amount, 
                type=type_, 
                description=description, 
                category=category, 
                merchant=merchant, 
                balance_cents=balance, 
                nsf=nsf
            ) for i, (date, amount, type_, description, category, merchant, balance, nsf) in enumerate(tuple_transactions)
        ]
        risk_score = risk_calculation_service.calculate_risk(transactions)
        
        assert risk_score["avg_daily_balance_cents"] == -10000
        assert risk_score["component_scores"]["balance_score"] == 0.0
        assert risk_score["component_scores"]["income_spend_score"] == 0.0
        assert risk_score["component_scores"]["nsf_score"] == 0.0
        assert risk_score["final_score"] == 0.0
        # BNPL philosophy: everyone gets approved, worst case gets Tier D (smallest limit)
        assert risk_score["limit_bucket"] == "Tier D"
        assert risk_score["approved"] is True
        assert risk_score["limit_amount"] == 2000  # $20 trial limit
