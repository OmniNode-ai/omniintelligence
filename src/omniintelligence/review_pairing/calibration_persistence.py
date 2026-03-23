# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Calibration Persistence Layer.

Handles saving calibration run results, updating EMA model scores,
and writing transactional outbox events.

Reference: OMN-6171
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from omniintelligence.review_pairing.models_calibration import (
    CalibrationRunResult,
)

logger = logging.getLogger(__name__)


# EMA weight: 70% old value + 30% new value
_EMA_ALPHA = 0.3


def _compute_ema(old_value: float, new_value: float, run_count: int) -> float:
    """Compute exponential moving average.

    On the first run (run_count=0), returns new_value directly.
    Otherwise: (1 - alpha) * old_value + alpha * new_value.
    """
    if run_count == 0:
        return new_value
    return (1 - _EMA_ALPHA) * old_value + _EMA_ALPHA * new_value


class AsyncDBConnection(Protocol):
    """Protocol for async database connections (asyncpg-compatible)."""

    async def execute(self, query: str, *args: Any) -> str: ...
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def fetchrow(self, query: str, *args: Any) -> Any: ...


class CalibrationPersistence:
    """Persistence layer for calibration run results and model scores.

    Uses asyncpg-compatible connection interface.

    Args:
        conn: Async database connection (asyncpg Connection or Pool).
    """

    def __init__(self, conn: AsyncDBConnection) -> None:
        self._conn = conn

    async def save_run(
        self,
        result: CalibrationRunResult,
        content_hash: str,
    ) -> None:
        """Save a calibration run result with transactional outbox.

        Failed runs (error != None, metrics == None) are skipped.

        Args:
            result: The calibration run result to persist.
            content_hash: Hash of the content reviewed (for dedup).
        """
        if result.error is not None and result.metrics is None:
            logger.info(
                "Skipping persistence for failed run %s: %s",
                result.run_id,
                result.error,
            )
            return

        metrics = result.metrics
        assert metrics is not None

        alignment_json = json.dumps(
            [a.model_dump(mode="json") for a in result.alignments]
        )

        await self._conn.execute(
            """
            INSERT INTO review_calibration_runs (
                run_id, ground_truth_model, challenger_model,
                precision_score, recall_score, f1_score, noise_ratio,
                true_positives, false_positives, false_negatives,
                finding_count, alignment_details,
                prompt_version, embedding_model_version, config_version,
                error, created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12::jsonb, $13, $14, $15, $16, $17
            )
            ON CONFLICT (run_id, challenger_model) DO NOTHING
            """,
            result.run_id,
            result.ground_truth_model,
            result.challenger_model,
            metrics.precision,
            metrics.recall,
            metrics.f1_score,
            metrics.noise_ratio,
            metrics.true_positives,
            metrics.false_positives,
            metrics.false_negatives,
            metrics.true_positives + metrics.false_positives + metrics.false_negatives,
            alignment_json,
            result.prompt_version,
            result.embedding_model_version,
            result.config_version,
            result.error,
            result.created_at,
        )

        event_payload = {
            "event_id": str(uuid4()),
            "run_id": result.run_id,
            "ground_truth_model": result.ground_truth_model,
            "challenger_model": result.challenger_model,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "noise_ratio": metrics.noise_ratio,
            "finding_count": (
                metrics.true_positives
                + metrics.false_positives
                + metrics.false_negatives
            ),
            "prompt_version": result.prompt_version,
            "created_at": result.created_at.isoformat(),
        }
        await self._conn.execute(
            """
            INSERT INTO calibration_event_outbox (
                event_type, event_payload, created_at
            ) VALUES ($1, $2::jsonb, $3)
            """,
            "calibration-run-completed",
            json.dumps(event_payload),
            datetime.now(tz=timezone.utc),
        )

    async def update_model_score(
        self,
        model_id: str,
        reference_model: str,
        f1_score: float,
    ) -> None:
        """Update EMA-based model score after a successful calibration run.

        Uses 0.7 old + 0.3 new weighting.

        Args:
            model_id: Challenger model key.
            reference_model: Ground-truth model key.
            f1_score: F1 score from the latest run.
        """
        row = await self._conn.fetchrow(
            """
            SELECT calibration_score, precision_ema, recall_ema,
                   f1_ema, noise_ema, run_count
            FROM review_calibration_model_scores
            WHERE model_id = $1 AND reference_model = $2
            """,
            model_id,
            reference_model,
        )

        if row is None:
            await self._conn.execute(
                """
                INSERT INTO review_calibration_model_scores (
                    model_id, reference_model, calibration_score,
                    precision_ema, recall_ema, f1_ema, noise_ema,
                    run_count, updated_at
                ) VALUES ($1, $2, $3, 0, 0, $3, 0, 1, now())
                """,
                model_id,
                reference_model,
                f1_score,
            )
        else:
            new_f1_ema = _compute_ema(row["f1_ema"], f1_score, row["run_count"])
            await self._conn.execute(
                """
                UPDATE review_calibration_model_scores
                SET calibration_score = $1,
                    f1_ema = $1,
                    run_count = run_count + 1,
                    updated_at = now()
                WHERE model_id = $2 AND reference_model = $3
                """,
                new_f1_ema,
                model_id,
                reference_model,
            )

    async def get_run_history(
        self,
        challenger_model: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get recent calibration run history for a model.

        Args:
            challenger_model: Model key to query.
            limit: Max number of results.

        Returns:
            List of run records ordered by created_at DESC.
        """
        rows = await self._conn.fetch(
            """
            SELECT run_id, ground_truth_model, challenger_model,
                   precision_score, recall_score, f1_score, noise_ratio,
                   finding_count, created_at
            FROM review_calibration_runs
            WHERE challenger_model = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            challenger_model,
            limit,
        )
        return [dict(r) for r in rows]

    async def get_all_model_scores(
        self,
        reference_model: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get all model calibration scores.

        Args:
            reference_model: Optional filter by reference model.

        Returns:
            List of score records.
        """
        if reference_model is not None:
            rows = await self._conn.fetch(
                """
                SELECT model_id, reference_model, calibration_score,
                       f1_ema, run_count, updated_at
                FROM review_calibration_model_scores
                WHERE reference_model = $1
                ORDER BY calibration_score DESC
                """,
                reference_model,
            )
        else:
            rows = await self._conn.fetch(
                """
                SELECT model_id, reference_model, calibration_score,
                       f1_ema, run_count, updated_at
                FROM review_calibration_model_scores
                ORDER BY calibration_score DESC
                """
            )
        return [dict(r) for r in rows]

    async def get_alignment_details(
        self,
        challenger_model: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get recent alignment details for a model.

        Args:
            challenger_model: Model key to query.
            limit: Max number of runs to return alignment details for.

        Returns:
            List of records with alignment_details JSONB.
        """
        rows = await self._conn.fetch(
            """
            SELECT run_id, alignment_details, created_at
            FROM review_calibration_runs
            WHERE challenger_model = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            challenger_model,
            limit,
        )
        return [dict(r) for r in rows]
