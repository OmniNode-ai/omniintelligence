# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for contract-driven topic discovery.

Validates:
    - collect_subscribe_topics_from_contracts returns exactly 12 topics
    - Discovered topics match the contract.yaml declarations
    - canonical_topic_to_dispatch_alias converts correctly
    - INTELLIGENCE_SUBSCRIBE_TOPICS in plugin.py is contract-driven

Related:
    - OMN-2033: Move intelligence topics to contract.yaml declarations
    - OMN-2424: NodePatternProjectionEffect adds 2 projection subscribe topics
    - OMN-2430: NodeWatchdogEffect has subscribe_topics: [] — it is OS-event driven and emits but never subscribes
"""

from __future__ import annotations

import pytest

from omniintelligence.runtime.contract_topics import (
    canonical_topic_to_dispatch_alias,
    collect_publish_topics_for_dispatch,
    collect_subscribe_topics_from_contracts,
)

# =============================================================================
# Expected topics (must match contract.yaml declarations)
# =============================================================================

EXPECTED_CLAUDE_HOOK = "onex.cmd.omniintelligence.claude-hook-event.v1"
EXPECTED_TOOL_CONTENT = "onex.cmd.omniintelligence.tool-content.v1"
EXPECTED_SESSION_OUTCOME = "onex.cmd.omniintelligence.session-outcome.v1"
EXPECTED_PATTERN_LEARNING = "onex.cmd.omniintelligence.pattern-learning.v1"
EXPECTED_PATTERN_LIFECYCLE = "onex.cmd.omniintelligence.pattern-lifecycle-transition.v1"
EXPECTED_PATTERN_LEARNED = "onex.evt.omniintelligence.pattern-learned.v1"
EXPECTED_PATTERN_DISCOVERED = "onex.evt.pattern.discovered.v1"

EXPECTED_COMPLIANCE_EVALUATE = "onex.cmd.omniintelligence.compliance-evaluate.v1"

EXPECTED_PATTERN_PROMOTED = "onex.evt.omniintelligence.pattern-promoted.v1"
EXPECTED_PATTERN_LIFECYCLE_TRANSITIONED = (
    "onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1"
)

# OMN-2430: NodeWatchdogEffect has subscribe_topics: [] — OS-event driven, emits but never subscribes
# OMN-2719: crawl-requested.v1 producer is node_watchdog_effect (omniintelligence) — no external
# omnimemory producer is needed; the trigger chain is internal to omniintelligence.
EXPECTED_CRAWL_REQUESTED = "onex.cmd.omnimemory.crawl-requested.v1"
EXPECTED_DOCUMENT_INDEXED = "onex.evt.omnimemory.document-indexed.v1"

EXPECTED_BLOOM_EVAL_RUN = "onex.cmd.omniintelligence.bloom-eval-run.v1"
EXPECTED_INTENT_PATTERN_PROMOTED = (
    "onex.evt.omniintelligence.intent-pattern-promoted.v1"
)
# OMN-5611: pattern-stored events trigger projection snapshots
EXPECTED_PATTERN_STORED = "onex.evt.omniintelligence.pattern-stored.v1"

# OMN-6391: code_crawler_effect subscribe topic
EXPECTED_CODE_CRAWL_REQUESTED = "onex.cmd.omniintelligence.code-crawl-requested.v1"

# OMN-6593: review_pairing subscribe topics
EXPECTED_FINDING_OBSERVED = "onex.evt.review-pairing.finding-observed.v1"
EXPECTED_FIX_APPLIED = "onex.evt.review-pairing.fix-applied.v1"

# OMN-6597: ci_failure_tracker_effect subscribe topics
EXPECTED_CI_FAILURE_DETECTED = "onex.cmd.omniintelligence.ci-failure-detected.v1"
EXPECTED_CI_FAILURE_DETECTED_TRACK = (
    "onex.cmd.omniintelligence.ci-failure-detected-track.v1"
)
EXPECTED_CI_FAILURE_TRACK = "onex.cmd.omniintelligence.ci-failure-track.v1"
EXPECTED_CI_RECOVERY_DETECTED = "onex.cmd.omniintelligence.ci-recovery-detected.v1"

EXPECTED_CODE_ANALYSIS = "onex.cmd.omniintelligence.code-analysis.v1"

# OMN-6979: newly contract-declared topics
EXPECTED_DECISION_RECORDED = "onex.cmd.omniintelligence.decision-recorded.v1"
EXPECTED_INTENT_RECEIVED = "onex.cmd.omniintelligence.intent-received.v1"
EXPECTED_PATTERN_LIFECYCLE_PROCESS = (
    "onex.cmd.omniintelligence.pattern-lifecycle-process.v1"
)
EXPECTED_UTILIZATION_SCORING = "onex.cmd.omniintelligence.utilization-scoring.v1"
EXPECTED_CODE_ENTITIES_EXTRACTED_EMBED = (
    "onex.evt.omniintelligence.code-entities-extracted-embed.v1"
)

# Topics discovered from nodes added after the original 20-topic baseline
EXPECTED_DOCUMENT_INGESTION = "onex.cmd.omniintelligence.document-ingestion.v1"
EXPECTED_QUALITY_ASSESSMENT = "onex.cmd.omniintelligence.quality-assessment.v1"
EXPECTED_PROMOTION_CHECK = "onex.cmd.omniintelligence.promotion-check-requested.v1"
EXPECTED_PROTOCOL_EXECUTE = "onex.cmd.omniintelligence.protocol-execute.v1"
EXPECTED_CRAWL_TICK = "onex.cmd.omnimemory.crawl-tick.v1"
EXPECTED_LLM_ROUTING_DECISION = "onex.evt.omniclaude.llm-routing-decision.v1"
EXPECTED_PATTERN_ENFORCEMENT = "onex.evt.omniclaude.pattern-enforcement.v1"
EXPECTED_ROUTING_FEEDBACK = "onex.evt.omniclaude.routing-feedback.v1"
EXPECTED_ENTITY_EXTRACTION_COMPLETED = (
    "onex.evt.omniintelligence.entity-extraction-completed.v1"
)
EXPECTED_INTENT_DRIFT_DETECTED = "onex.evt.omniintelligence.intent-drift-detected.v1"
EXPECTED_INTENT_OUTCOME_LABELED = "onex.evt.omniintelligence.intent-outcome-labeled.v1"
EXPECTED_PATTERN_MATCHED = "onex.evt.omniintelligence.pattern-matched.v1"
EXPECTED_VECTORIZATION_COMPLETED = (
    "onex.evt.omniintelligence.vectorization-completed.v1"
)
EXPECTED_DOCUMENT_CHANGED = "onex.evt.omnimemory.document-changed.v1"
EXPECTED_DOCUMENT_DISCOVERED = "onex.evt.omnimemory.document-discovered.v1"

# OMN-7652: node_ast_extraction_compute subscribe topic now active
EXPECTED_CODE_FILE_DISCOVERED = "onex.evt.omniintelligence.code-file-discovered.v1"

EXPECTED_TOPICS = {
    EXPECTED_CLAUDE_HOOK,
    EXPECTED_TOOL_CONTENT,
    EXPECTED_SESSION_OUTCOME,
    EXPECTED_PATTERN_LEARNING,
    EXPECTED_PATTERN_LIFECYCLE,
    EXPECTED_PATTERN_LEARNED,
    EXPECTED_PATTERN_DISCOVERED,
    EXPECTED_COMPLIANCE_EVALUATE,
    EXPECTED_PATTERN_PROMOTED,
    EXPECTED_PATTERN_LIFECYCLE_TRANSITIONED,
    EXPECTED_CRAWL_REQUESTED,
    EXPECTED_DOCUMENT_INDEXED,
    EXPECTED_BLOOM_EVAL_RUN,
    EXPECTED_INTENT_PATTERN_PROMOTED,
    EXPECTED_PATTERN_STORED,
    EXPECTED_CODE_CRAWL_REQUESTED,
    EXPECTED_FINDING_OBSERVED,
    EXPECTED_FIX_APPLIED,
    EXPECTED_CI_FAILURE_DETECTED,
    EXPECTED_CODE_ANALYSIS,
    # OMN-6597: additional ci_failure_tracker topics
    EXPECTED_CI_FAILURE_DETECTED_TRACK,
    EXPECTED_CI_FAILURE_TRACK,
    EXPECTED_CI_RECOVERY_DETECTED,
    # OMN-6979: orphan dispatch routes now contract-declared
    EXPECTED_DECISION_RECORDED,
    EXPECTED_INTENT_RECEIVED,
    EXPECTED_PATTERN_LIFECYCLE_PROCESS,
    EXPECTED_UTILIZATION_SCORING,
    EXPECTED_CODE_ENTITIES_EXTRACTED_EMBED,
    # Topics from nodes added after original baseline
    EXPECTED_DOCUMENT_INGESTION,
    EXPECTED_QUALITY_ASSESSMENT,
    EXPECTED_PROMOTION_CHECK,
    EXPECTED_PROTOCOL_EXECUTE,
    EXPECTED_CRAWL_TICK,
    EXPECTED_LLM_ROUTING_DECISION,
    EXPECTED_PATTERN_ENFORCEMENT,
    EXPECTED_ROUTING_FEEDBACK,
    EXPECTED_ENTITY_EXTRACTION_COMPLETED,
    EXPECTED_INTENT_DRIFT_DETECTED,
    EXPECTED_INTENT_OUTCOME_LABELED,
    EXPECTED_PATTERN_MATCHED,
    EXPECTED_VECTORIZATION_COMPLETED,
    EXPECTED_DOCUMENT_CHANGED,
    EXPECTED_DOCUMENT_DISCOVERED,
    EXPECTED_CODE_FILE_DISCOVERED,
}


# =============================================================================
# Tests: collect_subscribe_topics_from_contracts
# =============================================================================


class TestCollectSubscribeTopics:
    """Validate contract-driven topic collection."""

    def test_returns_expected_topic_count(self) -> None:
        """All intelligence effect nodes declare expected subscribe topics total."""
        topics = collect_subscribe_topics_from_contracts()
        unique = set(topics)
        assert unique == EXPECTED_TOPICS, (
            f"Expected {len(EXPECTED_TOPICS)} unique topics, got {len(unique)}.\n"
            f"Extra: {unique - EXPECTED_TOPICS}\n"
            f"Missing: {EXPECTED_TOPICS - unique}"
        )

    def test_contains_claude_hook_event_topic(self) -> None:
        """Claude hook event topic must be discovered from contract."""
        topics = collect_subscribe_topics_from_contracts()
        assert EXPECTED_CLAUDE_HOOK in topics

    def test_contains_session_outcome_topic(self) -> None:
        """Session outcome topic must be discovered from contract."""
        topics = collect_subscribe_topics_from_contracts()
        assert EXPECTED_SESSION_OUTCOME in topics

    def test_contains_pattern_learning_topic(self) -> None:
        """Pattern learning topic must be discovered from contract."""
        topics = collect_subscribe_topics_from_contracts()
        assert EXPECTED_PATTERN_LEARNING in topics

    def test_contains_pattern_lifecycle_topic(self) -> None:
        """Pattern lifecycle topic must be discovered from contract."""
        topics = collect_subscribe_topics_from_contracts()
        assert EXPECTED_PATTERN_LIFECYCLE in topics

    def test_contains_pattern_learned_topic(self) -> None:
        """Pattern learned topic must be discovered from storage effect contract."""
        topics = collect_subscribe_topics_from_contracts()
        assert EXPECTED_PATTERN_LEARNED in topics

    def test_contains_pattern_discovered_topic(self) -> None:
        """Pattern discovered topic must be discovered from storage effect contract."""
        topics = collect_subscribe_topics_from_contracts()
        assert EXPECTED_PATTERN_DISCOVERED in topics

    def test_contains_tool_content_topic(self) -> None:
        """Tool content topic must be discovered from claude hook event contract."""
        topics = collect_subscribe_topics_from_contracts()
        assert EXPECTED_TOOL_CONTENT in topics

    def test_all_expected_topics_present(self) -> None:
        """All 12 expected topics must be in the discovered set (OMN-2430: NodeWatchdogEffect adds 0 subscribe topics)."""
        topics = set(collect_subscribe_topics_from_contracts())
        assert topics == EXPECTED_TOPICS

    def test_returns_list_type(self) -> None:
        """Return type must be a list for ordered iteration."""
        topics = collect_subscribe_topics_from_contracts()
        assert isinstance(topics, list)

    def test_no_unexpected_duplicates(self) -> None:
        """Only known cross-node duplicates are allowed."""
        topics = collect_subscribe_topics_from_contracts()
        # Known duplicates: topics declared in multiple contracts or in
        # both a contract and _ADDITIONAL_SUBSCRIBE_TOPICS
        known_duplicates = {
            "onex.cmd.omniintelligence.code-analysis.v1",
            "onex.cmd.omniintelligence.pattern-learning.v1",
            "onex.cmd.omnimemory.crawl-tick.v1",
        }
        seen: set[str] = set()
        unexpected: list[str] = []
        for t in topics:
            if t in seen and t not in known_duplicates:
                unexpected.append(t)
            seen.add(t)
        assert not unexpected, f"Unexpected duplicate topics: {unexpected}"


# =============================================================================
# Tests: INTELLIGENCE_SUBSCRIBE_TOPICS is contract-driven
# =============================================================================


class TestPluginTopicListIsContractDriven:
    """Validate that plugin.py's topic list matches contract discovery."""

    def test_plugin_topics_match_contract_discovery(self) -> None:
        """INTELLIGENCE_SUBSCRIBE_TOPICS must equal contract-discovered topics."""
        from omniintelligence.runtime.plugin import INTELLIGENCE_SUBSCRIBE_TOPICS

        contract_topics = collect_subscribe_topics_from_contracts()
        assert set(INTELLIGENCE_SUBSCRIBE_TOPICS) == set(contract_topics)

    def test_plugin_topics_length_matches(self) -> None:
        """INTELLIGENCE_SUBSCRIBE_TOPICS length must match contract count."""
        from omniintelligence.runtime.plugin import INTELLIGENCE_SUBSCRIBE_TOPICS

        contract_topics = collect_subscribe_topics_from_contracts()
        assert len(INTELLIGENCE_SUBSCRIBE_TOPICS) == len(contract_topics)


