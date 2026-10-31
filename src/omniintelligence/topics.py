# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka topic registry: each value is read from the declaring node's contract (OMN-21677).

The episode boundary, the code-entity bridge dispatch topic and the intent-received
command keep their literal until a node contract declares them.
"""

from __future__ import annotations

from enum import Enum, unique

from omnibase_core.utils.util_str_enum_base import UtilStrValueHelper

from omniintelligence.models.topics import ModelContractTopicReader

_reader = ModelContractTopicReader()
_evt, _cmd = _reader.event, _reader.command
_review = ModelContractTopicReader(nodes_package="omniintelligence").event


@unique
class IntentTopic(UtilStrValueHelper, str, Enum):
    """Canonical Kafka topic names for omniintelligence output events (kind ``evt``)."""

    CLAUDE_CODE_REVIEW_COMPLETED = _evt(
        "node_claude_code_review_effect", "claude-code-review-completed"
    )
    """Claude Code review result, including named pool failures (OMN-20910)."""

    INTENT_DRIFT_DETECTED = _evt(
        "node_claude_hook_event_effect", "intent-drift-detected"
    )
    """Execution diverged from declared intent."""

    INTENT_OUTCOME_LABELED = _evt(
        "node_routing_feedback_effect", "intent-outcome-labeled"
    )
    """Intent outcome labeled after completion."""

    INTENT_PATTERN_PROMOTED = _evt(
        "node_pattern_projection_effect", "intent-pattern-promoted"
    )
    """Intent pattern promoted to learned patterns."""

    LLM_CALL_COMPLETED = _evt("node_claude_hook_event_effect", "llm-call-completed")
    """LLM call completed with token usage and latency telemetry (OMN-5184)."""

    ROUTING_FEEDBACK_PROCESSED = _evt(
        "node_routing_feedback_effect", "routing-feedback-processed"
    )
    """Routing feedback processed after upsert to routing_feedback_scores (OMN-2366)."""

    COMPLIANCE_EVALUATED = _evt(
        "node_compliance_evaluate_effect", "compliance-evaluated"
    )
    """Compliance evaluation completed for a source file (OMN-2339)."""

    RUN_EVALUATED = _evt("node_evidence_collection_effect", "run-evaluated")
    """Objective evaluation completed for an agent session (OMN-2578)."""

    EPISODE_BOUNDARY = "onex.evt.omniintelligence.episode-boundary.v1"
    """RL episode boundary (started/completed) event (OMN-5559)."""

    PLAN_REVIEW_STRATEGY_RUN_COMPLETED = _evt(
        "node_plan_reviewer_multi_compute", "plan-review-strategy-run-completed"
    )
    """Plan review strategy run completed (OMN-3282)."""

    PATTERN_LIFECYCLE_TRANSITIONED = _evt(
        "node_pattern_lifecycle_effect", "pattern-lifecycle-transitioned"
    )
    """Pattern lifecycle state change applied (OMN-1805)."""

    PATTERN_STORED = _evt("node_pattern_storage_effect", "pattern-stored")
    """Pattern persisted to storage (OMN-5611, OMN-8605)."""

    PATTERN_DISCOVERED = _evt("node_pattern_storage_effect", "discovered")
    """Pattern discovered from external producer (OMN-8605)."""

    FINDING_OBSERVED = _review("review_pairing", "finding-observed")
    """Review pairing finding observed (OMN-6592, OMN-8605)."""

    FIX_APPLIED = _review("review_pairing", "fix-applied")
    """Review pairing fix applied (OMN-6592, OMN-8605)."""

    FINDING_RESOLVED = _review("review_pairing", "finding-resolved")
    """Review pairing finding resolved (OMN-6592, OMN-8605)."""

    PAIR_CREATED = _review("review_pairing", "pair-created")
    """Review pairing pair created (OMN-6592, OMN-8605)."""

    CODE_ANALYSIS_COMPLETED = _evt(
        "node_intelligence_orchestrator", "code-analysis-completed"
    )
    """Code analysis completed event (OMN-8605)."""

    CODE_ANALYSIS_FAILED = _evt(
        "node_intelligence_orchestrator", "code-analysis-failed"
    )
    """Code analysis failed event (OMN-8605)."""

    CODE_ENTITIES_EXTRACTED_EMBED = _evt(
        "node_embedding_generation_effect", "code-entities-extracted-embed"
    )
    """Code entities extracted → embed+graph handler dispatch topic (OMN-8605)."""

    CODE_ENTITIES_EXTRACTED_BRIDGE = (
        "onex.evt.omniintelligence.code-entities-extracted-bridge.v1"
    )
    """Code entities extracted → bridge handler dispatch topic (OMN-8605)."""


@unique
class IntelligenceCommandTopic(UtilStrValueHelper, str, Enum):
    """Canonical Kafka topic names for omniintelligence input commands (kind ``cmd``)."""

    CLAUDE_CODE_REVIEW = _cmd("node_claude_code_review_effect", "claude-code-review")
    """Host account-pool Claude Code review command (OMN-20910)."""

    CLAUDE_HOOK_EVENT = _cmd("node_claude_hook_event_effect", "claude-hook-event")
    """Claude Code hook event command."""

    TOOL_CONTENT = _cmd("node_claude_hook_event_effect", "tool-content")
    """Tool content command."""

    PATTERN_LEARNING = _cmd("node_pattern_learning_effect", "pattern-learning")
    """Pattern learning command."""

    COMPLIANCE_EVALUATE = _cmd("node_compliance_evaluate_effect", "compliance-evaluate")
    """Compliance evaluate command (OMN-2339)."""

    INTENT_RECEIVED = "onex.cmd.omniintelligence.intent-received.v1"
    """Intelligence orchestrator intent reception (OMN-6590)."""

    DECISION_RECORDED = _cmd("node_llm_routing_decision_effect", "decision-recorded")
    """Decision recorded command (OMN-6595)."""

    BLOOM_EVAL_RUN = _cmd("node_bloom_eval_orchestrator", "bloom-eval-run")
    """Bloom eval orchestrator run command (OMN-6979)."""

    DOCUMENT_INGESTION = _cmd("node_intelligence_orchestrator", "document-ingestion")
    """Document ingestion orchestrator sub-command (OMN-6979)."""

    QUALITY_ASSESSMENT = _cmd("node_pattern_feedback_effect", "quality-assessment")
    """Quality assessment orchestrator sub-command (OMN-6979)."""

    CRAWL_TICK = _cmd("node_crawl_scheduler_effect", "crawl-tick")
    """Crawl scheduler tick command (cross-domain, produced for omnimemory)."""

    CODE_ANALYSIS = _cmd("node_intelligence_orchestrator", "code-analysis")
    """Code analysis compute command (OMN-8605)."""

    CRAWL_REQUESTED = _cmd("node_crawl_scheduler_effect", "crawl-requested")
    """Crawl requested command (cross-domain, consumed by omnimemory, OMN-8605)."""

    DOCUMENT_INDEXED = _evt("node_crawl_scheduler_effect", "document-indexed")
    """Document indexed event (cross-domain, produced by omnimemory, OMN-8605)."""


__all__ = ["IntentTopic", "IntelligenceCommandTopic"]
