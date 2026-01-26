"""Error pattern extraction from session data.

This module implements a pure functional handler for extracting error patterns
from Claude Code session snapshots. It identifies two categories of error
patterns:

1. **Error-Prone Files**: Files that appear frequently in sessions with errors,
   indicating fragile or problematic code paths that frequently cause errors.

2. **Session Failure Patterns**: Common error messages and failure outcomes
   across sessions, helping identify recurring issues.

ONEX Compliance:
    - Pure functional design (no side effects)
    - Deterministic results for same inputs
    - No external service calls or I/O operations
    - All state passed explicitly through parameters
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from omniintelligence.nodes.pattern_extraction_compute.models import (
        ModelSessionSnapshot,
    )

from omniintelligence.nodes.pattern_extraction_compute.handlers.protocols import (
    ErrorPatternResult,
)


def extract_error_patterns(
    sessions: Sequence[ModelSessionSnapshot],
    min_occurrences: int = 2,
    min_confidence: float = 0.6,
) -> list[ErrorPatternResult]:
    """Extract error patterns from sessions.

    Analyzes Claude Code session snapshots to identify recurring error
    patterns. This function is pure (no side effects) and deterministic
    for the same input data.

    Patterns detected:
        1. Error-prone files: Files in sessions with errors/failures
        2. Common error messages: Recurring error patterns across sessions

    Algorithm:
        1. Iterate through all sessions checking outcome and errors_encountered
        2. Track files associated with failed sessions
        3. Track error message patterns
        4. Calculate failure rates and confidence scores
        5. Filter patterns by minimum occurrence and confidence thresholds
        6. Return normalized, deduplicated pattern results

    Args:
        sessions: Session snapshots to analyze. Each session should have:
            - session_id (str): Unique session identifier
            - files_accessed (tuple[str, ...]): Files read during session
            - files_modified (tuple[str, ...]): Files modified during session
            - errors_encountered (tuple[str, ...]): Error messages
            - outcome (str): Session outcome (success, failure, partial, unknown)
        min_occurrences: Minimum times pattern must occur to be included.
            Defaults to 2 to filter out one-off occurrences.
        min_confidence: Minimum confidence threshold (0.0-1.0) for patterns.
            Defaults to 0.6 to ensure statistical relevance.

    Returns:
        List of detected error patterns, ordered by:
        - Error-prone files (sorted by confidence descending)
        - Common error patterns (sorted by confidence descending)

    Examples:
        >>> sessions = [
        ...     MockSession(
        ...         session_id="s1",
        ...         files_accessed=("api.py",),
        ...         files_modified=(),
        ...         errors_encountered=("FileNotFoundError",),
        ...         outcome="failure",
        ...     ),
        ... ]
        >>> patterns = extract_error_patterns(sessions)
        >>> for p in patterns:
        ...     ptype, summary = p['pattern_type'], p['error_summary']
        ...     print(f"{ptype}: {summary} ({p['confidence']:.2f})")
    """
    results: list[ErrorPatternResult] = []

    # Track error occurrences
    file_error_count: Counter[str] = Counter()
    file_total_count: Counter[str] = Counter()
    error_messages: Counter[str] = Counter()
    session_errors: defaultdict[str, set[str]] = defaultdict(set)
    file_error_contexts: defaultdict[str, list[str]] = defaultdict(list)

    for session in sessions:
        session_id = getattr(session, "session_id", str(uuid4()))
        files_accessed = getattr(session, "files_accessed", None) or ()
        files_modified = getattr(session, "files_modified", None) or ()
        errors_encountered = getattr(session, "errors_encountered", None) or ()
        outcome = getattr(session, "outcome", "unknown") or "unknown"

        # Track total file access counts
        all_files = set(files_accessed) | set(files_modified)
        for file_path in all_files:
            file_total_count[file_path] += 1

        # Check if session had errors (either explicit errors or failure outcome)
        has_errors = len(errors_encountered) > 0 or outcome == "failure"

        if has_errors:
            # Track files in error sessions
            for file_path in all_files:
                file_error_count[file_path] += 1
                session_errors[session_id].add(file_path)
                # Add error context to file
                for error in errors_encountered:
                    file_error_contexts[file_path].append(str(error)[:100])

            # Track error messages
            for error in errors_encountered:
                # Normalize error message (truncate and clean)
                error_normalized = str(error)[:100].strip()
                if error_normalized:
                    error_messages[error_normalized] += 1

    total_sessions = len(sessions) if sessions else 1
    failed_sessions = sum(
        1
        for s in sessions
        if (getattr(s, "outcome", "") == "failure")
        or len(getattr(s, "errors_encountered", ()) or ()) > 0
    )

    # Generate error-prone file patterns
    for file_path, error_count in file_error_count.most_common():
        if error_count < min_occurrences:
            break

        total_ops = file_total_count.get(file_path, error_count)
        failure_rate = error_count / max(total_ops, 1)
        # Confidence based on failure rate and how often the file appears in errors
        confidence = min(1.0, failure_rate * (error_count / max(failed_sessions, 1)))

        if confidence >= min_confidence:
            evidence = tuple(
                sid for sid, files in session_errors.items() if file_path in files
            )
            # Summarize errors
            contexts = file_error_contexts.get(file_path, [])
            summary = _summarize_errors(contexts) if contexts else "Session failures"

            results.append(
                ErrorPatternResult(
                    pattern_id=str(uuid4()),
                    pattern_type="error_prone_file",
                    affected_files=(file_path,),
                    error_summary=summary,
                    occurrences=error_count,
                    confidence=confidence,
                    evidence_session_ids=evidence,
                )
            )

    # Generate common error message patterns (using error_sequence type for recurring errors)
    for error_msg, count in error_messages.most_common(10):
        if count < min_occurrences:
            break

        # Confidence based on frequency of this error relative to failed sessions
        confidence = min(1.0, count / max(failed_sessions, 1))

        if confidence >= min_confidence:
            results.append(
                ErrorPatternResult(
                    pattern_id=str(uuid4()),
                    pattern_type="error_sequence",
                    affected_files=(),
                    error_summary=error_msg,
                    occurrences=count,
                    confidence=confidence,
                    evidence_session_ids=(),
                )
            )

    return results


def _get_extension(file_path: str) -> str:
    """Extract file extension from path.

    Returns the extension including the leading dot (e.g., '.py')
    or empty string if no extension found.

    Args:
        file_path: File path to extract extension from.

    Returns:
        File extension with leading dot, or empty string.

    Examples:
        >>> _get_extension("/path/to/file.py")
        '.py'
        >>> _get_extension("README")
        ''
        >>> _get_extension("config.settings.yaml")
        '.yaml'
    """
    if "." in file_path:
        return "." + file_path.rsplit(".", 1)[-1]
    return ""


def _summarize_errors(contexts: list[str]) -> str:
    """Summarize error messages from multiple occurrences.

    Identifies the most common error message and provides context
    about additional error types if multiple distinct errors exist.

    Args:
        contexts: List of error message snippets (truncated to 100 chars).

    Returns:
        Human-readable summary of the error patterns.

    Examples:
        >>> _summarize_errors(["FileNotFoundError", "FileNotFoundError"])
        'FileNotFoundError'
        >>> _summarize_errors(["ValidationError", "TypeError", "ValueError"])
        'ValidationError (and 2 other error types)'
    """
    if not contexts:
        return "Unknown errors"

    # Find most common error pattern
    error_types = Counter(contexts)
    most_common = error_types.most_common(1)[0][0]

    if len(error_types) == 1:
        return most_common
    return f"{most_common} (and {len(error_types) - 1} other error types)"


__all__ = ["extract_error_patterns"]
