# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Calibration Run Orchestrator.

Coordinates ground-truth and challenger model reviews, serializes findings,
runs alignment, and scores metrics for each challenger.

Reference: OMN-6169
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

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
from omniintelligence.review_pairing.serializer_r1r6 import serialize_external_finding

logger = logging.getLogger(__name__)

AdapterFunc = Callable[..., Awaitable[ModelExternalReviewResult]]


class CalibrationOrchestrator:
    """Orchestrates calibration runs across ground-truth and challenger models.

    Args:
        config: Calibration configuration.
        codex_adapter: Async function matching the codex adapter_codex_reviewer.async_parse_raw
            signature.
        ai_adapter: Async function matching the adapter_ai_reviewer.async_parse_raw signature.
        alignment_engine: Optional pre-configured alignment engine. Built from config if None.
        scorer: Optional pre-configured scorer. Uses default if None.
    """

    def __init__(
        self,
        config: CalibrationConfig,
        codex_adapter: AdapterFunc,
        ai_adapter: AdapterFunc,
        alignment_engine: FindingAlignmentEngine | None = None,
        scorer: CalibrationScorer | None = None,
    ) -> None:
        self._config = config
        self._codex_adapter = codex_adapter
        self._ai_adapter = ai_adapter
        self._alignment_engine = alignment_engine or FindingAlignmentEngine(
            similarity_threshold=config.similarity_threshold,
            category_families=config.category_families,
        )
        self._scorer = scorer or CalibrationScorer()

    async def run(
        self,
        content: str,
        review_type: str = "plan",
    ) -> CalibrationOrchestrationResult:
        """Execute a full calibration run.

        Args:
            content: Content to review (plan text or PR diff).
            review_type: Review type passed to adapters.

        Returns:
            CalibrationOrchestrationResult with per-challenger results.
        """
        # 1. Run ground truth model
        gt_result = await self._call_model(
            self._config.ground_truth_model, content, review_type=review_type
        )

        if not gt_result.success:
            return CalibrationOrchestrationResult(
                success=False,
                error=(
                    f"Ground truth model '{self._config.ground_truth_model}' failed: "
                    f"{gt_result.error}"
                ),
                ground_truth_findings=[],
                challenger_results=[],
            )

        # 2. Serialize ground truth findings
        gt_tuples = [serialize_external_finding(f) for f in gt_result.findings]

        # 3. Run challengers concurrently (bounded by max_concurrent_challengers)
        sem = asyncio.Semaphore(self._config.max_concurrent_challengers)
        challenger_results = await asyncio.gather(
            *(
                self._run_challenger(
                    challenger_model=model,
                    content=content,
                    review_type=review_type,
                    gt_tuples=gt_tuples,
                    gt_prompt_version=gt_result.prompt_version,
                    sem=sem,
                )
                for model in self._config.challenger_models
            )
        )

        return CalibrationOrchestrationResult(
            success=True,
            ground_truth_findings=gt_tuples,
            challenger_results=list(challenger_results),
        )

    async def _call_model(
        self,
        model_key: str,
        content: str,
        review_type: str = "plan",
    ) -> ModelExternalReviewResult:
        """Dispatch to the correct adapter based on model key."""
        if model_key == "codex":
            return await self._codex_adapter(content, review_type=review_type)
        return await self._ai_adapter(content, model=model_key, review_type=review_type)

    async def _run_challenger(
        self,
        challenger_model: str,
        content: str,
        review_type: str,
        gt_tuples: list[CalibrationFindingTuple],
        gt_prompt_version: str,
        sem: asyncio.Semaphore,
    ) -> CalibrationRunResult:
        """Run a single challenger model and produce a CalibrationRunResult."""
        run_id = str(uuid.uuid4())
        now = datetime.now(tz=UTC)

        async with sem:
            ch_result = await self._call_model(
                challenger_model, content, review_type=review_type
            )

        if not ch_result.success:
            return CalibrationRunResult(
                run_id=run_id,
                ground_truth_model=self._config.ground_truth_model,
                challenger_model=challenger_model,
                alignments=[],
                metrics=None,
                prompt_version=ch_result.prompt_version,
                error=ch_result.error,
                created_at=now,
            )

        # Serialize challenger findings
        ch_tuples = [serialize_external_finding(f) for f in ch_result.findings]

        # Align
        alignments = await self._alignment_engine.align(gt_tuples, ch_tuples)

        # Score
        metrics = self._scorer.score(alignments, model=challenger_model)

        return CalibrationRunResult(
            run_id=run_id,
            ground_truth_model=self._config.ground_truth_model,
            challenger_model=challenger_model,
            alignments=alignments,
            metrics=metrics,
            prompt_version=ch_result.prompt_version,
            embedding_model_version=self._alignment_engine._get_model_version(),
            created_at=now,
        )
