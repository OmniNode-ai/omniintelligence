# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for file access pattern relevance filters (OMN-6566).

Tests the four filters added to reduce file_access pattern noise:
1. Same-directory filter — trivially co-accessed pairs excluded
2. Common-file exclusion list — CLAUDE.md, pyproject.toml, etc.
3. Per-session pair cap — max 10 files for pair generation
4. min_occurrences default raised from 2 to 5
5. Combined integration test — all filters interact correctly
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_file_patterns import (
    COMMON_FILE_EXCLUSIONS,
    MAX_FILES_PER_SESSION_FOR_PAIRS,
    _is_excluded_file,
    _same_directory,
    extract_file_access_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelSessionSnapshot,
)

pytestmark = pytest.mark.unit

BASE_TIME = datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC)


def _make_session(
    session_id: str,
    files_accessed: tuple[str, ...] = (),
    files_modified: tuple[str, ...] = (),
) -> ModelSessionSnapshot:
    """Helper to create a minimal session snapshot."""
    return ModelSessionSnapshot(
        session_id=session_id,
        working_directory="/project",
        started_at=BASE_TIME,
        ended_at=BASE_TIME + timedelta(hours=1),
        files_accessed=files_accessed,
        files_modified=files_modified,
        outcome="success",
    )


# =============================================================================
# Helper function tests
# =============================================================================


class TestHelperFunctions:
    """Tests for _is_excluded_file and _same_directory helpers."""

    def test_is_excluded_file_matches_basename(self) -> None:
        """Should match regardless of directory prefix."""
        assert _is_excluded_file("CLAUDE.md") is True
        assert _is_excluded_file("src/deep/path/CLAUDE.md") is True
        assert _is_excluded_file("pyproject.toml") is True
        assert _is_excluded_file("some/dir/__init__.py") is True

    def test_is_excluded_file_rejects_non_excluded(self) -> None:
        """Should not match normal source files."""
        assert _is_excluded_file("src/api/routes.py") is False
        assert _is_excluded_file("src/models/user.py") is False

    def test_same_directory_true(self) -> None:
        """Files in the same directory should return True."""
        assert _same_directory("src/handlers/a.py", "src/handlers/b.py") is True
        assert _same_directory("a.py", "b.py") is True

    def test_same_directory_false(self) -> None:
        """Files in different directories should return False."""
        assert _same_directory("src/handlers/a.py", "src/models/b.py") is False
        assert _same_directory("src/a.py", "tests/b.py") is False


# =============================================================================
# Task 3: Same-directory filter
# =============================================================================


class TestSameDirectoryFilter:
    """Files in the same directory should be excluded from pair patterns."""

    def test_same_directory_pairs_excluded(self) -> None:
        """Co-access pairs within the same directory are filtered out."""
        # 4 files in src/handlers/ + 2 cross-directory files
        sessions = tuple(
            _make_session(
                session_id=f"s{i}",
                files_accessed=(
                    "src/handlers/handler_a.py",
                    "src/handlers/handler_b.py",
                    "src/handlers/handler_c.py",
                    "src/handlers/handler_d.py",
                    "src/models/user.py",
                    "tests/test_api.py",
                ),
            )
            for i in range(5)
        )

        results = extract_file_access_patterns(
            sessions, min_occurrences=3, min_confidence=0.1
        )

        co_access = [r for r in results if r["pattern_type"] == "co_access"]

        # No pair should have both files in src/handlers/
        for pattern in co_access:
            f1, f2 = pattern["files"]
            assert not _same_directory(f1, f2), (
                f"Same-directory pair should be filtered: {f1}, {f2}"
            )

    def test_cross_directory_pairs_preserved(self) -> None:
        """Cross-directory pairs should still appear."""
        sessions = tuple(
            _make_session(
                session_id=f"s{i}",
                files_accessed=(
                    "src/models/user.py",
                    "tests/test_user.py",
                ),
            )
            for i in range(5)
        )

        results = extract_file_access_patterns(
            sessions, min_occurrences=3, min_confidence=0.1
        )

        co_access = [r for r in results if r["pattern_type"] == "co_access"]
        assert len(co_access) > 0, "Cross-directory pair should be preserved"


# =============================================================================
# Task 4: Common-file exclusion list
# =============================================================================


class TestCommonFileExclusion:
    """Common files like CLAUDE.md and pyproject.toml should be excluded."""

    def test_common_files_excluded_from_pairs(self) -> None:
        """Pairs involving CLAUDE.md or pyproject.toml should not appear."""
        sessions = tuple(
            _make_session(
                session_id=f"s{i}",
                files_accessed=(
                    "CLAUDE.md",
                    "pyproject.toml",
                    "src/models/user.py",
                    "tests/test_api.py",
                ),
            )
            for i in range(5)
        )

        results = extract_file_access_patterns(
            sessions, min_occurrences=3, min_confidence=0.1
        )

        co_access = [r for r in results if r["pattern_type"] == "co_access"]

        # Only cross-directory pair should be models/user.py + tests/test_api.py
        for pattern in co_access:
            for f in pattern["files"]:
                assert not _is_excluded_file(f), f"Common file should be excluded: {f}"

    def test_common_files_excluded_from_entry_points(self) -> None:
        """Entry points should not include common files."""
        sessions = tuple(
            _make_session(
                session_id=f"s{i}",
                files_accessed=(
                    "CLAUDE.md",
                    "src/api/routes.py",
                ),
            )
            for i in range(5)
        )

        results = extract_file_access_patterns(
            sessions, min_occurrences=3, min_confidence=0.1
        )

        entry_points = [r for r in results if r["pattern_type"] == "entry_point"]
        for pattern in entry_points:
            assert "CLAUDE.md" not in pattern["files"]

    def test_exclusion_list_is_frozenset(self) -> None:
        """Exclusion list should be an immutable frozenset."""
        assert isinstance(COMMON_FILE_EXCLUSIONS, frozenset)
        assert len(COMMON_FILE_EXCLUSIONS) > 0


