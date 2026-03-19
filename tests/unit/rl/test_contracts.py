# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Tests for RL observation / action / reward contracts."""

from __future__ import annotations

import math

import pytest
import torch

from omniintelligence.rl.contracts.actions import NUM_ROUTING_ACTIONS, RoutingAction
from omniintelligence.rl.contracts.observations import (
    EndpointHealth,
    PipelineObservation,
    RoutingObservation,
    TeamObservation,
    make_routing_observation,
)
from omniintelligence.rl.contracts.rewards import RewardSignal

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_endpoint_health() -> list[EndpointHealth]:
    return [
        EndpointHealth(
            latency_p50=0.1 * (i + 1),
            error_rate=0.01 * (i + 1),
            circuit_state=0.0,
            queue_depth=0.05 * (i + 1),
        )
        for i in range(4)
    ]


def _sample_routing_observation() -> RoutingObservation:
    hour = 14.5
    angle = 2.0 * math.pi * hour / 24.0
    return RoutingObservation(
        task_type_onehot=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
        estimated_token_count_normalized=0.42,
        per_endpoint_health=_sample_endpoint_health(),
        historical_success_rate=[0.95, 0.88, 0.92, 0.99],
        time_of_day_sin=math.sin(angle),
        time_of_day_cos=math.cos(angle),
    )


# ---------------------------------------------------------------------------
# RoutingObservation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoutingObservation:
    def test_tensor_dimensionality(self) -> None:
        obs = _sample_routing_observation()
        t = obs.to_tensor()
        assert t.shape == (RoutingObservation.DIMS,)
        assert t.dtype == torch.float32

    def test_round_trip(self) -> None:
        obs = _sample_routing_observation()
        t = obs.to_tensor()
        restored = RoutingObservation.from_tensor(t)
        assert torch.allclose(t, restored.to_tensor(), atol=1e-6)

    def test_round_trip_preserves_values(self) -> None:
        obs = _sample_routing_observation()
        t = obs.to_tensor()
        restored = RoutingObservation.from_tensor(t)
        assert restored.task_type_onehot == pytest.approx(
            obs.task_type_onehot, abs=1e-6
        )
        assert restored.estimated_token_count_normalized == pytest.approx(
            obs.estimated_token_count_normalized, abs=1e-6
        )
        assert restored.historical_success_rate == pytest.approx(
            obs.historical_success_rate, abs=1e-6
        )
        assert restored.time_of_day_sin == pytest.approx(obs.time_of_day_sin, abs=1e-6)
        assert restored.time_of_day_cos == pytest.approx(obs.time_of_day_cos, abs=1e-6)

    def test_from_tensor_rejects_wrong_size(self) -> None:
        with pytest.raises(ValueError, match="Expected tensor of length"):
            RoutingObservation.from_tensor(torch.zeros(5))

    def test_make_routing_observation_helper(self) -> None:
        obs = make_routing_observation(
            task_type="code_gen",
            estimated_tokens=2000,
            max_tokens=8000,
            endpoint_health=_sample_endpoint_health(),
            historical_success_rates=[0.95, 0.88, 0.92, 0.99],
            hour_of_day=14.5,
        )
        assert obs.task_type_onehot[0] == 1.0
        assert sum(obs.task_type_onehot) == 1.0
        assert obs.estimated_token_count_normalized == pytest.approx(0.25, abs=1e-6)
        assert obs.to_tensor().shape == (RoutingObservation.DIMS,)


# ---------------------------------------------------------------------------
# PipelineObservation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineObservation:
    def test_tensor_dimensionality(self) -> None:
        obs = PipelineObservation(
            stage_progress=[0.1, 0.2, 0.3, 0.4, 0.5],
            queue_lengths_normalized=[0.0, 0.1, 0.2, 0.3, 0.4],
            error_counts_normalized=[0.0, 0.0, 0.01, 0.0, 0.0],
        )
        t = obs.to_tensor()
        assert t.shape == (PipelineObservation.DIMS,)

    def test_round_trip(self) -> None:
        obs = PipelineObservation(
            stage_progress=[0.1, 0.2, 0.3, 0.4, 0.5],
            queue_lengths_normalized=[0.0, 0.1, 0.2, 0.3, 0.4],
            error_counts_normalized=[0.0, 0.0, 0.01, 0.0, 0.0],
        )
        t = obs.to_tensor()
        restored = PipelineObservation.from_tensor(t)
        assert torch.allclose(t, restored.to_tensor(), atol=1e-6)


