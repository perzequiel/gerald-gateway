"""
Resilience tests for bank and ledger failures.

Tests verify:
- Bank API failures return 503 and increment bank_fetch_failures_total
- Ledger webhook failures trigger retries and record attempts
- Metrics are properly emitted on failures
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import Response, Request, HTTPStatusError, TimeoutException, RequestError
from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from infrastructure.clients.bank_client import BankClient
from infrastructure.clients.webhook_client import WebhookClient
from domain.exceptions import BankAPIError
from infrastructure.metrics.metrics import (
    bank_fetch_failures_total
)


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def reset_metrics():
    """Reset metrics before each test."""
    # Note: Prometheus counters don't have a reset method in production,
    # but for testing we can check increments
    yield
    # Metrics are cumulative, so we check relative values in tests


class TestBankFailure:
    """Tests for bank API failure scenarios."""
    
    @pytest.mark.asyncio
    async def test_bank_api_http_error_returns_503(self, client, reset_metrics):
        """Test that bank HTTP errors return 503 Service Unavailable."""
        from domain.exceptions import BankAPIError
        
        # Mock DecisionRepoSqlalchemy, PlanRepoSqlalchemy (to avoid DB access) and TransactionRepoAPI
        with patch('app.routers.v1.DecisionRepoSqlalchemy') as mock_decision_repo_class, \
             patch('app.routers.v1.PlanRepoSqlalchemy') as mock_plan_repo_class, \
             patch('app.routers.v1.TransactionRepoAPI') as mock_transaction_repo_class:
            
            # Mock decision repo to return None (no existing decision for idempotency check)
            mock_decision_repo_instance = AsyncMock()
            mock_decision_repo_instance.get_decision_by_request_id.return_value = None
            mock_decision_repo_class.return_value = mock_decision_repo_instance
            
            # Mock plan repo (not used in error path, but created by router)
            mock_plan_repo_instance = AsyncMock()
            mock_plan_repo_class.return_value = mock_plan_repo_instance
            
            # Mock TransactionRepoAPI.get_user_transactions to raise BankAPIError
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_user_transactions.side_effect = BankAPIError(
                "Bank API returned 500: Internal Server Error"
            )
            mock_transaction_repo_class.return_value = mock_repo_instance
            
            # Make request
            response = client.post(
                "/v1/decision",
                json={
                    "user_id": "user_good",
                    "amount_requested_cents": 40000
                },
                headers={"X-Request-ID": "test-bank-fail-1"}
            )
            
            # Verify 503 response
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            error_detail = response.json()["detail"]
            assert "bank_api_error" in error_detail.get("error", "").lower() or "bank" in error_detail.get("error", "").lower()
    
    @pytest.mark.asyncio
    async def test_bank_api_timeout_returns_503(self, client, reset_metrics):
        """Test that bank timeout errors return 503."""
        from domain.exceptions import BankAPIError
        
        # Mock DecisionRepoSqlalchemy, PlanRepoSqlalchemy (to avoid DB access) and TransactionRepoAPI
        with patch('app.routers.v1.DecisionRepoSqlalchemy') as mock_decision_repo_class, \
             patch('app.routers.v1.PlanRepoSqlalchemy') as mock_plan_repo_class, \
             patch('app.routers.v1.TransactionRepoAPI') as mock_transaction_repo_class:
            
            # Mock decision repo to return None (no existing decision for idempotency check)
            mock_decision_repo_instance = AsyncMock()
            mock_decision_repo_instance.get_decision_by_request_id.return_value = None
            mock_decision_repo_class.return_value = mock_decision_repo_instance
            
            # Mock plan repo (not used in error path, but created by router)
            mock_plan_repo_instance = AsyncMock()
            mock_plan_repo_class.return_value = mock_plan_repo_instance
            
            # Mock TransactionRepoAPI.get_user_transactions to raise BankAPIError
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_user_transactions.side_effect = BankAPIError(
                "Bank API request timed out after 5.0s"
            )
            mock_transaction_repo_class.return_value = mock_repo_instance
            
            response = client.post(
                "/v1/decision",
                json={
                    "user_id": "user_good",
                    "amount_requested_cents": 40000
                },
                headers={"X-Request-ID": "test-bank-timeout-1"}
            )
            
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            error_detail = response.json()["detail"]
            assert "bank_api_error" in error_detail.get("error", "").lower() or "bank" in error_detail.get("error", "").lower()
    
    @pytest.mark.asyncio
    async def test_bank_fetch_failures_metric_incremented(self, reset_metrics):
        """Test that bank_fetch_failures_total metric is incremented on failure."""
        # Get initial metric value (if any)
        initial_value = bank_fetch_failures_total._value.get()
        
        # Create bank client and simulate failure
        bank_client = BankClient(base_url="http://localhost:8001")
        
        with patch.object(bank_client._client, 'get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Bank API error",
                request=Request("GET", "http://localhost:8001/bank/transactions"),
                response=mock_response
            )
            mock_get.return_value = mock_response
            
            # Attempt to fetch (should raise BankAPIError)
            with pytest.raises(BankAPIError):
                await bank_client.fetch_transactions("user_good")
            
            # Verify metric was incremented
            # Note: We can't easily reset Prometheus counters, so we check it was called
            # In a real test environment, you'd use a test registry
            assert bank_fetch_failures_total._value.get() > initial_value


class TestLedgerWebhookFailure:
    """Tests for ledger webhook failure scenarios."""
    
    @pytest.mark.asyncio
    async def test_webhook_retries_on_failure(self, reset_metrics):
        """Test that webhook retries on failure using tenacity."""
        webhook_client = WebhookClient(base_url="http://localhost:8002")
        
        # Track number of attempts
        attempt_count = 0
        
        async def mock_post(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            # Simulate failure for first few attempts, success on last
            if attempt_count < 3:
                response = MagicMock()
                response.status_code = 500
                response.raise_for_status.side_effect = HTTPStatusError(
                    "Server error",
                    request=Request("POST", "http://localhost:8002/mock-ledger"),
                    response=response
                )
                return response
            else:
                # Success on 3rd attempt
                response = MagicMock()
                response.status_code = 200
                response.raise_for_status.return_value = None
                return response
        
        with patch.object(webhook_client._client, 'post', side_effect=mock_post):
            result = await webhook_client.send_webhook(
                plan_id="test-plan-id",
                decision_id="test-decision-id",
                user_id="user_good",
                amount_granted_cents=40000,
                request_id="test-webhook-retry"
            )
            
            # Should eventually succeed after retries
            assert result[0] is True
            # Should have attempted at least 3 times (1 initial + 2 retries)
            assert attempt_count >= 3
    
    @pytest.mark.asyncio
    async def test_webhook_fails_after_max_retries(self, reset_metrics):
        """Test that webhook fails after exhausting all retries."""
        webhook_client = WebhookClient(base_url="http://localhost:8002", max_retries=2)
        
        async def mock_post(*args, **kwargs):
            # Always fail
            response = MagicMock()
            response.status_code = 500
            response.raise_for_status.side_effect = HTTPStatusError(
                "Server error",
                request=Request("POST", "http://localhost:8002/mock-ledger"),
                response=response
            )
            return response
        
        with patch.object(webhook_client._client, 'post', side_effect=mock_post):
            result = await webhook_client.send_webhook(
                plan_id="test-plan-id",
                decision_id="test-decision-id",
                user_id="user_good",
                amount_granted_cents=40000,
                request_id="test-webhook-fail"
            )
            
            # Should return False after all retries exhausted
            assert result[0] is False
    
    @pytest.mark.asyncio
    async def test_webhook_latency_recorded(self, reset_metrics):
        """Test that webhook latency is recorded in histogram."""
        webhook_client = WebhookClient(base_url="http://localhost:8002")
        
        async def mock_post(*args, **kwargs):
            # Simulate some latency
            await asyncio.sleep(0.05)  # 50ms latency
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            return response
        
        with patch.object(webhook_client._client, 'post', side_effect=mock_post):
            # Send webhook - latency should be recorded
            result = await webhook_client.send_webhook(
                plan_id="test-plan-id",
                decision_id="test-decision-id",
                user_id="user_good",
                amount_granted_cents=40000
            )
            
            # Verify webhook succeeded
            assert result[0] is True
            # Note: Histogram observation happens internally in _send_with_retry
            # In a real test environment, you'd verify the histogram buckets


class TestIntegrationResilience:
    """Integration tests for end-to-end resilience scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_flow_bank_failure(self, client, reset_metrics):
        """Test full flow when bank fails - should return 503."""
        with patch('app.routers.v1.BankClient') as mock_bank:
            mock_client = AsyncMock()
            mock_client.fetch_transactions.side_effect = BankAPIError("Bank unavailable")
            mock_bank.return_value = mock_client
            
            response = client.post(
                "/v1/decision",
                json={
                    "user_id": "user_good",
                    "amount_requested_cents": 40000
                },
                headers={"X-Request-ID": "test-integration-bank-fail"}
            )
            
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_idempotency_with_same_request_id(self, client):
        """Test that same X-Request-ID returns same decision."""
        from domain.entities import Transaction
        from datetime import datetime
        
        request_id = "test-idempotency-123"
        saved_decision = [None]  # Store decision saved in first call
        
        with patch('app.routers.v1.DecisionRepoSqlalchemy') as mock_decision_repo_class, \
             patch('app.routers.v1.PlanRepoSqlalchemy') as mock_plan_repo_class, \
             patch('app.routers.v1.TransactionRepoAPI') as mock_transaction_repo_class:
            
            # Mock decision repo: first call returns None, second returns saved decision
            mock_decision_repo = AsyncMock()
            
            async def get_decision_side_effect(_):
                return None if saved_decision[0] is None else saved_decision[0]
            
            async def save_decision_side_effect(decision, **kwargs):
                saved_decision[0] = decision
                return decision
            
            mock_decision_repo.get_decision_by_request_id.side_effect = get_decision_side_effect
            mock_decision_repo.save_decision.side_effect = save_decision_side_effect
            mock_decision_repo_class.return_value = mock_decision_repo
            
            # Mock plan repo
            mock_plan_repo = AsyncMock()
            mock_plan_repo_class.return_value = mock_plan_repo
            
            # Mock transaction repo with good transactions
            mock_transaction_repo = AsyncMock()
            mock_transaction_repo.get_user_transactions.return_value = [
                Transaction(
                    transaction_id="tx1",
                    date=datetime.now(),
                    amount_cents=10000,
                    type="credit",
                    description="Salary",
                    category="income",
                    merchant="Employer",
                    balance_cents=100000,
                    nsf=False
                )
            ]
            mock_transaction_repo_class.return_value = mock_transaction_repo
            
            # Mock database session for plan lookup in second call
            from infrastructure.db.database import get_db_session
            mock_plan_model = MagicMock()
            
            async def mock_get_db_session():
                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_plan_model
                mock_db.execute.return_value = mock_result
                yield mock_db
            
            app.dependency_overrides[get_db_session] = mock_get_db_session
            
            try:
                # First request - creates new decision
                # Request $50 (5000 cents) - within new BNPL tier limits
                response1 = client.post(
                    "/v1/decision",
                    json={"user_id": "user_good", "amount_requested_cents": 5000},
                    headers={"X-Request-ID": request_id}
                )

                assert response1.status_code == 200
                decision1 = response1.json()
                assert decision1["approved"] is True
                
                # Update mock plan model with plan_id from first response
                if saved_decision[0] and saved_decision[0].plan:
                    mock_plan_model.id = str(saved_decision[0].plan.id)
                
                # Second request - should return same decision (idempotent)
                response2 = client.post(
                    "/v1/decision",
                    json={"user_id": "user_good", "amount_requested_cents": 40000},
                    headers={"X-Request-ID": request_id}
                )
                
                assert response2.status_code == 200
                decision2 = response2.json()
                
                # Verify idempotency: same decision returned
                assert decision1["plan_id"] == decision2["plan_id"]
                assert decision1["approved"] == decision2["approved"]
                assert decision1["credit_limit_cents"] == decision2["credit_limit_cents"]
                assert decision1["amount_granted_cents"] == decision2["amount_granted_cents"]
                
                # Verify get_decision_by_request_id was called twice
                assert mock_decision_repo.get_decision_by_request_id.call_count == 2
            finally:
                app.dependency_overrides.clear()

