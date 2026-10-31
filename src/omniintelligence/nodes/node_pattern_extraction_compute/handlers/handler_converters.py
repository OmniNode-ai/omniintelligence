# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Converter handlers for pattern extraction results.

Pure converter functions that transform raw pattern
extraction results into ModelCodebaseInsight objects. Converters are wired
declaratively in the node's extractor registry.

Each converter accepts typed results and a reference time without side effects.
"""

from __future__ import annotations

from datetime import datetime

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.protocols import (
    ArchitecturePatternResult,
    ErrorPatternResult,
    FileAccessPatternResult,
    ModelPatternConversionRequest,
    ModelPatternConversionResponse,
    ToolPatternResult,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    EnumInsightType,
    ModelCodebaseInsight,
)


def convert_file_patterns(
    results: list[FileAccessPatternResult],
    reference_time: datetime,
) -> list[ModelCodebaseInsight]:
    """Convert file pattern results to insights.

    Maps pattern_type to insight type:
        - co_access -> FILE_ACCESS_PATTERN
        - entry_point -> ENTRY_POINT_PATTERN
        - modification_cluster -> MODIFICATION_CLUSTER

    Args:
        results: File access pattern results from extractor.
        reference_time: Reference time for insight timestamps.

    Returns:
        List of ModelCodebaseInsight objects.
    """
    insights = []
    pattern_type_map = {
        "co_access": EnumInsightType.FILE_ACCESS_PATTERN,
        "entry_point": EnumInsightType.ENTRY_POINT_PATTERN,
        "modification_cluster": EnumInsightType.MODIFICATION_CLUSTER,
    }

    for r in results:
        insight_type = pattern_type_map.get(
            r["pattern_type"], EnumInsightType.FILE_ACCESS_PATTERN
        )

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


def convert_error_patterns(
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


def convert_architecture_patterns(
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


def convert_tool_patterns(
    results: list[ToolPatternResult],
    reference_time: datetime,
) -> list[ModelCodebaseInsight]:
    """Convert tool pattern results to insights.

    Builds description from tool sequence, success rate, and context.

    """
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


class HandlerConverters:
    """Convert extracted patterns into grouped insights."""

    def handle(
        self, request: ModelPatternConversionRequest
    ) -> ModelPatternConversionResponse:
        return ModelPatternConversionResponse(
            file_insights=tuple(
                convert_file_patterns(request.file_patterns, request.reference_time)
            ),
            error_insights=tuple(
                convert_error_patterns(request.error_patterns, request.reference_time)
            ),
            architecture_insights=tuple(
                convert_architecture_patterns(
                    request.architecture_patterns, request.reference_time
                )
            ),
            tool_insights=tuple(
                convert_tool_patterns(request.tool_patterns, request.reference_time)
            ),
        )


__all__ = [
    "HandlerConverters",
    "ModelPatternConversionRequest",
    "ModelPatternConversionResponse",
    "convert_architecture_patterns",
    "convert_error_patterns",
    "convert_file_patterns",
    "convert_tool_patterns",
]
