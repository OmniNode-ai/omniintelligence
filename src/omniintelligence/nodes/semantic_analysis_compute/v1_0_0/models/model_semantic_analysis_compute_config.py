"""Configuration model for SemanticAnalysis Compute Node"""
from pydantic import BaseModel, Field
from typing import Literal

class ModelSemanticAnalysisComputeConfig(BaseModel):
    """Configuration for semantic_analysis operations."""
    timeout_ms: int = Field(default=30000, description="Timeout in ms", gt=0)
    enable_caching: bool = Field(default=True, description="Enable caching")
    
    @classmethod
    def for_environment(cls, env: Literal["production", "staging", "development"]):
        if env == "production":
            return cls(timeout_ms=30000)
        elif env == "staging":
            return cls(timeout_ms=60000)
        else:
            return cls(timeout_ms=120000)
