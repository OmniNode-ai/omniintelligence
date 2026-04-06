# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Auto-wiring discovery test for intelligence effect node packages.

Verifies that dynamic discovery via directory scanning finds all
subscribing node packages and produces valid topics.

Reference: OMN-7142
"""

from __future__ import annotations

import pytest

from omniintelligence.runtime.contract_topics import (
    _discover_effect_node_packages,
    collect_subscribe_topics_from_contracts,
)

# Minimum expected packages -- known effect nodes that existed before
# dynamic discovery was introduced (OMN-7142).
_KNOWN_EFFECT_PACKAGES: set[str] = {
    "omniintelligence.nodes.node_bloom_eval_orchestrator",
    "omniintelligence.nodes.node_claude_hook_event_effect",
    "omniintelligence.nodes.node_compliance_evaluate_effect",
    "omniintelligence.nodes.node_crawl_scheduler_effect",
    "omniintelligence.nodes.node_pattern_feedback_effect",
    "omniintelligence.nodes.node_pattern_learning_effect",
    "omniintelligence.nodes.node_pattern_lifecycle_effect",
    "omniintelligence.nodes.node_pattern_projection_effect",
    "omniintelligence.nodes.node_pattern_storage_effect",
    "omniintelligence.nodes.node_code_crawler_effect",
    "omniintelligence.review_pairing",
    "omniintelligence.nodes.node_ci_failure_tracker_effect",
}


@pytest.mark.integration
class TestAutoWiringDiscovery:
    """Verify dynamic discovery finds all expected subscribing packages."""

    def test_known_packages_are_discovered(self) -> None:
        """All historically known packages must be found by discovery."""
        discovered = set(_discover_effect_node_packages())
        missing = _KNOWN_EFFECT_PACKAGES - discovered
        assert missing == set(), (
            f"Known packages not found by discovery: {missing}. "
            "These packages may be missing contract.yaml or subscribe_topics."
        )

    def test_discovery_finds_packages(self) -> None:
        """Discovery must find at least the known package count."""
        discovered = _discover_effect_node_packages()
        assert len(discovered) >= len(_KNOWN_EFFECT_PACKAGES), (
            f"Discovery found {len(discovered)} packages, "
            f"expected at least {len(_KNOWN_EFFECT_PACKAGES)}"
        )

    def test_collect_topics_produces_valid_topics(self) -> None:
        """Default collect (no override) produces valid onex topics."""
        topics = collect_subscribe_topics_from_contracts()
        assert len(topics) > 0, "No topics collected"
        for topic in topics:
            assert topic.startswith("onex."), f"Topic {topic} missing onex. prefix"

    def test_default_collect_includes_known_topics(self) -> None:
        """Default collect must include topics from known packages."""
        known_topics = set(
            collect_subscribe_topics_from_contracts(
                node_packages=list(_KNOWN_EFFECT_PACKAGES)
            )
        )
        default_topics = set(collect_subscribe_topics_from_contracts())

        missing = known_topics - default_topics
        assert missing == set(), f"Known topics not found in default collect: {missing}"


__all__ = ["TestAutoWiringDiscovery"]
