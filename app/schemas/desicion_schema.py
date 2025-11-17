# src/schemas/user_schema.py
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class DecisionCreate(BaseModel):
    user_id: str
    amount_requested_cents: int

class DecisionResponse(BaseModel):
    approved: bool
    credit_limit_cents: int
    amount_granted_cents: int
    plan_id: Optional[str] = None


class InstallmentResponse(BaseModel):
    id: str
    due_date: datetime
    amount_cents: int
    status: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PlanResponse(BaseModel):
    id: str
    decision_id: str
    user_id: str
    total_cents: int
    created_at: datetime
    installments: List[InstallmentResponse]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }