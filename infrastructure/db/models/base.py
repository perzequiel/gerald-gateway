"""
Shared base for all database models.
All models should import Base from here to ensure they're in the same registry.
"""
from sqlalchemy.orm import registry

# Create a single shared registry and base for all models
mapper_registry = registry()
Base = mapper_registry.generate_base()

