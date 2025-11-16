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
def mock_decision_repo_with_transactions_higher(mocker):
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

@pytest.fixture
def mock_decision_repo_with_transactions_middle(mocker):
    """Fixture to create a mock of the repository using pytest-mock"""
    mock_repo = mocker.AsyncMock(spec=DecisionRepository) 
    mock_repo.get_user_transactions.return_value = [
        Transaction(
            transaction_id="123",
            date=datetime.now(),
            amount_cents=500,
            type="debit",
            description="Test",
            category="Test",
            merchant="Test",
            balance_cents=500,
            nsf=True
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
async def test_validate_decision_with_plan_approved_higher(mock_decision_repo_with_transactions_higher):
    """Test for approved decision with plan"""
    service = ValidateDecisionService(mock_decision_repo_with_transactions_higher)
    decision = await service.execute(user_id="123", amount_requested_cents=1000)  # low risk
    
    assert decision is not None
    assert decision.id is not None
    assert decision.user_id == "123"
    assert decision.amount_requested_cents == 1000
    assert decision.credit_limit_cents == 0
    assert decision.approved is True
    assert decision.amount_granted_cents == 1000
    assert decision.plan is not None
    assert decision.plan.id is not None
    assert decision.plan.decision_id == decision.id
    assert decision.plan.user_id == "123"
    assert decision.plan.total_cents == 1000
    assert decision.plan.created_at is not None


@pytest.mark.asyncio
async def test_validate_decision_with_plan_approved_middle(mock_decision_repo_with_transactions_middle):
    """Test for approved decision with plan"""
    service = ValidateDecisionService(mock_decision_repo_with_transactions_middle);
    decision = await service.execute(user_id="123", amount_requested_cents=500)  # low risk
    
    assert decision is not None
    assert decision.id is not None
    assert decision.user_id == "123"
    assert decision.amount_requested_cents == 500
    assert decision.credit_limit_cents == 0
    assert decision.approved is True
    assert decision.amount_granted_cents == 500