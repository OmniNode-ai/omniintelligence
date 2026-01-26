"""Type protocols for pattern extraction handler results.

This module defines TypedDict structures for type-safe handler responses,
enabling static type checking with mypy and improved IDE support.

Design Decisions:
    - TypedDict is used because handlers return dicts, not objects with methods.
    - All confidence scores are normalized to 0.0-1.0 range for consistency.
    - Pattern types are string literals for extensibility.
    - Factory functions provide safe defaults for error/empty cases.
    - Immutable tuples used for collections to encourage functional patterns.

Pattern Types:
    - FileAccessPatternResult: Co-access, entry points, modification clusters
    - ErrorPatternResult: Error-prone files, fix sequences, tool failures
    - ArchitecturePatternResult: Module boundaries, layers, dependency chains
    - ToolPatternResult: Tool sequences, preferences, success rates

Usage:
    from omniintelligence.nodes.pattern_extraction_compute.handlers.protocols import (
        FileAccessPatternResult,
        ErrorPatternResult,
        ArchitecturePatternResult,
        ToolPatternResult,
        PatternExtractionResult,
        PatternExtractionMetrics,
    )

    def extract_file_patterns(...) -> list[FileAccessPatternResult]:
        return [
            {
                "pattern_id": "fp_001",
                "pattern_type": "co_access",
                "files": ("src/models.py", "src/schemas.py"),
                ...
            }
        ]
"""

from __future__ import annotations

from typing import Literal, TypedDict
from uuid import uuid4


# =============================================================================
# File Access Pattern Result TypedDict
# =============================================================================


class FileAccessPatternResult(TypedDict):
    """File access pattern extraction result.

    Represents patterns detected in how files are accessed together
    during Claude Code sessions.

    Pattern Types:
        - co_access: Files frequently accessed together in the same session
        - entry_point: Files that commonly start editing sessions
        - modification_cluster: Files that are modified together

    Attributes:
        pattern_id: Unique identifier for this pattern instance.
        pattern_type: Type of file access pattern detected.
        files: Tuple of file paths involved in this pattern.
        occurrences: Number of sessions where this pattern was observed.
        confidence: Confidence score (0.0-1.0) based on consistency and frequency.
        evidence_session_ids: Session IDs where this pattern was observed.

    Example:
        >>> result: FileAccessPatternResult = {
        ...     "pattern_id": "fp_001",
        ...     "pattern_type": "co_access",
        ...     "files": ("src/models.py", "src/schemas.py"),
        ...     "occurrences": 5,
        ...     "confidence": 0.85,
        ...     "evidence_session_ids": ("sess_1", "sess_2"),
        ... }
    """

    pattern_id: str
    pattern_type: Literal["co_access", "entry_point", "modification_cluster"]
    files: tuple[str, ...]
    occurrences: int
    confidence: float
    evidence_session_ids: tuple[str, ...]


# =============================================================================
# Architecture Pattern Result TypedDict
# =============================================================================


class ArchitecturePatternResult(TypedDict):
    """Result structure for an extracted architecture pattern.

    This TypedDict defines the guaranteed structure returned by the
    extract_architecture_patterns function for each detected pattern.

    Pattern Types:
        - module_boundary: Directory clusters that are accessed together,
          indicating related functionality or feature boundaries.
        - layer_pattern: Common path prefixes indicating architectural layers
          (e.g., src/, tests/, lib/, api/).
        - dependency_chain: Files accessed in sequence indicating dependencies
          or workflow patterns.

    All Attributes are Required:
        pattern_id: Unique identifier for this pattern instance (UUID string).
        pattern_type: Category of pattern detected (module_boundary, layer_pattern,
            dependency_chain).
        directory_prefix: Common directory prefix or path for this pattern.
        member_files: Tuple of file paths that belong to this pattern (limited
            to top 10 for performance).
        occurrences: Number of times this pattern was observed across sessions.
        confidence: Confidence score (0.0-1.0) based on occurrence frequency
            and consistency.

    Example:
        >>> result: ArchitecturePatternResult = {
        ...     "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
        ...     "pattern_type": "module_boundary",
        ...     "directory_prefix": "src/omniintelligence/nodes",
        ...     "member_files": (
        ...         "src/omniintelligence/nodes/quality_scoring_compute/node.py",
        ...         "src/omniintelligence/nodes/quality_scoring_compute/handlers/handler.py",
        ...     ),
        ...     "occurrences": 15,
        ...     "confidence": 0.85,
        ... }
    """

    pattern_id: str
    pattern_type: Literal["module_boundary", "layer_pattern", "dependency_chain"]
    directory_prefix: str
    member_files: tuple[str, ...]
    occurrences: int
    confidence: float


