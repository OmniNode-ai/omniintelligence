# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Frozen input/output models for the intent cost forecast compute node.

Input:  ModelIntentCostForecastInput  — fields needed to produce a forecast
Output: ModelIntentCostForecast       — the forecast attached to session context

Schema Rules:
    - frozen=True (events are immutable after emission)
    - extra="ignore" (forward compatibility)
    - from_attributes=True (pytest-xdist worker compatibility)
    - No datetime.now() defaults

Reference: OMN-2490
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from pydantic import BaseModel, ConfigDict, Field


class ModelIntentCostForecastInput(BaseModel):
    """Input for the intent cost forecast compute node.

    Attributes:
        session_id: Session ID being forecasted.
        correlation_id: Correlation ID for distributed tracing.
        intent_class: The classified intent class triggering the forecast.
        confidence: Classification confidence (affects forecast confidence interval).
        requested_at: Timestamp of the forecast request (injected by caller).
    """

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    session_id: str = Field(..., description="Session ID being forecasted")
    correlation_id: str = Field(
        ..., description="Correlation ID for distributed tracing (UUID string)"
    )
    intent_class: EnumIntentClass = Field(
        ..., description="The classified intent class triggering the forecast"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Classification confidence — affects forecast confidence interval width",
    )
    requested_at: datetime = Field(
        ...,
        description=(
            "Timestamp of the forecast request. "
            "Must NOT use datetime.now() as default — callers inject explicitly."
        ),
    )


class ModelIntentCostForecast(BaseModel):
    """Frozen forecast output attached to session context after classification.

    Contains estimated token budget, cost, latency, and a confidence interval
    derived from the historical baseline for the classified intent class.

    Escalation: If actual usage exceeds ``escalation_threshold_tokens``, an
    escalation signal should be emitted. This is observational only — it does
    not block execution.

    Attributes:
        event_type: Literal discriminator.
        session_id: Session ID this forecast belongs to.
        correlation_id: Correlation ID for distributed tracing.
        intent_class: The intent class this forecast covers.
        estimated_tokens_p50: Median estimated token count.
        estimated_tokens_p90: 90th-percentile estimated token count.
        estimated_tokens_p99: 99th-percentile estimated token count.
        estimated_cost_usd_p50: Median estimated cost in USD.
        estimated_cost_usd_p90: 90th-percentile estimated cost in USD.
        estimated_latency_ms_p50: Median estimated latency in milliseconds.
        estimated_latency_ms_p90: 90th-percentile estimated latency in milliseconds.
        confidence_interval: Width of forecast uncertainty (0.0 tight, 1.0 very wide).
        escalation_threshold_tokens: Token count above which escalation fires (p90).
        baseline_sample_count: Number of real (non-synthetic) sessions in baseline.
        forecasted_at: Timestamp of forecast generation (injected by caller).
    """

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    event_type: Literal["IntentCostForecast"] = "IntentCostForecast"
    session_id: str = Field(..., description="Session ID this forecast belongs to")
    correlation_id: str = Field(
        ..., description="Correlation ID for distributed tracing (UUID string)"
    )
    intent_class: EnumIntentClass = Field(
        ..., description="The intent class this forecast covers"
    )
    estimated_tokens_p50: float = Field(
        ..., ge=0.0, description="Median estimated token count"
    )
    estimated_tokens_p90: float = Field(
        ..., ge=0.0, description="90th-percentile estimated token count"
    )
    estimated_tokens_p99: float = Field(
        ..., ge=0.0, description="99th-percentile estimated token count"
    )
    estimated_cost_usd_p50: float = Field(
        ..., ge=0.0, description="Median estimated cost in USD"
    )
    estimated_cost_usd_p90: float = Field(
        ..., ge=0.0, description="90th-percentile estimated cost in USD"
    )
    estimated_latency_ms_p50: float = Field(
        ..., ge=0.0, description="Median estimated latency in milliseconds"
    )
    estimated_latency_ms_p90: float = Field(
        ..., ge=0.0, description="90th-percentile estimated latency in milliseconds"
    )
    confidence_interval: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Width of forecast uncertainty (0.0 = tight, 1.0 = very wide). "
            "Widens as classification confidence decreases."
        ),
    )
    escalation_threshold_tokens: float = Field(
        ...,
        ge=0.0,
        description="Token count above which escalation fires (equals estimated_tokens_p90)",
    )
    baseline_sample_count: int = Field(
        ...,
        ge=0,
        description="Number of real (non-synthetic) sessions contributing to this baseline",
    )
    forecasted_at: datetime = Field(
        ...,
        description=(
            "Timestamp of forecast generation. "
            "Must NOT use datetime.now() as default — callers inject explicitly."
        ),
    )


class ModelForecastAccuracyRecord(BaseModel):
    """Frozen record comparing actual vs forecasted cost for accuracy tracking.

    Logged after session completion for baseline improvement analysis.

    Attributes:
        session_id: Session ID.
        correlation_id: Correlation ID.
        intent_class: The intent class.
        forecast_tokens_p50: Forecasted median token count.
        actual_tokens: Actual token count observed.
        forecast_cost_usd_p50: Forecasted median cost.
        actual_cost_usd: Actual cost observed.
        escalation_triggered: Whether actual tokens exceeded the p90 threshold.
        recorded_at: Timestamp of accuracy recording (injected by caller).
    """

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    session_id: str = Field(..., description="Session ID")
    correlation_id: str = Field(..., description="Correlation ID")
    intent_class: EnumIntentClass = Field(..., description="The intent class")
    forecast_tokens_p50: float = Field(
        ..., ge=0.0, description="Forecasted median token count"
    )
    actual_tokens: int = Field(..., ge=0, description="Actual token count observed")
    forecast_cost_usd_p50: float = Field(
        ..., ge=0.0, description="Forecasted median cost in USD"
    )
    actual_cost_usd: float = Field(
        ..., ge=0.0, description="Actual cost in USD observed"
    )
    escalation_triggered: bool = Field(
        ...,
        description="True when actual tokens exceeded the p90 escalation threshold",
    )
    recorded_at: datetime = Field(
        ...,
        description="Timestamp of accuracy recording — injected by caller, no datetime.now() defaults",
    )


__all__ = [
    "ModelForecastAccuracyRecord",
    "ModelIntentCostForecast",
    "ModelIntentCostForecastInput",
]
