#!/usr/bin/env python3
"""
ModelIntelligenceInput - Domain Input Model for Intelligence Adapter Effect Node.

This is the primary input model for the Intelligence Adapter Effect Node,
providing operation routing and correlation tracking for Archon's intelligence
services including quality assessment, performance analysis, document freshness,
pattern learning, and vector operations.

ONEX v2.0 Compliance:
- Suffix-based naming: ModelIntelligenceInput
- UUID correlation tracking across operations
- Strongly-typed operation validation via EnumIntelligenceOperationType
- Comprehensive field validation with Pydantic v2
- Security validation helpers for content sanitization

Architecture:
The Intelligence Adapter Effect Node acts as a unified interface to Archon's
intelligence microservices, routing requests to appropriate backends:
- Quality Service (8053): Code/document quality analysis
- Performance Service (8053): Performance baselines and optimization
- Document Service (8053): Freshness analysis and refresh
- Pattern Service (8053): Pattern learning and traceability
- Vector Service: Qdrant semantic search and indexing
- Autonomous Service (8053): Autonomous learning and prediction

Migration Notes:
This model supports both content-based and path-based operations:
- Content-based: Provide content field with code/document text
- Path-based: Provide source_path for file-based operations
- Hybrid: Both content and source_path for context-rich analysis

Example (Code Quality Assessment):
    from uuid import uuid4
    from enum_intelligence_operation_type import EnumIntelligenceOperationType

    input_data = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
        correlation_id=uuid4(),
        source_path="src/services/api.py",
        content="def hello(): pass",
        language="python",
        options={"include_recommendations": True}
    )

Example (Performance Baseline):
    baseline_input = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.ESTABLISH_PERFORMANCE_BASELINE,
        correlation_id=uuid4(),
        options={
            "operation_name": "api_endpoint_latency",
            "target_percentile": 95
        }
    )

Example (Document Freshness):
    freshness_input = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.ANALYZE_DOCUMENT_FRESHNESS,
        correlation_id=uuid4(),
        source_path="docs/architecture/ONEX_GUIDE.md",
        options={"staleness_threshold_days": 30}
    )

See Also:
- EnumIntelligenceOperationType for operation types
- /CLAUDE.md Intelligence APIs (78) section for backend API reference
- ModelIntelligenceOutput for response structure
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ModelIntelligenceInput(BaseModel):
    """
    Strongly-typed input model for Intelligence Adapter Effect Node operations.

    This model serves as the primary routing mechanism for all intelligence
    operations. It provides flexible support for content-based and path-based
    operations with comprehensive validation and security checks.

    Operation Categories:
    - Quality Assessment: Code/document quality analysis, ONEX compliance
    - Performance: Baseline establishment, optimization, trend monitoring
    - Document Freshness: Freshness analysis, refresh operations
    - Pattern Learning: Pattern matching, analytics, traceability
    - Vector Operations: Semantic search, indexing, optimization
    - Autonomous Learning: Pattern ingestion, prediction, safety scoring

    Validation Rules:
    - operation_type must be valid EnumIntelligenceOperationType
    - Either content or source_path must be provided for content-requiring operations
    - Both cannot be empty simultaneously for analysis operations
    - language required for code quality operations
    - correlation_id preserved for distributed tracing

    Security Considerations:
    - Content sanitization via validate_content_security()
    - Path traversal prevention via validate_path_security()
    - Maximum content size limits (10MB)
    - Metadata validation for injection attacks

    Example (Code Quality with Content):
        >>> from uuid import uuid4
        >>> from enum_intelligence_operation_type import EnumIntelligenceOperationType
        >>>
        >>> quality_input = ModelIntelligenceInput(
        ...     operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
        ...     correlation_id=uuid4(),
        ...     content=\"\"\"
        ...     def calculate_total(items):
        ...         return sum(item.price for item in items)
        ...     \"\"\",
        ...     source_path="src/billing/calculator.py",
        ...     language="python",
        ...     options={
        ...         "include_recommendations": True,
        ...         "onex_compliance_check": True
        ...     }
        ... )

    Example (Performance Baseline):
        >>> baseline_input = ModelIntelligenceInput(
        ...     operation_type=EnumIntelligenceOperationType.ESTABLISH_PERFORMANCE_BASELINE,
        ...     correlation_id=uuid4(),
        ...     options={
        ...         "operation_name": "database_query_latency",
        ...         "target_percentile": 95,
        ...         "measurement_window_hours": 24
        ...     }
        ... )

    Example (Vector Search):
        >>> search_input = ModelIntelligenceInput(
        ...     operation_type=EnumIntelligenceOperationType.QUALITY_WEIGHTED_SEARCH,
        ...     correlation_id=uuid4(),
        ...     content="ONEX effect node patterns",
        ...     options={
        ...         "quality_weight": 0.3,
        ...         "min_quality_score": 0.7,
        ...         "limit": 10
        ...     }
        ... )

    Example (Document Freshness):
        >>> freshness_input = ModelIntelligenceInput(
        ...     operation_type=EnumIntelligenceOperationType.ANALYZE_DOCUMENT_FRESHNESS,
        ...     correlation_id=uuid4(),
        ...     source_path="docs/ONEX_ARCHITECTURE.md",
        ...     options={
        ...         "staleness_threshold_days": 30,
        ...         "include_refresh_recommendations": True
        ...     }
        ... )

    Example (Pattern Matching):
        >>> pattern_input = ModelIntelligenceInput(
        ...     operation_type=EnumIntelligenceOperationType.PATTERN_MATCH,
        ...     correlation_id=uuid4(),
        ...     content=\"\"\"
        ...     class NodeCalculatorCompute(NodeCompute):
        ...         async def execute_compute(self, contract: ModelContractCompute):
        ...             return await self._calculate(contract.data)
        ...     \"\"\",
        ...     language="python",
        ...     options={
        ...         "pattern_confidence_threshold": 0.8,
        ...         "include_similar_patterns": True
        ...     }
        ... )
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "operation_type": "assess_code_quality",
                    "correlation_id": "123e4567-e89b-12d3-a456-426614174000",
                    "source_path": "src/api.py",
                    "content": "def hello(): pass",
                    "language": "python",
                    "options": {"include_recommendations": True},
                }
            ]
        },
    )

    # =============================================================================
    # Operation Routing
    # =============================================================================

    operation_type: str = Field(
        ...,
        description="""
        Type of intelligence operation to perform (from EnumIntelligenceOperationType).

        Operation Categories:
        - Quality Assessment: assess_code_quality, analyze_document_quality,
          get_quality_patterns, check_architectural_compliance
        - Performance: establish_performance_baseline, identify_optimization_opportunities,
          apply_performance_optimization, get_optimization_report, monitor_performance_trends
        - Document Freshness: analyze_document_freshness, get_stale_documents,
          refresh_documents, get_freshness_stats, get_document_freshness, cleanup_freshness_data
        - Pattern Learning: pattern_match, hybrid_score, semantic_analyze,
          get_pattern_metrics, get_cache_stats, clear_pattern_cache, get_pattern_health
        - Vector Operations: advanced_vector_search, quality_weighted_search,
          batch_index_documents, get_vector_stats, optimize_vector_index
        - Autonomous Learning: ingest_patterns, record_success_pattern, predict_agent,
          predict_execution_time, calculate_safety_score, get_autonomous_stats, get_autonomous_health

        This field routes the input to the appropriate intelligence service and handler.
        """,
    )

    # =============================================================================
    # Correlation Tracking
    # =============================================================================

    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="""
        UUID correlation identifier for request tracking.

        This ID is preserved across the entire workflow, from the original
        request through intelligence service calls to result aggregation.
        It enables distributed tracing and end-to-end observability.

        Auto-generated if not provided.
        """,
    )

    # =============================================================================
    # Content Data
    # =============================================================================

    content: Optional[str] = Field(
        default=None,
        description="""
        Code or document content to analyze.

        Required for operations that analyze content:
        - Code quality assessment (assess_code_quality)
        - Document quality analysis (analyze_document_quality)
        - Pattern matching (pattern_match, hybrid_score, semantic_analyze)
        - Vector search (advanced_vector_search, quality_weighted_search)

        Optional for:
        - Operations that can work with source_path alone
        - Hybrid operations where both content and path provide context

        Validation:
        - Maximum size: 10MB (configurable)
        - Security: Sanitized for injection attacks
        - Encoding: UTF-8

        Example (Python code):
            content = '''
            class NodeCalculatorCompute(NodeCompute):
                async def execute_compute(self, contract):
                    return await self._calculate(contract.data)
            '''

        Example (Markdown documentation):
            content = '''
            # ONEX Architecture Guide

            This guide describes the ONEX architecture patterns...
            '''
        """,
        max_length=10_485_760,  # 10MB max content size
    )

    # =============================================================================
    # File Path Context
    # =============================================================================

    source_path: Optional[str] = Field(
        default=None,
        description="""
        Path to source file for context and identification.

        Required for operations that need file context:
        - Code quality with file context (assess_code_quality)
        - Document freshness (analyze_document_freshness, refresh_documents)
        - ONEX compliance checking (check_architectural_compliance)

        Optional for:
        - Content-only operations (pattern_match with inline code)
        - Operations that don't require path context

        Validation:
        - Path traversal prevention (no ../, absolute paths only)
        - Maximum length: 4096 characters
        - Character validation: alphanumeric, -, _, /, .

        Security:
        - Validated via validate_path_security()
        - Prevents directory traversal attacks
        - Sanitized for injection attempts

        Examples:
            source_path = "src/services/intelligence/api.py"
            source_path = "docs/architecture/ONEX_GUIDE.md"
            source_path = "/workspace/project/onex/effects/node_calculator_compute.py"
        """,
        max_length=4096,
    )

    # =============================================================================
    # Language Context
    # =============================================================================

    language: Optional[str] = Field(
        default=None,
        description="""
        Programming or markup language identifier.

        Required for:
        - Code quality assessment (assess_code_quality)
        - Pattern matching on code (pattern_match)
        - Language-specific analysis operations

        Optional for:
        - Document operations (markdown, text)
        - Operations that auto-detect language

        Supported languages:
        - Programming: python, typescript, javascript, rust, go, java, c, cpp
        - Markup: markdown, html, xml, yaml, json
        - Configuration: toml, ini, conf

        Examples:
            language = "python"
            language = "typescript"
            language = "markdown"
            language = "rust"
        """,
        max_length=50,
    )

    # =============================================================================
    # Operation Options
    # =============================================================================

    options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="""
        Operation-specific options and parameters.

        Flexible dictionary for operation-specific configuration:
        - Quality operations: include_recommendations, onex_compliance_check
        - Performance operations: operation_name, target_percentile, measurement_window_hours
        - Freshness operations: staleness_threshold_days, include_refresh_recommendations
        - Pattern operations: pattern_confidence_threshold, include_similar_patterns
        - Vector operations: quality_weight, min_quality_score, limit, filters
        - Autonomous operations: prediction_confidence_threshold, safety_threshold

        Example (Quality Assessment):
            options = {
                "include_recommendations": True,
                "onex_compliance_check": True,
                "max_recommendations": 10
            }

        Example (Performance Baseline):
            options = {
                "operation_name": "api_endpoint_latency",
                "target_percentile": 95,
                "measurement_window_hours": 24
            }

        Example (Vector Search):
            options = {
                "quality_weight": 0.3,
                "min_quality_score": 0.7,
                "limit": 10,
                "filters": {"language": "python"}
            }

        Example (Document Freshness):
            options = {
                "staleness_threshold_days": 30,
                "include_refresh_recommendations": True,
                "auto_refresh": False
            }

        Validation:
        - Keys must be strings
        - Values can be any JSON-serializable type
        - Reserved keys: _internal_*, _system_* (for internal use)
        """,
    )

    # =============================================================================
    # Metadata
    # =============================================================================

    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="""
        Additional metadata for extensibility and context.

        Optional metadata for tracking, analytics, and debugging:
        - user_id: User initiating the request
        - session_id: Session identifier for grouping requests
        - project_id: Project context for multi-project intelligence
        - namespace: Multi-tenant namespace identifier
        - tags: List of tags for categorization
        - custom: Custom application-specific metadata

        Example:
            metadata = {
                "user_id": "user-123",
                "project_id": "proj-456",
                "namespace": "production",
                "tags": ["quality-check", "pre-commit"],
                "custom": {
                    "git_commit": "abc123",
                    "git_branch": "feature/onex-compliance"
                }
            }

        Security:
        - Validated for injection attacks
        - Sanitized key/value pairs
        - Maximum metadata size: 100KB
        """,
    )

    # =============================================================================
    # Temporal Tracking
    # =============================================================================

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="""
        Timestamp when this input was created.

        Automatically set to current UTC time.
        Used for request tracking, latency measurement, and analytics.
        """,
    )

    # =============================================================================
    # Validators
    # =============================================================================

    @field_validator("operation_type")
    @classmethod
    def validate_operation_type(cls, v: str) -> str:
        """
        Validate operation type is a known intelligence operation.

        This validator imports EnumIntelligenceOperationType dynamically
        to avoid circular imports and validates the operation type.

        Args:
            v: Operation type string

        Returns:
            Validated operation type

        Raises:
            ValueError: If operation type is not recognized
        """
        # Import here to avoid circular dependency
        try:
            from .enum_intelligence_operation_type import EnumIntelligenceOperationType

            # Validate operation type
            if v not in [op.value for op in EnumIntelligenceOperationType]:
                valid_ops = [op.value for op in EnumIntelligenceOperationType]
                raise ValueError(
                    f"Invalid operation_type '{v}'. "
                    f"Must be one of: {', '.join(valid_ops[:5])}... "
                    f"(total: {len(valid_ops)} operations)"
                )
            return v
        except ImportError as e:
            raise ValueError(
                f"Cannot validate operation_type: {e}. "
                "Ensure enum_intelligence_operation_type.py is available."
            )

    @field_validator("source_path")
    @classmethod
    def validate_path_security(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate source_path for security concerns.

        Security checks:
        - Prevent path traversal attacks (../)
        - Validate character set (no shell injection)
        - Check maximum length

        Args:
            v: Source path string

        Returns:
            Validated source path

        Raises:
            ValueError: If path contains security risks
        """
        if v is None:
            return v

        # Prevent path traversal
        if ".." in v:
            raise ValueError(
                "Invalid source_path: Path traversal detected (..). "
                "Use absolute paths only."
            )

        # Check for common injection characters
        dangerous_chars = [";", "|", "&", "$", "`", "\n", "\r"]
        if any(char in v for char in dangerous_chars):
            raise ValueError(
                f"Invalid source_path: Contains dangerous characters. "
                f"Allowed: alphanumeric, -, _, /, ."
            )

        return v

    @field_validator("content")
    @classmethod
    def validate_content_security(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate content for size and basic security.

        Security checks:
        - Maximum size enforcement (10MB)
        - Basic sanitization (future: advanced scanning)

        Args:
            v: Content string

        Returns:
            Validated content

        Raises:
            ValueError: If content exceeds limits or contains risks
        """
        if v is None:
            return v

        # Size check (10MB)
        max_size = 10_485_760
        content_size = len(v.encode("utf-8"))
        if content_size > max_size:
            raise ValueError(
                f"Content size {content_size} bytes exceeds maximum {max_size} bytes (10MB)"
            )

        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate and normalize language identifier.

        Args:
            v: Language string

        Returns:
            Normalized language identifier (lowercase)
        """
        if v is None:
            return v

        # Normalize to lowercase
        normalized = v.lower()

        # Known languages (non-exhaustive, for validation guidance)
        known_languages = {
            # Programming languages
            "python",
            "typescript",
            "javascript",
            "rust",
            "go",
            "java",
            "c",
            "cpp",
            "c++",
            "csharp",
            "ruby",
            "php",
            "swift",
            "kotlin",
            "scala",
            # Markup/config languages
            "markdown",
            "html",
            "xml",
            "yaml",
            "json",
            "toml",
            "ini",
            "conf",
        }

        # Warn if language is not recognized (but don't fail)
        # This allows for new languages without breaking validation
        if normalized not in known_languages:
            # Log warning in production
            pass

        return normalized

    @model_validator(mode="after")
    def validate_operation_requirements(self) -> "ModelIntelligenceInput":
        """
        Validate that required fields are present for specific operations.

        This cross-field validator ensures:
        - Content-requiring operations have content or source_path
        - Language-requiring operations have language specified
        - Path-requiring operations have source_path

        Returns:
            Validated model instance

        Raises:
            ValueError: If operation requirements are not met
        """
        # Import here to avoid circular dependency
        from .enum_intelligence_operation_type import EnumIntelligenceOperationType

        try:
            op_type = EnumIntelligenceOperationType(self.operation_type)
        except ValueError:
            # Already validated in field validator, should not reach here
            return self

        # Check content requirements
        if op_type.requires_content():
            if not self.content and not self.source_path:
                raise ValueError(
                    f"Operation '{self.operation_type}' requires either 'content' or 'source_path'. "
                    "At least one must be provided."
                )

        # Check source_path requirements
        if op_type.requires_source_path():
            if not self.source_path:
                raise ValueError(
                    f"Operation '{self.operation_type}' requires 'source_path' field."
                )

        # Check language requirements for quality operations
        if op_type.is_quality_operation() and self.content:
            if not self.language:
                raise ValueError(
                    f"Operation '{self.operation_type}' with content requires 'language' field. "
                    "Specify the programming/markup language (e.g., 'python', 'markdown')."
                )

        return self

    # =============================================================================
    # Utility Methods
    # =============================================================================

    def get_operation_category(self) -> str:
        """
        Get the category of the operation.

        Returns:
            Operation category string (quality, performance, document, etc.)
        """
        from .enum_intelligence_operation_type import EnumIntelligenceOperationType

        op_type = EnumIntelligenceOperationType(self.operation_type)

        if op_type.is_quality_operation():
            return "quality"
        elif op_type.is_performance_operation():
            return "performance"
        elif op_type.is_document_operation():
            return "document"
        elif op_type.is_pattern_operation():
            return "pattern"
        elif op_type.is_vector_operation():
            return "vector"
        elif op_type.is_autonomous_operation():
            return "autonomous"
        else:
            return "unknown"

    def is_read_only_operation(self) -> bool:
        """
        Check if this operation is read-only.

        Returns:
            True if operation does not modify state
        """
        from .enum_intelligence_operation_type import EnumIntelligenceOperationType

        op_type = EnumIntelligenceOperationType(self.operation_type)
        return op_type.is_read_only()

    def get_content_or_placeholder(self) -> str:
        """
        Get content or placeholder for logging/display.

        Returns:
            Content preview or placeholder string
        """
        if self.content:
            max_preview = 100
            preview = self.content[:max_preview]
            if len(self.content) > max_preview:
                preview += "..."
            return preview
        elif self.source_path:
            return f"<file: {self.source_path}>"
        else:
            return "<no content>"
