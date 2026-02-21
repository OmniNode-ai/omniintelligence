# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Intent Cost Forecast Compute Node — thin shell delegating to handler.

Produces a ModelIntentCostForecast immediately after intent classification.
The forecast contains estimated token budget, cost, and latency derived from
per-intent-class historical baselines (seeded with synthetic values on first run).

Escalation: If actual token usage exceeds the p90 threshold after session
completion, consumers should emit an escalation signal (observational only —
never blocks execution).

Reference: OMN-2490
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_intent_cost_forecast_compute.handlers import (
    compute_forecast,
)
from omniintelligence.nodes.node_intent_cost_forecast_compute.models import (
    ModelCostBaseline,
    ModelIntentCostForecast,
    ModelIntentCostForecastInput,
    build_all_seeded_baselines,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeIntentCostForecastCompute(
    NodeCompute[ModelIntentCostForecastInput, ModelIntentCostForecast]
):
    """Pure compute node for intent cost and latency forecasting.

    Generates a forecast at classification time using per-intent-class
    historical baselines. Baselines are seeded with synthetic values to
    prevent cold-start empty forecasts.

    This node is a thin shell following the ONEX declarative pattern.
    All computation logic is delegated to handler functions.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialise with pre-seeded baselines for all 8 intent classes.

        Args:
            container: ONEX container with node configuration.
        """
        super().__init__(container)
        self._baselines: dict[EnumIntentClass, ModelCostBaseline] = (
            build_all_seeded_baselines()
        )

    async def compute(
        self, input_data: ModelIntentCostForecastInput
    ) -> ModelIntentCostForecast:
        """Generate a cost and latency forecast for the given session.

        Args:
            input_data: Frozen forecast input with session_id, intent_class,
                classification confidence, and requested_at timestamp.

        Returns:
            Frozen ModelIntentCostForecast for attachment to session context.
        """
        return compute_forecast(
            input_data,
            self._baselines,
            forecasted_at=datetime.now(tz=UTC),
        )


__all__ = ["NodeIntentCostForecastCompute"]
