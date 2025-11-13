"""
Extracted Pattern Model

Data model for patterns extracted from successful code validations.
Represents patterns discovered through autonomous learning.

Created: 2025-10-15 (MVP Phase 5A)
Purpose: Type-safe representation of discovered patterns
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class PatternCategory(str, Enum):
    """Categories of extracted patterns."""

    ARCHITECTURAL = "architectural"
    QUALITY = "quality"
    SECURITY = "security"
    ONEX = "onex"


class ExtractedPattern(BaseModel):
    """
    Represents a pattern extracted from successful code validation.

    Patterns are discovered by analyzing code that passes ONEX compliance
    and quality validation. These patterns feed back into the pattern
    learning system to improve future recommendations.

    Attributes:
        pattern_id: Unique identifier for the pattern
        pattern_category: Category of pattern (architectural, quality, security, onex)
        pattern_type: Specific pattern type within category
        code_snippet: Representative code snippet demonstrating the pattern
        context: Contextual information about where/how pattern was found
        frequency: Number of times this pattern has been observed
        confidence: Confidence score for pattern effectiveness (0.0-1.0)
        metadata: Additional pattern-specific metadata
        created_at: When pattern was first discovered
        last_seen_at: When pattern was most recently observed
    """

    # Identification
    pattern_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique pattern identifier"
    )

    pattern_category: PatternCategory = Field(
        ..., description="High-level pattern category"
    )

    pattern_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Specific pattern type (e.g., 'base_class_inheritance', 'error_handling')",
    )

    # Pattern content
    code_snippet: str = Field(
        ..., min_length=1, description="Representative code snippet showing the pattern"
    )

    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Contextual information (node_type, file_path, surrounding code)",
    )

    # Pattern metrics
    frequency: int = Field(
        default=1, ge=1, description="Number of times pattern has been observed"
    )

    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score for pattern effectiveness (0.0-1.0)",
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional pattern-specific metadata (category details, AST info)",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When pattern was first discovered (UTC)",
    )

    last_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When pattern was most recently observed (UTC)",
    )

    # Validation outcome tracking
    validation_success_count: int = Field(
        default=0,
        ge=0,
        description="Number of times code using this pattern passed validation",
    )

    validation_failure_count: int = Field(
        default=0,
        ge=0,
        description="Number of times code using this pattern failed validation",
    )

    def increment_frequency(self) -> None:
        """
        Increment pattern frequency and update last_seen_at timestamp.

        Should be called whenever this pattern is observed again.
        """
        self.frequency += 1
        self.last_seen_at = datetime.now(timezone.utc)

    def update_confidence(self, validation_success: bool) -> None:
        """
        Update pattern confidence based on validation outcome.

        Uses running average calculation weighted by frequency.

        Args:
            validation_success: True if validation passed, False otherwise
        """
        if validation_success:
            self.validation_success_count += 1
        else:
            self.validation_failure_count += 1

        total_validations = (
            self.validation_success_count + self.validation_failure_count
        )
        if total_validations > 0:
            # Calculate success rate
            success_rate = self.validation_success_count / total_validations

            # Weight by frequency - patterns seen more often have higher base confidence
            frequency_factor = min(1.0, self.frequency / 10.0)  # Cap at 10 observations

            # Combined confidence: 70% success rate, 30% frequency
            self.confidence = (success_rate * 0.7) + (frequency_factor * 0.3)

    def to_storage_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary suitable for PostgreSQL storage.

        Returns:
            Dictionary with all fields serialized for database storage
        """
        return {
            "pattern_id": self.pattern_id,
            "pattern_category": self.pattern_category.value,
            "pattern_type": self.pattern_type,
            "code_snippet": self.code_snippet,
            "context": self.context,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
            "validation_success_count": self.validation_success_count,
            "validation_failure_count": self.validation_failure_count,
        }

    def to_qdrant_payload(self) -> Dict[str, Any]:
        """
        Generate Qdrant payload metadata for semantic search.

        Returns:
            Dictionary with Qdrant-compatible metadata fields
        """
        return {
            "pattern_id": self.pattern_id,
            "pattern_category": self.pattern_category.value,
            "pattern_type": self.pattern_type,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "validation_success_rate": (
                self.validation_success_count
                / (self.validation_success_count + self.validation_failure_count)
                if (self.validation_success_count + self.validation_failure_count) > 0
                else 0.0
            ),
            "node_type": self.context.get("node_type"),
            "created_at": int(self.created_at.timestamp()),
            "last_seen_at": int(self.last_seen_at.timestamp()),
        }

    model_config = ConfigDict(
        use_enum_values=False,
        json_schema_extra={
            "example": {
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_category": "architectural",
                "pattern_type": "base_class_inheritance",
                "code_snippet": "class NodeDatabaseWriterEffect(NodeBase)",
                "context": {
                    "node_type": "effect",
                    "bases": ["NodeBase"],
                    "file_path": "node_database_writer_effect.py",
                },
                "frequency": 5,
                "confidence": 0.85,
                "metadata": {"category": "inheritance", "ast_node_type": "ClassDef"},
                "created_at": "2025-10-15T12:00:00Z",
                "last_seen_at": "2025-10-15T14:30:00Z",
                "validation_success_count": 8,
                "validation_failure_count": 2,
            }
        },
    )
