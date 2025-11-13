"""
Pydantic models for Archon Document Freshness System

Data models for document freshness analysis, dependency tracking,
and intelligent data refresh operations.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class DocumentType(str, Enum):
    """Document classification types"""

    README = "README"
    API_DOCUMENTATION = "API_DOCUMENTATION"
    TUTORIAL = "TUTORIAL"
    GUIDE = "GUIDE"
    ARCHITECTURE = "ARCHITECTURE"
    TROUBLESHOOTING = "TROUBLESHOOTING"
    CHANGELOG = "CHANGELOG"
    CONFIGURATION = "CONFIGURATION"
    CODE_EXAMPLE = "CODE_EXAMPLE"
    REFERENCE = "REFERENCE"
    SPECIFICATION = "SPECIFICATION"
    UNKNOWN = "UNKNOWN"


class DependencyType(str, Enum):
    """Types of dependencies between documents"""

    FILE_REFERENCE = "FILE_REFERENCE"
    CODE_IMPORT = "CODE_IMPORT"
    CONFIG_REFERENCE = "CONFIG_REFERENCE"
    LINK_REFERENCE = "LINK_REFERENCE"
    IMAGE_REFERENCE = "IMAGE_REFERENCE"
    INCLUDE_REFERENCE = "INCLUDE_REFERENCE"
    CROSS_REFERENCE = "CROSS_REFERENCE"
    VERSION_DEPENDENCY = "VERSION_DEPENDENCY"


class FreshnessLevel(str, Enum):
    """Freshness level classifications"""

    FRESH = "FRESH"  # Recently updated, all dependencies current
    STALE = "STALE"  # Somewhat outdated but usable
    OUTDATED = "OUTDATED"  # Significantly outdated, needs attention
    CRITICAL = "CRITICAL"  # Critical staleness, may be incorrect/harmful


class RefreshPriority(str, Enum):
    """Priority levels for refresh operations"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Dependency(BaseModel):
    """Represents a dependency relationship between documents"""

    dependency_id: str = Field(..., description="Unique dependency identifier")
    source_path: str = Field(..., description="Path of the source document")
    target_path: str = Field(..., description="Path of the target dependency")
    dependency_type: DependencyType = Field(..., description="Type of dependency")
    line_number: Optional[int] = Field(
        None, description="Line number where dependency occurs"
    )
    context: Optional[str] = Field(None, description="Context around the dependency")
    is_critical: bool = Field(
        default=False, description="Whether this dependency is critical"
    )
    last_verified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    verification_status: str = Field(
        default="unverified", description="Status of dependency verification"
    )

    @validator("source_path", "target_path")
    def validate_paths(cls, v):
        """Ensure paths are valid strings"""
        if not v or not isinstance(v, str):
            raise ValueError("Path must be a non-empty string")
        return v


class FreshnessScore(BaseModel):
    """Detailed freshness scoring information"""

    overall_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall freshness score"
    )
    time_decay_score: float = Field(
        ..., ge=0.0, le=1.0, description="Score based on time since last update"
    )
    dependency_score: float = Field(
        ..., ge=0.0, le=1.0, description="Score based on dependency freshness"
    )
    content_relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Score based on content analysis"
    )
    usage_frequency_score: float = Field(
        ..., ge=0.0, le=1.0, description="Score based on access patterns"
    )

    # Scoring weights (how much each factor contributes)
    time_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    dependency_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    content_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    usage_weight: float = Field(default=0.1, ge=0.0, le=1.0)

    # Detailed scoring factors - flexible structure for complex scoring data
    factors: Dict[str, Any] = Field(
        default_factory=dict, description="Detailed scoring factors and metadata"
    )
    explanation: Optional[str] = Field(None, description="Explanation of scoring")

    class Config:
        # Allow arbitrary types to handle complex nested data structures
        arbitrary_types_allowed = True

    @validator("time_weight", "dependency_weight", "content_weight", "usage_weight")
    def validate_weights(cls, v):
        """Ensure weights are between 0 and 1"""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Weights must be between 0.0 and 1.0")
        return v


