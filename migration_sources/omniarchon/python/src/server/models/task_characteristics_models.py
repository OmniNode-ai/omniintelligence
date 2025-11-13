"""
Task Characteristics Models for Track 3 (Pattern Matching) and Track 4 (Autonomous Execution)

This module defines the comprehensive TaskCharacteristics schema that supports:
1. Semantic similarity matching for finding similar historical tasks
2. Autonomous task execution planning and resource allocation
3. Context extraction from Archon task structures
4. Embedding generation for vector similarity search

Design Principles:
- All characteristics are designed to be extractable from Archon task objects
- Fields are optimized for both structured filtering and semantic embedding
- Validation ensures data quality and consistency
- Extensible for future intelligence enhancements
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, validator

# ============================================================================
# ENUMERATIONS - Categorical Types for Structured Filtering
# ============================================================================


class TaskType(str, Enum):
    """
    Primary task types based on development activities.
    Used for initial task categorization and pattern matching.
    """

    # Code Development
    FEATURE_IMPLEMENTATION = "feature_implementation"  # New feature development
    BUG_FIX = "bug_fix"  # Bug resolution
    REFACTORING = "refactoring"  # Code restructuring
    PERFORMANCE_OPTIMIZATION = (
        "performance_optimization"  # Speed/efficiency improvements
    )
    TECHNICAL_DEBT = "technical_debt"  # Debt reduction

    # Testing
    TEST_WRITING = "test_writing"  # Unit/integration test creation
    TEST_DEBUGGING = "test_debugging"  # Test failure investigation
    TEST_COVERAGE_IMPROVEMENT = "test_coverage_improvement"  # Coverage expansion

    # Documentation
    DOCUMENTATION_CREATION = "documentation_creation"  # New documentation
    DOCUMENTATION_UPDATE = "documentation_update"  # Existing docs update
    API_DOCUMENTATION = "api_documentation"  # API-specific docs

    # Infrastructure
    INFRASTRUCTURE_SETUP = "infrastructure_setup"  # Infra configuration
    DEPLOYMENT = "deployment"  # Deployment tasks
    DEVOPS_AUTOMATION = "devops_automation"  # CI/CD automation

    # Architecture
    ARCHITECTURE_DESIGN = "architecture_design"  # System design
    API_DESIGN = "api_design"  # API specification
    DATABASE_DESIGN = "database_design"  # Schema design

    # Investigation
    DEBUG_INVESTIGATION = "debug_investigation"  # Root cause analysis
    RESEARCH = "research"  # Technology research
    PROOF_OF_CONCEPT = "proof_of_concept"  # POC development

    # Project Management
    PLANNING = "planning"  # Task planning
    CODE_REVIEW = "code_review"  # PR review
    SECURITY_AUDIT = "security_audit"  # Security review

    # Unknown/Other
    UNKNOWN = "unknown"  # Could not determine type


class ComplexityLevel(str, Enum):
    """
    Discrete complexity levels for filtering.
    Complements the continuous complexity score.
    """

    TRIVIAL = "trivial"  # < 0.2: Simple, single-line changes
    SIMPLE = "simple"  # 0.2-0.4: Straightforward, well-defined
    MODERATE = "moderate"  # 0.4-0.6: Multiple files, some complexity
    COMPLEX = "complex"  # 0.6-0.8: Significant changes, dependencies
    VERY_COMPLEX = "very_complex"  # > 0.8: Major refactoring, architecture


class ChangeScope(str, Enum):
    """
    Scope of changes required for task completion.
    Critical for resource allocation and execution planning.
    """

    SINGLE_FILE = "single_file"  # Changes to one file
    MULTIPLE_FILES = "multiple_files"  # 2-5 files
    MODULE = "module"  # Single module/package
    CROSS_MODULE = "cross_module"  # Multiple modules
    CROSS_SERVICE = "cross_service"  # Multiple services
    REPOSITORY_WIDE = "repository_wide"  # Entire repository
    CROSS_REPOSITORY = "cross_repository"  # Multiple repositories


class Component(str, Enum):
    """
    System components that can be affected by tasks.
    Enables component-based filtering and coordination.
    """

    # Backend Components
    API_LAYER = "api_layer"
    BUSINESS_LOGIC = "business_logic"
    DATA_ACCESS = "data_access"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    BACKGROUND_JOBS = "background_jobs"
    EVENT_SYSTEM = "event_system"
    CACHING = "caching"

    # Frontend Components
    UI_COMPONENTS = "ui_components"
    STATE_MANAGEMENT = "state_management"
    ROUTING = "routing"
    FORMS = "forms"

    # Data Components
    DATABASE_SCHEMA = "database_schema"
    MIGRATIONS = "migrations"
    MODELS = "models"
    QUERIES = "queries"

    # Infrastructure Components
    CONTAINERIZATION = "containerization"
    ORCHESTRATION = "orchestration"
    MONITORING = "monitoring"
    LOGGING = "logging"
    CI_CD = "ci_cd"

    # Integration Components
    EXTERNAL_API = "external_api"
    WEBHOOKS = "webhooks"
    MESSAGE_QUEUE = "message_queue"
    FILE_STORAGE = "file_storage"

    # Documentation Components
    README = "readme"
    API_DOCS = "api_docs"
    INLINE_DOCUMENTATION = "inline_documentation"
    ARCHITECTURE_DOCS = "architecture_docs"

    # Testing Components
    UNIT_TESTS = "unit_tests"
    INTEGRATION_TESTS = "integration_tests"
    E2E_TESTS = "e2e_tests"
    FIXTURES = "fixtures"

    # Other
    CONFIGURATION = "configuration"
    DEPENDENCIES = "dependencies"
    UNKNOWN_COMPONENT = "unknown_component"


class ContextType(str, Enum):
    """
    Types of context information available for task execution.
    Used to assess task preparedness and execution feasibility.
    """

    DOCUMENTATION_REFERENCE = "documentation_reference"  # External docs
    CODE_EXAMPLE = "code_example"  # Reference implementations
    API_SPECIFICATION = "api_specification"  # API specs
    ACCEPTANCE_CRITERIA = "acceptance_criteria"  # Success criteria
    DESIGN_DOCUMENT = "design_document"  # Design docs
    RELATED_TASK = "related_task"  # Linked tasks
    PARENT_TASK = "parent_task"  # Parent context
    HISTORICAL_PATTERN = "historical_pattern"  # Similar past tasks
    ERROR_LOG = "error_log"  # Error traces
    PERFORMANCE_METRICS = "performance_metrics"  # Performance data


class ExecutionPattern(str, Enum):
    """
    Common execution patterns identified from historical tasks.
    Used for autonomous execution planning.
    """

    # Linear patterns
    SEQUENTIAL_IMPLEMENTATION = "sequential_implementation"  # Step-by-step
    TEST_DRIVEN_DEVELOPMENT = "test_driven_development"  # TDD approach
    REFACTOR_THEN_EXTEND = "refactor_then_extend"  # Refactor first

    # Iterative patterns
    SPIKE_THEN_IMPLEMENT = "spike_then_implement"  # Research then build
    PROTOTYPE_THEN_REFINE = "prototype_then_refine"  # Quick POC first
    INCREMENTAL_MIGRATION = "incremental_migration"  # Gradual migration

    # Investigative patterns
    DEBUG_ROOT_CAUSE = "debug_root_cause"  # Investigation-focused
    REPRODUCE_THEN_FIX = "reproduce_then_fix"  # Repro first
    ANALYZE_THEN_OPTIMIZE = "analyze_then_optimize"  # Measure first

    # Coordination patterns
    PARALLEL_DEVELOPMENT = "parallel_development"  # Concurrent work
    DEPENDENCY_FIRST = "dependency_first"  # Dependencies first
    INTEGRATION_LAST = "integration_last"  # Integration at end

    # Unknown
    UNKNOWN_PATTERN = "unknown_pattern"


# ============================================================================
# CORE MODELS - Task Characteristics Structure
# ============================================================================


class TaskMetadata(BaseModel):
    """
    Basic task metadata for identification and tracking.
    """

    task_id: str = Field(..., description="Unique task identifier (UUID)")
    project_id: str = Field(..., description="Project UUID")
    title: str = Field(..., description="Task title")
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    feature_label: Optional[str] = Field(
        None, description="Feature group label (e.g., 'authentication')"
    )


class TaskComplexityMetrics(BaseModel):
    """
    Multi-dimensional complexity assessment.
    Combines discrete levels with continuous metrics.
    """

    complexity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall complexity score (0.0-1.0)",
    )
    complexity_level: ComplexityLevel = Field(
        ..., description="Discrete complexity categorization"
    )
    estimated_tokens: Optional[int] = Field(
        None,
        description="Estimated token count for LLM processing",
    )
    estimated_files_affected: int = Field(
        0,
        ge=0,
        description="Estimated number of files to modify",
    )
    estimated_lines_changed: Optional[int] = Field(
        None,
        description="Estimated lines of code to change",
    )


class TaskContext(BaseModel):
    """
    Available context information for task execution.
    Critical for autonomous execution feasibility assessment.
    """

    has_sources: bool = Field(False, description="Has documentation/reference sources")
    has_code_examples: bool = Field(False, description="Has code examples")
    has_acceptance_criteria: bool = Field(
        False, description="Has explicit acceptance criteria"
    )
    has_parent_task: bool = Field(False, description="Has parent task context")
    has_related_tasks: bool = Field(False, description="Has related tasks")

    required_context_types: list[ContextType] = Field(
        default_factory=list,
        description="Types of context required for execution",
    )
    available_context_types: list[ContextType] = Field(
        default_factory=list,
        description="Types of context currently available",
    )
    context_completeness_score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Ratio of available/required context (0.0-1.0)",
    )


class TaskDependencies(BaseModel):
    """
    Task dependency information for execution ordering.
    """

    dependency_chain_length: int = Field(
        0,
        ge=0,
        description="Number of tasks in dependency chain",
    )
    parent_task_id: Optional[str] = Field(
        None, description="Parent task UUID if exists"
    )
    parent_task_type: Optional[TaskType] = Field(
        None, description="Type of parent task"
    )
    blocking_task_count: int = Field(
        0,
        ge=0,
        description="Number of tasks blocking this one",
    )
    dependent_task_count: int = Field(
        0,
        ge=0,
        description="Number of tasks depending on this one",
    )


class TaskFilePatterns(BaseModel):
    """
    File and directory patterns affected by the task.
    Used for scope assessment and coordination.
    """

    affected_file_patterns: list[str] = Field(
        default_factory=list,
        description="File glob patterns (e.g., 'src/api/**/*.py')",
    )
    affected_directories: list[str] = Field(
        default_factory=list,
        description="Directory paths affected",
    )
    primary_file_types: list[str] = Field(
        default_factory=list,
        description="Primary file extensions (e.g., ['.py', '.ts'])",
    )


class TaskHistoricalContext(BaseModel):
    """
    Historical pattern information for similarity matching.
    """

    similar_task_count: int = Field(
        0,
        ge=0,
        description="Number of similar tasks in history",
    )
    average_completion_time_hours: Optional[float] = Field(
        None,
        description="Average completion time for similar tasks",
    )
    success_rate: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Success rate for similar tasks (0.0-1.0)",
    )
    common_execution_pattern: Optional[ExecutionPattern] = Field(
        None,
        description="Most common execution pattern for similar tasks",
    )


class TaskCharacteristics(BaseModel):
    """
    Complete task characteristics schema for pattern matching and autonomous execution.

    This model is designed to support:
    1. Semantic similarity search via embedding generation
    2. Structured filtering via categorical fields
    3. Execution planning via context and complexity assessment
    4. Resource allocation via scope and dependency analysis

    Usage:
        # Extract from Archon task
        characteristics = TaskCharacteristics.from_archon_task(task_dict)

        # Generate embedding for similarity search
        embedding_text = characteristics.to_embedding_text()

        # Validate execution feasibility
        is_ready = characteristics.is_execution_ready()
    """

    # Core Identification
    metadata: TaskMetadata = Field(..., description="Task metadata")

    # Primary Categorization
    task_type: TaskType = Field(..., description="Primary task type")
    change_scope: ChangeScope = Field(..., description="Scope of changes")

    # Complexity Assessment
    complexity: TaskComplexityMetrics = Field(..., description="Complexity metrics")

    # Context Information
    context: TaskContext = Field(..., description="Available context")

    # Dependencies
    dependencies: TaskDependencies = Field(..., description="Dependency information")

    # File/Component Scope
    file_patterns: TaskFilePatterns = Field(..., description="File patterns affected")
    affected_components: list[Component] = Field(
        default_factory=list,
        description="System components affected",
    )

    # Historical Context
    historical: TaskHistoricalContext = Field(
        ..., description="Historical pattern information"
    )

    # Execution Planning
    suggested_execution_pattern: Optional[ExecutionPattern] = Field(
        None,
        description="Suggested execution pattern based on characteristics",
    )
    autonomous_execution_feasibility: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Feasibility score for autonomous execution (0.0-1.0)",
    )

    # Assignee Information
    assignee: str = Field("User", description="Task assignee")
    assignee_type: str = Field(
        "human",
        description="Assignee type: 'human', 'ai_agent', 'hybrid'",
    )

    # Raw Task Description (for embedding)
    description_text: str = Field(
        "", description="Full task description for semantic embedding"
    )

    # Extraction Metadata
    extracted_at: datetime = Field(
        default_factory=datetime.now,
        description="When characteristics were extracted",
    )
    extraction_version: str = Field(
        "1.0.0",
        description="Extraction logic version for schema evolution",
    )

    @validator("assignee_type", pre=True, always=True)
    def determine_assignee_type(cls, v, values):
        """Automatically determine assignee type from assignee field."""
        if v and v != "auto":
            return v

        assignee = values.get("assignee", "User")
        ai_assignees = ["Archon", "AI IDE Agent", "prp-executor", "prp-validator"]

        if assignee in ai_assignees or assignee.startswith("agent-"):
            return "ai_agent"
        elif assignee == "User":
            return "human"
        else:
            return "hybrid"

    @validator("autonomous_execution_feasibility", pre=True, always=True)
    def calculate_feasibility(cls, v, values):
        """Calculate autonomous execution feasibility score."""
        if v and v > 0:
            return v

        # Calculate based on multiple factors
        context = values.get("context")
        complexity = values.get("complexity")

        if not context or not complexity:
            return 0.0

        # Factors contributing to feasibility
        context_score = context.context_completeness_score
        complexity_penalty = 1.0 - complexity.complexity_score
        has_examples = 0.2 if context.has_code_examples else 0.0
        has_criteria = 0.2 if context.has_acceptance_criteria else 0.0

        # Weighted average
        feasibility = (
            context_score * 0.4 + complexity_penalty * 0.3 + has_examples + has_criteria
        )

        return min(1.0, max(0.0, feasibility))

    def to_embedding_text(self) -> str:
        """
        Generate optimized text for embedding generation.

        Combines task metadata, description, context, and characteristics
        into a coherent text that captures semantic meaning for similarity search.

        Returns:
            Formatted text string optimized for embedding models
        """
        parts = [
            f"Task Type: {self.task_type.value}",
            f"Title: {self.metadata.title}",
            f"Description: {self.description_text}",
            f"Scope: {self.change_scope.value}",
            f"Complexity: {self.complexity.complexity_level.value}",
        ]

        if self.affected_components:
            components = ", ".join([c.value for c in self.affected_components])
            parts.append(f"Components: {components}")

        if self.context.required_context_types:
            context_types = ", ".join(
                [ct.value for ct in self.context.required_context_types]
            )
            parts.append(f"Required Context: {context_types}")

        if self.metadata.feature_label:
            parts.append(f"Feature: {self.metadata.feature_label}")

        if self.suggested_execution_pattern:
            parts.append(f"Pattern: {self.suggested_execution_pattern.value}")

        return " | ".join(parts)

    def to_dict_for_filtering(self) -> dict[str, Any]:
        """
        Generate dictionary optimized for structured filtering.

        Returns categorical and numeric fields suitable for database queries
        and filtering operations.

        Returns:
            Dictionary with filter-friendly field values
        """
        return {
            "task_type": self.task_type.value,
            "change_scope": self.change_scope.value,
            "complexity_level": self.complexity.complexity_level.value,
            "complexity_score": self.complexity.complexity_score,
            "has_sources": self.context.has_sources,
            "has_code_examples": self.context.has_code_examples,
            "has_acceptance_criteria": self.context.has_acceptance_criteria,
            "context_completeness": self.context.context_completeness_score,
            "estimated_files": self.complexity.estimated_files_affected,
            "affected_components": [c.value for c in self.affected_components],
            "assignee_type": self.assignee_type,
            "autonomous_feasibility": self.autonomous_execution_feasibility,
            "feature_label": self.metadata.feature_label,
        }

    def is_execution_ready(self, min_feasibility: float = 0.6) -> bool:
        """
        Determine if task is ready for autonomous execution.

        Args:
            min_feasibility: Minimum feasibility threshold (default: 0.6)

        Returns:
            True if task meets execution readiness criteria
        """
        return (
            self.autonomous_execution_feasibility >= min_feasibility
            and self.context.context_completeness_score >= 0.7
            and self.complexity.complexity_score < 0.8
        )


# ============================================================================
# HELPER MODELS - Supporting Data Structures
# ============================================================================


class SimilarityMatch(BaseModel):
    """
    Represents a similarity match between tasks.
    Used in Track 3 for pattern matching results.
    """

    task_id: str = Field(..., description="Matched task ID")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score (0.0-1.0)",
    )
    matching_characteristics: list[str] = Field(
        default_factory=list,
        description="Characteristics that matched",
    )
    task_characteristics: TaskCharacteristics = Field(
        ..., description="Full characteristics of matched task"
    )


class TaskCharacteristicsQuery(BaseModel):
    """
    Query specification for finding similar tasks.
    """

    target_characteristics: TaskCharacteristics = Field(
        ..., description="Characteristics to match against"
    )
    min_similarity_threshold: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold",
    )
    max_results: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum number of results",
    )
    filter_by_task_type: Optional[list[TaskType]] = Field(
        None,
        description="Filter by specific task types",
    )
    filter_by_component: Optional[list[Component]] = Field(
        None,
        description="Filter by affected components",
    )
    require_code_examples: bool = Field(
        False,
        description="Only return tasks with code examples",
    )


# ============================================================================
# VALIDATION SCHEMAS
# ============================================================================


class TaskCharacteristicsValidation(BaseModel):
    """
    Validation result for task characteristics extraction.
    """

    is_valid: bool = Field(..., description="Overall validation status")
    validation_errors: list[str] = Field(
        default_factory=list,
        description="Validation error messages",
    )
    validation_warnings: list[str] = Field(
        default_factory=list,
        description="Validation warnings",
    )
    completeness_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Characteristic completeness score",
    )
    extraction_quality: str = Field(
        ...,
        description="Extraction quality: 'excellent', 'good', 'fair', 'poor'",
    )
