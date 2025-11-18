from datetime import datetime
from domain.entities import Decision, Plan, Transaction, User
from domain.services.risk_calculation import RiskCalculationService

class TestRiskCalculationService:
    def test_risk_calculation_service_calculate_risk_with_transactions_zero_case(self):
        risk_calculation_service = RiskCalculationService()
        transactions = [Transaction(transaction_id="1", date=datetime.now(), amount_cents=0, type="credit", description="Salary", category="income", merchant="Bank", balance_cents=10, nsf=False)]
        risk_score = risk_calculation_service.calculate_risk(transactions)
        assert risk_score["avg_daily_balance_cents"] == 10.0
        assert risk_score["component_scores"]["balance_score"] == 100.0
        assert risk_score["component_scores"]["income_spend_score"] == 100.0
        assert risk_score["component_scores"]["nsf_score"] == 100.0
        assert risk_score["final_score"] == 100.0
        assert risk_score["limit_bucket"] == "1000"

    def test_risk_calculation_service_calculate_risk_with_transactions_good_case(self):
        risk_calculation_service = RiskCalculationService()
        tuple_transactions = [
            # date, amount, type, description, category, merchant, balance, nsf
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", 1000, False),
            (datetime.now(), 2000, "credit", "Salary", "income", "Bank", 3000, False),
            (datetime.now(), 3000, "debit", "Rent", "housing", "Landlord", 0, False),
        ]
        transactions = [Transaction(transaction_id=str(i), 
            date=date, 
            amount_cents=amount, 
            type=type, 
            description=description, 
            category=category, 
            merchant=merchant, 
            balance_cents=balance, 
            nsf=nsf
        ) for i, (date, amount, type, description, category, merchant, balance, nsf) in enumerate[tuple[datetime, int, str, str, str, str, int, bool]](tuple_transactions)]
        risk_score = risk_calculation_service.calculate_risk(transactions)
        # {'avg_daily_balance_cents': 1000, 'component_scores': {'balance_score': 100.0, 'income_spend_score': 50.0, 'nsf_score': 100.0}, 'final_score': 85.0, 'limit_bucket': '1000', ...}
        assert risk_score["avg_daily_balance_cents"] == 1000
        assert risk_score["component_scores"]["balance_score"] == 100.0
        assert risk_score["component_scores"]["income_spend_score"] == 50.0
        assert risk_score["component_scores"]["nsf_score"] == 100.0
        assert risk_score["final_score"] == 85.0
        assert risk_score["limit_bucket"] == "1000"

    def test_risk_calculation_service_calculate_risk_with_transactions_bad_case(self):
        risk_calculation_service = RiskCalculationService()

        tuple_transactions = [
            # date, amount, type, description, category, merchant, balance, nsf
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", 1000, False),
            (datetime.now(), 2000, "credit", "Salary", "income", "Bank", 3000, False),
            (datetime.now(), 3000, "debit", "Rent", "housing", "Landlord", 0, False),
            (datetime.now(), 4000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -1000, False),
            (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -2000, True),
        ]
        transactions = [Transaction(transaction_id=str(i), 
            date=date, 
            amount_cents=amount, 
            type=type, 
            description=description, 
            category=category, 
            merchant=merchant, 
            balance_cents=balance, 
            nsf=nsf
        ) for i, (date, amount, type, description, category, merchant, balance, nsf) in enumerate[tuple[datetime, int, str, str, str, str, int, bool]](tuple_transactions)]
        risk_score = risk_calculation_service.calculate_risk(transactions)
        assert risk_score["avg_daily_balance_cents"] == 1000
        assert risk_score["component_scores"]["balance_score"] == 100.0    
        assert risk_score["nsf_count"] > 0.0
        assert risk_score["final_score"] < 85.0
        assert risk_score["limit_bucket"] == "500"

    def test_risk_calculation_service_calculate_risk_with_transactions_very_bad_case(self):
        risk_calculation_service = RiskCalculationService()
        tuple_transactions = [
            # date, amount, type, description, category, merchant, balance, nsf
            (datetime.now(), 2000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -4000, False),
            (datetime.now(), 2000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -6000, False),
            (datetime.now(), 2000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -8000, False),
        ]
        transactions = [Transaction(transaction_id=str(i), 
            date=date, 
            amount_cents=amount, 
            type=type, 
            description=description, 
            category=category, 
            merchant=merchant, 
            balance_cents=balance, 
            nsf=nsf
        ) for i, (date, amount, type, description, category, merchant, balance, nsf) in enumerate[tuple[datetime, int, str, str, str, str, int, bool]](tuple_transactions)]
        risk_score = risk_calculation_service.calculate_risk(transactions)
        assert risk_score["avg_daily_balance_cents"] == -4000
        assert risk_score["component_scores"]["balance_score"] == 60.0
        assert risk_score["component_scores"]["income_spend_score"] == 0.0
        assert risk_score["component_scores"]["nsf_score"] == 25.0
        assert risk_score["final_score"] == 35.0
        assert risk_score["limit_bucket"] == "100-400"

    def test_risk_calculation_service_calculate_risk_with_transactions_worst_case(self):
        risk_calculation_service = RiskCalculationService()
        tuple_transactions = [
            # date, amount, type, description, category, merchant, balance, nsf
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
        transactions = [Transaction(transaction_id=str(i), 
            date=date, 
            amount_cents=amount, 
            type=type, 
            description=description, 
            category=category, 
            merchant=merchant, 
            balance_cents=balance, 
            nsf=nsf
        ) for i, (date, amount, type, description, category, merchant, balance, nsf) in enumerate[tuple[datetime, int, str, str, str, str, int, bool]](tuple_transactions)]
        risk_score = risk_calculation_service.calculate_risk(transactions)
        assert risk_score["avg_daily_balance_cents"] == -10000
        assert risk_score["component_scores"]["balance_score"] == 0.0
        assert risk_score["component_scores"]["income_spend_score"] == 0.0
        assert risk_score["component_scores"]["nsf_score"] == 0.0
        assert risk_score["final_score"] == 0.0
        assert risk_score["limit_bucket"] == "0"