# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for omniintelligence.review_pairing.topics.

Covers:
- All topic names follow ONEX canonical format
- ReviewPairingTopic enum is importable and has all required members
- Topic values are strings (StrEnum behavior)

Reference: OMN-2535
"""

from __future__ import annotations

import pytest

from omniintelligence.review_pairing.topics import ReviewPairingTopic


class TestReviewPairingTopic:
    """Tests for ReviewPairingTopic enum."""

    @pytest.mark.unit
    def test_all_required_topics_exist(self) -> None:
        """All four required topics must be defined."""
        assert hasattr(ReviewPairingTopic, "FINDING_OBSERVED")
        assert hasattr(ReviewPairingTopic, "FIX_APPLIED")
        assert hasattr(ReviewPairingTopic, "FINDING_RESOLVED")
        assert hasattr(ReviewPairingTopic, "PAIR_CREATED")

    @pytest.mark.unit
    def test_topic_names_follow_onex_format(self) -> None:
        """All topic names must follow onex.{kind}.{producer}.{event-name}.v{n} format."""
        for topic in ReviewPairingTopic:
            value = str(topic)
            assert value.startswith("onex."), (
                f"{topic.name} does not start with 'onex.': {value}"
            )
            parts = value.split(".")
            assert len(parts) >= 4, f"{topic.name} has too few parts: {value}"
            # Format: onex.evt.review-pairing.<event>.<version>
            assert parts[1] == "evt", f"{topic.name} kind is not 'evt': {value}"
            assert parts[2] == "review-pairing", (
                f"{topic.name} producer is not 'review-pairing': {value}"
            )
            last_part = parts[-1]
            assert last_part.startswith("v") and last_part[1:].isdigit(), (
                f"{topic.name} version part invalid: {value}"
            )

    @pytest.mark.unit
    def test_finding_observed_topic_value(self) -> None:
        """FINDING_OBSERVED topic string should match canonical value."""
        assert (
            str(ReviewPairingTopic.FINDING_OBSERVED)
            == "onex.evt.review-pairing.finding-observed.v1"
        )

    @pytest.mark.unit
    def test_fix_applied_topic_value(self) -> None:
        """FIX_APPLIED topic string should match canonical value."""
        assert (
            str(ReviewPairingTopic.FIX_APPLIED)
            == "onex.evt.review-pairing.fix-applied.v1"
        )

    @pytest.mark.unit
    def test_finding_resolved_topic_value(self) -> None:
        """FINDING_RESOLVED topic string should match canonical value."""
        assert (
            str(ReviewPairingTopic.FINDING_RESOLVED)
            == "onex.evt.review-pairing.finding-resolved.v1"
        )

    @pytest.mark.unit
    def test_pair_created_topic_value(self) -> None:
        """PAIR_CREATED topic string should match canonical value."""
        assert (
            str(ReviewPairingTopic.PAIR_CREATED)
            == "onex.evt.review-pairing.pair-created.v1"
        )

    @pytest.mark.unit
    def test_topics_are_strings(self) -> None:
        """All topics should behave as strings (StrEnum / StrValueHelper pattern)."""
        for topic in ReviewPairingTopic:
            assert isinstance(str(topic), str)
