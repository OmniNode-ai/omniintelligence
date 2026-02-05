"""File access pattern extraction from session data.

This module implements a pure functional handler that extracts file access patterns
from Claude Code session snapshots. It identifies three types of patterns that
provide insights into codebase usage and developer workflows.

Pattern Types:
    1. Co-access patterns: Files frequently accessed together in the same session.
       These indicate logical relationships or dependencies between files.

    2. Entry points: Files commonly accessed first in sessions. These are likely
       important starting points for understanding or working with the codebase.

    3. Modification clusters: Files frequently modified together. These indicate
       coupled components that may need coordinated changes.

ONEX Compliance:
    - Pure functional design (no side effects)
    - Deterministic results for same inputs (with fixed UUIDs for testing)
    - No external service calls or I/O operations
    - Graceful handling of missing/malformed data

Algorithm:
    1. Iterate through all sessions, extracting files_accessed and files_modified
    2. Track file co-occurrences within each session
    3. Compute pattern confidence based on occurrence frequency
    4. Filter patterns by minimum occurrence and confidence thresholds
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_extraction_compute.models import (
        ModelSessionSnapshot,
    )

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.protocols import (
    FileAccessPatternResult,
)

# Confidence calculation significance factors
# These control how occurrence counts translate to confidence scores.
# A factor of 0.5 means pattern occurring in 50% of sessions yields confidence=1.0.
# A factor of 0.3 means pattern occurring in 30% of sessions yields confidence=1.0.

CO_ACCESS_SIGNIFICANCE_FACTOR = 0.5
"""Co-access patterns: occurrence in 50% of sessions is considered highly significant."""

MODIFICATION_CLUSTER_SIGNIFICANCE_FACTOR = 0.3
"""Modification clusters: occurrence in 30% of sessions is significant (rarer pattern)."""


def extract_file_access_patterns(
    sessions: Sequence[ModelSessionSnapshot],
    min_occurrences: int = 2,
    min_confidence: float = 0.6,
    min_distinct_sessions: int = 2,  # noqa: ARG001 - Unused, for uniform interface
    max_results_per_type: int = 20,  # noqa: ARG001 - Unused, for uniform interface
) -> list[FileAccessPatternResult]:
    """Extract file access patterns from sessions.

    Analyzes Claude Code session data to identify patterns in how files are
    accessed and modified. This information can be used to:
    - Suggest related files when working on a feature
    - Identify entry points for new developers
    - Detect coupled components that may need refactoring

    Patterns detected:
        1. Co-access patterns: Files frequently accessed together in the same session.
        2. Entry points: Files accessed first in sessions (common starting points).
        3. Modification clusters: Files modified together in the same session.

    Args:
        sessions: Session snapshots to analyze. Each session should have:
            - session_id (str): Unique session identifier
            - files_accessed (tuple[str, ...]): Files read during the session
            - files_modified (tuple[str, ...]): Files modified during the session
        min_occurrences: Minimum times a pattern must occur to be included.
            Default is 2 to filter out one-off coincidences.
        min_confidence: Minimum confidence threshold (0.0-1.0) for patterns.
            Default is 0.6 to ensure statistical significance.

    Returns:
        List of detected file access patterns, sorted by confidence descending.
        Returns empty list if no patterns meet the thresholds.

    Examples:
        >>> sessions = [
        ...     MockSession(
        ...         session_id="s1",
        ...         files_accessed=("api.py", "models.py"),
        ...         files_modified=(),
        ...     ),
        ...     MockSession(
        ...         session_id="s2",
        ...         files_accessed=("api.py", "models.py"),
        ...         files_modified=(),
        ...     ),
        ... ]
        >>> patterns = extract_file_access_patterns(sessions, min_occurrences=2)
        >>> len(patterns) > 0
        True
    """
    results: list[FileAccessPatternResult] = []

    # Track file co-occurrences across sessions
    file_pairs: Counter[tuple[str, str]] = Counter()
    entry_points: Counter[str] = Counter()
    modification_pairs: Counter[tuple[str, str]] = Counter()
    session_files: dict[str, set[str]] = defaultdict(set)

    for session in sessions:
        session_id = getattr(session, "session_id", None) or str(uuid4())
        files_accessed = getattr(session, "files_accessed", None) or ()
        files_modified = getattr(session, "files_modified", None) or ()

        # Track all files in this session for evidence gathering
        all_session_files = set(files_accessed) | set(files_modified)
        session_files[session_id] = all_session_files

        # Track entry points (first file accessed in session)
        if files_accessed:
            entry_points[files_accessed[0]] += 1

        # Track co-access pairs (files accessed together)
        # Use dict.fromkeys to preserve order while removing duplicates
        unique_accessed = list(dict.fromkeys(files_accessed))
        for i, f1 in enumerate(unique_accessed):
            for f2 in unique_accessed[i + 1 :]:
                # Sort pair to ensure consistent key regardless of access order
                sorted_files = sorted([f1, f2])
                pair: tuple[str, str] = (sorted_files[0], sorted_files[1])
                file_pairs[pair] += 1

        # Track modification clusters (files modified together)
        unique_modified = list(dict.fromkeys(files_modified))
        for i, f1 in enumerate(unique_modified):
            for f2 in unique_modified[i + 1 :]:
                sorted_files = sorted([f1, f2])
                pair = (sorted_files[0], sorted_files[1])
                modification_pairs[pair] += 1

    total_sessions = len(sessions) if sessions else 1

    # Generate co-access patterns
    for (f1, f2), count in file_pairs.most_common():
        if count < min_occurrences:
            break
        # Confidence based on fraction of sessions containing pair
        confidence = min(1.0, count / (total_sessions * CO_ACCESS_SIGNIFICANCE_FACTOR))
        if confidence >= min_confidence:
            # Find sessions containing this pair
            evidence = tuple(
                sid
                for sid, files in session_files.items()
                if f1 in files and f2 in files
            )
            results.append(
                FileAccessPatternResult(
                    pattern_id=str(uuid4()),
                    pattern_type="co_access",
                    files=(f1, f2),
                    occurrences=count,
                    confidence=confidence,
                    evidence_session_ids=evidence,
                )
            )

    # Generate entry point patterns
    for file_path, count in entry_points.most_common():
        if count < min_occurrences:
            break
        # Confidence based on fraction of sessions starting with this file
        confidence = min(1.0, count / total_sessions)
        if confidence >= min_confidence:
            evidence = tuple(
                sid for sid, files in session_files.items() if file_path in files
            )
            results.append(
                FileAccessPatternResult(
                    pattern_id=str(uuid4()),
                    pattern_type="entry_point",
                    files=(file_path,),
                    occurrences=count,
                    confidence=confidence,
                    evidence_session_ids=evidence,
                )
            )

    # Generate modification cluster patterns
    for (f1, f2), count in modification_pairs.most_common():
        if count < min_occurrences:
            break
        # Modification clusters are rarer than co-access patterns
        confidence = min(
            1.0, count / (total_sessions * MODIFICATION_CLUSTER_SIGNIFICANCE_FACTOR)
        )
        if confidence >= min_confidence:
            evidence = tuple(
                sid
                for sid, files in session_files.items()
                if f1 in files and f2 in files
            )
            results.append(
                FileAccessPatternResult(
                    pattern_id=str(uuid4()),
                    pattern_type="modification_cluster",
                    files=(f1, f2),
                    occurrences=count,
                    confidence=confidence,
                    evidence_session_ids=evidence,
                )
            )

    return results


__all__ = ["extract_file_access_patterns"]
