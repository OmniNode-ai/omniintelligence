# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for team observation builder.

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

from omniintelligence.rl.builders.team_observation_builder import (
    _NUM_AGENT_SLOTS,
    HistoricalTeamObservationRehydrator,
    OnlineTeamObservationBuilder,
    TeamEpisodeContext,
    TeamObservationBuilderConfig,
)
from omniintelligence.rl.contracts.observations import TeamObservation

# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------


class MockTeamMetricsProvider:
    """Mock team metrics provider for testing."""

    def __init__(
        self,
        *,
        record_count: int = 100,
        agent_utilization: list[float] | None = None,
        task_complexity: float = 5.0,
        pending_task_count: int = 10,
        time_pressure: float = 0.4,
        success_rate: float = 0.85,
        coordination_overhead: float = 20.0,
    ) -> None:
        self._record_count = record_count
        self._utilization = agent_utilization or [0.8, 0.5, 0.3, 0.9, 0.2]
        self._complexity = task_complexity
        self._pending = pending_task_count
        self._pressure = time_pressure
        self._success = success_rate
        self._overhead = coordination_overhead

    async def get_agent_utilization(self) -> list[float]:
        return self._utilization

    async def get_task_complexity(self) -> float:
        return self._complexity

    async def get_pending_task_count(self) -> int:
        return self._pending

    async def get_time_pressure(self) -> float:
        return self._pressure

    async def get_success_rate(self) -> float:
        return self._success

    async def get_coordination_overhead(self) -> float:
        return self._overhead

    async def get_record_count(self) -> int:
        return self._record_count


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def default_config() -> TeamObservationBuilderConfig:
    return TeamObservationBuilderConfig()


@pytest.fixture()
def rehydrator(
    default_config: TeamObservationBuilderConfig,
) -> HistoricalTeamObservationRehydrator:
    return HistoricalTeamObservationRehydrator(config=default_config)


@pytest.fixture()
def sample_context() -> TeamEpisodeContext:
    """A complete episode context with realistic values."""
    return TeamEpisodeContext(
        agent_utilization=[0.8, 0.5, 0.3, 0.9, 0.2],
        task_complexity=5.0,
        pending_task_count=10,
        time_pressure=0.4,
        success_rate=0.85,
        coordination_overhead=20.0,
    )


# ---------------------------------------------------------------------------
# Test: Online builder
# ---------------------------------------------------------------------------


class TestOnlineTeamBuilder:
    """Test online team observation builder."""

    @pytest.mark.asyncio()
    async def test_produces_correct_dims(self) -> None:
        """Online builder produces observation with correct dimensions."""
        builder = OnlineTeamObservationBuilder(
            metrics_provider=MockTeamMetricsProvider(),
        )
        obs = await builder.build()
        assert obs is not None
        tensor = obs.to_tensor()
        assert tensor.shape == (TeamObservation.DIMS,)

    @pytest.mark.asyncio()
    async def test_returns_none_insufficient_data(self) -> None:
        """Online builder returns None when insufficient records exist."""
        builder = OnlineTeamObservationBuilder(
            metrics_provider=MockTeamMetricsProvider(record_count=3),
        )
        obs = await builder.build()
        assert obs is None

    @pytest.mark.asyncio()
    async def test_normalizes_complexity(self) -> None:
        """Task complexity is normalized to [0, 1]."""
        builder = OnlineTeamObservationBuilder(
            metrics_provider=MockTeamMetricsProvider(task_complexity=15.0),
        )
        obs = await builder.build()
        assert obs is not None
        assert 0.0 <= obs.task_complexity_normalized <= 1.0

    @pytest.mark.asyncio()
    async def test_clamps_utilization(self) -> None:
        """Agent utilization is clamped to [0, 1]."""
        builder = OnlineTeamObservationBuilder(
            metrics_provider=MockTeamMetricsProvider(
                agent_utilization=[1.5, -0.1, 0.5, 0.7, 0.3],
            ),
        )
        obs = await builder.build()
        assert obs is not None
        for u in obs.agent_utilization:
            assert 0.0 <= u <= 1.0

    @pytest.mark.asyncio()
    async def test_pads_short_utilization(self) -> None:
        """Builder pads utilization shorter than _NUM_AGENT_SLOTS."""
        builder = OnlineTeamObservationBuilder(
            metrics_provider=MockTeamMetricsProvider(
                agent_utilization=[0.5, 0.3],
            ),
        )
        obs = await builder.build()
        assert obs is not None
        assert len(obs.agent_utilization) == _NUM_AGENT_SLOTS


# ---------------------------------------------------------------------------
# Test: Data quality report
# ---------------------------------------------------------------------------


