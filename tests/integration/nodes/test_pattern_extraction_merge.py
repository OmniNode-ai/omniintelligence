# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Integration tests for insight merge behavior in extract_all_patterns.

Verifies that running two sequential extractions — where the second run
receives the first run's ``new_insights`` as ``existing_insights`` — produces
correct merge semantics:

1. Insights that appear in both runs are moved to ``updated_insights`` in the
   second run (not duplicated in ``new_insights``).
2. Merged insights accumulate occurrence counts from both runs.
3. Merged insights union evidence_files and evidence_session_ids.
4. Merged insights preserve the canonical ``insight_id`` from the first run.
5. Net-new insights (seen only in run 2) appear in ``new_insights``.

These are pure-compute integration tests — no database or Kafka required.
They exercise the full ``extract_all_patterns`` → ``_deduplicate_and_merge``
pipeline rather than testing the merge handler in isolation.

Ticket: OMN-1585
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.handlers import (
    extract_all_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelCodebaseInsight,
    ModelExtractionConfig,
    ModelPatternExtractionInput,
    ModelPatternExtractionOutput,
    ModelSessionSnapshot,
)

pytestmark = pytest.mark.integration

# =============================================================================
# Helpers
# =============================================================================

_BASE_TIME = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


def _make_session(
    session_id: str,
    files_accessed: tuple[str, ...],
    files_modified: tuple[str, ...] = (),
    offset_minutes: int = 0,
) -> ModelSessionSnapshot:
    """Create a minimal ModelSessionSnapshot for testing."""
    started = _BASE_TIME + timedelta(minutes=offset_minutes)
    ended = started + timedelta(minutes=30)
    return ModelSessionSnapshot(
        session_id=session_id,
        working_directory="/project",
        started_at=started,
        ended_at=ended,
        files_accessed=files_accessed,
        files_modified=files_modified,
    )


