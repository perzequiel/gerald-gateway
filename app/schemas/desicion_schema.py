# src/schemas/user_schema.py
from typing import Optional
from pydantic import BaseModel

class DecisionCreate(BaseModel):
    user_id: str
    amount_requested_cents: int

class DecisionResponse(BaseModel):
    approved: bool
    credit_limit_cents: int
    amount_granted_cents: int
    plan_id: Optional[str] = None