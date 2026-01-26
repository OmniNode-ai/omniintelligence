"""Pattern Extraction Compute Handlers.

This module provides pure handler functions for pattern extraction operations.
Handlers implement the computation logic following the ONEX "pure shell pattern"
where nodes delegate to side-effect-free handler functions.

Handler Pattern:
    Each handler is a pure function that:
    - Accepts session snapshots and configuration parameters
    - Extracts patterns across multiple dimensions (file, error, architecture, tool)
    - Returns typed PatternExtractionResult dictionaries
    - Has no side effects (pure computation)

Pattern Types:
    - File Access Patterns: Co-access, entry points, modification clusters
    - Error Patterns: Error-prone files, fix sequences, tool failures
    - Architecture Patterns: Module boundaries, layers, dependency chains
    - Tool Patterns: Sequences, preferences, success rates

Identity Keys:
    The insight_identity_key handler generates unique keys for deduplication:
    - Key composition varies by insight type to capture semantic identity
    - Enables efficient deduplication across sessions and extraction runs
    - Uses deterministic hashing for description-based keys

Insight Merging:
    The merge_insights handler combines duplicate insights:
    - Preserves canonical IDs and types from existing insight
    - Uses higher-confidence description
    - Unions evidence files and session IDs
    - Updates occurrence counts and timestamps

Error Handling:
    Contract-defined exceptions with error codes for structured handling:
    - PatternExtractionValidationError (PATTERN_001): Non-recoverable input errors
    - PatternExtractionComputeError (PATTERN_002): Recoverable computation errors

Usage:
    from omniintelligence.nodes.pattern_extraction_compute.handlers import (
        FileAccessPatternResult,
        ErrorPatternResult,
        ArchitecturePatternResult,
        ToolPatternResult,
        PatternExtractionResult,
        PatternExtractionMetrics,
        create_empty_metrics,
        create_error_result,
        insight_identity_key,
        merge_insights,
        PatternExtractionValidationError,
        PatternExtractionComputeError,
    )

    # Generate identity key for deduplication
    key = insight_identity_key(insight)

    # Merge duplicate insights
    if key in existing_insights:
        merged = merge_insights(new_insight, existing_insights[key])

    # Error handling with contract codes
    try:
        result = extract_patterns(session_data)
    except PatternExtractionValidationError as e:
        log.error(f"Validation failed: {e.code} - {e.message}")
    except PatternExtractionComputeError as e:
        log.warning(f"Compute error: {e.code} - {e.message}, retrying...")
"""

from omniintelligence.nodes.pattern_extraction_compute.handlers.exceptions import (
    PatternExtractionComputeError,
    PatternExtractionError,
    PatternExtractionValidationError,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_identity import (
    insight_identity_key,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_merge import (
    merge_insights,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_error_patterns import (
    extract_error_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_file_patterns import (
    extract_file_access_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_patterns import (
    extract_tool_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_architecture_patterns import (
    extract_architecture_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.protocols import (
    ArchitecturePatternResult,
    ErrorPatternResult,
    FileAccessPatternResult,
    InsightDict,
    PatternExtractionMetadata,
    PatternExtractionMetrics,
    PatternExtractionResult,
    ToolPatternResult,
    create_empty_metrics,
    create_error_result,
)

__all__ = [
    "ArchitecturePatternResult",
    "ErrorPatternResult",
    "FileAccessPatternResult",
    "InsightDict",
    "PatternExtractionComputeError",
    "PatternExtractionError",
    "PatternExtractionMetadata",
    "PatternExtractionMetrics",
    "PatternExtractionResult",
    "PatternExtractionValidationError",
    "ToolPatternResult",
    "create_empty_metrics",
    "create_error_result",
    "extract_architecture_patterns",
    "extract_error_patterns",
    "extract_file_access_patterns",
    "extract_tool_patterns",
    "insight_identity_key",
    "merge_insights",
]
