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
        # Calculate base amount per installment (integer division)
        base_amount = total_cents // installments_count
        # Last installment absorbs any remainder (≤ 1 cent)
        remainder = total_cents % installments_count
        
        for i in range(1, installments_count + 1):
            due_date = plan.created_at + timedelta(days=i * days_between_installments)
            # Last installment gets base_amount + remainder
            amount_cents = base_amount + remainder if i == installments_count else base_amount
            installments.append(Installment.create(plan_id=plan.id, due_date=due_date, amount_cents=amount_cents))
        plan.installments = installments
        return plan