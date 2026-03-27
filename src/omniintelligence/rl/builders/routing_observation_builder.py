# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Routing observation builders for RL training.

Two builders are provided:

1. **OnlineRoutingObservationBuilder** -- queries live endpoint health and
   current success rates for shadow mode / future online use. Observation
   construction target: < 50ms.

2. **HistoricalRoutingObservationRehydrator** -- reconstructs observations
   from stored episode context using ONLY data available at
   ``observation_timestamp``. Must provably use no future-leaked features.

Ticket: OMN-5565
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from omniintelligence.rl.contracts.observations import (
    _NUM_ENDPOINTS,
    _TASK_TYPES,
    EndpointHealth,
    RoutingObservation,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocols for external dependencies
# ---------------------------------------------------------------------------


@runtime_checkable
class EndpointHealthProvider(Protocol):
    """Protocol for querying live endpoint health metrics."""

    async def get_endpoint_health(self) -> list[dict[str, float]]:
        """Return health metrics for each endpoint.

        Returns:
            List of dicts with keys: latency_p50, error_rate,
            circuit_state, queue_depth. One dict per endpoint.
        """
        ...


@runtime_checkable
class SuccessRateProvider(Protocol):
    """Protocol for querying historical success rates."""

    async def get_rolling_success_rates(self) -> list[float]:
        """Return rolling 7-day success rate per endpoint.

        Returns:
            List of floats in [0, 1], one per endpoint.
        """
        ...


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservationBuilderConfig:
    """Configuration for observation builders.

    Attributes:
        max_tokens: Upper bound for token count normalization.
        default_latency_p50: Default latency if health data unavailable.
        default_error_rate: Default error rate if health data unavailable.
        default_success_rate: Default success rate if history unavailable.
        construction_timeout_ms: Target budget for observation construction.
    """

    max_tokens: int = 65_536
    default_latency_p50: float = 0.5
    default_error_rate: float = 0.05
    default_success_rate: float = 0.85
    construction_timeout_ms: float = 50.0


# ---------------------------------------------------------------------------
# OnlineRoutingObservationBuilder
# ---------------------------------------------------------------------------


class OnlineRoutingObservationBuilder:
    """Builds routing observations from live platform state.

    Queries endpoint health and success rate providers to construct
    a RoutingObservation in real time. Designed for shadow mode / future
    online policy execution.

    Observation construction target: < 50ms.

    Args:
        health_provider: Provides live endpoint health metrics.
        success_provider: Provides rolling success rates.
        config: Builder configuration.
    """

    def __init__(
        self,
        health_provider: EndpointHealthProvider,
        success_provider: SuccessRateProvider,
        config: ObservationBuilderConfig | None = None,
    ) -> None:
        self._health_provider = health_provider
        self._success_provider = success_provider
        self._config = config or ObservationBuilderConfig()

    async def build(
        self,
        *,
        task_type: str,
        estimated_tokens: int,
    ) -> RoutingObservation:
        """Build a routing observation from live platform state.

        Args:
            task_type: The type of task being routed (e.g. "code_gen").
            estimated_tokens: Estimated token count for the request.

        Returns:
            A RoutingObservation with current health and success data.
        """
        start_ms = time.monotonic() * 1000.0

        # Fetch live data
        raw_health = await self._health_provider.get_endpoint_health()
        success_rates = await self._success_provider.get_rolling_success_rates()

        # Build endpoint health objects
        endpoint_health = self._parse_health(raw_health)
        success_rates = self._pad_success_rates(success_rates)

        # Time encoding
        now = datetime.now()
        hour = now.hour + now.minute / 60.0
        angle = 2.0 * math.pi * hour / 24.0

        # Task type one-hot
        onehot = [1.0 if t == task_type else 0.0 for t in _TASK_TYPES]

        # Token normalization
        token_norm = min(estimated_tokens / max(self._config.max_tokens, 1), 1.0)

        obs = RoutingObservation(
            task_type_onehot=onehot,
            estimated_token_count_normalized=token_norm,
            per_endpoint_health=endpoint_health,
            historical_success_rate=success_rates,
            time_of_day_sin=math.sin(angle),
            time_of_day_cos=math.cos(angle),
        )

        elapsed_ms = time.monotonic() * 1000.0 - start_ms
        if elapsed_ms > self._config.construction_timeout_ms:
            logger.warning(
                "Observation construction took %.1fms (budget: %.1fms)",
                elapsed_ms,
                self._config.construction_timeout_ms,
            )

        return obs

    def _parse_health(self, raw_health: list[dict[str, float]]) -> list[EndpointHealth]:
        """Parse raw health dicts into EndpointHealth objects.

        Pads with defaults if fewer than _NUM_ENDPOINTS entries provided.
        """
        result: list[EndpointHealth] = []
        for i in range(_NUM_ENDPOINTS):
            if i < len(raw_health):
                h = raw_health[i]
                result.append(
                    EndpointHealth(
                        latency_p50=h.get(
                            "latency_p50", self._config.default_latency_p50
                        ),
                        error_rate=h.get("error_rate", self._config.default_error_rate),
                        circuit_state=h.get("circuit_state", 0.0),
                        queue_depth=h.get("queue_depth", 0.0),
                    )
                )
            else:
                result.append(
                    EndpointHealth(
                        latency_p50=self._config.default_latency_p50,
                        error_rate=self._config.default_error_rate,
                        circuit_state=0.0,
                        queue_depth=0.0,
                    )
                )
        return result

    def _pad_success_rates(self, rates: list[float]) -> list[float]:
        """Ensure exactly _NUM_ENDPOINTS success rates."""
        padded = list(rates[:_NUM_ENDPOINTS])
        while len(padded) < _NUM_ENDPOINTS:
            padded.append(self._config.default_success_rate)
        return padded


# ---------------------------------------------------------------------------
# HistoricalRoutingObservationRehydrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EpisodeContext:
    """Stored context for rehydrating a historical observation.

    Contains ONLY data that was available at observation_timestamp.
    This is the provenance record ensuring no future leakage.

    Attributes:
        observation_timestamp: When the routing decision was made.
        task_type: The task type that was being routed.
        estimated_tokens: Token count estimate at decision time.
        endpoint_health_snapshot: Health metrics snapshot at decision time.
        success_rates_snapshot: Success rates at decision time.
    """

    observation_timestamp: datetime
    task_type: str
    estimated_tokens: int
    endpoint_health_snapshot: list[dict[str, float]] = field(default_factory=list)
    success_rates_snapshot: list[float] = field(default_factory=list)


class HistoricalRoutingObservationRehydrator:
    """Reconstructs observations from stored episode context.

    CRITICAL: Uses ONLY data available at ``observation_timestamp``.
    Must provably use no future-leaked features.

    The rehydrator takes an EpisodeContext (which was recorded at
    decision time) and reconstructs the exact RoutingObservation that
    was -- or should have been -- used for the routing decision.

    Future-leak prevention:
        - All features come from the EpisodeContext snapshot
        - Time-of-day is derived from observation_timestamp (not now())
        - Health metrics and success rates are from the stored snapshot
        - No database queries are made during rehydration
        - The output is deterministic given the same EpisodeContext

    Args:
        config: Builder configuration.
    """

    def __init__(
        self,
        config: ObservationBuilderConfig | None = None,
    ) -> None:
        self._config = config or ObservationBuilderConfig()

    def rehydrate(self, context: EpisodeContext) -> RoutingObservation:
        """Reconstruct a RoutingObservation from stored episode context.

        This method is intentionally synchronous and makes NO external
        queries. All data comes from the provided context.

        Args:
            context: Episode context recorded at decision time.

        Returns:
            The RoutingObservation as it was at decision time.
        """
        # Task type one-hot -- uses context.task_type (from decision time)
        onehot = [1.0 if t == context.task_type else 0.0 for t in _TASK_TYPES]

        # Token normalization -- uses context.estimated_tokens (from decision time)
        token_norm = min(
            context.estimated_tokens / max(self._config.max_tokens, 1), 1.0
        )

        # Endpoint health -- uses snapshot from decision time
        endpoint_health = self._parse_health_snapshot(context.endpoint_health_snapshot)

        # Success rates -- uses snapshot from decision time
        success_rates = self._pad_success_rates(context.success_rates_snapshot)

        # Time encoding -- uses observation_timestamp (NOT current time)
        hour = (
            context.observation_timestamp.hour
            + context.observation_timestamp.minute / 60.0
        )
        angle = 2.0 * math.pi * hour / 24.0

        return RoutingObservation(
            task_type_onehot=onehot,
            estimated_token_count_normalized=token_norm,
            per_endpoint_health=endpoint_health,
            historical_success_rate=success_rates,
            time_of_day_sin=math.sin(angle),
            time_of_day_cos=math.cos(angle),
        )

    def rehydrate_from_raw(
        self, episode_row: dict[str, Any]
    ) -> RoutingObservation | None:
        """Reconstruct observation from a raw episode database row.

        If the row contains a pre-computed ``observation`` field (as a list
        of floats with the correct dimension), it is used directly.
        Otherwise, falls back to building from stored context fields.

        Args:
            episode_row: Dictionary-like row from rl_episodes table.

        Returns:
            RoutingObservation, or None if the row lacks sufficient context.
        """
        # Fast path: use pre-computed observation vector
        obs_raw = episode_row.get("observation")
        if isinstance(obs_raw, list) and len(obs_raw) == RoutingObservation.DIMS:
            try:
                import torch

                t = torch.tensor(obs_raw, dtype=torch.float32)
                return RoutingObservation.from_tensor(t)
            except (ValueError, TypeError):
                logger.debug(
                    "Pre-computed observation invalid, falling back to context"
                )

        # Slow path: reconstruct from stored context fields
        context_raw = episode_row.get("context")
        if not isinstance(context_raw, dict):
            return None

        try:
            context = EpisodeContext(
                observation_timestamp=_parse_timestamp(
                    episode_row.get(
                        "observation_timestamp",
                        context_raw.get("observation_timestamp"),
                    )
                ),
                task_type=str(context_raw.get("task_type", "general")),
                estimated_tokens=int(context_raw.get("estimated_tokens", 0)),
                endpoint_health_snapshot=context_raw.get(
                    "endpoint_health_snapshot", []
                ),
                success_rates_snapshot=context_raw.get("success_rates_snapshot", []),
            )
            return self.rehydrate(context)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Cannot rehydrate observation from context: %s", exc)
            return None

    def _parse_health_snapshot(
        self, snapshot: list[dict[str, float]]
    ) -> list[EndpointHealth]:
        """Parse health snapshot dicts into EndpointHealth objects."""
        result: list[EndpointHealth] = []
        for i in range(_NUM_ENDPOINTS):
            if i < len(snapshot):
                h = snapshot[i]
                result.append(
                    EndpointHealth(
                        latency_p50=float(
                            h.get("latency_p50", self._config.default_latency_p50)
                        ),
                        error_rate=float(
                            h.get("error_rate", self._config.default_error_rate)
                        ),
                        circuit_state=float(h.get("circuit_state", 0.0)),
                        queue_depth=float(h.get("queue_depth", 0.0)),
                    )
                )
            else:
                result.append(
                    EndpointHealth(
                        latency_p50=self._config.default_latency_p50,
                        error_rate=self._config.default_error_rate,
                        circuit_state=0.0,
                        queue_depth=0.0,
                    )
                )
        return result

    def _pad_success_rates(self, rates: list[float]) -> list[float]:
        """Ensure exactly _NUM_ENDPOINTS success rates."""
        padded = [float(r) for r in rates[:_NUM_ENDPOINTS]]
        while len(padded) < _NUM_ENDPOINTS:
            padded.append(self._config.default_success_rate)
        return padded


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_timestamp(value: Any) -> datetime:
    """Parse a timestamp from various formats."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Try ISO format
        return datetime.fromisoformat(value)
    msg = f"Cannot parse timestamp from {type(value)}: {value}"
    raise TypeError(msg)
