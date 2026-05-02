# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler for dispatch-level pattern feedback recording.

This handler records per-task dispatch evaluation results without touching the
session-level pattern_injections outcome path owned by handler_session_outcome.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from omnibase_core.models.dispatch import ModelDispatchEvalResult

from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    EnumOutcomeRecordingStatus,
    ModelDispatchOutcomeResult,
)
from omniintelligence.protocols import ProtocolPatternRepository
from omniintelligence.utils.pg_status import parse_pg_status_count

logger = logging.getLogger(__name__)


SQL_UPSERT_DISPATCH_EVAL_RESULT = """
INSERT INTO dispatch_eval_results (
    task_id,
    dispatch_id,
    ticket_id,
    verdict,
    quality_score,
    token_cost,
    dollars_cost,
    model_calls,
    evaluated_at,
    eval_latency_ms,
    usage_source,
    estimation_method,
    source_payload_hash
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11, $12, $13)
ON CONFLICT (task_id, dispatch_id) DO UPDATE SET
    ticket_id = EXCLUDED.ticket_id,
    verdict = EXCLUDED.verdict,
    quality_score = EXCLUDED.quality_score,
    token_cost = EXCLUDED.token_cost,
    dollars_cost = EXCLUDED.dollars_cost,
    model_calls = EXCLUDED.model_calls,
    evaluated_at = EXCLUDED.evaluated_at,
    eval_latency_ms = EXCLUDED.eval_latency_ms,
    usage_source = EXCLUDED.usage_source,
    estimation_method = EXCLUDED.estimation_method,
    source_payload_hash = EXCLUDED.source_payload_hash
"""


async def record_dispatch_outcome(
    event: ModelDispatchEvalResult,
    *,
    repository: ProtocolPatternRepository,
) -> ModelDispatchOutcomeResult:
    """Record a dispatch evaluation result into dispatch_eval_results.

    The dedupe key is the table primary key: ``(task_id, dispatch_id)``.
    Replays update the same row with the canonical event payload rather than
    creating duplicates.
    """
    logger.info(
        "Recording dispatch outcome",
        extra={
            "task_id": event.task_id,
            "dispatch_id": event.dispatch_id,
            "ticket_id": event.ticket_id,
            "verdict": event.verdict.name,
        },
    )

    status = await repository.execute(
        SQL_UPSERT_DISPATCH_EVAL_RESULT,
        event.task_id,
        event.dispatch_id,
        event.ticket_id,
        event.verdict.name,
        event.quality_score,
        event.token_cost,
        event.dollars_cost,
        json.dumps(
            [call.model_dump(mode="json") for call in event.model_calls],
            sort_keys=True,
            separators=(",", ":"),
        ),
        event.evaluated_at,
        event.eval_latency_ms,
        event.cost_provenance.usage_source.name,
        event.cost_provenance.estimation_method,
        event.cost_provenance.source_payload_hash,
    )

    return ModelDispatchOutcomeResult(
        status=EnumOutcomeRecordingStatus.SUCCESS,
        task_id=event.task_id,
        dispatch_id=event.dispatch_id,
        ticket_id=event.ticket_id,
        rows_updated=parse_pg_status_count(status),
        recorded_at=datetime.now(UTC),
        error_message=None,
    )


__all__ = ["SQL_UPSERT_DISPATCH_EVAL_RESULT", "record_dispatch_outcome"]
