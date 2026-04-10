# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
Shared Constants for OmniIntelligence.

This module defines constants used across multiple modules to avoid magic numbers
and improve code readability and maintainability.

Usage:
    from omniintelligence.constants import PERCENTAGE_MULTIPLIER

    hit_rate = (hits / total) * PERCENTAGE_MULTIPLIER
"""

# =============================================================================
# Percentage and Rate Calculations
# =============================================================================

PERCENTAGE_MULTIPLIER: int = 100
"""
Multiplier for converting ratios (0.0-1.0) to percentages (0-100).

Used in rate calculations such as cache hit rates, pass rates, and
completion percentages. Multiply a ratio by this constant to get a
percentage value.

Example:
    ratio = 0.75
    percentage = ratio * PERCENTAGE_MULTIPLIER  # 75.0
"""

# =============================================================================
# Pattern Matching Limits
# =============================================================================

MAX_PATTERN_MATCH_RESULTS: int = 100
"""
Maximum number of pattern match results that can be returned.

This limit prevents excessive memory usage and response sizes when
querying for pattern matches. Pattern matching operations should not
return more than this many results.

Used in:
    - ModelPatternContext.max_results validation
    - Pattern matching compute node operations
"""

# =============================================================================
# Kafka Topic Constants (TEMP_BOOTSTRAP)
# =============================================================================
# TEMP_BOOTSTRAP: These constants are temporary until runtime injection from
# contract.yaml is wired end-to-end. Delete when OMN-1546 completes.
#
# Topic naming follows ONEX convention:
#   onex.{type}.{domain}.{event-name}.{version}
#
# The dispatch engine reads canonical topics from contract.yaml and uses them
# directly (no env prefix). These constants match the contract declarations.
#
# NOTE: The TOPIC_SUFFIX_ prefix is a legacy naming artifact. The dispatch engine
# uses these as canonical topics (no prefix).
# The names will be removed entirely with OMN-1546; renaming is not worthwhile.
# =============================================================================

TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1: str = (
    "onex.cmd.omniintelligence.claude-hook-event.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for Claude Code hook events (INPUT).

Canonical topic: onex.cmd.omniintelligence.claude-hook-event.v1

omniclaude publishes Claude Code hook events to this topic.
RuntimeHostProcess routes them to NodeClaudeHookEventEffect.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_INTENT_CLASSIFIED_V1: str = (
    "onex.evt.omniintelligence.intent-classified.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for intent classification events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.intent-classified.v1

NodeClaudeHookEventEffect publishes classified intents to this topic.
omnimemory consumes for graph storage.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_STORED_V1: str = "onex.evt.omniintelligence.pattern-stored.v1"
"""
TEMP_BOOTSTRAP: Canonical topic for pattern storage events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.pattern-stored.v1

NodePatternStorageEffect publishes when a pattern is stored in the database.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_PROMOTED_V1: str = "onex.evt.omniintelligence.pattern-promoted.v1"
"""
TEMP_BOOTSTRAP: Canonical topic for pattern promotion events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.pattern-promoted.v1

NodePatternPromotionEffect publishes when a pattern is promoted
from candidate to active status based on confidence thresholds
and validation criteria.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_DEPRECATED_V1: str = (
    "onex.evt.omniintelligence.pattern-deprecated.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for pattern deprecation events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.pattern-deprecated.v1

NodePatternDemotionEffect publishes when a validated pattern is deprecated,
e.g., due to rolling-window success metrics, failure streaks, or manual disable,
subject to cooldown/threshold gates.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_TOOL_CONTENT_V1: str = "onex.cmd.omniintelligence.tool-content.v1"
"""
TEMP_BOOTSTRAP: Canonical topic for tool content events (INPUT).

Canonical topic: onex.cmd.omniintelligence.tool-content.v1

