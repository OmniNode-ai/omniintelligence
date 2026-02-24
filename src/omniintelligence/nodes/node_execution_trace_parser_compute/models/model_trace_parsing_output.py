# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for Execution Trace Parser Compute."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator

from omniintelligence.nodes.node_execution_trace_parser_compute.models.model_error_event import (
    ModelErrorEvent,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models.model_parsed_event import (
    ModelParsedEvent,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models.model_timing_data import (
    ModelTimingData,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models.model_trace_metadata import (
    ModelTraceMetadata,
)


class ModelTraceParsingOutput(BaseModel):
    """Output model for trace parsing operations.

    This model represents the result of parsing execution traces.
    """

    success: bool = Field(
        ...,
        description="Whether trace parsing succeeded",
    )
    parsed_events: list[ModelParsedEvent] = Field(
        default_factory=list,
        description="List of parsed trace events",
    )
    error_events: list[ModelErrorEvent] = Field(
        default_factory=list,
        description="List of error events extracted from trace",
    )
    timing_data: ModelTimingData = Field(
        default_factory=ModelTimingData,
        description="Timing information extracted from trace",
    )
    metadata: ModelTraceMetadata | None = Field(
        default=None,
        description="Additional metadata about the parsing",
    )

    @model_validator(mode="after")
    def validate_metadata_counts_match_lists(self) -> Self:
        """Validate that metadata counts match actual list lengths when provided.

        When metadata contains event_count or error_count, these should match
        the lengths of parsed_events and error_events respectively. This ensures
        consistency between the reported counts and actual data.

        Returns:
            Self with validated metadata counts.

        Raises:
            ValueError: If metadata counts don't match actual list lengths.
        """
        if self.metadata is None:
            return self

        error_parts = []

        # Validate event_count if present in metadata
        if self.metadata.event_count is not None:
            actual_event_count = len(self.parsed_events)
            if self.metadata.event_count != actual_event_count:
                error_parts.append(
                    f"metadata.event_count ({self.metadata.event_count}) "
                    f"!= len(parsed_events) ({actual_event_count})"
                )

        # Validate error_count if present in metadata
        if self.metadata.error_count is not None:
            actual_error_count = len(self.error_events)
            if self.metadata.error_count != actual_error_count:
                error_parts.append(
                    f"metadata.error_count ({self.metadata.error_count}) "
                    f"!= len(error_events) ({actual_error_count})"
                )

        if error_parts:
            raise ValueError(
                f"Metadata counts must match list lengths: {'; '.join(error_parts)}"
            )

        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelTraceParsingOutput"]
