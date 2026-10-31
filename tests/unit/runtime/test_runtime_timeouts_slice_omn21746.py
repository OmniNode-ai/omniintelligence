# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The remaining literal timeouts are read from runtime_timeouts.yaml (OMN-21746)."""

from __future__ import annotations

import inspect
from typing import cast
from unittest.mock import patch

import pytest

from omniintelligence.models.runtime_timeouts import runtime_timeouts
from omniintelligence.nodes.node_intent_cost_forecast_compute.handlers import (
    handler_cost_forecast,
)
from omniintelligence.protocols import ProtocolKafkaPublisher
from omniintelligence.runtime import (
    dispatch_handlers,
    introspection,
    promotion_scheduler,
)

pytestmark = pytest.mark.unit


class _StopError(Exception):
    """Ends the scheduler loop after its first sleep."""


def test_the_projection_throttle_defaults_to_the_contract() -> None:
    assert (
        runtime_timeouts().projection_throttle_s
        == dispatch_handlers._PROJECTION_THROTTLE_SECONDS
    )


def test_the_introspection_heartbeat_defaults_to_the_contract() -> None:
    parameter = inspect.signature(
        introspection.publish_intelligence_introspection
    ).parameters["heartbeat_interval_seconds"]
    assert parameter.default is None
    assert runtime_timeouts().heartbeat_s > 0


def test_the_promotion_interval_defaults_to_the_contract() -> None:
    parameter = inspect.signature(
        promotion_scheduler.run_promotion_scheduler
    ).parameters["interval_seconds"]
    assert parameter.default is None
    assert not hasattr(promotion_scheduler, "DEFAULT_INTERVAL_SECONDS")


@pytest.mark.asyncio
async def test_the_promotion_scheduler_sleeps_the_contract_interval() -> None:
    sleeps: list[float] = []

    async def _sleep(seconds: float) -> None:
        sleeps.append(seconds)
        raise _StopError

    class _Publisher:
        async def publish(self, **_kwargs: object) -> bool:
            return True

    with (
        patch.object(promotion_scheduler.asyncio, "sleep", _sleep),
        pytest.raises(_StopError),
    ):
        await promotion_scheduler.run_promotion_scheduler(
            publisher=cast("ProtocolKafkaPublisher", _Publisher())
        )
    assert sleeps == [runtime_timeouts().promotion_interval_s]


def test_the_forecast_module_holds_no_interval_constant() -> None:
    assert not hasattr(handler_cost_forecast, "_MAX_CONFIDENCE_INTERVAL")
    assert runtime_timeouts().forecast_max_ci_width > 0
