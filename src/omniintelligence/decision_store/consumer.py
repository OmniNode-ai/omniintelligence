# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka consumer that writes DecisionRecords to the repository.

Consumes from ``onex.cmd.omniintelligence.decision-recorded.v1`` and persists
DecisionRecordRow instances via DecisionRecordRepository.

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
from typing import TYPE_CHECKING, Any

from omniintelligence.decision_store.models import DecisionRecordRow
from omniintelligence.decision_store.repository import DecisionRecordRepository

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Topic consumed by this consumer
# ---------------------------------------------------------------------------

DECISION_RECORDED_TOPIC = "onex.cmd.omniintelligence.decision-recorded.v1"


# ---------------------------------------------------------------------------
# DecisionRecordConsumer
# ---------------------------------------------------------------------------


class DecisionRecordConsumer:
    """Kafka consumer for DecisionRecord events.

    Subscribes to ``onex.cmd.omniintelligence.decision-recorded.v1`` and
    writes each received DecisionRecord to the DecisionRecordRepository.

    Idempotency:
        Duplicate ``decision_id`` values are silently dropped (the repository
        is idempotent by design).

    Usage:
        consumer = DecisionRecordConsumer(repository=repo)
        consumer.handle_message(raw_message_bytes)
    """

    def __init__(self, repository: DecisionRecordRepository) -> None:
        """Initialize with a repository for persistence.

        Args:
            repository: Storage backend for DecisionRecord rows.
        """
        self._repository = repository

    @property
    def topic(self) -> str:
        """The Kafka topic this consumer subscribes to."""
        return DECISION_RECORDED_TOPIC

    def handle_message(self, raw_value: bytes) -> bool:
        """Process a single Kafka message and persist the DecisionRecord.

        Args:
            raw_value: Raw Kafka message value bytes (JSON-encoded
                DecisionRecord payload).

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
            )
            return False  # fallback-ok: skip incomplete messages

        # ------------------------------------------------------------------
        # Build row and store (idempotent)
        # ------------------------------------------------------------------
        stored_at = datetime.now(UTC)
        try:
            row = DecisionRecordRow.from_event_payload(payload, stored_at=stored_at)
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning(
                "DecisionRecordConsumer: failed to build row from payload. "
                "decision_id=%s error=%s",
                payload.get("decision_id", "<unknown>"),
                exc,
            )
            return False  # fallback-ok: skip malformed payload

        stored = self._repository.store(row)
        if not stored:
            logger.debug(
                "DecisionRecordConsumer: duplicate skipped. decision_id=%s",
                row.decision_id,
            )
        return stored


__all__ = [
    "DECISION_RECORDED_TOPIC",
    "DecisionRecordConsumer",
]
