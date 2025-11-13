"""
ONEX Contract Models: Pattern Lineage Tracking

Purpose: Define contracts for pattern lineage tracker Effect node operations
Pattern: ONEX 4-Node Architecture - Contract Models
File: model_contract_pattern_lineage.py

Track: Track 3 Phase 4 - Pattern Traceability
ONEX Compliant: Contract naming convention (model_contract_*)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# ============================================================================
# Enumerations
# ============================================================================


class LineageEventType(str, Enum):
    """Types of lineage events."""

    PATTERN_CREATED = "pattern_created"
    PATTERN_MODIFIED = "pattern_modified"
    PATTERN_MERGED = "pattern_merged"
    PATTERN_APPLIED = "pattern_applied"
    PATTERN_DEPRECATED = "pattern_deprecated"
    PATTERN_FORKED = "pattern_forked"
    PATTERN_VALIDATED = "pattern_validated"


class EdgeType(str, Enum):
    """Types of relationships between patterns."""

    DERIVED_FROM = "derived_from"
    MODIFIED_FROM = "modified_from"
    MERGED_FROM = "merged_from"
    REPLACED_BY = "replaced_by"
    INSPIRED_BY = "inspired_by"
    DEPRECATED_BY = "deprecated_by"


class TransformationType(str, Enum):
    """Types of transformations applied to patterns."""

    REFACTOR = "refactor"
    ENHANCEMENT = "enhancement"
    BUGFIX = "bugfix"
    MERGE = "merge"
    OPTIMIZATION = "optimization"
    SIMPLIFICATION = "simplification"


class LineageOperation(str, Enum):
    """Operations supported by pattern lineage tracker."""

    CREATE = "create"
    UPDATE = "update"
    MERGE = "merge"
    QUERY_ANCESTORS = "query_ancestors"
    QUERY_DESCENDANTS = "query_descendants"
    QUERY_FULL_GRAPH = "query_full_graph"
    FIND_PATH = "find_path"


class LineageDepth(str, Enum):
    """Depth specification for lineage queries."""

    IMMEDIATE = "immediate"  # Only direct parents/children
    FULL = "full"  # All ancestors/descendants to root/leaves


# ============================================================================
# Base Result Model (ONEX Standard)
# ============================================================================


@dataclass
class ModelResult:
    """
    Standard ONEX result format for all operations.

    Attributes:
        success: Operation success status
        data: Operation result data (optional)
        error: Error message if operation failed (optional)
        metadata: Additional operation metadata (correlation_id, duration_ms, etc.)
    """

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


# ============================================================================
# Base Contract Model (ONEX Standard)
# ============================================================================


@dataclass
class ModelContractBase:
    """
    Base ONEX contract with common fields.

    All ONEX contracts extend this base with:
    - name: Contract/operation identifier
    - version: Contract version for compatibility
    - description: Human-readable operation description
    - correlation_id: Request tracing across services
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    correlation_id: UUID = field(default_factory=uuid4)


# ============================================================================
# Effect Contract Model (ONEX Standard)
# ============================================================================


@dataclass
class ModelContractEffect(ModelContractBase):
    """
    ONEX Effect contract for side effect operations.

    Effect nodes handle:
    - External I/O operations
    - Database operations
    - API calls
    - Event emissions

    Attributes:
        operation: Specific operation to execute
        node_type: Fixed as 'effect' for Effect nodes
    """

    operation: str = "execute"
    node_type: str = "effect"


# ============================================================================
# Pattern Lineage Input Contract
# ============================================================================


