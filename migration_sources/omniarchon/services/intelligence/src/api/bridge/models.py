"""
Bridge Intelligence Generation API Models

Request/response models for generating OmniNode Tool Metadata Standard v0.1
compliant metadata enriched with Archon intelligence.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# NOTE: correlation_id support enabled for tracing
class BridgeIntelligenceRequest(BaseModel):
    """
    Request for generating OmniNode protocol-compliant metadata with Archon intelligence.

    Attributes:
        file_path: Full path to the file to analyze
        content: Optional file content (if not provided, will attempt to read from file_path)
        include_patterns: Include pattern tracking data enrichment
        include_compliance: Include ONEX architectural compliance analysis
        include_semantic: Include LangExtract semantic analysis
        min_confidence: Minimum confidence threshold for semantic analysis (0.0-1.0)
    """

    file_path: str = Field(..., description="Full path to file")
    content: Optional[str] = Field(default=None, description="File content (optional)")
    include_patterns: bool = Field(
        default=True, description="Include pattern tracking intelligence"
    )
    include_compliance: bool = Field(
        default=True, description="Include ONEX compliance analysis"
    )
    include_semantic: bool = Field(
        default=True, description="Include semantic analysis"
    )
    min_confidence: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Min confidence for semantic results"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "/path/to/file.py",
                "content": "def example():\n    pass",
                "include_patterns": True,
                "include_compliance": True,
                "include_semantic": True,
                "min_confidence": 0.7,
            }
        }
    )


class QualityMetrics(BaseModel):
    """Quality metrics from Archon intelligence"""

    quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall quality score (0-1)"
    )
    onex_compliance: float = Field(
        ..., ge=0.0, le=1.0, description="ONEX compliance score (0-1)"
    )
    complexity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Complexity score (0-1)"
    )
    maintainability_score: float = Field(
        ..., ge=0.0, le=1.0, description="Maintainability score (0-1)"
    )
    documentation_score: float = Field(
        ..., ge=0.0, le=1.0, description="Documentation score (0-1)"
    )
    temporal_relevance: float = Field(
        ..., ge=0.0, le=1.0, description="Temporal relevance score (0-1)"
    )


class SemanticIntelligence(BaseModel):
    """Semantic intelligence from LangExtract"""

    concepts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Extracted semantic concepts"
    )
    themes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Identified high-level themes"
    )
    domains: List[Dict[str, Any]] = Field(
        default_factory=list, description="Domain classifications"
    )
    patterns: List[Dict[str, Any]] = Field(
        default_factory=list, description="Semantic patterns"
    )
    processing_time_ms: Optional[float] = Field(
        default=None, description="LangExtract processing time"
    )


class PatternIntelligence(BaseModel):
    """Pattern tracking intelligence from Archon database"""

    pattern_count: int = Field(
        default=0, description="Number of patterns tracked for this file"
    )
    total_executions: int = Field(default=0, description="Total pattern usage count")
    avg_quality_score: Optional[float] = Field(
        default=None, description="Average pattern quality"
    )
    last_modified: Optional[str] = Field(
        default=None, description="Last pattern modification timestamp"
    )
    pattern_types: List[str] = Field(
        default_factory=list, description="Types of patterns tracked"
    )


class OmniNodeMetadataClassification(BaseModel):
    """OmniNode protocol classification fields"""

    maturity: str = Field(
        ..., description="Maturity level: alpha, beta, stable, production"
    )
    trust_score: int = Field(..., ge=0, le=100, description="Trust score (0-100)")


class OmniNodeToolMetadata(BaseModel):
    """
    OmniNode Tool Metadata Standard v0.1 compliant metadata structure.

    Enriched with Archon intelligence including quality metrics, semantic analysis,
    and pattern tracking data.
    """

    # Required fields per OmniNode spec
    metadata_version: str = Field(default="0.1", description="Metadata version")
    name: str = Field(..., description="Tool/component name")
    namespace: str = Field(
        ..., description="Namespace (e.g., omninode.archon.intelligence)"
    )
    version: str = Field(default="1.0.0", description="Version (semantic versioning)")
    entrypoint: str = Field(..., description="Entry point file path")
    protocols_supported: List[str] = Field(
        default=["O.N.E. v0.1"], description="Supported protocols"
    )

    # Classification (Archon-enriched)
    classification: OmniNodeMetadataClassification = Field(
        ..., description="Classification with Archon trust_score"
    )

    # Archon Intelligence Extensions
    quality_metrics: QualityMetrics = Field(
        ..., description="Archon quality assessment"
    )
    semantic_intelligence: Optional[SemanticIntelligence] = Field(
        default=None, description="LangExtract semantic analysis"
    )
    pattern_intelligence: Optional[PatternIntelligence] = Field(
        default=None, description="Pattern tracking intelligence"
    )

    # Optional standard fields
    title: Optional[str] = Field(default=None, description="Human-readable title")
    description: Optional[str] = Field(default=None, description="Description")
    type: Optional[str] = Field(
        default="component", description="Type: agent, tool, component"
    )
    language: Optional[str] = Field(
        default="python", description="Programming language"
    )
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    author: Optional[str] = Field(default="Archon Intelligence", description="Author")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metadata_version": "0.1",
                "name": "example_module",
                "namespace": "omninode.archon.intelligence",
                "version": "1.0.0",
                "entrypoint": "/path/to/file.py",
                "protocols_supported": ["O.N.E. v0.1"],
                "classification": {"maturity": "beta", "trust_score": 87},
                "quality_metrics": {
                    "quality_score": 0.87,
                    "onex_compliance": 0.92,
                    "complexity_score": 0.75,
                    "maintainability_score": 0.85,
                    "documentation_score": 0.80,
                    "temporal_relevance": 0.90,
                },
            }
        }
    )


class BridgeIntelligenceResponse(BaseModel):
    """
    Response containing OmniNode protocol-compliant metadata enriched with Archon intelligence.

    Attributes:
        success: Whether the operation succeeded
        metadata: OmniNode Tool Metadata Standard v0.1 compliant metadata
        processing_metadata: Processing information and performance metrics
        intelligence_sources: List of intelligence sources used
        recommendations: Optional recommendations for improvement
        error: Optional error message if success=False
    """

    success: bool = Field(..., description="Operation success status")
    metadata: Optional[OmniNodeToolMetadata] = Field(
        default=None, description="Generated OmniNode metadata"
    )
    processing_metadata: Dict[str, Any] = Field(
        ..., description="Processing information"
    )
    intelligence_sources: List[str] = Field(
        ..., description="Intelligence sources used"
    )
    recommendations: Optional[List[str]] = Field(
        default=None, description="Improvement recommendations"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if success=False"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "metadata": {
                    "metadata_version": "0.1",
                    "name": "example_module",
                    "namespace": "omninode.archon.intelligence",
                    "version": "1.0.0",
                    "entrypoint": "/path/to/file.py",
                    "protocols_supported": ["O.N.E. v0.1"],
                    "classification": {"maturity": "beta", "trust_score": 87},
                    "quality_metrics": {
                        "quality_score": 0.87,
                        "onex_compliance": 0.92,
                        "complexity_score": 0.75,
                        "maintainability_score": 0.85,
                        "documentation_score": 0.80,
                        "temporal_relevance": 0.90,
                    },
                },
                "processing_metadata": {
                    "processing_time_ms": 1200,
                    "timestamp": "2025-10-06T12:00:00Z",
                    "file_size_bytes": 1024,
                },
                "intelligence_sources": [
                    "langextract",
                    "quality_scorer",
                    "pattern_tracking",
                ],
                "recommendations": [
                    "Consider adding more documentation",
                    "Reduce cyclomatic complexity in main function",
                ],
            }
        }
    )
