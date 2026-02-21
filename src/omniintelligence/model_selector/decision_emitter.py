# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""DecisionEmitter — wraps non-blocking DecisionRecord emission.

Provides a thin abstraction over Kafka event emission for DecisionRecord
events. This class is injected into ModelSelector and can be replaced
with a mock implementation during testing.

Design:
    - Non-blocking: emission happens via a background/fire-and-forget call.
    - Degraded mode: if emission fails, selection result is still returned.
    - Injected: MockDecisionEmitter is available for unit tests.

Topics:
    - onex.evt.omniintelligence.decision-recorded.v1 (summary, broad access)
    - onex.cmd.omniintelligence.decision-recorded.v1 (full payload, restricted)

Ticket: OMN-2466
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Topic constants
# ---------------------------------------------------------------------------

DECISION_RECORDED_EVT_TOPIC = "onex.evt.omniintelligence.decision-recorded.v1"
DECISION_RECORDED_CMD_TOPIC = "onex.cmd.omniintelligence.decision-recorded.v1"


# ---------------------------------------------------------------------------
# Protocol / Abstract base
# ---------------------------------------------------------------------------


class DecisionEmitterBase(ABC):
    """Abstract base for DecisionRecord emitters.

    Implement this to provide real or mock emission. The ModelSelector
    depends on this interface for testability.
    """

    @abstractmethod
    def emit(self, record: dict[str, Any], emitted_at: datetime) -> None:
        """Emit a DecisionRecord.

        Must be non-blocking. Failures must be handled gracefully (logged).

        Args:
            record: DecisionRecord as a serializable dict.
            emitted_at: Timestamp of emission (injected by caller).
        """
        ...


# ---------------------------------------------------------------------------
# DecisionEmitter (real implementation — logs, no real Kafka in this revision)
# ---------------------------------------------------------------------------


class DecisionEmitter(DecisionEmitterBase):
    """Production DecisionRecord emitter.

    Emits DecisionRecord to the Kafka topics for the Decision Provenance
    system. Emission is fire-and-forget — failures are logged but do not
    propagate to callers.

    Note:
        This implementation logs the emission intent. Full Kafka integration
        is wired via the runtime plugin (PluginIntelligence) which provides
        a KafkaPublisher. For dependency injection, provide a kafka_publisher
        at construction time.

    Topics:
        - ``onex.evt.omniintelligence.decision-recorded.v1`` — summary payload
          (privacy-safe: no agent_rationale or reproducibility_snapshot)
        - ``onex.cmd.omniintelligence.decision-recorded.v1`` — full payload

    Args:
        kafka_publisher: Optional Kafka publisher. If None, emission is
            logged but not sent to Kafka (degraded mode).
    """

    def __init__(self, kafka_publisher: Any = None) -> None:
        """Initialize with optional Kafka publisher."""
        self._publisher = kafka_publisher

    def emit(self, record: dict[str, Any], emitted_at: datetime) -> None:
        """Emit a DecisionRecord to Kafka topics (non-blocking).

        Builds the summary (evt) payload and full (cmd) payload and sends
        both. If Kafka is unavailable, logs the failure and returns.

        Args:
            record: DecisionRecord serializable dict.
            emitted_at: Timestamp of emission.
        """
        try:
            self._do_emit(record, emitted_at)
        except Exception as exc:
            # fallback-ok: emission failure must not block model selection
            logger.warning(
                "DecisionEmitter: failed to emit DecisionRecord. "
                "decision_id=%s error=%s",
                record.get("decision_id", "<unknown>"),
                exc,
            )

    def _do_emit(self, record: dict[str, Any], emitted_at: datetime) -> None:
        """Internal: build payloads and publish.

        Args:
            record: Full DecisionRecord dict.
            emitted_at: Emission timestamp.
        """
        decision_id = record.get("decision_id", "unknown")
        decision_type = record.get("decision_type", "unknown")
        selected_candidate = record.get("selected_candidate", "unknown")
        candidates_considered = record.get("candidates_considered", [])
        has_rationale = bool(record.get("agent_rationale"))

        # -------------------------------------------------------------------
        # EVT payload (privacy-safe summary, broad access)
        # -------------------------------------------------------------------
        evt_payload: dict[str, Any] = {
            "decision_id": decision_id,
            "decision_type": decision_type,
            "selected_candidate": selected_candidate,
            "candidates_count": len(candidates_considered),
            "has_rationale": has_rationale,
            "emitted_at": emitted_at.isoformat(),
            "session_id": record.get("session_id"),
        }

        # -------------------------------------------------------------------
        # CMD payload (full record, restricted access)
        # -------------------------------------------------------------------
        cmd_payload: dict[str, Any] = {
            **record,
            "emitted_at": emitted_at.isoformat(),
        }

        if self._publisher is not None:
            # Non-blocking publish via the injected Kafka publisher
            self._publisher.produce(
                topic=DECISION_RECORDED_EVT_TOPIC,
                value=json.dumps(evt_payload).encode("utf-8"),
                key=decision_id.encode("utf-8"),
            )
            self._publisher.produce(
                topic=DECISION_RECORDED_CMD_TOPIC,
                value=json.dumps(cmd_payload).encode("utf-8"),
                key=decision_id.encode("utf-8"),
            )
        else:
            # Degraded mode: no Kafka publisher configured
            logger.info(
                "DecisionEmitter: no Kafka publisher configured, "
                "logging emission intent. decision_id=%s type=%s selected=%s",
                decision_id,
                decision_type,
                selected_candidate,
            )


# ---------------------------------------------------------------------------
# MockDecisionEmitter (for unit testing)
# ---------------------------------------------------------------------------


class MockDecisionEmitter(DecisionEmitterBase):
    """Mock DecisionEmitter for unit testing.

    Captures all emitted records so tests can assert on them.

    Attributes:
        emitted: List of (record_dict, emitted_at) tuples from each emit call.
        should_fail: If True, raises RuntimeError on emit (tests degraded mode).
    """

    def __init__(self, *, should_fail: bool = False) -> None:
        """Initialize mock emitter."""
        self.emitted: list[tuple[dict[str, Any], datetime]] = []
        self.should_fail = should_fail

    def emit(self, record: dict[str, Any], emitted_at: datetime) -> None:
        """Capture the emission."""
        if self.should_fail:
            msg = "MockDecisionEmitter: forced failure"
            raise RuntimeError(msg)
        self.emitted.append((record, emitted_at))

    @property
    def emit_count(self) -> int:
        """Number of times emit was called successfully."""
        return len(self.emitted)

    def last_record(self) -> dict[str, Any] | None:
        """Return the most recently emitted record, or None."""
        if not self.emitted:
            return None
        return self.emitted[-1][0]


__all__ = [
    "DECISION_RECORDED_CMD_TOPIC",
    "DECISION_RECORDED_EVT_TOPIC",
    "DecisionEmitter",
    "DecisionEmitterBase",
    "MockDecisionEmitter",
]
