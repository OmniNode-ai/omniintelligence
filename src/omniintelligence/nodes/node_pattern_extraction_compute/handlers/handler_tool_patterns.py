# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tool usage pattern extraction from session data.

This module implements a pure functional handler for extracting tool usage
patterns from Claude Code session snapshots. It identifies three categories
of patterns:

1. **Tool Sequences**: Common tool chains like Read -> Edit -> Bash that
   indicate workflow patterns in how developers use tools together.

2. **Tool Preferences**: Which tools are frequently used with which file types
   (inferred from files_accessed extensions), helping understand tool selection.

3. **Session Success Rates**: Tool usage patterns in successful vs failed sessions,
   identifying tools associated with good outcomes.

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
    from omniintelligence.nodes.node_pattern_extraction_compute.models import (
        ModelSessionSnapshot,
    )

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.protocols import (
    ToolPatternResult,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.utils import (
    get_extension,
)

# Confidence calculation significance factors
# These control how occurrence counts translate to confidence scores.
# Higher factors require more occurrences to reach full confidence.

BIGRAM_SEQUENCE_SIGNIFICANCE_FACTOR = 2
"""Tool bigrams: expect ~2 bigrams per session on average, so 2x sessions = full confidence."""

TOOL_PREFERENCE_SIGNIFICANCE_FACTOR = 3
"""Tool preferences: expect multiple tool-type associations per session (3x sessions)."""

SUCCESS_RATE_SIGNIFICANCE_FACTOR = 5
"""Success rates: require substantial sample size for statistical relevance (5x sessions)."""


def extract_tool_patterns(
    sessions: Sequence[ModelSessionSnapshot],
    min_occurrences: int = 2,
    min_confidence: float = 0.6,
    min_distinct_sessions: int = 2,  # noqa: ARG001 - Unused, for uniform interface
    max_results_per_type: int = 20,  # noqa: ARG001 - Unused, for uniform interface
) -> list[ToolPatternResult]:
    """Extract tool usage patterns from sessions.

    Analyzes Claude Code session snapshots to identify recurring patterns
    in tool usage. This function is pure (no side effects) and deterministic
    for the same input data.

    Patterns detected:
        1. Tool sequences: Common tool chains (Read -> Edit -> Bash)
        2. Tool preferences: Which tools for which file type contexts
        3. Session success rates: Tool effectiveness based on session outcome

    Algorithm:
        1. Iterate through all sessions and their tools_used sequences
        2. Track bigram and trigram tool sequences
        3. Infer tool-to-file-type associations from files_accessed
        4. Track success/failure rates per tool based on session outcome
        5. Filter patterns by minimum occurrence and confidence thresholds
        6. Return normalized, deduplicated pattern results

    Args:
        sessions: Session snapshots to analyze. Each session should have:
            - tools_used (tuple[str, ...]): Tool names in order of invocation
            - files_accessed (tuple[str, ...]): Files read during session
            - outcome (str): Session outcome (success, failure, partial, unknown)
        min_occurrences: Minimum times pattern must occur to be included.
            Defaults to 2 to filter out one-off occurrences.
        min_confidence: Minimum confidence threshold (0.0-1.0) for patterns.
            Defaults to 0.6 to ensure statistical relevance.

    Returns:
        List of detected tool patterns, ordered by pattern type:
        sequences first, then preferences, then success rates.

    Examples:
        >>> sessions = [
        ...     MockSession(
        ...         tools_used=("Read", "Edit", "Bash"),
        ...         files_accessed=("api.py",),
        ...         outcome="success",
        ...     ),
        ... ]
        >>> patterns = extract_tool_patterns(sessions)
        >>> for p in patterns:
        ...     print(f"{p.pattern_type}: {p.tools} ({p.confidence:.2f})")
    """
    results: list[ToolPatternResult] = []

    # Track tool sequences (bigrams and trigrams)
    tool_bigrams: Counter[tuple[str, str]] = Counter()
    tool_trigrams: Counter[tuple[str, str, str]] = Counter()

    # Track tool preferences by file type context
    tool_by_ext: Counter[tuple[str, str]] = Counter()  # (tool, ext)

    # Track success rates by tool
    tool_success: defaultdict[str, list[bool]] = defaultdict(list)
    tool_context_success: defaultdict[tuple[str, str], list[bool]] = defaultdict(list)

    for session in sessions:
        tools_used = getattr(session, "tools_used", None) or ()
        files_accessed = getattr(session, "files_accessed", None) or ()
        outcome = getattr(session, "outcome", "unknown") or "unknown"

        # Convert tools_used to list for iteration
        tool_names = list(tools_used)

        # Determine session success
        is_success = outcome == "success"

        # Track tool usage and success
        for tool_name in tool_names:
            if not tool_name:
                continue

            tool_success[tool_name].append(is_success)

        # Infer tool-to-file-type associations
        # Associate each tool with the file extensions present in the session
        session_extensions = set()
        for file_path in files_accessed:
            ext = get_extension(file_path)
            if ext:
                session_extensions.add(ext)

        # Track tool usage in context of file types
        for tool_name in set(tool_names):  # Use set to count once per session
            if not tool_name:
                continue
            for ext in session_extensions:
                tool_by_ext[(tool_name, ext)] += 1

            # Track context-specific success
            context = _get_session_context(files_accessed)
            tool_context_success[(tool_name, context)].append(is_success)

        # Track sequences (bigrams)
        for i in range(len(tool_names) - 1):
            if tool_names[i] and tool_names[i + 1]:
                tool_bigrams[(tool_names[i], tool_names[i + 1])] += 1

        # Track sequences (trigrams)
        for i in range(len(tool_names) - 2):
            if tool_names[i] and tool_names[i + 1] and tool_names[i + 2]:
                tool_trigrams[
                    (tool_names[i], tool_names[i + 1], tool_names[i + 2])
                ] += 1

    total_sessions = len(sessions) if sessions else 1

    # Generate tool sequence patterns (bigrams)
    for (t1, t2), count in tool_bigrams.most_common(20):
        if count < min_occurrences:
            break

        confidence = min(
            1.0, count / (total_sessions * BIGRAM_SEQUENCE_SIGNIFICANCE_FACTOR)
        )
        if confidence >= min_confidence:
            results.append(
                ToolPatternResult(
                    pattern_id=str(uuid4()),
                    pattern_type="tool_sequence",
                    tools=(t1, t2),
                    context="sequential_usage",
                    occurrences=count,
                    confidence=confidence,
                    success_rate=None,
                )
            )

    # Generate tool sequence patterns (trigrams for stronger patterns)
    for (t1, t2, t3), count in tool_trigrams.most_common(10):
        if count < min_occurrences:
            break

        confidence = min(1.0, count / total_sessions)
        if confidence >= min_confidence:
            results.append(
                ToolPatternResult(
                    pattern_id=str(uuid4()),
                    pattern_type="tool_sequence",
                    tools=(t1, t2, t3),
                    context="workflow_pattern",
                    occurrences=count,
                    confidence=confidence,
                    success_rate=None,
                )
            )

    # Generate tool preference patterns (tool + file type)
    for (tool, ext), count in tool_by_ext.most_common(30):
        if count < min_occurrences:
            break

        confidence = min(
            1.0, count / (total_sessions * TOOL_PREFERENCE_SIGNIFICANCE_FACTOR)
        )
        if confidence >= min_confidence:
            results.append(
                ToolPatternResult(
                    pattern_id=str(uuid4()),
                    pattern_type="tool_preference",
                    tools=(tool,),
                    context=f"{ext}_files",
                    occurrences=count,
                    confidence=confidence,
                    success_rate=None,
                )
            )

    # Generate success rate patterns based on session outcomes
    for tool, successes in tool_success.items():
        if len(successes) < min_occurrences:
            continue

        success_rate = sum(successes) / len(successes)
        # Only report notably high or low success rates
        if success_rate >= 0.9 or success_rate <= 0.5:
            confidence = min(
                1.0,
                len(successes) / (total_sessions * SUCCESS_RATE_SIGNIFICANCE_FACTOR),
            )
            if confidence >= min_confidence:
                results.append(
                    ToolPatternResult(
                        pattern_id=str(uuid4()),
                        pattern_type="success_rate",
                        tools=(tool,),
                        context="overall",
                        occurrences=len(successes),
                        confidence=confidence,
                        success_rate=success_rate,
                    )
                )

    return results


def _get_session_context(files_accessed: tuple[str, ...] | list[str]) -> str:
    """Determine session context from accessed files.

    Categorizes a session based on the types of files accessed,
    using common project structure patterns.

    Args:
        files_accessed: Collection of file paths accessed in the session.

    Returns:
        Context category string representing the dominant file type.

    Examples:
        >>> _get_session_context(["/project/tests/test_utils.py"])
        'test_files'
        >>> _get_session_context(["/project/src/module.py", "/project/src/api.py"])
        'source_files'
        >>> _get_session_context(["/project/config.yaml"])
        'config_files'
        >>> _get_session_context(["/project/README.md"])
        'documentation'
    """
    if not files_accessed:
        return "general"

    # Count file types
    test_count = 0
    source_count = 0
    config_count = 0
    doc_count = 0

    for file_path in files_accessed:
        path_lower = file_path.lower()

        if "test" in path_lower:
            test_count += 1
        elif "src/" in path_lower or "lib/" in path_lower:
            source_count += 1
        elif "config" in path_lower or path_lower.endswith(
            (".json", ".yaml", ".yml", ".toml")
        ):
            config_count += 1
        elif "doc" in path_lower or path_lower.endswith(".md"):
            doc_count += 1

    # Return dominant context
    max_count = max(test_count, source_count, config_count, doc_count)
    if max_count == 0:
        return "general"
    if test_count == max_count:
        return "test_files"
    if source_count == max_count:
        return "source_files"
    if config_count == max_count:
        return "config_files"
    if doc_count == max_count:
        return "documentation"

    return "general"


__all__ = ["extract_tool_patterns"]
