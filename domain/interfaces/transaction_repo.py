from typing_extensions import Protocol
from domain.entities import Decision, Transaction


class TransactionRepository(Protocol):
    async def get_user_transactions(self, user_id: str) -> list[Transaction]: ...
    async def save_decision(self, decision: Decision) -> Decision: ...