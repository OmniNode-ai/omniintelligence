# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka event model for plan-review-strategy-run-completed.v1.

Emitted once per strategy run from node_plan_reviewer_multi_compute.

Ticket: OMN-3323
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelPlanReviewStrategyRunCompletedEvent(BaseModel):
    """Kafka event emitted once per strategy run from node_plan_reviewer_multi_compute.

    Published to: onex.evt.omniintelligence.plan-review-strategy-run-completed.v1

    Allowed strategies: S1_PANEL_VOTE, S2_SPECIALIST_SPLIT,
                        S3_SEQUENTIAL_CRITIQUE, S4_INDEPENDENT_MERGE
    Allowed model IDs: qwen3-coder, deepseek-r1, gemini-flash, glm-4

    Attributes:
        event_id: UUID string — unique per emission.
        node_id: Always "node_plan_reviewer_multi_compute".
        run_id: UUID string — unique per strategy run (from command.run_id or generated).
        strategy: EnumReviewStrategy.value — the strategy that was executed.
        models_used: List of EnumReviewModel.value strings that participated.
        plan_text_hash: SHA-256 hex digest of the input plan text.
        findings_count: Total number of findings in the output.
        blocks_count: Number of findings with severity == "BLOCK".
        categories_with_findings: EnumPlanReviewCategory values that had findings.
        categories_clean: EnumPlanReviewCategory values with no findings.
        avg_confidence: Mean confidence score across all findings, or None if no findings.
        tokens_used: Total tokens consumed (if available from LLM responses).
        duration_ms: Wall-clock duration of the full strategy run in milliseconds.
        strategy_run_stored: True when the audit row was written to the DB.
        model_weights: Snapshot of accuracy weights used — {model_id: score_correctness}.
        emitted_at: ISO 8601 timestamp of emission, e.g. 2026-03-01T19:00:00Z.

    Example::

        event = ModelPlanReviewStrategyRunCompletedEvent(
            event_id="550e8400-e29b-41d4-a716-446655440000",
            run_id="OMN-1234",
            strategy="S1_PANEL_VOTE",
            models_used=["qwen3-coder", "deepseek-r1"],
            plan_text_hash="abc123...",
            findings_count=2,
            blocks_count=1,
            categories_with_findings=["R1_COUNTS"],
            categories_clean=["R2_DEPENDENCIES", "R3_RISKS"],
            avg_confidence=0.85,
            tokens_used=1200,
            duration_ms=3400,
            strategy_run_stored=True,
            model_weights={"qwen3-coder": 0.72, "deepseek-r1": 0.68},
            emitted_at="2026-03-01T19:00:00Z",
        )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    """UUID string — unique per emission."""

    node_id: str = "node_plan_reviewer_multi_compute"
    """Always 'node_plan_reviewer_multi_compute'."""

    run_id: str
    """UUID string — unique per strategy run."""

    strategy: str
    """EnumReviewStrategy.value — the strategy that was executed."""

    models_used: list[str]
    """List of EnumReviewModel.value strings that participated."""

    plan_text_hash: str
    """SHA-256 hex digest of the input plan text."""

    findings_count: int
    """Total number of findings in the output."""

    blocks_count: int
    """Number of findings with severity == 'BLOCK'."""

    categories_with_findings: list[str]
    """EnumPlanReviewCategory values that had at least one finding."""

    categories_clean: list[str]
    """EnumPlanReviewCategory values with no findings."""

    avg_confidence: float | None
    """Mean confidence score across all findings, or None if no findings."""

    tokens_used: int | None
    """Total tokens consumed (if available from LLM responses)."""

    duration_ms: int | None
    """Wall-clock duration of the full strategy run in milliseconds."""

    strategy_run_stored: bool
    """True when the audit row was successfully written to plan_reviewer_strategy_runs."""

    model_weights: dict[str, float]
    """Snapshot of accuracy weights used — {model_id: score_correctness}."""

    emitted_at: str
    """ISO 8601 timestamp of emission, e.g. 2026-03-01T19:00:00Z."""


__all__ = ["ModelPlanReviewStrategyRunCompletedEvent"]
