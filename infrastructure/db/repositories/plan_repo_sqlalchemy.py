from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from domain.entities import Plan
from domain.interfaces import PlanRepository
from infrastructure.db.models.plans import PlanModel
from infrastructure.db.models.installments import InstallmentModel


class PlanRepoSqlalchemy(PlanRepository):
    """SQLAlchemy implementation of PlanRepository."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def save_plan(self, plan: Plan) -> Plan:
        """Save a plan to the database with its installments."""
        # Create plan model without installments first
        plan_model = PlanModel.from_domain(plan)
        
        # Add plan to session first so it's tracked
        self.db.add(plan_model)
        await self.db.flush()  # Flush to get the plan_id available
        
        # Now add installments after the plan is in the session
        if plan.installments:
            installment_models = [
                InstallmentModel.from_domain(inst)
                for inst in plan.installments
            ]
            # Set the back-reference on each installment
            for inst_model in installment_models:
                inst_model.plan_rel = plan_model
            # Add installments to session - cascade will handle the relationship
            for inst_model in installment_models:
                self.db.add(inst_model)
        
        await self.db.commit()
        # Refresh to load relationships
        await self.db.refresh(plan_model, ["installments_rel"])
        return plan
    
    async def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID with its installments loaded."""
        stmt = (
            select(PlanModel)
            .where(PlanModel.id == plan_id)
            .options(selectinload(PlanModel.installments_rel))
        )
        result = await self.db.execute(stmt)
        plan_model = result.scalar_one_or_none()
        if plan_model:
            return plan_model.to_domain()
        return None

