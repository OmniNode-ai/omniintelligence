"""Configuration model for PostgresPattern Effect Node"""
from pydantic import BaseModel, Field
from typing import Literal

class ModelPostgresPatternEffectConfig(BaseModel):
    """Configuration for postgres_pattern operations."""
    timeout_ms: int = Field(default=30000, description="Timeout in ms", gt=0)
    max_retries: int = Field(default=3, description="Max retry attempts", ge=0)
    
    @classmethod
    def for_environment(cls, env: Literal["production", "staging", "development"]):
        if env == "production":
            return cls(timeout_ms=30000, max_retries=3)
        elif env == "staging":
            return cls(timeout_ms=60000, max_retries=5)
        else:
            return cls(timeout_ms=120000, max_retries=10)
