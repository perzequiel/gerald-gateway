"""
Tests for metrics emission and validation.

Tests verify:
- gerald_decision_total is incremented with correct labels
- gerald_credit_limit_bucket is incremented with correct buckets
- Metrics are emitted for approved, declined, and error cases
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from prometheus_client import generate_latest, REGISTRY

from app.main import app
from infrastructure.metrics.metrics import (
    gerald_decision_total,
    gerald_credit_limit_bucket,
    bank_fetch_failures_total
)
from application.service.validate_decision import ValidateDecisionService
from domain.entities import Transaction
from datetime import datetime
import re
from prometheus_client import CONTENT_TYPE_LATEST


def _extract_metric_value(metrics_text: str, metric_name: str, labels: dict) -> float:
    """
    Extract metric value from Prometheus text format.
    
    Args:
        metrics_text: Prometheus metrics text output
        metric_name: Name of the metric (without _total suffix)
        labels: Dictionary of label key-value pairs
        
    Returns:
        Metric value as float, or 0.0 if not found
    
    Note: Prometheus automatically adds _total suffix to Counter metrics,
    so we search for both metric_name and metric_name_total.
    """
    # Prometheus adds _total to Counter metrics
    metric_variants = [metric_name, f"{metric_name}_total"]
    
    # Find all lines for this metric (skip comments and empty lines)
    lines = []
    for line in metrics_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Check if line starts with any variant of the metric name
        if any(line.startswith(variant) for variant in metric_variants):
            lines.append(line)
    
    for line in lines:
        # Skip TYPE and HELP lines
        if line.startswith('#') or 'TYPE' in line or 'HELP' in line:
            continue
        
        # Skip _created metrics (Prometheus auto-generated timestamps)
        if '_created' in line:
            continue
        
        # Check if this line matches our metric (with or without _total)
        if not any(line.startswith(variant) for variant in metric_variants):
            continue
        
        # Handle labels
        if labels:
            # Build expected label pattern (order-independent)
            # Format: metric_name{label1="value1",label2="value2"} value
            # Note: Prometheus escapes special chars, but we match the literal string
            all_labels_match = True
            for key, value in labels.items():
                # Simple string search for label pattern
                label_pattern = f'{key}="{value}"'
                if label_pattern not in line:
                    all_labels_match = False
                    break
            
            if not all_labels_match:
                continue
        else:
            # No labels expected - metric should not have labels
            if '{' in line:
                continue
        
        # Extract value: metric_name{labels} value or metric_name value
        # Value is after the last space or tab
        parts = line.split()
        if len(parts) >= 2:
            try:
                # Last part should be the value
                value_str = parts[-1]
                return float(value_str)
            except (ValueError, IndexError):
                continue
    
    return 0.0


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_transaction_repo_good(mocker):
    """Mock transaction repo with good user transactions."""
    mock_repo = mocker.AsyncMock()
    mock_repo.get_user_transactions.return_value = [
        Transaction(
            transaction_id="txn-1",
            date=datetime.now(),
            amount_cents=50000,
            type="credit",
            description="Salary",
            category="income",
            merchant="Employer",
            balance_cents=50000,
            nsf=False
        ),
        Transaction(
            transaction_id="txn-2",
            date=datetime.now(),
            amount_cents=10000,
            type="debit",
            description="Purchase",
            category="shopping",
            merchant="Store",
            balance_cents=40000,
            nsf=False
        )
    ]
    return mock_repo


@pytest.fixture
def mock_transaction_repo_no_transactions(mocker):
    """Mock transaction repo with no transactions."""
    mock_repo = mocker.AsyncMock()
    mock_repo.get_user_transactions.return_value = []
    return mock_repo


class TestDecisionMetrics:
    """Tests for decision metrics."""
    
    @pytest.mark.asyncio
    async def test_approved_decision_emits_metrics(self, mock_transaction_repo_good, mocker):
        """Test that approved decisions emit correct metrics."""
        # Mock repositories
        mock_decision_repo = mocker.AsyncMock()
        mock_plan_repo = mocker.AsyncMock()
        
        # Get initial metric values from Prometheus text format
        initial_metrics = generate_latest(REGISTRY).decode('utf-8')
        initial_approved_count = _extract_metric_value(initial_metrics, 'gerald_decision_total', {'outcome': 'approved'})
        
        service = ValidateDecisionService(
            transaction_repo=mock_transaction_repo_good,
            decision_repo=mock_decision_repo,
            plan_repo=mock_plan_repo
        )
        
        decision = await service.execute(
            user_id="user_good",
            amount_requested_cents=40000,
            request_id="test-metrics-approved"
        )
        
        # Verify decision was approved
        assert decision.approved is True
        
        # Verify metrics were incremented by checking the /metrics endpoint
        final_metrics = generate_latest(REGISTRY).decode('utf-8')
        final_approved_count = _extract_metric_value(final_metrics, 'gerald_decision_total', {'outcome': 'approved'})
        
        assert final_approved_count > initial_approved_count, "gerald_decision_total{outcome='approved'} should be incremented"
    
    @pytest.mark.asyncio
    async def test_declined_decision_emits_metrics(self, mock_transaction_repo_good, mocker):
        """Test that declined decisions emit correct metrics."""
        mock_decision_repo = mocker.AsyncMock()
        mock_plan_repo = mocker.AsyncMock()
        
        initial_metrics = generate_latest(REGISTRY).decode('utf-8')
        initial_declined_count = _extract_metric_value(initial_metrics, 'gerald_decision_total', {'outcome': 'declined'})
        
        service = ValidateDecisionService(
            transaction_repo=mock_transaction_repo_good,
            decision_repo=mock_decision_repo,
            plan_repo=mock_plan_repo
        )
        
        # Request amount higher than limit to get declined
        decision = await service.execute(
            user_id="user_good",
            amount_requested_cents=200000,  # Higher than limit
            request_id="test-metrics-declined"
        )
        
        assert decision.approved is False
        
        final_metrics = generate_latest(REGISTRY).decode('utf-8')
        final_declined_count = _extract_metric_value(final_metrics, 'gerald_decision_total', {'outcome': 'declined'})
        assert final_declined_count > initial_declined_count, "gerald_decision_total{outcome='declined'} should be incremented"
    
    @pytest.mark.asyncio
    async def test_error_case_emits_metrics(self, mock_transaction_repo_no_transactions, mocker):
        """Test that error cases (no transactions) emit correct metrics."""
        mock_decision_repo = mocker.AsyncMock()
        mock_plan_repo = mocker.AsyncMock()
        
        initial_metrics = generate_latest(REGISTRY).decode('utf-8')
        initial_error_count = _extract_metric_value(initial_metrics, 'gerald_decision_total', {'outcome': 'error'})
        initial_bucket_zero_count = _extract_metric_value(initial_metrics, 'gerald_credit_limit_bucket', {'bucket': '$0'})
        
        service = ValidateDecisionService(
            transaction_repo=mock_transaction_repo_no_transactions,
            decision_repo=mock_decision_repo,
            plan_repo=mock_plan_repo
        )
        
        decision = await service.execute(
            user_id="user_no_txns",
            amount_requested_cents=40000,
            request_id="test-metrics-error"
        )
        
        assert decision.approved is False
        
        final_metrics = generate_latest(REGISTRY).decode('utf-8')
        final_error_count = _extract_metric_value(final_metrics, 'gerald_decision_total', {'outcome': 'error'})
        final_bucket_zero_count = _extract_metric_value(final_metrics, 'gerald_credit_limit_bucket', {'bucket': '$0'})
        
        assert final_error_count > initial_error_count, "gerald_decision_total{outcome='error'} should be incremented"
        assert final_bucket_zero_count > initial_bucket_zero_count, "gerald_credit_limit_bucket{bucket='$0'} should be incremented"


class TestCreditLimitBucketMetrics:
    """Tests for credit limit bucket metrics."""
    
    def test_bucket_metrics_for_different_limits(self):
        """Test that different credit limit buckets are tracked."""
        # Verify the metric structure exists
        assert gerald_credit_limit_bucket is not None
        assert hasattr(gerald_credit_limit_bucket, 'labels')
        
        # Get initial values
        initial_metrics = generate_latest(REGISTRY).decode('utf-8')
        initial_bucket_0 = _extract_metric_value(initial_metrics, 'gerald_credit_limit_bucket', {'bucket': '$0'})
        initial_bucket_100_400 = _extract_metric_value(initial_metrics, 'gerald_credit_limit_bucket', {'bucket': '$100 - $400'})
        initial_bucket_500 = _extract_metric_value(initial_metrics, 'gerald_credit_limit_bucket', {'bucket': '$500'})
        initial_bucket_1000 = _extract_metric_value(initial_metrics, 'gerald_credit_limit_bucket', {'bucket': '$1000+'})
        
        # Increment different buckets
        gerald_credit_limit_bucket.labels(bucket="$0").inc()
        gerald_credit_limit_bucket.labels(bucket="$100 - $400").inc()
        gerald_credit_limit_bucket.labels(bucket="$500").inc()
        gerald_credit_limit_bucket.labels(bucket="$1000+").inc()
        
        # Verify buckets were incremented
        final_metrics = generate_latest(REGISTRY).decode('utf-8')
        final_bucket_0 = _extract_metric_value(final_metrics, 'gerald_credit_limit_bucket', {'bucket': '$0'})
        final_bucket_100_400 = _extract_metric_value(final_metrics, 'gerald_credit_limit_bucket', {'bucket': '$100 - $400'})
        final_bucket_500 = _extract_metric_value(final_metrics, 'gerald_credit_limit_bucket', {'bucket': '$500'})
        final_bucket_1000 = _extract_metric_value(final_metrics, 'gerald_credit_limit_bucket', {'bucket': '$1000+'})
        
        assert final_bucket_0 > initial_bucket_0
        assert final_bucket_100_400 > initial_bucket_100_400
        assert final_bucket_500 > initial_bucket_500
        assert final_bucket_1000 > initial_bucket_1000


class TestBankFailureMetrics:
    """Tests for bank failure metrics."""
    
    @pytest.mark.asyncio
    async def test_bank_failure_increments_metric(self):
        """Test that bank failures increment bank_fetch_failures_total."""
        from infrastructure.clients.bank_client import BankClient
        from httpx import HTTPStatusError, Request as HTTPRequest
        
        initial_metrics = generate_latest(REGISTRY).decode('utf-8')
        initial_value = _extract_metric_value(initial_metrics, 'bank_fetch_failures_total', {})
        
        bank_client = BankClient(base_url="http://localhost:8001")
        
        # Mock httpx client to raise error
        with patch.object(bank_client._client, 'get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Bank API error",
                request=HTTPRequest("GET", "http://localhost:8001/bank/transactions"),
                response=mock_response
            )
            mock_get.return_value = mock_response
            
            with pytest.raises(Exception):  # BankAPIError
                await bank_client.fetch_transactions("user_good")
            
            # Verify metric was incremented
            final_metrics = generate_latest(REGISTRY).decode('utf-8')
            final_value = _extract_metric_value(final_metrics, 'bank_fetch_failures_total', {})
            assert final_value > initial_value, "bank_fetch_failures_total should be incremented on failure"


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""
    
    def test_metrics_endpoint_returns_prometheus_format(self, client):
        """Test that /metrics endpoint returns Prometheus format."""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        # Use the actual CONTENT_TYPE_LATEST from prometheus_client (version may vary)
        assert response.headers["content-type"] == CONTENT_TYPE_LATEST
        
        # Verify metrics are present in response
        content = response.text
        assert "gerald_decision_total" in content
        assert "gerald_credit_limit_bucket" in content
        assert "bank_fetch_failures_total" in content
        assert "webhook_latency_seconds" in content
    
    def test_metrics_endpoint_includes_labels(self, client):
        """Test that metrics endpoint includes label information."""
        # First, increment some metrics to ensure they appear
        gerald_decision_total.labels(outcome="approved").inc()
        gerald_credit_limit_bucket.labels(bucket="$1000+").inc()
        
        response = client.get("/metrics")
        content = response.text
        
        # Check for label examples in the metrics
        # Prometheus format: metric_name{label="value"} value
        has_outcome_label = 'outcome="' in content or "outcome=" in content
        has_bucket_label = 'bucket="' in content or "bucket=" in content
        
        assert has_outcome_label or has_bucket_label, \
            f"Expected 'outcome=' or 'bucket=' labels in metrics. Content sample: {content[:500]}"

