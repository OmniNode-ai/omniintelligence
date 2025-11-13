"""
Document Update Event Models for Event-Driven Freshness Analysis

Events that trigger automatic freshness re-evaluation when documents
are created, updated, or deleted in the intelligence system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocumentUpdateType(str, Enum):
    """Types of document update events"""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    BATCH_UPDATED = "BATCH_UPDATED"


class FreshnessAnalysisTrigger(str, Enum):
    """What triggered the freshness analysis"""

    DOCUMENT_UPDATE = "DOCUMENT_UPDATE"
    SCHEDULED_REFRESH = "SCHEDULED_REFRESH"
    MANUAL_REQUEST = "MANUAL_REQUEST"
    DEPENDENCY_CHANGE = "DEPENDENCY_CHANGE"


class DocumentUpdateEvent(BaseModel):
    """
    Event triggered when a document is updated, requiring freshness re-evaluation.

    This event integrates with the existing omnibase event system to trigger
    automatic freshness analysis workflows.
    """

    # Event identification
    event_id: UUID = Field(default_factory=uuid4)
    event_type: DocumentUpdateType = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Document information
    document_path: str = Field(..., description="Path to the updated document")
    document_id: Optional[str] = Field(
        None, description="Document identifier if available"
    )
    content_hash: Optional[str] = Field(
        None, description="Content hash for change detection"
    )

    # Update details
    file_size: Optional[int] = Field(None, description="File size in bytes")
    modification_time: Optional[datetime] = Field(
        None, description="Last modification time"
    )
    created_by: Optional[str] = Field(
        None, description="User/system that created the update"
    )

    # Context information
    base_path: Optional[str] = Field(
        None, description="Base directory for batch operations"
    )
    affected_dependencies: List[str] = Field(
        default_factory=list, description="Paths of dependent documents"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional event metadata"
    )

    # Processing hints
    priority: int = Field(
        default=5, ge=1, le=10, description="Processing priority (1=highest, 10=lowest)"
    )
    batch_id: Optional[UUID] = Field(None, description="Batch ID for grouped updates")
    requires_immediate_analysis: bool = Field(
        default=False, description="Skip batch processing"
    )


class FreshnessAnalysisRequestedEvent(BaseModel):
    """
    Event requesting freshness analysis to be performed.

    Can be triggered by document updates, schedules, or manual requests.
    """

    event_id: UUID = Field(default_factory=uuid4)
    trigger: FreshnessAnalysisTrigger = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Analysis scope
    target_paths: List[str] = Field(..., description="Paths to analyze")
    recursive: bool = Field(default=True, description="Analyze recursively")
    max_files: Optional[int] = Field(None, description="Limit number of files")

    # Analysis options
    include_patterns: Optional[List[str]] = Field(
        None, description="File patterns to include"
    )
    exclude_patterns: Optional[List[str]] = Field(
        None, description="File patterns to exclude"
    )
    calculate_dependencies: bool = Field(default=True)

    # Processing context
    correlation_id: Optional[UUID] = Field(
        None, description="Correlation with triggering event"
    )
    requested_by: Optional[str] = Field(
        None, description="User/system requesting analysis"
    )
    priority: int = Field(default=5, ge=1, le=10)

    # Workflow hints
    use_cache: bool = Field(default=True, description="Use cached results if available")
    force_refresh: bool = Field(default=False, description="Force fresh analysis")


class FreshnessAnalysisCompletedEvent(BaseModel):
    """
    Event published when freshness analysis completes.

    Contains analysis results and triggers re-ranking workflows.
    """

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Analysis identification
    analysis_id: str = Field(..., description="Analysis identifier")
    correlation_id: Optional[UUID] = Field(
        None, description="Correlation with request event"
    )

    # Results summary
    total_documents: int = Field(..., ge=0)
    analyzed_documents: int = Field(..., ge=0)
    stale_documents_count: int = Field(default=0)
    critical_documents_count: int = Field(default=0)

    # Performance metrics
    analysis_time_seconds: float = Field(..., ge=0.0)
    documents_per_second: float = Field(default=0.0, ge=0.0)

    # Quality indicators
    average_freshness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    health_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Actions triggered
    requires_reranking: bool = Field(
        default=True, description="Trigger document re-ranking"
    )
    updated_document_paths: List[str] = Field(default_factory=list)

    # Status and error handling
    status: str = Field(default="completed", description="Analysis status")
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class DocumentRerankingRequestedEvent(BaseModel):
    """
    Event requesting document re-ranking based on freshness analysis.

    Triggered automatically after freshness analysis completion.
    """

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Triggering context
    analysis_id: str = Field(..., description="Analysis that triggered re-ranking")
    correlation_id: Optional[UUID] = Field(None)

    # Re-ranking scope
    document_paths: List[str] = Field(..., description="Documents to re-rank")
    freshness_scores: Dict[str, float] = Field(
        default_factory=dict, description="Path -> freshness score mapping"
    )

    # Re-ranking options
    ranking_algorithm: str = Field(
        default="weighted_freshness", description="Ranking algorithm to use"
    )
    include_dependencies: bool = Field(
        default=True, description="Consider dependency relationships"
    )
    boost_recent_updates: bool = Field(
        default=True, description="Boost recently updated documents"
    )

    # Integration targets
    update_knowledge_graph: bool = Field(
        default=True, description="Update knowledge graph rankings"
    )
    update_search_index: bool = Field(
        default=True, description="Update search index priorities"
    )
    notify_subscribers: bool = Field(
        default=False, description="Notify ranking change subscribers"
    )


# Event type registry for omnibase integration
FRESHNESS_EVENT_TYPES = {
    "document.updated": DocumentUpdateEvent,
    "freshness.analysis.requested": FreshnessAnalysisRequestedEvent,
    "freshness.analysis.completed": FreshnessAnalysisCompletedEvent,
    "document.reranking.requested": DocumentRerankingRequestedEvent,
}
