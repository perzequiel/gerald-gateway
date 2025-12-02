"""
Tests for cooldown mechanism.
"""
import json
import os
from datetime import datetime, timedelta

from domain.services.cooldown import compute_cooldown, DEFAULT_COOLDOWN_HOURS
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


class TestCooldown:
    """Tests for cooldown computation."""

    def test_no_events_no_cooldown(self):
        """No events means no cooldown."""
        result = compute_cooldown(user_events=None, transactions=None)
        
        assert result["is_in_cooldown"] is False
        assert result["remaining_hours"] is None

    def test_old_advance_no_cooldown(self):
        """Advance taken > 72 hours ago should not trigger cooldown."""
        old_advance = datetime.now() - timedelta(hours=100)
        events = [
            {"type": "advance_taken", "timestamp": old_advance.isoformat()}
        ]
        
        result = compute_cooldown(user_events=events)
        
        assert result["is_in_cooldown"] is False
        assert result["remaining_hours"] == 0

    def test_recent_advance_triggers_cooldown(self):
        """Advance taken within 72 hours should trigger cooldown."""
        recent_advance = datetime.now() - timedelta(hours=24)
        events = [
            {"type": "advance_taken", "timestamp": recent_advance.isoformat()}
        ]
        
        result = compute_cooldown(user_events=events)
        
        assert result["is_in_cooldown"] is True
        assert result["remaining_hours"] is not None
        assert result["remaining_hours"] > 40  # ~48 hours remaining

    def test_cooldown_blocks_decision(self):
        """Cooldown should block new advances in calculate_risk."""
        txs = load_transactions("transactions_user_good.json")
        
        # Simulate recent advance
        recent_advance = datetime.now() - timedelta(hours=12)
        events = [
            {"type": "advance_taken", "timestamp": recent_advance.isoformat()}
        ]
        
        svc = RiskCalculationService()
        result = svc.calculate_risk(txs, user_events=events)
        
        # Should be denied due to cooldown
        assert result["limit_amount"] == 0
        assert result["approved"] is False
        assert result["limit_bucket"] == "Deny"
        assert result["cooldown"]["is_in_cooldown"] is True

    def test_custom_cooldown_hours(self):
        """Test custom cooldown period."""
        # Advance taken 50 hours ago
        advance_time = datetime.now() - timedelta(hours=50)
        events = [
            {"type": "cash_advance", "timestamp": advance_time.isoformat()}
        ]
        
        # Default 72h cooldown - should still be in cooldown
        result_default = compute_cooldown(user_events=events, cooldown_hours=72)
        assert result_default["is_in_cooldown"] is True
        
        # Short 24h cooldown - should NOT be in cooldown
        result_short = compute_cooldown(user_events=events, cooldown_hours=24)
        assert result_short["is_in_cooldown"] is False

    def test_multiple_events_uses_latest(self):
        """Should use the most recent advance for cooldown calculation."""
        old_advance = datetime.now() - timedelta(hours=100)
        recent_advance = datetime.now() - timedelta(hours=10)
        
        events = [
            {"type": "advance_taken", "timestamp": old_advance.isoformat()},
            {"type": "advance_taken", "timestamp": recent_advance.isoformat()},
        ]
        
        result = compute_cooldown(user_events=events)
        
        # Should be in cooldown due to recent advance
        assert result["is_in_cooldown"] is True
        assert result["remaining_hours"] > 50  # ~62 hours remaining

    def test_cooldown_explanation_is_clear(self):
        """Cooldown explanation should be human-readable."""
        recent_advance = datetime.now() - timedelta(hours=24)
        events = [
            {"type": "advance_taken", "timestamp": recent_advance.isoformat()}
        ]
        
        result = compute_cooldown(user_events=events)
        
        assert "remaining" in result["explanation"].lower()
        assert "hours" in result["explanation"].lower()

