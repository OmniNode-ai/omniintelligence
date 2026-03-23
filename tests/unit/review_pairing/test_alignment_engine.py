# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for FindingAlignmentEngine.

TDD: Tests written first for OMN-6167.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from omniintelligence.review_pairing.alignment_engine import FindingAlignmentEngine
from omniintelligence.review_pairing.models_calibration import (
    CalibrationFindingTuple,
)


def _make_finding(
    category: str = "architecture",
    location: str | None = "file.py",
    description: str = "Issue found",
    severity: str = "error",
    source: str = "codex",
) -> CalibrationFindingTuple:
    return CalibrationFindingTuple(
        category=category,
        location=location,
        description=description,
        severity=severity,
        source_model=source,
        finding_id=uuid4(),
        raw_finding=None,
    )


@pytest.mark.unit
class TestFindingAlignmentEngine:
    """Tests for the FindingAlignmentEngine."""

    @pytest.mark.asyncio
    async def test_identical_findings_align(self) -> None:
        engine = FindingAlignmentEngine(similarity_threshold=0.7)
        gt = [_make_finding(description="Missing error handling in auth module")]
        ch = [
            _make_finding(
                description="Missing error handling in auth module",
                source="deepseek-r1",
            )
        ]
        alignments = await engine.align(gt, ch)
        tp = [a for a in alignments if a.alignment_type == "true_positive"]
        assert len(tp) == 1
        assert tp[0].similarity_score == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_completely_different_no_alignment(self) -> None:
        engine = FindingAlignmentEngine(similarity_threshold=0.7)
        gt = [
            _make_finding(
                category="security",
                description="SQL injection vulnerability in database layer",
            )
        ]
        ch = [
            _make_finding(
                category="style",
                description="Variable naming convention inconsistency",
                source="deepseek-r1",
            )
        ]
        alignments = await engine.align(gt, ch)
        fp = [a for a in alignments if a.alignment_type == "false_positive"]
        fn = [a for a in alignments if a.alignment_type == "false_negative"]
        assert len(fp) == 1
        assert len(fn) == 1

    @pytest.mark.asyncio
    async def test_empty_ground_truth(self) -> None:
        engine = FindingAlignmentEngine(similarity_threshold=0.7)
        ch = [_make_finding(source="deepseek-r1")]
        alignments = await engine.align([], ch)
        assert len(alignments) == 1
        assert alignments[0].alignment_type == "false_positive"
        assert alignments[0].ground_truth is None

    @pytest.mark.asyncio
    async def test_empty_challenger(self) -> None:
        engine = FindingAlignmentEngine(similarity_threshold=0.7)
        gt = [_make_finding()]
        alignments = await engine.align(gt, [])
        assert len(alignments) == 1
        assert alignments[0].alignment_type == "false_negative"
        assert alignments[0].challenger is None

    @pytest.mark.asyncio
    async def test_both_empty(self) -> None:
        engine = FindingAlignmentEngine(similarity_threshold=0.7)
        alignments = await engine.align([], [])
        assert len(alignments) == 0

    @pytest.mark.asyncio
    async def test_embedding_model_version_set(self) -> None:
        engine = FindingAlignmentEngine(similarity_threshold=0.7)
        gt = [_make_finding(description="Test finding")]
        ch = [_make_finding(description="Test finding", source="deepseek-r1")]
        alignments = await engine.align(gt, ch)
        for a in alignments:
            assert a.embedding_model_version == "jaccard-v1"

    @pytest.mark.asyncio
    async def test_category_family_boost(self) -> None:
        families = {"design": ["architecture", "structure"]}
        engine = FindingAlignmentEngine(
            similarity_threshold=0.5,
            category_families=families,
        )
        gt = [
            _make_finding(
                category="architecture",
                description="poor separation of concerns in module design",
            )
        ]
        ch = [
            _make_finding(
                category="structure",
                description="poor separation of concerns in module design",
                source="deepseek-r1",
            )
        ]
        alignments = await engine.align(gt, ch)
        tp = [a for a in alignments if a.alignment_type == "true_positive"]
        assert len(tp) == 1

    @pytest.mark.asyncio
    async def test_multiple_findings_hungarian_optimal(self) -> None:
        """Verify Hungarian matching finds globally optimal assignment."""
        engine = FindingAlignmentEngine(similarity_threshold=0.3)
        gt = [
            _make_finding(description="Missing error handling"),
            _make_finding(description="SQL injection risk"),
        ]
        ch = [
            _make_finding(
                description="SQL injection vulnerability", source="deepseek-r1"
            ),
            _make_finding(
                description="Missing error handling in API", source="deepseek-r1"
            ),
        ]
        alignments = await engine.align(gt, ch)
        tp = [a for a in alignments if a.alignment_type == "true_positive"]
        # Hungarian should match optimally: "Missing error handling" <-> "Missing error handling in API"
        # and "SQL injection risk" <-> "SQL injection vulnerability"
        assert len(tp) == 2
