# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""EpisodeEmitter — wraps non-blocking RL episode boundary event emission.

Emits (state, action, reward) episode events to Kafka for the Learned
Decision Optimization Platform. Each model selection produces a pair of
events: ``episode_started`` (pre-action observation) and
``episode_completed`` (post-action outcome).

The emitter follows the same fire-and-forget pattern as DecisionEmitter:
emission failures are caught and logged, never blocking the selection result.

Topic: ``onex.evt.omniintelligence.episode-boundary.v1``

Ticket: OMN-5559
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from omniintelligence.constants import TOPIC_EPISODE_BOUNDARY_V1

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Topic constant — imported from constants.py (single source of truth)
# ---------------------------------------------------------------------------

EPISODE_BOUNDARY_TOPIC = TOPIC_EPISODE_BOUNDARY_V1


# ---------------------------------------------------------------------------
# Protocol / Abstract base
# ---------------------------------------------------------------------------


class EpisodeEmitterBase(ABC):
    """Abstract base for episode event emitters.

    Implement this to provide real or mock emission. The ModelSelector
    depends on this interface for testability.
    """

    @abstractmethod
    def emit_started(
        self,
        episode_id: str,
        surface: str,
        decision_snapshot: dict[str, Any],
        observation_timestamp: datetime,
        action_taken: dict[str, Any],
        emitted_at: datetime,
    ) -> None:
        """Emit an episode_started event.

        Must be non-blocking. Failures must be handled gracefully (logged).

        Args:
            episode_id: Deduplication key (UUID string).
            surface: Decision surface (routing, pipeline, team).
            decision_snapshot: Pre-action observation state ONLY.
            observation_timestamp: When the observation was frozen.
            action_taken: The selected action.
            emitted_at: Timestamp of emission.
        """
        ...

    @abstractmethod
    def emit_completed(
        self,
        episode_id: str,
        surface: str,
        terminal_status: str,
        outcome_metrics: dict[str, Any],
        emitted_at: datetime,
    ) -> None:
        """Emit an episode_completed event.

        Must be non-blocking. Failures must be handled gracefully (logged).

        Args:
            episode_id: Same UUID as the corresponding started event.
            surface: Decision surface.
            terminal_status: Final outcome (success, failure, incomplete, timeout).
            outcome_metrics: Post-execution metrics.
            emitted_at: Timestamp of emission.
        """
        ...


# ---------------------------------------------------------------------------
# EpisodeEmitter (real implementation)
# ---------------------------------------------------------------------------