@dataclass
class ModelPatternLineageInput(ModelContractEffect):
    """
    Input contract for pattern lineage tracking operations.

    Extends ModelContractEffect with lineage-specific fields for tracking
    pattern ancestry, evolution, and relationships.

    Operations:
        - track_creation: Record new pattern creation
        - track_modification: Record pattern update
        - track_merge: Record pattern merge
        - track_application: Record pattern usage
        - track_deprecation: Record pattern deprecation
        - track_fork: Record pattern branching
        - query_ancestry: Query pattern ancestry chain
        - query_descendants: Query pattern descendants

    Attributes:
        event_type: Type of lineage event
        pattern_id: Unique identifier for the pattern
        pattern_name: Human-readable pattern name
        pattern_type: Category of pattern (code, config, template, workflow)
        pattern_version: Version string (semantic versioning)
        pattern_data: Full pattern data snapshot
        parent_pattern_ids: List of parent pattern IDs (for derived/merged patterns)
        edge_type: Type of relationship to parent (for derived patterns)
        transformation_type: Type of transformation applied
        metadata: Additional event metadata
        reason: Human-readable reason for the event
        triggered_by: Who/what triggered the event

    Example - Track Creation:
        >>> contract = ModelPatternLineageInput(
        ...     name="track_new_pattern",
        ...     operation="track_creation",
        ...     event_type=LineageEventType.PATTERN_CREATED,
        ...     pattern_id="async_db_writer_v1",
        ...     pattern_name="AsyncDatabaseWriter",
        ...     pattern_type="code",
        ...     pattern_version="1.0.0",
        ...     pattern_data={
        ...         "template_code": "async def execute_effect(...)...",
        ...         "language": "python"
        ...     },
        ...     triggered_by="ai_assistant"
        ... )

    Example - Track Modification:
        >>> contract = ModelPatternLineageInput(
        ...     name="track_pattern_update",
        ...     operation="track_modification",
        ...     event_type=LineageEventType.PATTERN_MODIFIED,
        ...     pattern_id="async_db_writer_v2",
        ...     pattern_version="2.0.0",
        ...     parent_pattern_ids=["async_db_writer_v1"],
        ...     edge_type=EdgeType.MODIFIED_FROM,
        ...     transformation_type=TransformationType.ENHANCEMENT,
        ...     reason="Added error handling and retry logic"
        ... )

    Example - Track Merge:
        >>> contract = ModelPatternLineageInput(
        ...     name="track_pattern_merge",
        ...     operation="track_merge",
        ...     event_type=LineageEventType.PATTERN_MERGED,
        ...     pattern_id="unified_db_writer_v1",
        ...     parent_pattern_ids=["async_db_writer_v2", "sync_db_writer_v1"],
        ...     edge_type=EdgeType.MERGED_FROM,
        ...     transformation_type=TransformationType.MERGE,
        ...     reason="Unified async and sync database writers"
        ... )
    """

    # Event classification
    event_type: LineageEventType = LineageEventType.PATTERN_CREATED

    # Pattern identification
    pattern_id: str = ""
    pattern_name: str = ""
    pattern_type: str = "code"  # code, config, template, workflow
    pattern_version: str = "1.0.0"

    # Pattern context (added for database column support)
    tool_name: Optional[str] = None  # Tool that created the pattern (Write, Edit, etc.)
    file_path: Optional[str] = None  # Full path to the file
    language: Optional[str] = "python"  # Programming language

    # Pattern content
    pattern_data: Dict[str, Any] = field(default_factory=dict)

    # Lineage relationships
    parent_pattern_ids: List[str] = field(default_factory=list)
    edge_type: Optional[EdgeType] = None
    transformation_type: Optional[TransformationType] = None

    # Event metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None
    triggered_by: str = "system"  # user, system, ai_assistant

    def __post_init__(self):
        """Validate contract after initialization."""
        # Set default name if not provided
        if not self.name:
            self.name = f"pattern_lineage_{self.operation}"

        # Set default description
        if not self.description:
            self.description = f"Pattern lineage operation: {self.operation}"

        # Validate operation-specific requirements
        if self.operation == "track_creation":
            if not self.pattern_id:
                raise ValueError("track_creation requires pattern_id")
            if not self.pattern_data:
                raise ValueError("track_creation requires pattern_data")

        elif self.operation == "track_modification":
            if not self.pattern_id:
                raise ValueError("track_modification requires pattern_id")
            if not self.parent_pattern_ids:
                raise ValueError("track_modification requires parent_pattern_ids")

        elif self.operation == "track_merge":
            if not self.pattern_id:
                raise ValueError("track_merge requires pattern_id")
            if len(self.parent_pattern_ids) < 2:
                raise ValueError("track_merge requires at least 2 parent_pattern_ids")

        elif self.operation in ["query_ancestry", "query_descendants"]:
            if not self.pattern_id:
                raise ValueError(f"{self.operation} requires pattern_id")


# ============================================================================
# Pattern Lineage Query Contract
# ============================================================================


@dataclass
class ModelLineageQueryInput(ModelContractEffect):
    """
    Input contract for pattern lineage query operations.

    Extends ModelContractEffect with query-specific fields for retrieving
    pattern lineage information.

    Operations:
        - query_ancestors: Get all ancestors of a pattern
        - query_descendants: Get all descendants of a pattern
        - query_full_graph: Get complete lineage graph
        - find_path: Find path between two patterns

    Attributes:
        operation: Type of query operation (from LineageOperation enum)
        pattern_id: Target pattern identifier
        depth: Query depth (IMMEDIATE or FULL)
        include_metadata: Whether to include metadata in results
        target_pattern_id: Target pattern ID (for find_path operation)
        metadata_filter: Optional filter for metadata fields

    Example - Query Ancestors:
        >>> contract = ModelLineageQueryInput(
        ...     operation=LineageOperation.QUERY_ANCESTORS,
        ...     pattern_id="derived_pattern_v2",
        ...     depth=LineageDepth.FULL,
        ...     include_metadata=True
        ... )

    Example - Find Path:
        >>> contract = ModelLineageQueryInput(
        ...     operation=LineageOperation.FIND_PATH,
        ...     pattern_id="pattern_a",
        ...     target_pattern_id="pattern_z",
        ...     depth=LineageDepth.FULL,
        ...     include_metadata=False
        ... )
    """

    # Query specification
    operation: LineageOperation = LineageOperation.QUERY_ANCESTORS
    pattern_id: str = ""
    depth: LineageDepth = LineageDepth.FULL
    include_metadata: bool = False

    # Optional parameters
    target_pattern_id: Optional[str] = None  # For find_path operation
    metadata_filter: Optional[Dict[str, Any]] = None  # For filtering results

    def __post_init__(self):
        """Validate query contract after initialization."""
        # Set default name if not provided
        if not self.name:
            self.name = f"pattern_lineage_{self.operation}"

        # Set default description
        if not self.description:
            self.description = f"Pattern lineage query: {self.operation}"

        # Validate operation-specific requirements
        if not self.pattern_id:
            raise ValueError(f"{self.operation} requires pattern_id")

        if self.operation == LineageOperation.FIND_PATH:
            if not self.target_pattern_id:
                raise ValueError("find_path requires target_pattern_id")


