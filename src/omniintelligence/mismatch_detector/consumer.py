# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka consumer triggering rationale mismatch detection.

Consumes DecisionRecord events from Kafka, runs mismatch detection for
records with agent_rationale, and emits mismatch events to the
rationale-mismatch topic.

Design:
    - Triggers detection when has_rationale=True in event payload.
    - Skips records with agent_rationale=None.
    - Emits mismatch events to onex.evt.omniintelligence.rationale-mismatch.v1.
    - Clean decisions (no mismatches) do NOT emit events (avoids noise).
    - Non-blocking: consumer runs async; mismatch events fire-and-forget.

Ticket: OMN-2472
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from omniintelligence.hooks.topics import OmniIntelligenceTopics
from omniintelligence.mismatch_detector.detector import detect_mismatches

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MismatchDetectionConsumer
# ---------------------------------------------------------------------------


class MismatchDetectionConsumer:
    """Kafka consumer for DecisionRecord mismatch detection.

    Listens on the DecisionRecord cmd topic, runs rationale mismatch
    detection for records with rationale, and emits mismatch events.

    The consumer only triggers detection when:
    - The message payload has ``has_rationale: True`` (for evt topic events)
    - OR the message payload contains ``agent_rationale`` with a value.

    Args:
        event_emitter: Callable that emits a mismatch event dict to Kafka.
            Signature: ``emitter(topic: str, payload: dict) -> None``.
            If None, emits are logged only (degraded mode).
        mismatch_store: Optional dict-based store for mismatch reports
            (keyed by decision_id → list of report dicts). If provided,
            reports are stored for the dashboard API.
    """

    def __init__(
        self,
        event_emitter: Any = None,
        mismatch_store: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        """Initialize with optional emitter and store."""
        self._emitter = event_emitter
        self._store: dict[str, list[dict[str, Any]]] = mismatch_store or {}

    @property
    def subscribed_topic(self) -> str:
        """The Kafka topic this consumer subscribes to."""
        return OmniIntelligenceTopics.DECISION_RECORDED_CMD

    def handle_message(self, raw_value: bytes) -> int:
        """Process a Kafka DecisionRecord message.

        Runs mismatch detection for records with rationale. Emits
        mismatch events if any are found. Clean decisions do NOT emit.

        Args:
            raw_value: Raw Kafka message bytes (JSON-encoded DecisionRecord).

        Returns:
            Number of mismatches detected (0 if clean or no rationale).
        """
        # ------------------------------------------------------------------
        # Deserialize
        # ------------------------------------------------------------------
        try:
            payload: dict[str, Any] = json.loads(raw_value.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning(
                "MismatchDetectionConsumer: failed to parse message. error=%s",
                exc,
            )
            return 0  # fallback-ok: skip malformed messages

        # ------------------------------------------------------------------
        # Skip if no rationale
        # ------------------------------------------------------------------
        agent_rationale = payload.get("agent_rationale")
        has_rationale_flag = payload.get("has_rationale", False)

        if agent_rationale is None and not has_rationale_flag:
            logger.debug(
                "MismatchDetectionConsumer: skipping (no rationale). decision_id=%s",
                payload.get("decision_id", "<unknown>"),
            )
            return 0

        # ------------------------------------------------------------------
        # Run detection
        # ------------------------------------------------------------------
        detected_at = datetime.now(UTC)
        try:
            reports = detect_mismatches(payload, detected_at=detected_at)
        except Exception as exc:
            # fallback-ok: detection failure must not block consumer
            logger.warning(
                "MismatchDetectionConsumer: detection failed. decision_id=%s error=%s",
                payload.get("decision_id", "<unknown>"),
                exc,
            )
            return 0

        if not reports:
            # Clean decision — no events emitted
            logger.debug(
                "MismatchDetectionConsumer: clean decision. decision_id=%s",
                payload.get("decision_id", "<unknown>"),
            )
            return 0

        # ------------------------------------------------------------------
        # Emit mismatch events and store reports
        # ------------------------------------------------------------------
        decision_id = str(payload.get("decision_id", "unknown"))
        self._store.setdefault(decision_id, [])

        for report in reports:
            # Store for dashboard API
            self._store[decision_id].append(report.to_full_dict())

            # Emit event (privacy-safe summary only)
            event_dict = report.to_event_dict()
            self._emit_event(event_dict)

        logger.info(
            "MismatchDetectionConsumer: emitted %d mismatch event(s). decision_id=%s",
            len(reports),
            decision_id,
        )
        return len(reports)

    def get_mismatches(self, decision_id: str) -> list[dict[str, Any]]:
        """Retrieve stored mismatch reports for a decision.

        Args:
            decision_id: The decision identifier.

        Returns:
            List of mismatch report dicts, or empty list if none found.
        """
        return self._store.get(decision_id, [])

    # ------------------------------------------------------------------
    # Internal emit helper
    # ------------------------------------------------------------------

    def _emit_event(self, event_dict: dict[str, Any]) -> None:
        """Emit a mismatch event to Kafka.

        Args:
            event_dict: Privacy-safe event payload.
        """
        topic = OmniIntelligenceTopics.RATIONALE_MISMATCH_EVT
        try:
            if self._emitter is not None:
                self._emitter(topic, event_dict)
            else:
                # Degraded mode: log only
                logger.info(
                    "MismatchDetectionConsumer [degraded]: would emit to %s. "
                    "decision_id=%s type=%s severity=%s",
                    topic,
                    event_dict.get("decision_id"),
                    event_dict.get("mismatch_type"),
                    event_dict.get("severity"),
                )
        except Exception as exc:
            # fallback-ok: emission failure must not block detection
            logger.warning(
                "MismatchDetectionConsumer: failed to emit event. error=%s",
                exc,
            )


__all__ = [
    "MismatchDetectionConsumer",
]