class DocumentClassification(BaseModel):
    """Document classification and metadata"""

    document_type: DocumentType = Field(..., description="Classified document type")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Classification confidence"
    )
    language: Optional[str] = Field(
        None, description="Programming language (for code docs)"
    )
    framework: Optional[str] = Field(None, description="Framework or technology")
    audience: Optional[str] = Field(
        None, description="Target audience (dev, user, admin)"
    )
    complexity_level: Optional[str] = Field(
        None, description="Complexity level (basic, intermediate, advanced)"
    )
    tags: List[str] = Field(default_factory=list, description="Categorization tags")

    # Auto-detection metadata
    has_code_examples: bool = Field(default=False)
    has_images: bool = Field(default=False)
    has_links: bool = Field(default=False)
    estimated_reading_time_minutes: Optional[int] = Field(None)
    word_count: Optional[int] = Field(None)


class DocumentFreshness(BaseModel):
    """Complete freshness analysis for a document"""

    document_id: str = Field(..., description="Unique document identifier")
    file_path: str = Field(..., description="Path to the document file")
    file_size_bytes: int = Field(..., ge=0)

    # Temporal information
    last_modified: datetime = Field(..., description="Last modification time")
    last_analyzed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: Optional[datetime] = Field(None, description="Document creation time")

    # Classification and scoring
    classification: DocumentClassification = Field(
        ..., description="Document classification"
    )
    freshness_score: FreshnessScore = Field(
        ..., description="Freshness scoring details"
    )
    freshness_level: FreshnessLevel = Field(..., description="Overall freshness level")

    # Dependencies
    dependencies: List[Dependency] = Field(default_factory=list)
    dependent_documents: List[str] = Field(
        default_factory=list, description="Documents that depend on this one"
    )
    critical_dependencies_count: int = Field(default=0)
    broken_dependencies_count: int = Field(default=0)

    # Refresh information
    needs_refresh: bool = Field(default=False)
    refresh_priority: RefreshPriority = Field(default=RefreshPriority.LOW)
    estimated_refresh_effort_minutes: Optional[int] = Field(None)

    # Analysis metadata
    analysis_version: str = Field(default="1.0.0")
    analyzer_metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def age_days(self) -> int:
        """Calculate document age in days"""
        return (datetime.now(timezone.utc) - self.last_modified).days

    @property
    def is_stale(self) -> bool:
        """Check if document is considered stale"""
        return self.freshness_level in [
            FreshnessLevel.STALE,
            FreshnessLevel.OUTDATED,
            FreshnessLevel.CRITICAL,
        ]

    @property
    def is_critical(self) -> bool:
        """Check if document requires critical attention"""
        return self.freshness_level == FreshnessLevel.CRITICAL


class RefreshStrategy(BaseModel):
    """Strategy for refreshing stale documents"""

    strategy_id: str = Field(..., description="Unique strategy identifier")
    document_path: str = Field(..., description="Target document path")
    refresh_type: str = Field(..., description="Type of refresh needed")

    # Strategy details
    priority: RefreshPriority = Field(..., description="Refresh priority")
    estimated_effort_minutes: int = Field(..., ge=0)
    risk_level: str = Field(..., description="Risk level of refresh operation")

    # Specific actions
    actions: List[str] = Field(
        default_factory=list, description="Specific refresh actions"
    )
    dependencies_to_update: List[str] = Field(default_factory=list)
    validation_steps: List[str] = Field(default_factory=list)

    # Scheduling
    recommended_schedule: Optional[datetime] = Field(None)
    frequency: Optional[str] = Field(
        None, description="Refresh frequency (daily, weekly, monthly)"
    )

    # Automation support
    can_automate: bool = Field(default=False)
    automation_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    manual_review_required: bool = Field(default=True)


