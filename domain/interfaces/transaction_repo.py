from typing_extensions import Protocol
from domain.entities import Transaction


class TransactionRepository(Protocol):
    async def get_user_transactions(self, user_id: str) -> list[Transaction]: ...