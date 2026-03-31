# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""CI structural health checks for the pattern intelligence pipeline.

Validates that the pattern pipeline wiring is internally consistent:
- Contract subscribe topics have corresponding dispatch engine routes
- Publish/subscribe topic overlap ensures no orphaned events
- Omnidash topic matches what omniintelligence publishes
- Dispatch engine includes the projection handler

These are structural anti-drift checks — they read contract YAML files
and code constants, not runtime state. They catch regressions like topic
renames, missing dispatch routes, or contract drift before deployment.

Related:
    - OMN-6981: Pattern pipeline CI health check
    - OMN-2424: Pattern projection snapshot publisher
    - OMN-5611: Wire pattern-stored events to projection handler
"""

from __future__ import annotations

import pytest

from omniintelligence.runtime.contract_topics import (
    collect_publish_topics_for_dispatch,
    collect_subscribe_topics_from_contracts,
)

# ---------------------------------------------------------------------------
# Constants: expected topics from contracts
# ---------------------------------------------------------------------------

_PROJECTION_EFFECT_PACKAGE = "omniintelligence.nodes.node_pattern_projection_effect"
_STORAGE_EFFECT_PACKAGE = "omniintelligence.nodes.node_pattern_storage_effect"

# Omnidash topic constant (must match omnidash/shared/topics.ts)
_OMNIDASH_PATTERN_PROJECTION_TOPIC = "onex.evt.omniintelligence.pattern-projection.v1"


# ===========================================================================
# Test 1: Contract subscribe topics have dispatch routes
# ===========================================================================


@pytest.mark.unit
class TestProjectionEffectContractTopicsMatchDispatch:
    """Verify all projection effect subscribe topics have dispatch routes."""

    def test_projection_effect_contract_topics_in_all_subscribe_topics(
        self,
    ) -> None:
        """All pattern-projection subscribe topics must appear in the
        collected subscribe topic list used by the dispatch engine.

        If a topic is declared in the projection effect contract but not
        collected by collect_subscribe_topics_from_contracts(), the dispatch
        engine will never receive messages for it.
        """
        projection_topics = collect_subscribe_topics_from_contracts(
            node_packages=[_PROJECTION_EFFECT_PACKAGE],
        )
        all_topics = collect_subscribe_topics_from_contracts()

        assert len(projection_topics) > 0, (
            f"Projection effect contract declares no subscribe topics — "
            f"check {_PROJECTION_EFFECT_PACKAGE}/contract.yaml event_bus section"
        )

        missing = set(projection_topics) - set(all_topics)
        assert not missing, (
            f"Projection effect subscribe topics not collected by dispatch: {missing}. "
            f"Ensure {_PROJECTION_EFFECT_PACKAGE} is listed in "
            f"_INTELLIGENCE_EFFECT_NODE_PACKAGES in contract_topics.py"
        )


# ===========================================================================
# Test 2: Storage publish topics overlap with projection subscribe topics
# ===========================================================================


@pytest.mark.unit
class TestStoragePublishOverlapsProjectionSubscribe:
    """Verify storage effect publishes to topics the projection effect subscribes to."""

    def test_storage_effect_publishes_to_projection_subscribe(self) -> None:
        """At least one storage effect publish topic must be subscribed by
        the projection effect. Without this overlap, pattern-stored events
        would never reach the projection handler.
        """
        storage_publish = collect_publish_topics_for_dispatch(
            node_packages=[_STORAGE_EFFECT_PACKAGE],
        )
        projection_subscribe = collect_subscribe_topics_from_contracts(
            node_packages=[_PROJECTION_EFFECT_PACKAGE],
        )

        assert len(storage_publish) > 0, (
            f"Storage effect contract declares no publish topics — "
            f"check {_STORAGE_EFFECT_PACKAGE}/contract.yaml event_bus section"
        )
        assert len(projection_subscribe) > 0, (
            f"Projection effect contract declares no subscribe topics — "
            f"check {_PROJECTION_EFFECT_PACKAGE}/contract.yaml event_bus section"
        )

        storage_topics_set = set(storage_publish.values())
        projection_topics_set = set(projection_subscribe)

        overlap = storage_topics_set & projection_topics_set
        assert overlap, (
            f"No overlap between storage publish topics ({storage_topics_set}) "
            f"and projection subscribe topics ({projection_topics_set}). "
            f"Pattern-stored events will never reach the projection handler."
        )


# ===========================================================================
# Test 3: Omnidash topic matches projection publish topic
# ===========================================================================


@pytest.mark.unit
class TestOmnidashTopicMatchesProjectionPublish:
    """Verify omnidash pattern-projection topic matches what omniintelligence publishes."""

    def test_omnidash_topic_matches_projection_publish(self) -> None:
        """The omnidash SUFFIX_INTELLIGENCE_PATTERN_PROJECTION constant must
        match the publish topic declared in the projection effect contract.

        A mismatch means omnidash subscribes to a topic that omniintelligence
        never publishes to, resulting in 0 rows in pattern_learning_artifacts.
        """
        publish_topics = collect_publish_topics_for_dispatch(
            node_packages=[_PROJECTION_EFFECT_PACKAGE],
        )

        assert "pattern_projection" in publish_topics, (
            f"Projection effect contract has no publish topics mapped to "
            f"'pattern_projection' dispatch key. Keys found: {list(publish_topics.keys())}"
        )

        actual_topic = publish_topics["pattern_projection"]
        assert actual_topic == _OMNIDASH_PATTERN_PROJECTION_TOPIC, (
            f"Omnidash expects topic '{_OMNIDASH_PATTERN_PROJECTION_TOPIC}' "
            f"but projection effect publishes to '{actual_topic}'. "
            f"Update omnidash/shared/topics.ts or the projection contract."
        )


# ===========================================================================
# Test 4: Dispatch engine includes projection handler key
# ===========================================================================


@pytest.mark.unit
class TestDispatchEngineHasProjectionHandler:
    """Verify collect_publish_topics_for_dispatch includes pattern_projection key."""

    def test_dispatch_engine_has_projection_handler(self) -> None:
        """The default publish topics collection must include 'pattern_projection'.

        If missing, the projection handler won't receive its publish topic
        from the dispatch engine configuration.
        """
        topics = collect_publish_topics_for_dispatch()

        assert "pattern_projection" in topics, (
            f"'pattern_projection' key missing from collect_publish_topics_for_dispatch(). "
            f"Keys found: {list(topics.keys())}. "
            f"Ensure node_pattern_projection_effect is in _DISPATCH_KEY_TO_PACKAGE "
            f"in contract_topics.py"
        )
