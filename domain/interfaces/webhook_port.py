from typing_extensions import Protocol
from typing import Optional


class WebhookPort(Protocol):
    """Protocol for webhook operations."""
    
    async def send_webhook(
        self,
        plan_id: str,
        decision_id: str,
        user_id: str,
        amount_granted_cents: int,
        request_id: Optional[str] = None
    ) -> bool:
        """
        Send webhook to ledger service.
        
        Args:
            plan_id: ID of the plan
            decision_id: ID of the decision
            user_id: ID of the user
            amount_granted_cents: Amount granted in cents
            request_id: Optional request ID for tracing
            
        Returns:
            True if webhook was sent successfully, False otherwise
        """
        ...

