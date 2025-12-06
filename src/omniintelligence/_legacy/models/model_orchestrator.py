"""
Orchestrator Models for omniintelligence.

Input, output, and configuration models for intelligence orchestrators.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumOperationType

from .model_intent import ModelIntent


class ModelOrchestratorInput(BaseModel):
    """Input model for intelligence orchestrator."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "operation_type": "DOCUMENT_INGESTION",
                "entity_id": "doc_123",
                "payload": {
                    "file_path": "src/main.py",
                    "content": "def main(): pass",
                },
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        }
    )

    operation_type: EnumOperationType = Field(..., description="Operation type")
    entity_id: str = Field(..., description="Entity identifier")
    payload: dict[str, Any] = Field(..., description="Operation payload")
    context: Optional[dict[str, Any]] = Field(None, description="Additional context")
    correlation_id: str = Field(..., description="Correlation ID")


class ModelOrchestratorOutput(BaseModel):
    """Output model for intelligence orchestrator."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "workflow_id": "wf_789",
                "results": {
                    "entities_extracted": 5,
                    "relationships_found": 8,
                },
            }
        }
    )

    success: bool = Field(..., description="Whether orchestration succeeded")
    workflow_id: str = Field(..., description="Workflow execution ID")
    results: Optional[dict[str, Any]] = Field(
        default=None, description="Workflow results"
    )
    intents: list[ModelIntent] = Field(
        default_factory=list, description="Emitted intents"
    )
    errors: list[str] = Field(default_factory=list, description="Error messages")


class ModelOrchestratorConfig(BaseModel):
    """Configuration for intelligence orchestrator."""

    model_config = ConfigDict(populate_by_name=True)

    max_concurrent_workflows: int = Field(10, description="Max concurrent workflows")
    workflow_timeout_ms: int = Field(
        300000,
        description="Workflow timeout in milliseconds",
        alias="workflow_timeout_seconds",
    )
    caching_enabled: bool = Field(
        True, description="Enable result caching", alias="enable_caching"
    )
    cache_ttl_ms: int = Field(
        300000, description="Cache TTL in milliseconds", alias="cache_ttl_seconds"
    )


__all__ = [
    "ModelOrchestratorConfig",
    "ModelOrchestratorInput",
    "ModelOrchestratorOutput",
]
