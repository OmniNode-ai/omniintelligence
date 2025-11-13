"""
Extraction Event Models for LangExtract Service

Event models for document extraction lifecycle, semantic analysis events,
and knowledge graph integration events.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ExtractionEventType(str, Enum):
    """Types of extraction events"""

    EXTRACTION_STARTED = "EXTRACTION_STARTED"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    SEMANTIC_ANALYSIS_COMPLETED = "SEMANTIC_ANALYSIS_COMPLETED"
    KNOWLEDGE_GRAPH_UPDATED = "KNOWLEDGE_GRAPH_UPDATED"
    BATCH_EXTRACTION_COMPLETED = "BATCH_EXTRACTION_COMPLETED"
    ENTITY_ENRICHMENT_COMPLETED = "ENTITY_ENRICHMENT_COMPLETED"


class ExtractionPriority(str, Enum):
    """Priority levels for extraction events"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ExtractionStartedEvent(BaseModel):
    """Event emitted when extraction process begins"""

    # Event identification
    event_id: UUID = Field(default_factory=uuid4)
    event_type: ExtractionEventType = Field(
        default=ExtractionEventType.EXTRACTION_STARTED
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Extraction context
    extraction_id: str = Field(..., description="Unique extraction identifier")
    document_path: str = Field(..., description="Path to document being extracted")
    extraction_mode: str = Field(..., description="Extraction mode being used")

    # Processing information
    expected_duration_seconds: Optional[float] = Field(
        None, description="Expected processing time"
    )
    priority: ExtractionPriority = Field(default=ExtractionPriority.NORMAL)

    # Request context
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
    requested_by: Optional[str] = Field(
        None, description="User/system requesting extraction"
    )

    # Configuration
    extraction_options: Dict[str, Any] = Field(default_factory=dict)


class ExtractionCompletedEvent(BaseModel):
    """Event emitted when extraction process completes successfully"""

    # Event identification
    event_id: UUID = Field(default_factory=uuid4)
    event_type: ExtractionEventType = Field(
        default=ExtractionEventType.EXTRACTION_COMPLETED
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Extraction context
    extraction_id: str = Field(..., description="Unique extraction identifier")
    document_path: str = Field(..., description="Path to extracted document")

    # Results summary
    entity_count: int = Field(..., ge=0, description="Number of entities extracted")
    relationship_count: int = Field(
        ..., ge=0, description="Number of relationships extracted"
    )
    pattern_count: int = Field(
        default=0, ge=0, description="Number of semantic patterns found"
    )

    # Quality metrics
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall extraction confidence"
    )
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Extraction quality score"
    )
    completeness_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Extraction completeness"
    )

    # Performance metrics
    processing_time_seconds: float = Field(
        ..., ge=0.0, description="Total processing time"
    )
    entities_per_second: Optional[float] = Field(
        None, ge=0.0, description="Extraction rate"
    )

    # Language analysis
    languages_detected: List[str] = Field(
        default_factory=list, description="Languages found in document"
    )
    primary_language: str = Field(default="en", description="Primary document language")
    multilingual_content: bool = Field(
        default=False, description="Whether content is multilingual"
    )

    # Content characteristics
    document_type: Optional[str] = Field(None, description="Detected document type")
    content_complexity: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Content complexity score"
    )
    semantic_density: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Semantic information density"
    )

    # Integration flags
    knowledge_graph_updated: bool = Field(
        default=False, description="Whether KG was updated"
    )
    events_emitted: bool = Field(
        default=False, description="Whether follow-up events were emitted"
    )

    # Correlation context
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
    batch_id: Optional[str] = Field(
        None, description="Batch ID if part of batch processing"
    )


class ExtractionFailedEvent(BaseModel):
    """Event emitted when extraction process fails"""

    # Event identification
    event_id: UUID = Field(default_factory=uuid4)
    event_type: ExtractionEventType = Field(
        default=ExtractionEventType.EXTRACTION_FAILED
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Extraction context
    extraction_id: str = Field(..., description="Unique extraction identifier")
    document_path: str = Field(..., description="Path to document that failed")

    # Failure information
    error_type: str = Field(..., description="Type/category of error")
    error_message: str = Field(..., description="Detailed error message")
    error_code: Optional[str] = Field(None, description="Specific error code")

    # Context information
    failure_stage: str = Field(..., description="Stage where failure occurred")
    partial_results: bool = Field(
        default=False, description="Whether partial results available"
    )

    # Retry information
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    retry_possible: bool = Field(
        default=True, description="Whether retry is recommended"
    )

    # Performance context
    processing_time_before_failure: Optional[float] = Field(
        None, ge=0.0, description="Time before failure"
    )

    # Correlation context
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
    batch_id: Optional[str] = Field(
        None, description="Batch ID if part of batch processing"
    )


class SemanticAnalysisEvent(BaseModel):
    """Event for semantic analysis completion"""

    # Event identification
    event_id: UUID = Field(default_factory=uuid4)
    event_type: ExtractionEventType = Field(
        default=ExtractionEventType.SEMANTIC_ANALYSIS_COMPLETED
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Analysis context
    analysis_id: str = Field(..., description="Unique analysis identifier")
    document_path: str = Field(..., description="Analyzed document path")
    extraction_id: Optional[str] = Field(None, description="Parent extraction ID")

    # Analysis results
    concepts_discovered: int = Field(
        default=0, ge=0, description="Number of concepts found"
    )
    themes_identified: int = Field(
        default=0, ge=0, description="Number of themes identified"
    )
    patterns_detected: int = Field(
        default=0, ge=0, description="Number of patterns found"
    )

    # Semantic metrics
    semantic_density: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Semantic information density"
    )
    conceptual_coherence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Conceptual coherence score"
    )
    thematic_consistency: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Thematic consistency score"
    )

    # Language analysis
    primary_language: str = Field(default="en", description="Primary content language")
    language_confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Language detection confidence"
    )

    # Content characteristics
    content_type: Optional[str] = Field(None, description="Content type classification")
    domain_indicators: List[str] = Field(
        default_factory=list, description="Domain/field indicators"
    )

    # Processing metrics
    analysis_time_seconds: float = Field(
        ..., ge=0.0, description="Analysis processing time"
    )

    # Integration context
    triggers_reranking: bool = Field(
        default=False, description="Whether analysis triggers reranking"
    )
    updates_knowledge_graph: bool = Field(
        default=False, description="Whether KG should be updated"
    )


class KnowledgeGraphUpdateEvent(BaseModel):
    """Event for knowledge graph update operations"""

    # Event identification
    event_id: UUID = Field(default_factory=uuid4)
    event_type: ExtractionEventType = Field(
        default=ExtractionEventType.KNOWLEDGE_GRAPH_UPDATED
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Update context
    update_id: str = Field(..., description="Unique update identifier")
    source_extraction_id: str = Field(..., description="Source extraction ID")
    document_path: str = Field(..., description="Source document path")

    # Update statistics
    entities_added: int = Field(default=0, ge=0, description="Number of entities added")
    entities_updated: int = Field(
        default=0, ge=0, description="Number of entities updated"
    )
    entities_deleted: int = Field(
        default=0, ge=0, description="Number of entities deleted"
    )
    relationships_added: int = Field(
        default=0, ge=0, description="Number of relationships added"
    )
    relationships_updated: int = Field(
        default=0, ge=0, description="Number of relationships updated"
    )
    relationships_deleted: int = Field(
        default=0, ge=0, description="Number of relationships deleted"
    )

    # Update operation details
    update_mode: str = Field(
        ..., description="Update mode used (upsert, replace, append)"
    )
    validation_passed: bool = Field(
        default=True, description="Whether validation passed"
    )

    # Quality metrics
    update_confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in update operation"
    )
    data_consistency_maintained: bool = Field(
        default=True, description="Whether data consistency maintained"
    )

    # Performance metrics
    update_time_seconds: float = Field(
        ..., ge=0.0, description="Update processing time"
    )
    graph_size_after_update: Optional[int] = Field(
        None, ge=0, description="Graph size after update"
    )

    # Conflict resolution
    conflicts_detected: int = Field(
        default=0, ge=0, description="Number of conflicts detected"
    )
    conflicts_resolved: int = Field(
        default=0, ge=0, description="Number of conflicts resolved"
    )

    # Integration effects
    triggers_search_reindex: bool = Field(
        default=False, description="Whether search index needs update"
    )
    affects_downstream_systems: bool = Field(
        default=False, description="Whether other systems affected"
    )


class BatchExtractionCompletedEvent(BaseModel):
    """Event for batch extraction completion"""

    # Event identification
    event_id: UUID = Field(default_factory=uuid4)
    event_type: ExtractionEventType = Field(
        default=ExtractionEventType.BATCH_EXTRACTION_COMPLETED
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Batch context
    batch_id: str = Field(..., description="Unique batch identifier")
    total_documents: int = Field(..., ge=1, description="Total documents in batch")

    # Processing results
    successful_extractions: int = Field(
        ..., ge=0, description="Number of successful extractions"
    )
    failed_extractions: int = Field(
        ..., ge=0, description="Number of failed extractions"
    )
    partial_extractions: int = Field(
        default=0, ge=0, description="Number of partial extractions"
    )

    # Aggregate statistics
    total_entities_extracted: int = Field(
        default=0, ge=0, description="Total entities across all documents"
    )
    total_relationships_extracted: int = Field(
        default=0, ge=0, description="Total relationships across all documents"
    )

    # Performance metrics
    batch_processing_time_seconds: float = Field(
        ..., ge=0.0, description="Total batch processing time"
    )
    average_document_processing_time: float = Field(
        ..., ge=0.0, description="Average per-document time"
    )
    documents_per_second: float = Field(
        ..., ge=0.0, description="Batch processing rate"
    )

    # Quality metrics
    average_confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Average extraction confidence"
    )
    batch_success_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Batch success rate"
    )

    # Error summary
    error_categories: Dict[str, int] = Field(
        default_factory=dict, description="Error category counts"
    )
    retry_recommendations: List[str] = Field(
        default_factory=list, description="Documents recommended for retry"
    )

    # Integration impact
    knowledge_graph_updates: int = Field(
        default=0, ge=0, description="Number of KG updates triggered"
    )
    downstream_events_emitted: int = Field(
        default=0, ge=0, description="Number of follow-up events"
    )


