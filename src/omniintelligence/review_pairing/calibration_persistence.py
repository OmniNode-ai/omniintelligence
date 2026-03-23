# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Calibration Persistence Layer for review calibration runs.

Handles PostgreSQL persistence, EMA score updates, and transactional outbox
writes for Kafka event emission.

Reference: OMN-6171 (epic OMN-6164)
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from omniintelligence.review_pairing.models_calibration import (
    CalibrationRunResult,
)


class ProtocolDBConnection(Protocol):
    """Minimal asyncpg-compatible connection protocol."""

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        """Execute a query and return all rows."""
        ...

    async def fetchrow(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single row."""
        ...

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status."""
        ...


_SQL_SAVE_RUN = """
INSERT INTO review_calibration_runs (
    run_id, ground_truth_model, challenger_model,
    true_positives, false_positives, false_negatives,
    precision_score, recall_score, f1_score, noise_ratio,
    ground_truth_count, challenger_count,
    prompt_version, content_hash,
    embedding_model_version, config_version,
    alignment_details
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17::jsonb)
ON CONFLICT (run_id, challenger_model)
DO UPDATE SET
    true_positives = EXCLUDED.true_positives,
    false_positives = EXCLUDED.false_positives,
    false_negatives = EXCLUDED.false_negatives,
    precision_score = EXCLUDED.precision_score,
    recall_score = EXCLUDED.recall_score,
    f1_score = EXCLUDED.f1_score,
    noise_ratio = EXCLUDED.noise_ratio,
    ground_truth_count = EXCLUDED.ground_truth_count,
    challenger_count = EXCLUDED.challenger_count,
    alignment_details = EXCLUDED.alignment_details
"""

_SQL_UPDATE_MODEL_SCORE = """
INSERT INTO review_calibration_model_scores (model_id, reference_model, calibration_score, calibration_run_count, updated_at)
VALUES ($1, $2, $3, 1, NOW())
ON CONFLICT (model_id, reference_model)
DO UPDATE SET
    calibration_score = 0.7 * review_calibration_model_scores.calibration_score + 0.3 * $3,
    calibration_run_count = review_calibration_model_scores.calibration_run_count + 1,
    updated_at = NOW()
RETURNING calibration_score
"""

_SQL_ENQUEUE_OUTBOX = """
INSERT INTO calibration_event_outbox (event_topic, event_key, event_payload)
VALUES ($1, $2, $3::jsonb)
"""

_SQL_GET_RUN_HISTORY = """
SELECT run_id, ground_truth_model, challenger_model,
       true_positives, false_positives, false_negatives,
       precision_score, recall_score, f1_score, noise_ratio,
       ground_truth_count, challenger_count,
       prompt_version, content_hash,
       embedding_model_version, config_version,
       created_at
FROM review_calibration_runs
WHERE challenger_model = $1
ORDER BY created_at DESC
LIMIT $2
"""

_SQL_GET_ALL_MODEL_SCORES = """
SELECT model_id, reference_model, calibration_score, calibration_run_count, updated_at
FROM review_calibration_model_scores
ORDER BY calibration_score DESC
"""

_SQL_GET_MODEL_SCORES_BY_REF = """
SELECT model_id, reference_model, calibration_score, calibration_run_count, updated_at
FROM review_calibration_model_scores
WHERE reference_model = $1
ORDER BY calibration_score DESC
"""

_SQL_GET_ALIGNMENT_DETAILS = """
SELECT alignment_details
FROM review_calibration_runs
WHERE challenger_model = $1
ORDER BY created_at DESC
LIMIT $2
"""


class CalibrationPersistence:
    """Persistence layer for calibration runs and model scores."""

    def __init__(self, db_conn: ProtocolDBConnection) -> None:
        self._db = db_conn

    async def save_run(self, result: CalibrationRunResult, content_hash: str) -> None:
        """Save a calibration run result to the database.

        Must be called within a transaction that also calls update_model_score
        and enqueues the Kafka event via the outbox.
        """
        if result.metrics is None:
            return

        m = result.metrics
        alignment_json = json.dumps(
            [a.model_dump(mode="json") for a in result.alignments]
        )

        await self._db.execute(
            _SQL_SAVE_RUN,
            result.run_id,
            result.ground_truth_model,
            result.challenger_model,
            m.true_positives,
            m.false_positives,
            m.false_negatives,
            m.precision,
            m.recall,
            m.f1_score,
            m.noise_ratio,
            m.true_positives + m.false_negatives,  # ground_truth_count
            m.true_positives + m.false_positives,  # challenger_count
            result.prompt_version,
            content_hash,
            result.embedding_model_version,
            result.config_version,
            alignment_json,
        )

    async def update_model_score(
        self, model: str, reference_model: str, f1_score: float
    ) -> float:
        """EMA update of calibration score for (model, reference_model) pair.

        Formula: new_score = 0.7 * old_score + 0.3 * f1_score
        Returns the new score.
        """
        row = await self._db.fetchrow(
            _SQL_UPDATE_MODEL_SCORE, model, reference_model, f1_score
        )
        return float(row["calibration_score"])

    async def enqueue_event(
        self, topic: str, key: str, payload: dict[str, Any]
    ) -> None:
        """Write an event to the transactional outbox."""
        await self._db.execute(_SQL_ENQUEUE_OUTBOX, topic, key, json.dumps(payload))

    async def get_run_history(
        self, challenger_model: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch recent calibration runs for time-series display."""
        rows = await self._db.fetch(_SQL_GET_RUN_HISTORY, challenger_model, limit)
        return [dict(row) for row in rows]

    async def get_all_model_scores(
        self, reference_model: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch current calibration scores."""
        if reference_model is not None:
            rows = await self._db.fetch(_SQL_GET_MODEL_SCORES_BY_REF, reference_model)
        else:
            rows = await self._db.fetch(_SQL_GET_ALL_MODEL_SCORES)
        return [dict(row) for row in rows]

    async def get_alignment_details(
        self, challenger_model: str, limit: int = 10
    ) -> list[list[dict[str, Any]]]:
        """Fetch alignment_details JSONB from recent runs."""
        rows = await self._db.fetch(_SQL_GET_ALIGNMENT_DETAILS, challenger_model, limit)
        result: list[list[dict[str, Any]]] = []
        for row in rows:
            details = row["alignment_details"]
            if isinstance(details, str):
                details = json.loads(details)
            result.append(details)
        return result