def _config(reference_time: datetime | None = None) -> ModelExtractionConfig:
    """Return a minimal config that enables architecture and file extractors."""
    return ModelExtractionConfig(
        extract_file_patterns=True,
        extract_error_patterns=False,
        extract_architecture_patterns=True,
        extract_tool_patterns=False,
        extract_tool_failure_patterns=False,
        min_pattern_occurrences=2,
        min_confidence=0.3,
        min_distinct_sessions=2,
        max_insights_per_type=100,
        reference_time=reference_time,
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def run1_sessions() -> tuple[ModelSessionSnapshot, ...]:
    """Four sessions that share a file access pattern (src/api/*.py)."""
    return (
        _make_session(
            "s1",
            files_accessed=("src/api/routes.py", "src/api/handlers.py"),
            offset_minutes=0,
        ),
        _make_session(
            "s2",
            files_accessed=("src/api/routes.py", "src/api/handlers.py"),
            files_modified=("src/api/routes.py",),
            offset_minutes=30,
        ),
        _make_session(
            "s3",
            files_accessed=("src/api/handlers.py", "src/models/user.py"),
            offset_minutes=60,
        ),
        _make_session(
            "s4",
            files_accessed=("src/api/routes.py", "src/models/user.py"),
            offset_minutes=90,
        ),
    )


@pytest.fixture
def run2_sessions(run1_sessions: tuple[ModelSessionSnapshot, ...]) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions for the second run.

    Overlaps with run1 (same files, different session IDs) to ensure
    merge happens, plus a new file pair to produce a net-new insight.
    """
    return (
        *run1_sessions,
        _make_session(
            "s5",
            files_accessed=("src/api/routes.py", "src/api/handlers.py"),
            offset_minutes=120,
        ),
        _make_session(
            "s6",
            files_accessed=("src/api/routes.py", "src/api/handlers.py"),
            files_modified=("src/api/handlers.py",),
            offset_minutes=150,
        ),
        # Net-new pattern: tests/ directory pair — only appears in run2
        _make_session(
            "s7",
            files_accessed=("tests/unit/test_api.py", "tests/unit/test_models.py"),
            offset_minutes=180,
        ),
        _make_session(
            "s8",
            files_accessed=("tests/unit/test_api.py", "tests/unit/test_models.py"),
            files_modified=("tests/unit/test_api.py",),
            offset_minutes=210,
        ),
    )


# =============================================================================
# Tests
# =============================================================================


def test_run1_produces_new_insights(
    run1_sessions: tuple[ModelSessionSnapshot, ...],
) -> None:
    """First extraction produces new_insights from fresh sessions."""
    input1 = ModelPatternExtractionInput(
        session_snapshots=run1_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=2)),
        existing_insights=(),
    )
    result1: ModelPatternExtractionOutput = extract_all_patterns(input1)

    assert result1.success is True, f"Run 1 failed: {result1.metadata}"
    assert len(result1.new_insights) > 0, "Run 1 must produce at least one new insight"
    assert len(result1.updated_insights) == 0, (
        "Run 1 has no existing insights to merge against"
    )


def test_run2_merges_overlapping_insights(
    run1_sessions: tuple[ModelSessionSnapshot, ...],
    run2_sessions: tuple[ModelSessionSnapshot, ...],
) -> None:
    """Second extraction merges insights that appeared in run 1.

    Insights seen in both runs appear in ``updated_insights`` in run 2,
    not duplicated in ``new_insights``.
    """
    # Run 1 — no existing insights
    input1 = ModelPatternExtractionInput(
        session_snapshots=run1_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=2)),
        existing_insights=(),
    )
    result1 = extract_all_patterns(input1)
    assert result1.success is True

    run1_insights = result1.new_insights
    assert len(run1_insights) > 0, "Need insights from run 1 to test merging"

    # Run 2 — pass run 1 insights as existing
    input2 = ModelPatternExtractionInput(
        session_snapshots=run2_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=5)),
        existing_insights=run1_insights,
    )
    result2 = extract_all_patterns(input2)
    assert result2.success is True, f"Run 2 failed: {result2.metadata}"

    # At least some insights should be updated (merged), not freshly created
    assert len(result2.updated_insights) > 0, (
        "Run 2 should merge at least some insights from run 1 into updated_insights. "
        f"Got {len(result2.updated_insights)} updated, {len(result2.new_insights)} new."
    )


def test_merged_insight_occurrence_count_increases(
    run1_sessions: tuple[ModelSessionSnapshot, ...],
    run2_sessions: tuple[ModelSessionSnapshot, ...],
) -> None:
    """Merged insights accumulate occurrence_count from both runs."""
    input1 = ModelPatternExtractionInput(
        session_snapshots=run1_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=2)),
        existing_insights=(),
    )
    result1 = extract_all_patterns(input1)
    assert result1.success

    run1_by_id = {i.insight_id: i for i in result1.new_insights}

    input2 = ModelPatternExtractionInput(
        session_snapshots=run2_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=5)),
        existing_insights=result1.new_insights,
    )
    result2 = extract_all_patterns(input2)
    assert result2.success

    for merged in result2.updated_insights:
        original = run1_by_id.get(merged.insight_id)
        if original is None:
            continue  # merged from an insight not in run1_by_id; skip
        assert merged.occurrence_count > original.occurrence_count, (
            f"Merged insight {merged.insight_id} occurrence_count "
            f"({merged.occurrence_count}) should exceed original "
            f"({original.occurrence_count})"
        )


def test_merged_insight_unions_evidence(
    run1_sessions: tuple[ModelSessionSnapshot, ...],
    run2_sessions: tuple[ModelSessionSnapshot, ...],
) -> None:
    """Merged insights contain evidence from both extraction runs."""
    input1 = ModelPatternExtractionInput(
        session_snapshots=run1_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=2)),
        existing_insights=(),
    )
    result1 = extract_all_patterns(input1)
    assert result1.success

    run1_sessions_per_id: dict[str, set[str]] = {
        i.insight_id: set(i.evidence_session_ids) for i in result1.new_insights
    }

    input2 = ModelPatternExtractionInput(
        session_snapshots=run2_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=5)),
        existing_insights=result1.new_insights,
    )
    result2 = extract_all_patterns(input2)
    assert result2.success

    for merged in result2.updated_insights:
        original_sessions = run1_sessions_per_id.get(merged.insight_id)
        if original_sessions is None:
            continue
        merged_sessions = set(merged.evidence_session_ids)
        # The merged insight must be a superset of the run1 evidence
        assert original_sessions <= merged_sessions, (
            f"Merged insight {merged.insight_id} evidence_session_ids "
            f"{merged_sessions} must be a superset of run1 sessions "
            f"{original_sessions}"
        )


def test_merged_insight_preserves_canonical_id(
    run1_sessions: tuple[ModelSessionSnapshot, ...],
    run2_sessions: tuple[ModelSessionSnapshot, ...],
) -> None:
    """The canonical insight_id from run 1 is preserved in the merged insight."""
    input1 = ModelPatternExtractionInput(
        session_snapshots=run1_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=2)),
        existing_insights=(),
    )
    result1 = extract_all_patterns(input1)
    assert result1.success

    run1_ids = {i.insight_id for i in result1.new_insights}

    input2 = ModelPatternExtractionInput(
        session_snapshots=run2_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=5)),
        existing_insights=result1.new_insights,
    )
    result2 = extract_all_patterns(input2)
    assert result2.success

    for merged in result2.updated_insights:
        assert merged.insight_id in run1_ids, (
            f"Merged insight_id {merged.insight_id!r} was not in run 1 insights. "
            "Canonical IDs must be preserved from the first extraction."
        )


def test_net_new_insights_not_in_updated(
    run1_sessions: tuple[ModelSessionSnapshot, ...],
    run2_sessions: tuple[ModelSessionSnapshot, ...],
) -> None:
    """Insights seen only in run 2 appear in new_insights, not updated_insights."""
    input1 = ModelPatternExtractionInput(
        session_snapshots=run1_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=2)),
        existing_insights=(),
    )
    result1 = extract_all_patterns(input1)
    assert result1.success

    run1_ids = {i.insight_id for i in result1.new_insights}

    input2 = ModelPatternExtractionInput(
        session_snapshots=run2_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=5)),
        existing_insights=result1.new_insights,
    )
    result2 = extract_all_patterns(input2)
    assert result2.success

    # Updated insights must all have IDs from run 1
    for updated in result2.updated_insights:
        assert updated.insight_id in run1_ids, (
            f"updated_insights entry {updated.insight_id!r} not in run1 IDs — "
            "it should be in new_insights instead"
        )

    # The two sets must be disjoint
    updated_ids = {i.insight_id for i in result2.updated_insights}
    new_ids = {i.insight_id for i in result2.new_insights}
    overlap = updated_ids & new_ids
    assert not overlap, (
        f"Insight IDs appear in both new_insights and updated_insights: {overlap}"
    )


def test_metrics_reflect_merge(
    run1_sessions: tuple[ModelSessionSnapshot, ...],
    run2_sessions: tuple[ModelSessionSnapshot, ...],
) -> None:
    """Extraction metrics accurately reflect new vs. updated insight counts."""
    input1 = ModelPatternExtractionInput(
        session_snapshots=run1_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=2)),
        existing_insights=(),
    )
    result1 = extract_all_patterns(input1)
    assert result1.success

    input2 = ModelPatternExtractionInput(
        session_snapshots=run2_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=5)),
        existing_insights=result1.new_insights,
    )
    result2 = extract_all_patterns(input2)
    assert result2.success

    assert result2.metrics.new_insights_count == len(result2.new_insights), (
        "metrics.new_insights_count must equal len(new_insights)"
    )
    assert result2.metrics.updated_insights_count == len(result2.updated_insights), (
        "metrics.updated_insights_count must equal len(updated_insights)"
    )
    # Combined insight count matches metrics
    total = result2.metrics.new_insights_count + result2.metrics.updated_insights_count
    assert total > 0, "Combined insight count should be positive after two runs"


def test_empty_existing_insights_behaves_as_run1(
    run1_sessions: tuple[ModelSessionSnapshot, ...],
) -> None:
    """Passing empty existing_insights is identical to a fresh first run."""
    input_fresh = ModelPatternExtractionInput(
        session_snapshots=run1_sessions,
        options=_config(reference_time=_BASE_TIME + timedelta(hours=2)),
        existing_insights=(),
    )
    result = extract_all_patterns(input_fresh)

    assert result.success
    assert len(result.updated_insights) == 0, (
        "No updates expected when existing_insights is empty"
    )


def test_idempotent_double_merge(
    run1_sessions: tuple[ModelSessionSnapshot, ...],
) -> None:
    """Merging a run against itself produces updated_insights (not new ones).

    If the same sessions are extracted twice and the second run receives the
    first run's insights as existing, the result must not produce duplicate
    new_insights for patterns already present.
    """
    options = _config(reference_time=_BASE_TIME + timedelta(hours=2))
    input1 = ModelPatternExtractionInput(
        session_snapshots=run1_sessions,
        options=options,
        existing_insights=(),
    )
    result1 = extract_all_patterns(input1)
    assert result1.success
    assert len(result1.new_insights) > 0

    # Same sessions, same config, but pass run1 insights as existing
    input2 = ModelPatternExtractionInput(
        session_snapshots=run1_sessions,
        options=options,
        existing_insights=result1.new_insights,
    )
    result2 = extract_all_patterns(input2)
    assert result2.success

    # Patterns seen in run1 should all be in updated_insights, not new_insights
    run1_keys = {i.insight_id for i in result1.new_insights}
    spurious_new = [i for i in result2.new_insights if i.insight_id in run1_keys]
    assert not spurious_new, (
        "Insights already present in existing_insights must not appear as "
        f"new_insights again: {[i.insight_id for i in spurious_new]}"
    )
