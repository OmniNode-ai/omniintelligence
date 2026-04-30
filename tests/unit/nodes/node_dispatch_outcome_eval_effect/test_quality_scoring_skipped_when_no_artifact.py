# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""No-artifact quality scoring tests for node_dispatch_outcome_eval_effect."""

from __future__ import annotations

from pathlib import Path

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


def _make_event(artifact_path: str | None = None) -> ModelInput:
    return ModelInput(
        task_id="task-123",
        dispatch_id="dispatch-456",
        ticket_id="OMN-10385",
        status="completed",
        artifact_path=artifact_path,
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


@pytest.mark.asyncio
async def test_skips_quality_scoring_compute_for_unsupported_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsupported artifact languages do not invoke quality scoring."""
    artifact = tmp_path / "dispatch_artifact.ts"
    artifact.write_text("export const value = 1;\n", encoding="utf-8")

    def fail_if_called(
        input_data: ModelQualityScoringInput,
    ) -> ModelQualityScoringOutput:
        raise AssertionError("quality scoring should not be invoked")

    monkeypatch.setattr(
        handler_dispatch_outcome,
        "handle_quality_scoring_compute",
        fail_if_called,
    )

    result = await handler_dispatch_outcome.handle_dispatch_outcome(
        _make_event(str(artifact))
    )

    assert result.quality_score is None


@pytest.mark.asyncio
async def test_skips_quality_scoring_compute_when_artifact_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing Python artifacts do not fail dispatch outcome evaluation."""
    artifact = tmp_path / "missing_artifact.py"

    def fail_if_called(
        input_data: ModelQualityScoringInput,
    ) -> ModelQualityScoringOutput:
        raise AssertionError("quality scoring should not be invoked")

    monkeypatch.setattr(
        handler_dispatch_outcome,
        "handle_quality_scoring_compute",
        fail_if_called,
    )

    result = await handler_dispatch_outcome.handle_dispatch_outcome(
        _make_event(str(artifact))
    )

    assert result.quality_score is None


@pytest.mark.asyncio
async def test_skips_quality_score_when_compute_raises_runtime_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime scoring failures do not fail dispatch outcome evaluation."""
    artifact = tmp_path / "dispatch_artifact.py"
    artifact.write_text("class DispatchArtifact:\n    pass\n", encoding="utf-8")

    def fail_with_runtime_error(
        input_data: ModelQualityScoringInput,
    ) -> ModelQualityScoringOutput:
        raise RuntimeError("scoring failed")

    monkeypatch.setattr(
        handler_dispatch_outcome,
        "handle_quality_scoring_compute",
        fail_with_runtime_error,
    )

    result = await handler_dispatch_outcome.handle_dispatch_outcome(
        _make_event(str(artifact))
    )

    assert result.quality_score is None
