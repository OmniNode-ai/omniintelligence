# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the Calibration Run Orchestrator.

Reference: OMN-6169 (epic OMN-6164)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from omniintelligence.review_pairing.alignment_engine import FindingAlignmentEngine
from omniintelligence.review_pairing.calibration_orchestrator import (
    CalibrationOrchestrator,
)
from omniintelligence.review_pairing.calibration_scorer import CalibrationScorer
from omniintelligence.review_pairing.models import (
    FindingSeverity,
    ReviewFindingObserved,
)
from omniintelligence.review_pairing.models_calibration import CalibrationConfig
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
)


def _make_review_result(
    model: str = "codex",
    success: bool = True,
    findings_count: int = 3,
) -> ModelExternalReviewResult:
    findings = [
        ReviewFindingObserved(
            finding_id=uuid4(),
            repo="OmniNode-ai/test",
            pr_id=1,
            rule_id=f"ai-reviewer:{model}:architecture",
            severity=FindingSeverity.ERROR,
            file_path="src/main.py",
            line_start=i * 10 + 1,
            line_end=None,
            tool_name="ai-reviewer",
            tool_version="1.0",
            normalized_message=f"Finding {i} from {model}",
            raw_message=f"Raw finding {i}",
            commit_sha_observed="abcdef1234567",
            observed_at=datetime.now(timezone.utc),
        )
        for i in range(findings_count)
    ]
    return ModelExternalReviewResult(
        model=model,
        prompt_version="1.1.0",
        success=success,
        findings=findings,
        result_count=len(findings),
    )


def _make_failed_result(model: str = "codex") -> ModelExternalReviewResult:
    return ModelExternalReviewResult(
        model=model,
        prompt_version="1.1.0",
        success=False,
        error="Connection timeout",
    )


@pytest.mark.unit
class TestCalibrationOrchestrator:
    @pytest.fixture
    def config(self) -> CalibrationConfig:
        return CalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["deepseek-r1"],
            similarity_threshold=0.3,
        )

    @pytest.fixture
    def engine(self) -> FindingAlignmentEngine:
        return FindingAlignmentEngine(similarity_threshold=0.3)

    @pytest.fixture
    def scorer(self) -> CalibrationScorer:
        return CalibrationScorer()

    @pytest.mark.asyncio
    async def test_successful_run(
        self,
        config: CalibrationConfig,
        engine: FindingAlignmentEngine,
        scorer: CalibrationScorer,
    ) -> None:
        gt_adapter = AsyncMock(
            return_value=_make_review_result("codex", findings_count=3)
        )
        ch_adapter = AsyncMock(
            return_value=_make_review_result("deepseek-r1", findings_count=3)
        )
        orchestrator = CalibrationOrchestrator(
            config=config,
            alignment_engine=engine,
            scorer=scorer,
            adapter_dispatch={"codex": gt_adapter, "deepseek-r1": ch_adapter},
        )
        result = await orchestrator.run("test plan content")
        assert result.success is True
        assert len(result.ground_truth_findings) == 3
        assert len(result.challenger_results) == 1
        assert result.challenger_results[0].metrics is not None
        gt_adapter.assert_called_once()
        ch_adapter.assert_called_once()

    @pytest.mark.asyncio
    async def test_ground_truth_failure_aborts(
        self,
        config: CalibrationConfig,
        engine: FindingAlignmentEngine,
        scorer: CalibrationScorer,
    ) -> None:
        gt_adapter = AsyncMock(return_value=_make_failed_result("codex"))
        ch_adapter = AsyncMock()
        orchestrator = CalibrationOrchestrator(
            config=config,
            alignment_engine=engine,
            scorer=scorer,
            adapter_dispatch={"codex": gt_adapter, "deepseek-r1": ch_adapter},
        )
        result = await orchestrator.run("test plan content")
        assert result.success is False
        assert "Ground truth model failed" in (result.error or "")
        assert len(result.challenger_results) == 0
        ch_adapter.assert_not_called()

    @pytest.mark.asyncio
    async def test_challenger_failure_produces_error_result(
        self,
        config: CalibrationConfig,
        engine: FindingAlignmentEngine,
        scorer: CalibrationScorer,
    ) -> None:
        gt_adapter = AsyncMock(return_value=_make_review_result("codex"))
        ch_adapter = AsyncMock(return_value=_make_failed_result("deepseek-r1"))
        orchestrator = CalibrationOrchestrator(
            config=config,
            alignment_engine=engine,
            scorer=scorer,
            adapter_dispatch={"codex": gt_adapter, "deepseek-r1": ch_adapter},
        )
        result = await orchestrator.run("test plan content")
        assert result.success is True
        assert len(result.challenger_results) == 1
        assert result.challenger_results[0].metrics is None
        assert result.challenger_results[0].error is not None

    @pytest.mark.asyncio
    async def test_prompt_version_propagated(
        self,
        config: CalibrationConfig,
        engine: FindingAlignmentEngine,
        scorer: CalibrationScorer,
    ) -> None:
        gt_adapter = AsyncMock(return_value=_make_review_result("codex"))
        ch_result = _make_review_result("deepseek-r1")
        ch_adapter = AsyncMock(return_value=ch_result)
        orchestrator = CalibrationOrchestrator(
            config=config,
            alignment_engine=engine,
            scorer=scorer,
            adapter_dispatch={"codex": gt_adapter, "deepseek-r1": ch_adapter},
        )
        result = await orchestrator.run("test plan content")
        assert result.challenger_results[0].prompt_version == "1.1.0"

    @pytest.mark.asyncio
    async def test_multiple_challengers(
        self,
        engine: FindingAlignmentEngine,
        scorer: CalibrationScorer,
    ) -> None:
        config = CalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["deepseek-r1", "qwen3-coder"],
            similarity_threshold=0.3,
        )
        gt_adapter = AsyncMock(return_value=_make_review_result("codex"))
        ch1_adapter = AsyncMock(return_value=_make_review_result("deepseek-r1"))
        ch2_adapter = AsyncMock(return_value=_make_review_result("qwen3-coder"))
        orchestrator = CalibrationOrchestrator(
            config=config,
            alignment_engine=engine,
            scorer=scorer,
            adapter_dispatch={
                "codex": gt_adapter,
                "deepseek-r1": ch1_adapter,
                "qwen3-coder": ch2_adapter,
            },
        )
        result = await orchestrator.run("test plan content")
        assert result.success is True
        assert len(result.challenger_results) == 2
