import time
from typing import Optional
from domain.entities import Decision, Plan
from domain.interfaces import TransactionRepository, DecisionRepository, PlanRepository, WebhookPort
from domain.services import RiskCalculationService
from infrastructure.logging.structlog_logs import logger
from infrastructure.metrics.metrics import gerald_decision_total, gerald_credit_limit_bucket

class ValidateDecisionService:
    def __init__(
        self,
        transaction_repo: TransactionRepository,
        decision_repo: Optional[DecisionRepository] = None,
        plan_repo: Optional[PlanRepository] = None,
        webhook_port: Optional[WebhookPort] = None
    ):
        """
        Initialize the decision validation service.
        
        Args:
            transaction_repo: Repository for fetching transactions (required)
            decision_repo: Repository for saving decisions (optional)
            plan_repo: Repository for saving plans (optional)
            webhook_port: Webhook port for sending webhooks to ledger (optional)
        """
        self.transaction_repo = transaction_repo
        self.decision_repo = decision_repo
        self.plan_repo = plan_repo
        self.webhook_port = webhook_port 
    
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
            transactions = await self.transaction_repo.get_user_transactions(user_id)
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
                limit_bucket = "$0"
            else:
                approved = amount_requested_cents <= risk_score['limit_amount']
                score = risk_score.get('final_score', 0.0)
                limit_bucket = risk_score.get('limit_bucket', '$0')
                log.info(
                    "risk_calculated",
                    step="risk_calculation",
                    duration_ms=round(calc_duration, 2),
                    score=score,
                    avg_daily_balance_cents=risk_score.get('avg_daily_balance_cents'),
                    monthly_income_cents=risk_score.get('monthly_income_cents'),
                    monthly_spend_cents=risk_score.get('monthly_spend_cents'),
                    nsf_count=risk_score.get('nsf_count'),
                    limit_bucket=limit_bucket,
                    limit_amount=risk_score.get('limit_amount')
                )
            
            # Step 3: Create decision
            decision = Decision.create(user_id=user_id, amount_requested_cents=amount_requested_cents)
            decision.set_score(score)
            
            if approved:
                amount_granted_cents = min(amount_requested_cents, risk_score['limit_amount'])
                plan = Plan.create(decision_id=decision.id, user_id=user_id, total_cents=amount_granted_cents)
                decision.set_plan(plan=plan)
                decision.set_approved(approved=approved)
                decision.set_amount_granted_cents(amount_granted_cents=amount_granted_cents)
                decision.set_credit_limit_cents(credit_limit_cents=risk_score['limit_amount'])
                
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
            
            # Emit metrics once at the end (avoid double counting)
            if 'error' in risk_score:
                gerald_decision_total.labels(outcome="error").inc()
            elif approved:
                gerald_decision_total.labels(outcome="approved").inc()
            else:
                gerald_decision_total.labels(outcome="declined").inc()
            
            # Emit credit limit bucket metric (only once)
            gerald_credit_limit_bucket.labels(bucket=limit_bucket).inc()
            
            # Save decision to database FIRST (before plan, since plan has FK to decision)
            if self.decision_repo:
                log.info("saving_decision", step="db_persist")
                await self.decision_repo.save_decision(decision, risk_score=risk_score, request_id=request_id)
            
            # Save plan to database AFTER decision is saved (plan references decision)
            if approved and self.plan_repo:
                log.info("saving_plan", step="db_persist")
                await self.plan_repo.save_plan(plan)
            
            # Send webhook to ledger if approved (AFTER persisting decision + plan)
            if approved and self.webhook_port:
                log.info("sending_webhook", step="webhook_send")
                webhook_start = time.time()
                webhook_success = await self.webhook_port.send_webhook(
                    plan_id=str(plan.id),
                    decision_id=str(decision.id),
                    user_id=user_id,
                    amount_granted_cents=amount_granted_cents,
                    request_id=request_id
                )
                webhook_duration = (time.time() - webhook_start) * 1000
                log.info(
                    "webhook_sent",
                    step="webhook_send",
                    success=webhook_success,
                    duration_ms=round(webhook_duration, 2)
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