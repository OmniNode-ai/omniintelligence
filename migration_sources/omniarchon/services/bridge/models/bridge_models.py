"""
Pydantic models for Bridge Service

Data models for bridge API communication and entity mapping.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Import EntityType via adapter (handles unified vs legacy)
from .entity_type_adapter import EntityType


class SyncDirection(str, Enum):
    """Sync direction options"""

    POSTGRES_TO_GRAPH = "postgres_to_graph"
    GRAPH_TO_POSTGRES = "graph_to_postgres"
    BIDIRECTIONAL = "bidirectional"


class SyncRequest(BaseModel):
    """Request model for sync operations"""

    entity_types: List[EntityType] = Field(
        default_factory=list, description="Entity types to sync"
    )
    since_timestamp: Optional[datetime] = Field(
        default=None, description="Sync changes since this timestamp"
    )
    source_ids: Optional[List[str]] = Field(
        default=None, description="Specific source IDs to sync"
    )
    direction: SyncDirection = Field(
        default=SyncDirection.BIDIRECTIONAL, description="Sync direction"
    )
    dry_run: bool = Field(default=False, description="Preview changes without applying")


class SyncResponse(BaseModel):
    """Response model for sync operations"""

    sync_id: str = Field(..., description="Unique sync operation ID")
    status: str = Field(..., description="Sync status")
    message: str = Field(..., description="Status message")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    entities_processed: Optional[int] = None
    entities_created: Optional[int] = None
    entities_updated: Optional[int] = None
    errors: List[str] = Field(default_factory=list)


class DatabaseQueryRequest(BaseModel):
    """Request model for database query execution"""

    query: str = Field(..., description="SQL query to execute")
    params: Optional[List[Any]] = Field(default=None, description="Query parameters")
    fetch_mode: str = Field(
        default="all", description="Fetch mode: 'all', 'one', 'many', or 'execute'"
    )
    limit: Optional[int] = Field(default=None, description="Limit number of results")


class DatabaseQueryResponse(BaseModel):
    """Response model for database query execution"""

    success: bool = Field(..., description="Whether query executed successfully")
    data: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Query result data"
    )
    rows_affected: Optional[int] = Field(
        default=None, description="Number of rows affected"
    )
    message: Optional[str] = Field(default=None, description="Status or error message")
    execution_time_ms: Optional[float] = Field(
        default=None, description="Query execution time in milliseconds"
    )


class EntityMappingRequest(BaseModel):
    """Request model for entity mapping operations"""

    entity_type: EntityType = Field(..., description="Type of entity to map")
    entity_id: str = Field(..., description="ID of entity to map")
    include_relationships: bool = Field(
        default=True, description="Include related entities"
    )
    include_content: bool = Field(default=True, description="Include content analysis")
    force_refresh: bool = Field(
        default=False, description="Force re-mapping even if exists"
    )


class BridgeHealthStatus(BaseModel):
    """Health status of bridge service"""

    status: str = Field(..., description="Overall service status")
    memgraph_connected: bool = Field(default=False)
    intelligence_connected: bool = Field(default=False)
    service_version: str = Field(default="1.0.0")
    uptime_seconds: Optional[float] = None
    error: Optional[str] = None
    last_check: datetime = Field(default_factory=datetime.utcnow)


class SupabaseEntity(BaseModel):
    """Base model for Supabase entities"""

    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ArchonSource(SupabaseEntity):
    """Archon source entity from Supabase"""

    source_id: str
    source_url: str
    source_display_name: str
    source_type: str
    status: str
    crawl_schedule: Optional[str] = None
    last_crawled_at: Optional[datetime] = None
    total_pages: Optional[int] = 0


class ArchonProject(SupabaseEntity):
    """Archon project entity from Supabase"""

    project_id: str
    title: str
    description: Optional[str] = None
    github_repo: Optional[str] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


class ArchonCrawledPage(SupabaseEntity):
    """Archon crawled page entity from Supabase"""

    page_id: str
    source_id: str
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    content_hash: Optional[str] = None
    page_type: Optional[str] = None
    embedding: Optional[List[float]] = None


class ArchonCodeExample(SupabaseEntity):
    """Archon code example entity from Supabase"""

    example_id: str
    source_id: str
    page_id: Optional[str] = None
    language: str
    code_content: str
    summary: Optional[str] = None


class MappingResult(BaseModel):
    """Result of entity mapping operation"""

    source_entity_id: str
    source_entity_type: EntityType
    graph_entity_ids: List[str] = Field(default_factory=list)
    relationships_created: int = 0
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    mapping_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SyncStatistics(BaseModel):
    """Statistics for sync operations"""

    total_entities_synced: int = 0
    entities_by_type: Dict[EntityType, int] = Field(default_factory=dict)
    last_full_sync: Optional[datetime] = None
    last_incremental_sync: Optional[datetime] = None
    sync_errors: List[str] = Field(default_factory=list)
    performance_metrics: Dict[str, float] = Field(default_factory=dict)


class ContentExtractionRequest(BaseModel):
    """Request for content extraction via intelligence service"""

    content: str = Field(..., description="Content to extract entities from")
    source_path: str = Field(..., description="Source path for context")
    content_type: str = Field(default="document", description="Type of content")
    language: Optional[str] = Field(
        default=None, description="Programming language if code"
    )
    extract_relationships: bool = Field(
        default=True, description="Extract entity relationships"
    )


class BridgeConfiguration(BaseModel):
    """Configuration for bridge service"""

    sync_interval_minutes: int = Field(
        default=60, description="Auto-sync interval in minutes"
    )
    batch_size: int = Field(default=100, description="Batch size for sync operations")
    max_retry_attempts: int = Field(
        default=3, description="Max retry attempts for failed operations"
    )
    enable_auto_sync: bool = Field(
        default=False, description="Enable automatic synchronization"
    )
    intelligence_service_timeout: float = Field(
        default=30.0, description="Intelligence service timeout in seconds"
    )
    mapping_confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum confidence for entity mapping"
    )


# Webhook models for real-time sync
class SupabaseWebhookPayload(BaseModel):
    """Supabase webhook payload structure"""

    type: str  # INSERT, UPDATE, DELETE
    table: str
    db_schema: str = Field(..., alias="schema", description="Database schema name")
    record: Dict[str, Any]
    old_record: Optional[Dict[str, Any]] = None


class WebhookSyncRequest(BaseModel):
    """Request to process webhook for real-time sync"""

    payload: SupabaseWebhookPayload
    sync_to_graph: bool = Field(default=True)
    extract_entities: bool = Field(default=True)


class RealtimeDocumentSyncRequest(BaseModel):
    """Request model for real-time document synchronization from MCP"""

    document_id: str = Field(..., description="Document ID")
    project_id: str = Field(..., description="Project ID")
    document_data: Dict[str, Any] = Field(..., description="Complete document data")
    source: Optional[str] = Field(
        default="unknown", description="Source of the sync request"
    )
    trigger_type: Optional[str] = Field(default="manual", description="Type of trigger")
