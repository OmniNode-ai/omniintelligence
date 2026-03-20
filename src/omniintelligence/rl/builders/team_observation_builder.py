# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Team observation builder for exploratory RL training.

Builds TeamObservation (~10 dims) from available historical data.
Gracefully skips if insufficient data is available.

This is exploratory infrastructure -- not expected to drive production
decisions. Data collection and supervised-learning precursor only.

Ticket: OMN-5572
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from omniintelligence.rl.contracts.observations import TeamObservation

logger = logging.getLogger(__name__)

# Number of agent slots tracked in the observation
_NUM_AGENT_SLOTS: int = 5

# Minimum number of historical records required to build a meaningful observation
_MIN_RECORDS_FOR_OBSERVATION: int = 10


# ---------------------------------------------------------------------------
# Protocols for external dependencies
# ---------------------------------------------------------------------------


@runtime_checkable
class TeamMetricsProvider(Protocol):
    """Protocol for querying team/agent coordination metrics."""

    async def get_agent_utilization(self) -> list[float]:
        """Return utilization fraction per agent slot [0, 1].

        Returns:
            List of floats, one per agent slot.
        """
        ...

    async def get_task_complexity(self) -> float:
        """Return the current task complexity score (raw, unnormalized).

        Returns:
            Float representing task complexity.
        """
        ...

    async def get_pending_task_count(self) -> int:
        """Return the number of pending tasks.

        Returns:
            Integer count of pending tasks.
        """
        ...

    async def get_time_pressure(self) -> float:
        """Return the current time pressure signal [0=relaxed, 1=urgent].

        Returns:
            Float in [0, 1].
        """
        ...

    async def get_success_rate(self) -> float:
        """Return the rolling team success rate [0, 1].

        Returns:
            Float in [0, 1].
        """
        ...

    async def get_coordination_overhead(self) -> float:
        """Return the inter-agent communication overhead (raw, unnormalized).

        Returns:
            Float representing overhead.
        """
        ...

    async def get_record_count(self) -> int:
        """Return total number of available historical records.

        Used to determine whether sufficient data exists for
        observation construction.
        """
        ...


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TeamObservationBuilderConfig:
    """Configuration for the team observation builder.

    Attributes:
        min_records: Minimum records required before building observations.
        max_task_complexity: Upper bound for complexity normalization.
        max_pending_tasks: Upper bound for pending task normalization.
        max_coordination_overhead: Upper bound for overhead normalization.
        default_utilization: Default agent utilization if data unavailable.
        default_complexity: Default normalized task complexity.
        default_pending: Default normalized pending tasks.
        default_time_pressure: Default time pressure signal.
        default_success_rate: Default rolling success rate.
        default_overhead: Default normalized coordination overhead.
    """

    min_records: int = _MIN_RECORDS_FOR_OBSERVATION
    max_task_complexity: float = 10.0
    max_pending_tasks: int = 50
    max_coordination_overhead: float = 100.0
    default_utilization: float = 0.0
    default_complexity: float = 0.5
    default_pending: float = 0.0
    default_time_pressure: float = 0.5
    default_success_rate: float = 0.85
    default_overhead: float = 0.0


# ---------------------------------------------------------------------------
# Data quality report
# ---------------------------------------------------------------------------


