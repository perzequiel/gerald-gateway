from typing_extensions import Protocol
from typing import Optional


class MetricsPort(Protocol):
    """Protocol for metrics operations."""
    
    def increment_decision_total(self, outcome: str) -> None:
        """
        Increment the gerald_decision_total counter.
        
        Args:
            outcome: One of "approved", "declined", or "error"
        """
        ...
    
    def increment_credit_limit_bucket(self, bucket: str) -> None:
        """
        Increment the gerald_credit_limit_bucket_total counter.
        
        Args:
            bucket: Credit limit bucket (e.g., "0-100", "100-400", etc.)
        """
        ...
    


