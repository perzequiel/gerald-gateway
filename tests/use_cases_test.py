# use cases test

from datetime import datetime, timedelta
import pytest

from application.service.validate_decision import ValidateDecisionService
from domain.entities import InstallmentStatus, Transaction
from domain.interfaces.transaction_repo import TransactionRepository



@pytest.fixture
def mock_decision_repo_no_transactions(mocker):
    """Fixture to create a mock of the repository using pytest-mock"""
    mock_repo = mocker.AsyncMock(spec=TransactionRepository)
    # Default behavior
    mock_repo.get_user_transactions.return_value = []
    return mock_repo


@pytest.fixture
def mock_decision_repo_with_transactions_higher(mocker):
    """Fixture to create a mock of the repository using pytest-mock"""
    mock_repo = mocker.AsyncMock(spec=TransactionRepository) 
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
    return mock_repo

@pytest.fixture
def mock_decision_repo_with_transactions_middle(mocker):
    """Fixture to create a mock of the repository using pytest-mock"""
    mock_repo = mocker.AsyncMock(spec=TransactionRepository) 
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
    return mock_repo

@pytest.fixture
def mock_decision_repo_with_transactions_lower(mocker):
    """Fixture to create a mock of the repository using pytest-mock"""
    mock_repo = mocker.AsyncMock(spec=TransactionRepository)
    mock_repo.get_user_transactions.return_value = [
        Transaction(
            transaction_id="123",
            date=datetime.now(),
            amount_cents=100,
            type="debit",
            description="Test",
            category="Test",
            merchant="Test",
            balance_cents=-10000,
            nsf=True
        )]
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
    assert decision.credit_limit_cents == 0


@pytest.mark.asyncio
async def test_validate_decision_with_plan_approved_higher_score(mock_decision_repo_with_transactions_higher):
    """Test for approved decision with plan"""
    service = ValidateDecisionService(mock_decision_repo_with_transactions_higher)
    decision = await service.execute(user_id="123", amount_requested_cents=1000)  # low risk
    
    assert decision is not None
    assert decision.id is not None
    assert decision.user_id == "123"
    assert decision.amount_requested_cents == 1000
    assert decision.approved is True
    assert decision.amount_granted_cents == 1000
    assert decision.plan is not None
    assert decision.plan.id is not None
    assert decision.plan.decision_id == decision.id
    assert decision.plan.user_id == "123"
    assert decision.plan.total_cents == 1000
    assert decision.plan.created_at is not None
    assert decision.credit_limit_cents == 100000


@pytest.mark.asyncio
async def test_validate_decision_with_plan_approved_middle_score(mock_decision_repo_with_transactions_middle):
    """Test for approved decision with plan"""
    service = ValidateDecisionService(mock_decision_repo_with_transactions_middle);
    decision = await service.execute(user_id="123", amount_requested_cents=500)  # low risk
    
    assert decision is not None
    assert decision.id is not None
    assert decision.user_id == "123"
    assert decision.amount_requested_cents == 500
    assert decision.approved is True
    assert decision.amount_granted_cents == 500
    assert decision.credit_limit_cents == 500

@pytest.mark.asyncio
async def test_validate_decision_with_plan_approved_lower_score(mock_decision_repo_with_transactions_lower):
    """Test for approved decision with plan"""
    service = ValidateDecisionService(mock_decision_repo_with_transactions_lower);
    decision = await service.execute(user_id="123", amount_requested_cents=500)  # low risk
    
    assert decision is not None
    assert decision.id is not None
    assert decision.user_id == "123"
    assert decision.amount_requested_cents == 500
    assert decision.approved is False
    assert decision.amount_granted_cents == 0
    assert decision.credit_limit_cents == 0

@pytest.mark.asyncio
async def test_validate_decision_with_plan_approved_bi_weekly_installment(mock_decision_repo_with_transactions_higher):
    """Test for approved decision with plan for bi-weekly installment"""
    service = ValidateDecisionService(mock_decision_repo_with_transactions_higher);
    decision = await service.execute(user_id="123", amount_requested_cents=500)  # low risk
    
    assert decision is not None
    assert decision.id is not None
    assert decision.user_id == "123"
    assert decision.amount_requested_cents == 500
    assert decision.approved is True
    assert decision.amount_granted_cents == 500
    assert decision.credit_limit_cents == 100000
    assert decision.plan.installments is not None
    assert len(decision.plan.installments) == 4
    assert decision.plan.installments[0].id is not None
    assert decision.plan.installments[0].plan_id == decision.plan.id
    assert decision.plan.installments[0].due_date is not None
    assert decision.plan.installments[0].amount_cents == 125
    assert decision.plan.installments[0].status == InstallmentStatus.PENDING.value
    # 4 bi-weekly created at
    for i in range(len(decision.plan.installments)):
        assert decision.plan.installments[i].due_date.date() == (
            decision.plan.created_at + timedelta(days=(i+1) * decision.plan.days_between_installments)
        ).date()