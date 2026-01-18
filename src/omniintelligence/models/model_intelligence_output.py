"""Output model for Intelligence operations.

This model is used by the intelligence_adapter effect node
for publishing code analysis results to Kafka events.

Migration Note:
    This simplified output model differs intentionally from the legacy
    omniarchon ModelIntelligenceOutput. Key changes:

    - correlation_id: Changed from required UUID to Optional[str]
    - onex_compliant: Boolean flag (was onex_compliance float score)
    - patterns_detected: List of pattern names (was list[ModelPatternDetection])
    - analysis_results: Renamed from result_data for clarity

    Removed fields (moved to event envelope or observability layer):
    - processing_time_ms, complexity_score, issues, metrics
    - error_code, retry_allowed, timestamp

    See MIGRATION.md for complete migration guidance.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from omniintelligence.enums import EnumIntelligenceOperationType


class ModelIntelligenceOutput(BaseModel):
    """Output model for intelligence operations.

    This model represents the output of code analysis and intelligence operations
    that are published as Kafka events.

    Migration from Legacy:
        This canonical model is intentionally simplified from the legacy
        omniarchon ModelIntelligenceOutput for event-driven architecture.

        Key field changes:

        correlation_id (UUID -> Optional[str]):
            Legacy: correlation_id: UUID (required)
            Canonical: correlation_id: Optional[str] = None
            Rationale: String is more portable; optional for system events

        onex_compliance (float -> bool):
            Legacy: onex_compliance: Optional[float] (0.0-1.0 score)
            Canonical: onex_compliant: Optional[bool]
            Rationale: Binary compliance is sufficient for most consumers;
                       score available in analysis_results if needed

        patterns (list[ModelPatternDetection] -> list[str]):
            Legacy: patterns: list[ModelPatternDetection] (rich objects)
            Canonical: patterns_detected: list[str] (pattern names only)
            Rationale: Reduces payload size; details in analysis_results

        Removed fields:
            - processing_time_ms: Use event envelope or metadata
            - complexity_score: Use analysis_results["complexity_score"]
            - issues: Merged into recommendations
            - metrics (ModelIntelligenceMetrics): Observability layer
            - error_code: Use metadata["error_code"]
            - retry_allowed: DLQ routing configuration
            - timestamp: Event envelope metadata

    Example (legacy to canonical):
        >>> # Legacy
        >>> from uuid import UUID
        >>> legacy = LegacyModelIntelligenceOutput(
        ...     success=True,
        ...     operation_type="assess_code_quality",
        ...     correlation_id=UUID("550e8400-..."),
        ...     processing_time_ms=1234,
        ...     quality_score=0.87,
        ...     onex_compliance=0.92,
        ...     patterns=[ModelPatternDetection(pattern_name="MISSING_DOCSTRING", ...)]
        ... )

        >>> # Canonical equivalent
        >>> canonical = ModelIntelligenceOutput(
        ...     success=True,
        ...     operation_type="assess_code_quality",
        ...     quality_score=0.87,
        ...     onex_compliant=True,  # threshold-based
        ...     patterns_detected=["MISSING_DOCSTRING"],
        ...     analysis_results={"onex_compliance_score": 0.92},
        ...     correlation_id="550e8400-...",
        ...     metadata={"processing_time_ms": 1234}
        ... )
    """

    success: bool = Field(
        ...,
        description="Whether the intelligence operation succeeded",
    )
    operation_type: EnumIntelligenceOperationType = Field(
        ...,
        description="Type of intelligence operation performed",
    )
    quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall quality score (0.0 to 1.0) if applicable",
    )
    analysis_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Results of the analysis",
    )
    patterns_detected: list[str] = Field(
        default_factory=list,
        description="List of detected patterns",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="List of recommendations",
    )
    onex_compliant: bool | None = Field(
        default=None,
        description="Whether the analyzed code is ONEX compliant",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if the operation failed",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the result",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIntelligenceOutput"]
