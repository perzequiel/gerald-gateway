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
    
    async def get_decision(self, decision_id: str) -> Optional[Decision]:
        """Get a decision by ID."""
        stmt = select(DecisionModel).where(DecisionModel.id == decision_id)
        result = await self.db.execute(stmt)
        decision_model = result.scalar_one_or_none()
        return decision_model.to_domain() if decision_model else None
    
    async def get_decision_by_request_id(self, request_id: str) -> Optional[Decision]:
        """
        Get a decision by request ID (for idempotency).
        
        Uses the risk_factors JSONB field to store and search for request_id.
        The request_id is stored as risk_factors->_request_id.
        """
        if not request_id:
            return None
        # Search in risk_factors JSONB field using PostgreSQL JSONB operators
        # risk_factors->'_request_id' extracts the _request_id field
        stmt = select(DecisionModel).where(
            DecisionModel.risk_factors['_request_id'].astext == request_id
        )
        result = await self.db.execute(stmt)
        decision_model = result.scalar_one_or_none()
        return decision_model.to_domain() if decision_model else None
    
    async def save_decision(self, decision: Decision, risk_score: Optional[dict] = None, request_id: Optional[str] = None) -> Decision:
        """
        Save a decision to the database.
        
        Args:
            decision: Domain Decision entity
            risk_score: Optional risk score dict
            request_id: Optional request ID for idempotency (stored in risk_factors)
            
        Returns:
            Saved Decision entity
        """
        # Check for existing decision with same request_id before saving
        if request_id:
            existing = await self.get_decision_by_request_id(request_id)
            if existing:
                return existing
        
        decision_model = DecisionModel.from_domain(decision, risk_score=risk_score, request_id=request_id)
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

