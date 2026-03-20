# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Typed observation spaces for RL training.

Each observation model defines a fixed-dimension vector representation
with ``to_tensor()`` / ``from_tensor()`` round-trip methods suitable for
feeding into policy networks.
"""

from __future__ import annotations

import math
from typing import ClassVar, Self

import torch
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# RoutingObservation  (30 dims)
# ---------------------------------------------------------------------------

_TASK_TYPES: list[str] = [
    "code_gen",
    "code_review",
    "embedding",
    "reasoning",
    "routing",
    "summarization",
    "test_gen",
    "general",
]

_NUM_ENDPOINTS: int = 4  # Qwen3-30B, Qwen3-14B, DeepSeek-R1, Embedding
_HEALTH_FEATURES_PER_ENDPOINT: int = (
    4  # latency_p50, error_rate, circuit_state, queue_depth
)


class EndpointHealth(BaseModel, frozen=True):
    """Per-endpoint health snapshot (4 dims)."""

    latency_p50: float = Field(description="Median latency in seconds, normalised")
    error_rate: float = Field(description="Error rate [0, 1]")
    circuit_state: float = Field(
        description="Circuit-breaker state: 0.0=closed, 0.5=half-open, 1.0=open"
    )
    queue_depth: float = Field(description="Normalised pending-request queue depth")


class RoutingObservation(BaseModel, frozen=True):
    """Observation for the LLM routing decision (30 dims total).

    Layout::

        [0..8)   task_type_onehot              8 dims
        [8..9)   estimated_token_count_norm     1 dim
        [9..25)  per_endpoint_health           16 dims  (4 endpoints x 4 features)
        [25..29) historical_success_rate        4 dims  (rolling 7-day per endpoint)
        [29..31) time_of_day_encoding           2 dims  (sin, cos)

    Total = 8 + 1 + 16 + 4 + 2 = 31  (corrected from ticket sketch; sin/cos
    encoding adds a 31st dim).

    .. note::
       The ticket originally stated 30 dims. The actual count is **31** because
       ``time_of_day_encoding`` requires two components (sin + cos) which,
       combined with the other groups, yields 31. We keep the documented field
       semantics and let the tensor shape be authoritative.
    """

    DIMS: ClassVar[int] = 31  # class-level constant for external use

    task_type_onehot: list[float] = Field(
        min_length=len(_TASK_TYPES),
        max_length=len(_TASK_TYPES),
        description="One-hot encoding of the task type (8 dims)",
    )
    estimated_token_count_normalized: float = Field(
        description="Token count normalised to [0, 1] range"
    )
    per_endpoint_health: list[EndpointHealth] = Field(
        min_length=_NUM_ENDPOINTS,
        max_length=_NUM_ENDPOINTS,
        description="Health snapshot per LLM endpoint (4 endpoints)",
    )
    historical_success_rate: list[float] = Field(
        min_length=_NUM_ENDPOINTS,
        max_length=_NUM_ENDPOINTS,
        description="Rolling 7-day success rate per endpoint [0, 1]",
    )
    time_of_day_sin: float = Field(description="sin(2*pi*hour/24)")
    time_of_day_cos: float = Field(description="cos(2*pi*hour/24)")

    # -- tensor helpers -----------------------------------------------------

    def to_tensor(self) -> torch.Tensor:
        """Flatten observation into a 1-D float tensor of length ``DIMS``."""
        values: list[float] = []
        values.extend(self.task_type_onehot)
        values.append(self.estimated_token_count_normalized)
        for ep in self.per_endpoint_health:
            values.extend(
                [ep.latency_p50, ep.error_rate, ep.circuit_state, ep.queue_depth]
            )
        values.extend(self.historical_success_rate)
        values.extend([self.time_of_day_sin, self.time_of_day_cos])
        return torch.tensor(values, dtype=torch.float32)

    @classmethod
    def from_tensor(cls, t: torch.Tensor) -> Self:
        """Reconstruct a ``RoutingObservation`` from a flat tensor."""
        v = t.tolist()
        if len(v) != cls.DIMS:
            msg = f"Expected tensor of length {cls.DIMS}, got {len(v)}"
            raise ValueError(msg)
        idx = 0
        task_type_onehot = v[idx : idx + len(_TASK_TYPES)]
        idx += len(_TASK_TYPES)

        estimated_token_count_normalized = v[idx]
        idx += 1

        endpoints: list[EndpointHealth] = []
        for _ in range(_NUM_ENDPOINTS):
            endpoints.append(
                EndpointHealth(
                    latency_p50=v[idx],
                    error_rate=v[idx + 1],
                    circuit_state=v[idx + 2],
                    queue_depth=v[idx + 3],
                )
            )
            idx += _HEALTH_FEATURES_PER_ENDPOINT

        historical_success_rate = v[idx : idx + _NUM_ENDPOINTS]
        idx += _NUM_ENDPOINTS

        time_sin = v[idx]
        time_cos = v[idx + 1]

        return cls(
            task_type_onehot=task_type_onehot,
            estimated_token_count_normalized=estimated_token_count_normalized,
            per_endpoint_health=endpoints,
            historical_success_rate=historical_success_rate,
            time_of_day_sin=time_sin,
            time_of_day_cos=time_cos,
        )


# ---------------------------------------------------------------------------
# PipelineObservation  (~15 dims) — exploratory
# ---------------------------------------------------------------------------


class PipelineObservation(BaseModel, frozen=True):
    """Observation for pipeline orchestration decisions (15 dims).

    Exploratory — defined for future training but not expected to drive
    production decisions initially.
    """

    DIMS: ClassVar[int] = 15

    stage_progress: list[float] = Field(
        min_length=5,
        max_length=5,
        description="Completion fraction per pipeline stage [0, 1] (5 dims)",
    )
    queue_lengths_normalized: list[float] = Field(
        min_length=5,
        max_length=5,
        description="Normalised queue depth per stage (5 dims)",
    )
    error_counts_normalized: list[float] = Field(
        min_length=5,
        max_length=5,
        description="Normalised recent error count per stage (5 dims)",
    )

    def to_tensor(self) -> torch.Tensor:
        values: list[float] = []
        values.extend(self.stage_progress)
        values.extend(self.queue_lengths_normalized)
        values.extend(self.error_counts_normalized)
        return torch.tensor(values, dtype=torch.float32)

    @classmethod
    def from_tensor(cls, t: torch.Tensor) -> Self:
        v = t.tolist()
        if len(v) != cls.DIMS:
            msg = f"Expected tensor of length {cls.DIMS}, got {len(v)}"
            raise ValueError(msg)
        return cls(
            stage_progress=v[0:5],
            queue_lengths_normalized=v[5:10],
            error_counts_normalized=v[10:15],
        )


# ---------------------------------------------------------------------------
# TeamObservation  (~10 dims) — exploratory
# ---------------------------------------------------------------------------


class TeamObservation(BaseModel, frozen=True):
    """Observation for team/agent coordination decisions (10 dims).

    Exploratory — defined for future training.
    """

    DIMS: ClassVar[int] = 10

    agent_utilization: list[float] = Field(
        min_length=5,
        max_length=5,
        description="Utilisation fraction per agent slot [0, 1] (5 dims)",
    )
    task_complexity_normalized: float = Field(
        description="Normalised task complexity score"
    )
    pending_tasks_normalized: float = Field(
        description="Normalised count of pending tasks"
    )
    time_pressure: float = Field(
        description="Time pressure signal [0=relaxed, 1=urgent]"
    )
    success_rate_rolling: float = Field(description="Rolling team success rate [0, 1]")
    coordination_overhead: float = Field(
        description="Normalised inter-agent communication overhead"
    )

    def to_tensor(self) -> torch.Tensor:
        values: list[float] = []
        values.extend(self.agent_utilization)
        values.extend(
            [
                self.task_complexity_normalized,
                self.pending_tasks_normalized,
                self.time_pressure,
                self.success_rate_rolling,
                self.coordination_overhead,
            ]
        )
        return torch.tensor(values, dtype=torch.float32)

    @classmethod
    def from_tensor(cls, t: torch.Tensor) -> Self:
        v = t.tolist()
        if len(v) != cls.DIMS:
            msg = f"Expected tensor of length {cls.DIMS}, got {len(v)}"
            raise ValueError(msg)
        return cls(
            agent_utilization=v[0:5],
            task_complexity_normalized=v[5],
            pending_tasks_normalized=v[6],
            time_pressure=v[7],
            success_rate_rolling=v[8],
            coordination_overhead=v[9],
        )


# ---------------------------------------------------------------------------
# Helper: build a RoutingObservation from raw inputs
# ---------------------------------------------------------------------------


def make_routing_observation(
    *,
    task_type: str,
    estimated_tokens: int,
    max_tokens: int,
    endpoint_health: list[EndpointHealth],
    historical_success_rates: list[float],
    hour_of_day: float,
) -> RoutingObservation:
    """Convenience factory that handles one-hot encoding and normalisation."""
    onehot = [1.0 if t == task_type else 0.0 for t in _TASK_TYPES]
    token_norm = min(estimated_tokens / max(max_tokens, 1), 1.0)
    angle = 2.0 * math.pi * hour_of_day / 24.0
    return RoutingObservation(
        task_type_onehot=onehot,
        estimated_token_count_normalized=token_norm,
        per_endpoint_health=endpoint_health,
        historical_success_rate=historical_success_rates,
        time_of_day_sin=math.sin(angle),
        time_of_day_cos=math.cos(angle),
    )
