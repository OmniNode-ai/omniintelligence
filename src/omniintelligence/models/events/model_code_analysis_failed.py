"""Code analysis failed event payload model.

This module defines the Pydantic model for CODE_ANALYSIS_FAILED events
published to the code analysis failed Kafka topic when analysis fails.

ONEX Compliance:
- Model-based naming: Model{Domain}{Purpose}
- Strong typing with Pydantic Field validation
- UUID pattern validation for correlation_id
"""

from pydantic import BaseModel, Field

from omniintelligence.enums.enum_analysis_operation_type import (
    EnumAnalysisOperationType,
)

# UUID pattern for correlation_id validation
UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class ModelCodeAnalysisFailedPayload(BaseModel):
    """Event payload for failed code analysis.

    Published to the CODE_ANALYSIS_FAILED topic when analysis fails,
    containing error details and recovery suggestions.

    Attributes:
        correlation_id: UUID for distributed tracing
        error_code: Error code (e.g., TIMEOUT, INVALID_INPUT)
        error_message: Human-readable error message
        operation_type: Type of analysis that failed
        source_path: Path to the source that was analyzed
        retry_allowed: Whether retry is recommended
        processing_time_ms: Processing time before failure
        error_details: Detailed error information
        suggested_action: Suggested action to resolve the error
    """

    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing (UUID format)",
        pattern=UUID_PATTERN,
    )
    error_code: str = Field(default="", min_length=0)
    error_message: str = Field(default="", min_length=0)
    operation_type: EnumAnalysisOperationType | None = Field(
        default=None, description="Type of analysis that failed"
    )
    source_path: str = Field(
        default="", description="Path to the source that was analyzed"
    )
    retry_allowed: bool = Field(default=True, description="Whether retry is allowed")
    processing_time_ms: float = Field(
        default=0.0, ge=0.0, description="Processing time in ms"
    )
    error_details: str | None = Field(
        default=None, description="Detailed error information"
    )
    suggested_action: str | None = Field(
        default=None, description="Suggested action to resolve"
    )