# =============================================================================
# Tests: collect_publish_topics_for_dispatch
# =============================================================================


class TestCollectPublishTopicsForDispatch:
    """Validate contract-driven publish topic collection for dispatch engine."""

    def test_returns_dict(self) -> None:
        """Return type must be a dict."""
        result = collect_publish_topics_for_dispatch()
        assert isinstance(result, dict)

    def test_contains_claude_hook_key(self) -> None:
        """Must contain 'claude_hook' key for intent classification events."""
        result = collect_publish_topics_for_dispatch()
        assert "claude_hook" in result

    def test_contains_lifecycle_key(self) -> None:
        """Must contain 'lifecycle' key for transition events."""
        result = collect_publish_topics_for_dispatch()
        assert "lifecycle" in result

    def test_contains_pattern_learning_key(self) -> None:
        """Must contain 'pattern_learning' key for learning events."""
        result = collect_publish_topics_for_dispatch()
        assert "pattern_learning" in result

    def test_contains_pattern_storage_key(self) -> None:
        """Must contain 'pattern_storage' key for storage events."""
        result = collect_publish_topics_for_dispatch()
        assert "pattern_storage" in result

    def test_claude_hook_topic_is_evt(self) -> None:
        """Claude hook publish topic must be an .evt. topic."""
        result = collect_publish_topics_for_dispatch()
        assert ".evt." in result["claude_hook"]

    def test_lifecycle_topic_is_evt(self) -> None:
        """Lifecycle publish topic must be an .evt. topic."""
        result = collect_publish_topics_for_dispatch()
        assert ".evt." in result["lifecycle"]

    def test_pattern_storage_topic_is_evt(self) -> None:
        """Pattern storage publish topic must be an .evt. topic."""
        result = collect_publish_topics_for_dispatch()
        assert ".evt." in result["pattern_storage"]

    def test_contains_code_entities_extracted_key(self) -> None:
        """Must contain 'code_entities_extracted' key for AST extraction events (OMN-7652)."""
        result = collect_publish_topics_for_dispatch()
        assert "code_entities_extracted" in result

    def test_code_entities_extracted_topic_is_evt(self) -> None:
        """AST extraction publish topic must be an .evt. topic (OMN-7652)."""
        result = collect_publish_topics_for_dispatch()
        assert ".evt." in result["code_entities_extracted"]

    def test_all_values_are_strings(self) -> None:
        """All publish topic values must be strings."""
        result = collect_publish_topics_for_dispatch()
        for key, value in result.items():
            assert isinstance(value, str), f"Value for '{key}' is not a string: {value}"


