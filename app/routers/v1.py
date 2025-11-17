from fastapi import APIRouter, Depends, HTTPException, status, Request
from infrastructure.clients import TransactionRepoAPI, BankClient
from app.schemas.desicion_schema import DecisionCreate, DecisionResponse
from application.service.validate_decision import ValidateDecisionService
from domain.exceptions import BankAPIError
import uuid

def url_builder() -> str:
    return f"http://localhost:8001/"

router = APIRouter(prefix="/v1")

@router.post("/desicion")
async def desicion(payload: DecisionCreate, request: Request) -> DecisionResponse:
    # Obtain request ID from headers
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    
    try:
        srv = ValidateDecisionService(TransactionRepoAPI(
            BankClient(base_url=url_builder())))
        decision = await srv.execute(
            user_id=payload.user_id,
            amount_requested_cents=payload.amount_requested_cents,
            request_id=request_id
        )
        return DecisionResponse(
            approved=decision.approved, 
            credit_limit_cents=decision.credit_limit_cents, 
            amount_granted_cents=decision.amount_granted_cents, 
            plan_id=decision.plan.id if decision.plan else ""
        )
    except BankAPIError as e:
        # Return 503 on bank fetch failure as per codebase rules
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "bank_api_error", "message": str(e)}
        )

@router.get("/desicion/history")
async def desicion_history(user_id: str):
    return {"status": "ok", "message": "desicion history is running"}

@router.get("/plan/{plan_id}")
async def plan(plan_id: str):
    return {"status": "ok", "message": "plan is running"}
