# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Canonical Kafka topic registry for omniintelligence events.

Defines all omniintelligence output Kafka topics as a StrEnum. All topic names
follow ONEX canonical format: ``onex.{kind}.{producer}.{event-name}.v{n}``

This module is the single source of truth for omniintelligence topic names.
No hardcoded topic strings should appear in producer or consumer code; use
these enum values instead.

Note:
    The classified-intent topic (``onex.evt.omniintelligence.intent-classified.v1``)
    is produced directly by node_claude_hook_event_effect and lives in constants.py
    as ``TOPIC_SUFFIX_INTENT_CLASSIFIED_V1``. It is not part of this enum.

ONEX Compliance:
    - Topic names are immutable StrEnum values (no hardcoded strings elsewhere).
    - All `emitted_at` fields in envelope models must be injected by callers.
    - No datetime.now() defaults permitted.

Reference: OMN-2487, OMN-6808
"""

from __future__ import annotations

from enum import Enum, unique

from omnibase_core.utils.util_str_enum_base import StrValueHelper


@unique
class IntentTopic(StrValueHelper, str, Enum):
    """Canonical Kafka topic names for omniintelligence output events.

    All topics use ``onex.evt.omniintelligence.*`` as the producer namespace
    (producer: ``omniintelligence``, kind: ``evt``).
    """

    INTENT_DRIFT_DETECTED = "onex.evt.omniintelligence.intent-drift-detected.v1"
    """Execution diverged from declared intent."""

    INTENT_OUTCOME_LABELED = "onex.evt.omniintelligence.intent-outcome-labeled.v1"
    """Intent outcome labeled after completion."""

    INTENT_PATTERN_PROMOTED = "onex.evt.omniintelligence.intent-pattern-promoted.v1"
    """Intent pattern promoted to learned patterns."""

    LLM_CALL_COMPLETED = "onex.evt.omniintelligence.llm-call-completed.v1"
    """LLM call completed with token usage and latency telemetry (OMN-5184)."""

    ROUTING_FEEDBACK_PROCESSED = (
        "onex.evt.omniintelligence.routing-feedback-processed.v1"
    )
    """Routing feedback processed after upsert to routing_feedback_scores (OMN-2366)."""

    COMPLIANCE_EVALUATED = "onex.evt.omniintelligence.compliance-evaluated.v1"
    """Compliance evaluation completed for a source file (OMN-2339)."""

    RUN_EVALUATED = "onex.evt.omniintelligence.run-evaluated.v1"
    """Objective evaluation completed for an agent session (OMN-2578)."""

    EPISODE_BOUNDARY = "onex.evt.omniintelligence.episode-boundary.v1"
    """RL episode boundary (started/completed) event (OMN-5559)."""

    PLAN_REVIEW_STRATEGY_RUN_COMPLETED = (
        "onex.evt.omniintelligence.plan-review-strategy-run-completed.v1"
    )
    """Plan review strategy run completed (OMN-3282)."""

    PATTERN_LIFECYCLE_TRANSITIONED = (
        "onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1"
    )
    """Pattern lifecycle state change applied (OMN-1805)."""


__all__ = ["IntentTopic"]
