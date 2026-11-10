# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity for the intent cost forecast handler (OMN-2490 / OMN-23422).

``HandlerComputeForecast.handle`` must return exactly what the preserved
``compute_forecast`` function returns for the same request and the same injected
``forecasted_at`` timestamp.
"""

import importlib
import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

import pytest
from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass

from omniintelligence.nodes.node_intent_cost_forecast_compute.handlers.handler_cost_forecast import (
    compute_forecast,
)
from omniintelligence.nodes.node_intent_cost_forecast_compute.models import (
    ModelCostBaseline,
    ModelIntentCostForecastInput,
    build_seeded_baseline,
)

MODULE = (
    "omniintelligence.nodes.node_intent_cost_forecast_compute"
    ".handlers.handler_cost_forecast"
)
CLASS_NAME = "HandlerComputeForecast"
_NOW = datetime(2026, 1, 15, 9, 30, 0, tzinfo=UTC)


def _input(
    intent_class: EnumIntentClass = EnumIntentClass.REFACTOR,
    confidence: float = 0.9,
) -> ModelIntentCostForecastInput:
    return ModelIntentCostForecastInput(
        session_id="sess-parity",
        correlation_id="00000000-0000-0000-0000-000000000042",
        intent_class=intent_class,
        confidence=confidence,
        requested_at=_NOW,
    )


def _seeded(intent_class: EnumIntentClass) -> dict[EnumIntentClass, ModelCostBaseline]:
    return {intent_class: build_seeded_baseline(intent_class)}


def _observed_baseline() -> dict[EnumIntentClass, ModelCostBaseline]:
    return {
        EnumIntentClass.BUGFIX: ModelCostBaseline(
            intent_class=EnumIntentClass.BUGFIX,
            token_samples=[1000, 2000, 3000, 4000, 50000, 60000, 900, 1100, 70000, 80],
            latency_samples_ms=[100.0, 250.5, 9000.0, 12000.0, 300.0, 800.0],
            sample_count=10,
        )
    }


def _single_sample_baseline() -> dict[EnumIntentClass, ModelCostBaseline]:
    return {
        EnumIntentClass.FEATURE: ModelCostBaseline(
            intent_class=EnumIntentClass.FEATURE,
            token_samples=[4200],
            latency_samples_ms=[15000.0],
            sample_count=1,
        )
    }


def _empty_baseline() -> dict[EnumIntentClass, ModelCostBaseline]:
    return {
        EnumIntentClass.ANALYSIS: ModelCostBaseline(
            intent_class=EnumIntentClass.ANALYSIS
        )
    }


def _deps() -> dict[str, Any]:
    return {"forecasted_at": _NOW}


def _no_forecasted_at() -> dict[str, Any]:
    return {}


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "seeded-baseline-high-confidence",
        CLASS_NAME,
        lambda: {
            "input_data": _input(),
            "baselines": _seeded(EnumIntentClass.REFACTOR),
        },
        _deps,
    ),
    (
        "missing-class-falls-back-to-seed",
        CLASS_NAME,
        lambda: {"input_data": _input(EnumIntentClass.MIGRATION), "baselines": {}},
        _deps,
    ),
    (
        "observed-baseline-low-confidence",
        CLASS_NAME,
        lambda: {
            "input_data": _input(EnumIntentClass.BUGFIX, confidence=0.3),
            "baselines": _observed_baseline(),
        },
        _deps,
    ),
    (
        "zero-confidence-widest-interval",
        CLASS_NAME,
        lambda: {
            "input_data": _input(EnumIntentClass.SECURITY, confidence=0.0),
            "baselines": _seeded(EnumIntentClass.SECURITY),
        },
        _deps,
    ),
    (
        "perfect-confidence-zero-interval",
        CLASS_NAME,
        lambda: {
            "input_data": _input(EnumIntentClass.DOCUMENTATION, confidence=1.0),
            "baselines": _seeded(EnumIntentClass.DOCUMENTATION),
        },
        _deps,
    ),
    (
        "single-sample-baseline",
        CLASS_NAME,
        lambda: {
            "input_data": _input(EnumIntentClass.FEATURE, confidence=0.5),
            "baselines": _single_sample_baseline(),
        },
        _deps,
    ),
    (
        "empty-sample-baseline",
        CLASS_NAME,
        lambda: {
            "input_data": _input(EnumIntentClass.ANALYSIS, confidence=0.7),
            "baselines": _empty_baseline(),
        },
        _deps,
    ),
    (
        "baselines-none-raises",
        CLASS_NAME,
        lambda: {"input_data": _input(), "baselines": None},
        _deps,
    ),
    (
        "missing-forecasted-at-raises",
        CLASS_NAME,
        lambda: {
            "input_data": _input(),
            "baselines": _seeded(EnumIntentClass.REFACTOR),
        },
        _no_forecasted_at,
    ),
]


def _describe(value: Any) -> Any:
    if isinstance(value, ModelIntentCostForecastInput):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {
            getattr(key, "value", key): (
                {**asdict(val), "intent_class": val.intent_class.value}
                if isinstance(val, ModelCostBaseline)
                else val
            )
            for key, val in value.items()
        }
    return value


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(
                    {key: _describe(val) for key, val in request_builder().items()},
                    default=str,
                )
            ),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], dict[str, Any]],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """Wrapper and preserved function return (or raise) exactly alike."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = None
    function_result = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = await compute_forecast(**request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
    # The baselines passed in must be left untouched by both entry points.
    assert request_a["baselines"] == request_b["baselines"]