# =============================================================================
# Tool Pattern Result TypedDict
# =============================================================================


class ToolPatternResult(TypedDict):
    """Result structure for an extracted tool usage pattern.

    This TypedDict defines the guaranteed structure returned by the
    extract_tool_patterns function for each detected tool pattern.

    Pattern Types:
        - tool_sequence: Common tool chains (Read -> Edit -> Bash) that
          indicate workflow patterns in how developers use tools together.
        - tool_preference: Which tools are preferred for which file types
          or contexts, helping understand tool selection patterns.
        - success_rate: Effectiveness metrics for tools in different contexts,
          identifying tools that work well (or poorly) for specific tasks.

    All Attributes are Required:
        pattern_id: Unique identifier for this pattern instance (UUID string).
        pattern_type: Category of tool pattern detected.
        tools: Tuple of tool names involved in this pattern.
        context: Context description (e.g., file type, workflow stage).
        occurrences: Number of times this pattern was observed.
        confidence: Confidence score (0.0-1.0) based on occurrence frequency.
        success_rate: Success rate for this pattern (None for non-success patterns).

    Example:
        >>> result: ToolPatternResult = {
        ...     "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
        ...     "pattern_type": "tool_sequence",
        ...     "tools": ("Read", "Edit", "Bash"),
        ...     "context": "workflow_pattern",
        ...     "occurrences": 15,
        ...     "confidence": 0.85,
        ...     "success_rate": None,
        ... }
    """

    pattern_id: str
    pattern_type: Literal["tool_sequence", "tool_preference", "success_rate"]
    tools: tuple[str, ...]
    context: str
    occurrences: int
    confidence: float
    success_rate: float | None


# =============================================================================
# Error Pattern Result TypedDict
# =============================================================================


class ErrorPatternResult(TypedDict):
    """Result structure for an extracted error pattern.

    This TypedDict defines the guaranteed structure returned by the
    extract_error_patterns function for each detected error pattern.

    Pattern Types:
        - error_prone_file: Files with high failure rates across sessions,
          indicating fragile or problematic code paths.
        - tool_failure: Specific tools that consistently fail on specific
          file types or extensions (e.g., Edit fails on .yaml files).
        - error_sequence: Common error -> fix patterns that indicate
          recurring issues with predictable remediation steps.

    All Attributes are Required:
        pattern_id: Unique identifier for this pattern instance (UUID string).
        pattern_type: Category of error pattern detected.
        affected_files: Tuple of file paths affected by this pattern.
        error_summary: Human-readable summary of the error pattern or common
            error message.
        occurrences: Number of times this error pattern was observed.
        confidence: Confidence score (0.0-1.0) based on failure rate and
            occurrence frequency.
        evidence_session_ids: Tuple of session IDs where this pattern was observed.

    Example:
        >>> result: ErrorPatternResult = {
        ...     "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
        ...     "pattern_type": "error_prone_file",
        ...     "affected_files": ("src/api/handler.py",),
        ...     "error_summary": "Validation failed: missing required field",
        ...     "occurrences": 5,
        ...     "confidence": 0.85,
        ...     "evidence_session_ids": ("session-1", "session-2"),
        ... }
    """

    pattern_id: str
    pattern_type: Literal["error_prone_file", "tool_failure", "error_sequence"]
    affected_files: tuple[str, ...]
    error_summary: str
    occurrences: int
    confidence: float
    evidence_session_ids: tuple[str, ...]


# =============================================================================
# Factory Functions
# =============================================================================


def create_empty_error_pattern(
    pattern_type: Literal[
        "error_prone_file", "tool_failure", "error_sequence"
    ] = "error_prone_file",
) -> ErrorPatternResult:
    """Create an empty error pattern for error or placeholder cases.

    Returns a valid ErrorPatternResult with minimal default values,
    suitable for use when extraction fails or produces no results.

    Args:
        pattern_type: The type of error pattern to create.
            Defaults to "error_prone_file".

    Returns:
        ErrorPatternResult with zero confidence and empty collections.

    Example:
        >>> pattern = create_empty_error_pattern()
        >>> pattern["confidence"]
        0.0
        >>> pattern["affected_files"]
        ()
    """
    return ErrorPatternResult(
        pattern_id=str(uuid4()),
        pattern_type=pattern_type,
        affected_files=(),
        error_summary="",
        occurrences=0,
        confidence=0.0,
        evidence_session_ids=(),
    )


