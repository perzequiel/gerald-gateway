from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import uuid4

class InstallmentStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"

@dataclass
class Installment:
    id: str
    plan_id: str
    due_date: datetime
    amount_cents: int
    status: str
    created_at: datetime

    @staticmethod
    def create(plan_id: str, due_date: datetime, amount_cents: int) -> 'Installment':
        return Installment(
            id=str(uuid4()), 
            plan_id=plan_id, 
            due_date=due_date, 
            amount_cents=amount_cents, 
            status=InstallmentStatus.PENDING,
            created_at=datetime.now()
        )