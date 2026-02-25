# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Architecture pattern extraction from session data.

This module implements a pure functional architecture pattern extraction
algorithm that analyzes Claude Code session snapshots to identify:

1. Module boundaries: Directory clusters that are accessed together,
   indicating related functionality or feature boundaries.

2. Layer patterns: Common path prefixes indicating architectural layers
   (e.g., src/, tests/, lib/, api/, handlers/).

3. Dependency chains: Files accessed in sequence indicating dependencies
   or workflow patterns.

ONEX Compliance:
    - Pure functional design (no side effects)
    - Deterministic results for same inputs (except UUIDs)
    - No external service calls or I/O operations
    - Uses TypedDict for type-safe return values

Algorithm Overview:
    1. Iterate through sessions and extract file paths from files_accessed/files_modified
    2. Build directory access patterns (which directories appear together)
    3. Track directory prefix frequencies for layer detection
    4. Generate patterns that exceed confidence thresholds
    5. Return deduplicated, confidence-sorted results
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import uuid4

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.protocols import (
    ArchitecturePatternResult,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.utils import (
    normalize_path,
)

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_extraction_compute.models import (
        ModelSessionSnapshot,
    )


# =============================================================================
# Main Handler Function
# =============================================================================


def extract_architecture_patterns(
    sessions: Sequence[ModelSessionSnapshot],
    min_occurrences: int = 2,
    min_confidence: float = 0.6,
    min_distinct_sessions: int = 2,  # noqa: ARG001 - Unused, for uniform interface
    max_results_per_type: int = 20,  # noqa: ARG001 - Unused, for uniform interface
) -> list[ArchitecturePatternResult]:
    """Extract architecture patterns from Claude Code session snapshots.

    Analyzes file access patterns across sessions to identify architectural
    structures in the codebase. This is a pure function with no side effects.

    Patterns Detected:
        1. **Module boundaries**: Directory pairs that are frequently accessed
           together, indicating related functionality. Detected by tracking
           which directories appear in the same session.

        2. **Layer patterns**: Common path prefixes that appear frequently,
           indicating architectural layers (e.g., src/api/, tests/unit/).
           Detected by analyzing prefix frequency across all accessed files.

        3. **Dependency chains**: (Future) Files accessed in sequence that
           indicate workflow dependencies.

    Args:
        sessions: Sequence of session snapshot objects. Each session should have:
            - files_accessed (tuple[str, ...]): Files read during the session
            - files_modified (tuple[str, ...]): Files modified during the session
        min_occurrences: Minimum number of times a pattern must occur across
            sessions to be considered valid. Higher values reduce noise but
            may miss rare patterns. Default: 2.
        min_confidence: Minimum confidence score (0.0-1.0) for a pattern to be
            included in results. Higher values return only stronger patterns.
            Default: 0.6.

    Returns:
        List of ArchitecturePatternResult dictionaries, sorted by confidence
        descending. Each result contains:
            - pattern_id: Unique UUID for the pattern
            - pattern_type: "module_boundary" or "layer_pattern"
            - directory_prefix: Common path prefix for the pattern
            - member_files: Tuple of files belonging to the pattern (max 10)
            - occurrences: Number of sessions where pattern was observed
            - confidence: Confidence score (0.0-1.0)

    Examples:
        >>> from dataclasses import dataclass
        >>> @dataclass
        ... class MockSession:
        ...     files_accessed: tuple[str, ...]
        ...     files_modified: tuple[str, ...]
        >>> sessions = [
        ...     MockSession(
        ...         files_accessed=("src/api/routes.py", "src/api/handlers.py"),
        ...         files_modified=(),
        ...     ),
        ...     MockSession(
        ...         files_accessed=("src/api/routes.py", "src/api/models.py"),
        ...         files_modified=(),
        ...     ),
        ... ]
        >>> patterns = extract_architecture_patterns(sessions, min_occurrences=1)
        >>> len(patterns) > 0
        True

    Notes:
        - Empty sessions are gracefully skipped
        - Files without valid paths are ignored
        - Pattern IDs are UUIDs, making results non-deterministic in that regard
        - Results are deduplicated by directory_prefix within each pattern type
    """
    results: list[ArchitecturePatternResult] = []

    # Track directory access patterns across sessions
    dir_pairs: Counter[tuple[str, str]] = Counter()
    dir_files: defaultdict[str, set[str]] = defaultdict(set)
    layer_prefixes: Counter[str] = Counter()

    for session in sessions:
        files_accessed = getattr(session, "files_accessed", None) or ()
        files_modified = getattr(session, "files_modified", None) or ()
        session_dirs: set[str] = set()

        # Combine all files from the session
        all_files = list(files_accessed) + list(files_modified)

        for file_path in all_files:
            if not file_path:
                continue

            # Normalize path separators for cross-platform compatibility
            file_path = normalize_path(file_path)

            # Extract directory from file path
            dir_path = os.path.dirname(file_path)
            if dir_path:
                session_dirs.add(dir_path)
                dir_files[dir_path].add(file_path)

                # Track layer prefixes (path components)
                parts = normalize_path(dir_path).split("/")
                for i in range(1, min(4, len(parts) + 1)):
                    prefix = "/".join(parts[:i])
                    if prefix:
                        layer_prefixes[prefix] += 1

        # Track directory co-access patterns (which directories appear together)
        # Sort to ensure consistent ordering of pairs
        dirs_list = sorted(session_dirs)
        for i, d1 in enumerate(dirs_list):
            for d2 in dirs_list[i + 1 :]:
                # Only pair directories at similar depth to avoid noise
                # e.g., pair src/api with src/models, not src with src/api/v2/handlers
                depth1 = d1.count("/")
                depth2 = d2.count("/")
                if abs(depth1 - depth2) <= 1:
                    dir_pairs[(d1, d2)] += 1

    # Calculate normalization factor for confidence
    total_sessions = len(sessions) if sessions else 1

    # ==========================================================================
    # Generate Module Boundary Patterns
    # ==========================================================================
    # Module boundaries are directory pairs that frequently appear together

    seen_prefixes_boundary: set[str] = set()

    for (d1, d2), count in dir_pairs.most_common():
        if count < min_occurrences:
            break

        # Confidence based on how often this pair appears relative to sessions
        # Using 0.4 factor since not every session will touch every module pair
        confidence = min(1.0, count / (total_sessions * 0.4))
        if confidence < min_confidence:
            continue

        # Find common parent directory for the boundary
        try:
            common = os.path.commonpath([d1, d2]) if d1 and d2 else ""
        except ValueError:
            # commonpath raises ValueError for paths on different drives (Windows)
            common = ""

        # Use common path as the prefix, or d1 if no common path
        prefix = common if common else d1

        # Deduplicate by prefix
        if prefix in seen_prefixes_boundary:
            continue
        seen_prefixes_boundary.add(prefix)

        # Collect member files from both directories (limit to 10)
        sorted_files = sorted(dir_files.get(d1, set()) | dir_files.get(d2, set()))
        member_files: tuple[str, ...] = tuple(sorted_files[:10])

        results.append(
            ArchitecturePatternResult(
                pattern_id=str(uuid4()),
                pattern_type="module_boundary",
                directory_prefix=prefix,
                member_files=member_files,
                occurrences=count,
                confidence=confidence,
            )
        )

    # ==========================================================================
    # Generate Layer Patterns
    # ==========================================================================
    # Layer patterns are frequently accessed path prefixes indicating structure

    # Group prefixes by depth to find patterns at different levels
    prefix_by_depth: defaultdict[int, list[tuple[str, int]]] = defaultdict(list)
    for prefix, count in layer_prefixes.items():
        if count < min_occurrences:
            continue
        depth = prefix.count("/")
        prefix_by_depth[depth].append((prefix, count))

    seen_prefixes_layer: set[str] = set()

    # Process top 3 depths to capture different architectural levels
    for depth in sorted(prefix_by_depth.keys())[:3]:
        prefixes = prefix_by_depth[depth]
        # Take top 5 prefixes at each depth
        for prefix, count in sorted(prefixes, key=lambda x: -x[1])[:5]:
            # Confidence based on occurrence relative to total sessions
            confidence = min(1.0, count / total_sessions)
            if confidence < min_confidence:
                continue

            # Skip if already seen (could happen from module_boundary)
            if prefix in seen_prefixes_layer:
                continue
            seen_prefixes_layer.add(prefix)

            # Collect member files for this prefix (limit to 10)
            layer_sorted_files = sorted(dir_files.get(prefix, set()))
            layer_member_files: tuple[str, ...] = tuple(layer_sorted_files[:10])

            results.append(
                ArchitecturePatternResult(
                    pattern_id=str(uuid4()),
                    pattern_type="layer_pattern",
                    directory_prefix=prefix,
                    member_files=layer_member_files,
                    occurrences=count,
                    confidence=confidence,
                )
            )

    # Sort results by confidence descending for consistent output
    results.sort(key=lambda r: r["confidence"], reverse=True)

    return results


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "extract_architecture_patterns",
]
