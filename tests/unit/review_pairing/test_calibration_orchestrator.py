# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for CalibrationOrchestrator.

TDD: Tests written first for OMN-6169.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from omniintelligence.review_pairing.calibration_orchestrator import (
    CalibrationOrchestrator,
)
from omniintelligence.review_pairing.models import (
    FindingSeverity,
    ReviewFindingObserved,
)
from omniintelligence.review_pairing.models_calibration import (
    CalibrationConfig,
    CalibrationOrchestrationResult,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_observed_finding(
    model: str = "codex",
    category: str = "architecture",
    message: str = "Issue found",
) -> ReviewFindingObserved:
    """Build a ReviewFindingObserved for testing."""
    return ReviewFindingObserved(
        finding_id=uuid4(),
        repo="OmniNode-ai/test",
        pr_id=1,
        tool_name="ai-reviewer",
        tool_version="1.0.0",
        rule_id=f"ai-reviewer:{model}:{category}",
        file_path="file.py",
        line_start=1,
        line_end=1,
        severity=FindingSeverity.ERROR,
        normalized_message=message,
        raw_message=message,
        commit_sha_observed="abc1234",
        observed_at=datetime.now(tz=UTC),
    )


def _make_review_result(
    model: str = "codex",
    success: bool = True,
    findings: list[ReviewFindingObserved] | None = None,
    error: str | None = None,
) -> ModelExternalReviewResult:
    """Build a ModelExternalReviewResult for testing."""
    f = findings or []
    return ModelExternalReviewResult(
        model=model,
        prompt_version="v1.0",
        success=success,
        error=error,
        findings=f,
        result_count=len(f),
    )


def _default_config(
    ground_truth: str = "codex",
    challengers: list[str] | None = None,
) -> CalibrationConfig:
    return CalibrationConfig(
        ground_truth_model=ground_truth,
        challenger_models=challengers or ["deepseek-r1"],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_happy_path_single_challenger() -> None:
    """Ground truth + one challenger both succeed; result has metrics."""
    gt_findings = [
        _make_observed_finding("codex", "architecture", "Missing abstraction layer"),
    ]
    ch_findings = [
        _make_observed_finding(
            "deepseek-r1", "architecture", "Missing abstraction layer"
        ),
    ]

    async def mock_codex(content: str, **kwargs: object) -> ModelExternalReviewResult:
        return _make_review_result("codex", findings=gt_findings)

    async def mock_ai(content: str, **kwargs: object) -> ModelExternalReviewResult:
        return _make_review_result("deepseek-r1", findings=ch_findings)

    config = _default_config()
    orchestrator = CalibrationOrchestrator(
        config=config,
        codex_adapter=mock_codex,
        ai_adapter=mock_ai,
    )
    result = await orchestrator.run("some plan content", review_type="plan")

    assert isinstance(result, CalibrationOrchestrationResult)
    assert result.success is True
    assert result.error is None
    assert len(result.ground_truth_findings) == 1
    assert len(result.challenger_results) == 1
    cr = result.challenger_results[0]
    assert cr.challenger_model == "deepseek-r1"
    assert cr.ground_truth_model == "codex"
    assert cr.error is None
    assert cr.metrics is not None
    assert cr.prompt_version == "v1.0"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ground_truth_failure_aborts() -> None:
    """If ground truth model fails, entire run aborts with error."""

    async def mock_codex(content: str, **kwargs: object) -> ModelExternalReviewResult:
        return _make_review_result("codex", success=False, error="timeout")

    async def mock_ai(content: str, **kwargs: object) -> ModelExternalReviewResult:
        raise AssertionError("AI adapter should not be called on GT failure")

    config = _default_config()
    orchestrator = CalibrationOrchestrator(
        config=config,
        codex_adapter=mock_codex,
        ai_adapter=mock_ai,
    )
    result = await orchestrator.run("plan content")

    assert result.success is False
    assert result.error is not None
    assert "ground truth" in result.error.lower() or "codex" in result.error.lower()
    assert result.challenger_results == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_challenger_returns_error_result() -> None:
    """Failed challenger produces result with error and no metrics."""
    gt_findings = [_make_observed_finding("codex")]

    async def mock_codex(content: str, **kwargs: object) -> ModelExternalReviewResult:
        return _make_review_result("codex", findings=gt_findings)

    async def mock_ai(content: str, **kwargs: object) -> ModelExternalReviewResult:
        return _make_review_result("deepseek-r1", success=False, error="model down")

    config = _default_config()
    orchestrator = CalibrationOrchestrator(
        config=config,
        codex_adapter=mock_codex,
        ai_adapter=mock_ai,
    )
    result = await orchestrator.run("plan content")

    assert result.success is True  # orchestration succeeds even if challenger fails
    assert len(result.challenger_results) == 1
    cr = result.challenger_results[0]
    assert cr.error is not None
    assert "model down" in cr.error
    assert cr.metrics is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multiple_challengers() -> None:
    """Orchestrator runs all challengers and returns one result per challenger."""
    gt_findings = [_make_observed_finding("codex")]

    call_log: list[str] = []

    async def mock_codex(content: str, **kwargs: object) -> ModelExternalReviewResult:
        call_log.append("codex")
        return _make_review_result("codex", findings=gt_findings)

    async def mock_ai(content: str, **kwargs: object) -> ModelExternalReviewResult:
        model = kwargs.get("model", "unknown")
        call_log.append(str(model))
        return _make_review_result(
            str(model),
            findings=[_make_observed_finding(str(model))],
        )

    config = _default_config(challengers=["deepseek-r1", "qwen3-coder"])
    orchestrator = CalibrationOrchestrator(
        config=config,
        codex_adapter=mock_codex,
        ai_adapter=mock_ai,
    )
    result = await orchestrator.run("plan content")

    assert result.success is True
    assert len(result.challenger_results) == 2
    models = {r.challenger_model for r in result.challenger_results}
    assert models == {"deepseek-r1", "qwen3-coder"}
    # Ground truth called exactly once
    assert call_log.count("codex") == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_codex_challenger_uses_codex_adapter() -> None:
    """When a challenger model is 'codex', it uses the codex adapter."""
    gt_findings = [_make_observed_finding("codex")]

    codex_call_count = 0

    async def mock_codex(content: str, **kwargs: object) -> ModelExternalReviewResult:
        nonlocal codex_call_count
        codex_call_count += 1
        return _make_review_result("codex", findings=gt_findings)

    async def mock_ai(content: str, **kwargs: object) -> ModelExternalReviewResult:
        raise AssertionError("AI adapter should not be called for codex challenger")

    config = _default_config(challengers=["codex"])
    orchestrator = CalibrationOrchestrator(
        config=config,
        codex_adapter=mock_codex,
        ai_adapter=mock_ai,
    )
    result = await orchestrator.run("plan content")

    assert result.success is True
    # codex adapter called twice: once for GT, once for challenger
    assert codex_call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ai_ground_truth_uses_ai_adapter() -> None:
    """When ground truth model is not 'codex', it uses the ai adapter."""
    ai_call_models: list[str] = []

    async def mock_codex(content: str, **kwargs: object) -> ModelExternalReviewResult:
        raise AssertionError("Codex adapter should not be called")

    async def mock_ai(content: str, **kwargs: object) -> ModelExternalReviewResult:
        model = kwargs.get("model", "unknown")
        ai_call_models.append(str(model))
        return _make_review_result(
            str(model),
            findings=[_make_observed_finding(str(model))],
        )

    config = _default_config(
        ground_truth="deepseek-r1",
        challengers=["qwen3-coder"],
    )
    orchestrator = CalibrationOrchestrator(
        config=config,
        codex_adapter=mock_codex,
        ai_adapter=mock_ai,
    )
    result = await orchestrator.run("plan content")

    assert result.success is True
    assert "deepseek-r1" in ai_call_models
    assert "qwen3-coder" in ai_call_models
