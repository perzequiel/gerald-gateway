from domain.entities import Decision, Plan
from domain.repositories import DecisionRepository

class ValidateDecisionService:
    def __init__(self, repo: DecisionRepository):
        self.repo = repo # Repository 
    
    async def execute(self, user_id: str, amount_requested_cents: int) -> Decision:
        # transactions = await self.repo.get_user_transactions(user_id)
        approved = False if amount_requested_cents > 1000 else True # simulate high risk
        decision = Decision.create(user_id=user_id, amount_requested_cents=amount_requested_cents)
        if approved:
            amount_granted_cents = amount_requested_cents * 0.8 # simulate 20% discount
            plan = Plan.create(decision_id=decision.id, user_id=user_id, total_cents=amount_granted_cents)
            decision.set_plan(plan=plan)
            decision.set_approved(approved=approved)
            decision.set_amount_granted_cents(amount_granted_cents=amount_granted_cents)
        return decision