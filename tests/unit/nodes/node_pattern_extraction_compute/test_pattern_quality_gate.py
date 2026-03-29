# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern quality gate tests (OMN-6965).

Validates that pattern extraction quality filters prevent:
1. O(n^2) co-access pair explosion from large file sets
2. Trivial same-tool bigrams (Read->Read, Grep->Grep)
3. Patterns appearing in fewer than min_distinct_sessions
4. Placeholder-named patterns (general, stored_placeholder, unknown)

These are CI-enforced budget tests that prevent quality regressions.
"""

from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_extract_all_patterns import (
    _deduplicate_and_merge,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_file_patterns import (
    extract_file_access_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_tool_patterns import (
    extract_tool_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    EnumInsightType,
    ModelCodebaseInsight,
    ModelSessionSnapshot,
)

# =============================================================================
# Helpers
# =============================================================================

_BASE_TIME = datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC)


def _make_session(
    session_id: str,
    files: tuple[str, ...] = (),
    tools: tuple[str, ...] = (),
    outcome: str = "success",
) -> ModelSessionSnapshot:
    """Create a minimal session snapshot for testing."""
    return ModelSessionSnapshot(
        session_id=session_id,
        working_directory="/project",
        started_at=_BASE_TIME,
        ended_at=_BASE_TIME + timedelta(hours=1),
        files_accessed=files,
        files_modified=(),
        tools_used=tools,
        errors_encountered=(),
        outcome=outcome,
        tool_executions=(),
    )


def _make_insight(
    description: str,
    insight_type: EnumInsightType = EnumInsightType.FILE_ACCESS_PATTERN,
    confidence: float = 0.8,
) -> ModelCodebaseInsight:
    """Create a minimal codebase insight for testing dedup/merge."""
    from uuid import uuid4

    return ModelCodebaseInsight(
        insight_id=str(uuid4()),
        insight_type=insight_type,
        description=description,
        confidence=confidence,
        evidence_files=("src/test.py",),
        evidence_session_ids=("s1", "s2"),
        occurrence_count=5,
        first_observed=_BASE_TIME,
        last_observed=_BASE_TIME,
        metadata={},
    )


# =============================================================================
# File Pattern Quality Tests
# =============================================================================


class TestFilePatternCardinality:
    """Verify file co-access patterns don't explode with O(n^2) pairs."""

    @pytest.mark.unit
    def test_large_session_capped_output(self) -> None:
        """Session with 100 files across different dirs should produce <100 patterns, not C(100,2)=4950."""
        # Create files in different directories to bypass same-directory filter
        files = tuple(f"src/dir{i}/module_{i}.py" for i in range(100))

        # Multiple sessions with same files to satisfy min_occurrences
        sessions = [_make_session(f"s{j}", files=files) for j in range(10)]

        patterns = extract_file_access_patterns(
            sessions,
            min_occurrences=2,
            min_confidence=0.1,
            min_distinct_sessions=1,
            max_results_per_type=50,
        )

        # Should be capped by max_results_per_type, not O(n^2)
        co_access = [p for p in patterns if p["pattern_type"] == "co_access"]
        assert len(co_access) <= 50, (
            f"Expected <=50 co-access patterns, got {len(co_access)}. "
            f"Cardinality cap not applied."
        )

    @pytest.mark.unit
    def test_min_distinct_sessions_filters_single_session_patterns(self) -> None:
        """Patterns appearing in only 1 session should be filtered when min_distinct_sessions=2."""
        # Files shared across session 1 and 2
        shared_files = ("src/api/routes.py", "src/handlers/handler.py")
        # Files only in session 1
        unique_files = ("src/unique/only_here.py", "src/unique/also_here.py")

        sessions = [
            _make_session("s1", files=shared_files + unique_files),
            _make_session("s2", files=shared_files),
            _make_session("s3", files=shared_files),
            _make_session("s4", files=shared_files),
            _make_session("s5", files=shared_files),
        ]

        patterns = extract_file_access_patterns(
            sessions,
            min_occurrences=1,
            min_confidence=0.0,
            min_distinct_sessions=2,
            max_results_per_type=50,
        )

        # Patterns from unique_files should be filtered (only in 1 session)
        pattern_files = [
            p["files"] for p in patterns if p["pattern_type"] == "co_access"
        ]
        for pf in pattern_files:
            # Should not see the unique-only pair
            assert not (
                "src/unique/only_here.py" in pf and "src/unique/also_here.py" in pf
            ), "Pattern from single session should be filtered by min_distinct_sessions"


