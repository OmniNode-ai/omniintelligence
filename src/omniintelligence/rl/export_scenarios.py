# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Scenario grid generator for policy-to-Bifrost fidelity checking.

Generates a comprehensive grid of ``RoutingObservation`` instances covering
normal, degraded, and edge-case operating states.  The grid intentionally
oversamples degraded and high-impact states so the fidelity check catches
policy--config divergence in the conditions that matter most.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import ClassVar

from omniintelligence.rl.contracts.observations import (
    _NUM_ENDPOINTS,
    _TASK_TYPES,
    EndpointHealth,
    RoutingObservation,
    make_routing_observation,
)


@dataclass(frozen=True)
class Scenario:
    """A single evaluation scenario with associated metadata.

    Attributes:
        observation: The observation to feed into the policy.
        bucket: Human-readable scenario bucket for fidelity reporting.
        description: Short description of the operating conditions.
    """

    observation: RoutingObservation
    bucket: str
    description: str


# ---------------------------------------------------------------------------
# Bucket definitions
# ---------------------------------------------------------------------------

BUCKET_NORMAL = "normal"
BUCKET_DEGRADED_HEALTH = "degraded-health"
BUCKET_HIGH_TOKEN = "high-token"  # noqa: S105 — bucket name, not a password
BUCKET_LOW_TOKEN = "low-token"  # noqa: S105 — bucket name, not a password
BUCKET_MIXED_HEALTH = "mixed-health"

ALL_BUCKETS: list[str] = [
    BUCKET_NORMAL,
    BUCKET_DEGRADED_HEALTH,
    BUCKET_HIGH_TOKEN,
    BUCKET_LOW_TOKEN,
    BUCKET_MIXED_HEALTH,
]

#: Buckets considered critical for fidelity reporting.
CRITICAL_BUCKETS: ClassVar[set[str]] = {
    BUCKET_DEGRADED_HEALTH,
    BUCKET_HIGH_TOKEN,
    BUCKET_MIXED_HEALTH,
}


# ---------------------------------------------------------------------------
# Health presets
# ---------------------------------------------------------------------------

_HEALTHY = EndpointHealth(
    latency_p50=0.1, error_rate=0.01, circuit_state=0.0, queue_depth=0.1
)
_DEGRADED = EndpointHealth(
    latency_p50=0.7, error_rate=0.3, circuit_state=0.5, queue_depth=0.7
)
_DOWN = EndpointHealth(
    latency_p50=1.0, error_rate=0.9, circuit_state=1.0, queue_depth=1.0
)

_NORMAL_HEALTHS = [_HEALTHY] * _NUM_ENDPOINTS
_ALL_DEGRADED = [_DEGRADED] * _NUM_ENDPOINTS
_ALL_DOWN = [_DOWN] * _NUM_ENDPOINTS


def _mixed_health(down_index: int) -> list[EndpointHealth]:
    """Return health list with one endpoint down, others healthy."""
    healths = [_HEALTHY] * _NUM_ENDPOINTS
    healths[down_index] = _DOWN
    return healths


# ---------------------------------------------------------------------------
# Scenario grid generation
# ---------------------------------------------------------------------------


def _normal_success_rates() -> list[float]:
    return [0.95] * _NUM_ENDPOINTS


def _degraded_success_rates() -> list[float]:
    return [0.5] * _NUM_ENDPOINTS


def _mixed_success_rates(low_index: int) -> list[float]:
    rates = [0.95] * _NUM_ENDPOINTS
    rates[low_index] = 0.3
    return rates


def generate_scenario_grid(
    *,
    oversample_degraded: int = 3,
) -> list[Scenario]:
    """Generate evaluation scenarios covering all observation combinations.

    The grid covers every task type under multiple operating conditions,
    with intentional oversampling of degraded and high-impact states.

    Args:
        oversample_degraded: How many times to repeat degraded/critical
            scenarios relative to normal ones.  Default 3 means each
            degraded scenario appears 3x for each normal-bucket scenario.

    Returns:
        List of ``Scenario`` objects ready for policy evaluation.
    """
    scenarios: list[Scenario] = []

    # Representative token counts (normalised)
    token_levels = [
        (0.1, BUCKET_LOW_TOKEN, "low-token"),
        (0.5, BUCKET_NORMAL, "mid-token"),
        (0.9, BUCKET_HIGH_TOKEN, "high-token"),
    ]

    # Representative hours for time encoding
    hours = [2.0, 10.0, 14.0, 22.0]

    # --- Normal scenarios (1x) ---
    for task_type, (token_norm, _, token_desc), hour in itertools.product(
        _TASK_TYPES, token_levels, hours
    ):
        angle = 2.0 * math.pi * hour / 24.0
        obs = make_routing_observation(
            task_type=task_type,
            estimated_tokens=int(token_norm * 100_000),
            max_tokens=100_000,
            endpoint_health=_NORMAL_HEALTHS,
            historical_success_rates=_normal_success_rates(),
            hour_of_day=hour,
        )
        bucket = (
            BUCKET_LOW_TOKEN
            if token_norm < 0.2
            else (BUCKET_HIGH_TOKEN if token_norm > 0.8 else BUCKET_NORMAL)
        )
        scenarios.append(
            Scenario(
                observation=obs,
                bucket=bucket,
                description=f"{task_type}/{token_desc}/hour={hour:.0f}/all-healthy",
            )
        )

    # --- Degraded-health scenarios (oversampled) ---
    for _ in range(oversample_degraded):
        for task_type, (token_norm, _, token_desc), hour in itertools.product(
            _TASK_TYPES, token_levels, hours
        ):
            # All endpoints degraded
            obs = make_routing_observation(
                task_type=task_type,
                estimated_tokens=int(token_norm * 100_000),
                max_tokens=100_000,
                endpoint_health=_ALL_DEGRADED,
                historical_success_rates=_degraded_success_rates(),
                hour_of_day=hour,
            )
            scenarios.append(
                Scenario(
                    observation=obs,
                    bucket=BUCKET_DEGRADED_HEALTH,
                    description=f"{task_type}/{token_desc}/hour={hour:.0f}/all-degraded",
                )
            )

    # --- Mixed-health scenarios (oversampled) ---
    for _ in range(oversample_degraded):
        for task_type, down_idx in itertools.product(
            _TASK_TYPES, range(_NUM_ENDPOINTS)
        ):
            obs = make_routing_observation(
                task_type=task_type,
                estimated_tokens=50_000,
                max_tokens=100_000,
                endpoint_health=_mixed_health(down_idx),
                historical_success_rates=_mixed_success_rates(down_idx),
                hour_of_day=14.0,
            )
            scenarios.append(
                Scenario(
                    observation=obs,
                    bucket=BUCKET_MIXED_HEALTH,
                    description=(
                        f"{task_type}/mid-token/hour=14/endpoint-{down_idx}-down"
                    ),
                )
            )

    return scenarios


__all__: list[str] = [
    "ALL_BUCKETS",
    "BUCKET_DEGRADED_HEALTH",
    "BUCKET_HIGH_TOKEN",
    "BUCKET_LOW_TOKEN",
    "BUCKET_MIXED_HEALTH",
    "BUCKET_NORMAL",
    "CRITICAL_BUCKETS",
    "Scenario",
    "generate_scenario_grid",
]
