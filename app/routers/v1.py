from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from application.service.decision_history import DecisionHistoryService
from application.service.get_plan import GetPlanService
from infrastructure.clients import TransactionRepoAPI, BankClient
from infrastructure.db.database import get_db_session
from infrastructure.db.repositories.decision_repo_sqlalchemy import DecisionRepoSqlalchemy
from infrastructure.db.repositories.plan_repo_sqlalchemy import PlanRepoSqlalchemy
from app.schemas.desicion_schema import DecisionCreate, DecisionResponse, PlanResponse, InstallmentResponse
from application.service.validate_decision import ValidateDecisionService
from domain.exceptions import BankAPIError
import uuid

def url_builder() -> str:
    return f"http://localhost:8001/"

router = APIRouter(prefix="/v1")

@router.post("/desicion")
async def desicion(
    payload: DecisionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) -> DecisionResponse:
    """
    Create a decision for a user.
    
    This endpoint:
    - Fetches transactions from the bank API
    - Calculates risk score
    - Creates decision and plan (if approved)
    - Saves to database if repositories are configured
    """
    # Obtain request ID from headers
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    
    try:
        # Create transaction repository (API-based)
        transaction_repo = TransactionRepoAPI(BankClient(base_url=url_builder()))
        
        # Create decision and plan repositories (database-based)
        decision_repo = DecisionRepoSqlalchemy(db)
        plan_repo = PlanRepoSqlalchemy(db)
        
        # Initialize service with all repositories
        srv = ValidateDecisionService(
            transaction_repo=transaction_repo,
            decision_repo=decision_repo,
            plan_repo=plan_repo
        )
        
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
async def desicion_history(user_id: str, db: AsyncSession = Depends(get_db_session)) -> list[DecisionResponse]:
    """
    Get the history of decisions for a user.
    """
    decision_repo = DecisionRepoSqlalchemy(db)
    srv = DecisionHistoryService(decision_repo)
    decisions = await srv.execute(user_id)
    return decisions

@router.get("/plan/{plan_id}")
async def plan(plan_id: str, db: AsyncSession = Depends(get_db_session)) -> PlanResponse:
    """
    Get a plan by ID with its repayment schedule.
    
    Returns the plan with 4 installments, each 14 days apart.
    Installment dates are in ISO8601 format.
    """
    plan_repo = PlanRepoSqlalchemy(db)
    srv = GetPlanService(plan_repo)
    plan = await srv.execute(plan_id)
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "plan_not_found", "message": f"Plan with id {plan_id} not found"}
        )
    
    # Convert installments to response format
    installments = []
    if plan.installments:
        installments = [
            InstallmentResponse(
                id=inst.id,
                due_date=inst.due_date,
                amount_cents=inst.amount_cents,
                status=inst.status
            )
            for inst in plan.installments
        ]
    
    return PlanResponse(
        id=plan.id,
        decision_id=plan.decision_id,
        user_id=plan.user_id,
        total_cents=plan.total_cents,
        created_at=plan.created_at,
        installments=installments
    )
