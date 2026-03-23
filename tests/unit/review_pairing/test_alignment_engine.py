# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the Finding Alignment Engine.

Reference: OMN-6167 (epic OMN-6164)
"""

from __future__ import annotations

import pytest

from omniintelligence.review_pairing.alignment_engine import (
    FindingAlignmentEngine,
    _jaccard_similarity,
)
from omniintelligence.review_pairing.models_calibration import (
    CalibrationFindingTuple,
)


def _make_finding(
    category: str = "architecture",
    location: str | None = "Task 1",
    description: str = "Missing error handling",
    model: str = "codex",
) -> CalibrationFindingTuple:
    return CalibrationFindingTuple(
        category=category,
        location=location,
        description=description,
        severity="error",
        source_model=model,
    )


@pytest.mark.unit
class TestJaccardSimilarity:
    def test_identical(self) -> None:
        assert _jaccard_similarity("hello world", "hello world") == 1.0

    def test_no_overlap(self) -> None:
        assert _jaccard_similarity("hello world", "foo bar") == 0.0

    def test_partial_overlap(self) -> None:
        score = _jaccard_similarity("hello world foo", "hello bar foo")
        assert 0.0 < score < 1.0

    def test_case_insensitive(self) -> None:
        assert _jaccard_similarity("Hello World", "hello world") == 1.0

    def test_both_empty(self) -> None:
        assert _jaccard_similarity("", "") == 1.0

    def test_one_empty(self) -> None:
        assert _jaccard_similarity("hello", "") == 0.0


@pytest.mark.unit
class TestFindingAlignmentEngine:
    @pytest.fixture
    def engine(self) -> FindingAlignmentEngine:
        return FindingAlignmentEngine(
            similarity_threshold=0.5,
            category_families={"design": ["architecture", "structure"]},
        )

    @pytest.mark.asyncio
    async def test_identical_findings_align(
        self, engine: FindingAlignmentEngine
    ) -> None:
        gt = [_make_finding(description="Missing error handling in retry logic")]
        ch = [
            _make_finding(
                description="Missing error handling in retry logic",
                model="deepseek-r1",
            )
        ]
        results = await engine.align(gt, ch)
        tp = [r for r in results if r.alignment_type == "true_positive"]
        assert len(tp) == 1
        assert tp[0].similarity_score == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_completely_different_findings(
        self, engine: FindingAlignmentEngine
    ) -> None:
        gt = [_make_finding(description="Missing error handling in retry logic")]
        ch = [
            _make_finding(
                description="Database schema needs normalization",
                category="performance",
                model="deepseek-r1",
            )
        ]
        results = await engine.align(gt, ch)
        fn = [r for r in results if r.alignment_type == "false_negative"]
        fp = [r for r in results if r.alignment_type == "false_positive"]
        assert len(fn) == 1
        assert len(fp) == 1

    @pytest.mark.asyncio
    async def test_empty_ground_truth(self, engine: FindingAlignmentEngine) -> None:
        ch = [_make_finding(model="deepseek-r1")]
        results = await engine.align([], ch)
        assert len(results) == 0 or all(
            r.alignment_type == "false_positive" for r in results
        )

    @pytest.mark.asyncio
    async def test_empty_challenger(self, engine: FindingAlignmentEngine) -> None:
        gt = [_make_finding()]
        results = await engine.align(gt, [])
        assert len(results) == 1
        assert results[0].alignment_type == "false_negative"

    @pytest.mark.asyncio
    async def test_both_empty(self, engine: FindingAlignmentEngine) -> None:
        results = await engine.align([], [])
        assert results == []

    @pytest.mark.asyncio
    async def test_embedding_model_version_set(
        self, engine: FindingAlignmentEngine
    ) -> None:
        gt = [_make_finding()]
        ch = [_make_finding(model="deepseek-r1")]
        results = await engine.align(gt, ch)
        for r in results:
            assert r.embedding_model_version == "jaccard-v1"

    @pytest.mark.asyncio
    async def test_related_category_can_align(
        self, engine: FindingAlignmentEngine
    ) -> None:
        """Categories in the same family get 0.5 category_sim boost."""
        gt = [
            _make_finding(
                category="architecture",
                description="Missing error handling in retry logic",
            )
        ]
        ch = [
            _make_finding(
                category="structure",
                description="Missing error handling in retry logic",
                model="deepseek-r1",
            )
        ]
        results = await engine.align(gt, ch)
        tp = [r for r in results if r.alignment_type == "true_positive"]
        assert len(tp) == 1

    @pytest.mark.asyncio
    async def test_location_substring_match(
        self, engine: FindingAlignmentEngine
    ) -> None:
        gt = [
            _make_finding(
                location="Task 5",
                description="Missing error handling in retry logic",
            )
        ]
        ch = [
            _make_finding(
                location="Task 5: Calibration Run Orchestrator",
                description="Missing error handling in retry logic",
                model="deepseek-r1",
            )
        ]
        results = await engine.align(gt, ch)
        tp = [r for r in results if r.alignment_type == "true_positive"]
        assert len(tp) == 1

    @pytest.mark.asyncio
    async def test_multiple_findings_optimal_matching(
        self, engine: FindingAlignmentEngine
    ) -> None:
        """Hungarian matching should produce globally optimal assignment."""
        gt = [
            _make_finding(description="Missing error handling"),
            _make_finding(description="Race condition in async code"),
        ]
        ch = [
            _make_finding(
                description="Race condition in async code", model="deepseek-r1"
            ),
            _make_finding(description="Missing error handling", model="deepseek-r1"),
        ]
        results = await engine.align(gt, ch)
        tp = [r for r in results if r.alignment_type == "true_positive"]
        assert len(tp) == 2
