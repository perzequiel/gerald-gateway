# create a test for the plan entity

from datetime import datetime
from domain.entities import Decision, Plan, User

def test_decision_entity_create():
    decision = Decision.create(user_id="123", amount_requested_cents=1000)
    assert decision is not None
    assert decision.id is not None
    assert decision.user_id == "123"
    assert decision.amount_requested_cents == 1000
    assert decision.created_at is not None

def test_plan_entity_create():
    plan = Plan.create(decision_id="123", user_id="123", total_cents=1000)
    assert plan is not None
    assert plan.id is not None
    assert plan.decision_id == "123"
    assert plan.user_id == "123"
    assert plan.total_cents == 1000
    assert plan.created_at is not None

def test_user_entity_get_transactions():
    transactions = User.get_transactions(user_id="123")
    assert transactions is not None
    assert len(transactions) == 1
    assert transactions[0].transaction_id is not None
    assert transactions[0].date is not None
    assert transactions[0].amount_cents == 1000
    assert transactions[0].type == "debit"
    assert transactions[0].description == "FoodiePlace"
    assert transactions[0].category == "restaurants"
    assert transactions[0].merchant == "FoodiePlace"
    assert transactions[0].balance_cents == 1000
    assert transactions[0].nsf is False