@dataclass
class TeamDataQualityReport:
    """Surface-specific data quality report for team observations.

    Generated before any training claims to ensure transparency about
    data availability and coverage.

    Attributes:
        total_records: Number of historical records available.
        sufficient_data: Whether minimum threshold is met.
        agents_with_data: Number of agent slots that have utilization data.
        agents_total: Total number of tracked agent slots.
        has_complexity_data: Whether task complexity data is available.
        has_success_rate_data: Whether success rate data is available.
        quality_notes: Human-readable notes about data quality.
    """

    total_records: int = 0
    sufficient_data: bool = False
    agents_with_data: int = 0
    agents_total: int = _NUM_AGENT_SLOTS
    has_complexity_data: bool = False
    has_success_rate_data: bool = False
    quality_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Historical context for rehydration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TeamEpisodeContext:
    """Stored context for rehydrating a historical team observation.

    Contains ONLY data that was available at the time of the team
    coordination decision, ensuring no future leakage.

    Attributes:
        agent_utilization: Utilization fraction per agent slot at decision time.
        task_complexity: Raw task complexity at decision time.
        pending_task_count: Pending task count at decision time.
        time_pressure: Time pressure signal at decision time.
        success_rate: Rolling success rate at decision time.
        coordination_overhead: Raw coordination overhead at decision time.
    """

    agent_utilization: list[float] = field(default_factory=list)
    task_complexity: float = 0.0
    pending_task_count: int = 0
    time_pressure: float = 0.5
    success_rate: float = 0.85
    coordination_overhead: float = 0.0


# ---------------------------------------------------------------------------
# OnlineTeamObservationBuilder
# ---------------------------------------------------------------------------


class OnlineTeamObservationBuilder:
    """Builds team observations from live platform state.

    Queries team metrics providers to construct a TeamObservation.
    Returns None if insufficient data is available.

    Args:
        metrics_provider: Provides live team/agent metrics.
        config: Builder configuration.
    """

    def __init__(
        self,
        metrics_provider: TeamMetricsProvider,
        config: TeamObservationBuilderConfig | None = None,
    ) -> None:
        self._provider = metrics_provider
        self._config = config or TeamObservationBuilderConfig()

    async def build(self) -> TeamObservation | None:
        """Build a team observation from live platform state.

        Returns:
            A TeamObservation if sufficient data exists, None otherwise.
        """
        record_count = await self._provider.get_record_count()
        if record_count < self._config.min_records:
            logger.info(
                "Insufficient team data: %d records (need %d). Skipping.",
                record_count,
                self._config.min_records,
            )
            return None

        raw_util = await self._provider.get_agent_utilization()
        raw_complexity = await self._provider.get_task_complexity()
        raw_pending = await self._provider.get_pending_task_count()
        time_pressure = await self._provider.get_time_pressure()
        success_rate = await self._provider.get_success_rate()
        raw_overhead = await self._provider.get_coordination_overhead()

        utilization = self._pad_utilization(raw_util)
        complexity_norm = min(
            raw_complexity / max(self._config.max_task_complexity, 1.0), 1.0
        )
        pending_norm = min(raw_pending / max(self._config.max_pending_tasks, 1), 1.0)
        overhead_norm = min(
            raw_overhead / max(self._config.max_coordination_overhead, 1.0), 1.0
        )

        return TeamObservation(
            agent_utilization=utilization,
            task_complexity_normalized=complexity_norm,
            pending_tasks_normalized=pending_norm,
            time_pressure=time_pressure,
            success_rate_rolling=success_rate,
            coordination_overhead=overhead_norm,
        )

    async def build_quality_report(self) -> TeamDataQualityReport:
        """Generate a data quality report for team observations.

        Should be called before any training claims to assess data coverage.

        Returns:
            A TeamDataQualityReport with coverage details.
        """
        record_count = await self._provider.get_record_count()
        raw_util = await self._provider.get_agent_utilization()
        raw_complexity = await self._provider.get_task_complexity()
        success_rate = await self._provider.get_success_rate()

        agents_with_data = sum(1 for u in raw_util if u > 0.0)
        sufficient = record_count >= self._config.min_records
        has_complexity = raw_complexity > 0.0
        has_success = success_rate > 0.0

        notes: list[str] = []
        if not sufficient:
            notes.append(
                f"Only {record_count} records available "
                f"(minimum: {self._config.min_records})"
            )
        if agents_with_data < _NUM_AGENT_SLOTS:
            notes.append(
                f"Only {agents_with_data}/{_NUM_AGENT_SLOTS} "
                "agent slots have utilization data"
            )
        if not has_complexity:
            notes.append("No task complexity data available")
        if sufficient and agents_with_data == _NUM_AGENT_SLOTS:
            notes.append("Full coverage across all agent slots")

        return TeamDataQualityReport(
            total_records=record_count,
            sufficient_data=sufficient,
            agents_with_data=agents_with_data,
            has_complexity_data=has_complexity,
            has_success_rate_data=has_success,
            quality_notes=notes,
        )

    def _pad_utilization(self, raw: list[float]) -> list[float]:
        """Ensure exactly _NUM_AGENT_SLOTS utilization values."""
        result = [max(0.0, min(1.0, float(v))) for v in raw[:_NUM_AGENT_SLOTS]]
        while len(result) < _NUM_AGENT_SLOTS:
            result.append(self._config.default_utilization)
        return result


