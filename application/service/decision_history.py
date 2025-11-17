from domain.entities import Decision
from domain.interfaces import DecisionRepository

class DecisionHistoryService:
    def __init__(self, decision_repo: DecisionRepository):
        self.decision_repo = decision_repo

    async def execute(self, user_id: str) -> list[Decision]:
        return await self.decision_repo.get_user_decisions(user_id)