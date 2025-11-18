"""
Metrics adapter that implements MetricsPort protocol.

This adapter wraps the Prometheus metrics and Datadog adapter
to provide a clean interface for the application layer.
"""
import os
from domain.interfaces import MetricsPort
from infrastructure.metrics.metrics import (
    gerald_decision_total,
    gerald_credit_limit_bucket_total,
)

class MetricsAdapter:
    """
    Adapter that implements MetricsPort for emitting metrics.
    
    This adapter:
    - Increments Prometheus metrics (for /metrics endpoint)
    - Sends metrics to Datadog via DogStatsD (for Terraform compatibility)
    """
    
    def __init__(self, service_name: str = None):
        """
        Initialize the metrics adapter.
        
        Args:
            service_name: Name of the service (defaults to SERVICE_NAME env var or "gerald-gateway")
        """
        self.service_name = service_name or os.getenv("SERVICE_NAME", "gerald-gateway")
    
    def increment_decision_total(self, outcome: str) -> None:
        """
        Increment the gerald_decision_total counter.
        
        Args:
            outcome: One of "approved", "declined", or "error"
        """
        gerald_decision_total.labels(outcome=outcome).inc()
    
    def increment_credit_limit_bucket(self, bucket: str) -> None:
        """
        Increment the gerald_credit_limit_bucket_total counter.
        
        Args:
            bucket: Credit limit bucket (e.g., "0-100", "100-400", etc.)
        """
        gerald_credit_limit_bucket_total.labels(bucket=bucket).inc()