# =============================================================================
# Task 5: Per-session pair cap
# =============================================================================


class TestPerSessionPairCap:
    """Sessions with many files should be capped for pair generation."""

    def test_pair_cap_limits_combinations(self) -> None:
        """25 unique files should generate at most C(10,2) pairs, not C(25,2)."""
        # Generate 25 unique files across different directories
        files = tuple(f"src/dir{i}/file{j}.py" for i in range(5) for j in range(5))
        assert len(files) == 25

        sessions = tuple(
            _make_session(
                session_id=f"s{i}",
                files_accessed=files,
            )
            for i in range(5)
        )

        results = extract_file_access_patterns(
            sessions, min_occurrences=3, min_confidence=0.1
        )

        co_access = [r for r in results if r["pattern_type"] == "co_access"]
        # C(10,2) = 45 max pairs (after cap), minus same-directory pairs
        # With 5 dirs x 2 files each (after cap=10), same-dir pairs removed
        # Actual count will be less than 45
        assert len(co_access) <= 45, (
            f"Too many co-access pairs: {len(co_access)}, expected <= 45"
        )

    def test_cap_value(self) -> None:
        """Cap should be 10."""
        assert MAX_FILES_PER_SESSION_FOR_PAIRS == 10


# =============================================================================
# Task 6: min_occurrences default + combined filter test
# =============================================================================


class TestMinOccurrencesDefault:
    """Default min_occurrences should be 5."""

    def test_default_min_occurrences_is_5(self) -> None:
        """Patterns appearing in only 2-4 sessions should be excluded by default."""
        # 4 sessions — below the new default of 5
        sessions = tuple(
            _make_session(
                session_id=f"s{i}",
                files_accessed=(
                    "src/models/user.py",
                    "tests/test_user.py",
                ),
            )
            for i in range(4)
        )

        # Default min_occurrences=5 should filter everything
        results = extract_file_access_patterns(sessions, min_confidence=0.1)
        assert len(results) == 0, (
            "Patterns with only 4 occurrences should be excluded at default threshold"
        )

    def test_explicit_min_occurrences_override(self) -> None:
        """Callers can still override min_occurrences."""
        sessions = tuple(
            _make_session(
                session_id=f"s{i}",
                files_accessed=(
                    "src/models/user.py",
                    "tests/test_user.py",
                ),
            )
            for i in range(3)
        )

        results = extract_file_access_patterns(
            sessions, min_occurrences=2, min_confidence=0.1
        )
        assert len(results) > 0, "Explicit min_occurrences=2 should find patterns"


class TestCombinedFiltering:
    """Integration test: all 4 filters compose correctly with realistic data."""

    def test_combined_filters_reduce_pattern_count(self) -> None:
        """8 sessions with 15-25 files each should produce <20 total patterns.

        This test uses realistic data including:
        - Common files (CLAUDE.md, pyproject.toml)
        - Same-directory clusters
        - Large file lists that would trigger the cap
        - Cross-directory signal files
        """
        sessions: list[ModelSessionSnapshot] = []

        # Session template: common files + same-dir clusters + signal files
        for i in range(8):
            accessed = [
                "CLAUDE.md",
                "pyproject.toml",
                "conftest.py",
                # Same-directory cluster: src/handlers/
                f"src/handlers/handler_{chr(97 + (i % 4))}.py",
                "src/handlers/base.py",
                "src/handlers/utils.py",
                # Same-directory cluster: src/models/
                "src/models/user.py",
                "src/models/session.py",
                f"src/models/model_{chr(97 + (i % 3))}.py",
                # Cross-directory signal files (the real patterns)
                "src/api/routes.py",
                "tests/test_routes.py",
                "src/config/settings.py",
                # Extra files to pad up to 15-20
                f"src/utils/helper_{i}.py",
                f"docs/section_{i}.md",
                f"scripts/run_{i}.sh",
            ]

            modified = [
                f"src/handlers/handler_{chr(97 + (i % 4))}.py",
                "src/api/routes.py",
                "tests/test_routes.py",
            ]

            sessions.append(
                _make_session(
                    session_id=f"session-{i:03d}",
                    files_accessed=tuple(accessed),
                    files_modified=tuple(modified),
                )
            )

        # Use default min_occurrences=5 (the new default)
        results = extract_file_access_patterns(
            tuple(sessions),
            min_confidence=0.3,
        )

        # With all filters active, total patterns should be manageable
        assert len(results) < 20, (
            f"Expected <20 patterns with all filters active, got {len(results)}: "
            + ", ".join(f"{r['pattern_type']}({r['files']})" for r in results)
        )

        # Verify no excluded files leaked through
        for pattern in results:
            for f in pattern["files"]:
                assert not _is_excluded_file(f), f"Excluded file leaked through: {f}"

        # Verify no same-directory pairs in co_access or modification_cluster
        pair_types = ("co_access", "modification_cluster")
        for pattern in results:
            if pattern["pattern_type"] in pair_types:
                f1, f2 = pattern["files"]
                assert not _same_directory(f1, f2), (
                    f"Same-directory pair leaked: {f1}, {f2}"
                )