class FreshnessAnalysis(BaseModel):
    """Complete freshness analysis result"""

    analysis_id: str = Field(..., description="Unique analysis identifier")
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Scope of analysis
    base_path: str = Field(..., description="Base path analyzed")
    total_documents: int = Field(..., ge=0)
    analyzed_documents: int = Field(..., ge=0)
    skipped_documents: int = Field(..., ge=0)

    # Results summary
    documents: List[DocumentFreshness] = Field(default_factory=list)
    freshness_distribution: Dict[str, int] = Field(default_factory=dict)

    # Statistics
    average_freshness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    stale_documents_count: int = Field(default=0)
    critical_documents_count: int = Field(default=0)
    total_dependencies: int = Field(default=0)
    broken_dependencies: int = Field(default=0)

    # Recommendations
    refresh_strategies: List[RefreshStrategy] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    priority_actions: List[str] = Field(default_factory=list)

    # Performance metadata
    analysis_time_seconds: float = Field(default=0.0, ge=0.0)
    memory_usage_mb: Optional[float] = Field(None)
    error_count: int = Field(default=0)
    warnings: List[str] = Field(default_factory=list)

    @property
    def staleness_percentage(self) -> float:
        """Calculate percentage of stale documents"""
        if self.analyzed_documents == 0:
            return 0.0
        return (self.stale_documents_count / self.analyzed_documents) * 100

    @property
    def health_score(self) -> float:
        """Calculate overall documentation health score"""
        if self.analyzed_documents == 0:
            return 1.0

        # Combine freshness and dependency health
        freshness_health = self.average_freshness_score
        dependency_health = 1.0 - (
            self.broken_dependencies / max(self.total_dependencies, 1)
        )

        return (freshness_health * 0.7) + (dependency_health * 0.3)


# API Request/Response Models


class FreshnessAnalysisRequest(BaseModel):
    """Request for document freshness analysis"""

    path: str = Field(..., description="Path to analyze (file or directory)")
    recursive: bool = Field(default=True, description="Analyze recursively")
    include_patterns: Optional[List[str]] = Field(
        None, description="File patterns to include"
    )
    exclude_patterns: Optional[List[str]] = Field(
        None, description="File patterns to exclude"
    )
    max_files: Optional[int] = Field(
        None, description="Maximum number of files to analyze"
    )

    # Analysis options
    calculate_dependencies: bool = Field(default=True)
    classify_documents: bool = Field(default=True)
    generate_strategies: bool = Field(default=True)
    include_detailed_scoring: bool = Field(default=False)


class RefreshRequest(BaseModel):
    """Request to refresh stale documents"""

    document_paths: List[str] = Field(..., description="Paths to refresh")
    refresh_mode: str = Field(
        default="safe", description="Refresh mode (safe, aggressive, force)"
    )
    backup_enabled: bool = Field(
        default=True, description="Whether to backup before refresh"
    )
    dry_run: bool = Field(default=False, description="Whether to perform a dry run")

    # Filtering options
    max_age_days: Optional[int] = Field(
        None, description="Only refresh docs older than N days"
    )
    min_freshness_score: Optional[float] = Field(
        None, description="Only refresh docs below score"
    )
    priority_filter: Optional[RefreshPriority] = Field(
        None, description="Filter by priority"
    )


class FreshnessStats(BaseModel):
    """Statistics about document freshness"""

    total_documents: int = Field(..., ge=0)
    fresh_count: int = Field(..., ge=0)
    stale_count: int = Field(..., ge=0)
    outdated_count: int = Field(..., ge=0)
    critical_count: int = Field(..., ge=0)

    average_age_days: float = Field(..., ge=0.0)
    average_freshness_score: float = Field(..., ge=0.0, le=1.0)

    # By document type
    type_distribution: Dict[str, int] = Field(default_factory=dict)

    # Recent activity
    recently_updated_count: int = Field(default=0, description="Updated in last 7 days")
    never_updated_count: int = Field(
        default=0, description="Never updated since creation"
    )

    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RefreshResult(BaseModel):
    """Result of a document refresh operation"""

    refresh_id: str = Field(..., description="Unique refresh operation ID")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(None)

    # Operation details
    requested_documents: List[str] = Field(
        ..., description="Documents requested for refresh"
    )
    processed_documents: List[str] = Field(default_factory=list)
    skipped_documents: List[str] = Field(default_factory=list)
    failed_documents: List[str] = Field(default_factory=list)

    # Results
    success_count: int = Field(default=0)
    failure_count: int = Field(default=0)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    # Impact assessment
    freshness_improvement: Dict[str, float] = Field(default_factory=dict)
    dependencies_fixed: List[str] = Field(default_factory=list)
    backup_locations: List[str] = Field(default_factory=list)

    # Performance
    total_time_seconds: float = Field(default=0.0)
    average_time_per_document: float = Field(default=0.0)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100
