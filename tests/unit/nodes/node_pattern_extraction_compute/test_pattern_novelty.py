# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for pattern novelty scoring (OMN-6966).

Verifies that:
- Exact duplicates are rejected (novelty_score ~ 0)
- Near-duplicates (>90% overlap) are rejected
- Genuinely novel patterns pass through
- Within-batch duplicates are caught
- Metadata includes novelty_score for accepted patterns
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_novelty import (
    ModelNoveltyResult,
    filter_novel_patterns,
    score_novelty,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.enum_insight_type import (
    EnumInsightType,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_insight import (
    ModelCodebaseInsight,
)


def _make_pattern(
    *,
    insight_id: str = "test-pattern",
    files: tuple[str, ...] = (),
    description: str = "test pattern",
    insight_type: EnumInsightType = EnumInsightType.FILE_ACCESS_PATTERN,
    confidence: float = 0.8,
) -> ModelCodebaseInsight:
    """Create a test pattern with the given evidence files."""
    now = datetime.now(UTC)
    return ModelCodebaseInsight(
        insight_id=insight_id,
        insight_type=insight_type,
        description=description,
        confidence=confidence,
        evidence_files=files,
        first_observed=now,
        last_observed=now,
    )


class TestScoreNovelty:
    """Tests for the score_novelty function."""

    @pytest.mark.unit
    def test_exact_duplicate_has_zero_novelty(self) -> None:
        """A pattern with identical files to an existing one scores ~0."""
        existing = [
            _make_pattern(insight_id="existing", files=("a.py", "b.py", "c.py"))
        ]
        candidate = _make_pattern(
            insight_id="candidate", files=("a.py", "b.py", "c.py")
        )

        result = score_novelty(candidate, existing)
        assert result.novelty_score < 0.1, f"Expected <0.1, got {result.novelty_score}"
        assert result.most_similar_id == "existing"

    @pytest.mark.unit
    def test_completely_novel_pattern(self) -> None:
        """A pattern with no file overlap scores 1.0."""
        existing = [_make_pattern(insight_id="existing", files=("a.py", "b.py"))]
        candidate = _make_pattern(insight_id="candidate", files=("x.py", "y.py"))

        result = score_novelty(candidate, existing)
        assert result.novelty_score == 1.0

    @pytest.mark.unit
    def test_partial_overlap_scores_intermediate(self) -> None:
        """66% overlap -> novelty ~ 0.34."""
        existing = [
            _make_pattern(insight_id="existing", files=("a.py", "b.py", "c.py"))
        ]
        candidate = _make_pattern(
            insight_id="candidate", files=("a.py", "b.py", "d.py")
        )

        result = score_novelty(candidate, existing)
        # Jaccard: 2/4 = 0.5, novelty = 0.5
        assert 0.1 < result.novelty_score < 0.9

    @pytest.mark.unit
    def test_near_duplicate_high_overlap(self) -> None:
        """90%+ overlap should yield novelty < 0.1."""
        existing = [
            _make_pattern(
                insight_id="existing",
                files=(
                    "a.py",
                    "b.py",
                    "c.py",
                    "d.py",
                    "e.py",
                    "f.py",
                    "g.py",
                    "h.py",
                    "i.py",
                    "j.py",
                ),
            )
        ]
        # 9 out of 10 files overlap -> Jaccard 9/11 ~ 0.818 -> novelty ~ 0.18
        # Need 10/11 for novelty < 0.1
        candidate_files = (
            "a.py",
            "b.py",
            "c.py",
            "d.py",
            "e.py",
            "f.py",
            "g.py",
            "h.py",
            "i.py",
            "k.py",
        )
        candidate = _make_pattern(insight_id="candidate", files=candidate_files)
        result = score_novelty(candidate, existing)
        # 9/11 = 0.818 overlap -> novelty = 0.182 -- passes threshold
        assert result.novelty_score > 0.1

        # True near-duplicate: 10/10 overlap + 1 extra -> Jaccard 10/11 ~ 0.909
        near_dup_files = (
            "a.py",
            "b.py",
            "c.py",
            "d.py",
            "e.py",
            "f.py",
            "g.py",
            "h.py",
            "i.py",
            "j.py",
            "k.py",
        )
        near_dup = _make_pattern(insight_id="near_dup", files=near_dup_files)
        result2 = score_novelty(near_dup, existing)
        # Jaccard 10/11 = 0.909 -> novelty = 0.091 -> rejected
        assert result2.novelty_score < 0.1

    @pytest.mark.unit
    def test_empty_existing_always_novel(self) -> None:
        """With no existing patterns, everything is novel."""
        candidate = _make_pattern(files=("a.py",))
        result = score_novelty(candidate, [])
        assert result.novelty_score == 1.0
        assert result.most_similar_id is None

    @pytest.mark.unit
    def test_cross_type_not_compared(self) -> None:
        """Patterns of different types should not reduce novelty."""
        existing = [
            _make_pattern(
                insight_id="error-pattern",
                files=("a.py", "b.py"),
                insight_type=EnumInsightType.ERROR_PATTERN,
            )
        ]
        candidate = _make_pattern(
            insight_id="file-pattern",
            files=("a.py", "b.py"),
            insight_type=EnumInsightType.FILE_ACCESS_PATTERN,
        )
        result = score_novelty(candidate, existing)
        assert result.novelty_score == 1.0

    @pytest.mark.unit
    def test_description_fallback_when_no_files(self) -> None:
        """When patterns have no files, description tokens are used."""
        existing = [_make_pattern(insight_id="e1", description="common error pattern")]
        candidate = _make_pattern(insight_id="c1", description="common error pattern")

        result = score_novelty(candidate, existing)
        assert result.novelty_score < 0.1


class TestFilterNovelPatterns:
    """Tests for the filter_novel_patterns function."""

    @pytest.mark.unit
    def test_rejects_exact_duplicates(self) -> None:
        """Exact duplicates should be rejected."""
        existing = [_make_pattern(insight_id="e1", files=("a.py", "b.py"))]
        new = [_make_pattern(insight_id="n1", files=("a.py", "b.py"))]

        accepted, rejected = filter_novel_patterns(new, existing)
        assert len(accepted) == 0
        assert len(rejected) == 1

    @pytest.mark.unit
    def test_accepts_novel_patterns(self) -> None:
        """Novel patterns should pass through with novelty_score in metadata."""
        existing = [_make_pattern(insight_id="e1", files=("a.py",))]
        new = [_make_pattern(insight_id="n1", files=("x.py", "y.py"))]

        accepted, rejected = filter_novel_patterns(new, existing)
        assert len(accepted) == 1
        assert len(rejected) == 0
        assert "novelty_score" in accepted[0].metadata
        assert accepted[0].metadata["novelty_score"] > 0.1

    @pytest.mark.unit
    def test_within_batch_duplicate_detection(self) -> None:
        """Second pattern in batch that duplicates first should be rejected."""
        existing: list[ModelCodebaseInsight] = []
        new = [
            _make_pattern(insight_id="n1", files=("a.py", "b.py")),
            _make_pattern(insight_id="n2", files=("a.py", "b.py")),
        ]

        accepted, rejected = filter_novel_patterns(new, existing)
        assert len(accepted) == 1
        assert len(rejected) == 1
        assert accepted[0].insight_id == "n1"

    @pytest.mark.unit
    def test_custom_threshold(self) -> None:
        """Higher threshold rejects more patterns."""
        existing = [_make_pattern(insight_id="e1", files=("a.py", "b.py", "c.py"))]
        # 2/4 = 0.5 Jaccard -> novelty = 0.5
        new = [_make_pattern(insight_id="n1", files=("a.py", "b.py", "d.py"))]

        # With default threshold 0.1, should pass
        accepted_low, _ = filter_novel_patterns(new, existing, novelty_threshold=0.1)
        assert len(accepted_low) == 1

        # With high threshold 0.6, should be rejected
        accepted_high, _ = filter_novel_patterns(new, existing, novelty_threshold=0.6)
        assert len(accepted_high) == 0

    @pytest.mark.unit
    def test_novelty_score_model(self) -> None:
        """ModelNoveltyResult validates field constraints."""
        result = ModelNoveltyResult(novelty_score=0.5, jaccard_overlap=0.5)
        assert result.novelty_score == 0.5
        assert result.most_similar_id is None
