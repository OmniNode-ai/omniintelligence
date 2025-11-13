"""
Shared Pydantic Models for Archon Services

This package provides standardized data models that can be used across
all Archon services to ensure type safety and consistency.
"""

from .base_models import (
    BaseEntity,
    BaseRelationship,
    EntityMetadata,
    ServiceHealth,
)
from .communication import (
    EntitySyncRequest,
    EntitySyncResponse,
    ServiceRequest,
    ServiceResponse,
)
from .entity_types import (
    EntityType,
    EntityTypeMapper,
    IntelligenceEntityType,
    SearchEntityType,
)

__all__ = [
    # Entity Types
    "EntityType",
    "EntityTypeMapper",
    "IntelligenceEntityType",
    "SearchEntityType",
    # Base Models
    "BaseEntity",
    "BaseRelationship",
    "ServiceHealth",
    "EntityMetadata",
    # Communication
    "ServiceRequest",
    "ServiceResponse",
    "EntitySyncRequest",
    "EntitySyncResponse",
]
