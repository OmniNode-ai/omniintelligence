"""Configuration model for Intelligence Reducer Node"""
from pydantic import BaseModel, Field
from typing import Literal

class ModelIntelligenceReducerConfig(BaseModel):
    """Configuration for reducer operations."""
    database_url: str = Field(..., description="Database connection URL")
    enable_lease_management: bool = Field(default=True, description="Enable lease management")
    lease_timeout_seconds: int = Field(default=300, description="Lease timeout in seconds")
    max_transition_retries: int = Field(default=3, description="Max FSM transition retries")
    
    @classmethod
    def for_environment(cls, env: Literal["production", "staging", "development"]):
        db_url = "postgresql://localhost:5432/omniintelligence"
        if env == "production":
            return cls(database_url=db_url, enable_lease_management=True, lease_timeout_seconds=300)
        elif env == "staging":
            return cls(database_url=db_url, enable_lease_management=True, lease_timeout_seconds=600)
        else:
            return cls(database_url=db_url, enable_lease_management=False, lease_timeout_seconds=1200)
