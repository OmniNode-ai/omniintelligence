"""
Intelligence Service API Contracts - ONEX Effect Node Models

Request/response models for Intelligence Adapter Effect Node communication
with Archon Intelligence Service (http://localhost:8053).

ONEX Pattern: Effect Node (External HTTP I/O)
Service: Archon Intelligence Service
Base URL: http://localhost:8053

API Categories:
- Code Quality Assessment (POST /assess/code)
- Performance Analysis (POST /performance/baseline)
- Pattern Detection (POST /patterns/extract)
- Architectural Compliance (POST /compliance/check)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ============================================================================
# Enums and Constants
# ============================================================================


class ArchitecturalEra(str, Enum):
    """Architectural era classifications for temporal relevance."""

    PRE_ARCHON = "pre_archon"
    EARLY_ARCHON = "early_archon"
    MODERN_ARCHON = "modern_archon"
    ADVANCED_ARCHON = "advanced_archon"


class ValidationStatus(str, Enum):
    """Validation status for quality assessment."""

    UNVALIDATED = "unvalidated"
    VALIDATED = "validated"
    FAILED = "failed"
    PENDING = "pending"


class PatternCategory(str, Enum):
    """Pattern categories for detection and classification."""

    BEST_PRACTICES = "best_practices"
    ANTI_PATTERNS = "anti_patterns"
    SECURITY_PATTERNS = "security_patterns"
    ARCHITECTURAL_PATTERNS = "architectural_patterns"


# ============================================================================
# API Contract 1: Code Quality Assessment
# ============================================================================


class ModelQualityAssessmentRequest(BaseModel):
    """
    Request model for code quality assessment.

    Endpoint: POST /assess/code

    Performs comprehensive quality analysis including:
    - Overall quality scoring (6 dimensions)
    - ONEX architectural compliance
    - Complexity analysis (cyclomatic, cognitive)
    - Maintainability assessment
    - Pattern detection
    - Temporal relevance classification

    Attributes:
        content: Source code content to analyze
        source_path: File path for context and caching
        language: Programming language (auto-detected if None)
        include_recommendations: Include improvement recommendations
        min_quality_threshold: Minimum acceptable quality score (0.0-1.0)
    """

    content: str = Field(
        ..., description="Source code content to analyze", min_length=1
    )
    source_path: str = Field(
        ...,
        description="File path for context and pattern tracking",
        examples=["src/api/endpoints.py", "services/intelligence/main.py"],
    )
    language: Optional[str] = Field(
        default=None,
        description="Programming language (auto-detected from extension if None)",
        examples=["python", "typescript", "rust", "go"],
    )
    include_recommendations: bool = Field(
        default=True, description="Include actionable improvement recommendations"
    )
    min_quality_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable quality score for validation",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "def calculate_total(items: List[Item]) -> float:\n    return sum(item.price for item in items)",
                "source_path": "src/core/calculator.py",
                "language": "python",
                "include_recommendations": True,
                "min_quality_threshold": 0.7,
            }
        }


class ArchitecturalCompliance(BaseModel):
    """Architectural compliance details."""

    score: float = Field(
        ..., ge=0.0, le=1.0, description="ONEX architectural compliance score (0.0-1.0)"
    )
    reasoning: str = Field(..., description="Explanation of compliance assessment")


class MaintainabilityMetrics(BaseModel):
    """Maintainability assessment metrics."""

    complexity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Complexity score (inverse of cyclomatic complexity)",
    )
    readability_score: float = Field(
        ..., ge=0.0, le=1.0, description="Code readability score"
    )
    testability_score: float = Field(
        ..., ge=0.0, le=1.0, description="Testability assessment score"
    )


class OnexComplianceDetails(BaseModel):
    """ONEX compliance details and violations."""

    score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall ONEX compliance score"
    )
    violations: List[str] = Field(
        default_factory=list, description="List of ONEX compliance violations"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="ONEX compliance improvement recommendations"
    )


class ModelQualityAssessmentResponse(BaseModel):
    """
    Response model for code quality assessment.

    Contains comprehensive quality analysis with 6-dimensional scoring:
    1. Complexity (20%): Cyclomatic, cognitive, function/class size
    2. Maintainability (20%): Organization, structure
    3. Documentation (15%): Coverage, quality
    4. Temporal Relevance (15%): Era classification
    5. Pattern Compliance (15%): Best practices, anti-patterns
    6. Architectural Compliance (15%): ONEX pattern detection

    Attributes:
        success: Operation success status
        quality_score: Overall quality score (weighted average)
        architectural_compliance: Architectural compliance assessment
        code_patterns: Detected code patterns (best practices, anti-patterns)
        maintainability: Maintainability metrics breakdown
        onex_compliance: ONEX compliance details
        architectural_era: Temporal era classification
        temporal_relevance: Temporal relevance score
        timestamp: Analysis timestamp (ISO 8601)
        error: Error message if success=False
    """

    success: bool = Field(..., description="Operation success status")
    quality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall quality score (6-dimensional weighted average)",
    )
    architectural_compliance: ArchitecturalCompliance = Field(
        ..., description="Architectural compliance assessment"
    )
    code_patterns: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Detected code patterns (best practices, anti-patterns, security)",
    )
    maintainability: MaintainabilityMetrics = Field(
        ..., description="Maintainability metrics breakdown"
    )
    onex_compliance: OnexComplianceDetails = Field(
        ..., description="ONEX compliance details and recommendations"
    )
    architectural_era: str = Field(
        ...,
        description="Architectural era classification (pre_archon, modern_archon, etc.)",
    )
    temporal_relevance: float = Field(
        ..., ge=0.0, le=1.0, description="Temporal relevance score based on era"
    )
    timestamp: datetime = Field(..., description="Analysis timestamp (ISO 8601)")
    error: Optional[str] = Field(
        default=None, description="Error message if success=False"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "quality_score": 0.87,
                "architectural_compliance": {
                    "score": 0.92,
                    "reasoning": "Strong ONEX compliance with proper node typing",
                },
                "code_patterns": [],
                "maintainability": {
                    "complexity_score": 0.85,
                    "readability_score": 0.90,
                    "testability_score": 0.82,
                },
                "onex_compliance": {
                    "score": 0.92,
                    "violations": [],
                    "recommendations": [
                        "Add docstring examples",
                        "Include type hints for return values",
                    ],
                },
                "architectural_era": "modern_archon",
                "temporal_relevance": 0.88,
                "timestamp": "2025-10-21T14:00:00+00:00",
            }
        }


# ============================================================================
# API Contract 2: Performance Analysis
# ============================================================================


class ModelPerformanceAnalysisRequest(BaseModel):
    """
    Request model for performance baseline analysis.

    Endpoint: POST /performance/baseline

    Establishes performance baselines for operations and identifies
    optimization opportunities with ROI estimates.

    Attributes:
        operation_name: Unique operation identifier for tracking
        code_content: Code to analyze for performance characteristics
        context: Optional execution context (async/sync, I/O-bound, CPU-bound)
        include_opportunities: Include optimization opportunity analysis
        target_percentile: Target performance percentile (50, 90, 95, 99)
    """

    operation_name: str = Field(
        ...,
        description="Unique operation identifier for baseline tracking",
        min_length=1,
        examples=["database_query", "api_endpoint_users", "vector_search"],
    )
    code_content: str = Field(
        ...,
        description="Code content to analyze for performance baseline",
        min_length=1,
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Execution context metadata (async/sync, I/O type, dependencies)",
    )
    include_opportunities: bool = Field(
        default=True, description="Include optimization opportunity analysis"
    )
    target_percentile: int = Field(
        default=95,
        ge=50,
        le=99,
        description="Target performance percentile for SLA (50, 90, 95, 99)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "operation_name": "database_query_users",
                "code_content": "async def query_users(db: Session) -> List[User]:\n    return db.query(User).all()",
                "context": {
                    "execution_type": "async",
                    "io_type": "database",
                    "expected_frequency": "high",
                },
                "include_opportunities": True,
                "target_percentile": 95,
            }
        }


class BaselineMetrics(BaseModel):
    """
    Performance baseline metrics (DEPRECATED - kept for backward compatibility).

    Use ModelPerformanceAnalysisResponse directly instead.
    """

    operation_name: str = Field(..., description="Operation identifier")
    baseline_latency_ms: Optional[float] = Field(
        default=None, description="Baseline latency in milliseconds (if available)"
    )
    target_latency_ms: Optional[float] = Field(
        default=None, description="Target latency based on percentile"
    )
    complexity_estimate: str = Field(
        default="medium",
        description="Estimated computational complexity (low, medium, high)",
    )
    io_characteristics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="I/O characteristics (sync/async, blocking, network/disk)",
    )


class OptimizationOpportunity(BaseModel):
    """Single optimization opportunity with ROI estimate."""

    opportunity_id: str = Field(..., description="Unique opportunity identifier")
    title: str = Field(..., description="Opportunity title")
    description: str = Field(..., description="Detailed description of optimization")
    category: str = Field(
        ..., description="Category (caching, indexing, async, batching, etc.)"
    )
    estimated_improvement: str = Field(
        ..., description="Estimated improvement (e.g., '30-50% latency reduction')"
    )
    effort_estimate: str = Field(
        ..., description="Implementation effort (low, medium, high)"
    )
    roi_score: float = Field(
        ..., ge=0.0, le=1.0, description="ROI score (0.0-1.0, higher = better ROI)"
    )
    implementation_steps: List[str] = Field(
        default_factory=list, description="Recommended implementation steps"
    )


class ModelPerformanceAnalysisResponse(BaseModel):
    """
    Response model for performance baseline analysis.

    **UPDATED**: Now matches actual API response format (flat structure).

    The API returns performance metrics directly without wrapping in
    a nested structure. Response varies based on baseline source:

    - **code_analysis**: Synthetic baseline from code complexity analysis
    - **cached**: Real baseline from historical measurements
    - **empty**: No baseline available yet

    Attributes:
        operation_name: Operation identifier
        average_response_time_ms: Mean response time
        p50_ms: 50th percentile response time
        p95_ms: 95th percentile response time
        p99_ms: 99th percentile response time
        quality_score: Overall quality score (code_analysis only)
        complexity_score: Code complexity score (code_analysis only)
        sample_size: Number of measurements (0 if no baseline)
        timestamp: Analysis timestamp (ISO 8601 string)
        source: Baseline source ("code_analysis", "cached", or empty string)
        message: Optional status message
        std_dev_ms: Standard deviation (cached baseline only)
    """

    operation_name: str = Field(
        ..., description="Operation identifier for baseline tracking"
    )
    average_response_time_ms: float = Field(
        ..., ge=0.0, description="Average/mean response time in milliseconds"
    )
    p50_ms: float = Field(
        ...,
        ge=0.0,
        description="50th percentile (median) response time in milliseconds",
    )
    p95_ms: float = Field(
        ..., ge=0.0, description="95th percentile response time in milliseconds"
    )
    p99_ms: float = Field(
        ..., ge=0.0, description="99th percentile response time in milliseconds"
    )
    quality_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall quality score (0.0-1.0, code_analysis source only)",
    )
    complexity_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Code complexity score (0.0-1.0, code_analysis source only)",
    )
    sample_size: int = Field(
        ..., ge=0, description="Number of measurements in baseline (0 if no baseline)"
    )
    timestamp: str = Field(..., description="Analysis timestamp (ISO 8601 format)")
    source: str = Field(
        ...,
        description="Baseline source: 'code_analysis' (synthetic), 'cached' (historical), or empty",
    )
    message: Optional[str] = Field(
        default=None, description="Optional status or informational message"
    )
    std_dev_ms: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Standard deviation in milliseconds (cached baseline only)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "operation_name": "test_operation",
                "average_response_time_ms": 140.0,
                "p50_ms": 126.0,
                "p95_ms": 210.0,
                "p99_ms": 280.0,
                "quality_score": 0.5683333333333334,
                "complexity_score": 0.9,
                "sample_size": 1,
                "timestamp": "2025-10-21T15:28:07.601704+00:00",
                "source": "code_analysis",
                "message": "Synthetic baseline generated from code analysis",
            }
        }


# ============================================================================
# API Contract 3: Pattern Detection
# ============================================================================


class ModelPatternDetectionRequest(BaseModel):
    """
    Request model for pattern detection and extraction.

    Endpoint: POST /patterns/extract

    Detects code patterns including:
    - Best practices (SOLID, DRY, KISS)
    - Anti-patterns (code smells, performance issues)
    - Security patterns (input validation, authentication)
    - Architectural patterns (node types, contracts)

    Attributes:
        content: Source code content to analyze
        source_path: File path for context
        pattern_categories: Categories to detect (None = all)
        min_confidence: Minimum confidence threshold (0.0-1.0)
        include_recommendations: Include pattern-based recommendations
    """

    content: str = Field(
        ..., description="Source code content to analyze for patterns", min_length=1
    )
    source_path: str = Field(
        ...,
        description="File path for context and tracking",
        examples=["src/api/routes.py", "services/auth/middleware.py"],
    )
    pattern_categories: Optional[List[PatternCategory]] = Field(
        default=None, description="Pattern categories to detect (None = all categories)"
    )
    min_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for pattern detection",
    )
    include_recommendations: bool = Field(
        default=True, description="Include pattern-based improvement recommendations"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "class UserService:\n    def __init__(self, db):\n        self.db = db",
                "source_path": "src/services/user_service.py",
                "pattern_categories": ["best_practices", "anti_patterns"],
                "min_confidence": 0.7,
                "include_recommendations": True,
            }
        }


class DetectedPattern(BaseModel):
    """Single detected pattern with metadata."""

    pattern_id: str = Field(..., description="Pattern identifier")
    pattern_type: str = Field(
        ..., description="Pattern type (e.g., 'singleton', 'factory', 'god_class')"
    )
    category: PatternCategory = Field(..., description="Pattern category")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Detection confidence (0.0-1.0)"
    )
    description: str = Field(..., description="Pattern description and context")
    location: Optional[Dict[str, Any]] = Field(
        default=None, description="Code location (line numbers, function names)"
    )
    severity: Optional[str] = Field(
        default=None,
        description="Severity for anti-patterns (low, medium, high, critical)",
    )
    suggested_fix: Optional[str] = Field(
        default=None, description="Suggested fix for anti-patterns"
    )


class ArchitecturalComplianceDetails(BaseModel):
    """Architectural compliance details for patterns."""

    onex_compliance: bool = Field(
        ..., description="Whether patterns comply with ONEX standards"
    )
    node_type_detected: Optional[str] = Field(
        default=None,
        description="Detected ONEX node type (Effect, Compute, Reducer, Orchestrator)",
    )
    contract_compliance: bool = Field(
        default=False, description="Whether contract patterns are compliant"
    )
    violations: List[str] = Field(
        default_factory=list, description="ONEX compliance violations"
    )


class ModelPatternDetectionResponse(BaseModel):
    """
    Response model for pattern detection.

    Contains detected patterns with confidence scores, categorization,
    and actionable recommendations.

    Attributes:
        success: Operation success status
        detected_patterns: List of detected patterns
        anti_patterns: Detected anti-patterns (subset for quick access)
        architectural_compliance: ONEX architectural compliance
        analysis_summary: Summary statistics
        confidence_scores: Confidence scoring metadata
        recommendations: Pattern-based improvement recommendations
        timestamp: Analysis timestamp (ISO 8601)
        error: Error message if success=False
    """

    success: bool = Field(..., description="Operation success status")
    detected_patterns: List[DetectedPattern] = Field(
        default_factory=list, description="All detected patterns"
    )
    anti_patterns: List[DetectedPattern] = Field(
        default_factory=list,
        description="Detected anti-patterns (subset for quick access)",
    )
    architectural_compliance: Optional[ArchitecturalComplianceDetails] = Field(
        default=None, description="ONEX architectural compliance assessment"
    )
    analysis_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Analysis summary (pattern counts, coverage, etc.)",
    )
    confidence_scores: Dict[str, float] = Field(
        default_factory=dict, description="Overall confidence scores by category"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Pattern-based improvement recommendations"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Analysis timestamp (ISO 8601)"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if success=False"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "detected_patterns": [
                    {
                        "pattern_id": "pat_001",
                        "pattern_type": "dependency_injection",
                        "category": "best_practices",
                        "confidence": 0.92,
                        "description": "Dependency injection via constructor",
                        "location": {"line_start": 5, "line_end": 7},
                        "severity": None,
                        "suggested_fix": None,
                    }
                ],
                "anti_patterns": [],
                "architectural_compliance": {
                    "onex_compliance": True,
                    "node_type_detected": "Effect",
                    "contract_compliance": True,
                    "violations": [],
                },
                "analysis_summary": {
                    "pattern_type": "best_practices",
                    "content_analyzed": 150,
                    "patterns_found": 1,
                },
                "confidence_scores": {
                    "overall_confidence": 0.8,
                    "pattern_accuracy": 0.85,
                },
                "recommendations": ["Consider adding interface for better testability"],
                "timestamp": "2025-10-21T14:00:00+00:00",
            }
        }


# ============================================================================
# Additional Response Models
# ============================================================================


class ModelHealthCheckResponse(BaseModel):
    """Health check response from Intelligence Service."""

    status: str = Field(
        ..., description="Service health status (healthy, degraded, unhealthy)"
    )
    memgraph_connected: bool = Field(
        ..., description="Memgraph knowledge graph connection status"
    )
    ollama_connected: bool = Field(
        ..., description="Ollama LLM service connection status"
    )
    freshness_database_connected: bool = Field(
        ..., description="Freshness database connection status"
    )
    service_version: str = Field(..., description="Service version")
    uptime_seconds: Optional[float] = Field(
        default=None, description="Service uptime in seconds"
    )
    error: Optional[str] = Field(default=None, description="Error message if unhealthy")
    last_check: datetime = Field(..., description="Last health check timestamp")


class ModelErrorResponse(BaseModel):
    """Standard error response from Intelligence Service."""

    success: bool = Field(
        default=False, description="Operation success status (always False for errors)"
    )
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(
        default=None, description="Error code for programmatic handling"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )
