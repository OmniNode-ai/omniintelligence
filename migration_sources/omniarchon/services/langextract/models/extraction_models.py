"""
Pydantic Data Models for LangExtract Service

Comprehensive data models for advanced language-aware extraction,
semantic analysis, and knowledge graph integration.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


# Enums for entity and relationship types
class EntityType(str, Enum):
    """Enhanced entity types for language-aware extraction"""

    # Code entities
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    MODULE = "module"
    INTERFACE = "interface"
    ENUM = "enum"

    # Documentation entities
    DOCUMENT = "document"
    CONCEPT = "concept"
    PROCEDURE = "procedure"
    REQUIREMENT = "requirement"
    SPECIFICATION = "specification"
    EXAMPLE = "example"

    # Semantic entities
    TOPIC = "topic"
    THEME = "theme"
    KEYWORD = "keyword"
    CATEGORY = "category"
    TAG = "tag"

    # Structured data entities
    SCHEMA = "schema"
    FIELD = "field"
    RECORD = "record"
    TABLE = "table"

    # Language-specific entities
    PHRASE = "phrase"
    SENTIMENT = "sentiment"
    INTENT = "intent"
    ENTITY_MENTION = "entity_mention"


class RelationshipType(str, Enum):
    """Enhanced relationship types for semantic connections"""

    # Structural relationships
    CONTAINS = "contains"
    BELONGS_TO = "belongs_to"
    INHERITS_FROM = "inherits_from"
    INHERITS = "INHERITS"  # Code detector output format
    IMPLEMENTS = "implements"
    DEPENDS_ON = "depends_on"
    IMPORTS = "IMPORTS"  # Code detector output format

    # Semantic relationships
    RELATES_TO = "relates_to"
    SIMILAR_TO = "similar_to"
    OPPOSITE_OF = "opposite_of"
    PART_OF = "part_of"
    EXAMPLE_OF = "example_of"

    # Functional relationships
    CALLS = "calls"
    CALLS_UPPER = "CALLS"  # Code detector output format
    USES = "uses"
    DEFINES = "defines"
    DEFINES_UPPER = "DEFINES"  # Code detector output format
    REFERENCES = "references"

    # Conceptual relationships
    DESCRIBES = "describes"
    EXPLAINS = "explains"
    DEMONSTRATES = "demonstrates"
    CATEGORIZES = "categorizes"


class LanguageCode(str, Enum):
    """Supported language codes for multilingual extraction"""

    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    ARABIC = "ar"
    HINDI = "hi"
    AUTO_DETECT = "auto"


class ExtractionMode(str, Enum):
    """Extraction processing modes"""

    FAST = "fast"  # Quick extraction with basic patterns
    STANDARD = "standard"  # Balanced extraction with semantic analysis
    COMPREHENSIVE = "comprehensive"  # Deep analysis with all features
    CUSTOM = "custom"  # Custom configuration


class ConfidenceLevel(str, Enum):
    """Confidence level categories"""

    LOW = "low"  # 0.0 - 0.4
    MEDIUM = "medium"  # 0.4 - 0.7
    HIGH = "high"  # 0.7 - 0.9
    VERY_HIGH = "very_high"  # 0.9 - 1.0


# Core data models
class EntityMetadata(BaseModel):
    """Metadata for extracted entities"""

    extraction_method: str = Field(..., description="Method used for extraction")
    confidence_level: ConfidenceLevel = Field(..., description="Confidence category")
    language_detected: Optional[LanguageCode] = Field(
        None, description="Detected language"
    )

    # Timing information
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[float] = Field(
        None, description="Processing time in milliseconds"
    )

    # Quality metrics
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Quality assessment score"
    )
    completeness_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Completeness assessment"
    )

    # Source information
    source_line_start: Optional[int] = Field(None, description="Starting line number")
    source_line_end: Optional[int] = Field(None, description="Ending line number")
    source_char_start: Optional[int] = Field(
        None, description="Starting character position"
    )
    source_char_end: Optional[int] = Field(
        None, description="Ending character position"
    )

    # Semantic context
    semantic_context: Dict[str, Any] = Field(default_factory=dict)
    linguistic_features: Dict[str, Any] = Field(default_factory=dict)


class EnhancedEntity(BaseModel):
    """Enhanced entity with language-aware features"""

    # Core identification
    entity_id: str = Field(..., description="Unique entity identifier")
    name: str = Field(..., description="Entity name or primary identifier")
    entity_type: EntityType = Field(..., description="Type of entity")

    # Content and description
    description: str = Field("", description="Human-readable description")
    content: Optional[str] = Field(None, description="Full content/source code")
    summary: Optional[str] = Field(None, description="Brief summary")

    # Confidence and quality
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Extraction confidence"
    )
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Content quality score"
    )

    # Location and context
    source_path: str = Field(..., description="Source file path")
    parent_entity_id: Optional[str] = Field(None, description="Parent entity if nested")

    # Enhanced features
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    tags: List[str] = Field(default_factory=list, description="Semantic tags")
    categories: List[str] = Field(
        default_factory=list, description="Classification categories"
    )

    # Language and semantic information
    language: Optional[LanguageCode] = Field(None, description="Content language")
    semantic_embedding: Optional[List[float]] = Field(
        None, description="Vector embedding"
    )
    semantic_concepts: List[str] = Field(
        default_factory=list, description="Associated concepts"
    )

    # Properties and attributes
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Additional properties"
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Structured attributes"
    )

    # Metadata
    metadata: EntityMetadata = Field(default_factory=EntityMetadata)

    @validator("confidence_score")
    def validate_confidence_score(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v


class EnhancedRelationship(BaseModel):
    """Enhanced relationship with semantic features"""

    # Core identification
    relationship_id: str = Field(..., description="Unique relationship identifier")
    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")

    # Confidence and quality
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Relationship confidence"
    )
    strength: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Relationship strength"
    )

    # Description and context
    description: Optional[str] = Field(None, description="Relationship description")
    context: Optional[str] = Field(
        None, description="Context where relationship was found"
    )

    # Semantic features
    semantic_weight: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Semantic importance"
    )
    directionality: bool = Field(
        True, description="Whether relationship is directional"
    )

    # Properties and metadata
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Additional properties"
    )
    evidence: List[str] = Field(
        default_factory=list, description="Evidence supporting relationship"
    )

    # Location information
    detected_in_source: Optional[str] = Field(
        None, description="Source where relationship was detected"
    )
    source_line_number: Optional[int] = Field(
        None, description="Line where relationship evidence found"
    )

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SemanticPattern(BaseModel):
    """Semantic pattern detected in content"""

    pattern_id: str = Field(..., description="Unique pattern identifier")
    pattern_type: str = Field(..., description="Type of semantic pattern")
    pattern_name: str = Field(..., description="Human-readable pattern name")

    # Pattern details
    description: str = Field(..., description="Pattern description")
    examples: List[str] = Field(default_factory=list, description="Example instances")
    frequency: int = Field(default=1, ge=1, description="Occurrence count")

    # Quality and confidence
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    significance_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Context and properties
    context: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)

    # Associated entities
    related_entity_ids: List[str] = Field(default_factory=list)


# Request models
class ExtractionOptions(BaseModel):
    """Configuration options for extraction"""

    # Processing mode
    mode: ExtractionMode = Field(default=ExtractionMode.STANDARD)

    # Language settings
    target_languages: List[LanguageCode] = Field(default=[LanguageCode.AUTO_DETECT])
    enable_multilingual: bool = Field(default=True)

    # Extraction features
    include_semantic_analysis: bool = Field(default=True)
    include_relationship_extraction: bool = Field(default=True)
    include_entity_linking: bool = Field(default=False)
    extract_code_patterns: bool = Field(default=True)
    extract_documentation_concepts: bool = Field(default=True)

    # Quality thresholds
    min_confidence_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    min_quality_threshold: float = Field(default=0.2, ge=0.0, le=1.0)

    # Schema hints
    schema_hints: Dict[str, Any] = Field(default_factory=dict)
    expected_entity_types: List[EntityType] = Field(default_factory=list)

    # Semantic context
    semantic_context: Optional[str] = Field(
        None, description="Context for semantic analysis"
    )
    domain_specific_terms: List[str] = Field(default_factory=list)

    # Performance settings
    max_entities_per_type: Optional[int] = Field(None, ge=1)
    enable_caching: bool = Field(default=True)
    timeout_seconds: Optional[int] = Field(default=300, ge=1)


class DocumentExtractionRequest(BaseModel):
    """Request for extracting from a single document"""

    document_path: str = Field(..., description="Path to document for extraction")
    content: Optional[str] = Field(
        None, description="Inline content (if not reading from file)"
    )
    extraction_options: ExtractionOptions = Field(default_factory=ExtractionOptions)

    # Integration options
    update_knowledge_graph: bool = Field(default=True)
    emit_events: bool = Field(default=True)

    # Processing hints
    document_type: Optional[str] = Field(None, description="Expected document type")
    encoding: str = Field(default="utf-8")

    # Correlation
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")


class BatchExtractionRequest(BaseModel):
    """Request for batch extraction from multiple documents"""

    document_paths: List[str] = Field(
        ..., min_items=1, description="List of document paths"
    )
    extraction_options: ExtractionOptions = Field(default_factory=ExtractionOptions)

    # Batch processing options
    max_concurrent_extractions: int = Field(default=5, ge=1, le=20)
    continue_on_error: bool = Field(default=True)

    # Integration options
    update_knowledge_graph: bool = Field(default=True)
    emit_events: bool = Field(default=True)

    # Correlation
    batch_id: Optional[str] = Field(None, description="Batch processing ID")


# Response models
class LanguageExtractionResult(BaseModel):
    """Results from language-aware extraction"""

    entities: List[EnhancedEntity] = Field(default_factory=list)
    language_detected: LanguageCode = Field(default=LanguageCode.ENGLISH)
    confidence_score: float = Field(..., ge=0.0, le=1.0)

    # Language-specific metrics
    language_confidence: float = Field(..., ge=0.0, le=1.0)
    multilingual_detected: bool = Field(default=False)
    primary_language: LanguageCode = Field(default=LanguageCode.ENGLISH)
    secondary_languages: List[LanguageCode] = Field(default_factory=list)

    # Processing statistics
    processing_time_ms: float = Field(..., ge=0.0)
    total_tokens: Optional[int] = Field(None, ge=0)


class StructuredDataResult(BaseModel):
    """Results from structured data extraction"""

    structured_entities: List[EnhancedEntity] = Field(default_factory=list)
    data_schemas: List[Dict[str, Any]] = Field(default_factory=list)

    # Data quality metrics
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    consistency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    validity_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Schema information
    detected_formats: List[str] = Field(default_factory=list)
    schema_compliance: Dict[str, float] = Field(default_factory=dict)


class SemanticAnalysisResult(BaseModel):
    """Results from semantic analysis"""

    semantic_patterns: List[SemanticPattern] = Field(default_factory=list)
    concepts: List[str] = Field(default_factory=list)
    themes: List[str] = Field(default_factory=list)

    # Semantic metrics
    semantic_density: float = Field(default=0.0, ge=0.0, le=1.0)
    conceptual_coherence: float = Field(default=0.0, ge=0.0, le=1.0)
    thematic_consistency: float = Field(default=0.0, ge=0.0, le=1.0)

    # Semantic context
    semantic_context: Dict[str, Any] = Field(default_factory=dict)
    domain_indicators: List[str] = Field(default_factory=list)

    # Topic analysis
    primary_topics: List[str] = Field(default_factory=list)
    topic_weights: Dict[str, float] = Field(default_factory=dict)


class DocumentAnalysisResult(BaseModel):
    """Results from comprehensive document analysis"""

    # Document characteristics
    document_type: str = Field(..., description="Identified document type")
    structure_analysis: Dict[str, Any] = Field(default_factory=dict)
    content_summary: str = Field(default="")

    # Quality metrics
    readability_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    complexity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    information_density: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Content analysis
    key_concepts: List[str] = Field(default_factory=list)
    main_topics: List[str] = Field(default_factory=list)
    sentiment_analysis: Optional[Dict[str, Any]] = Field(None)

    # Structural elements
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    hierarchical_structure: Dict[str, Any] = Field(default_factory=dict)


class ExtractionStatistics(BaseModel):
    """Statistics for extraction operation"""

    total_entities: int = Field(default=0, ge=0)
    total_relationships: int = Field(default=0, ge=0)
    total_patterns: int = Field(default=0, ge=0)

    # Performance metrics
    extraction_time_seconds: float = Field(..., ge=0.0)
    processing_rate_entities_per_second: Optional[float] = Field(None, ge=0.0)

    # Quality metrics
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    average_entity_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    average_relationship_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Distribution statistics
    entity_type_distribution: Dict[str, int] = Field(default_factory=dict)
    relationship_type_distribution: Dict[str, int] = Field(default_factory=dict)
    confidence_distribution: Dict[str, int] = Field(default_factory=dict)


class ExtractionResponse(BaseModel):
    """Comprehensive response from extraction operation"""

    # Identification
    extraction_id: str = Field(..., description="Unique extraction identifier")
    document_path: str = Field(..., description="Source document path")

    # Results
    language_results: LanguageExtractionResult = Field(...)
    structured_results: StructuredDataResult = Field(...)
    semantic_results: SemanticAnalysisResult = Field(...)
    analysis_result: DocumentAnalysisResult = Field(...)

    # Enhanced entities and relationships
    enriched_entities: List[EnhancedEntity] = Field(default_factory=list)
    relationships: List[EnhancedRelationship] = Field(default_factory=list)

    # Statistics and metadata
    extraction_statistics: ExtractionStatistics = Field(...)

    # Status and timing
    status: str = Field(default="completed")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Optional fields
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class HealthStatus(BaseModel):
    """Service health status"""

    status: str = Field(..., description="Overall service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="1.0.0")

    # Component health
    components: Dict[str, str] = Field(default_factory=dict)

    # Performance metrics
    uptime_seconds: Optional[float] = Field(None, ge=0.0)
    memory_usage_mb: Optional[float] = Field(None, ge=0.0)
    cpu_usage_percent: Optional[float] = Field(None, ge=0.0, le=100.0)

    # Error information
    error: Optional[str] = Field(None)
    warnings: List[str] = Field(default_factory=list)


# Utility models for specific operations
class EntityLinkingRequest(BaseModel):
    """Request for entity linking operation"""

    entities: List[EnhancedEntity] = Field(...)
    knowledge_base: Optional[str] = Field(None, description="Target knowledge base")
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class SemanticEnrichmentRequest(BaseModel):
    """Request for semantic enrichment of entities"""

    entities: List[EnhancedEntity] = Field(...)
    enrichment_options: Dict[str, Any] = Field(default_factory=dict)
    include_embeddings: bool = Field(default=True)
    include_concept_linking: bool = Field(default=True)


class KnowledgeGraphUpdateRequest(BaseModel):
    """Request for updating knowledge graph"""

    entities: List[EnhancedEntity] = Field(...)
    relationships: List[EnhancedRelationship] = Field(...)
    update_mode: str = Field(
        default="upsert", description="Update mode: upsert, replace, append"
    )
    validate_before_update: bool = Field(default=True)
