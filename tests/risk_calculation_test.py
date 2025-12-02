from datetime import datetime
from domain.entities import Decision, Plan, Transaction, User
from domain.services.risk_calculation import RiskCalculationService

def calc_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")

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
        # Note: utilization is 200% (debits $40 vs income $20), so expect high-risk label
        assert risk_score["utilization_info"]["utilization_label"] in ("high-risk", "very-high-risk", "critical-risk")
        assert risk_score["component_scores"]["balance_score"] == 100.0
        assert risk_score["component_scores"]["income_spend_score"] == 50.0
        assert risk_score["component_scores"]["nsf_score"] == 100.0
        assert risk_score["final_score"] == 85.0
        assert risk_score["limit_bucket"] == "1000"

    def test_risk_calculation_service_calculate_risk_with_transactions_bad_case_highutil(self):
        risk_calculation_service = RiskCalculationService()

        tuple_transactions = [
            # date, amount, type, description, category, merchant, balance, nsf
            # (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", 1000, False),
            # (datetime.now(), 2000, "credit", "Salary", "income", "Bank", 3000, False),
            # (datetime.now(), 3000, "debit", "Rent", "housing", "Landlord", 0, False),
            # (datetime.now(), 4000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -1000, False),
            # (datetime.now(), 1000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -2000, True),
            (calc_date("2025-06-20"), 14491, "debit", "Online Marketplace", "shopping", "Online Marketplace", 55509, False),
            (calc_date("2025-06-20"), 9384, "debit", "SuperMart Purchase", "groceries", "SuperMart Purchase", 46125, False),
            (calc_date("2025-06-21"), 30160, "debit", "FoodiePlace", "restaurants", "FoodiePlace", 15965, False),
            (calc_date("2025-06-23"), 20789, "debit", "SuperMart Purchase", "groceries", "SuperMart Purchase", -4824, False),
            (calc_date("2025-06-23"), 12598, "debit", "SuperMart Purchase", "groceries", "SuperMart Purchase", -17422, False),
            (calc_date("2025-06-24"), 13783, "debit", "SuperMart Purchase", "groceries", "SuperMart Purchase", -31205, False),
            (calc_date("2025-06-24"), 48214, "debit", "Online Marketplace", "shopping", "Online Marketplace", -79419, False),
            (calc_date("2025-06-25"), 21139, "debit", "Utility Bill", "utilities", "Utility Bill", -100558, False),
            (calc_date("2025-06-26"), 26921, "debit", "Utility Bill", "utilities", "Utility Bill", -127479, False),
            (calc_date("2025-06-27"), 77874, "debit", "Online Marketplace", "shopping", "Online Marketplace", -205353, False),
            (calc_date("2025-06-27"), 74288, "debit", "RideShare", "transport", "RideShare", -279641, False),
            (calc_date("2025-06-27"), 30498, "debit", "Utility Bill", "utilities", "Utility Bill", -310139, False),
            (calc_date("2025-06-29"), 14016, "debit", "Utility Bill", "utilities", "Utility Bill", -324155, False),
            (calc_date("2025-06-30"), 180000, "credit", "Direct Deposit - Payroll", "income", "Employer Inc", -144155, False),
            (calc_date("2025-06-30"), 65470, "debit", "RideShare", "transport", "RideShare", -209625, False),
            (calc_date("2025-06-30"), 72756, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -282381, False),
            (calc_date("2025-07-01"), 6253, "debit", "Utility Bill", "utilities", "Utility Bill", -288634, False),
            (calc_date("2025-07-02"), 14138, "debit", "Online Marketplace", "shopping", "Online Marketplace", -302772, False),
            (calc_date("2025-07-03"), 49235, "debit", "RideShare", "transport", "RideShare", -352007, False),
            (calc_date("2025-07-03"), 45832, "debit", "SuperMart Purchase", "groceries", "SuperMart Purchase", -397839, False),
            (calc_date("2025-07-04"), 38523, "debit", "Utility Bill", "utilities", "Utility Bill", -436362, False),
            (calc_date("2025-07-04"), 500, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -436862, False),
            (calc_date("2025-07-06"), 51724, "debit", "SuperMart Purchase", "groceries", "SuperMart Purchase", -488586, False),
            (calc_date("2025-07-07"), 3069, "credit", "Merchant Refund", "refund", None, -485517, False),
            (calc_date("2025-07-08"), 59039, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -544556, False),
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
        assert risk_score["avg_daily_balance_cents"] < 0  # Negative balance expected
        assert risk_score["utilization_info"]["utilization_label"] in ("high-risk", "very-high-risk", "critical-risk")
        assert risk_score["component_scores"]["balance_score"] == 0.0    
        assert risk_score["nsf_count"] > 0
        assert risk_score["final_score"] < 85.0
        assert risk_score["limit_bucket"] == "0"

    def test_risk_calculation_service_calculate_risk_with_transactions_very_bad_case_overdraft(self):
        risk_calculation_service = RiskCalculationService()
        tuple_transactions = [
            # date, amount, type, description, category, merchant, balance, nsf
            # (datetime.now(), 2000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -4000, False),
            # (datetime.now(), 2000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -6000, False),
            # (datetime.now(), 2000, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -8000, False),
            (calc_date("2025-09-01"), 13335, "debit", "Online Marketplace", "shopping", "Online Marketplace", -1121493, False),
            (calc_date("2025-09-02"), 17802, "debit", "Online Marketplace", "shopping", "Online Marketplace", -1139295, False),
            (calc_date("2025-09-03"), 3500, "debit", "Overdraft/NSF Fee", "fees", None, -1142795, False),
            (calc_date("2025-09-04"), 19008, "debit", "Online Marketplace", "shopping", "Online Marketplace", -1161803, False),
            (calc_date("2025-09-04"), 27282, "debit", "SuperMart Purchase", "groceries", "SuperMart Purchase", -1189085, False),
            (calc_date("2025-09-05"), 46073, "debit", "SuperMart Purchase", "groceries", "SuperMart Purchase", -1235158, False),
            (calc_date("2025-09-06"), 500, "debit", "Online Marketplace", "shopping", "Online Marketplace", -1235658, False),
            (calc_date("2025-09-06"), 6818, "debit", "Utility Bill", "utilities", "Utility Bill", -1242476, False),
            (calc_date("2025-09-07"), 1149, "debit", "Utility Bill", "utilities", "Utility Bill", -1243625, False),
            (calc_date("2025-09-07"), 3500, "debit", "Overdraft/NSF Fee", "fees", None, -1247125, False),
            (calc_date("2025-09-08"), 120000, "credit", "Direct Deposit - Payroll", "income", "Employer Inc", -1127125, False),
            (calc_date("2025-09-08"), 43874, "debit", "Online Marketplace", "shopping", "Online Marketplace", -1170999, False),
            (calc_date("2025-09-10"), 3500, "debit", "Overdraft/NSF Fee", "fees", None, -1174499, False),
            (calc_date("2025-09-11"), 21646, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -1196145, False),
            (calc_date("2025-09-12"), 3500, "debit", "Overdraft/NSF Fee", "fees", None, -1199645, False),
            (calc_date("2025-09-13"), 15682, "debit", "Utility Bill", "utilities", "Utility Bill", -1215327, False),
            (calc_date("2025-09-13"), 7857, "debit", "FoodiePlace", "restaurants", "FoodiePlace", -1223184, False),
            (calc_date("2025-09-14"), 45812, "debit", "RideShare", "transport", "RideShare", -1268996, False),
            (calc_date("2025-09-14"), 23407, "debit", "Utility Bill", "utilities", "Utility Bill", -1292403, False),
            (calc_date("2025-09-15"), 11737, "debit", "RideShare", "transport", "RideShare", -1304140, False),
            (calc_date("2025-09-15"), 54164, "debit", "Online Marketplace", "shopping", "Online Marketplace", -1358304, False),
            (calc_date("2025-09-15"), 3500, "debit", "Overdraft/NSF Fee", "fees", None, -1361804, False),
            (calc_date("2025-09-16"), 32138, "debit", "RideShare", "transport", "RideShare", -1393942, False),
            (calc_date("2025-09-17"), 30034, "debit", "Online Marketplace", "shopping", "Online Marketplace", -1423976, False),
            (calc_date("2025-09-17"), 19387, "debit", "SuperMart Purchase", "groceries", "SuperMart Purchase", -1443363, False),
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
        assert risk_score["avg_daily_balance_cents"] < 0  # Negative balance expected
        assert risk_score["utilization_info"]["utilization_label"] in ("high-risk", "very-high-risk", "critical-risk")
        assert risk_score["component_scores"]["balance_score"] == 0.0
        # Income vs spend score depends on monthly calculation
        assert risk_score["component_scores"]["income_spend_score"] >= 0
        assert risk_score["final_score"] <= 15.0  # Very low score expected for overdraft user
        assert risk_score["limit_bucket"] == "0"

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
        assert risk_score["utilization_info"]["utilization_label"] == "unknown"
        assert risk_score["component_scores"]["balance_score"] == 0.0
        assert risk_score["component_scores"]["income_spend_score"] == 0.0
        assert risk_score["component_scores"]["nsf_score"] == 0.0
        assert risk_score["final_score"] == 0.0
        assert risk_score["limit_bucket"] == "0"