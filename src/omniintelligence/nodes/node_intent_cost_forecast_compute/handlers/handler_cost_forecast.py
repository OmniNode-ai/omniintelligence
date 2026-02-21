# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Pure compute handlers for intent cost and latency forecasting.

All functions are pure (no I/O). The baseline registry is passed in by the
caller so tests can supply controlled baselines without mocking.

Public API:
    compute_forecast         — Produce a ModelIntentCostForecast from a baseline.
    update_baseline          — Record a completed session into the baseline.
    check_escalation         — Return True if actual tokens exceed p90 threshold.
    compute_accuracy_record  — Build a ModelForecastAccuracyRecord for logging.

Reference: OMN-2490
"""

from __future__ import annotations

from datetime import datetime

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass

from omniintelligence.nodes.node_intent_cost_forecast_compute.models.model_cost_baseline import (
    ModelCostBaseline,
    build_seeded_baseline,
)
from omniintelligence.nodes.node_intent_cost_forecast_compute.models.model_intent_cost_forecast import (
    ModelForecastAccuracyRecord,
    ModelIntentCostForecast,
    ModelIntentCostForecastInput,
)

# Maximum confidence interval width. Multiplied by (1 - classification_confidence)
# to produce the final confidence_interval in the forecast.
_MAX_CONFIDENCE_INTERVAL: float = 0.8


def compute_forecast(
    input_data: ModelIntentCostForecastInput,
    baselines: dict[EnumIntentClass, ModelCostBaseline],
    *,
    forecasted_at: datetime,
) -> ModelIntentCostForecast:
    """Produce a frozen ModelIntentCostForecast from the given baseline.

    Uses the historical p50/p90/p99 token distributions to estimate cost and
    latency. Widens the confidence interval as classification confidence drops.

    Args:
        input_data: Frozen forecast input (session_id, intent_class, confidence, …).
        baselines: Registry mapping each intent class to its historical baseline.
            If the class is missing, a fresh seeded baseline is used.
        forecasted_at: Timestamp injected by the caller — no datetime.now().

    Returns:
        Frozen ModelIntentCostForecast ready for attachment to session context.
    """
    intent_class = input_data.intent_class
    baseline = baselines.get(intent_class) or build_seeded_baseline(intent_class)

    # Widen confidence interval inversely with classification confidence
    confidence_interval = round(
        (1.0 - input_data.confidence) * _MAX_CONFIDENCE_INTERVAL, 4
    )

    return ModelIntentCostForecast(
        session_id=input_data.session_id,
        correlation_id=input_data.correlation_id,
        intent_class=intent_class,
        estimated_tokens_p50=baseline.token_p50,
        estimated_tokens_p90=baseline.token_p90,
        estimated_tokens_p99=baseline.token_p99,
        estimated_cost_usd_p50=baseline.estimated_cost_usd(baseline.token_p50),
        estimated_cost_usd_p90=baseline.estimated_cost_usd(baseline.token_p90),
        estimated_latency_ms_p50=baseline.latency_p50_ms,
        estimated_latency_ms_p90=baseline.latency_p90_ms,
        confidence_interval=confidence_interval,
        escalation_threshold_tokens=baseline.token_p90,
        baseline_sample_count=baseline.sample_count,
        forecasted_at=forecasted_at,
    )


def update_baseline(
    baseline: ModelCostBaseline,
    *,
    actual_tokens: int,
    actual_latency_ms: float,
) -> None:
    """Record a completed session's token and latency observations into the baseline.

    Mutates the baseline in place. Called after each session completion
    (triggered by onex.evt.intent.outcome.labeled.v1).

    Args:
        baseline: The mutable baseline to update.
        actual_tokens: Actual token count (input + output) for the session.
        actual_latency_ms: Actual wall-clock latency for the session in milliseconds.
    """
    baseline.token_samples.append(actual_tokens)
    baseline.latency_samples_ms.append(actual_latency_ms)
    baseline.sample_count += 1


def check_escalation(
    actual_tokens: int,
    forecast: ModelIntentCostForecast,
) -> bool:
    """Return True if actual token usage exceeds the p90 escalation threshold.

    This is a pure observability check — it never blocks execution.

    Args:
        actual_tokens: Actual token count for the session.
        forecast: The forecast produced at classification time.

    Returns:
        True if escalation should be signalled.
    """
    return actual_tokens > forecast.escalation_threshold_tokens


def compute_accuracy_record(
    *,
    session_id: str,
    correlation_id: str,
    intent_class: EnumIntentClass,
    forecast: ModelIntentCostForecast,
    actual_tokens: int,
    actual_cost_usd: float,
    recorded_at: datetime,
) -> ModelForecastAccuracyRecord:
    """Build a frozen accuracy record comparing actual vs. forecasted cost.

    Args:
        session_id: Session ID.
        correlation_id: Correlation ID.
        intent_class: The intent class.
        forecast: The forecast produced at classification time.
        actual_tokens: Actual token count for the session.
        actual_cost_usd: Actual cost in USD for the session.
        recorded_at: Timestamp injected by caller — no datetime.now().

    Returns:
        Frozen ModelForecastAccuracyRecord for logging.
    """
    return ModelForecastAccuracyRecord(
        session_id=session_id,
        correlation_id=correlation_id,
        intent_class=intent_class,
        forecast_tokens_p50=forecast.estimated_tokens_p50,
        actual_tokens=actual_tokens,
        forecast_cost_usd_p50=forecast.estimated_cost_usd_p50,
        actual_cost_usd=actual_cost_usd,
        escalation_triggered=check_escalation(actual_tokens, forecast),
        recorded_at=recorded_at,
    )


__all__ = [
    "check_escalation",
    "compute_accuracy_record",
    "compute_forecast",
    "update_baseline",
]
