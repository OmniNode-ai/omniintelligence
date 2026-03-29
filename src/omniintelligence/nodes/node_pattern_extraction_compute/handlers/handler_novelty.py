# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern novelty scoring using Jaccard similarity.

Computes a novelty score for each new pattern by comparing its evidence
files (or metadata signature) against existing patterns. Patterns with
novelty_score < threshold are considered near-duplicates and should be
dropped.

Novelty is defined as 1 - max_overlap, where max_overlap is the maximum
Jaccard similarity between the new pattern and any existing pattern of
the same type.

Ticket: OMN-6966
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_insight import (
    ModelCodebaseInsight,
)


class ModelNoveltyResult(BaseModel):
    """Result of a novelty score computation.

    Attributes:
        novelty_score: Value in [0, 1]. 0 = exact duplicate, 1 = completely novel.
        most_similar_id: ID of the most similar existing pattern, if any.
        jaccard_overlap: Maximum Jaccard overlap found.
    """

    novelty_score: float = Field(ge=0.0, le=1.0)
    most_similar_id: str | None = None
    jaccard_overlap: float = Field(default=0.0, ge=0.0, le=1.0)


def _jaccard_similarity(set_a: frozenset[str], set_b: frozenset[str]) -> float:
    """Compute Jaccard similarity between two sets.

    Returns 0.0 if both sets are empty (no overlap is possible).
    """
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return intersection / union


def _pattern_signature(pattern: ModelCodebaseInsight) -> frozenset[str]:
    """Extract a comparable signature from a pattern.

    Uses evidence_files as the primary signal. If no files are present,
    falls back to a set derived from the description tokens (words).
    """
    if pattern.evidence_files:
        return frozenset(pattern.evidence_files)
    # Fallback: use description tokens for patterns without file evidence
    return frozenset(pattern.description.lower().split())


def score_novelty(
    candidate: ModelCodebaseInsight,
    existing_patterns: list[ModelCodebaseInsight] | tuple[ModelCodebaseInsight, ...],
) -> ModelNoveltyResult:
    """Score the novelty of a candidate pattern against existing patterns.

    Compares only against patterns of the same insight_type, since
    cross-type overlap is expected and acceptable.

    Args:
        candidate: The new pattern to score.
        existing_patterns: Existing patterns to compare against.

    Returns:
        ModelNoveltyResult with novelty_score and similarity details.
    """
    candidate_sig = _pattern_signature(candidate)
    max_overlap = 0.0
    most_similar_id: str | None = None

    for existing in existing_patterns:
        # Only compare patterns of the same type
        if existing.insight_type != candidate.insight_type:
            continue
        existing_sig = _pattern_signature(existing)
        overlap = _jaccard_similarity(candidate_sig, existing_sig)
        if overlap > max_overlap:
            max_overlap = overlap
            most_similar_id = existing.insight_id

    return ModelNoveltyResult(
        novelty_score=round(1.0 - max_overlap, 4),
        most_similar_id=most_similar_id,
        jaccard_overlap=round(max_overlap, 4),
    )


def filter_novel_patterns(
    new_patterns: list[ModelCodebaseInsight],
    existing_patterns: list[ModelCodebaseInsight] | tuple[ModelCodebaseInsight, ...],
    *,
    novelty_threshold: float = 0.1,
) -> tuple[list[ModelCodebaseInsight], list[ModelCodebaseInsight]]:
    """Filter patterns by novelty, keeping only sufficiently novel ones.

    Each retained pattern gets a ``novelty_score`` key added to its
    metadata. Rejected patterns are returned separately for logging.

    Args:
        new_patterns: Candidate patterns to filter.
        existing_patterns: Existing patterns to compare against.
        novelty_threshold: Minimum novelty score to keep (default 0.1).

    Returns:
        Tuple of (accepted_patterns, rejected_patterns).
    """
    accepted: list[ModelCodebaseInsight] = []
    rejected: list[ModelCodebaseInsight] = []

    # Build a growing set of accepted patterns so that within-batch
    # near-duplicates are also caught.
    comparison_pool = list(existing_patterns)

    for pattern in new_patterns:
        result = score_novelty(pattern, comparison_pool)
        if result.novelty_score >= novelty_threshold:
            # Add novelty_score to metadata (model is frozen, so rebuild)
            updated_metadata = {
                **pattern.metadata,
                "novelty_score": result.novelty_score,
            }
            accepted_pattern = pattern.model_copy(update={"metadata": updated_metadata})
            accepted.append(accepted_pattern)
            comparison_pool.append(accepted_pattern)
        else:
            rejected.append(pattern)

    return accepted, rejected


__all__ = [
    "ModelNoveltyResult",
    "filter_novel_patterns",
    "score_novelty",
]