# ---------------------------------------------------------------------------
# HistoricalTeamObservationRehydrator
# ---------------------------------------------------------------------------


class HistoricalTeamObservationRehydrator:
    """Reconstructs team observations from stored episode context.

    Uses ONLY data available at decision time. No future leakage.

    Args:
        config: Builder configuration.
    """

    def __init__(
        self,
        config: TeamObservationBuilderConfig | None = None,
    ) -> None:
        self._config = config or TeamObservationBuilderConfig()

    def rehydrate(self, context: TeamEpisodeContext) -> TeamObservation:
        """Reconstruct a TeamObservation from stored context.

        This method is synchronous and makes NO external queries.

        Args:
            context: Episode context recorded at decision time.

        Returns:
            The TeamObservation as it was at decision time.
        """
        utilization = self._pad_utilization(context.agent_utilization)
        complexity_norm = min(
            context.task_complexity / max(self._config.max_task_complexity, 1.0), 1.0
        )
        pending_norm = min(
            context.pending_task_count / max(self._config.max_pending_tasks, 1), 1.0
        )
        overhead_norm = min(
            context.coordination_overhead
            / max(self._config.max_coordination_overhead, 1.0),
            1.0,
        )

        return TeamObservation(
            agent_utilization=utilization,
            task_complexity_normalized=complexity_norm,
            pending_tasks_normalized=pending_norm,
            time_pressure=context.time_pressure,
            success_rate_rolling=context.success_rate,
            coordination_overhead=overhead_norm,
        )

    def rehydrate_from_raw(self, episode_row: dict[str, Any]) -> TeamObservation | None:
        """Reconstruct observation from a raw episode database row.

        Args:
            episode_row: Dictionary-like row from stored episodes.

        Returns:
            TeamObservation, or None if the row lacks sufficient context.
        """
        # Fast path: use pre-computed observation vector
        obs_raw = episode_row.get("observation")
        if isinstance(obs_raw, list) and len(obs_raw) == TeamObservation.DIMS:
            try:
                import torch

                t = torch.tensor(obs_raw, dtype=torch.float32)
                return TeamObservation.from_tensor(t)
            except (ValueError, TypeError):
                logger.debug(
                    "Pre-computed team observation invalid, falling back to context"
                )

        # Slow path: reconstruct from stored context
        context_raw = episode_row.get("context")
        if not isinstance(context_raw, dict):
            return None

        try:
            context = TeamEpisodeContext(
                agent_utilization=context_raw.get("agent_utilization", []),
                task_complexity=float(context_raw.get("task_complexity", 0.0)),
                pending_task_count=int(context_raw.get("pending_task_count", 0)),
                time_pressure=float(context_raw.get("time_pressure", 0.5)),
                success_rate=float(context_raw.get("success_rate", 0.85)),
                coordination_overhead=float(
                    context_raw.get("coordination_overhead", 0.0)
                ),
            )
            return self.rehydrate(context)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Cannot rehydrate team observation: %s", exc)
            return None

    def _pad_utilization(self, raw: list[float]) -> list[float]:
        """Ensure exactly _NUM_AGENT_SLOTS utilization values."""
        result = [max(0.0, min(1.0, float(v))) for v in raw[:_NUM_AGENT_SLOTS]]
        while len(result) < _NUM_AGENT_SLOTS:
            result.append(self._config.default_utilization)
        return result
