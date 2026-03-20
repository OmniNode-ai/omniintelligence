# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for pipeline observation builder.

Tests cover:
    1. Online builder produces correct dimensions
    2. Online builder returns None when insufficient data
    3. Historical rehydrator round-trips correctly
    4. Data quality report accuracy
    5. Rehydration from raw episode rows

Ticket: OMN-5572
"""

from __future__ import annotations

import pytest
import torch

from omniintelligence.rl.builders.pipeline_observation_builder import (
    _NUM_STAGES,
    HistoricalPipelineObservationRehydrator,
    OnlinePipelineObservationBuilder,
    PipelineEpisodeContext,
    PipelineObservationBuilderConfig,
)
from omniintelligence.rl.contracts.observations import PipelineObservation

# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------


class MockPipelineMetricsProvider:
    """Mock pipeline metrics provider for testing."""

    def __init__(
        self,
        *,
        record_count: int = 100,
        stage_progress: list[float] | None = None,
        queue_lengths: list[float] | None = None,
        error_counts: list[float] | None = None,
    ) -> None:
        self._record_count = record_count
        self._progress = stage_progress or [0.8, 0.6, 0.4, 0.2, 0.1]
        self._queues = queue_lengths or [10.0, 20.0, 30.0, 5.0, 15.0]
        self._errors = error_counts or [1.0, 3.0, 0.0, 2.0, 1.0]

    async def get_stage_progress(self) -> list[float]:
        return self._progress

    async def get_queue_lengths(self) -> list[float]:
        return self._queues

    async def get_error_counts(self) -> list[float]:
        return self._errors

    async def get_record_count(self) -> int:
        return self._record_count


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def default_config() -> PipelineObservationBuilderConfig:
    return PipelineObservationBuilderConfig()


@pytest.fixture()
def rehydrator(
    default_config: PipelineObservationBuilderConfig,
) -> HistoricalPipelineObservationRehydrator:
    return HistoricalPipelineObservationRehydrator(config=default_config)


@pytest.fixture()
def sample_context() -> PipelineEpisodeContext:
    """A complete episode context with realistic values."""
    return PipelineEpisodeContext(
        stage_progress=[0.8, 0.6, 0.4, 0.2, 0.1],
        queue_lengths=[10.0, 20.0, 30.0, 5.0, 15.0],
        error_counts=[1.0, 3.0, 0.0, 2.0, 1.0],
    )


# ---------------------------------------------------------------------------
# Test: Online builder
# ---------------------------------------------------------------------------


class TestOnlinePipelineBuilder:
    """Test online pipeline observation builder."""

    @pytest.mark.asyncio()
    async def test_produces_correct_dims(self) -> None:
        """Online builder produces observation with correct dimensions."""
        builder = OnlinePipelineObservationBuilder(
            metrics_provider=MockPipelineMetricsProvider(),
        )
        obs = await builder.build()
        assert obs is not None
        tensor = obs.to_tensor()
        assert tensor.shape == (PipelineObservation.DIMS,)

    @pytest.mark.asyncio()
    async def test_returns_none_insufficient_data(self) -> None:
        """Online builder returns None when insufficient records exist."""
        builder = OnlinePipelineObservationBuilder(
            metrics_provider=MockPipelineMetricsProvider(record_count=3),
        )
        obs = await builder.build()
        assert obs is None

    @pytest.mark.asyncio()
    async def test_normalizes_queue_lengths(self) -> None:
        """Queue lengths are normalized to [0, 1]."""
        builder = OnlinePipelineObservationBuilder(
            metrics_provider=MockPipelineMetricsProvider(
                queue_lengths=[50.0, 100.0, 150.0, 0.0, 25.0],
            ),
        )
        obs = await builder.build()
        assert obs is not None
        for q in obs.queue_lengths_normalized:
            assert 0.0 <= q <= 1.0

    @pytest.mark.asyncio()
    async def test_pads_short_data(self) -> None:
        """Builder pads data shorter than _NUM_STAGES."""
        builder = OnlinePipelineObservationBuilder(
            metrics_provider=MockPipelineMetricsProvider(
                stage_progress=[0.5, 0.3],
                queue_lengths=[10.0],
                error_counts=[],
            ),
        )
        obs = await builder.build()
        assert obs is not None
        assert len(obs.stage_progress) == _NUM_STAGES
        assert len(obs.queue_lengths_normalized) == _NUM_STAGES
        assert len(obs.error_counts_normalized) == _NUM_STAGES


# ---------------------------------------------------------------------------
# Test: Data quality report
# ---------------------------------------------------------------------------


class TestPipelineDataQualityReport:
    """Test data quality report generation."""

    @pytest.mark.asyncio()
    async def test_sufficient_data_report(self) -> None:
        """Report reflects sufficient data correctly."""
        builder = OnlinePipelineObservationBuilder(
            metrics_provider=MockPipelineMetricsProvider(record_count=100),
        )
        report = await builder.build_quality_report()
        assert report.sufficient_data is True
        assert report.total_records == 100

    @pytest.mark.asyncio()
    async def test_insufficient_data_report(self) -> None:
        """Report reflects insufficient data correctly."""
        builder = OnlinePipelineObservationBuilder(
            metrics_provider=MockPipelineMetricsProvider(record_count=5),
        )
        report = await builder.build_quality_report()
        assert report.sufficient_data is False
        assert any("Only 5 records" in n for n in report.quality_notes)

    @pytest.mark.asyncio()
    async def test_missing_stages_reported(self) -> None:
        """Report identifies stages with no data."""
        builder = OnlinePipelineObservationBuilder(
            metrics_provider=MockPipelineMetricsProvider(
                stage_progress=[0.5, 0.0, 0.3, 0.0, 0.0],
            ),
        )
        report = await builder.build_quality_report()
        assert 1 in report.missing_stages
        assert 3 in report.missing_stages
        assert 4 in report.missing_stages


# ---------------------------------------------------------------------------
# Test: Historical rehydrator
# ---------------------------------------------------------------------------


class TestPipelineRehydrator:
    """Test historical pipeline observation rehydrator."""

    def test_rehydration_produces_correct_dims(
        self,
        rehydrator: HistoricalPipelineObservationRehydrator,
        sample_context: PipelineEpisodeContext,
    ) -> None:
        """Rehydrated observation has correct dimensions."""
        obs = rehydrator.rehydrate(sample_context)
        tensor = obs.to_tensor()
        assert tensor.shape == (PipelineObservation.DIMS,)

    def test_rehydration_is_deterministic(
        self,
        rehydrator: HistoricalPipelineObservationRehydrator,
        sample_context: PipelineEpisodeContext,
    ) -> None:
        """Same context produces identical observations."""
        obs1 = rehydrator.rehydrate(sample_context)
        obs2 = rehydrator.rehydrate(sample_context)
        assert torch.equal(obs1.to_tensor(), obs2.to_tensor())

    def test_tensor_roundtrip(
        self,
        rehydrator: HistoricalPipelineObservationRehydrator,
        sample_context: PipelineEpisodeContext,
    ) -> None:
        """Observation survives tensor roundtrip."""
        obs = rehydrator.rehydrate(sample_context)
        tensor = obs.to_tensor()
        recovered = PipelineObservation.from_tensor(tensor)
        # Use approximate comparison due to float32 precision
        assert torch.allclose(recovered.to_tensor(), obs.to_tensor(), atol=1e-5)

    def test_rehydrate_from_raw_with_precomputed(
        self,
        rehydrator: HistoricalPipelineObservationRehydrator,
        sample_context: PipelineEpisodeContext,
    ) -> None:
        """Pre-computed observation vectors are used directly."""
        expected_obs = rehydrator.rehydrate(sample_context)
        raw_vector = expected_obs.to_tensor().tolist()

        row = {"observation": raw_vector}
        result = rehydrator.rehydrate_from_raw(row)

        assert result is not None
        assert torch.allclose(
            result.to_tensor(),
            expected_obs.to_tensor(),
            atol=1e-5,
        )

    def test_rehydrate_from_raw_with_context(
        self,
        rehydrator: HistoricalPipelineObservationRehydrator,
    ) -> None:
        """Observation can be rehydrated from stored context dict."""
        row: dict[str, object] = {
            "context": {
                "stage_progress": [0.5, 0.3, 0.7, 0.1, 0.9],
                "queue_lengths": [5.0, 10.0, 15.0, 20.0, 25.0],
                "error_counts": [0.0, 1.0, 2.0, 0.0, 3.0],
            }
        }
        result = rehydrator.rehydrate_from_raw(row)
        assert result is not None
        assert result.to_tensor().shape == (PipelineObservation.DIMS,)

    def test_rehydrate_from_raw_returns_none_on_missing_context(
        self,
        rehydrator: HistoricalPipelineObservationRehydrator,
    ) -> None:
        """Rehydration returns None when context is missing."""
        result = rehydrator.rehydrate_from_raw({})
        assert result is None

    def test_empty_context_uses_defaults(
        self,
        rehydrator: HistoricalPipelineObservationRehydrator,
    ) -> None:
        """Empty context produces observation with default values."""
        context = PipelineEpisodeContext()
        obs = rehydrator.rehydrate(context)
        assert obs.to_tensor().shape == (PipelineObservation.DIMS,)
        # All values should be defaults (0.0)
        assert all(v == 0.0 for v in obs.stage_progress)
