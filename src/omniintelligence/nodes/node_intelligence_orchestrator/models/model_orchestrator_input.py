# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for Intelligence Orchestrator."""

from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel, Field

from omniintelligence.enums import EnumOrchestratorWorkflowType


class OrchestratorPayloadDict(TypedDict, total=False):
    """Typed structure for orchestrator operation payload.

    Provides type-safe fields for workflow payload data.
    All fields are optional (total=False) to support different workflow types.
    """

    # Document ingestion fields
    content: str
    file_path: str
    source_type: str
    document_hash: str

    # Pattern learning fields
    pattern_name: str
    training_data: list[str]
    confidence_threshold: float

    # Quality assessment fields
    quality_dimensions: list[str]
    include_recommendations: bool

    # Semantic analysis fields
    embedding_model: str
    similarity_threshold: float

    # Common fields
    options: dict[str, bool]


class OrchestratorContextDict(TypedDict, total=False):
    """Typed structure for orchestrator operation context.

    Provides type-safe fields for operation context.
    All fields are optional (total=False) for flexibility.
    """

    # Source information
    source_repository: str
    source_branch: str
    source_commit: str

    # User/session info
    user_id: str
    session_id: str
    request_id: str

    # Processing hints
    priority: int
    timeout_ms: int
    max_retries: int

    # Environment
    environment: str
    debug_mode: bool


class ModelOrchestratorInput(BaseModel):
    """Input model for intelligence orchestrator operations.

    This model represents the input to the intelligence orchestrator,
    containing the operation type, entity identifier, payload data,
    and correlation ID for distributed tracing.

    All fields use strong typing without dict[str, Any].
    """

    operation_type: EnumOrchestratorWorkflowType = Field(
        ...,
        description="Type of intelligence operation (e.g., DOCUMENT_INGESTION, PATTERN_LEARNING)",
    )
    entity_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the entity being processed",
    )
    payload: OrchestratorPayloadDict = Field(
        ...,
        description="Operation-specific payload data with typed fields",
    )
    context: OrchestratorContextDict = Field(
        default_factory=lambda: OrchestratorContextDict(),
        description="Additional context for the operation with typed fields",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for distributed tracing",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelOrchestratorInput",
    "OrchestratorContextDict",
    "OrchestratorPayloadDict",
]
