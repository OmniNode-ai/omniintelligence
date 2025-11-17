"""Configuration model for Intelligence Orchestrator Node"""
from pydantic import BaseModel, Field
from typing import Literal
from .....shared.enums import EnumRAGProvider

class ModelIntelligenceOrchestratorConfig(BaseModel):
    """Configuration for orchestrator operations."""
    max_concurrent_workflows: int = Field(default=10, description="Max concurrent workflows")
    workflow_timeout_seconds: int = Field(default=300, description="Workflow timeout")
    enable_caching: bool = Field(default=True, description="Enable caching")
    cache_ttl_seconds: int = Field(default=300, description="Cache TTL")
    rag_provider: EnumRAGProvider = Field(default=EnumRAGProvider.CUSTOM, description="RAG provider")
    enable_haystack_rag: bool = Field(default=False, description="Enable Haystack RAG")
    
    @classmethod
    def for_environment(cls, env: Literal["production", "staging", "development"]):
        if env == "production":
            return cls(max_concurrent_workflows=10, workflow_timeout_seconds=300)
        elif env == "staging":
            return cls(max_concurrent_workflows=5, workflow_timeout_seconds=600)
        else:
            return cls(max_concurrent_workflows=2, workflow_timeout_seconds=1200)
