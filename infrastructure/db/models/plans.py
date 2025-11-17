from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship
from domain.entities.plan import Plan
from infrastructure.db.models.base import Base

if TYPE_CHECKING:
    from infrastructure.db.models.installments import InstallmentModel

class PlanModel(Base):
    __tablename__ = "bnpl_plan"
    
    id: Mapped[str] = Column(UUID(as_uuid=False), primary_key=True)
    decision_id: Mapped[str] = Column(UUID(as_uuid=False), ForeignKey("bnpl_decision.id"), nullable=False)
    user_id: Mapped[str] = Column(String, nullable=False)
    total_cents: Mapped[int] = Column(Integer, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, nullable=False)
    
    # Relationship to installments (one-to-many)
    installments_rel: Mapped[list["InstallmentModel"]] = relationship(
        "InstallmentModel",
        back_populates="plan_rel",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    def to_domain(self) -> Plan:
        """Convert database model to domain entity."""
        from domain.entities.installment import Installment
        
        # Convert related installments to domain entities
        # SQLAlchemy relationships return InstrumentedList which is iterable
        installments_list = []
        try:
            # Access the relationship attribute
            installments_rel = getattr(self, 'installments_rel', None)
            if installments_rel is not None:
                # Check if it's iterable (should be a list or InstrumentedList)
                # SQLAlchemy relationships are always iterable when loaded
                if hasattr(installments_rel, '__iter__') and not isinstance(installments_rel, str):
                    # Iterate over the relationship (works with InstrumentedList or regular list)
                    for inst_model in installments_rel:
                        installments_list.append(inst_model.to_domain())
                else:
                    # If it's a single object (shouldn't happen, but handle it)
                    installments_list = [installments_rel.to_domain()]
        except (TypeError, AttributeError) as e:
            # If installments_rel is not iterable or doesn't exist, continue with empty list
            # This should not happen, but handle it gracefully
            installments_list = []
        
        plan = Plan(
            id=self.id,
            decision_id=self.decision_id,
            user_id=self.user_id,
            total_cents=self.total_cents,
            created_at=self.created_at,
            installments=installments_list if installments_list else None,
            installments_count=len(installments_list) if installments_list else 4,
            days_between_installments=14  # Default, could be stored if needed
        )
        return plan
    
    @classmethod
    def from_domain(cls, plan: Plan) -> "PlanModel":
        """Convert domain Plan entity to database model.
        
        Note: Installments are not set here. They should be added separately
        in the repository after the plan is added to the session.
        """
        # Create plan model without installments
        # Installments will be added in the repository after the plan is in the session
        plan_model = cls(
            id=plan.id,
            decision_id=plan.decision_id,
            user_id=plan.user_id,
            total_cents=plan.total_cents,
            created_at=plan.created_at,
        )
        
        return plan_model

