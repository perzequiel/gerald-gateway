from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Optional

from .installment import Installment

@dataclass
class Plan:
    id: str
    decision_id: str
    user_id: str
    total_cents: int
    created_at: datetime
    installments: Optional[list[Installment]] = None
    installments_count: int = 4
    days_between_installments: int = 14

    @staticmethod
    def create(decision_id: str, user_id: str, total_cents: int, installments_count: int = 4, days_between_installments: int = 14) -> 'Plan':
        plan = Plan(id=str(uuid4()), 
            decision_id=decision_id, 
            user_id=user_id,
            total_cents=total_cents,
            created_at=datetime.now(),
            installments_count=installments_count,
            days_between_installments=days_between_installments
        )

        installments = []
        for amount in range(1, installments_count + 1):
            due_date = plan.created_at + timedelta(days=amount * days_between_installments)
            installments.append(Installment.create(plan_id=plan.id, due_date=due_date, amount_cents=total_cents / installments_count))
        plan.installments = installments
        return plan