class EpisodeEmitter(EpisodeEmitterBase):
    """Production episode event emitter.

    Emits episode boundary events to Kafka. Emission is fire-and-forget;
    failures are logged but do not propagate to callers.

    Args:
        kafka_publisher: Optional Kafka publisher. If None, emission is
            logged but not sent to Kafka (degraded mode).
    """

    def __init__(self, kafka_publisher: Any = None) -> None:
        """Initialize with optional Kafka publisher."""
        self._publisher = kafka_publisher

    def emit_started(
        self,
        episode_id: str,
        surface: str,
        decision_snapshot: dict[str, Any],
        observation_timestamp: datetime,
        action_taken: dict[str, Any],
        emitted_at: datetime,
    ) -> None:
        """Emit an episode_started event to Kafka (non-blocking)."""
        try:
            self._do_emit(
                episode_id=episode_id,
                surface=surface,
                phase="started",
                terminal_status=None,
                decision_snapshot=decision_snapshot,
                observation_timestamp=observation_timestamp,
                action_taken=action_taken,
                outcome_metrics={},
                emitted_at=emitted_at,
            )
        except Exception as exc:
            # fallback-ok: emission failure must not block model selection
            logger.warning(
                "EpisodeEmitter: failed to emit episode_started. "
                "episode_id=%s error=%s",
                episode_id,
                exc,
            )

    def emit_completed(
        self,
        episode_id: str,
        surface: str,
        terminal_status: str,
        outcome_metrics: dict[str, Any],
        emitted_at: datetime,
    ) -> None:
        """Emit an episode_completed event to Kafka (non-blocking)."""
        try:
            self._do_emit(
                episode_id=episode_id,
                surface=surface,
                phase="completed",
                terminal_status=terminal_status,
                decision_snapshot={},
                observation_timestamp=emitted_at,
                action_taken={},
                outcome_metrics=outcome_metrics,
                emitted_at=emitted_at,
            )
        except Exception as exc:
            # fallback-ok: emission failure must not block model selection
            logger.warning(
                "EpisodeEmitter: failed to emit episode_completed. "
                "episode_id=%s error=%s",
                episode_id,
                exc,
            )

    def _do_emit(
        self,
        *,
        episode_id: str,
        surface: str,
        phase: str,
        terminal_status: str | None,
        decision_snapshot: dict[str, Any],
        observation_timestamp: datetime,
        action_taken: dict[str, Any],
        outcome_metrics: dict[str, Any],
        emitted_at: datetime,
    ) -> None:
        """Internal: build payload and publish."""
        payload: dict[str, Any] = {
            "episode_id": episode_id,
            "surface": surface,
            "phase": phase,
            "terminal_status": terminal_status,
            "decision_snapshot": decision_snapshot,
            "observation_timestamp": observation_timestamp.isoformat(),
            "action_taken": action_taken,
            "outcome_metrics": outcome_metrics,
            "emitted_at": emitted_at.isoformat(),
        }

        if self._publisher is not None:
            self._publisher.produce(
                topic=EPISODE_BOUNDARY_TOPIC,
                value=json.dumps(payload).encode("utf-8"),
                key=episode_id.encode("utf-8"),
            )
        else:
            logger.info(
                "EpisodeEmitter: no Kafka publisher configured, "
                "logging emission intent. episode_id=%s phase=%s surface=%s",
                episode_id,
                phase,
                surface,
            )


# ---------------------------------------------------------------------------
# MockEpisodeEmitter (for unit testing)
# ---------------------------------------------------------------------------


class MockEpisodeEmitter(EpisodeEmitterBase):
    """Mock EpisodeEmitter for unit testing.

    Captures all emitted events so tests can assert on them.

    Attributes:
        started_events: List of started event kwargs.
        completed_events: List of completed event kwargs.
        should_fail: If True, raises RuntimeError on emit (tests degraded mode).
    """

    def __init__(self, *, should_fail: bool = False) -> None:
        """Initialize mock emitter."""
        self.started_events: list[dict[str, Any]] = []
        self.completed_events: list[dict[str, Any]] = []
        self.should_fail = should_fail

    def emit_started(
        self,
        episode_id: str,
        surface: str,
        decision_snapshot: dict[str, Any],
        observation_timestamp: datetime,
        action_taken: dict[str, Any],
        emitted_at: datetime,
    ) -> None:
        """Capture the started emission."""
        if self.should_fail:
            msg = "MockEpisodeEmitter: forced failure"
            raise RuntimeError(msg)
        self.started_events.append(
            {
                "episode_id": episode_id,
                "surface": surface,
                "decision_snapshot": decision_snapshot,
                "observation_timestamp": observation_timestamp,
                "action_taken": action_taken,
                "emitted_at": emitted_at,
            }
        )

    def emit_completed(
        self,
        episode_id: str,
        surface: str,
        terminal_status: str,
        outcome_metrics: dict[str, Any],
        emitted_at: datetime,
    ) -> None:
        """Capture the completed emission."""
        if self.should_fail:
            msg = "MockEpisodeEmitter: forced failure"
            raise RuntimeError(msg)
        self.completed_events.append(
            {
                "episode_id": episode_id,
                "surface": surface,
                "terminal_status": terminal_status,
                "outcome_metrics": outcome_metrics,
                "emitted_at": emitted_at,
            }
        )

    def clear(self) -> None:
        """Reset all captured emissions. For test use only."""
        self.started_events.clear()
        self.completed_events.clear()


__all__ = [
    "EPISODE_BOUNDARY_TOPIC",
    "EpisodeEmitter",
    "EpisodeEmitterBase",
    "MockEpisodeEmitter",
]
