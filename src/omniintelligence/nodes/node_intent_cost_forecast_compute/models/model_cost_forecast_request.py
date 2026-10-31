# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Frozen request for intent cost and latency forecasting."""

from __future__ import annotations

from datetime import datetime

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_intent_cost_forecast_compute.models.model_cost_baseline import (
    ModelCostBaseline,
)
from omniintelligence.nodes.node_intent_cost_forecast_compute.models.model_intent_cost_forecast import (
    ModelIntentCostForecastInput,
)


class ModelCostForecastRequest(BaseModel):
    """Forecast input, historical baselines, and caller-injected timestamp."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    input_data: ModelIntentCostForecastInput
    baselines: dict[EnumIntentClass, ModelCostBaseline]
    forecasted_at: datetime


__all__ = ["ModelCostForecastRequest"]