class EntityEnrichmentCompletedEvent(BaseModel):
    """Event for entity enrichment completion"""

    # Event identification
    event_id: UUID = Field(default_factory=uuid4)
    event_type: ExtractionEventType = Field(
        default=ExtractionEventType.ENTITY_ENRICHMENT_COMPLETED
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Enrichment context
    enrichment_id: str = Field(..., description="Unique enrichment identifier")
    source_extraction_id: str = Field(..., description="Source extraction ID")

    # Enrichment statistics
    entities_enriched: int = Field(..., ge=0, description="Number of entities enriched")
    enrichment_types_applied: List[str] = Field(
        default_factory=list, description="Types of enrichment applied"
    )

    # Quality improvements
    average_confidence_improvement: float = Field(
        default=0.0, description="Average confidence score improvement"
    )
    semantic_coverage_improvement: float = Field(
        default=0.0, ge=0.0, description="Semantic coverage improvement"
    )

    # Enrichment details
    embeddings_generated: int = Field(
        default=0, ge=0, description="Number of embeddings generated"
    )
    concept_links_added: int = Field(
        default=0, ge=0, description="Number of concept links added"
    )
    attribute_enhancements: int = Field(
        default=0, ge=0, description="Number of attribute enhancements"
    )

    # Performance metrics
    enrichment_time_seconds: float = Field(
        ..., ge=0.0, description="Enrichment processing time"
    )
    entities_per_second: float = Field(..., ge=0.0, description="Enrichment rate")

    # Integration effects
    knowledge_graph_updated: bool = Field(
        default=False, description="Whether KG was updated with enrichments"
    )
    search_index_updated: bool = Field(
        default=False, description="Whether search index was updated"
    )


# Event type registry for DocumentEventBus integration
LANGEXTRACT_EVENT_TYPES = {
    "extraction.started": ExtractionStartedEvent,
    "extraction.completed": ExtractionCompletedEvent,
    "extraction.failed": ExtractionFailedEvent,
    "semantic.analysis.completed": SemanticAnalysisEvent,
    "knowledge_graph.updated": KnowledgeGraphUpdateEvent,
    "batch.extraction.completed": BatchExtractionCompletedEvent,
    "entity.enrichment.completed": EntityEnrichmentCompletedEvent,
}


# Base event class for all LangExtract events
class BaseLangExtractEvent(BaseModel):
    """Base class for all LangExtract events"""

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    service_name: str = Field(default="langextract", description="Source service name")
    service_version: str = Field(default="1.0.0", description="Service version")

    # Event metadata
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
    trace_id: Optional[str] = Field(None, description="Distributed trace ID")
    user_id: Optional[str] = Field(None, description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier")

    # Event routing
    priority: ExtractionPriority = Field(default=ExtractionPriority.NORMAL)
    routing_key: Optional[str] = Field(None, description="Event routing key")
    target_services: List[str] = Field(
        default_factory=list, description="Target service names"
    )

    # Processing hints
    requires_acknowledgment: bool = Field(
        default=False, description="Whether event requires ack"
    )
    ttl_seconds: Optional[int] = Field(None, description="Time-to-live in seconds")
    retry_policy: Optional[Dict[str, Any]] = Field(
        None, description="Retry policy configuration"
    )


# Event payload wrapper for omnibase compatibility
class LangExtractEventEnvelope(BaseModel):
    """Event envelope for omnibase integration compatibility"""

    envelope_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(..., description="Event type identifier")
    payload: BaseLangExtractEvent = Field(..., description="Event payload")

    # Envelope metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source_service: str = Field(default="langextract")
    schema_version: str = Field(default="1.0.0")

    # Delivery metadata
    delivery_count: int = Field(default=0, ge=0)
    last_delivery_attempt: Optional[datetime] = Field(None)

    # Routing and processing
    routing_metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)
