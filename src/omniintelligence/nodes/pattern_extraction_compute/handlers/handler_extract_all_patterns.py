"""Handler for full pattern extraction workflow.

This handler implements the main pattern extraction logic as a pure function.
It coordinates all extractor functions and handles the complete workflow:
- Input validation
- Reference time resolution
- Running all extractors based on config flags
- Converting results to insights
- Deduplication and merging with existing insights
- Metrics and metadata construction
- Error handling

This follows the ONEX declarative pattern where the node is a thin shell
and all business logic lives in handler functions.

Ticket: OMN-1402
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from omniintelligence.nodes.pattern_extraction_compute.handlers.exceptions import (
    PatternExtractionComputeError,
    PatternExtractionValidationError,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_architecture_patterns import (
    extract_architecture_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_converters import (
    convert_architecture_patterns,
    convert_error_patterns,
    convert_file_patterns,
    convert_tool_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_error_patterns import (
    extract_error_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_file_patterns import (
    extract_file_access_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_identity import (
    insight_identity_key,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_merge import (
    merge_insights,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
    extract_tool_failure_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_patterns import (
    extract_tool_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.models import (
    ModelCodebaseInsight,
    ModelExtractionConfig,
    ModelExtractionMetrics,
    ModelPatternExtractionInput,
    ModelPatternExtractionMetadata,
    ModelPatternExtractionOutput,
    ModelSessionSnapshot,
)

logger = logging.getLogger(__name__)

# Type aliases for extractor and converter functions
# All extractors now have a uniform signature:
#   (sessions, min_occurrences, min_confidence, min_distinct_sessions, max_results_per_type)
_ExtractorFunc = Callable[
    [Sequence[ModelSessionSnapshot], int, float, int, int],
    list[Any],
]
_ConverterFunc = Callable[
    [list[Any], datetime],
    list[ModelCodebaseInsight],
]

# Declarative extractor registry: (id, config_flag, metrics_field, extractor, converter)
# This follows the ONEX pattern where extractors are wired declaratively
# rather than via if/else branching.
_EXTRACTORS: list[tuple[str, str, str, _ExtractorFunc, _ConverterFunc]] = [
    (
        "PATTERN-001",
        "extract_file_patterns",
        "file_patterns_count",
        extract_file_access_patterns,
        convert_file_patterns,
    ),
    (
        "PATTERN-002",
        "extract_error_patterns",
        "error_patterns_count",
        extract_error_patterns,
        convert_error_patterns,
    ),
    (
        "PATTERN-003",
        "extract_architecture_patterns",
        "architecture_patterns_count",
        extract_architecture_patterns,
        convert_architecture_patterns,
    ),
    (
        "PATTERN-004",
        "extract_tool_patterns",
        "tool_patterns_count",
        extract_tool_patterns,
        convert_tool_patterns,
    ),
    (
        "PATTERN-005",
        "extract_tool_failure_patterns",
        "tool_failure_patterns_count",
        extract_tool_failure_patterns,
        convert_error_patterns,
    ),
]


def extract_all_patterns(
    input_data: ModelPatternExtractionInput,
) -> ModelPatternExtractionOutput:
    """Main handler that performs all pattern extraction.

    This handler:
    - Validates input
    - Resolves reference time
    - Runs all extractors based on config flags
    - Converts results to insights
    - Deduplicates and merges with existing
    - Builds metrics and metadata
    - Handles errors

    Args:
        input_data: Input containing session snapshots, config, and existing insights.

    Returns:
        Complete ModelPatternExtractionOutput with extracted insights,
        metrics, and metadata.

    Raises:
        PatternExtractionComputeError: On unrecoverable extraction failures.
    """
    start_time = time.perf_counter()
    config = input_data.config

    try:
        # Validate input
        if not input_data.session_snapshots:
            raise PatternExtractionValidationError(
                "At least one session snapshot required"
            )

        # Determine reference time for determinism
        reference_time = _resolve_reference_time(config, input_data.session_snapshots)

        # Run extractors declaratively
        all_patterns, metrics_counts = _run_extractors(
            input_data.session_snapshots,
            config,
            reference_time,
        )

        # Deduplicate and merge with existing insights
        new_insights, updated_insights = _deduplicate_and_merge(
            all_patterns,
            input_data.existing_insights,
            config.max_insights_per_type,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        return ModelPatternExtractionOutput(
            success=True,
            new_insights=tuple(new_insights),
            updated_insights=tuple(updated_insights),
            metrics=ModelExtractionMetrics(
                sessions_analyzed=len(input_data.session_snapshots),
                total_patterns_found=len(all_patterns),
                new_insights_count=len(new_insights),
                updated_insights_count=len(updated_insights),
                **metrics_counts,
            ),
            metadata=ModelPatternExtractionMetadata(
                status="completed",
                processing_time_ms=processing_time,
                reference_time=reference_time,
            ),
        )

    except PatternExtractionValidationError as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        return ModelPatternExtractionOutput(
            success=False,
            new_insights=(),
            updated_insights=(),
            metrics=ModelExtractionMetrics(
                sessions_analyzed=0,
                total_patterns_found=0,
                new_insights_count=0,
                updated_insights_count=0,
            ),
            metadata=ModelPatternExtractionMetadata(
                status="validation_error",
                message=str(e),
                processing_time_ms=processing_time,
            ),
        )

    except Exception as e:
        logger.exception("Pattern extraction failed: %s", e)
        raise PatternExtractionComputeError(f"Extraction failed: {e}") from e


def _resolve_reference_time(
    config: ModelExtractionConfig,
    sessions: Sequence[ModelSessionSnapshot],
) -> datetime:
    """Resolve reference time for deterministic output.

    Args:
        config: Extraction configuration.
        sessions: Session snapshots to analyze.

    Returns:
        Reference time from config or derived from sessions.
    """
    if config.reference_time is not None:
        return config.reference_time
    # Use max ended_at from sessions
    ended_times = [s.ended_at for s in sessions if s.ended_at]
    return max(ended_times) if ended_times else datetime.now(UTC)


def _run_extractors(
    sessions: Sequence[ModelSessionSnapshot],
    config: ModelExtractionConfig,
    reference_time: datetime,
) -> tuple[list[ModelCodebaseInsight], dict[str, int]]:
    """Run all enabled extractors declaratively.

    Iterates through extractor registry, checking config flags via getattr().
    No custom if/else branching per extractor type.

    Args:
        sessions: Session snapshots to analyze.
        config: Extraction configuration with enable flags.
        reference_time: Reference time for insight timestamps.

    Returns:
        Tuple of (all_patterns, metrics_counts).
    """
    all_patterns: list[ModelCodebaseInsight] = []
    metrics_counts: dict[str, int] = {}

    for extractor_id, config_flag, metrics_field, extract_func, convert_func in (
        _EXTRACTORS
    ):
        # Check if extractor is enabled via config flag
        if not getattr(config, config_flag, False):
            metrics_counts[metrics_field] = 0
            continue

        # Extract and convert - all extractors have uniform signature
        results = extract_func(
            sessions,
            config.min_pattern_occurrences,
            config.min_confidence,
            config.min_distinct_sessions,
            config.max_results_per_pattern_type,
        )
        insights = convert_func(results, reference_time)

        all_patterns.extend(insights)
        metrics_counts[metrics_field] = len(insights)

    return all_patterns, metrics_counts


def _deduplicate_and_merge(
    new_patterns: list[ModelCodebaseInsight],
    existing: tuple[ModelCodebaseInsight, ...],
    max_per_type: int,
) -> tuple[list[ModelCodebaseInsight], list[ModelCodebaseInsight]]:
    """Deduplicate patterns and merge with existing.

    Pure function for deduplication - no instance state required.

    Args:
        new_patterns: Newly extracted patterns.
        existing: Existing insights to merge with.
        max_per_type: Maximum insights to keep per type.

    Returns:
        Tuple of (new_insights, updated_insights).
    """
    # Build lookup of existing by identity key
    existing_by_key: dict[str, ModelCodebaseInsight] = {
        insight_identity_key(i): i for i in existing
    }

    new_insights: list[ModelCodebaseInsight] = []
    updated_insights: list[ModelCodebaseInsight] = []
    seen_keys: set[str] = set()

    for pattern in new_patterns:
        key = insight_identity_key(pattern)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        if key in existing_by_key:
            # Merge with existing
            merged = merge_insights(pattern, existing_by_key[key])
            updated_insights.append(merged)
        else:
            new_insights.append(pattern)

    # Limit per type
    type_counts: dict[str, int] = {}
    limited_new: list[ModelCodebaseInsight] = []

    for insight in sorted(new_insights, key=lambda x: -x.confidence):
        type_key = insight.insight_type.value
        count = type_counts.get(type_key, 0)
        if count < max_per_type:
            limited_new.append(insight)
            type_counts[type_key] = count + 1

    return limited_new, updated_insights


__all__ = ["extract_all_patterns"]
