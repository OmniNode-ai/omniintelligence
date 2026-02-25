# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for the evidence collection effect node (OMN-2578)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ModelCollectionOutput"]


class ModelCollectionOutput(BaseModel):
    """Output from the evidence collection evaluation pipeline.

    Returned after collection and evaluation complete (or are skipped).
    Carries enough information for callers to track the evaluation outcome
    without requiring access to the full EvidenceBundle or EvaluationResult.

    Attributes:
        run_id: The run that was evaluated.
        session_id: The Claude Code session identifier.
        bundle_fingerprint: SHA-256 fingerprint of the EvidenceBundle.
            None if collection was skipped (no evidence items collected).
        passed: True if all gates passed. None if evaluation was skipped.
        evidence_item_count: Number of EvidenceItems collected.
        kafka_emitted: True if RunEvaluatedEvent was successfully published.
        db_stored: True if EvaluationResult was stored in the database.
        skipped: True if evaluation was skipped (no evidence items available).
        skip_reason: Human-readable reason for skip (only set when skipped=True).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(description="The run that was evaluated.")
    session_id: str = Field(description="Claude Code session identifier.")
    bundle_fingerprint: str | None = Field(
        default=None,
        description=(
            "SHA-256 fingerprint of the EvidenceBundle. None if collection was skipped."
        ),
    )
    passed: bool | None = Field(
        default=None,
        description="True if all gates passed. None if evaluation was skipped.",
    )
    evidence_item_count: int = Field(
        default=0,
        ge=0,
        description="Number of EvidenceItems collected from the session.",
    )
    kafka_emitted: bool = Field(
        default=False,
        description="True if RunEvaluatedEvent was successfully published to Kafka.",
    )
    db_stored: bool = Field(
        default=False,
        description="True if EvaluationResult was stored in the database.",
    )
    skipped: bool = Field(
        default=False,
        description="True if evaluation was skipped (no evidence items available).",
    )
    skip_reason: str | None = Field(
        default=None,
        description="Human-readable reason for skip. Only set when skipped=True.",
    )
