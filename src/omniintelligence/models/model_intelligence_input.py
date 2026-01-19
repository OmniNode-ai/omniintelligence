"""Input model for Intelligence operations.

This model is used by the intelligence_adapter effect node
for processing code analysis requests from Kafka events.

Migration Note:
    This unified input model replaces multiple operation-specific request
    models from the legacy omniarchon system:
    - ModelQualityAssessmentRequest -> EnumIntelligenceOperationType.ASSESS_CODE_QUALITY
    - ModelPerformanceAnalysisRequest -> EnumIntelligenceOperationType.ESTABLISH_PERFORMANCE_BASELINE
    - ModelPatternDetectionRequest -> EnumIntelligenceOperationType.PATTERN_MATCH

    Operation-specific parameters that were individual fields in legacy models
    should now be passed in the `options` TypedDict.

    See MIGRATION.md for complete migration guidance.
"""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field

from omniintelligence.enums import EnumIntelligenceOperationType


class PerformanceContextDict(TypedDict, total=False):
    """Typed structure for performance analysis context.

    Used within IntelligenceOptionsDict for performance-related operations.
    """

    execution_type: str  # e.g., "async", "sync"
    io_type: str  # e.g., "database", "network", "file"
    expected_frequency: str  # e.g., "high", "medium", "low"
    current_latency_p95: int  # Current P95 latency in ms
    current_latency_p99: int  # Current P99 latency in ms
    target_latency_ms: int  # Target latency in ms


class IntelligenceOptionsDict(TypedDict, total=False):
    """Typed structure for operation-specific options.

    Contains known option fields for various intelligence operations.
    With total=False, all fields are optional, allowing operation-specific
    subsets to be provided.

    Quality Assessment Options:
        include_recommendations: bool - Include improvement recommendations
        min_quality_threshold: float - Minimum quality score threshold (0.0-1.0)

    Performance Analysis Options:
        operation_name: str - Name of the operation being analyzed
        target_percentile: int - Target percentile (e.g., 95, 99)
        include_opportunities: bool - Include optimization opportunities
        context: PerformanceContextDict - Performance context information

    Pattern Detection Options:
        pattern_categories: list[str] - Filter patterns by categories
        min_confidence: float - Minimum confidence threshold (0.0-1.0)
        max_patterns: int - Maximum patterns to return

    Vector Operations Options:
        top_k: int - Number of top results to return
        similarity_threshold: float - Minimum similarity score (0.0-1.0)
        include_metadata: bool - Include metadata in results

    Document Freshness Options:
        max_age_days: int - Maximum document age in days
        include_stale: bool - Include stale documents in results
    """

    # Quality Assessment options
    include_recommendations: bool
    min_quality_threshold: float

    # Performance Analysis options
    operation_name: str
    target_percentile: int
    include_opportunities: bool
    context: PerformanceContextDict

    # Pattern Detection options
    pattern_categories: list[str]
    min_confidence: float
    max_patterns: int

    # Vector Operations options
    top_k: int
    similarity_threshold: float
    include_metadata: bool

    # Document Freshness options
    max_age_days: int
    include_stale: bool

    # Autonomous Learning options
    safety_threshold: float
    prediction_confidence: float


class IntelligenceMetadataDict(TypedDict, total=False):
    """Typed structure for request metadata.

    Contains common metadata fields for intelligence operations.
    With total=False, all fields are optional.
    """

    # Request tracking
    request_id: str
    session_id: str
    user_id: str
    agent_id: str

    # Source context
    repository: str
    branch: str
    commit_hash: str

    # Timing information
    timestamp_utc: str
    request_deadline_ms: int

    # Processing hints
    priority: str  # e.g., "high", "normal", "low"
    retry_count: int
    max_retries: int

    # Feature flags
    enable_caching: bool
    enable_tracing: bool


