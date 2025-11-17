from typing import Optional
from domain.interfaces import PlanRepository
from domain.entities import Plan

class GetPlanService:
    def __init__(self, plan_repo: PlanRepository):
        self.plan_repo = plan_repo

    async def execute(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID with its installments."""
        return await self.plan_repo.get_plan(plan_id)