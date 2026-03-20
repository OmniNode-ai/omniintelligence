# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pipeline observation builder for exploratory RL training.

Builds PipelineObservation (~15 dims) from available historical data.
Gracefully skips if insufficient data is available.

This is exploratory infrastructure -- not expected to drive production
decisions. Data collection and supervised-learning precursor only.

Ticket: OMN-5572
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from omniintelligence.rl.contracts.observations import PipelineObservation

logger = logging.getLogger(__name__)

# Number of pipeline stages tracked in the observation
_NUM_STAGES: int = 5

# Minimum number of historical records required to build a meaningful observation
_MIN_RECORDS_FOR_OBSERVATION: int = 10


# ---------------------------------------------------------------------------
# Protocols for external dependencies
# ---------------------------------------------------------------------------


@runtime_checkable
class PipelineMetricsProvider(Protocol):
    """Protocol for querying pipeline stage metrics."""

    async def get_stage_progress(self) -> list[float]:
        """Return completion fraction per pipeline stage [0, 1].

        Returns:
            List of floats, one per stage. Length may be less than _NUM_STAGES
            if some stages have no data.
        """
        ...

    async def get_queue_lengths(self) -> list[float]:
        """Return raw queue depth per stage.

        Returns:
            List of floats, one per stage.
        """
        ...

    async def get_error_counts(self) -> list[float]:
        """Return recent error count per stage.

        Returns:
            List of floats, one per stage.
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
class PipelineObservationBuilderConfig:
    """Configuration for the pipeline observation builder.

    Attributes:
        min_records: Minimum records required before building observations.
        max_queue_depth: Upper bound for queue depth normalization.
        max_error_count: Upper bound for error count normalization.
        default_progress: Default stage progress if data unavailable.
        default_queue_depth: Default normalized queue depth.
        default_error_count: Default normalized error count.
    """

    min_records: int = _MIN_RECORDS_FOR_OBSERVATION
    max_queue_depth: float = 100.0
    max_error_count: float = 50.0
    default_progress: float = 0.0
    default_queue_depth: float = 0.0
    default_error_count: float = 0.0


# ---------------------------------------------------------------------------
# Data quality report
# ---------------------------------------------------------------------------


@dataclass
class PipelineDataQualityReport:
    """Surface-specific data quality report for pipeline observations.

    Generated before any training claims to ensure transparency about
    data availability and coverage.

    Attributes:
        total_records: Number of historical records available.
        sufficient_data: Whether minimum threshold is met.
        stages_with_data: Number of stages that have progress data.
        stages_total: Total number of tracked stages.
        missing_stages: List of stage indices with no data.
        quality_notes: Human-readable notes about data quality.
    """

    total_records: int = 0
    sufficient_data: bool = False
    stages_with_data: int = 0
    stages_total: int = _NUM_STAGES
    missing_stages: list[int] = field(default_factory=list)
    quality_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Historical context for rehydration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineEpisodeContext:
    """Stored context for rehydrating a historical pipeline observation.

    Contains ONLY data that was available at the time of the pipeline
    decision, ensuring no future leakage.

    Attributes:
        stage_progress: Completion fraction per stage at decision time.
        queue_lengths: Raw queue depths at decision time.
        error_counts: Raw error counts at decision time.
    """

    stage_progress: list[float] = field(default_factory=list)
    queue_lengths: list[float] = field(default_factory=list)
    error_counts: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# OnlinePipelineObservationBuilder
# ---------------------------------------------------------------------------


class OnlinePipelineObservationBuilder:
    """Builds pipeline observations from live platform state.

    Queries pipeline metrics providers to construct a PipelineObservation.
    Returns None if insufficient data is available, rather than fabricating
    observations from insufficient evidence.

    Args:
        metrics_provider: Provides live pipeline stage metrics.
        config: Builder configuration.
    """

    def __init__(
        self,
        metrics_provider: PipelineMetricsProvider,
        config: PipelineObservationBuilderConfig | None = None,
    ) -> None:
        self._provider = metrics_provider
        self._config = config or PipelineObservationBuilderConfig()

    async def build(self) -> PipelineObservation | None:
        """Build a pipeline observation from live platform state.

        Returns:
            A PipelineObservation if sufficient data exists, None otherwise.
        """
        record_count = await self._provider.get_record_count()
        if record_count < self._config.min_records:
            logger.info(
                "Insufficient pipeline data: %d records (need %d). Skipping.",
                record_count,
                self._config.min_records,
            )
            return None

        raw_progress = await self._provider.get_stage_progress()
        raw_queues = await self._provider.get_queue_lengths()
        raw_errors = await self._provider.get_error_counts()

        progress = self._pad_values(raw_progress, self._config.default_progress)
        queues = self._normalize_and_pad(
            raw_queues, self._config.max_queue_depth, self._config.default_queue_depth
        )
        errors = self._normalize_and_pad(
            raw_errors, self._config.max_error_count, self._config.default_error_count
        )

        return PipelineObservation(
            stage_progress=progress,
            queue_lengths_normalized=queues,
            error_counts_normalized=errors,
        )

    async def build_quality_report(self) -> PipelineDataQualityReport:
        """Generate a data quality report for pipeline observations.

        Should be called before any training claims to assess data coverage.

        Returns:
            A PipelineDataQualityReport with coverage details.
        """
        record_count = await self._provider.get_record_count()
        raw_progress = await self._provider.get_stage_progress()

        stages_with_data = sum(1 for p in raw_progress if p > 0.0)
        missing = [
            i
            for i in range(_NUM_STAGES)
            if i >= len(raw_progress) or raw_progress[i] == 0.0
        ]

        notes: list[str] = []
        sufficient = record_count >= self._config.min_records

        if not sufficient:
            notes.append(
                f"Only {record_count} records available "
                f"(minimum: {self._config.min_records})"
            )
        if missing:
            notes.append(f"Stages {missing} have no progress data")
        if stages_with_data == _NUM_STAGES and sufficient:
            notes.append("Full coverage across all pipeline stages")

        return PipelineDataQualityReport(
            total_records=record_count,
            sufficient_data=sufficient,
            stages_with_data=stages_with_data,
            missing_stages=missing,
            quality_notes=notes,
        )

    def _pad_values(self, raw: list[float], default: float) -> list[float]:
        """Ensure exactly _NUM_STAGES values, padding with default."""
        result = [float(v) for v in raw[:_NUM_STAGES]]
        while len(result) < _NUM_STAGES:
            result.append(default)
        return result

    def _normalize_and_pad(
        self, raw: list[float], max_val: float, default: float
    ) -> list[float]:
        """Normalize raw values to [0, 1] and pad to _NUM_STAGES."""
        result: list[float] = []
        for v in raw[:_NUM_STAGES]:
            result.append(min(float(v) / max(max_val, 1.0), 1.0))
        while len(result) < _NUM_STAGES:
            result.append(default)
        return result


# ---------------------------------------------------------------------------
# HistoricalPipelineObservationRehydrator
# ---------------------------------------------------------------------------


class HistoricalPipelineObservationRehydrator:
    """Reconstructs pipeline observations from stored episode context.

    Uses ONLY data available at decision time. No future leakage.

    Args:
        config: Builder configuration.
    """

    def __init__(
        self,
        config: PipelineObservationBuilderConfig | None = None,
    ) -> None:
        self._config = config or PipelineObservationBuilderConfig()

    def rehydrate(self, context: PipelineEpisodeContext) -> PipelineObservation:
        """Reconstruct a PipelineObservation from stored context.

        This method is synchronous and makes NO external queries.

        Args:
            context: Episode context recorded at decision time.

        Returns:
            The PipelineObservation as it was at decision time.
        """
        progress = self._pad_values(
            context.stage_progress, self._config.default_progress
        )
        queues = self._normalize_and_pad(
            context.queue_lengths,
            self._config.max_queue_depth,
            self._config.default_queue_depth,
        )
        errors = self._normalize_and_pad(
            context.error_counts,
            self._config.max_error_count,
            self._config.default_error_count,
        )

        return PipelineObservation(
            stage_progress=progress,
            queue_lengths_normalized=queues,
            error_counts_normalized=errors,
        )

    def rehydrate_from_raw(
        self, episode_row: dict[str, Any]
    ) -> PipelineObservation | None:
        """Reconstruct observation from a raw episode database row.

        Args:
            episode_row: Dictionary-like row from stored episodes.

        Returns:
            PipelineObservation, or None if the row lacks sufficient context.
        """
        # Fast path: use pre-computed observation vector
        obs_raw = episode_row.get("observation")
        if isinstance(obs_raw, list) and len(obs_raw) == PipelineObservation.DIMS:
            try:
                import torch

                t = torch.tensor(obs_raw, dtype=torch.float32)
                return PipelineObservation.from_tensor(t)
            except (ValueError, TypeError):
                logger.debug(
                    "Pre-computed pipeline observation invalid, falling back to context"
                )

        # Slow path: reconstruct from stored context
        context_raw = episode_row.get("context")
        if not isinstance(context_raw, dict):
            return None

        try:
            context = PipelineEpisodeContext(
                stage_progress=context_raw.get("stage_progress", []),
                queue_lengths=context_raw.get("queue_lengths", []),
                error_counts=context_raw.get("error_counts", []),
            )
            return self.rehydrate(context)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Cannot rehydrate pipeline observation: %s", exc)
            return None

    def _pad_values(self, raw: list[float], default: float) -> list[float]:
        """Ensure exactly _NUM_STAGES values."""
        result = [float(v) for v in raw[:_NUM_STAGES]]
        while len(result) < _NUM_STAGES:
            result.append(default)
        return result

    def _normalize_and_pad(
        self, raw: list[float], max_val: float, default: float
    ) -> list[float]:
        """Normalize and pad to _NUM_STAGES."""
        result: list[float] = []
        for v in raw[:_NUM_STAGES]:
            result.append(min(float(v) / max(max_val, 1.0), 1.0))
        while len(result) < _NUM_STAGES:
            result.append(default)
        return result
