# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the Calibration Persistence Layer.

Reference: OMN-6171 (epic OMN-6164)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from omniintelligence.review_pairing.calibration_persistence import (
    CalibrationPersistence,
)
from omniintelligence.review_pairing.models_calibration import (
    CalibrationFindingTuple,
    CalibrationMetrics,
    CalibrationRunResult,
    FindingAlignment,
)


def _make_run_result(
    run_id: str = "test-run-1",
    model: str = "deepseek-r1",
    tp: int = 5,
    fp: int = 2,
    fn: int = 1,
) -> CalibrationRunResult:
    metrics = CalibrationMetrics(
        model=model,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=tp / (tp + fp) if (tp + fp) > 0 else 0.0,
        recall=tp / (tp + fn) if (tp + fn) > 0 else 0.0,
        f1_score=0.769,
        noise_ratio=fp / (tp + fp) if (tp + fp) > 0 else 0.0,
    )
    gt = CalibrationFindingTuple(
        category="architecture",
        location="Task 1",
        description="Test",
        severity="error",
        source_model="codex",
    )
    ch = CalibrationFindingTuple(
        category="architecture",
        location="Task 1",
        description="Test",
        severity="error",
        source_model=model,
    )
    alignments = [
        FindingAlignment(
            ground_truth=gt,
            challenger=ch,
            similarity_score=0.9,
            aligned=True,
            alignment_type="true_positive",
        )
    ]
    return CalibrationRunResult(
        run_id=run_id,
        ground_truth_model="codex",
        challenger_model=model,
        alignments=alignments,
        metrics=metrics,
        prompt_version="1.1.0",
        created_at=datetime.now(timezone.utc),
    )


def _make_failed_result(run_id: str = "test-run-fail") -> CalibrationRunResult:
    return CalibrationRunResult(
        run_id=run_id,
        ground_truth_model="codex",
        challenger_model="deepseek-r1",
        alignments=[],
        metrics=None,
        prompt_version="1.1.0",
        error="Connection timeout",
        created_at=datetime.now(timezone.utc),
    )


def _make_mock_db() -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock(return_value="INSERT 0 1")
    db.fetchrow = AsyncMock(return_value={"calibration_score": 0.5})
    db.fetch = AsyncMock(return_value=[])
    return db


@pytest.mark.unit
class TestCalibrationPersistence:
    @pytest.fixture
    def db(self) -> AsyncMock:
        return _make_mock_db()

    @pytest.fixture
    def persistence(self, db: AsyncMock) -> CalibrationPersistence:
        return CalibrationPersistence(db_conn=db)

    @pytest.mark.asyncio
    async def test_save_run_calls_execute(
        self, persistence: CalibrationPersistence, db: AsyncMock
    ) -> None:
        result = _make_run_result()
        await persistence.save_run(result, content_hash="abc123")
        db.execute.assert_called_once()
        call_args = db.execute.call_args
        assert call_args[0][1] == "test-run-1"  # run_id
        assert call_args[0][2] == "codex"  # ground_truth_model
        assert call_args[0][3] == "deepseek-r1"  # challenger_model

    @pytest.mark.asyncio
    async def test_save_run_skips_failed_result(
        self, persistence: CalibrationPersistence, db: AsyncMock
    ) -> None:
        result = _make_failed_result()
        await persistence.save_run(result, content_hash="abc123")
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_model_score_returns_new_score(
        self, persistence: CalibrationPersistence, db: AsyncMock
    ) -> None:
        db.fetchrow.return_value = {"calibration_score": 0.65}
        new_score = await persistence.update_model_score("deepseek-r1", "codex", 0.8)
        assert new_score == 0.65
        db.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_event(
        self, persistence: CalibrationPersistence, db: AsyncMock
    ) -> None:
        await persistence.enqueue_event(
            topic="onex.evt.review-pairing.calibration-run-completed.v1",
            key="deepseek-r1",
            payload={"run_id": "test-1", "f1_score": 0.8},
        )
        db.execute.assert_called_once()
        call_args = db.execute.call_args
        assert "calibration-run-completed" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_run_history(
        self, persistence: CalibrationPersistence, db: AsyncMock
    ) -> None:
        mock_row = MagicMock()
        mock_row.__iter__ = MagicMock(return_value=iter([]))
        mock_row.items = MagicMock(return_value=[("run_id", "r1"), ("f1_score", 0.8)])
        mock_row.keys = MagicMock(return_value=["run_id", "f1_score"])
        mock_row.__getitem__ = lambda self, key: dict(self.items())[key]
        db.fetch.return_value = [{"run_id": "r1", "f1_score": 0.8}]
        rows = await persistence.get_run_history("deepseek-r1", limit=10)
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_get_alignment_details_parses_json(
        self, persistence: CalibrationPersistence, db: AsyncMock
    ) -> None:
        alignment_data = [{"alignment_type": "true_positive", "similarity_score": 0.9}]
        db.fetch.return_value = [{"alignment_details": json.dumps(alignment_data)}]
        result = await persistence.get_alignment_details("deepseek-r1", limit=5)
        assert len(result) == 1
        assert result[0][0]["alignment_type"] == "true_positive"

    @pytest.mark.asyncio
    async def test_get_all_model_scores_no_filter(
        self, persistence: CalibrationPersistence, db: AsyncMock
    ) -> None:
        db.fetch.return_value = [
            {
                "model_id": "deepseek-r1",
                "reference_model": "codex",
                "calibration_score": 0.7,
            }
        ]
        scores = await persistence.get_all_model_scores()
        assert len(scores) == 1

    @pytest.mark.asyncio
    async def test_get_all_model_scores_with_reference_filter(
        self, persistence: CalibrationPersistence, db: AsyncMock
    ) -> None:
        db.fetch.return_value = []
        await persistence.get_all_model_scores(reference_model="codex")
        call_args = db.fetch.call_args
        assert "reference_model" in call_args[0][0]
