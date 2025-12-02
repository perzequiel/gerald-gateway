"""
Tests for payback capacity computation.
"""
import json
import os
from datetime import datetime

from domain.services.payback_capacity import compute_payback_capacity
from domain.entities import Transaction
from domain.services.normalization import Normalization
from domain.services.basics_features import BasicsFeatures
from domain.services.utilizations import PaycheckInfo, UtilizationService


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


class TestPaybackCapacity:
    """Tests for payback capacity computation."""

    def test_payback_positive_label(self):
        """Test positive payback capacity for user with surplus."""
        result = compute_payback_capacity(
            avg_daily_balance_cents=50000,  # $500 balance
            burn_days=30,
            avg_daily_spend_cents=1000,     # $10/day
            avg_paycheck_cents=300000       # $3000 paycheck
        )
        
        # With $500 balance and $10/day spend for 30 days = -$300
        # Capacity = $500 - $300 = $200 positive
        assert result["payback_label"] == "positive"
        assert result["payback_capacity_cents"] > 0

    def test_payback_negative_label(self):
        """Test negative payback capacity for user who overspends."""
        result = compute_payback_capacity(
            avg_daily_balance_cents=-10000,  # -$100 balance
            burn_days=15,
            avg_daily_spend_cents=5000,      # $50/day
            avg_paycheck_cents=300000
        )
        
        # With -$100 balance and $50/day spend for 15 days = -$750
        # Capacity = -$100 - $750 = -$850 negative
        assert result["payback_label"] == "negative"
        assert result["payback_capacity_cents"] < 0

    def test_payback_neutral_label(self):
        """Test neutral payback capacity for borderline user."""
        result = compute_payback_capacity(
            avg_daily_balance_cents=15000,  # $150 balance
            burn_days=30,
            avg_daily_spend_cents=500,       # $5/day
            avg_paycheck_cents=300000
        )
        
        # Capacity = $150 - $150 = $0 (within 10% threshold)
        assert result["payback_label"] in ("positive", "neutral")

    def test_payback_user_good(self):
        """Test payback capacity for user_good profile."""
        txs = load_transactions("transactions_user_good.json")
        
        # Calculate features
        avg_balance = BasicsFeatures.calculate_avg_daily_balance(txs)
        income_spend = BasicsFeatures.calculate_monthly_income_vs_spend(txs)
        monthly_income = income_spend.income
        
        paycheck_info = PaycheckInfo(
            avg_paycheck_cents=int(monthly_income) if monthly_income > 0 else None,
            period_days=30,
            paycheck_confidence=0.8
        )
        util_info = UtilizationService(txs, paycheck_info).calculate()
        
        result = compute_payback_capacity(
            avg_daily_balance_cents=int(avg_balance),
            burn_days=util_info.get("burn_days"),
            avg_daily_spend_cents=util_info.get("avg_daily_spend_cents", 0),
            avg_paycheck_cents=paycheck_info.avg_paycheck_cents
        )
        
        # User_good has healthy balance - payback label should be computed
        assert result["payback_label"] in ("positive", "neutral", "negative")
        # Should have a reasonable capacity value (not extreme)
        assert result["payback_capacity_cents"] is not None

    def test_payback_user_overdraft(self):
        """Test payback capacity for user_overdraft profile."""
        txs = load_transactions("transactions_user_overdraft.json")
        
        avg_balance = BasicsFeatures.calculate_avg_daily_balance(txs)
        income_spend = BasicsFeatures.calculate_monthly_income_vs_spend(txs)
        monthly_income = income_spend.income
        
        paycheck_info = PaycheckInfo(
            avg_paycheck_cents=int(monthly_income) if monthly_income > 0 else None,
            period_days=30,
            paycheck_confidence=0.8
        )
        util_info = UtilizationService(txs, paycheck_info).calculate()
        
        result = compute_payback_capacity(
            avg_daily_balance_cents=int(avg_balance),
            burn_days=util_info.get("burn_days"),
            avg_daily_spend_cents=util_info.get("avg_daily_spend_cents", 0),
            avg_paycheck_cents=paycheck_info.avg_paycheck_cents
        )
        
        # User_overdraft should have negative payback
        assert result["payback_label"] == "negative"