omniclaude publishes PostToolUse payloads with file contents and command
outputs to this topic. The claude hook event effect node consumes them
for intelligence analysis.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1: str = (
    "onex.cmd.omniintelligence.pattern-learning.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for pattern learning commands (INPUT).

Canonical topic: onex.cmd.omniintelligence.pattern-learning.v1

NodeClaudeHookEventEffect publishes this command when a session stops,
triggering pattern extraction in the intelligence orchestrator.

Reference: OMN-2210
Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_PROJECTION_V1: str = (
    "onex.evt.omniintelligence.pattern-projection.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for pattern projection snapshot events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.pattern-projection.v1

NodePatternProjectionEffect publishes a full materialized snapshot of all
validated patterns to this topic whenever a lifecycle change occurs
(pattern-promoted, pattern-lifecycle-transitioned).
Consumers (e.g. omniclaude) subscribe to receive the latest projection without
needing direct DB access.

Deletion ticket: OMN-1546
"""

TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1: str = (
    "onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for pattern lifecycle transition events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1

NodePatternLifecycleEffect publishes when a pattern status transition is applied,
providing the single source of truth for pattern status changes with full audit trail.

This is the unified lifecycle event that replaces individual promotion/demotion events
for comprehensive lifecycle tracking.

Reference: OMN-1805
Deletion ticket: OMN-1546
"""

TOPIC_PATTERN_LIFECYCLE_CMD_V1: str = (
    "onex.cmd.omniintelligence.pattern-lifecycle-transition.v1"
)
"""Canonical topic for pattern lifecycle transition commands (INPUT to reducer).

NodePatternPromotionEffect and NodePatternDemotionEffect publish lifecycle events
to this topic. The reducer consumes them, validates the transition against the
contract.yaml FSM, and the effect node applies the actual database update.

Reference: OMN-1805
"""

TOPIC_ROUTING_FEEDBACK_PROCESSED: str = (
    "onex.evt.omniintelligence.routing-feedback-processed.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for routing feedback processed events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.routing-feedback-processed.v1

NodeRoutingFeedbackEffect publishes after a successful upsert to
routing_feedback_scores. Consumers can use this to confirm that a routing
feedback event was fully processed.

This constant uses the canonical ONEX format (no env prefix) per OMN-2876.
Both the contract.yaml publish_topics and this Python constant use bare
canonical onex.* names — no {env}. prefix.

Reference: OMN-2366
Deletion ticket: OMN-1546
"""

TOPIC_LLM_ROUTING_DECISION_PROCESSED: str = (
    "onex.evt.omniintelligence.llm-routing-decision-processed.v1"
)
"""
TEMP_BOOTSTRAP: Canonical topic for LLM routing decision processed events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.llm-routing-decision-processed.v1

NodeLlmRoutingDecisionEffect publishes after a successful upsert to
llm_routing_decisions. Consumers can use this to confirm that a Bifrost
LLM routing decision event was fully processed for model performance analytics.

This constant uses the canonical ONEX format (no env prefix) per OMN-2876.
Both the contract.yaml publish_topics and this Python constant use bare
canonical onex.* names — no {env}. prefix.

Reference: OMN-2939
Deletion ticket: OMN-1546
"""

# NOTE: The pattern.discovered topic string lives exclusively in
# node_pattern_storage_effect/contract.yaml (subscribe_topics).
# No Python constant is needed because RuntimeHostProcess reads
# the topic from the contract at startup.  Removed in OMN-2059 review.

TOPIC_RUN_EVALUATED_V1: str = "onex.evt.omniintelligence.run-evaluated.v1"
"""
TEMP_BOOTSTRAP: Canonical topic for objective evaluation result events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.run-evaluated.v1

NodeEvidenceCollectionEffect publishes a RunEvaluatedEvent after each agent
session is evaluated against an ObjectiveSpec. Consumers:
  - NodePolicyStateReducer (OMN-2557): Updates policy state.
  - omnidash: Displays objective scores in analytics dashboard.
  - omniintelligence audit: Stores full evaluation for replay verification.

Reference: OMN-2578
Deletion ticket: OMN-1546
"""

# Mirror of contract.yaml publish_topics — canonical source is contract.yaml
TOPIC_PLAN_REVIEW_STRATEGY_RUN_COMPLETED_V1: str = (
    "onex.evt.omniintelligence.plan-review-strategy-run-completed.v1"
)
"""Emitted once per strategy run from node_plan_reviewer_multi_compute.
Canonical declaration: nodes/node_plan_reviewer_multi_compute/contract.yaml
Reference: OMN-3282
"""

# Mirror of contract.yaml topics — canonical source is contract.yaml
TOPIC_BLOOM_EVAL_RUN_V1: str = "onex.cmd.omniintelligence.bloom-eval-run.v1"
"""Command topic to trigger a bloom eval suite run.
Canonical declaration: nodes/node_bloom_eval_orchestrator/contract.yaml
Reference: OMN-4028
"""

TOPIC_BLOOM_EVAL_COMPLETED_V1: str = "onex.evt.omniintelligence.bloom-eval-completed.v1"
"""Event topic emitted after each bloom eval suite run with aggregated results.
Canonical declaration: nodes/node_bloom_eval_orchestrator/contract.yaml
Reference: OMN-4028
"""

TOPIC_DECISION_RECORDED_EVT_V1: str = "onex.evt.omniintelligence.decision-recorded.v1"
"""Canonical topic for DecisionRecord summary events (OUTPUT, broad access).

Privacy-safe summary: decision_id, type, selected, count, has_rationale.
No agent_rationale or reproducibility_snapshot.

Reference: OMN-2466
Deletion ticket: OMN-1546
"""

TOPIC_DECISION_RECORDED_CMD_V1: str = "onex.cmd.omniintelligence.decision-recorded.v1"
"""Canonical topic for full DecisionRecord events (INPUT/CMD, restricted access).

Full payload including agent_rationale and reproducibility_snapshot.
Consumed by decision_store and mismatch_detector.

Reference: OMN-2466, OMN-2467
Deletion ticket: OMN-1546
"""

TOPIC_RATIONALE_MISMATCH_EVT_V1: str = "onex.evt.omniintelligence.rationale-mismatch.v1"
"""Canonical topic for rationale mismatch events (OUTPUT, broad access).

Mismatch event payload: decision_id, mismatch_type, severity, timestamp.
No rationale text in this topic.

Reference: OMN-2472
Deletion ticket: OMN-1546
"""

TOPIC_COMPLIANCE_EVALUATED_V1: str = "onex.evt.omniintelligence.compliance-evaluated.v1"
"""
TEMP_BOOTSTRAP: Canonical topic for compliance evaluated events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.compliance-evaluated.v1

NodeComplianceEvaluateEffect publishes after a compliance evaluation completes
for a source file against applicable patterns.

Reference: OMN-2339, OMN-6808
Deletion ticket: OMN-1546
"""

TOPIC_EPISODE_BOUNDARY_V1: str = "onex.evt.omniintelligence.episode-boundary.v1"
"""
TEMP_BOOTSTRAP: Canonical topic for RL episode boundary events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.episode-boundary.v1

EpisodeEmitter publishes episode_started and episode_completed events
for the Learned Decision Optimization Platform.

Reference: OMN-5559, OMN-6808
Deletion ticket: OMN-1546
"""

TOPIC_UTILIZATION_SCORING_CMD_V1: str = (
    "onex.cmd.omniintelligence.utilization-scoring.v1"
)
"""Canonical topic for utilization scoring commands (INPUT).

Emitted by omniclaude Stop hook when patterns were injected during a session.
Consumed by the utilization scoring dispatch handler which calls a local LLM
to score pattern utilization.

Reference: OMN-5507
"""

TOPIC_CONTEXT_UTILIZATION_EVT_V1: str = "onex.evt.omniclaude.context-utilization.v1"
"""Canonical topic for context utilization events (OUTPUT cross-domain).

Emitted by the utilization scoring handler after LLM-based scoring.
Consumed by omnidash for the Context Effectiveness dashboard.

Reference: OMN-5506
"""

TOPIC_PROMOTION_CHECK_CMD_V1: str = (
    "onex.cmd.omniintelligence.promotion-check-requested.v1"
)
"""Canonical topic for periodic promotion-check commands (INPUT).

Emitted by the promotion scheduler and bootstrap sweep script. Consumed by the
promotion-check dispatch handler which triggers the auto-promote handler for all
candidate and provisional patterns.

Reference: OMN-5498, OMN-5499, OMN-5502
"""

# =============================================================================
# Code Extraction Pipeline Topics (OMN-5662)
# =============================================================================

TOPIC_CODE_CRAWL_REQUESTED_V1: str = "onex.cmd.omniintelligence.code-crawl-requested.v1"
"""Canonical topic for code crawl request commands (INPUT).

Triggers the code crawler to scan configured repositories for Python files
and emit code-file-discovered.v1 per file found.

Reference: OMN-5662, OMN-5657 (epic)
"""

TOPIC_CODE_FILE_DISCOVERED_V1: str = "onex.evt.omniintelligence.code-file-discovered.v1"
"""Canonical topic for code file discovery events (OUTPUT/INPUT).

Emitted by the code crawl handler for each Python file found. Consumed by the
code extract handler which runs AST extraction and relationship detection.

Reference: OMN-5662, OMN-5658
"""

TOPIC_CODE_ENTITIES_EXTRACTED_V1: str = (
    "onex.evt.omniintelligence.code-entities-extracted.v1"
)
"""Canonical topic for code entities extracted events (OUTPUT/INPUT).

Emitted by the code extract handler after AST parsing. Consumed by the code
persist handler which upserts entities/relationships to Postgres.

Reference: OMN-5662, OMN-5659
"""

TOPIC_CODE_ENTITIES_PERSISTED_V1: str = (
    "onex.evt.omniintelligence.code-entities-persisted.v1"
)
"""Canonical topic for code entities persisted events (OUTPUT/INPUT).

Emitted by the code persist handler after successful upsert to Postgres.
Consumed by Part 2 enrichment handlers (classification, quality scoring).

Reference: OMN-5677
"""

TOPIC_CODE_ENTITY_PATTERNS_DERIVED_V1: str = (
    "onex.evt.omniintelligence.code-entity-patterns-derived.v1"
)
"""Canonical topic for code entity patterns derived events (OUTPUT).

Emitted by the code entity bridge handler after deriving learned_patterns
from code_entities. Consumed by downstream pattern storage pipeline.

Reference: OMN-7863
"""

TOPIC_CODE_ENTITIES_CLASSIFIED_V1: str = (
    "onex.evt.omniintelligence.code-entities-classified.v1"
)
"""Canonical topic for code entities classified events (OUTPUT).

Emitted by the deterministic classification handler after classifying entities.

Reference: OMN-5674
"""

TOPIC_CODE_ENTITIES_SCORED_V1: str = "onex.evt.omniintelligence.code-entities-scored.v1"
"""Canonical topic for code entities scored events (OUTPUT).

Emitted by the quality scoring handler after scoring entities.

Reference: OMN-5675
"""

# =============================================================================
# Operation Lifecycle Topics (OMN-6125)
# =============================================================================

TOPIC_OPERATION_STARTED_V1: str = "onex.evt.omniintelligence.operation-started.v1"
"""Canonical topic for intelligence operation started events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.operation-started.v1

Emitted at the start of each intelligence operation dispatch (claude-hook,
pattern-lifecycle, pattern-storage, etc.) for omnidash /intelligence page.

Reference: OMN-6125
Deletion ticket: OMN-1546
"""

TOPIC_OPERATION_COMPLETED_V1: str = "onex.evt.omniintelligence.operation-completed.v1"
"""Canonical topic for intelligence operation completed events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.operation-completed.v1

Emitted at the end of each intelligence operation dispatch with status
and duration_ms for omnidash /intelligence page.

Reference: OMN-6125
Deletion ticket: OMN-1546
"""

# =============================================================================
# RL Routing Decision Topics (OMN-6126)
# =============================================================================

TOPIC_RL_ROUTING_DECISION_V1: str = "onex.evt.omniintelligence.rl-routing-decision.v1"
"""Canonical topic for RL routing decision events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.rl-routing-decision.v1

Emitted when the RL routing system makes a shadow-mode routing decision,
allowing comparison between RL-recommended and actual agent selection.

Reference: OMN-6126
Deletion ticket: OMN-1546
"""

# =============================================================================
# CI Debug Escalation Topics (OMN-6123)
# =============================================================================

TOPIC_CI_DEBUG_ESCALATION_V1: str = "onex.evt.omniintelligence.ci-debug-escalation.v1"
"""Canonical topic for CI debug escalation events (OUTPUT).

Canonical topic: onex.evt.omniintelligence.ci-debug-escalation.v1

Emitted when consecutive CI failures cross the escalation threshold,
triggering debug intelligence analysis for omnidash /ci-intelligence page.

Reference: OMN-6123
Deletion ticket: OMN-1546
"""

TOPIC_QUALITY_ASSESSMENT_CMD_V1: str = "onex.cmd.omniintelligence.quality-assessment.v1"
"""Canonical topic for quality-assessment commands (INPUT).

Consumed by NodeIntelligenceOrchestrator to trigger quality scoring.
NodePatternFeedbackEffect publishes one command per updated pattern after
effectiveness scoring, routing patterns through the quality assessment FSM.

Reference: OMN-8144
"""

TOPIC_OMNICLAUDE_ROUTING_FEEDBACK_V1: str = "onex.evt.omniclaude.routing-feedback.v1"
"""Canonical subscribe topic for routing feedback events from omniclaude (INPUT, cross-repo).

Published by omniclaude hooks (omniclaude.hooks.event_registry, TopicBase.ROUTING_FEEDBACK).
This is a cross-system exception: the topic uses 'evt' kind because it is produced by omniclaude.
OMN-2622: Carries both produced and skipped outcomes via feedback_status field.

Reference: OMN-2622, OMN-2366
"""

TOPIC_LEGACY_ROUTING_FEEDBACK_BARE: str = "routing.feedback"
"""DEPRECATED (OMN-2366): Legacy bare topic name for routing feedback.

Predates the canonical onex.evt.omniclaude.routing-feedback.v1 naming convention
(OMN-2622). No active producers detected as of 2026-04-09.

Subscribed in node_routing_feedback_effect contract.yaml for drain purposes only.
Remove this constant after the topic is confirmed empty and purged from Redpanda.
"""

# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MAX_PATTERN_MATCH_RESULTS",
    "PERCENTAGE_MULTIPLIER",
    "TOPIC_BLOOM_EVAL_COMPLETED_V1",
    "TOPIC_BLOOM_EVAL_RUN_V1",
    "TOPIC_CI_DEBUG_ESCALATION_V1",
    "TOPIC_COMPLIANCE_EVALUATED_V1",
    "TOPIC_CODE_CRAWL_REQUESTED_V1",
    "TOPIC_CODE_ENTITIES_CLASSIFIED_V1",
    "TOPIC_CODE_ENTITIES_EXTRACTED_V1",
    "TOPIC_CODE_ENTITIES_PERSISTED_V1",
    "TOPIC_CODE_ENTITIES_SCORED_V1",
    "TOPIC_CODE_ENTITY_PATTERNS_DERIVED_V1",
    "TOPIC_CODE_FILE_DISCOVERED_V1",
    "TOPIC_CONTEXT_UTILIZATION_EVT_V1",
    "TOPIC_DECISION_RECORDED_CMD_V1",
    "TOPIC_DECISION_RECORDED_EVT_V1",
    "TOPIC_EPISODE_BOUNDARY_V1",
    "TOPIC_LLM_ROUTING_DECISION_PROCESSED",
    "TOPIC_OPERATION_COMPLETED_V1",
    "TOPIC_OPERATION_STARTED_V1",
    "TOPIC_PATTERN_LIFECYCLE_CMD_V1",
    "TOPIC_PLAN_REVIEW_STRATEGY_RUN_COMPLETED_V1",
    "TOPIC_PROMOTION_CHECK_CMD_V1",
    "TOPIC_LEGACY_ROUTING_FEEDBACK_BARE",
    "TOPIC_OMNICLAUDE_ROUTING_FEEDBACK_V1",
    "TOPIC_QUALITY_ASSESSMENT_CMD_V1",
    "TOPIC_RATIONALE_MISMATCH_EVT_V1",
    "TOPIC_RL_ROUTING_DECISION_V1",
    "TOPIC_ROUTING_FEEDBACK_PROCESSED",
    "TOPIC_RUN_EVALUATED_V1",
    "TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1",
    "TOPIC_SUFFIX_INTENT_CLASSIFIED_V1",
    "TOPIC_SUFFIX_PATTERN_DEPRECATED_V1",
    "TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1",
    "TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1",
    "TOPIC_SUFFIX_PATTERN_PROJECTION_V1",
    "TOPIC_SUFFIX_PATTERN_PROMOTED_V1",
    "TOPIC_SUFFIX_PATTERN_STORED_V1",
    "TOPIC_SUFFIX_TOOL_CONTENT_V1",
    "TOPIC_UTILIZATION_SCORING_CMD_V1",
]
