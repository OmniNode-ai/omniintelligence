"""Pattern Extraction Compute - Pure compute node for extracting patterns from sessions.

This node analyzes Claude Code session snapshots to extract patterns across
four dimensions: file access, errors, architecture, and tool usage. It produces
ModelCodebaseInsight objects that can be used to build intelligence about
the codebase.

ONEX Compliance:
    - Pure computation: No external I/O, HTTP calls, or side effects
    - Deterministic: Same inputs produce same outputs (with fixed reference_time)
    - Delegating: Business logic in handler functions following pure shell pattern
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, UTC
from typing import TYPE_CHECKING

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.pattern_extraction_compute.handlers import (
    PatternExtractionComputeError,
    PatternExtractionValidationError,
    extract_architecture_patterns,
    extract_error_patterns,
    extract_file_access_patterns,
    extract_tool_patterns,
    insight_identity_key,
    merge_insights,
)
from omniintelligence.nodes.pattern_extraction_compute.models import (
    EnumInsightType,
    ModelCodebaseInsight,
    ModelExtractionMetrics,
    ModelPatternExtractionInput,
    ModelPatternExtractionMetadata,
    ModelPatternExtractionOutput,
)

if TYPE_CHECKING:
    from omniintelligence.nodes.pattern_extraction_compute.handlers.protocols import (
        ArchitecturePatternResult,
        ErrorPatternResult,
        FileAccessPatternResult,
        ToolPatternResult,
    )

logger = logging.getLogger(__name__)


class NodePatternExtractionCompute(
    NodeCompute[ModelPatternExtractionInput, ModelPatternExtractionOutput]
):
    """Pure compute node for extracting patterns from Claude Code sessions.

    This node analyzes session snapshots to extract:
        - File access patterns: Co-access, entry points, modification clusters
        - Error patterns: Error-prone files, failure sequences
        - Architecture patterns: Module boundaries, layer patterns
        - Tool usage patterns: Sequences, preferences, success rates

    The node follows the ONEX pure shell pattern, delegating computation
    to side-effect-free handler functions.

    Example:
        >>> node = NodePatternExtractionCompute()
        >>> input_data = ModelPatternExtractionInput(
        ...     session_snapshots=(session1, session2),
        ...     config=ModelExtractionConfig(),
        ... )
        >>> output = await node.compute(input_data)
        >>> print(f"Found {len(output.new_insights)} new insights")
    """

    async def compute(
        self, input_data: ModelPatternExtractionInput
    ) -> ModelPatternExtractionOutput:
        """Extract patterns from session snapshots.

        Follows ONEX pure shell pattern - delegates to handler functions
        for computation.

        Args:
            input_data: Input containing session snapshots and config.

        Returns:
            Output with extracted insights, metrics, and metadata.
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
            reference_time = config.reference_time
            if reference_time is None:
                # Use max ended_at from sessions
                ended_times = [
                    s.ended_at for s in input_data.session_snapshots if s.ended_at
                ]
                reference_time = (
                    max(ended_times) if ended_times else datetime.now(UTC)
                )

            all_patterns: list[ModelCodebaseInsight] = []
            metrics_data = {
                "file_patterns_count": 0,
                "error_patterns_count": 0,
                "architecture_patterns_count": 0,
                "tool_patterns_count": 0,
            }

            # Extract file patterns
            if config.extract_file_patterns:
                file_results = extract_file_access_patterns(
                    sessions=input_data.session_snapshots,
                    min_occurrences=config.min_pattern_occurrences,
                    min_confidence=config.min_confidence,
                )
                file_insights = self._convert_file_patterns(file_results, reference_time)
                all_patterns.extend(file_insights)
                metrics_data["file_patterns_count"] = len(file_insights)

            # Extract error patterns
            if config.extract_error_patterns:
                error_results = extract_error_patterns(
                    sessions=input_data.session_snapshots,
                    min_occurrences=config.min_pattern_occurrences,
                    min_confidence=config.min_confidence,
                )
                error_insights = self._convert_error_patterns(
                    error_results, reference_time
                )
                all_patterns.extend(error_insights)
                metrics_data["error_patterns_count"] = len(error_insights)

            # Extract architecture patterns
            if config.extract_architecture_patterns:
                arch_results = extract_architecture_patterns(
                    sessions=input_data.session_snapshots,
                    min_occurrences=config.min_pattern_occurrences,
                    min_confidence=config.min_confidence,
                )
                arch_insights = self._convert_architecture_patterns(
                    arch_results, reference_time
                )
                all_patterns.extend(arch_insights)
                metrics_data["architecture_patterns_count"] = len(arch_insights)

            # Extract tool patterns
            if config.extract_tool_patterns:
                tool_results = extract_tool_patterns(
                    sessions=input_data.session_snapshots,
                    min_occurrences=config.min_pattern_occurrences,
                    min_confidence=config.min_confidence,
                )
                tool_insights = self._convert_tool_patterns(tool_results, reference_time)
                all_patterns.extend(tool_insights)
                metrics_data["tool_patterns_count"] = len(tool_insights)

            # Deduplicate and merge with existing insights
            new_insights, updated_insights = self._deduplicate_and_merge(
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
                    file_patterns_count=metrics_data["file_patterns_count"],
                    error_patterns_count=metrics_data["error_patterns_count"],
                    architecture_patterns_count=metrics_data["architecture_patterns_count"],
                    tool_patterns_count=metrics_data["tool_patterns_count"],
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

    def _convert_file_patterns(
        self,
        results: list[FileAccessPatternResult],
        reference_time: datetime,
    ) -> list[ModelCodebaseInsight]:
        """Convert file pattern results to insights."""
        insights = []
        for r in results:
            insight_type = {
                "co_access": EnumInsightType.FILE_ACCESS_PATTERN,
                "entry_point": EnumInsightType.ENTRY_POINT_PATTERN,
                "modification_cluster": EnumInsightType.MODIFICATION_CLUSTER,
            }.get(r["pattern_type"], EnumInsightType.FILE_ACCESS_PATTERN)

            # Build description
            files_str = ", ".join(r["files"][:3])
            if len(r["files"]) > 3:
                files_str += f" (+{len(r['files']) - 3} more)"
            description = f"{r['pattern_type']}: {files_str}"

            insights.append(
                ModelCodebaseInsight(
                    insight_id=r["pattern_id"],
                    insight_type=insight_type,
                    description=description,
                    confidence=r["confidence"],
                    evidence_files=r["files"],
                    evidence_session_ids=r["evidence_session_ids"],
                    occurrence_count=r["occurrences"],
                    first_observed=reference_time,
                    last_observed=reference_time,
                )
            )
        return insights

    def _convert_error_patterns(
        self,
        results: list[ErrorPatternResult],
        reference_time: datetime,
    ) -> list[ModelCodebaseInsight]:
        """Convert error pattern results to insights."""
        return [
            ModelCodebaseInsight(
                insight_id=r["pattern_id"],
                insight_type=EnumInsightType.ERROR_PATTERN,
                description=r["error_summary"],
                confidence=r["confidence"],
                evidence_files=r["affected_files"],
                evidence_session_ids=r["evidence_session_ids"],
                occurrence_count=r["occurrences"],
                first_observed=reference_time,
                last_observed=reference_time,
            )
            for r in results
        ]

    def _convert_architecture_patterns(
        self,
        results: list[ArchitecturePatternResult],
        reference_time: datetime,
    ) -> list[ModelCodebaseInsight]:
        """Convert architecture pattern results to insights."""
        return [
            ModelCodebaseInsight(
                insight_id=r["pattern_id"],
                insight_type=EnumInsightType.ARCHITECTURE_PATTERN,
                description=f"{r['pattern_type']}: {r['directory_prefix']}",
                confidence=r["confidence"],
                evidence_files=r["member_files"],
                evidence_session_ids=(),
                occurrence_count=r["occurrences"],
                working_directory=r["directory_prefix"],
                first_observed=reference_time,
                last_observed=reference_time,
            )
            for r in results
        ]

    def _convert_tool_patterns(
        self,
        results: list[ToolPatternResult],
        reference_time: datetime,
    ) -> list[ModelCodebaseInsight]:
        """Convert tool pattern results to insights."""
        insights = []
        for r in results:
            desc = f"{r['pattern_type']}: {' -> '.join(r['tools'])}"
            if r["success_rate"] is not None:
                desc += f" ({r['success_rate']:.0%} success)"
            if r["context"]:
                desc += f" in {r['context']}"

            insights.append(
                ModelCodebaseInsight(
                    insight_id=r["pattern_id"],
                    insight_type=EnumInsightType.TOOL_USAGE_PATTERN,
                    description=desc,
                    confidence=r["confidence"],
                    evidence_files=(),
                    evidence_session_ids=(),
                    occurrence_count=r["occurrences"],
                    first_observed=reference_time,
                    last_observed=reference_time,
                )
            )
        return insights

    def _deduplicate_and_merge(
        self,
        new_patterns: list[ModelCodebaseInsight],
        existing: tuple[ModelCodebaseInsight, ...],
        max_per_type: int,
    ) -> tuple[list[ModelCodebaseInsight], list[ModelCodebaseInsight]]:
        """Deduplicate patterns and merge with existing.

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
        type_counts: dict[EnumInsightType, int] = {}
        limited_new: list[ModelCodebaseInsight] = []

        for insight in sorted(new_insights, key=lambda x: -x.confidence):
            count = type_counts.get(insight.insight_type, 0)
            if count < max_per_type:
                limited_new.append(insight)
                type_counts[insight.insight_type] = count + 1

        return limited_new, updated_insights


__all__ = ["NodePatternExtractionCompute"]