class TestTeamDataQualityReport:
    """Test data quality report generation."""

    @pytest.mark.asyncio()
    async def test_sufficient_data_report(self) -> None:
        """Report reflects sufficient data correctly."""
        builder = OnlineTeamObservationBuilder(
            metrics_provider=MockTeamMetricsProvider(record_count=100),
        )
        report = await builder.build_quality_report()
        assert report.sufficient_data is True
        assert report.total_records == 100

    @pytest.mark.asyncio()
    async def test_insufficient_data_report(self) -> None:
        """Report reflects insufficient data correctly."""
        builder = OnlineTeamObservationBuilder(
            metrics_provider=MockTeamMetricsProvider(record_count=5),
        )
        report = await builder.build_quality_report()
        assert report.sufficient_data is False
        assert any("Only 5 records" in n for n in report.quality_notes)

    @pytest.mark.asyncio()
    async def test_partial_agent_coverage(self) -> None:
        """Report identifies partial agent coverage."""
        builder = OnlineTeamObservationBuilder(
            metrics_provider=MockTeamMetricsProvider(
                agent_utilization=[0.5, 0.0, 0.3, 0.0, 0.0],
            ),
        )
        report = await builder.build_quality_report()
        assert report.agents_with_data == 2
        assert any("2/5" in n for n in report.quality_notes)

    @pytest.mark.asyncio()
    async def test_complexity_data_detection(self) -> None:
        """Report detects presence of complexity data."""
        builder = OnlineTeamObservationBuilder(
            metrics_provider=MockTeamMetricsProvider(task_complexity=5.0),
        )
        report = await builder.build_quality_report()
        assert report.has_complexity_data is True

    @pytest.mark.asyncio()
    async def test_no_complexity_data_detection(self) -> None:
        """Report detects absence of complexity data."""
        builder = OnlineTeamObservationBuilder(
            metrics_provider=MockTeamMetricsProvider(task_complexity=0.0),
        )
        report = await builder.build_quality_report()
        assert report.has_complexity_data is False


# ---------------------------------------------------------------------------
# Test: Historical rehydrator
# ---------------------------------------------------------------------------


class TestTeamRehydrator:
    """Test historical team observation rehydrator."""

    def test_rehydration_produces_correct_dims(
        self,
        rehydrator: HistoricalTeamObservationRehydrator,
        sample_context: TeamEpisodeContext,
    ) -> None:
        """Rehydrated observation has correct dimensions."""
        obs = rehydrator.rehydrate(sample_context)
        tensor = obs.to_tensor()
        assert tensor.shape == (TeamObservation.DIMS,)

    def test_rehydration_is_deterministic(
        self,
        rehydrator: HistoricalTeamObservationRehydrator,
        sample_context: TeamEpisodeContext,
    ) -> None:
        """Same context produces identical observations."""
        obs1 = rehydrator.rehydrate(sample_context)
        obs2 = rehydrator.rehydrate(sample_context)
        assert torch.equal(obs1.to_tensor(), obs2.to_tensor())

    def test_tensor_roundtrip(
        self,
        rehydrator: HistoricalTeamObservationRehydrator,
        sample_context: TeamEpisodeContext,
    ) -> None:
        """Observation survives tensor roundtrip."""
        obs = rehydrator.rehydrate(sample_context)
        tensor = obs.to_tensor()
        recovered = TeamObservation.from_tensor(tensor)
        # Use approximate comparison due to float32 precision
        assert torch.allclose(recovered.to_tensor(), obs.to_tensor(), atol=1e-5)

    def test_rehydrate_from_raw_with_precomputed(
        self,
        rehydrator: HistoricalTeamObservationRehydrator,
        sample_context: TeamEpisodeContext,
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
        rehydrator: HistoricalTeamObservationRehydrator,
    ) -> None:
        """Observation can be rehydrated from stored context dict."""
        row: dict[str, object] = {
            "context": {
                "agent_utilization": [0.5, 0.3, 0.7, 0.1, 0.9],
                "task_complexity": 3.0,
                "pending_task_count": 5,
                "time_pressure": 0.6,
                "success_rate": 0.9,
                "coordination_overhead": 15.0,
            }
        }
        result = rehydrator.rehydrate_from_raw(row)
        assert result is not None
        assert result.to_tensor().shape == (TeamObservation.DIMS,)

    def test_rehydrate_from_raw_returns_none_on_missing_context(
        self,
        rehydrator: HistoricalTeamObservationRehydrator,
    ) -> None:
        """Rehydration returns None when context is missing."""
        result = rehydrator.rehydrate_from_raw({})
        assert result is None

    def test_empty_context_uses_defaults(
        self,
        rehydrator: HistoricalTeamObservationRehydrator,
    ) -> None:
        """Empty context produces observation with default values."""
        context = TeamEpisodeContext()
        obs = rehydrator.rehydrate(context)
        assert obs.to_tensor().shape == (TeamObservation.DIMS,)
