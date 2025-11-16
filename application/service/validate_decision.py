from domain.entities import Decision, Plan
from domain.repositories import DecisionRepository
from domain.services.risk_calculation import RiskCalculationService

class ValidateDecisionService:
    def __init__(self, repo: DecisionRepository):
        self.repo = repo # Repository 
    
    async def execute(self, user_id: str, amount_requested_cents: int) -> Decision:
        transactions = await self.repo.get_user_transactions(user_id)
        risk_score = RiskCalculationService().calculate_risk(transactions)
        if 'error' in risk_score:
            approved = False
        else:
            approved = amount_requested_cents <= risk_score['limit_amount']
        decision = Decision.create(user_id=user_id, amount_requested_cents=amount_requested_cents)
        if approved:
            amount_granted_cents = min(amount_requested_cents, risk_score['limit_amount'])
            plan = Plan.create(decision_id=decision.id, user_id=user_id, total_cents=amount_granted_cents)
            decision.set_plan(plan=plan)
            decision.set_approved(approved=approved)
            decision.set_amount_granted_cents(amount_granted_cents=amount_granted_cents)
            decision.set_credit_limit_cents(credit_limit_cents=min(amount_requested_cents, risk_score['limit_amount']))
        return decision