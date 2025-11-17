"""
Database configuration and session management for async SQLAlchemy.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import os

# Import all models to ensure they're registered in the same registry
# This must happen before creating the engine
from infrastructure.db.models import Base, DecisionModel, PlanModel, InstallmentModel  # noqa: F401

# Database URL from environment or default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://root:root@localhost:5432/gerald"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    future=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncSession:
    """
    Dependency function to get database session.
    Use this in FastAPI route dependencies.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

