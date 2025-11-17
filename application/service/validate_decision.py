import time
from domain.entities import Decision, Plan
from domain.interfaces import TransactionRepository
from domain.services import RiskCalculationService
from infrastructure.logging.structlog_logs import logger

class ValidateDecisionService:
    def __init__(self, repo: TransactionRepository):
        self.repo = repo # Repository 
    
    async def execute(self, user_id: str, amount_requested_cents: int, request_id: str = None) -> Decision:
        """
        Execute the decision validation service.
        This service is used to validate a decision based on the user's transactions and risk score.

        Args:
            user_id: ID of the user
            amount_requested_cents: Amount requested in cents
            request_id: ID of the request for tracing (optional)
        """
        start_time = time.time()
        
        # Bind request_id and user_id to the logger to appear in all logs
        log = logger.bind(
            request_id=request_id or "unknown",
            user_id=user_id,
            step="decision_validation"
        )
        
        log.info("decision_validation_started", amount_requested_cents=amount_requested_cents)
        
        try:
            # Step 1: Get transactions
            log.info("fetching_transactions", step="bank_fetch")
            fetch_start = time.time()
            transactions = await self.repo.get_user_transactions(user_id)
            fetch_duration = (time.time() - fetch_start) * 1000
            log.info(
                "transactions_fetched",
                step="bank_fetch",
                duration_ms=round(fetch_duration, 2),
                transaction_count=len(transactions)
            )
            
            # Step 2: Calculate risk
            log.info("calculating_risk", step="risk_calculation")
            calc_start = time.time()
            risk_score = RiskCalculationService().calculate_risk(transactions)
            calc_duration = (time.time() - calc_start) * 1000
            
            if 'error' in risk_score:
                log.warning(
                    "risk_calculation_error",
                    step="risk_calculation",
                    duration_ms=round(calc_duration, 2),
                    error=risk_score.get('error')
                )
                approved = False
                score = 0.0
            else:
                approved = amount_requested_cents <= risk_score['limit_amount']
                score = risk_score.get('final_score', 0.0)
                log.info(
                    "risk_calculated",
                    step="risk_calculation",
                    duration_ms=round(calc_duration, 2),
                    score=score,
                    avg_daily_balance_cents=risk_score.get('avg_daily_balance_cents'),
                    monthly_income_cents=risk_score.get('monthly_income_cents'),
                    monthly_spend_cents=risk_score.get('monthly_spend_cents'),
                    nsf_count=risk_score.get('nsf_count'),
                    limit_bucket=risk_score.get('limit_bucket'),
                    limit_amount=risk_score.get('limit_amount')
                )
            
            # Step 3: Create decision
            decision = Decision.create(user_id=user_id, amount_requested_cents=amount_requested_cents)
            
            if approved:
                amount_granted_cents = min(amount_requested_cents, risk_score['limit_amount'])
                plan = Plan.create(decision_id=decision.id, user_id=user_id, total_cents=amount_granted_cents)
                decision.set_plan(plan=plan)
                decision.set_approved(approved=approved)
                decision.set_amount_granted_cents(amount_granted_cents=amount_granted_cents)
                decision.set_credit_limit_cents(credit_limit_cents=min(amount_requested_cents, risk_score['limit_amount']))
                
                log.info(
                    "decision_approved",
                    step="decision_creation",
                    approved=True,
                    score=score,
                    plan_id=str(plan.id),
                    amount_granted_cents=amount_granted_cents,
                    credit_limit_cents=decision.credit_limit_cents
                )
            else:
                decision.set_approved(approved=False)
                log.info(
                    "decision_declined",
                    step="decision_creation",
                    approved=False,
                    score=score,
                    reason="amount_exceeds_limit" if 'error' not in risk_score else "risk_calculation_error"
                )
            
            # Log final with total duration
            total_duration = (time.time() - start_time) * 1000
            log.info(
                "decision_validation_completed",
                step="decision_validation",
                duration_ms=round(total_duration, 2),
                approved=approved,
                score=score,
                plan_id=str(decision.plan.id) if decision.plan else None
            )
            
            return decision
            
        except Exception as e:
            total_duration = (time.time() - start_time) * 1000
            log.error(
                "decision_validation_failed",
                step="decision_validation",
                duration_ms=round(total_duration, 2),
                error=str(e),
                exc_info=True
            )
            raise