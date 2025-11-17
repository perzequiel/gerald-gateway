from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from infrastructure.db.models.base import Base


class OutboundWebhookModel(Base):
    """Database model for outbound webhooks to ledger service."""
    
    __tablename__ = "outbound_webhook"
    
    id: str = Column(UUID(as_uuid=False), primary_key=True)
    event_type: str = Column(String, nullable=False)  # e.g., "BNPL_APPROVED"
    payload: Dict[str, Any] = Column(JSONB, nullable=False)  # Full webhook payload
    target_url: str = Column(String, nullable=False)  # Webhook destination URL
    status: str = Column(String, nullable=False)  # "pending", "success", "failed"
    last_attempt_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    attempts: int = Column(Integer, nullable=False, default=0)  # Attempt counter
    created_at: datetime = Column(DateTime(timezone=True), nullable=False)
    
    # Optional: Foreign key to plan for reference
    plan_id: Optional[str] = Column(UUID(as_uuid=False), ForeignKey("bnpl_plan.id"), nullable=True)
    
    @classmethod
    def create(
        cls,
        webhook_id: str,
        event_type: str,
        payload: Dict[str, Any],
        target_url: str,
        plan_id: Optional[str] = None
    ) -> "OutboundWebhookModel":
        """Create a new outbound webhook record."""
        return cls(
            id=webhook_id,
            event_type=event_type,
            payload=payload,
            target_url=target_url,
            status="pending",
            attempts=0,
            last_attempt_at=None,
            created_at=datetime.now(),
            plan_id=plan_id
        )
    
    def update_attempt(self, success: bool, latency_ms: Optional[int] = None):
        """Update webhook record after an attempt."""
        self.attempts += 1
        self.last_attempt_at = datetime.now()
        self.status = "success" if success else "failed"