# =============================================================================
# Tool Pattern Quality Tests
# =============================================================================


class TestToolBigramFiltering:
    """Verify trivial same-tool bigrams are filtered."""

    @pytest.mark.unit
    def test_same_tool_bigrams_filtered(self) -> None:
        """Read->Read, Grep->Grep tool bigrams should be filtered as trivial."""
        sessions = [
            _make_session(
                f"s{i}",
                tools=("Read", "Read", "Read", "Edit", "Grep", "Grep"),
            )
            for i in range(10)
        ]

        patterns = extract_tool_patterns(
            sessions,
            min_occurrences=2,
            min_confidence=0.1,
            min_distinct_sessions=1,
            max_results_per_type=50,
        )

        bigram_patterns = [
            p
            for p in patterns
            if p["pattern_type"] == "tool_sequence" and len(p["tools"]) == 2
        ]
        bigram_names = [(p["tools"][0], p["tools"][1]) for p in bigram_patterns]

        # Should NOT contain same-tool bigrams
        assert ("Read", "Read") not in bigram_names, (
            "Read->Read bigram should be filtered"
        )
        assert ("Grep", "Grep") not in bigram_names, (
            "Grep->Grep bigram should be filtered"
        )

    @pytest.mark.unit
    def test_different_tool_bigrams_kept(self) -> None:
        """Read->Edit bigrams should be kept (different tools)."""
        sessions = [
            _make_session(
                f"s{i}",
                tools=("Read", "Edit", "Bash"),
            )
            for i in range(10)
        ]

        patterns = extract_tool_patterns(
            sessions,
            min_occurrences=2,
            min_confidence=0.1,
            min_distinct_sessions=1,
            max_results_per_type=50,
        )

        bigram_patterns = [
            p
            for p in patterns
            if p["pattern_type"] == "tool_sequence" and len(p["tools"]) == 2
        ]
        bigram_names = [(p["tools"][0], p["tools"][1]) for p in bigram_patterns]

        # Should contain Read->Edit (different tools)
        assert ("Read", "Edit") in bigram_names, "Read->Edit bigram should be kept"


# =============================================================================
# Placeholder Name Rejection Tests
# =============================================================================


class TestPlaceholderDescriptionRejection:
    """Verify patterns with placeholder descriptions are rejected during dedup/merge."""

    @pytest.mark.unit
    def test_general_description_rejected(self) -> None:
        """Pattern with description 'general' should be filtered during dedup."""
        patterns = [
            _make_insight("general"),
            _make_insight("file_co_access_api_handler"),
        ]

        new, updated = _deduplicate_and_merge(patterns, existing=(), max_per_type=50)

        descriptions = [p.description for p in new]
        assert "general" not in descriptions, (
            "Pattern described as 'general' should be rejected"
        )
        assert "file_co_access_api_handler" in descriptions

    @pytest.mark.unit
    def test_stored_placeholder_rejected(self) -> None:
        """Pattern with description 'stored_placeholder' should be filtered during dedup."""
        patterns = [
            _make_insight("stored_placeholder"),
            _make_insight("tool_sequence_read_edit"),
        ]

        new, updated = _deduplicate_and_merge(patterns, existing=(), max_per_type=50)

        descriptions = [p.description for p in new]
        assert "stored_placeholder" not in descriptions
        assert "tool_sequence_read_edit" in descriptions

    @pytest.mark.unit
    def test_unknown_description_rejected(self) -> None:
        """Pattern with description 'unknown' should be filtered during dedup."""
        patterns = [_make_insight("unknown")]

        new, updated = _deduplicate_and_merge(patterns, existing=(), max_per_type=50)

        assert len(new) == 0, "Pattern described as 'unknown' should be rejected"