def create_empty_tool_pattern(
    pattern_type: Literal[
        "tool_sequence", "tool_preference", "success_rate"
    ] = "tool_sequence",
) -> ToolPatternResult:
    """Create an empty tool pattern for error or placeholder cases.

    Returns a valid ToolPatternResult with minimal default values,
    suitable for use when extraction fails or produces no results.

    Args:
        pattern_type: The type of tool pattern to create.
            Defaults to "tool_sequence".

    Returns:
        ToolPatternResult with zero confidence and empty collections.

    Example:
        >>> pattern = create_empty_tool_pattern()
        >>> pattern["confidence"]
        0.0
        >>> pattern["tools"]
        ()
    """
    return ToolPatternResult(
        pattern_id=str(uuid4()),
        pattern_type=pattern_type,
        tools=(),
        context="",
        occurrences=0,
        confidence=0.0,
        success_rate=None,
    )


def create_empty_architecture_pattern(
    pattern_type: Literal[
        "module_boundary", "layer_pattern", "dependency_chain"
    ] = "module_boundary",
) -> ArchitecturePatternResult:
    """Create an empty architecture pattern for error or placeholder cases.

    Returns a valid ArchitecturePatternResult with minimal default values,
    suitable for use when extraction fails or produces no results.

    Args:
        pattern_type: The type of pattern to create. Defaults to "module_boundary".

    Returns:
        ArchitecturePatternResult with zero confidence and empty members.

    Example:
        >>> pattern = create_empty_architecture_pattern()
        >>> pattern["confidence"]
        0.0
        >>> pattern["member_files"]
        ()
    """
    return ArchitecturePatternResult(
        pattern_id=str(uuid4()),
        pattern_type=pattern_type,
        directory_prefix="",
        member_files=(),
        occurrences=0,
        confidence=0.0,
    )


def create_empty_file_pattern(
    pattern_type: Literal[
        "co_access", "entry_point", "modification_cluster"
    ] = "co_access",
) -> FileAccessPatternResult:
    """Create an empty file pattern for error or placeholder cases.

    Returns a valid FileAccessPatternResult with minimal default values,
    suitable for use when extraction fails or produces no results.

    Args:
        pattern_type: The type of file pattern to create.
            Defaults to "co_access".

    Returns:
        FileAccessPatternResult with zero confidence and empty collections.
    """
    return FileAccessPatternResult(
        pattern_id=str(uuid4()),
        pattern_type=pattern_type,
        files=(),
        occurrences=0,
        confidence=0.0,
        evidence_session_ids=(),
    )


# =============================================================================
# Insight TypedDict
# =============================================================================


class InsightDict(TypedDict):
    """A single insight extracted from pattern analysis.

    Insights are human-readable observations derived from pattern data
    that can guide development or highlight areas of concern.

    Attributes:
        category: Category of the insight (e.g., "architecture", "workflow",
            "error_prone", "optimization").
        severity: Severity level indicating importance.
        message: Human-readable description of the insight.
        evidence: Supporting pattern IDs that led to this insight.
        suggested_action: Optional suggested action to address the insight.

    Example:
        >>> insight: InsightDict = {
        ...     "category": "architecture",
        ...     "severity": "warning",
        ...     "message": "High coupling detected between api/ and database/ modules",
        ...     "evidence": ("arch_001", "arch_002"),
        ...     "suggested_action": "Consider adding an abstraction layer",
        ... }
    """

    category: str
    severity: Literal["info", "warning", "critical"]
    message: str
    evidence: tuple[str, ...]
    suggested_action: str | None


# =============================================================================
# Pattern Extraction Metadata TypedDict
# =============================================================================


class PatternExtractionMetadata(TypedDict, total=False):
    """Metadata about the pattern extraction operation.

    Contains information about the extraction process for debugging,
    observability, and audit purposes. All fields are optional.

    Attributes:
        processing_time_ms: Time taken for extraction in milliseconds.
        algorithm_version: Version of the extraction algorithm used.
        session_count: Number of sessions analyzed.
        correlation_id: Request correlation ID for distributed tracing.
        timestamp_utc: UTC timestamp when extraction was performed.
    """

    processing_time_ms: float
    algorithm_version: str
    session_count: int
    correlation_id: str
    timestamp_utc: str


# =============================================================================
# Pattern Extraction Metrics TypedDict
# =============================================================================


