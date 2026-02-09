# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for contract-driven topic discovery.

Validates:
    - collect_subscribe_topics_from_contracts returns exactly 3 topics
    - Discovered topics match the contract.yaml declarations
    - canonical_topic_to_dispatch_alias converts correctly
    - INTELLIGENCE_SUBSCRIBE_TOPICS in plugin.py is contract-driven

Related:
    - OMN-2033: Move intelligence topics to contract.yaml declarations
"""

from __future__ import annotations

import pytest

from omniintelligence.runtime.contract_topics import (
    canonical_topic_to_dispatch_alias,
    collect_subscribe_topics_from_contracts,
)

# =============================================================================
# Expected topics (must match contract.yaml declarations)
# =============================================================================

EXPECTED_CLAUDE_HOOK = "onex.cmd.omniintelligence.claude-hook-event.v1"
EXPECTED_SESSION_OUTCOME = "onex.cmd.omniintelligence.session-outcome.v1"
EXPECTED_PATTERN_LIFECYCLE = "onex.cmd.omniintelligence.pattern-lifecycle-transition.v1"

EXPECTED_TOPICS = {
    EXPECTED_CLAUDE_HOOK,
    EXPECTED_SESSION_OUTCOME,
    EXPECTED_PATTERN_LIFECYCLE,
}


# =============================================================================
# Tests: collect_subscribe_topics_from_contracts
# =============================================================================


class TestCollectSubscribeTopics:
    """Validate contract-driven topic collection."""

    def test_returns_exactly_three_topics(self) -> None:
        """Exactly 3 intelligence effect nodes declare subscribe topics."""
        topics = collect_subscribe_topics_from_contracts()
        assert len(topics) == 3

    def test_contains_claude_hook_event_topic(self) -> None:
        """Claude hook event topic must be discovered from contract."""
        topics = collect_subscribe_topics_from_contracts()
        assert EXPECTED_CLAUDE_HOOK in topics

    def test_contains_session_outcome_topic(self) -> None:
        """Session outcome topic must be discovered from contract."""
        topics = collect_subscribe_topics_from_contracts()
        assert EXPECTED_SESSION_OUTCOME in topics

    def test_contains_pattern_lifecycle_topic(self) -> None:
        """Pattern lifecycle topic must be discovered from contract."""
        topics = collect_subscribe_topics_from_contracts()
        assert EXPECTED_PATTERN_LIFECYCLE in topics

    def test_all_expected_topics_present(self) -> None:
        """All 3 expected topics must be in the discovered set."""
        topics = set(collect_subscribe_topics_from_contracts())
        assert topics == EXPECTED_TOPICS

    def test_returns_list_type(self) -> None:
        """Return type must be a list for ordered iteration."""
        topics = collect_subscribe_topics_from_contracts()
        assert isinstance(topics, list)

    def test_no_duplicates(self) -> None:
        """No duplicate topics should be returned."""
        topics = collect_subscribe_topics_from_contracts()
        assert len(topics) == len(set(topics))


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

    @pytest.mark.parametrize(
        "canonical,expected_alias",
        [
            (
                EXPECTED_CLAUDE_HOOK,
                "onex.commands.omniintelligence.claude-hook-event.v1",
            ),
            (
                EXPECTED_SESSION_OUTCOME,
                "onex.commands.omniintelligence.session-outcome.v1",
            ),
            (
                EXPECTED_PATTERN_LIFECYCLE,
                "onex.commands.omniintelligence.pattern-lifecycle-transition.v1",
            ),
        ],
    )
    def test_all_intelligence_topics_convert_to_dispatch_aliases(
        self,
        canonical: str,
        expected_alias: str,
    ) -> None:
        """All 3 intelligence topics must produce correct dispatch aliases."""
        assert canonical_topic_to_dispatch_alias(canonical) == expected_alias
