# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Quality scoring invocation tests for node_dispatch_outcome_eval_effect."""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.nodes.node_dispatch_outcome_eval_effect.handlers import (
    handler_dispatch_outcome,
)
from omniintelligence.nodes.node_dispatch_outcome_eval_effect.models import (
    EnumUsageSource,
    ModelCallRecord,
    ModelCostProvenance,
    ModelInput,
)
from omniintelligence.nodes.node_quality_scoring_compute.models import (
    ModelQualityScoringInput,
    ModelQualityScoringOutput,
)

pytestmark = pytest.mark.unit


def _make_event(artifact_path: str) -> ModelInput:
    return ModelInput(
        task_id="task-123",
        dispatch_id="dispatch-456",
        ticket_id="OMN-10385",
        status="completed",
        artifact_path=artifact_path,
        model_calls=[
            ModelCallRecord(
                provider="claude_code",
                model="claude_subprocess",
                input_tokens=700,
                output_tokens=300,
                latency_ms=25,
                cost_dollars=0.25,
                cost_provenance=ModelCostProvenance(
                    usage_source=EnumUsageSource.ESTIMATED,
                    estimation_method="test_estimate",
                ),
            )
        ],
        token_cost=1000,
        dollars_cost=0.25,
        cost_provenance=ModelCostProvenance(
            usage_source=EnumUsageSource.ESTIMATED,
            estimation_method="model_call_rollup",
        ),
    )


@pytest.mark.asyncio
async def test_invokes_quality_scoring_compute_for_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Artifact-backed dispatch outcomes invoke quality scoring in-process."""
    artifact = tmp_path / "dispatch_artifact.py"
    artifact.write_text("class DispatchArtifact:\n    pass\n", encoding="utf-8")
    scoring_inputs: list[ModelQualityScoringInput] = []

    def fake_handle_quality_scoring_compute(
        input_data: ModelQualityScoringInput,
    ) -> ModelQualityScoringOutput:
        scoring_inputs.append(input_data)
        return ModelQualityScoringOutput(success=True, quality_score=0.875)

    monkeypatch.setattr(
        handler_dispatch_outcome,
        "handle_quality_scoring_compute",
        fake_handle_quality_scoring_compute,
    )

    result = await handler_dispatch_outcome.handle_dispatch_outcome(
        _make_event(str(artifact))
    )

    assert result.quality_score == 0.875
    assert len(scoring_inputs) == 1
    assert scoring_inputs[0].source_path == str(artifact)
    assert scoring_inputs[0].content == artifact.read_text(encoding="utf-8")
    assert scoring_inputs[0].language == "python"
