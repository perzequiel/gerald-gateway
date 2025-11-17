# src/infra/db/models/user_model.py
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Boolean, Table, Integer, Float, DateTime
from sqlalchemy.orm import Mapped
from sqlalchemy.dialects.postgresql import JSONB, UUID
from domain.entities.decision import Decision
from infrastructure.db.models.base import Base

class DecisionModel(Base):
    __tablename__ = "bnpl_decision"
    id: Mapped[str] = Column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = Column(String, nullable=False)
    requested_cents: Mapped[int] = Column(Integer, nullable=False)
    approved: Mapped[bool] = Column(Boolean, default=False)
    credit_limit_cents: Mapped[int] = Column(Integer, nullable=False)
    amount_granted_cents: Mapped[int] = Column(Integer, nullable=False)
    score_numeric: Mapped[float] = Column(Float, nullable=False)
    score_band: Mapped[str] = Column(String, nullable=False)
    risk_factors: Mapped[dict] = Column("risk_factors", JSONB, nullable=False)  # Column name matches DB schema
    created_at: Mapped[datetime] = Column(DateTime, nullable=False)

    def to_domain(self) -> Decision:
        return Decision(
            id=self.id,
            user_id=self.user_id,
            amount_requested_cents=self.requested_cents,
            approved=self.approved,
            credit_limit_cents=self.credit_limit_cents,
            amount_granted_cents=self.amount_granted_cents,
            score=self.score_numeric,
            created_at=self.created_at
        )

    @classmethod
    def from_domain(cls, decision: Decision, risk_score: Optional[dict] = None, request_id: Optional[str] = None) -> "DecisionModel":
        """
        Convert domain Decision to database model.
        
        Args:
            decision: Domain Decision entity
            risk_score: Optional risk score dict for additional fields
            request_id: Optional request ID for idempotency (stored in risk_factors)
        """
        # Store request_id in risk_factors JSONB field for idempotency
        risk_factors = risk_score.copy() if risk_score else {}
        if request_id:
            risk_factors['_request_id'] = request_id  # Prefix with _ to avoid conflicts
        
        return cls(
            id=decision.id,
            user_id=decision.user_id,
            requested_cents=decision.amount_requested_cents,
            approved=decision.approved,
            credit_limit_cents=decision.credit_limit_cents,
            amount_granted_cents=decision.amount_granted_cents,
            score_numeric=decision.score,
            score_band=risk_score.get('limit_bucket', '') if risk_score else '',
            risk_factors=risk_factors,
            created_at=decision.created_at,
        )