# =============================================================================
# Tests: canonical_topic_to_dispatch_alias
# =============================================================================


class TestCanonicalTopicToDispatchAlias:
    """Validate canonical-to-dispatch topic conversion."""

    def test_converts_cmd_to_commands(self) -> None:
        """`.cmd.` should be converted to `.commands.`."""
        result = canonical_topic_to_dispatch_alias(
            "onex.cmd.omniintelligence.claude-hook-event.v1"
        )
        assert result == "onex.commands.omniintelligence.claude-hook-event.v1"

    def test_converts_evt_to_events(self) -> None:
        """`.evt.` should be converted to `.events.`."""
        result = canonical_topic_to_dispatch_alias(
            "onex.evt.omniintelligence.intent-classified.v1"
        )
        assert result == "onex.events.omniintelligence.intent-classified.v1"

    def test_session_outcome_conversion(self) -> None:
        """Session outcome topic should convert correctly."""
        result = canonical_topic_to_dispatch_alias(EXPECTED_SESSION_OUTCOME)
        assert result == "onex.commands.omniintelligence.session-outcome.v1"

    def test_pattern_lifecycle_conversion(self) -> None:
        """Pattern lifecycle topic should convert correctly."""
        result = canonical_topic_to_dispatch_alias(EXPECTED_PATTERN_LIFECYCLE)
        assert (
            result == "onex.commands.omniintelligence.pattern-lifecycle-transition.v1"
        )

    def test_no_cmd_or_evt_unchanged(self) -> None:
        """Topics without .cmd. or .evt. should pass through unchanged."""
        topic = "some.other.topic.v1"
        assert canonical_topic_to_dispatch_alias(topic) == topic

    def test_pattern_learned_conversion(self) -> None:
        """Pattern learned topic should convert correctly."""
        result = canonical_topic_to_dispatch_alias(EXPECTED_PATTERN_LEARNED)
        assert result == "onex.events.omniintelligence.pattern-learned.v1"

    def test_pattern_discovered_conversion(self) -> None:
        """Pattern discovered topic should convert correctly."""
        result = canonical_topic_to_dispatch_alias(EXPECTED_PATTERN_DISCOVERED)
        assert result == "onex.events.pattern.discovered.v1"

    def test_pattern_learning_conversion(self) -> None:
        """Pattern learning topic should convert correctly."""
        result = canonical_topic_to_dispatch_alias(EXPECTED_PATTERN_LEARNING)
        assert result == "onex.commands.omniintelligence.pattern-learning.v1"

    @pytest.mark.parametrize(
        "canonical,expected_alias",
        [
            (
                EXPECTED_CLAUDE_HOOK,
                "onex.commands.omniintelligence.claude-hook-event.v1",
            ),
            (
                EXPECTED_TOOL_CONTENT,
                "onex.commands.omniintelligence.tool-content.v1",
            ),
            (
                EXPECTED_SESSION_OUTCOME,
                "onex.commands.omniintelligence.session-outcome.v1",
            ),
            (
                EXPECTED_PATTERN_LEARNING,
                "onex.commands.omniintelligence.pattern-learning.v1",
            ),
            (
                EXPECTED_PATTERN_LIFECYCLE,
                "onex.commands.omniintelligence.pattern-lifecycle-transition.v1",
            ),
            (
                EXPECTED_PATTERN_LEARNED,
                "onex.events.omniintelligence.pattern-learned.v1",
            ),
            (
                EXPECTED_PATTERN_DISCOVERED,
                "onex.events.pattern.discovered.v1",
            ),
        ],
    )
    def test_all_intelligence_topics_convert_to_dispatch_aliases(
        self,
        canonical: str,
        expected_alias: str,
    ) -> None:
        """All 8 intelligence topics must produce correct dispatch aliases."""
        assert canonical_topic_to_dispatch_alias(canonical) == expected_alias


