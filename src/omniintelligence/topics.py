# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Canonical Kafka topic registry for omniintelligence events and commands.

Defines all omniintelligence Kafka topics as StrEnums. All topic names
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

Reference: OMN-2487, OMN-6808, OMN-8605
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

    PATTERN_LEARNED = "onex.evt.omniintelligence.pattern-learned.v1"
    """Pattern learning pipeline completed (OMN-8605)."""

    PATTERN_STORED = "onex.evt.omniintelligence.pattern-stored.v1"
    """Pattern persisted to storage (OMN-5611, OMN-8605)."""

    PATTERN_PROMOTED = "onex.evt.omniintelligence.pattern-promoted.v1"
    """Pattern promoted to validated status (OMN-2424, OMN-8605)."""

    DEBUG_TRIGGER_RECORD_CREATED = (
        "onex.evt.omniintelligence.debug-trigger-record-created.v1"
    )
    """Debug trigger record created (OMN-6597, OMN-8605)."""

    PATTERN_DISCOVERED = "onex.evt.pattern.discovered.v1"
    """Pattern discovered from external producer (OMN-8605)."""

    FINDING_OBSERVED = "onex.evt.review-pairing.finding-observed.v1"
    """Review pairing finding observed (OMN-6592, OMN-8605)."""

    FIX_APPLIED = "onex.evt.review-pairing.fix-applied.v1"
    """Review pairing fix applied (OMN-6592, OMN-8605)."""

    FINDING_RESOLVED = "onex.evt.review-pairing.finding-resolved.v1"
    """Review pairing finding resolved (OMN-6592, OMN-8605)."""

    PAIR_CREATED = "onex.evt.review-pairing.pair-created.v1"
    """Review pairing pair created (OMN-6592, OMN-8605)."""


@unique
class IntelligenceCommandTopic(StrValueHelper, str, Enum):
    """Canonical Kafka topic names for omniintelligence input commands.

    All topics use ``onex.cmd.omniintelligence.*`` or ``onex.cmd.*`` as the
    consumer namespace (kind: ``cmd``).
    """

    CLAUDE_HOOK_EVENT = "onex.cmd.omniintelligence.claude-hook-event.v1"
    """Claude Code hook event command."""

    SESSION_OUTCOME = "onex.cmd.omniintelligence.session-outcome.v1"
    """Session outcome command."""

    PATTERN_LIFECYCLE_TRANSITION = (
        "onex.cmd.omniintelligence.pattern-lifecycle-transition.v1"
    )
    """Pattern lifecycle transition command."""

    TOOL_CONTENT = "onex.cmd.omniintelligence.tool-content.v1"
    """Tool content command."""

    PATTERN_LEARNING = "onex.cmd.omniintelligence.pattern-learning.v1"
    """Pattern learning command."""

    COMPLIANCE_EVALUATE = "onex.cmd.omniintelligence.compliance-evaluate.v1"
    """Compliance evaluate command (OMN-2339)."""

    INTENT_RECEIVED = "onex.cmd.omniintelligence.intent-received.v1"
    """Intelligence orchestrator intent reception (OMN-6590)."""

    PATTERN_LIFECYCLE_PROCESS = "onex.cmd.omniintelligence.pattern-lifecycle-process.v1"
    """Intelligence reducer process handler (OMN-6594)."""

    CI_FAILURE_DETECTED = "onex.cmd.omniintelligence.ci-failure-detected.v1"
    """CI failure fingerprint compute (OMN-6598)."""

    CI_FAILURE_TRACK = "onex.cmd.omniintelligence.ci-failure-track.v1"
    """CI failure tracker effect (OMN-6598)."""

    CI_RECOVERY_DETECTED = "onex.cmd.omniintelligence.ci-recovery-detected.v1"
    """CI recovery handler (OMN-6598)."""

    DECISION_RECORDED = "onex.cmd.omniintelligence.decision-recorded.v1"
    """Decision recorded command (OMN-6595)."""

    CI_FAILURE_DETECTED_TRACK = (
        "onex.cmd.omniintelligence.ci-failure-detected-track.v1"
    )
    """CI failure detected tracking command (OMN-6597)."""

    BLOOM_EVAL_RUN = "onex.cmd.omniintelligence.bloom-eval-run.v1"
    """Bloom eval orchestrator run command (OMN-6979)."""

    DOCUMENT_INGESTION = "onex.cmd.omniintelligence.document-ingestion.v1"
    """Document ingestion orchestrator sub-command (OMN-6979)."""

    QUALITY_ASSESSMENT = "onex.cmd.omniintelligence.quality-assessment.v1"
    """Quality assessment orchestrator sub-command (OMN-6979)."""

    PROTOCOL_EXECUTE = "onex.cmd.omniintelligence.protocol-execute.v1"
    """Protocol execution command (OMN-6979)."""

    CRAWL_TICK = "onex.cmd.omnimemory.crawl-tick.v1"
    """Crawl scheduler tick command (cross-domain, produced for omnimemory)."""


__all__ = ["IntentTopic", "IntelligenceCommandTopic"]
