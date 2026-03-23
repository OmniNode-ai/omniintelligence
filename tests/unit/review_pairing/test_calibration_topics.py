# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for calibration Kafka topics and event model.

Reference: OMN-6173 (epic OMN-6164)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from omniintelligence.review_pairing.models_calibration import (
    CalibrationRunCompletedEvent,
)
from omniintelligence.review_pairing.topics import ReviewPairingTopic


@pytest.mark.unit
class TestCalibrationTopic:
    def test_topic_name_follows_onex_convention(self) -> None:
        topic = ReviewPairingTopic.CALIBRATION_RUN_COMPLETED
        assert topic.startswith("onex.evt.")
        assert "review-pairing" in topic
        assert topic.endswith(".v1")

    def test_topic_value(self) -> None:
        assert (
            ReviewPairingTopic.CALIBRATION_RUN_COMPLETED
            == "onex.evt.review-pairing.calibration-run-completed.v1"
        )


@pytest.mark.unit
class TestCalibrationRunCompletedEvent:
    def test_creation(self) -> None:
        event = CalibrationRunCompletedEvent(
            run_id="test-run-1",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            true_positives=5,
            false_positives=2,
            false_negatives=1,
            precision=0.714,
            recall=0.833,
            f1_score=0.769,
            noise_ratio=0.286,
            ground_truth_count=6,
            challenger_count=7,
            prompt_version="1.1.0",
            agreement_f1_ema=0.65,
            calibration_run_count=10,
            created_at=datetime.now(timezone.utc),
        )
        assert event.challenger_model == "deepseek-r1"
        assert event.fewshot_snapshot is None

    def test_json_serializable(self) -> None:
        event = CalibrationRunCompletedEvent(
            run_id="test-run-1",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            true_positives=5,
            false_positives=2,
            false_negatives=1,
            precision=0.714,
            recall=0.833,
            f1_score=0.769,
            noise_ratio=0.286,
            ground_truth_count=6,
            challenger_count=7,
            prompt_version="1.1.0",
            agreement_f1_ema=0.65,
            calibration_run_count=10,
            created_at=datetime.now(timezone.utc),
        )
        data = json.loads(event.model_dump_json())
        restored = CalibrationRunCompletedEvent.model_validate(data)
        assert restored.run_id == event.run_id
        assert restored.f1_score == event.f1_score

    def test_with_fewshot_snapshot(self) -> None:
        event = CalibrationRunCompletedEvent(
            run_id="test-run-2",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            true_positives=5,
            false_positives=2,
            false_negatives=1,
            precision=0.714,
            recall=0.833,
            f1_score=0.769,
            noise_ratio=0.286,
            ground_truth_count=6,
            challenger_count=7,
            prompt_version="1.2.0",
            agreement_f1_ema=0.72,
            calibration_run_count=15,
            fewshot_snapshot={
                "true_positives": [{"category": "arch", "description": "test"}],
                "false_positives": [],
            },
            created_at=datetime.now(timezone.utc),
        )
        assert event.fewshot_snapshot is not None
        assert "true_positives" in event.fewshot_snapshot
