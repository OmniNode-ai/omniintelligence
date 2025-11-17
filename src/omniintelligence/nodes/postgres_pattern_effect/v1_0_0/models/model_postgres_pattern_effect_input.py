"""Input model for PostgresPattern Effect Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID, uuid4

class ModelPostgresPatternEffectInput(BaseModel):
    """Input model for postgres_pattern operations."""
    operation: str
pattern_data: Dict[str, Any]
project_name: str
    correlation_id: UUID = Field(default_factory=uuid4, description="Correlation ID")
