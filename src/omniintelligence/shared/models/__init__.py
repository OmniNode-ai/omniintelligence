"""
Shared models for omniintelligence.

Data models used across all nodes for consistency.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from ..enums import (
    EnumFSMType,
    EnumOperationType,
    EnumIntentType,
    EnumFSMAction,
    EnumEntityType,
    EnumRelationshipType,
    EnumQualityDimension,
    EnumRAGProvider,
)


# ============================================================================
# Intent Models
# ============================================================================

class ModelIntent(BaseModel):
    """
    Intent emitted by reducers to orchestrators or effect nodes.

    Intents are the primary communication mechanism in the system,
    allowing pure reducers to request actions without side effects.
    """
    intent_type: EnumIntentType = Field(..., description="Type of intent")
    target: str = Field(..., description="Target node for this intent")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Intent payload")
    correlation_id: str = Field(..., description="Correlation ID for tracing")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Intent creation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "intent_type": "WORKFLOW_TRIGGER",
                "target": "intelligence_orchestrator",
                "payload": {
                    "operation_type": "DOCUMENT_INGESTION",
                    "entity_id": "doc_123"
                },
                "correlation_id": "corr_456",
            }
        }


# ============================================================================
# Reducer Models
# ============================================================================

class ModelReducerInput(BaseModel):
    """Input model for intelligence reducer."""
    fsm_type: EnumFSMType = Field(..., description="Type of FSM")
    entity_id: str = Field(..., description="Entity identifier")
    action: EnumFSMAction = Field(..., description="FSM action to execute")
    payload: Optional[Dict[str, Any]] = Field(None, description="Action payload")
    correlation_id: str = Field(..., description="Correlation ID")
    lease_id: Optional[str] = Field(None, description="Action lease ID")
    epoch: Optional[int] = Field(None, description="Lease epoch")

    class Config:
        json_schema_extra = {
            "example": {
                "fsm_type": "INGESTION",
                "entity_id": "doc_123",
                "action": "START_PROCESSING",
                "correlation_id": "corr_456",
            }
        }


class ModelReducerOutput(BaseModel):
    """Output model for intelligence reducer."""
    success: bool = Field(..., description="Whether transition succeeded")
    previous_state: Optional[str] = Field(None, description="Previous FSM state")
    current_state: str = Field(..., description="Current FSM state")
    intents: List[ModelIntent] = Field(default_factory=list, description="Emitted intents")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Transition metadata")
    errors: List[str] = Field(default_factory=list, description="Error messages")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "previous_state": "RECEIVED",
                "current_state": "PROCESSING",
                "intents": [],
            }
        }


class ModelReducerConfig(BaseModel):
    """Configuration for intelligence reducer."""
    database_url: str = Field(..., description="PostgreSQL connection URL")
    enable_lease_management: bool = Field(True, description="Enable action leases")
    lease_timeout_seconds: int = Field(300, description="Lease timeout")
    max_retry_attempts: int = Field(3, description="Max retry attempts")


# ============================================================================
# Orchestrator Models
# ============================================================================

class ModelOrchestratorInput(BaseModel):
    """Input model for intelligence orchestrator."""
    operation_type: EnumOperationType = Field(..., description="Operation type")
    entity_id: str = Field(..., description="Entity identifier")
    payload: Dict[str, Any] = Field(..., description="Operation payload")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    correlation_id: str = Field(..., description="Correlation ID")

    class Config:
        json_schema_extra = {
            "example": {
                "operation_type": "DOCUMENT_INGESTION",
                "entity_id": "doc_123",
                "payload": {
                    "file_path": "src/main.py",
                    "content": "def main(): pass"
                },
                "correlation_id": "corr_456",
            }
        }


class ModelOrchestratorOutput(BaseModel):
    """Output model for intelligence orchestrator."""
    success: bool = Field(..., description="Whether orchestration succeeded")
    workflow_id: str = Field(..., description="Workflow execution ID")
    results: Optional[Dict[str, Any]] = Field(None, description="Workflow results")
    intents: List[ModelIntent] = Field(default_factory=list, description="Emitted intents")
    errors: List[str] = Field(default_factory=list, description="Error messages")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "workflow_id": "wf_789",
                "results": {
                    "entities_extracted": 5,
                    "relationships_found": 8
                },
            }
        }


class ModelOrchestratorConfig(BaseModel):
    """Configuration for intelligence orchestrator."""
    max_concurrent_workflows: int = Field(10, description="Max concurrent workflows")
    workflow_timeout_seconds: int = Field(300, description="Workflow timeout")
    enable_caching: bool = Field(True, description="Enable result caching")
    cache_ttl_seconds: int = Field(300, description="Cache TTL")

    # Feature flags for RAG provider selection
    rag_provider: EnumRAGProvider = Field(
        EnumRAGProvider.CUSTOM,
        description="RAG provider to use (CUSTOM or HAYSTACK) for A/B testing"
    )
    enable_haystack_rag: bool = Field(
        False,
        description="Enable Haystack RAG workflow (feature flag)"
    )


# ============================================================================
# Entity Models
# ============================================================================

class ModelEntity(BaseModel):
    """Entity model for knowledge graph."""
    entity_id: str = Field(..., description="Unique entity identifier")
    entity_type: EnumEntityType = Field(..., description="Entity type")
    name: str = Field(..., description="Entity name")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Entity metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "entity_id": "ent_123",
                "entity_type": "CLASS",
                "name": "MyClass",
                "metadata": {"file_path": "src/main.py"},
            }
        }


class ModelRelationship(BaseModel):
    """Relationship model for knowledge graph."""
    source_id: str = Field(..., description="Source entity ID")
    target_id: str = Field(..., description="Target entity ID")
    relationship_type: EnumRelationshipType = Field(..., description="Relationship type")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Relationship metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "source_id": "ent_123",
                "target_id": "ent_456",
                "relationship_type": "CONTAINS",
            }
        }


# ============================================================================
# Quality Models
# ============================================================================

class ModelQualityScore(BaseModel):
    """Quality assessment score."""
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score")
    dimensions: Dict[EnumQualityDimension, float] = Field(..., description="Dimension scores")
    onex_compliant: bool = Field(..., description="ONEX compliance status")
    compliance_issues: List[str] = Field(default_factory=list, description="Compliance issues")
    recommendations: List[Dict[str, Any]] = Field(default_factory=list, description="Recommendations")

    class Config:
        json_schema_extra = {
            "example": {
                "overall_score": 0.85,
                "dimensions": {
                    "MAINTAINABILITY": 0.9,
                    "READABILITY": 0.8,
                },
                "onex_compliant": True,
            }
        }


# ============================================================================
# FSM State Model
# ============================================================================

class ModelFSMState(BaseModel):
    """FSM state representation."""
    fsm_type: EnumFSMType = Field(..., description="FSM type")
    entity_id: str = Field(..., description="Entity identifier")
    current_state: str = Field(..., description="Current state")
    previous_state: Optional[str] = Field(None, description="Previous state")
    transition_timestamp: datetime = Field(..., description="Last transition timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="State metadata")
    lease_id: Optional[str] = Field(None, description="Current lease ID")
    lease_epoch: Optional[int] = Field(None, description="Lease epoch")
    lease_expires_at: Optional[datetime] = Field(None, description="Lease expiration")

    class Config:
        json_schema_extra = {
            "example": {
                "fsm_type": "INGESTION",
                "entity_id": "doc_123",
                "current_state": "PROCESSING",
                "previous_state": "RECEIVED",
                "transition_timestamp": "2025-11-14T12:00:00Z",
            }
        }


# ============================================================================
# Workflow Models
# ============================================================================

class ModelWorkflowStep(BaseModel):
    """Workflow step definition."""
    name: str = Field(..., description="Step name")
    step_type: str = Field(..., description="Step type")
    description: Optional[str] = Field(None, description="Step description")
    depends_on: List[str] = Field(default_factory=list, description="Dependencies")
    input_data: Optional[Dict[str, Any]] = Field(None, description="Step input")
    output_key: Optional[str] = Field(None, description="Output key")


class ModelWorkflowExecution(BaseModel):
    """Workflow execution state."""
    workflow_id: str = Field(..., description="Workflow ID")
    operation_type: EnumOperationType = Field(..., description="Operation type")
    status: str = Field(..., description="Execution status")
    current_step: Optional[str] = Field(None, description="Current step")
    completed_steps: List[str] = Field(default_factory=list, description="Completed steps")
    failed_step: Optional[str] = Field(None, description="Failed step")
    started_at: datetime = Field(..., description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    results: Optional[Dict[str, Any]] = Field(None, description="Execution results")


__all__ = [
    "ModelIntent",
    "ModelReducerInput",
    "ModelReducerOutput",
    "ModelReducerConfig",
    "ModelOrchestratorInput",
    "ModelOrchestratorOutput",
    "ModelOrchestratorConfig",
    "ModelEntity",
    "ModelRelationship",
    "ModelQualityScore",
    "ModelFSMState",
    "ModelWorkflowStep",
    "ModelWorkflowExecution",
]
