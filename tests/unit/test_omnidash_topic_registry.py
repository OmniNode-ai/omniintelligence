# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests that all omnidash-projected topics are centrally registered.

Verifies that every topic consumed by the omnidash read-model-consumer
for omniintelligence projection tables is present in either
IntentTopic (topics.py) or constants.py, and that no hardcoded
topic strings appear in handler code.

These topics feed omnidash projection tables that were found empty
(0 messages). Centralizing them in the registry ensures:
  1. Topic strings are consistent between producer and consumer.
  2. Hardcoded topic strings in handler files are replaced with imports.
  3. New emitters use the registry instead of inline strings.

Ticket: OMN-6808, OMN-6809
"""

from __future__ import annotations

import pytest

from omniintelligence.constants import (
    TOPIC_COMPLIANCE_EVALUATED_V1,
    TOPIC_EPISODE_BOUNDARY_V1,
    TOPIC_PLAN_REVIEW_STRATEGY_RUN_COMPLETED_V1,
    TOPIC_ROUTING_FEEDBACK_PROCESSED,
    TOPIC_RUN_EVALUATED_V1,
    TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1,
)
from omniintelligence.topics import IntentTopic

# =============================================================================
# Expected topics — the 9 omnidash projection table topics (OMN-6808)
# =============================================================================

# Map: (omnidash table name) -> (expected canonical topic string)
OMNIDASH_PROJECTION_TOPICS: dict[str, str] = {
    "llm_cost_aggregates": "onex.evt.omniintelligence.llm-call-completed.v1",
    "intent_drift_events": "onex.evt.omniintelligence.intent-drift-detected.v1",
    "routing_feedback_events": "onex.evt.omniintelligence.routing-feedback-processed.v1",
    "compliance_evaluations": "onex.evt.omniintelligence.compliance-evaluated.v1",
    "objective_evaluations": "onex.evt.omniintelligence.run-evaluated.v1",
    "objective_gate_failures": "onex.evt.omniintelligence.run-evaluated.v1",
    "rl_episodes": "onex.evt.omniintelligence.episode-boundary.v1",
    "plan_review_runs": "onex.evt.omniintelligence.plan-review-strategy-run-completed.v1",
    "pattern_lifecycle_transitions": "onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1",
}


class TestOmnidashTopicRegistry:
    """Verify all omnidash-projected topics are centrally registered."""

    @pytest.mark.unit
    def test_all_omnidash_topics_in_intent_topic_enum(self) -> None:
        """Every omnidash projection topic must appear in IntentTopic enum values."""
        enum_values = {member.value for member in IntentTopic}
        # Deduplicate (objective_evaluations and objective_gate_failures share a topic)
        unique_topics = set(OMNIDASH_PROJECTION_TOPICS.values())

        missing = unique_topics - enum_values
        assert not missing, (
            f"Topics missing from IntentTopic enum: {missing}. "
            "Add them to omniintelligence/topics.py"
        )

    @pytest.mark.unit
    def test_intent_topic_values_match_onex_convention(self) -> None:
        """All IntentTopic values must follow onex.evt.omniintelligence.*.v1 format."""
        for member in IntentTopic:
            assert member.value.startswith("onex.evt.omniintelligence."), (
                f"IntentTopic.{member.name} = {member.value!r} "
                "does not follow onex.evt.omniintelligence.* convention"
            )
            assert member.value.endswith(".v1"), (
                f"IntentTopic.{member.name} = {member.value!r} does not end with .v1"
            )

    @pytest.mark.unit
    def test_constants_py_topic_values_match(self) -> None:
        """Centralized constants match the expected topic strings."""
        assert (
            TOPIC_COMPLIANCE_EVALUATED_V1
            == "onex.evt.omniintelligence.compliance-evaluated.v1"
        )
        assert (
            TOPIC_EPISODE_BOUNDARY_V1 == "onex.evt.omniintelligence.episode-boundary.v1"
        )
        assert (
            TOPIC_ROUTING_FEEDBACK_PROCESSED
            == "onex.evt.omniintelligence.routing-feedback-processed.v1"
        )
        assert TOPIC_RUN_EVALUATED_V1 == "onex.evt.omniintelligence.run-evaluated.v1"
        assert (
            TOPIC_PLAN_REVIEW_STRATEGY_RUN_COMPLETED_V1
            == "onex.evt.omniintelligence.plan-review-strategy-run-completed.v1"
        )
        assert (
            TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1
            == "onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1"
        )

    @pytest.mark.unit
    def test_enum_and_constants_agree(self) -> None:
        """IntentTopic enum values and constants.py values agree for shared topics."""
        assert (
            IntentTopic.INTENT_DRIFT_DETECTED.value
            == "onex.evt.omniintelligence.intent-drift-detected.v1"
        )
        assert (
            IntentTopic.LLM_CALL_COMPLETED.value
            == "onex.evt.omniintelligence.llm-call-completed.v1"
        )
        assert (
            IntentTopic.ROUTING_FEEDBACK_PROCESSED.value
            == TOPIC_ROUTING_FEEDBACK_PROCESSED
        )
        assert IntentTopic.COMPLIANCE_EVALUATED.value == TOPIC_COMPLIANCE_EVALUATED_V1
        assert IntentTopic.RUN_EVALUATED.value == TOPIC_RUN_EVALUATED_V1
        assert IntentTopic.EPISODE_BOUNDARY.value == TOPIC_EPISODE_BOUNDARY_V1
        assert (
            IntentTopic.PLAN_REVIEW_STRATEGY_RUN_COMPLETED.value
            == TOPIC_PLAN_REVIEW_STRATEGY_RUN_COMPLETED_V1
        )
        assert (
            IntentTopic.PATTERN_LIFECYCLE_TRANSITIONED.value
            == TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1
        )

    @pytest.mark.unit
    def test_episode_emitter_uses_central_constant(self) -> None:
        """EpisodeEmitter.EPISODE_BOUNDARY_TOPIC must match the central constant."""
        from omniintelligence.model_selector.episode_emitter import (
            EPISODE_BOUNDARY_TOPIC,
        )

        assert EPISODE_BOUNDARY_TOPIC == TOPIC_EPISODE_BOUNDARY_V1

    @pytest.mark.unit
    def test_compliance_handler_uses_central_constant(self) -> None:
        """Compliance evaluate handler PUBLISH_TOPIC must match the central constant."""
        from omniintelligence.nodes.node_compliance_evaluate_effect.handlers.handler_compliance_evaluate import (
            PUBLISH_TOPIC,
        )

        assert PUBLISH_TOPIC == TOPIC_COMPLIANCE_EVALUATED_V1

    @pytest.mark.unit
    def test_no_duplicate_enum_values(self) -> None:
        """IntentTopic must have no duplicate values."""
        values = [member.value for member in IntentTopic]
        assert len(values) == len(set(values)), "IntentTopic contains duplicate values"
