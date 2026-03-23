# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for calibration Kafka topics.

TDD: Tests written first for OMN-6173.
"""

from __future__ import annotations

import pytest

from omniintelligence.review_pairing.topics import ReviewPairingTopic


@pytest.mark.unit
class TestCalibrationTopic:
    """Tests for the calibration-run-completed topic."""

    def test_topic_exists(self) -> None:
        assert hasattr(ReviewPairingTopic, "CALIBRATION_RUN_COMPLETED")

    def test_topic_name_follows_convention(self) -> None:
        topic = ReviewPairingTopic.CALIBRATION_RUN_COMPLETED
        assert topic.startswith("onex.evt.")
        assert "review-pairing" in topic
        assert topic.endswith(".v1")

    def test_topic_value(self) -> None:
        assert (
            ReviewPairingTopic.CALIBRATION_RUN_COMPLETED
            == "onex.evt.review-pairing.calibration-run-completed.v1"
        )

    def test_topic_is_str_enum(self) -> None:
        topic = ReviewPairingTopic.CALIBRATION_RUN_COMPLETED
        assert isinstance(topic, str)
        assert topic == str(topic)
