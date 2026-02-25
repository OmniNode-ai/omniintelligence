# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""RunEvaluatedEvent model for the evidence collection node (OMN-2578).

Emitted to Kafka after each successful objective evaluation at session end.
Topic: onex.evt.omniintelligence.run-evaluated.v1

This event carries the full evaluation result and the bundle fingerprint
for replay verification. Consumers (omnidash, policy state reducer) subscribe
to this topic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ModelRunEvaluatedEvent"]


class ModelRunEvaluatedEvent(BaseModel):
    """Kafka event emitted after a run is evaluated against an objective spec.

    Published to: onex.evt.omniintelligence.run-evaluated.v1

    Consumers:
        - NodePolicyStateReducer (OMN-2557): Updates policy state based on result.
        - omnidash: Displays objective scores in the analytics dashboard.
        - omniintelligence audit: Stores full evaluation for replay verification.

    Attributes:
        run_id: The run that was evaluated (same as EvidenceBundle.run_id).
        session_id: The Claude Code session identifier.
        task_class: Task class for which the evaluation was performed.
        bundle_fingerprint: SHA-256 fingerprint of the evidence bundle.
        passed: True if all hard gates passed; False otherwise.
        failures: Gate IDs that failed (empty if passed=True).
        score_correctness: Correctness dimension of the score vector.
        score_safety: Safety dimension of the score vector.
        score_cost: Cost efficiency dimension of the score vector.
        score_latency: Latency dimension of the score vector.
        score_maintainability: Maintainability dimension of the score vector.
        score_human_time: Human time saved dimension of the score vector.
        evaluated_at_utc: ISO-8601 UTC timestamp when evaluation completed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(
        description="The run that was evaluated (matches EvidenceBundle.run_id)."
    )
    session_id: str = Field(
        description="Claude Code session identifier (opaque string from upstream API)."
    )
    task_class: str = Field(
        default="default",
        description="Task class for which evaluation was performed.",
    )
    bundle_fingerprint: str = Field(
        description="SHA-256 fingerprint of the EvidenceBundle used for evaluation."
    )
    passed: bool = Field(
        description="True if all hard gates passed; False if any gate failed."
    )
    failures: tuple[str, ...] = Field(
        default=(),
        description="Gate IDs that failed. Empty when passed=True.",
    )
    score_correctness: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Correctness dimension of the score vector.",
    )
    score_safety: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Safety dimension of the score vector.",
    )
    score_cost: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Cost efficiency dimension of the score vector.",
    )
    score_latency: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Latency dimension of the score vector.",
    )
    score_maintainability: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Maintainability dimension of the score vector.",
    )
    score_human_time: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Human time saved dimension of the score vector.",
    )
    evaluated_at_utc: str = Field(
        description="ISO-8601 UTC timestamp when evaluation was completed."
    )