# ---------------------------------------------------------------------------
# TeamObservation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTeamObservation:
    def test_tensor_dimensionality(self) -> None:
        obs = TeamObservation(
            agent_utilization=[0.5, 0.6, 0.7, 0.8, 0.9],
            task_complexity_normalized=0.6,
            pending_tasks_normalized=0.3,
            time_pressure=0.4,
            success_rate_rolling=0.92,
            coordination_overhead=0.15,
        )
        t = obs.to_tensor()
        assert t.shape == (TeamObservation.DIMS,)

    def test_round_trip(self) -> None:
        obs = TeamObservation(
            agent_utilization=[0.5, 0.6, 0.7, 0.8, 0.9],
            task_complexity_normalized=0.6,
            pending_tasks_normalized=0.3,
            time_pressure=0.4,
            success_rate_rolling=0.92,
            coordination_overhead=0.15,
        )
        t = obs.to_tensor()
        restored = TeamObservation.from_tensor(t)
        assert torch.allclose(t, restored.to_tensor(), atol=1e-6)


# ---------------------------------------------------------------------------
# RoutingAction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoutingAction:
    def test_to_index_values(self) -> None:
        assert RoutingAction.QWEN3_30B.to_index() == 0
        assert RoutingAction.QWEN3_14B.to_index() == 1
        assert RoutingAction.DEEPSEEK_R1.to_index() == 2
        assert RoutingAction.EMBEDDING.to_index() == 3

    def test_from_index_round_trip(self) -> None:
        for action in RoutingAction:
            assert RoutingAction.from_index(action.to_index()) == action

    def test_from_index_invalid(self) -> None:
        with pytest.raises(ValueError):
            RoutingAction.from_index(99)

    def test_num_actions(self) -> None:
        assert len(RoutingAction) == NUM_ROUTING_ACTIONS
        assert NUM_ROUTING_ACTIONS == 4


# ---------------------------------------------------------------------------
# RewardSignal
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRewardSignal:
    def test_to_scalar_determinism(self) -> None:
        reward = RewardSignal(
            latency_reward=0.8,
            success_reward=1.0,
            cost_reward=-0.2,
            quality_reward=0.6,
        )
        results = [reward.to_scalar() for _ in range(100)]
        assert all(r == results[0] for r in results)

    def test_to_scalar_default_weights(self) -> None:
        reward = RewardSignal(
            latency_reward=1.0,
            success_reward=1.0,
            cost_reward=1.0,
            quality_reward=1.0,
        )
        assert reward.to_scalar() == pytest.approx(1.0, abs=1e-9)

    def test_to_scalar_custom_weights(self) -> None:
        reward = RewardSignal(
            latency_reward=1.0,
            success_reward=0.0,
            cost_reward=0.0,
            quality_reward=0.0,
            weight_latency=1.0,
            weight_success=0.0,
            weight_cost=0.0,
            weight_quality=0.0,
        )
        assert reward.to_scalar() == pytest.approx(1.0, abs=1e-9)

    def test_to_scalar_zero_rewards(self) -> None:
        reward = RewardSignal(
            latency_reward=0.0,
            success_reward=0.0,
            cost_reward=0.0,
            quality_reward=0.0,
        )
        assert reward.to_scalar() == pytest.approx(0.0, abs=1e-9)

    def test_frozen(self) -> None:
        reward = RewardSignal(
            latency_reward=0.5,
            success_reward=0.5,
            cost_reward=0.5,
            quality_reward=0.5,
        )
        with pytest.raises(Exception):  # noqa: B017
            reward.latency_reward = 1.0  # type: ignore[misc]
