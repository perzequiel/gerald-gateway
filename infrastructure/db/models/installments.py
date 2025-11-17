from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship
from domain.entities.installment import Installment
from infrastructure.db.models.base import Base

class InstallmentModel(Base):
    __tablename__ = "bnpl_installment"
    
    id: Mapped[str] = Column(UUID(as_uuid=False), primary_key=True)
    plan_id: Mapped[str] = Column(UUID(as_uuid=False), ForeignKey("bnpl_plan.id"), nullable=False)
    due_date: Mapped[datetime] = Column(DateTime, nullable=False)
    amount_cents: Mapped[int] = Column(Integer, nullable=False)
    status: Mapped[str] = Column(String, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, nullable=False)
    
    # Relationship back to plan (many-to-one)
    plan_rel: Mapped["PlanModel"] = relationship(
        "PlanModel",
        back_populates="installments_rel"
    )
    
    def to_domain(self) -> Installment:
        """Convert database model to domain entity."""
        return Installment(
            id=self.id,
            plan_id=self.plan_id,
            due_date=self.due_date,
            amount_cents=self.amount_cents,
            status=self.status,
            created_at=self.created_at
        )
    
    @classmethod
    def from_domain(cls, installment: Installment) -> "InstallmentModel":
        """Convert domain Installment entity to database model."""
        return cls(
            id=installment.id,
            plan_id=installment.plan_id,
            due_date=installment.due_date,
            amount_cents=installment.amount_cents,
            status=installment.status if isinstance(installment.status, str) else str(installment.status),
            created_at=installment.created_at,
        )