# ============================================================================
# Pattern Lineage Output Contract
# ============================================================================


@dataclass
class ModelPatternLineageOutput:
    """
    Output contract for pattern lineage tracking operations.

    Contains results from lineage tracking and query operations.

    Attributes:
        success: Operation success status
        lineage_id: UUID identifying the pattern lineage
        pattern_id: Pattern identifier
        pattern_node_id: UUID of the pattern node in lineage graph
        event_id: UUID of the lineage event
        ancestry_depth: Number of generations to root
        total_ancestors: Total number of ancestors
        total_descendants: Total number of descendants
        lineage_created: Timestamp of lineage creation
        metadata: Additional result metadata
        error: Error message if operation failed
    """

    success: bool
    lineage_id: Optional[UUID] = None
    pattern_id: Optional[str] = None
    pattern_node_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    ancestry_depth: int = 0
    total_ancestors: int = 0
    total_descendants: int = 0
    lineage_created: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert output to dictionary format."""
        return {
            "success": self.success,
            "lineage_id": str(self.lineage_id) if self.lineage_id else None,
            "pattern_id": self.pattern_id,
            "pattern_node_id": (
                str(self.pattern_node_id) if self.pattern_node_id else None
            ),
            "event_id": str(self.event_id) if self.event_id else None,
            "ancestry_depth": self.ancestry_depth,
            "total_ancestors": self.total_ancestors,
            "total_descendants": self.total_descendants,
            "lineage_created": (
                self.lineage_created.isoformat() if self.lineage_created else None
            ),
            "metadata": self.metadata,
            "error": self.error,
        }


# ============================================================================
# Ancestry Query Result Models
# ============================================================================


@dataclass
class ModelAncestorRecord:
    """
    Represents a single ancestor in the lineage chain.

    Attributes:
        ancestor_id: UUID of ancestor node
        ancestor_pattern_id: Pattern identifier of ancestor
        generation: Generation number (1 = root)
        edge_type: Type of relationship edge
        created_at: When ancestor was created
    """

    ancestor_id: UUID
    ancestor_pattern_id: str
    generation: int
    edge_type: Optional[str]
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "ancestor_id": str(self.ancestor_id),
            "ancestor_pattern_id": self.ancestor_pattern_id,
            "generation": self.generation,
            "edge_type": self.edge_type,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ModelDescendantRecord:
    """
    Represents a single descendant in the lineage tree.

    Attributes:
        descendant_id: UUID of descendant node
        descendant_pattern_id: Pattern identifier of descendant
        edge_type: Type of relationship edge
        transformation_type: Type of transformation applied
        created_at: When descendant was created
    """

    descendant_id: UUID
    descendant_pattern_id: str
    edge_type: str
    transformation_type: Optional[str]
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "descendant_id": str(self.descendant_id),
            "descendant_pattern_id": self.descendant_pattern_id,
            "edge_type": self.edge_type,
            "transformation_type": self.transformation_type,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ModelLineageGraph:
    """
    Represents complete lineage graph for a pattern.

    Attributes:
        pattern_id: Pattern identifier
        pattern_node_id: UUID of pattern node
        ancestors: List of ancestor records
        descendants: List of descendant records
        ancestry_depth: Depth from root
        total_ancestors: Total ancestor count
        total_descendants: Total descendant count
        lineage_id: UUID of lineage group
    """

    pattern_id: str
    pattern_node_id: UUID
    ancestors: List[ModelAncestorRecord] = field(default_factory=list)
    descendants: List[ModelDescendantRecord] = field(default_factory=list)
    ancestry_depth: int = 0
    total_ancestors: int = 0
    total_descendants: int = 0
    lineage_id: Optional[UUID] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_node_id": str(self.pattern_node_id),
            "ancestors": [a.to_dict() for a in self.ancestors],
            "descendants": [d.to_dict() for d in self.descendants],
            "ancestry_depth": self.ancestry_depth,
            "total_ancestors": self.total_ancestors,
            "total_descendants": self.total_descendants,
            "lineage_id": str(self.lineage_id) if self.lineage_id else None,
        }
