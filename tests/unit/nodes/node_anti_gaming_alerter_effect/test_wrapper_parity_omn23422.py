# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Deterministic parity checks for the HandlerAntiGamingAlerterEffect wrapper (OMN-23422).

The contract-bound wrapper must return exactly what the preserved
``NodeAntiGamingAlerterEffect.execute`` method returns for the same request
and the same dependencies.  The publisher is an in-memory fake so no Kafka
broker is needed.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_anti_gaming_alerter_effect.models.model_alerter_input import (
    ModelAlerterInput,
)
from omniintelligence.nodes.node_anti_gaming_alerter_effect.models.model_alerter_output import (
    ModelAlerterOutput,
)
from omniintelligence.nodes.node_anti_gaming_alerter_effect.node import (
    NodeAntiGamingAlerterEffect,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_alert_event import (
    ModelAntiGamingAlertUnion,
    ModelDistributionalShiftAlert,
    ModelDiversityConstraintViolation,
    ModelGoodhartViolationAlert,
    ModelRewardHackingAlert,
)

MODULE = "omniintelligence.nodes.node_anti_gaming_alerter_effect.node"
WRAPPER_CLASS = "HandlerAntiGamingAlerterEffect"


def _goodhart(run_id: str = "test-run-001") -> ModelGoodhartViolationAlert:
    return ModelGoodhartViolationAlert(
        run_id=run_id,
        objective_id="obj-1",
        improving_metric="correctness",
        degrading_metric="latency",
        improvement_delta=0.3,
        degradation_delta=0.2,
        threshold=0.1,
        occurred_at_utc="2026-01-01T00:00:00Z",
    )


def _reward_hacking(run_id: str = "test-run-001") -> ModelRewardHackingAlert:
    return ModelRewardHackingAlert(
        run_id=run_id,
        objective_id="obj-1",
        score_improvement=0.4,
        acceptance_rate_delta=-0.1,
        threshold=0.05,
        occurred_at_utc="2026-01-01T00:00:01Z",
    )


def _shift(run_id: str = "test-run-001") -> ModelDistributionalShiftAlert:
    return ModelDistributionalShiftAlert(
        run_id=run_id,
        objective_id="obj-1",
        drift_score=0.7,
        threshold=0.5,
        shifted_sources=("ci", "review"),
        occurred_at_utc="2026-01-01T00:00:02Z",
    )


def _make_diversity_violation() -> ModelDiversityConstraintViolation:
    """Build a diversity constraint violation for parity tests."""
    return ModelDiversityConstraintViolation(
        run_id="test-run-001",
        objective_id="obj-1",
        present_sources=("ci",),
        required_min_sources=2,
        occurred_at_utc="2026-01-01T00:00:03Z",
    )


def _make_guardrail_output(
    alerts: list[ModelAntiGamingAlertUnion] | None = None,
    diversity_violation: ModelDiversityConstraintViolation | None = None,
) -> Any:
    """Build a guardrail output object for parity tests."""
    from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_output import (
        ModelGuardrailOutput,
    )

    return ModelGuardrailOutput(
        run_id="test-run-001",
        alerts=tuple(alerts or []),
        diversity_violation=diversity_violation,
    )


def _request(
    alerts: list[ModelAntiGamingAlertUnion] | None = None,
    diversity_violation: ModelDiversityConstraintViolation | None = None,
    topic: str = "test.topic",
) -> ModelAlerterInput:
    """Build a ModelAlerterInput for parity tests."""
    return ModelAlerterInput(
        guardrail_output=_make_guardrail_output(alerts, diversity_violation),
        kafka_topic=topic,
    )


def _deps() -> dict[str, Any]:
    """Fresh dependency dict with a fresh AsyncMock publisher per call."""
    return {"publisher": AsyncMock()}


PARITY_CASES: list[
    tuple[str, str, Callable[[], BaseModel], Callable[[], dict[str, Any]]]
] = [
    (
        "single-alert",
        WRAPPER_CLASS,
        lambda: _request(alerts=[_goodhart()]),
        _deps,
    ),
    (
        "multiple-alerts",
        WRAPPER_CLASS,
        lambda: _request(
            alerts=[
                _goodhart(),
                _reward_hacking(),
                _shift(),
            ]
        ),
        _deps,
    ),
    (
        "with-diversity-violation",
        WRAPPER_CLASS,
        lambda: _request(
            alerts=[_goodhart()],
            diversity_violation=_make_diversity_violation(),
        ),
        _deps,
    ),
    (
        "empty-alerts",
        WRAPPER_CLASS,
        lambda: _request(alerts=[]),
        _deps,
    ),
    (
        "only-diversity-violation",
        WRAPPER_CLASS,
        lambda: _request(
            alerts=[],
            diversity_violation=_make_diversity_violation(),
        ),
        _deps,
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _, _, _ in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], BaseModel],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """The wrapper returns exactly what NodeAntiGamingAlerterEffect.execute returns."""
    module = importlib.import_module(MODULE)
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    via_wrapper = await wrapper_cls(**deps_a).handle(request_a)
    via_function = await NodeAntiGamingAlerterEffect(**deps_b).execute(request_b)

    assert isinstance(via_wrapper, ModelAlerterOutput)
    assert via_wrapper == via_function
    assert via_wrapper.run_id == request_a.guardrail_output.run_id
    assert via_wrapper.topic == request_a.kafka_topic

    # Compare publisher calls recorded by deps_a and deps_b
    assert deps_a["publisher"].mock_calls == deps_b["publisher"].mock_calls


def corpus_inputs() -> list[dict[str, Any]]:
    """JSON-describable inputs of PARITY_CASES, in corpus order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(request_builder().model_dump(mode="json"), default=str)
            ),
        }
        for case_id, class_name, request_builder, _deps_builder in PARITY_CASES
    ]
