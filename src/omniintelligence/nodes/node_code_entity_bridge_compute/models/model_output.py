# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for the code entity → learned pattern bridge compute node.

Ticket: OMN-7863
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelDerivedPattern(BaseModel):
    """A single learned pattern derived from one or more code entities."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    pattern_id: UUID = Field(..., description="Generated UUID for this pattern")
    pattern_signature: str = Field(
        ..., description="Human-readable pattern signature text"
    )
    signature_hash: str = Field(
        ..., description="SHA256 of canonicalized signature for stable lineage identity"
    )
    domain_id: str = Field(..., description="Domain identifier")
    domain_version: str = Field(default="1.0", description="Domain version")
    confidence: float = Field(..., ge=0.5, le=1.0, description="Pattern confidence")
    keywords: list[str] = Field(
        default_factory=list, description="Extracted keywords for search"
    )
    source_entity_ids: list[str] = Field(
        default_factory=list, description="IDs of source code entities"
    )
    entity_type: str = Field(
        ..., description="Entity type this pattern was derived from"
    )
    project_scope: str | None = Field(
        default=None,
        description="Optional project scope. NULL means global.",
    )
    canary_id: str | None = Field(
        default=None,
        description="Optional canary tag for A/B testing",
    )
    compiled_snippet: str | None = Field(
        default=None,
        description="Ready-to-inject snippet for context injection",
    )


class ModelCodeEntityBridgeOutput(BaseModel):
    """Output from deriving learned patterns from code entities."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    correlation_id: UUID = Field(..., description="End-to-end tracing identifier")
    source_repo: str = Field(..., description="Source repository")
    derived_patterns: list[ModelDerivedPattern] = Field(
        default_factory=list,
        description="Patterns derived and ready for upsert into learned_patterns",
    )
    skipped_count: int = Field(
        default=0,
        ge=0,
        description="Number of entities skipped (below confidence threshold or unsupported type)",
    )
    error_count: int = Field(
        default=0,
        ge=0,
        description="Number of entities that caused derivation errors",
    )
    duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total processing duration in milliseconds",
    )


__all__ = ["ModelCodeEntityBridgeOutput", "ModelDerivedPattern"]
