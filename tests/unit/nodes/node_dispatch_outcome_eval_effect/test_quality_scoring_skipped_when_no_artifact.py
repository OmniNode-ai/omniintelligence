# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""No-artifact quality scoring tests for node_dispatch_outcome_eval_effect."""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_dispatch_outcome_eval_effect.handlers import (
    handler_dispatch_outcome,
)
from omniintelligence.nodes.node_dispatch_outcome_eval_effect.models import ModelInput
from omniintelligence.nodes.node_quality_scoring_compute.models import (
    ModelQualityScoringInput,
    ModelQualityScoringOutput,
)

pytestmark = pytest.mark.unit


def _make_event() -> ModelInput:
    return ModelInput(
        task_id="task-123",
        dispatch_id="dispatch-456",
        ticket_id="OMN-10385",
        status="completed",
        artifact_path=None,
        model_calls=2,
        token_cost=1000,
        dollars_cost=0.25,
    )


@pytest.mark.asyncio
async def test_skips_quality_scoring_compute_without_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch outcomes without artifact_path do not invoke quality scoring."""

    def fail_if_called(
        input_data: ModelQualityScoringInput,
    ) -> ModelQualityScoringOutput:
        raise AssertionError("quality scoring should not be invoked")

    monkeypatch.setattr(
        handler_dispatch_outcome,
        "handle_quality_scoring_compute",
        fail_if_called,
    )

    result = await handler_dispatch_outcome.handle_dispatch_outcome(_make_event())

    assert result.quality_score is None
