#!/usr/bin/env python3
"""
Task Characteristics Model - ONEX Compliant

Defines the comprehensive structure for task characteristics used in
the autonomous agent system for pattern matching and agent selection.

Part of Track 4 Autonomous System (Pattern Learning Engine).

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Enums for Task Classification
# ============================================================================


class EnumTaskType(str, Enum):
    """Task type classification."""

    CODE_GENERATION = "code_generation"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ANALYSIS = "analysis"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    SECURITY = "security"
    INTEGRATION = "integration"
    DEPLOYMENT = "deployment"
    RESEARCH = "research"
    UNKNOWN = "unknown"


class EnumComplexity(str, Enum):
    """Task complexity classification."""

    TRIVIAL = "trivial"  # < 1 hour, single file
    SIMPLE = "simple"  # 1-4 hours, 1-3 files
    MODERATE = "moderate"  # 4-16 hours, 3-10 files
    COMPLEX = "complex"  # 16-40 hours, 10-25 files
    VERY_COMPLEX = "very_complex"  # > 40 hours, > 25 files


class EnumChangeScope(str, Enum):
    """Scope of changes required."""

    SINGLE_FUNCTION = "single_function"
    SINGLE_FILE = "single_file"
    MULTIPLE_FILES = "multiple_files"
    SINGLE_MODULE = "single_module"
    MULTIPLE_MODULES = "multiple_modules"
    CROSS_SERVICE = "cross_service"
    SYSTEM_WIDE = "system_wide"


# ============================================================================
# Task Characteristics Model
# ============================================================================


class ModelTaskCharacteristics(BaseModel):
    """
    Comprehensive task characteristics for autonomous agent selection.

    This model captures all relevant features of a task that influence
    which agent should handle it and what strategies should be used.

    Used for:
    - Pattern matching with historical task executions
    - Agent capability alignment
    - Complexity estimation
    - Resource allocation
    - Embedding generation for similarity search
    """

    # Core identification
    task_id: UUID = Field(description="Unique task identifier")
    correlation_id: UUID = Field(
        default_factory=uuid4, description="Correlation ID for tracking"
    )
    extracted_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When characteristics were extracted",
    )

    # Task classification
    task_type: EnumTaskType = Field(
        default=EnumTaskType.UNKNOWN, description="Primary task type classification"
    )
    complexity: EnumComplexity = Field(
        default=EnumComplexity.MODERATE, description="Task complexity level"
    )
    change_scope: EnumChangeScope = Field(
        default=EnumChangeScope.MULTIPLE_FILES,
        description="Scope of changes required",
    )

    # Context availability flags
    has_sources: bool = Field(
        default=False, description="Whether task includes source references"
    )
    has_code_examples: bool = Field(
        default=False, description="Whether task includes code examples"
    )
    has_acceptance_criteria: bool = Field(
        default=False, description="Whether task has explicit acceptance criteria"
    )

    # Dependency information
    dependency_chain_length: int = Field(
        default=0, description="Length of parent task dependency chain"
    )
    parent_task_type: Optional[EnumTaskType] = Field(
        default=None, description="Type of parent task if exists"
    )
    is_subtask: bool = Field(
        default=False, description="Whether this is a subtask of another task"
    )

    # Impact estimation
    affected_file_patterns: List[str] = Field(
        default_factory=list,
        description="File patterns likely to be affected (e.g., ['*.py', 'tests/*'])",
    )
    estimated_files_affected: int = Field(
        default=0, description="Estimated number of files to be modified"
    )
    affected_components: List[str] = Field(
        default_factory=list,
        description="Components/modules likely affected (e.g., ['auth', 'api'])",
    )

    # Pattern matching features
    similar_task_count: int = Field(
        default=0, description="Count of similar tasks in history"
    )
    feature_label: Optional[str] = Field(
        default=None, description="Feature area label (e.g., 'authentication')"
    )

    # Resource estimation
    estimated_tokens: int = Field(
        default=0,
        description="Estimated token count for task completion (context + generation)",
    )

    # Rich text features for embedding
    title_normalized: str = Field(
        default="", description="Normalized task title for embedding"
    )
    description_normalized: str = Field(
        default="", description="Normalized task description for embedding"
    )
    keywords: List[str] = Field(
        default_factory=list, description="Extracted keywords for semantic matching"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional extraction metadata"
    )

    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={UUID: str, datetime: lambda v: v.isoformat()},
        json_schema_extra={
            "example": {
                "task_id": "9adc6257-10d5-4653-9956-f90633dacd0f",
                "task_type": "code_generation",
                "complexity": "moderate",
                "change_scope": "multiple_files",
                "has_sources": True,
                "has_code_examples": True,
                "has_acceptance_criteria": True,
                "dependency_chain_length": 0,
                "estimated_files_affected": 5,
                "affected_components": ["pattern_learning", "intelligence"],
                "feature_label": "autonomous_system",
                "estimated_tokens": 8000,
                "keywords": [
                    "schema",
                    "task",
                    "characteristics",
                    "extraction",
                    "autonomous",
                ],
            }
        },
    )

    def to_embedding_text(self) -> str:
        """
        Generate text representation for embedding generation.

        Combines key textual features in a format optimized for
        semantic similarity matching.

        Returns:
            Formatted string for embedding generation
        """
        # Handle both enum and string values (due to use_enum_values=True)
        task_type_val = (
            self.task_type.value if hasattr(self.task_type, "value") else self.task_type
        )
        complexity_val = (
            self.complexity.value
            if hasattr(self.complexity, "value")
            else self.complexity
        )
        scope_val = (
            self.change_scope.value
            if hasattr(self.change_scope, "value")
            else self.change_scope
        )

        parts = [
            f"Task Type: {task_type_val}",
            f"Complexity: {complexity_val}",
            f"Scope: {scope_val}",
            f"Title: {self.title_normalized}",
            f"Description: {self.description_normalized}",
        ]

        if self.keywords:
            parts.append(f"Keywords: {', '.join(self.keywords)}")

        if self.affected_components:
            parts.append(f"Components: {', '.join(self.affected_components)}")

        if self.feature_label:
            parts.append(f"Feature: {self.feature_label}")

        return " | ".join(parts)

    def to_feature_vector(self) -> Dict[str, Any]:
        """
        Generate feature vector for ML-based matching.

        Returns structured features suitable for similarity calculations
        and pattern matching algorithms.

        Returns:
            Dictionary of numerical and categorical features
        """
        # Handle both enum and string values (due to use_enum_values=True)
        task_type_val = (
            self.task_type.value if hasattr(self.task_type, "value") else self.task_type
        )
        complexity_val = (
            self.complexity.value
            if hasattr(self.complexity, "value")
            else self.complexity
        )
        scope_val = (
            self.change_scope.value
            if hasattr(self.change_scope, "value")
            else self.change_scope
        )

        return {
            # Categorical features
            "task_type": task_type_val,
            "complexity": complexity_val,
            "change_scope": scope_val,
            # Boolean features
            "has_sources": int(self.has_sources),
            "has_code_examples": int(self.has_code_examples),
            "has_acceptance_criteria": int(self.has_acceptance_criteria),
            "is_subtask": int(self.is_subtask),
            # Numerical features
            "dependency_chain_length": self.dependency_chain_length,
            "estimated_files_affected": self.estimated_files_affected,
            "estimated_tokens": self.estimated_tokens,
            "affected_component_count": len(self.affected_components),
            "keyword_count": len(self.keywords),
            # Feature label (for grouping)
            "feature_label": self.feature_label or "none",
        }


# ============================================================================
# Input/Output Models for Extraction
# ============================================================================


class ModelTaskCharacteristicsInput(BaseModel):
    """Input for task characteristics extraction."""

    task_id: UUID = Field(description="Task identifier")
    title: str = Field(description="Task title")
    description: str = Field(description="Task description")
    assignee: Optional[str] = Field(default=None, description="Assigned agent/user")
    feature: Optional[str] = Field(default=None, description="Feature label")
    parent_task_id: Optional[UUID] = Field(
        default=None, description="Parent task ID if subtask"
    )
    sources: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Source references"
    )
    code_examples: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Code examples"
    )
    correlation_id: UUID = Field(
        default_factory=uuid4, description="Correlation ID for tracing"
    )


class ModelTaskCharacteristicsOutput(BaseModel):
    """Output from task characteristics extraction."""

    characteristics: ModelTaskCharacteristics = Field(
        description="Extracted task characteristics"
    )
    confidence: float = Field(
        description="Extraction confidence (0.0-1.0)", ge=0.0, le=1.0
    )
    processing_time_ms: float = Field(description="Extraction processing time in ms")
    correlation_id: UUID = Field(description="Correlation ID for tracing")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