# =============================================================================
# Tests: Runtime subscribes to all topics (OMN-2189 integration)
# =============================================================================


class TestRuntimeTopicSubscription:
    """Validate that the runtime subscribes to all intelligence topics.

    OMN-2189 Bug 2: node_pattern_storage_effect was missing from the topic
    scanner, so its topics were never subscribed to.
    """

    def test_storage_effect_in_node_packages(self) -> None:
        """node_pattern_storage_effect must be in the discovered node packages."""
        from omniintelligence.runtime.contract_topics import (
            _discover_effect_node_packages,
        )

        packages = _discover_effect_node_packages()
        assert "omniintelligence.nodes.node_pattern_storage_effect" in packages

    def test_learning_effect_in_node_packages(self) -> None:
        """node_pattern_learning_effect must be in the discovered node packages."""
        from omniintelligence.runtime.contract_topics import (
            _discover_effect_node_packages,
        )

        packages = _discover_effect_node_packages()
        assert "omniintelligence.nodes.node_pattern_learning_effect" in packages

    def test_plugin_subscribes_to_at_least_four_topics(self) -> None:
        """INTELLIGENCE_SUBSCRIBE_TOPICS must have at least 4 topics."""
        from omniintelligence.runtime.plugin import INTELLIGENCE_SUBSCRIBE_TOPICS

        assert len(INTELLIGENCE_SUBSCRIBE_TOPICS) >= 4, (
            f"Expected at least 4 topics, got {len(INTELLIGENCE_SUBSCRIBE_TOPICS)}: "
            f"{INTELLIGENCE_SUBSCRIBE_TOPICS}"
        )

    def test_plugin_subscribes_to_pattern_learned(self) -> None:
        """Plugin must subscribe to pattern-learned topic."""
        from omniintelligence.runtime.plugin import INTELLIGENCE_SUBSCRIBE_TOPICS

        assert EXPECTED_PATTERN_LEARNED in INTELLIGENCE_SUBSCRIBE_TOPICS

    def test_plugin_subscribes_to_pattern_discovered(self) -> None:
        """Plugin must subscribe to pattern.discovered topic."""
        from omniintelligence.runtime.plugin import INTELLIGENCE_SUBSCRIBE_TOPICS

        assert EXPECTED_PATTERN_DISCOVERED in INTELLIGENCE_SUBSCRIBE_TOPICS
