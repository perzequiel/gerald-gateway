from typing_extensions import Protocol
from domain.entities import Decision
from typing import Optional


class DecisionRepository(Protocol):
    async def save_decision(self, decision: Decision, risk_score: Optional[dict] = None) -> Decision: ...
    async def get_decision(self, decision_id: str) -> Optional[Decision]: ...
    async def get_user_decisions(self, user_id: str, limit: int = 10) -> list[Decision]: ...

