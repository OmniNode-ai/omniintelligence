# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Code analysis request event payload model.

This module defines the Pydantic model for CODE_ANALYSIS_REQUESTED events
published to the code analysis request Kafka topic.

ONEX Compliance:
- Model-based naming: Model{Domain}{Purpose}
- Strong typing with Pydantic Field validation
- UUID pattern validation for correlation_id

Contract notes:
- operation_type is required (non-optional). Every CODE_ANALYSIS_REQUESTED
  event MUST specify an operation type. Producers must not publish null
  operation_type values; consumers may assert this field is non-null and
  treat absent values as malformed requests.
"""

from pydantic import BaseModel, Field

from omniintelligence.enums.enum_analysis_operation_type import (
    EnumAnalysisOperationType,
)

# UUID pattern for correlation_id validation
UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class ModelCodeAnalysisRequestPayload(BaseModel):
    """Event payload for code analysis requests.

    This payload is consumed from the CODE_ANALYSIS_REQUESTED topic
    and contains the source code and analysis configuration.

    Attributes:
        correlation_id: UUID for distributed tracing
        source_path: Path to the source file (for context)
        content: Source code content to analyze
        operation_type: Type of analysis to perform (required, must not be null)
        language: Programming language (default: python)
        options: Additional operation-specific options
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing (UUID format)",
        pattern=UUID_PATTERN,
    )
    source_path: str = Field(default="", min_length=0)
    content: str = Field(default="", min_length=0)
    operation_type: EnumAnalysisOperationType = Field(
        description="Type of analysis operation to perform. Required — producers must always specify this field.",
    )
    language: str = Field(
        default="python", description="Programming language of the content"
    )
    options: dict[str, object] = Field(
        default_factory=dict, description="Operation options"
    )
    project_id: str | None = Field(default=None, description="Project identifier")
    user_id: str | None = Field(default=None, description="User identifier")
