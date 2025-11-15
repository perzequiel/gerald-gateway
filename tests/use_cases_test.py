# use cases test

from datetime import datetime
import pytest

from application.service.validate_decision import ValidateDecisionService
from domain.entities import Transaction
from domain.repositories import DecisionRepository

@pytest.fixture
def mock_decision_repo_no_transactions(mocker):
    """Fixture to create a mock of the repository using pytest-mock"""
    mock_repo = mocker.AsyncMock(spec=DecisionRepository)
    # Default behavior
    mock_repo.get_user_transactions.return_value = []
    mock_repo.save.return_value = None
    return mock_repo


@pytest.fixture
def mock_decision_repo_with_transactions(mocker):
    """Fixture to create a mock of the repository using pytest-mock"""
    mock_repo = mocker.AsyncMock(spec=DecisionRepository) 
    mock_repo.get_user_transactions.return_value = [
        Transaction(
            transaction_id="123",
            date=datetime.now(),
            amount_cents=1000,
            type="debit",
            description="Test",
            category="Test",
            merchant="Test",
            balance_cents=1000,
            nsf=False
        )]
    mock_repo.save.return_value = None
    return mock_repo


@pytest.mark.asyncio
async def test_validate_decision_high_risk(mock_decision_repo_no_transactions):
    """Test for high risk decision (rejected)"""
    service = ValidateDecisionService(mock_decision_repo_no_transactions)
    decision = await service.execute(user_id="123", amount_requested_cents=10000)  # high risk
    
    assert decision is not None
    assert decision.id is not None
    assert decision.user_id == "123"
    assert decision.amount_requested_cents == 10000
    assert decision.credit_limit_cents == 0
    assert decision.amount_granted_cents == 0
    assert decision.approved is False
    assert decision.plan is None


@pytest.mark.asyncio
async def test_validate_decision_with_plan(mock_decision_repo_with_transactions):
    """Test for approved decision with plan"""
    service = ValidateDecisionService(mock_decision_repo_with_transactions)
    decision = await service.execute(user_id="123", amount_requested_cents=1000)  # low risk
    
    assert decision is not None
    assert decision.id is not None
    assert decision.user_id == "123"
    assert decision.amount_requested_cents == 1000
    assert decision.credit_limit_cents == 0
    assert decision.approved is True
    assert decision.amount_granted_cents == 800  # 1000 * 0.8
    assert decision.plan is not None
    assert decision.plan.id is not None
    assert decision.plan.decision_id == decision.id
    assert decision.plan.user_id == "123"
    assert decision.plan.total_cents == 800
    assert decision.plan.created_at is not None


@pytest.mark.asyncio
async def test_validate_decision_with_custom_mock(mocker):
    """Test for approved decision with custom mock"""
    # Create mock using the 'mocker' fixture from pytest-mock
    mock_repo = mocker.AsyncMock(spec=DecisionRepository)
    mock_repo.get_user_transactions.return_value = []
    mock_repo.save.return_value = None
    
    service = ValidateDecisionService(mock_repo)
    decision = await service.execute(user_id="123", amount_requested_cents=500)
    
    assert decision is not None
    assert decision.approved is True
    assert decision.amount_granted_cents == 400  # 500 * 0.8
    
    # Verify that the methods were called (if you use them in the future)
    # mock_repo.get_user_transactions.assert_called_once_with("123")

# def test_score_applicant():
#     transactions = [Transaction.create(user_id="123", amount_cents=1000)]
#     score, credit_limit, reason_breakdown = score_applicant(transactions, 1000)
#     assert score == 0.5
#     assert credit_limit == 1000
#     assert reason_breakdown == "score_reason_breakdown"

# def test_create_plan():
#     decision = Decision.create(user_id="123", amount_requested_cents=1000)
#     plan = create_plan(decision_id=decision.id, amount_granted_cents=1000, start_date=datetime.now())
#     assert plan is not None
#     assert plan.id is not None
#     assert plan.decision_id == decision.id
#     assert plan.amount_cents == 1000
#     assert plan.installments == []
#     assert plan.created_at is not None

# def test_create_transaction():
#     transaction = create_transaction(user_id="123", amount_cents=1000)
#     assert transaction is not None
#     assert transaction.id is not None
#     assert transaction.user_id == "123"
#     assert transaction.amount_cents == 1000
#     assert transaction.created_at is not None

# def test_create_plan_with_installments():
#     decision = Decision.create(user_id="123", amount_requested_cents=1000)
#     plan = create_plan(decision.id, 1000, datetime.now())
#     assert plan is not None
#     assert plan.id is not None
#     assert plan.decision_id == decision.id
#     assert plan.amount_cents == 1000
#     assert plan.installments == []
#     assert plan.created_at is not None

# def test_create_plan_with_installments():
#     decision = Decision.create(user_id="123", amount_requested_cents=1000)
#     plan = create_plan(decision.id, 1000, datetime.now())
#     assert plan is not None
#     assert plan.id is not None
#     assert plan.decision_id == decision.id
#     assert plan.amount_cents == 1000
#     assert plan.installments == []
#     assert plan.created_at is not None