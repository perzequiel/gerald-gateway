from typing_extensions import Protocol
from domain.entities import Plan
from typing import Optional


class PlanRepository(Protocol):
    async def save_plan(self, plan: Plan) -> Plan: ...
    async def get_plan(self, plan_id: str) -> Optional[Plan]: ...