class PatternExtractionMetrics(TypedDict):
    """Metrics summarizing the pattern extraction results.

    Provides aggregate statistics about extracted patterns for
    monitoring and dashboard purposes.

    All Attributes are Required:
        total_patterns: Total number of patterns extracted across all types.
        architecture_pattern_count: Number of architecture patterns detected.
        file_access_pattern_count: Number of file access patterns detected.
        error_pattern_count: Number of error patterns detected.
        tool_pattern_count: Number of tool patterns detected.
        average_confidence: Average confidence score across all patterns.
        insight_count: Number of insights generated from patterns.

    Example:
        >>> metrics: PatternExtractionMetrics = {
        ...     "total_patterns": 25,
        ...     "architecture_pattern_count": 8,
        ...     "file_access_pattern_count": 10,
        ...     "error_pattern_count": 3,
        ...     "tool_pattern_count": 4,
        ...     "average_confidence": 0.78,
        ...     "insight_count": 5,
        ... }
    """

    total_patterns: int
    architecture_pattern_count: int
    file_access_pattern_count: int
    error_pattern_count: int
    tool_pattern_count: int
    average_confidence: float
    insight_count: int


# =============================================================================
# Pattern Extraction Result TypedDict
# =============================================================================


class PatternExtractionResult(TypedDict):
    """Complete result structure for pattern extraction.

    This TypedDict defines the guaranteed structure returned by the
    main pattern extraction function, aggregating all pattern types.

    All Attributes are Required:
        success: Whether extraction completed without fatal errors.
        architecture_patterns: List of architecture patterns detected.
        file_access_patterns: List of file access patterns detected.
        error_patterns: List of error patterns detected.
        tool_patterns: List of tool patterns detected.
        insights: List of insights derived from pattern analysis.
        metrics: Summary metrics for the extraction.
        metadata: Operation metadata for observability.
        warnings: List of non-fatal warnings encountered.

    Example:
        >>> result: PatternExtractionResult = {
        ...     "success": True,
        ...     "architecture_patterns": [...],
        ...     "file_access_patterns": [...],
        ...     "error_patterns": [...],
        ...     "tool_patterns": [...],
        ...     "insights": [...],
        ...     "metrics": {...},
        ...     "metadata": {...},
        ...     "warnings": [],
        ... }
    """

    success: bool
    architecture_patterns: list[ArchitecturePatternResult]
    file_access_patterns: list[FileAccessPatternResult]
    error_patterns: list[ErrorPatternResult]
    tool_patterns: list[ToolPatternResult]
    insights: list[InsightDict]
    metrics: PatternExtractionMetrics
    metadata: PatternExtractionMetadata
    warnings: list[str]


# =============================================================================
# Additional Factory Functions
# =============================================================================


def create_empty_metrics() -> PatternExtractionMetrics:
    """Create empty metrics for error or placeholder cases.

    Returns a valid PatternExtractionMetrics with zero values,
    suitable for use when extraction fails or produces no results.

    Returns:
        PatternExtractionMetrics with all counts at zero.

    Example:
        >>> metrics = create_empty_metrics()
        >>> metrics["total_patterns"]
        0
    """
    return PatternExtractionMetrics(
        total_patterns=0,
        architecture_pattern_count=0,
        file_access_pattern_count=0,
        error_pattern_count=0,
        tool_pattern_count=0,
        average_confidence=0.0,
        insight_count=0,
    )


def create_error_result(
    error_message: str,
    *,
    algorithm_version: str = "1.0.0",
) -> PatternExtractionResult:
    """Create an error result for failed extraction.

    Factory function that creates a valid PatternExtractionResult
    indicating failure, suitable for returning when extraction fails.

    Args:
        error_message: Description of the error (added to warnings).
        algorithm_version: Version string for metadata.

    Returns:
        PatternExtractionResult with success=False and empty data.

    Example:
        >>> result = create_error_result("No sessions provided")
        >>> result["success"]
        False
        >>> result["warnings"]
        ['No sessions provided']
    """
    return PatternExtractionResult(
        success=False,
        architecture_patterns=[],
        file_access_patterns=[],
        error_patterns=[],
        tool_patterns=[],
        insights=[],
        metrics=create_empty_metrics(),
        metadata=PatternExtractionMetadata(
            algorithm_version=algorithm_version,
            session_count=0,
        ),
        warnings=[error_message],
    )


__all__ = [
    "ArchitecturePatternResult",
    "ErrorPatternResult",
    "FileAccessPatternResult",
    "InsightDict",
    "PatternExtractionMetadata",
    "PatternExtractionMetrics",
    "PatternExtractionResult",
    "ToolPatternResult",
    "create_empty_architecture_pattern",
    "create_empty_error_pattern",
    "create_empty_file_pattern",
    "create_empty_metrics",
    "create_empty_tool_pattern",
    "create_error_result",
]
