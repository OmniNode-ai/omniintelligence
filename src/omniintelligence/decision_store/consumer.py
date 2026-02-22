# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka consumer that writes DecisionRecords to the repository.

Consumes from ``onex.cmd.omniintelligence.decision-recorded.v1`` and persists
DecisionRecordRow instances via ProtocolDecisionRecordRepository.

Design:
    - Idempotent: duplicate decision_id is a no-op in the repository.
    - Non-blocking: consumer runs in a background asyncio task.
    - Graceful degradation: Kafka unavailability is logged and skipped.

Ticket: OMN-2467
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from omniintelligence.decision_store.models import DecisionRecordRow
from omniintelligence.protocols import ProtocolDecisionRecordRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Topic enum (external Kafka contract surface)
# ---------------------------------------------------------------------------


class DecisionRecordTopic(StrEnum):
    """Kafka topics consumed by DecisionRecordConsumer."""

    DECISION_RECORDED = "onex.cmd.omniintelligence.decision-recorded.v1"


# Keep a module-level alias for backwards compatibility and easy access
DECISION_RECORDED_TOPIC = DecisionRecordTopic.DECISION_RECORDED


# ---------------------------------------------------------------------------
# DecisionRecordConsumer
# ---------------------------------------------------------------------------


class DecisionRecordConsumer:
    """Kafka consumer for DecisionRecord events.

    Subscribes to ``DecisionRecordTopic.DECISION_RECORDED`` and writes each
    received DecisionRecord to the repository.

    Idempotency:
        Duplicate ``decision_id`` values are silently dropped (the repository
        is idempotent by design).

    Usage:
        consumer = DecisionRecordConsumer(repository=repo)
        consumer.handle_message(raw_message_bytes, correlation_id="abc-123")
    """

    def __init__(self, repository: ProtocolDecisionRecordRepository) -> None:
        """Initialize with a repository for persistence.

        Args:
            repository: Storage backend implementing ProtocolDecisionRecordRepository.
        """
        self._repository = repository

    @property
    def topic(self) -> str:
        """The Kafka topic this consumer subscribes to."""
        return DecisionRecordTopic.DECISION_RECORDED

    def handle_message(
        self,
        raw_value: bytes,
        *,
        correlation_id: str | None = None,
    ) -> bool:
        """Process a single Kafka message and persist the DecisionRecord.

        Args:
            raw_value: Raw Kafka message value bytes (JSON-encoded
                DecisionRecord payload).
            correlation_id: Trace correlation ID for end-to-end tracing.

        Returns:
            True if the record was stored, False if skipped (duplicate or
            parse error).
        """
        # ------------------------------------------------------------------
        # Deserialize
        # ------------------------------------------------------------------
        try:
            payload: dict[str, Any] = json.loads(raw_value.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning(
                "DecisionRecordConsumer: failed to parse message JSON. error=%s",
                exc,
                extra={"correlation_id": correlation_id},
            )
            return False  # fallback-ok: skip malformed messages

        # ------------------------------------------------------------------
        # Validate required fields
        # ------------------------------------------------------------------
        required = ("decision_id", "decision_type", "timestamp", "selected_candidate")
        missing = [f for f in required if f not in payload]
        if missing:
            logger.warning(
                "DecisionRecordConsumer: message missing required fields=%s. decision_id=%s",
                missing,
                payload.get("decision_id", "<unknown>"),
                extra={"correlation_id": correlation_id},
            )
            return False  # fallback-ok: skip incomplete messages

        # ------------------------------------------------------------------
        # Build row and store (idempotent)
        # ------------------------------------------------------------------
        stored_at = datetime.now(UTC)
        try:
            row = DecisionRecordRow.from_event_payload(
                payload,
                stored_at=stored_at,
                correlation_id=correlation_id,
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning(
                "DecisionRecordConsumer: failed to build row from payload. "
                "decision_id=%s error=%s",
                payload.get("decision_id", "<unknown>"),
                exc,
                extra={"correlation_id": correlation_id},
            )
            return False  # fallback-ok: skip malformed payload

        stored = self._repository.store(row, correlation_id=correlation_id)
        if not stored:
            logger.debug(
                "DecisionRecordConsumer: duplicate skipped. decision_id=%s",
                row.decision_id,
                extra={"correlation_id": correlation_id},
            )
        return stored


__all__ = [
    "DECISION_RECORDED_TOPIC",
    "DecisionRecordConsumer",
    "DecisionRecordTopic",
]
