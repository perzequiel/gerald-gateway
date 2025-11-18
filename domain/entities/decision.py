from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4
from .plan import Plan

@dataclass
class Decision:
    id: str
    user_id: str
    amount_requested_cents: int
    approved: bool
    credit_limit_cents: int
    amount_granted_cents: int
    score: float
    created_at: datetime
    plan: Optional[Plan] = None

    @staticmethod
    def create(user_id: str, amount_requested_cents: int) -> 'Decision':
        return Decision(id=str(uuid4()),
            user_id=user_id, 
            amount_requested_cents=amount_requested_cents,
            created_at=datetime.now(),
            approved=False,
            credit_limit_cents=0,
            amount_granted_cents=0,
            score=0.0)
    
    def set_approved(self, approved: bool) -> 'Decision':
        self.approved = approved
        return self

    def set_plan(self, plan: Plan) -> 'Decision':
        self.plan = plan
        return self

    def set_amount_granted_cents(self, amount_granted_cents: int) -> 'Decision':
        self.amount_granted_cents = amount_granted_cents
        return self

    def set_credit_limit_cents(self, credit_limit_cents: int) -> 'Decision':
        self.credit_limit_cents = credit_limit_cents
        return self
    
    def set_score(self, score: float) -> 'Decision':
        self.score = score
        return self