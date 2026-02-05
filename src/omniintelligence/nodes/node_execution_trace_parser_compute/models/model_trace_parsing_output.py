"""Output model for Execution Trace Parser Compute."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator


class ModelParsedEvent(BaseModel):
    """Typed model for parsed trace events.

    Provides strong typing for trace events extracted during parsing.
    """

    event_id: str | None = Field(default=None, description="Unique event identifier")
    event_type: str | None = Field(default=None, description="Type of event")
    timestamp: str | None = Field(default=None, description="Event timestamp")
    span_id: str | None = Field(default=None, description="Associated span ID")
    trace_id: str | None = Field(default=None, description="Associated trace ID")
    operation_name: str | None = Field(default=None, description="Operation name")
    service_name: str | None = Field(default=None, description="Service name")
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Event attributes"
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelErrorEvent(BaseModel):
    """Typed model for error events extracted from traces.

    Provides strong typing for error information found during trace parsing.
    """

    error_id: str | None = Field(default=None, description="Unique error identifier")
    error_type: str | None = Field(default=None, description="Type of error")
    error_message: str | None = Field(default=None, description="Error message")
    timestamp: str | None = Field(default=None, description="Error timestamp")
    span_id: str | None = Field(default=None, description="Associated span ID")
    stack_trace: str | None = Field(
        default=None, description="Stack trace if available"
    )
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Error attributes"
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelTimingData(BaseModel):
    """Typed model for timing information.

    Provides strong typing for timing metrics extracted from traces.
    """

    total_duration_ms: float | None = Field(
        default=None, description="Total duration in milliseconds"
    )
    start_time: str | None = Field(default=None, description="Start timestamp")
    end_time: str | None = Field(default=None, description="End timestamp")
    span_count: int | None = Field(default=None, ge=0, description="Number of spans")
    critical_path_ms: float | None = Field(
        default=None, description="Critical path duration in ms"
    )
    latency_breakdown: dict[str, float] = Field(
        default_factory=dict, description="Latency breakdown by operation"
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelTraceMetadata(BaseModel):
    """Typed model for trace parsing metadata.

    Provides strong typing for metadata about the parsing process.
    """

    parser_version: str | None = Field(default=None, description="Parser version used")
    parse_time_ms: float | None = Field(
        default=None, description="Time taken to parse in ms"
    )
    source_format: str | None = Field(
        default=None, description="Source format of the trace"
    )
    event_count: int | None = Field(
        default=None, ge=0, description="Number of events parsed"
    )
    error_count: int | None = Field(
        default=None, ge=0, description="Number of errors extracted"
    )
    warnings: list[str] = Field(default_factory=list, description="Parsing warnings")

    model_config = {"frozen": True, "extra": "forbid"}


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


__all__ = [
    "ModelErrorEvent",
    "ModelParsedEvent",
    "ModelTimingData",
    "ModelTraceMetadata",
    "ModelTraceParsingOutput",
]
