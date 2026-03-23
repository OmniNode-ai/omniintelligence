# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Calibration Run Orchestrator.

Coordinates ground-truth and challenger model executions, serializes findings,
runs alignment, and produces scored calibration results.

Reference: OMN-6169 (epic OMN-6164)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from omniintelligence.review_pairing.alignment_engine import FindingAlignmentEngine
from omniintelligence.review_pairing.calibration_scorer import CalibrationScorer
from omniintelligence.review_pairing.models_calibration import (
    CalibrationConfig,
    CalibrationFindingTuple,
    CalibrationOrchestrationResult,
    CalibrationRunResult,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
)
from omniintelligence.review_pairing.serializer_r1r6 import (
    serialize_external_finding,
)

logger = logging.getLogger(__name__)


class ReviewAdapter(Protocol):
    """Protocol for review adapter dispatch."""

    async def __call__(
        self, content: str, **kwargs: Any
    ) -> ModelExternalReviewResult: ...


class CalibrationOrchestrator:
    """Orchestrates calibration runs across ground-truth and challenger models."""

    def __init__(
        self,
        config: CalibrationConfig,
        alignment_engine: FindingAlignmentEngine,
        scorer: CalibrationScorer,
        adapter_dispatch: dict[str, ReviewAdapter] | None = None,
    ) -> None:
        self._config = config
        self._engine = alignment_engine
        self._scorer = scorer
        self._adapter_dispatch = adapter_dispatch or {}

    async def run(
        self, content: str, review_type: str = "plan"
    ) -> CalibrationOrchestrationResult:
        """Execute a full calibration run.

        Args:
            content: Document content to review.
            review_type: Type of review (default: "plan").

        Returns:
            CalibrationOrchestrationResult with ground-truth findings
            and per-challenger results.
        """
        run_id = str(uuid4())

        gt_result = await self._run_model(
            self._config.ground_truth_model, content, review_type
        )
        if gt_result is None or not gt_result.success:
            error_msg = (
                gt_result.error
                if gt_result is not None
                else "Ground truth adapter not found"
            )
            return CalibrationOrchestrationResult(
                success=False,
                error=f"Ground truth model failed: {error_msg}",
            )

        gt_findings = [serialize_external_finding(f) for f in gt_result.findings]

        semaphore = asyncio.Semaphore(self._config.max_concurrent_challengers)
        tasks = [
            self._run_challenger(
                run_id=run_id,
                challenger_model=model,
                content=content,
                review_type=review_type,
                gt_findings=gt_findings,
                prompt_version=gt_result.prompt_version,
                semaphore=semaphore,
            )
            for model in self._config.challenger_models
        ]

        results = await asyncio.gather(*tasks)

        return CalibrationOrchestrationResult(
            success=True,
            ground_truth_findings=gt_findings,
            challenger_results=list(results),
        )

    async def _run_model(
        self, model_key: str, content: str, review_type: str
    ) -> ModelExternalReviewResult | None:
        """Dispatch a model review via the adapter registry."""
        adapter = self._adapter_dispatch.get(model_key)
        if adapter is None:
            return None
        try:
            return await adapter(content, model=model_key, review_type=review_type)
        except Exception as e:
            logger.exception("Model %s failed", model_key)
            return ModelExternalReviewResult(
                model=model_key,
                prompt_version="unknown",
                success=False,
                error=str(e),
            )

    async def _run_challenger(
        self,
        run_id: str,
        challenger_model: str,
        content: str,
        review_type: str,
        gt_findings: list[CalibrationFindingTuple],
        prompt_version: str,
        semaphore: asyncio.Semaphore,
    ) -> CalibrationRunResult:
        """Run a single challenger and produce a CalibrationRunResult."""
        async with semaphore:
            ch_result = await self._run_model(challenger_model, content, review_type)

        now = datetime.now(timezone.utc)

        if ch_result is None or not ch_result.success:
            error_msg = (
                ch_result.error
                if ch_result is not None
                else f"Adapter not found for {challenger_model}"
            )
            return CalibrationRunResult(
                run_id=run_id,
                ground_truth_model=self._config.ground_truth_model,
                challenger_model=challenger_model,
                alignments=[],
                metrics=None,
                prompt_version=prompt_version,
                error=error_msg,
                created_at=now,
            )

        ch_findings = [serialize_external_finding(f) for f in ch_result.findings]

        alignments = await self._engine.align(gt_findings, ch_findings)
        metrics = self._scorer.score(
            alignments,
            ground_truth_count=len(gt_findings),
            challenger_count=len(ch_findings),
            model=challenger_model,
        )

        return CalibrationRunResult(
            run_id=run_id,
            ground_truth_model=self._config.ground_truth_model,
            challenger_model=challenger_model,
            alignments=alignments,
            metrics=metrics,
            prompt_version=ch_result.prompt_version,
            created_at=now,
        )
