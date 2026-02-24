# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka command model for compliance evaluation.

Ticket: OMN-2339
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_compliance_evaluate_effect.models.model_applicable_pattern_payload import (
    ModelApplicablePatternPayload,
)


class ModelComplianceEvaluateCommand(BaseModel):
    """Kafka command payload from onex.cmd.omniintelligence.compliance-evaluate.v1.

    This is the wire-format model that omniclaude emits. The node deserializes
    incoming Kafka messages into this model before calling the handler.

    Idempotency:
        The tuple (source_path, content_sha256, pattern_id) is the idempotency
        key per OMN-2339 requirements. correlation_id is NOT part of the key.

    Attributes:
        correlation_id: UUID for end-to-end tracing (NOT the idempotency key).
        source_path: Path of the source file being evaluated.
        content: Source code content to evaluate.
        content_sha256: SHA-256 hex digest of content for idempotency keying.
        language: Programming language of the content.
        applicable_patterns: Patterns to check compliance against.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for end-to-end tracing (NOT the idempotency key)",
    )
    source_path: str = Field(
        ...,
        min_length=1,
        description="Path to the source file being evaluated",
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=1_000_000,
        description="Source code content to evaluate for compliance",
    )
    content_sha256: str = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "SHA-256 hex digest of content. "
            "Used as idempotency key together with source_path and pattern_id."
        ),
    )
    language: str = Field(
        default="python",
        description="Programming language of the content",
    )
    applicable_patterns: list[ModelApplicablePatternPayload] = Field(
        ...,
        min_length=1,
        description="Patterns to check compliance against (from pattern store API)",
    )
    session_id: str | None = Field(
        default=None,
        description="Session identifier for tracing; provided when invoked from a hook context.",
    )


__all__ = ["ModelComplianceEvaluateCommand"]
