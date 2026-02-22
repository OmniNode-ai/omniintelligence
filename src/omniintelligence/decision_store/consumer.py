# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka consumer that writes DecisionRecords to the repository.

Consumes from ``DecisionTopics.DECISION_RECORDED`` and persists
DecisionRecordRow instances via a ProtocolDecisionRecordRepository.

Design:
    - Idempotent: duplicate decision_id is a no-op in the repository.
    - Non-blocking: consumer runs in a background asyncio task.
    - Graceful degradation: Kafka unavailability is logged and skipped.
    - DI-friendly: accepts ProtocolDecisionRecordRepository, not a concrete class.

Ticket: OMN-2467
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from omniintelligence.decision_store.models import DecisionRecordRow
from omniintelligence.decision_store.protocols import ProtocolDecisionRecordRepository
from omniintelligence.decision_store.topics import DecisionTopics

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DecisionRecordConsumer
# ---------------------------------------------------------------------------


class DecisionRecordConsumer:
    """Kafka consumer for DecisionRecord events.

    Subscribes to ``DecisionTopics.DECISION_RECORDED`` and writes each
    received DecisionRecord to the repository.

    Idempotency:
        Duplicate ``decision_id`` values are silently dropped (the repository
        is idempotent by design).

    DI Pattern:
        Accepts ``ProtocolDecisionRecordRepository`` for testability —
        consistent with ``ProtocolPatternRepository`` usage across the codebase.

    Usage:
        consumer = DecisionRecordConsumer(repository=repo)
        consumer.handle_message(raw_message_bytes)
    """

    def __init__(self, repository: ProtocolDecisionRecordRepository) -> None:
        """Initialize with a repository for persistence.

        Args:
            repository: Storage backend implementing
                ``ProtocolDecisionRecordRepository``.
        """
        self._repository = repository

    @property
    def topic(self) -> str:
        """The Kafka topic this consumer subscribes to."""
        return DecisionTopics.DECISION_RECORDED

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
            correlation_id: Optional correlation ID for end-to-end tracing.
                Included in all log messages and passed to repository calls.

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
                "DecisionRecordConsumer: failed to parse message JSON. "
                "error=%s correlation_id=%s",
                exc,
                correlation_id,
            )
            return False  # fallback-ok: skip malformed messages

        # ------------------------------------------------------------------
        # Validate required fields
        # ------------------------------------------------------------------
        required = ("decision_id", "decision_type", "timestamp", "selected_candidate")
        missing = [f for f in required if f not in payload]
        if missing:
            logger.warning(
                "DecisionRecordConsumer: message missing required fields=%s. "
                "decision_id=%s correlation_id=%s",
                missing,
                payload.get("decision_id", "<unknown>"),
                correlation_id,
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
                "decision_id=%s error=%s correlation_id=%s",
                payload.get("decision_id", "<unknown>"),
                exc,
                correlation_id,
            )
            return False  # fallback-ok: skip malformed payload

        stored = self._repository.store(row, correlation_id=correlation_id)
        if not stored:
            logger.debug(
                "DecisionRecordConsumer: duplicate skipped. "
                "decision_id=%s correlation_id=%s",
                row.decision_id,
                correlation_id,
            )
        return stored


__all__ = [
    "DecisionRecordConsumer",
]
