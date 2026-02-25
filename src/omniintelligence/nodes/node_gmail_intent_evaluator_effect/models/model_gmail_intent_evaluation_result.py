# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Result models for the Gmail Intent Evaluator.

Reference:
    - OMN-2788: Add ModelGmailIntentEvaluatorConfig + ModelGmailIntentEvaluationResult
    - OMN-2787: Gmail Intent Evaluator — Email-to-Initial-Plan Pipeline
"""

from typing import Literal

from omnibase_core.types import JsonType
from pydantic import BaseModel, ConfigDict, Field


class ModelMemoryHit(BaseModel):
    """A single omnimemory retrieval result for duplicate detection.

    Attributes:
        item_id: Unique identifier of the memory item.
        score: Similarity score in range [0.0, 1.0].
        snippet: Short title or tag summary (empty string if unavailable).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: str
    score: float
    snippet: str = ""


class ModelGmailIntentEvaluationResult(BaseModel):
    """Full result of evaluating a single Gmail intent signal.

    Produced by HandlerGmailIntentEvaluate after URL fetch, omnimemory lookup,
    LLM evaluation, and optional Slack delivery.

    Attributes:
        evaluation_id: sha256(message_id:selected_url:resolver_version) — stable idempotency key.
        verdict: LLM verdict: SURFACE (act now), WATCHLIST (future), SKIP (noise).
        reasoning: 2-3 sentence explanation from LLM.
        relevance_score: Float in [0.0, 1.0] from LLM.
        initial_plan: Bullet-point plan (non-None only when verdict=SURFACE).
        selected_url: URL actually fetched and evaluated (None if no suitable URL).
        url_candidates: All candidate URLs considered (Tier 1-3, up to 3).
        url_fetch_status: Status of URL content fetch attempt.
        memory_hits: Top omnimemory results for duplicate detection.
        llm_parse_status: Whether LLM response was parsed cleanly.
        slack_sent: True if Slack notification was successfully delivered.
        rate_limited: True if Slack suppressed due to rate limit (5/hour).
        errors: Non-fatal error messages accumulated during processing.
        pending_events: Downstream Kafka events to emit after handler completes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_id: str  # sha256(message_id:selected_url:resolver_version)
    verdict: Literal["SURFACE", "WATCHLIST", "SKIP"]
    reasoning: str
    relevance_score: float
    initial_plan: str | None  # Non-None only when verdict=SURFACE
    selected_url: str | None  # URL actually fetched and evaluated
    url_candidates: list[str]  # All candidate URLs considered
    url_fetch_status: Literal["OK", "FAILED", "SKIPPED"]
    memory_hits: list[ModelMemoryHit]  # Top omnimemory results with scores
    llm_parse_status: Literal["OK", "RECOVERED", "FAILED"]
    slack_sent: bool = False
    rate_limited: bool = False  # True if Slack suppressed by rate limit
    errors: list[str] = Field(default_factory=list)
    pending_events: list[JsonType] = Field(default_factory=list)
