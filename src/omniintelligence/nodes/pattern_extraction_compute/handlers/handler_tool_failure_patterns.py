"""Tool failure pattern extraction from session data.

Extracts failure patterns from structured tool execution records.
Returns ErrorPatternResult with pattern_type="tool_failure".

Pattern Types Detected:
1. recurring_failure: Same tool + error_type across sessions
2. failure_sequence: Tool A failure followed by Tool B failure
3. context_failure: Failures correlated with file types/paths
4. recovery_pattern: Failure -> retry -> success/failure
5. failure_hotspot: Directories with high failure rates

CRITICAL DESIGN DECISIONS:
- Pattern IDs are DETERMINISTIC (content hash, NOT uuid4())
- Ordering is INDEX-BASED (tool_executions order is authoritative)
- Time-based checks are SECONDARY guards only
- All patterns require min_distinct_sessions to avoid single-session noise

ONEX Compliance:
    - Pure functional design (no side effects)
    - Deterministic results for same inputs
    - No external service calls or I/O operations
    - All state passed explicitly through parameters

Ticket: OMN-1579
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from omnibase_core.types import JsonType

    from omniintelligence.nodes.pattern_extraction_compute.models import (
        ModelSessionSnapshot,
        ModelToolExecution,
    )

from omniintelligence.nodes.pattern_extraction_compute.handlers.protocols import (
    ErrorPatternResult,
)

# =============================================================================
# Constants
# =============================================================================

SEQUENCE_MAX_TOOL_GAP = 5
"""A->B must be within 5 tool calls (index-based)."""

SEQUENCE_MAX_TIME_GAP_SEC = 60
"""Secondary guard: A->B within 60 seconds."""

RETRY_MAX_TOOL_GAP = 3
"""Retry must be within 3 tool calls."""

MAX_RESULTS_PER_TYPE = 20
"""Cap per pattern type to prevent noise."""

# Path key normalization (aliases -> canonical)
PATH_KEY_ALIASES = ("file_path", "path", "filename", "file")
"""Common aliases for file path parameters."""

CANONICAL_PATH_KEY = "file_path"
"""Canonical key for file path in tool_parameters."""


# =============================================================================
# Internal Data Structures
# =============================================================================


@dataclass(frozen=True)
class _FailureRecord:
    """Internal record of a single tool failure."""

    session_id: str
    tool_name: str
    error_type: str  # Normalized to "unknown" if None
    error_message: str  # Normalized to "" if None
    index: int  # Position in tool_executions (0-based)
    timestamp: datetime
    tool_parameters: dict[str, Any] | None


# =============================================================================
# Public API
# =============================================================================


def extract_tool_failure_patterns(
    sessions: Sequence[ModelSessionSnapshot],
    min_occurrences: int = 2,
    min_confidence: float = 0.6,
    min_distinct_sessions: int = 2,
) -> list[ErrorPatternResult]:
    """Extract failure patterns from tool executions.

    Returns ErrorPatternResult with pattern_type="tool_failure".
    Results are DETERMINISTICALLY ordered by (pattern_subtype, tool_name, confidence desc).

    Args:
        sessions: Session snapshots to analyze. Each session should have
            tool_executions with structured failure data.
        min_occurrences: Minimum times pattern must occur to be included.
            Defaults to 2 to filter out one-off occurrences.
        min_confidence: Minimum confidence threshold (0.0-1.0) for patterns.
            Defaults to 0.6 to ensure statistical relevance.
        min_distinct_sessions: Minimum distinct sessions a pattern must appear in.
            Defaults to 2 to avoid single-session noise.

    Returns:
        List of detected tool failure patterns, deterministically ordered.
    """
    results: list[ErrorPatternResult] = []

    # Collect all failures across sessions
    failures = _collect_failures(sessions)

    if not failures:
        return results

    # 1. Recurring failures (same tool + error_type)
    results.extend(
        _detect_recurring_failures(
            failures, min_occurrences, min_confidence, min_distinct_sessions
        )
    )

    # 2. Failure sequences (A fails -> B fails within bounds)
    results.extend(
        _detect_failure_sequences(
            sessions, min_occurrences, min_confidence, min_distinct_sessions
        )
    )

    # 3. Context-sensitive failures (file type/path correlations)
    results.extend(
        _detect_context_failures(
            failures, min_occurrences, min_confidence, min_distinct_sessions
        )
    )

    # 4. Recovery patterns (failure -> retry -> outcome)
    results.extend(
        _detect_recovery_patterns(
            sessions, min_occurrences, min_confidence, min_distinct_sessions
        )
    )

    # 5. Failure hotspots (tool_name + directory level)
    results.extend(
        _detect_failure_hotspots(
            failures, min_occurrences, min_confidence, min_distinct_sessions
        )
    )

    # DETERMINISTIC ORDERING: sort by (pattern_subtype, tool_name, confidence desc)
    results.sort(
        key=lambda r: (
            _get_pattern_subtype(r),
            _get_primary_tool(r),
            -r["confidence"],
        )
    )

    return results


# =============================================================================
# Pattern ID Generation
# =============================================================================


def _generate_stable_pattern_id(pattern_subtype: str, *key_components: str) -> str:
    """Generate deterministic pattern ID from content hash.

    NEVER use uuid4() - that breaks determinism.

    Args:
        pattern_subtype: The subtype of pattern (e.g., "recurring_failure").
        *key_components: Additional components to hash (tool_name, error_type, etc.).

    Returns:
        16-character hex string derived from SHA-256 hash.
    """
    content = "|".join([pattern_subtype, *key_components])
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# Failure Collection
# =============================================================================


def _collect_failures(
    sessions: Sequence[ModelSessionSnapshot],
) -> list[_FailureRecord]:
    """Collect all failure records from sessions.

    Args:
        sessions: Session snapshots to scan.

    Returns:
        List of _FailureRecord for each failed tool execution.
    """
    failures: list[_FailureRecord] = []

    for session in sessions:
        session_id = session.session_id
        tool_executions = session.tool_executions or ()

        for idx, exec_record in enumerate(tool_executions):
            if exec_record.success:
                continue

            # Normalize error_type and error_message
            error_type = (exec_record.error_type or "unknown").strip()
            error_message = (exec_record.error_message or "").strip()

            # Convert tool_parameters to dict if not None
            params: dict[str, Any] | None = None
            if exec_record.tool_parameters is not None:
                if isinstance(exec_record.tool_parameters, dict):
                    params = exec_record.tool_parameters

            failures.append(
                _FailureRecord(
                    session_id=session_id,
                    tool_name=exec_record.tool_name,
                    error_type=error_type if error_type else "unknown",
                    error_message=error_message,
                    index=idx,
                    timestamp=exec_record.timestamp,
                    tool_parameters=params,
                )
            )

    return failures


# =============================================================================
# Pattern Detection: Recurring Failures
# =============================================================================


def _detect_recurring_failures(
    failures: list[_FailureRecord],
    min_occurrences: int,
    min_confidence: float,
    min_distinct_sessions: int,
) -> list[ErrorPatternResult]:
    """Detect recurring failure patterns (same tool + error_type).

    Confidence = occurrences / total_failures_for_that_tool

    Args:
        failures: All failure records.
        min_occurrences: Minimum occurrences threshold.
        min_confidence: Minimum confidence threshold.
        min_distinct_sessions: Minimum distinct sessions threshold.

    Returns:
        List of ErrorPatternResult for recurring failures.
    """
    results: list[ErrorPatternResult] = []

    # Group failures by (tool_name, error_type)
    pattern_failures: defaultdict[tuple[str, str], list[_FailureRecord]] = defaultdict(
        list
    )
    for failure in failures:
        key = (failure.tool_name, failure.error_type)
        pattern_failures[key].append(failure)

    # Count total failures per tool (for confidence calculation)
    tool_failure_totals: Counter[str] = Counter()
    for failure in failures:
        tool_failure_totals[failure.tool_name] += 1

    # Generate patterns
    for (tool_name, error_type), matching_failures in pattern_failures.items():
        occurrences = len(matching_failures)

        if occurrences < min_occurrences:
            continue

        # Check distinct sessions requirement
        distinct_sessions = {f.session_id for f in matching_failures}
        if len(distinct_sessions) < min_distinct_sessions:
            continue

        # Calculate confidence: prevalence of this error type for this tool
        tool_total = tool_failure_totals.get(tool_name, occurrences)
        confidence = occurrences / max(tool_total, 1)

        if confidence < min_confidence:
            continue

        # Extract affected files from tool_parameters
        affected_files = _extract_affected_files(matching_failures)

        # Generate stable pattern ID
        pattern_id = _generate_stable_pattern_id(
            "recurring_failure", tool_name, error_type
        )

        # Build error summary with prevalence info
        prevalence_pct = (occurrences / max(tool_total, 1)) * 100
        error_summary = (
            f"recurring_failure:{tool_name}:{error_type} - "
            f"{occurrences}/{tool_total} failures ({prevalence_pct:.0f}% of {tool_name} failures)"
        )

        results.append(
            ErrorPatternResult(
                pattern_id=pattern_id,
                pattern_type="tool_failure",
                affected_files=tuple(sorted(affected_files)[:10]),
                error_summary=error_summary,
                occurrences=occurrences,
                confidence=round(confidence, 4),
                evidence_session_ids=tuple(sorted(distinct_sessions)),
            )
        )

    # Sort by confidence descending, limit to MAX_RESULTS_PER_TYPE
    results.sort(key=lambda r: -r["confidence"])
    return results[:MAX_RESULTS_PER_TYPE]


# =============================================================================
# Pattern Detection: Failure Sequences
# =============================================================================


def _detect_failure_sequences(
    sessions: Sequence[ModelSessionSnapshot],
    min_occurrences: int,
    min_confidence: float,
    min_distinct_sessions: int,
) -> list[ErrorPatternResult]:
    """Detect failure sequence patterns (A fails -> B fails within bounds).

    Uses index-based ordering primarily, time as secondary guard.

    Args:
        sessions: All sessions to analyze.
        min_occurrences: Minimum occurrences threshold.
        min_confidence: Minimum confidence threshold.
        min_distinct_sessions: Minimum distinct sessions threshold.

    Returns:
        List of ErrorPatternResult for failure sequences.
    """
    results: list[ErrorPatternResult] = []

    # Track sequences: (tool_a, tool_b) -> list of session_ids
    sequence_sessions: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    sequence_counts: Counter[tuple[str, str]] = Counter()

    for session in sessions:
        tool_executions = session.tool_executions or ()
        if len(tool_executions) < 2:
            continue

        session_id = session.session_id

        # Find failure indices
        failure_indices: list[int] = []
        for i, exec_record in enumerate(tool_executions):
            if not exec_record.success:
                failure_indices.append(i)

        # Look for sequences within bounds
        for i, idx_a in enumerate(failure_indices):
            exec_a = tool_executions[idx_a]

            for j in range(i + 1, len(failure_indices)):
                idx_b = failure_indices[j]

                # Check index gap (primary criterion)
                index_gap = idx_b - idx_a
                if index_gap > SEQUENCE_MAX_TOOL_GAP:
                    break  # No point checking further failures

                exec_b = tool_executions[idx_b]

                # Secondary time check (if timestamps differ)
                if not _within_time_bound(exec_a, exec_b, SEQUENCE_MAX_TIME_GAP_SEC):
                    continue

                # Record the sequence
                seq_key = (exec_a.tool_name, exec_b.tool_name)
                sequence_counts[seq_key] += 1
                sequence_sessions[seq_key].add(session_id)

    # Total failure pairs for confidence calculation
    total_pairs = sum(sequence_counts.values()) if sequence_counts else 1

    # Generate patterns
    for (tool_a, tool_b), count in sequence_counts.most_common():
        if count < min_occurrences:
            continue

        distinct_sessions = sequence_sessions[(tool_a, tool_b)]
        if len(distinct_sessions) < min_distinct_sessions:
            continue

        # Confidence: how often this specific sequence occurs relative to all sequences
        confidence = count / max(total_pairs, 1)

        if confidence < min_confidence:
            continue

        # Generate stable pattern ID
        pattern_id = _generate_stable_pattern_id("failure_sequence", tool_a, tool_b)

        error_summary = (
            f"failure_sequence:{tool_a}->{tool_b} - "
            f"{count} occurrences across {len(distinct_sessions)} sessions"
        )

        results.append(
            ErrorPatternResult(
                pattern_id=pattern_id,
                pattern_type="tool_failure",
                affected_files=(),
                error_summary=error_summary,
                occurrences=count,
                confidence=round(confidence, 4),
                evidence_session_ids=tuple(sorted(distinct_sessions)),
            )
        )

    # Sort by confidence descending, limit to MAX_RESULTS_PER_TYPE
    results.sort(key=lambda r: -r["confidence"])
    return results[:MAX_RESULTS_PER_TYPE]


# =============================================================================
# Pattern Detection: Context Failures
# =============================================================================


def _detect_context_failures(
    failures: list[_FailureRecord],
    min_occurrences: int,
    min_confidence: float,
    min_distinct_sessions: int,
) -> list[ErrorPatternResult]:
    """Detect context-sensitive failures (file extension/directory correlations).

    Extracts stable features only (extension, top_level_dir, param_shape as sorted keys).
    Normalizes paths (posix separators, lowercase extension).

    Args:
        failures: All failure records.
        min_occurrences: Minimum occurrences threshold.
        min_confidence: Minimum confidence threshold.
        min_distinct_sessions: Minimum distinct sessions threshold.

    Returns:
        List of ErrorPatternResult for context failures.
    """
    results: list[ErrorPatternResult] = []

    # Group by (tool_name, extension)
    ext_failures: defaultdict[tuple[str, str], list[_FailureRecord]] = defaultdict(list)

    # Group by (tool_name, top_level_dir)
    dir_failures: defaultdict[tuple[str, str], list[_FailureRecord]] = defaultdict(list)

    for failure in failures:
        features = _extract_context_features(failure.tool_parameters)
        ext = features.get("extension")
        top_dir = features.get("top_level_dir")

        if ext:
            ext_failures[(failure.tool_name, ext)].append(failure)
        if top_dir:
            dir_failures[(failure.tool_name, top_dir)].append(failure)

    # Count total failures per tool for confidence
    tool_totals: Counter[str] = Counter()
    for f in failures:
        tool_totals[f.tool_name] += 1

    # Process extension-based patterns
    for (tool_name, ext), matching in ext_failures.items():
        occurrences = len(matching)
        if occurrences < min_occurrences:
            continue

        distinct_sessions = {f.session_id for f in matching}
        if len(distinct_sessions) < min_distinct_sessions:
            continue

        tool_total = tool_totals.get(tool_name, occurrences)
        confidence = occurrences / max(tool_total, 1)

        if confidence < min_confidence:
            continue

        affected_files = _extract_affected_files(matching)
        pattern_id = _generate_stable_pattern_id("context_failure_ext", tool_name, ext)

        error_summary = (
            f"context_failure:{tool_name}:{ext} - "
            f"{occurrences}/{tool_total} failures on {ext} files"
        )

        results.append(
            ErrorPatternResult(
                pattern_id=pattern_id,
                pattern_type="tool_failure",
                affected_files=tuple(sorted(affected_files)[:10]),
                error_summary=error_summary,
                occurrences=occurrences,
                confidence=round(confidence, 4),
                evidence_session_ids=tuple(sorted(distinct_sessions)),
            )
        )

    # Process directory-based patterns
    for (tool_name, top_dir), matching in dir_failures.items():
        occurrences = len(matching)
        if occurrences < min_occurrences:
            continue

        distinct_sessions = {f.session_id for f in matching}
        if len(distinct_sessions) < min_distinct_sessions:
            continue

        tool_total = tool_totals.get(tool_name, occurrences)
        confidence = occurrences / max(tool_total, 1)

        if confidence < min_confidence:
            continue

        affected_files = _extract_affected_files(matching)
        pattern_id = _generate_stable_pattern_id(
            "context_failure_dir", tool_name, top_dir
        )

        error_summary = (
            f"context_failure:{tool_name}:{top_dir}/ - "
            f"{occurrences}/{tool_total} failures in {top_dir}/ directory"
        )

        results.append(
            ErrorPatternResult(
                pattern_id=pattern_id,
                pattern_type="tool_failure",
                affected_files=tuple(sorted(affected_files)[:10]),
                error_summary=error_summary,
                occurrences=occurrences,
                confidence=round(confidence, 4),
                evidence_session_ids=tuple(sorted(distinct_sessions)),
            )
        )

    # Sort by confidence descending, limit to MAX_RESULTS_PER_TYPE
    results.sort(key=lambda r: -r["confidence"])
    return results[:MAX_RESULTS_PER_TYPE]


# =============================================================================
# Pattern Detection: Recovery Patterns
# =============================================================================


def _detect_recovery_patterns(
    sessions: Sequence[ModelSessionSnapshot],
    min_occurrences: int,
    min_confidence: float,
    min_distinct_sessions: int,
) -> list[ErrorPatternResult]:
    """Detect recovery patterns (failure -> retry -> outcome).

    Retry = same tool + same primary param + within RETRY_MAX_TOOL_GAP.
    Tracks "recovered" vs "persistent" outcomes.

    Args:
        sessions: All sessions to analyze.
        min_occurrences: Minimum occurrences threshold.
        min_confidence: Minimum confidence threshold.
        min_distinct_sessions: Minimum distinct sessions threshold.

    Returns:
        List of ErrorPatternResult for recovery patterns.
    """
    results: list[ErrorPatternResult] = []

    # Track recovery patterns: (tool_name, outcome) -> session_ids
    recovery_sessions: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    recovery_counts: Counter[tuple[str, str]] = Counter()
    recovery_files: defaultdict[tuple[str, str], set[str]] = defaultdict(set)

    for session in sessions:
        tool_executions = session.tool_executions or ()
        if len(tool_executions) < 2:
            continue

        session_id = session.session_id

        # Build index of (tool_name, primary_param) -> list of (index, success)
        param_history: defaultdict[tuple[str, str], list[tuple[int, bool]]] = (
            defaultdict(list)
        )

        for i, exec_record in enumerate(tool_executions):
            primary_param = _extract_primary_param(exec_record.tool_parameters)
            if not primary_param:
                continue  # Skip tools without path-like params to avoid false patterns
            key = (exec_record.tool_name, primary_param)
            param_history[key].append((i, exec_record.success))

        # Look for failure -> retry patterns
        for (tool_name, primary_param), history in param_history.items():
            for i, (idx_fail, success_fail) in enumerate(history):
                if success_fail:
                    continue  # Looking for failures

                # Look for retry within RETRY_MAX_TOOL_GAP
                for j in range(i + 1, len(history)):
                    idx_retry, success_retry = history[j]

                    # Check index gap
                    index_gap = idx_retry - idx_fail
                    if index_gap > RETRY_MAX_TOOL_GAP:
                        break

                    # Found a retry - determine outcome
                    outcome = "recovered" if success_retry else "persistent"
                    pattern_key = (tool_name, outcome)

                    recovery_counts[pattern_key] += 1
                    recovery_sessions[pattern_key].add(session_id)

                    if primary_param:
                        recovery_files[pattern_key].add(primary_param)

                    break  # Only count first retry

    # Total retries for confidence calculation
    total_retries = sum(recovery_counts.values()) if recovery_counts else 1

    # Generate patterns
    for (tool_name, outcome), count in recovery_counts.most_common():
        if count < min_occurrences:
            continue

        distinct_sessions = recovery_sessions[(tool_name, outcome)]
        if len(distinct_sessions) < min_distinct_sessions:
            continue

        # Confidence: proportion of this recovery type relative to all retries
        confidence = count / max(total_retries, 1)

        if confidence < min_confidence:
            continue

        pattern_id = _generate_stable_pattern_id("recovery_pattern", tool_name, outcome)

        outcome_desc = (
            "successfully recovered after retry"
            if outcome == "recovered"
            else "failed persistently despite retry"
        )

        error_summary = (
            f"recovery_pattern:{tool_name}:{outcome} - "
            f"{count} retries {outcome_desc} across {len(distinct_sessions)} sessions"
        )

        affected = recovery_files.get((tool_name, outcome), set())

        results.append(
            ErrorPatternResult(
                pattern_id=pattern_id,
                pattern_type="tool_failure",
                affected_files=tuple(sorted(affected)[:10]),
                error_summary=error_summary,
                occurrences=count,
                confidence=round(confidence, 4),
                evidence_session_ids=tuple(sorted(distinct_sessions)),
            )
        )

    # Sort by confidence descending, limit to MAX_RESULTS_PER_TYPE
    results.sort(key=lambda r: -r["confidence"])
    return results[:MAX_RESULTS_PER_TYPE]


# =============================================================================
# Pattern Detection: Failure Hotspots
# =============================================================================


def _detect_failure_hotspots(
    failures: list[_FailureRecord],
    min_occurrences: int,
    min_confidence: float,
    min_distinct_sessions: int,
) -> list[ErrorPatternResult]:
    """Detect failure hotspots (tool_name + directory level).

    Granularity: (tool_name, directory_path) NOT (tool_name, file_path).

    Args:
        failures: All failure records.
        min_occurrences: Minimum occurrences threshold.
        min_confidence: Minimum confidence threshold.
        min_distinct_sessions: Minimum distinct sessions threshold.

    Returns:
        List of ErrorPatternResult for failure hotspots.
    """
    results: list[ErrorPatternResult] = []

    # Group by (tool_name, directory)
    hotspot_failures: defaultdict[tuple[str, str], list[_FailureRecord]] = defaultdict(
        list
    )

    for failure in failures:
        directory = _extract_directory(failure.tool_parameters)
        if directory:
            hotspot_failures[(failure.tool_name, directory)].append(failure)

    # Count total failures per tool for confidence
    tool_totals: Counter[str] = Counter()
    for f in failures:
        tool_totals[f.tool_name] += 1

    # Generate patterns
    for (tool_name, directory), matching in hotspot_failures.items():
        occurrences = len(matching)
        if occurrences < min_occurrences:
            continue

        distinct_sessions = {f.session_id for f in matching}
        if len(distinct_sessions) < min_distinct_sessions:
            continue

        tool_total = tool_totals.get(tool_name, occurrences)
        confidence = occurrences / max(tool_total, 1)

        if confidence < min_confidence:
            continue

        affected_files = _extract_affected_files(matching)
        pattern_id = _generate_stable_pattern_id(
            "failure_hotspot", tool_name, directory
        )

        error_summary = (
            f"failure_hotspot:{tool_name}:{directory} - "
            f"{occurrences}/{tool_total} failures ({(confidence * 100):.0f}% of {tool_name} failures)"
        )

        results.append(
            ErrorPatternResult(
                pattern_id=pattern_id,
                pattern_type="tool_failure",
                affected_files=tuple(sorted(affected_files)[:10]),
                error_summary=error_summary,
                occurrences=occurrences,
                confidence=round(confidence, 4),
                evidence_session_ids=tuple(sorted(distinct_sessions)),
            )
        )

    # Sort by confidence descending, limit to MAX_RESULTS_PER_TYPE
    results.sort(key=lambda r: -r["confidence"])
    return results[:MAX_RESULTS_PER_TYPE]


# =============================================================================
# Helper Functions: Path and Context Extraction
# =============================================================================


def _extract_path_value(params: dict[str, Any] | None) -> str | None:
    """Extract path value from tool_parameters using alias lookup.

    Args:
        params: Tool parameters dict.

    Returns:
        Path value if found, None otherwise.
    """
    if not params or not isinstance(params, dict):
        return None

    for key in PATH_KEY_ALIASES:
        if key in params:
            value = params[key]
            if isinstance(value, str):
                return value
    return None


def _normalize_path(path: str) -> str:
    """Normalize path to posix separators.

    Args:
        path: File path string.

    Returns:
        Path with forward slashes.
    """
    return path.replace("\\", "/")


def _extract_extension(path: str | None) -> str | None:
    """Extract lowercase file extension from path.

    Args:
        path: File path string.

    Returns:
        Lowercase extension including dot (e.g., ".py"), or None.
    """
    if not path:
        return None

    path = _normalize_path(path)
    filename = path.rsplit("/", 1)[-1]

    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
        return ext if len(ext) <= 10 else None  # Sanity check

    return None


def _extract_top_level_dir(path: str | None) -> str | None:
    """Extract first path component as top-level directory.

    Args:
        path: File path string.

    Returns:
        First directory component, or None.
    """
    if not path:
        return None

    path = _normalize_path(path).lstrip("/")
    if not path:
        return None

    parts = path.split("/")
    if len(parts) > 1:
        return parts[0]

    return None


def _extract_directory(params: dict[str, Any] | None) -> str | None:
    """Extract parent directory from file path in tool_parameters.

    Args:
        params: Tool parameters dict.

    Returns:
        Parent directory path, or None.
    """
    path = _extract_path_value(params)
    if not path:
        return None

    path = _normalize_path(path)

    # Find last slash to get directory
    if "/" in path:
        directory = path.rsplit("/", 1)[0]
        return directory if directory else "/"

    return None


def _extract_context_features(params: dict[str, Any] | None) -> dict[str, Any]:
    """Extract STABLE context features from tool_parameters.

    Values in tool_parameters don't affect features - only structure matters.

    Args:
        params: Tool parameters dict.

    Returns:
        Dict with extension, top_level_dir, has_lockfile, param_shape.
    """
    if not params or not isinstance(params, dict):
        return {
            "extension": None,
            "top_level_dir": None,
            "has_lockfile": False,
            "param_shape": "",
        }

    path_value = _extract_path_value(params)

    extension = _extract_extension(path_value)
    top_level_dir = _extract_top_level_dir(path_value)
    has_lockfile = _is_lockfile_path(path_value)

    # param_shape = sorted top-level keys only, capped at 10, no values
    param_keys = sorted(set(params.keys()))[:10]
    param_shape = "|".join(param_keys)

    return {
        "extension": extension,
        "top_level_dir": top_level_dir,
        "has_lockfile": has_lockfile,
        "param_shape": param_shape,
    }


def _is_lockfile_path(path: str | None) -> bool:
    """Check if path is a common lockfile.

    Args:
        path: File path string.

    Returns:
        True if path is a known lockfile.
    """
    if not path:
        return False

    path_lower = path.lower()
    lockfile_patterns = (
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "pipfile.lock",
        "gemfile.lock",
        "cargo.lock",
        "composer.lock",
        "go.sum",
    )

    return any(pattern in path_lower for pattern in lockfile_patterns)


def _extract_primary_param(params: JsonType | None) -> str:
    """Extract primary (path-like) parameter for retry matching.

    Args:
        params: Tool parameters (JsonType).

    Returns:
        Normalized path string, or empty string if not found.
    """
    # JsonType can be many things; we only handle dict case
    if not isinstance(params, dict):
        return ""
    path = _extract_path_value(params)
    if path:
        return _normalize_path(path).lower()
    return ""


def _extract_affected_files(failures: list[_FailureRecord]) -> set[str]:
    """Extract unique file paths from failure records.

    Args:
        failures: List of failure records.

    Returns:
        Set of file paths.
    """
    files: set[str] = set()
    for failure in failures:
        path = _extract_path_value(failure.tool_parameters)
        if path:
            files.add(_normalize_path(path))
    return files


# =============================================================================
# Helper Functions: Time and Ordering
# =============================================================================


def _within_time_bound(
    exec_a: ModelToolExecution,
    exec_b: ModelToolExecution,
    max_gap_sec: int,
) -> bool:
    """Check if two executions are within time bound.

    This is a SECONDARY guard - index-based ordering is primary.

    Args:
        exec_a: First execution.
        exec_b: Second execution.
        max_gap_sec: Maximum time gap in seconds.

    Returns:
        True if within time bound or timestamps are equal/missing.
    """
    ts_a = exec_a.timestamp
    ts_b = exec_b.timestamp

    # If timestamps are identical, allow (index is primary ordering)
    if ts_a == ts_b:
        return True

    # Calculate time delta
    delta = (ts_b - ts_a).total_seconds()

    # Allow if within bounds (or negative, which shouldn't happen but handle gracefully)
    return delta <= max_gap_sec


# =============================================================================
# Helper Functions: Result Ordering
# =============================================================================


def _get_pattern_subtype(result: ErrorPatternResult) -> str:
    """Extract pattern subtype from error_summary for ordering.

    Pattern subtypes are encoded at the start of error_summary:
    - recurring_failure:...
    - failure_sequence:...
    - context_failure:...
    - recovery_pattern:...
    - failure_hotspot:...

    Args:
        result: An ErrorPatternResult dict.

    Returns:
        Pattern subtype string, or "zzz" for unknown (sorts last).
    """
    summary = result.get("error_summary", "")
    if ":" in summary:
        return summary.split(":")[0]
    return "zzz"  # Sort unknown last


def _get_primary_tool(result: ErrorPatternResult) -> str:
    """Extract primary tool name from error_summary for ordering.

    Args:
        result: An ErrorPatternResult dict.

    Returns:
        Tool name string, or empty string if not found.
    """
    summary = result.get("error_summary", "")
    parts = summary.split(":")
    if len(parts) >= 2:
        return parts[1].split("-")[0].split("/")[0]  # Handle A->B sequences
    return ""


__all__ = ["extract_tool_failure_patterns"]
