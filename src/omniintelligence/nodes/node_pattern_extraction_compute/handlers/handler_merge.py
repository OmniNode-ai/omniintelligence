"""Insight merging for deduplication.

This module provides functions for merging duplicate insights,
combining evidence and updating metadata when the same pattern
is observed multiple times.
"""

from __future__ import annotations

from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelCodebaseInsight,
)


def merge_insights(
    new: ModelCodebaseInsight,
    existing: ModelCodebaseInsight,
) -> ModelCodebaseInsight:
    """Merge duplicate insights, updating confidence and evidence.

    When the same insight is observed multiple times (same identity key),
    this function combines the evidence from both observations while
    preserving the most confident description and updating counts.

    Merge Rules:
        - insight_id: Preserved from existing (canonical ID)
        - insight_type: Preserved from existing (must match)
        - description: Uses the description with higher confidence
        - confidence: Takes the maximum of both
        - evidence_files: Union of both sets
        - evidence_session_ids: Union of both sets
        - occurrence_count: Sum of both counts
        - first_observed: Takes the earlier timestamp
        - last_observed: Takes the later timestamp
        - working_directory: Preserved from existing
        - metadata: Merged from both (existing values take precedence)

    Args:
        new: The newly observed insight to merge.
        existing: The existing insight to merge into.

    Returns:
        A new ModelCodebaseInsight with merged data.

    Example:
        >>> from datetime import datetime, timedelta
        >>> existing = ModelCodebaseInsight(
        ...     insight_id="insight-1",
        ...     insight_type=EnumInsightType.FILE_ACCESS_PATTERN,
        ...     description="Old description",
        ...     confidence=0.7,
        ...     evidence_files=("a.py",),
        ...     evidence_session_ids=("s1",),
        ...     occurrence_count=2,
        ...     first_observed=datetime.now() - timedelta(days=1),
        ...     last_observed=datetime.now() - timedelta(hours=1),
        ... )
        >>> new = ModelCodebaseInsight(
        ...     insight_id="insight-2",
        ...     insight_type=EnumInsightType.FILE_ACCESS_PATTERN,
        ...     description="Better description",
        ...     confidence=0.9,
        ...     evidence_files=("b.py",),
        ...     evidence_session_ids=("s2",),
        ...     occurrence_count=1,
        ...     first_observed=datetime.now(),
        ...     last_observed=datetime.now(),
        ... )
        >>> merged = merge_insights(new, existing)
        >>> merged.confidence
        0.9
        >>> merged.occurrence_count
        3
        >>> set(merged.evidence_files) == {"a.py", "b.py"}
        True
    """
    # Determine which description to use based on confidence
    description = (
        new.description
        if new.confidence > existing.confidence
        else existing.description
    )

    # Merge evidence sets using union
    merged_files = tuple(set(existing.evidence_files) | set(new.evidence_files))
    merged_sessions = tuple(
        set(existing.evidence_session_ids) | set(new.evidence_session_ids)
    )

    # Merge metadata (new values override existing)
    merged_metadata = {**new.metadata, **existing.metadata}

    return ModelCodebaseInsight(
        insight_id=existing.insight_id,
        insight_type=existing.insight_type,
        description=description,
        confidence=max(new.confidence, existing.confidence),
        evidence_files=merged_files,
        evidence_session_ids=merged_sessions,
        occurrence_count=existing.occurrence_count + new.occurrence_count,
        first_observed=min(existing.first_observed, new.first_observed),
        last_observed=max(existing.last_observed, new.last_observed),
        working_directory=existing.working_directory,
        metadata=merged_metadata,
    )


__all__ = ["merge_insights"]