class ModelIntelligenceInput(BaseModel):
    """Input model for intelligence operations.

    This model represents the input for code analysis and intelligence operations
    consumed from Kafka events.

    Migration from Legacy:
        This unified model replaces operation-specific request models:

        Legacy ModelQualityAssessmentRequest:
            >>> # Legacy
            >>> ModelQualityAssessmentRequest(
            ...     content="def foo(): pass",
            ...     source_path="src/main.py",
            ...     language="python",
            ...     include_recommendations=True,
            ...     min_quality_threshold=0.7
            ... )
            >>> # Canonical equivalent (using enum)
            >>> from omniintelligence.enums import EnumIntelligenceOperationType
            >>> ModelIntelligenceInput(
            ...     operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
            ...     content="def foo(): pass",
            ...     source_path="src/main.py",
            ...     language="python",
            ...     options={"include_recommendations": True, "min_quality_threshold": 0.7}
            ... )

        Legacy ModelPatternDetectionRequest:
            >>> # Legacy
            >>> ModelPatternDetectionRequest(
            ...     content="class Foo: pass",
            ...     source_path="src/foo.py",
            ...     pattern_categories=["best_practices"],
            ...     min_confidence=0.7
            ... )
            >>> # Canonical equivalent (using enum)
            >>> from omniintelligence.enums import EnumIntelligenceOperationType
            >>> ModelIntelligenceInput(
            ...     operation_type=EnumIntelligenceOperationType.PATTERN_MATCH,
            ...     content="class Foo: pass",
            ...     source_path="src/foo.py",
            ...     options={"pattern_categories": ["best_practices"], "min_confidence": 0.7}
            ... )
    """

    operation_type: EnumIntelligenceOperationType = Field(
        ...,
        description=(
            "Type of intelligence operation. Valid operation types are defined in "
            "EnumIntelligenceOperationType and include:\n"
            "- Quality Assessment: ASSESS_CODE_QUALITY, ANALYZE_DOCUMENT_QUALITY, "
            "GET_QUALITY_PATTERNS, CHECK_ARCHITECTURAL_COMPLIANCE\n"
            "- Performance: ESTABLISH_PERFORMANCE_BASELINE, IDENTIFY_OPTIMIZATION_OPPORTUNITIES, "
            "APPLY_PERFORMANCE_OPTIMIZATION, GET_OPTIMIZATION_REPORT, MONITOR_PERFORMANCE_TRENDS\n"
            "- Document Freshness: ANALYZE_DOCUMENT_FRESHNESS, GET_STALE_DOCUMENTS, "
            "REFRESH_DOCUMENTS, GET_FRESHNESS_STATS, GET_DOCUMENT_FRESHNESS, CLEANUP_FRESHNESS_DATA\n"
            "- Pattern Learning: PATTERN_MATCH, HYBRID_SCORE, SEMANTIC_ANALYZE, GET_PATTERN_METRICS, "
            "GET_CACHE_STATS, CLEAR_PATTERN_CACHE, GET_PATTERN_HEALTH\n"
            "- Vector Operations: ADVANCED_VECTOR_SEARCH, QUALITY_WEIGHTED_SEARCH, "
            "BATCH_INDEX_DOCUMENTS, GET_VECTOR_STATS, OPTIMIZE_VECTOR_INDEX\n"
            "- Pattern Traceability: TRACK_PATTERN_LINEAGE, GET_PATTERN_LINEAGE, "
            "GET_EXECUTION_LOGS, GET_EXECUTION_SUMMARY\n"
            "- Autonomous Learning: INGEST_PATTERNS, RECORD_SUCCESS_PATTERN, PREDICT_AGENT, "
            "PREDICT_EXECUTION_TIME, CALCULATE_SAFETY_SCORE, GET_AUTONOMOUS_STATS, GET_AUTONOMOUS_HEALTH"
        ),
    )
    content: str = Field(
        ...,
        min_length=1,
        description=(
            "Content to analyze (source code, document, etc.). "
            "When both content and source_path are provided, content takes precedence "
            "and is used for analysis. The source_path is then used only for metadata "
            "(e.g., language detection, file context in reports)."
        ),
    )
    source_path: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Path to the source file being analyzed. Used for metadata and context "
            "when content is provided inline. Note: This field does NOT load content "
            "from the path - content must be provided explicitly in the content field."
        ),
    )
    language: str = Field(
        default="python",
        description="Programming language of the content",
    )
    project_name: str | None = Field(
        default=None,
        description="Name of the project for context",
    )
    options: IntelligenceOptionsDict = Field(
        default_factory=lambda: IntelligenceOptionsDict(),
        description=(
            "Operation-specific options using typed IntelligenceOptionsDict. "
            "See IntelligenceOptionsDict docstring for available fields by operation type."
        ),
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )
    metadata: IntelligenceMetadataDict = Field(
        default_factory=lambda: IntelligenceMetadataDict(),
        description=(
            "Request metadata using typed IntelligenceMetadataDict. "
            "See IntelligenceMetadataDict docstring for available fields."
        ),
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "IntelligenceMetadataDict",
    "IntelligenceOptionsDict",
    "ModelIntelligenceInput",
    "PerformanceContextDict",
]
