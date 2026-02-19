# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Input model for node_compliance_evaluate_effect.

Defines the Kafka command payload emitted by omniclaude (PR #161) on topic
onex.cmd.omniintelligence.compliance-evaluate.v1.

The command carries the same information as ModelComplianceRequest from
node_pattern_compliance_effect, plus a content_sha256 fingerprint used
as the idempotency key (OMN-2339: idempotency key is
(source_path, content_sha256, pattern_id), NOT correlation_id).

Ticket: OMN-2339
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelApplicablePatternPayload(BaseModel):
    """A pattern serialized inside a compliance-evaluate command.

    Mirrors the fields that omniclaude places in the Kafka payload for
    each pattern.  Kept separate from ModelApplicablePattern (OMN-2256)
    so the two nodes evolve independently.

    Attributes:
        pattern_id: Unique identifier for the pattern.
        pattern_signature: The pattern signature text.
        domain_id: Domain the pattern belongs to.
        confidence: Confidence score (0.0-1.0).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the pattern",
    )
    pattern_signature: str = Field(
        ...,
        min_length=1,
        description="Pattern signature text describing what the pattern enforces",
    )
    domain_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Domain the pattern belongs to",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the pattern (0.0-1.0)",
    )


class ModelComplianceEvaluateCommand(BaseModel):
    """Kafka command payload from onex.cmd.omniintelligence.compliance-evaluate.v1.

    This is the wire-format model that omniclaude emits.  The node deserializes
    incoming Kafka messages into this model before calling the handler.

    Idempotency:
        The tuple (source_path, content_sha256, pattern_id) is the idempotency
        key per OMN-2339 requirements.  correlation_id is NOT part of the key.

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


__all__ = ["ModelApplicablePatternPayload", "ModelComplianceEvaluateCommand"]
