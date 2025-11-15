from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

@dataclass
class Plan:
    id: str
    decision_id: str
    user_id: str
    total_cents: int
    created_at: datetime

    @staticmethod
    def create(decision_id: str, user_id: str, total_cents: int) -> 'Plan':
        return Plan(id=str(uuid4()), 
            decision_id=decision_id, 
            user_id=user_id,
            total_cents=total_cents,
            created_at=datetime.now())