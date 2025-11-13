"""
Semantic Analysis Response Models

Models for langextract service semantic analysis responses.
These models represent the structured data returned from the langextract service.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


# NOTE: correlation_id support enabled for tracing
class SemanticConcept(BaseModel):
    """
    Individual semantic concept extracted from text.

    Attributes:
        concept: The concept name or identifier
        score: Confidence score (0.0-1.0)
        context: Optional context or category for the concept
    """

    concept: str = Field(..., min_length=1, description="Concept name or identifier")
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    context: Optional[str] = Field(default=None, description="Context or category")


class SemanticTheme(BaseModel):
    """
    High-level theme identified in the text.

    Attributes:
        theme: Theme name or identifier
        weight: Importance weight (0.0-1.0)
        related_concepts: List of related concept names
    """

    theme: str = Field(..., min_length=1, description="Theme name or identifier")
    weight: float = Field(
        ..., ge=0.0, le=1.0, description="Importance weight (0.0-1.0)"
    )
    related_concepts: List[str] = Field(
        default_factory=list, description="Related concepts"
    )


class SemanticDomain(BaseModel):
    """
    Domain classification for the analyzed text.

    Attributes:
        domain: Domain name (e.g., 'debugging', 'api_design', 'performance')
        confidence: Confidence score (0.0-1.0)
        subdomain: Optional subdomain classification
    """

    domain: str = Field(..., min_length=1, description="Domain name")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)"
    )
    subdomain: Optional[str] = Field(
        default=None, description="Subdomain classification"
    )


class SemanticPattern(BaseModel):
    """
    Semantic pattern identified in the text.

    Attributes:
        pattern_type: Type of pattern (e.g., 'workflow', 'anti-pattern', 'best-practice')
        description: Pattern description
        strength: Pattern strength score (0.0-1.0)
        indicators: List of text indicators that suggest this pattern
    """

    pattern_type: str = Field(..., min_length=1, description="Type of pattern")
    description: str = Field(..., description="Pattern description")
    strength: float = Field(
        ..., ge=0.0, le=1.0, description="Pattern strength (0.0-1.0)"
    )
    indicators: List[str] = Field(default_factory=list, description="Text indicators")


class SemanticAnalysisResult(BaseModel):
    """
    Complete semantic analysis result from langextract service.

    This is the top-level response model returned by the langextract HTTP client.

    Attributes:
        concepts: List of extracted semantic concepts
        themes: List of identified high-level themes
        domains: List of domain classifications
        patterns: List of identified semantic patterns
        language: Detected or specified language code
        processing_time_ms: Time taken for analysis (milliseconds)
        metadata: Additional metadata from the analysis
    """

    concepts: List[SemanticConcept] = Field(
        default_factory=list, description="Extracted semantic concepts"
    )
    themes: List[SemanticTheme] = Field(
        default_factory=list, description="Identified high-level themes"
    )
    domains: List[SemanticDomain] = Field(
        default_factory=list, description="Domain classifications"
    )
    patterns: List[SemanticPattern] = Field(
        default_factory=list, description="Identified semantic patterns"
    )
    language: str = Field(default="en", description="Language code")
    processing_time_ms: Optional[float] = Field(
        default=None, description="Processing time in milliseconds"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional analysis metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "concepts": [
                    {"concept": "authentication", "score": 0.92, "context": "security"},
                    {"concept": "api_endpoint", "score": 0.87, "context": "api_design"},
                ],
                "themes": [
                    {
                        "theme": "api_security",
                        "weight": 0.85,
                        "related_concepts": ["authentication", "authorization"],
                    }
                ],
                "domains": [
                    {
                        "domain": "api_design",
                        "confidence": 0.91,
                        "subdomain": "security",
                    }
                ],
                "patterns": [
                    {
                        "pattern_type": "best-practice",
                        "description": "JWT-based authentication pattern",
                        "strength": 0.88,
                        "indicators": ["token", "bearer", "jwt"],
                    }
                ],
                "language": "en",
                "processing_time_ms": 245.3,
                "metadata": {"model_version": "1.0.0", "confidence_threshold": 0.7},
            }
        }
    )


class SemanticAnalysisRequest(BaseModel):
    """
    Request model for semantic analysis.

    Attributes:
        content: Text content to analyze
        context: Optional context to guide the analysis
        language: Language code (default: 'en')
        min_confidence: Minimum confidence threshold for results (0.0-1.0)
    """

    content: str = Field(..., min_length=1, description="Text content to analyze")
    context: Optional[str] = Field(default=None, description="Analysis context")
    language: str = Field(default="en", description="Language code")
    min_confidence: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "Implement JWT authentication for REST API endpoints",
                "context": "api_development",
                "language": "en",
                "min_confidence": 0.7,
            }
        }
    )
