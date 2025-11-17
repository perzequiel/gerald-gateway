from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from domain.entities import Decision
from domain.interfaces import DecisionRepository
from infrastructure.db.models.desicions import DecisionModel


class DecisionRepoSqlalchemy(DecisionRepository):
    """SQLAlchemy implementation of DecisionRepository."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def save_decision(self, decision: Decision, risk_score: Optional[dict] = None) -> Decision:
        """Save a decision to the database."""
        decision_model = DecisionModel.from_domain(decision, risk_score=risk_score)
        self.db.add(decision_model)
        await self.db.commit()
        await self.db.refresh(decision_model)
        return decision
    
    async def get_user_decisions(self, user_id: str, limit: int = 10) -> list[Decision]:
        """Get recent decisions for a user."""
        stmt = (
            select(DecisionModel)
            .where(DecisionModel.user_id == user_id)
            .order_by(DecisionModel.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        decision_models = result.scalars().all()
        return [dm.to_domain() for dm in decision_models]

