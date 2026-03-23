# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for CalibrationPersistence.

TDD: Tests written first for OMN-6171.
These tests use mock connections to validate SQL generation and
EMA update logic without requiring a live database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from omniintelligence.review_pairing.calibration_persistence import (
    CalibrationPersistence,
    _compute_ema,
)
from omniintelligence.review_pairing.models_calibration import (
    CalibrationMetrics,
    CalibrationRunResult,
)


@pytest.mark.unit
class TestComputeEma:
    """Tests for EMA computation helper."""

    def test_first_run(self) -> None:
        result = _compute_ema(old_value=0.0, new_value=0.8, run_count=0)
        assert result == pytest.approx(0.8)

    def test_subsequent_run(self) -> None:
        result = _compute_ema(old_value=0.7, new_value=1.0, run_count=5)
        assert result == pytest.approx(0.7 * 0.7 + 1.0 * 0.3)

    def test_stable_ema(self) -> None:
        value = 0.5
        for _ in range(10):
            value = _compute_ema(old_value=value, new_value=0.5, run_count=10)
        assert value == pytest.approx(0.5, abs=0.01)


@pytest.mark.unit
class TestCalibrationPersistence:
    """Tests for CalibrationPersistence class."""

    def _make_run_result(
        self,
        run_id: str = "run-001",
        challenger: str = "deepseek-r1",
        f1: float = 0.75,
    ) -> CalibrationRunResult:
        return CalibrationRunResult(
            run_id=run_id,
            ground_truth_model="codex",
            challenger_model=challenger,
            alignments=[],
            metrics=CalibrationMetrics(
                model=challenger,
                true_positives=5,
                false_positives=2,
                false_negatives=1,
                precision=0.714,
                recall=0.833,
                f1_score=f1,
                noise_ratio=0.286,
            ),
            prompt_version="1.1.0",
            embedding_model_version="jaccard-v1",
            config_version="v1",
            created_at=datetime.now(tz=timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_save_run_calls_execute(self) -> None:
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        persistence = CalibrationPersistence(conn)
        result = self._make_run_result()
        await persistence.save_run(result, content_hash="abc123")
        assert conn.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_update_model_score_ema(self) -> None:
        conn = AsyncMock()
        # Simulate existing score row
        conn.fetchrow = AsyncMock(
            return_value={
                "calibration_score": 0.7,
                "precision_ema": 0.7,
                "recall_ema": 0.8,
                "f1_ema": 0.7,
                "noise_ema": 0.3,
                "run_count": 5,
            }
        )
        conn.execute = AsyncMock()
        persistence = CalibrationPersistence(conn)
        await persistence.update_model_score("deepseek-r1", "codex", 0.9)
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_run_history(self) -> None:
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        persistence = CalibrationPersistence(conn)
        result = await persistence.get_run_history("deepseek-r1", limit=10)
        assert result == []
        conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_model_scores(self) -> None:
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        persistence = CalibrationPersistence(conn)
        result = await persistence.get_all_model_scores()
        assert result == []

    @pytest.mark.asyncio
    async def test_failed_run_not_persisted(self) -> None:
        conn = AsyncMock()
        conn.execute = AsyncMock()
        persistence = CalibrationPersistence(conn)
        failed_result = CalibrationRunResult(
            run_id="run-fail",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            alignments=[],
            metrics=None,
            prompt_version="1.1.0",
            error="Connection timeout",
            created_at=datetime.now(tz=timezone.utc),
        )
        await persistence.save_run(failed_result, content_hash="abc")
        conn.execute.assert_not_called()
