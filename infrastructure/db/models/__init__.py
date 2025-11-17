"""
Database models package.
Import Base from here or from base.py directly.
"""
from infrastructure.db.models.base import Base

# Import all models to ensure they're registered in the same registry
# This must be done after Base is created
from infrastructure.db.models.desicions import DecisionModel
from infrastructure.db.models.plans import PlanModel
from infrastructure.db.models.installments import InstallmentModel

__all__ = ["Base", "DecisionModel", "PlanModel", "InstallmentModel"]

