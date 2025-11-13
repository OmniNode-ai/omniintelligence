"""
ONEX Contract Models: Pattern Storage Operations

Purpose: Define contracts for pattern storage Effect node operations
Pattern: ONEX 4-Node Architecture - Contract Models
File: model_contract_pattern_storage.py

Track: Track 3-1.2 - PostgreSQL Storage Layer
ONEX Compliant: Contract naming convention (model_contract_*)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

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
# Pattern Storage Contract (Specialized Effect Contract)
# ============================================================================


@dataclass
class ModelContractPatternStorage(ModelContractEffect):
    """
    Specialized contract for pattern storage operations.

    Extends ModelContractEffect with pattern-specific fields for CRUD operations
    on pattern_templates table.

    Operations:
        - insert: Insert new pattern template
        - update: Update existing pattern template
        - delete: Delete pattern template
        - batch_insert: Insert multiple patterns in transaction
        - query: Query patterns by criteria (read-only)

    Attributes:
        operation: One of [insert, update, delete, batch_insert, query]
        pattern_id: UUID of pattern for update/delete operations
        data: Pattern data for insert/update operations
        patterns: List of patterns for batch_insert operations
        query_params: Query parameters for query operations

    Example - Insert:
        >>> contract = ModelContractPatternStorage(
        ...     name="insert_async_pattern",
        ...     operation="insert",
        ...     data={
        ...         "pattern_name": "AsyncIOPattern",
        ...         "pattern_type": "code",
        ...         "language": "python",
        ...         "template_code": "async def execute_effect(...)...",
        ...         "confidence_score": 0.95
        ...     }
        ... )

    Example - Update:
        >>> contract = ModelContractPatternStorage(
        ...     name="update_pattern_score",
        ...     operation="update",
        ...     pattern_id=UUID("..."),
        ...     data={"confidence_score": 0.98, "usage_count": 42}
        ... )

    Example - Batch Insert:
        >>> contract = ModelContractPatternStorage(
        ...     name="batch_import_patterns",
        ...     operation="batch_insert",
        ...     patterns=[
        ...         {"pattern_name": "Pattern1", ...},
        ...         {"pattern_name": "Pattern2", ...}
        ...     ]
        ... )
    """

    # Pattern-specific fields
    pattern_id: Optional[UUID] = None
    data: Dict[str, Any] = field(default_factory=dict)
    patterns: List[Dict[str, Any]] = field(default_factory=list)
    query_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate contract after initialization."""
        # Set default name if not provided
        if not self.name:
            self.name = f"pattern_storage_{self.operation}"

        # Set default description
        if not self.description:
            self.description = f"Pattern storage operation: {self.operation}"

        # Validate operation-specific requirements
        if self.operation == "insert":
            if not self.data:
                raise ValueError("Insert operation requires 'data' field")
            required_fields = [
                "pattern_name",
                "pattern_type",
                "language",
                "template_code",
            ]
            missing = [f for f in required_fields if f not in self.data]
            if missing:
                raise ValueError(f"Insert operation missing required fields: {missing}")

        elif self.operation == "update":
            if not self.pattern_id:
                raise ValueError("Update operation requires 'pattern_id' field")
            if not self.data:
                raise ValueError("Update operation requires 'data' field with updates")

        elif self.operation == "delete":
            if not self.pattern_id:
                raise ValueError("Delete operation requires 'pattern_id' field")

        elif self.operation == "batch_insert":
            if not self.patterns:
                raise ValueError("Batch insert operation requires 'patterns' list")
            # Validate each pattern has required fields
            for idx, pattern in enumerate(self.patterns):
                required_fields = [
                    "pattern_name",
                    "pattern_type",
                    "language",
                    "template_code",
                ]
                missing = [f for f in required_fields if f not in pattern]
                if missing:
                    raise ValueError(
                        f"Pattern {idx} missing required fields: {missing}"
                    )


# ============================================================================
# Query Result Models
# ============================================================================


@dataclass
class ModelPatternRecord:
    """
    Represents a pattern template record from database.

    Maps directly to pattern_templates table schema.
    """

    id: UUID
    pattern_name: str
    pattern_type: str
    language: str
    category: Optional[str]
    template_code: str
    description: Optional[str]
    example_usage: Optional[str]
    source: Optional[str]
    confidence_score: float
    usage_count: int
    success_rate: float
    complexity_score: Optional[int]
    maintainability_score: Optional[float]
    performance_score: Optional[float]
    parent_pattern_id: Optional[UUID]
    is_deprecated: bool
    created_by: Optional[str]
    tags: List[str]
    context: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db_record(cls, record: Any) -> "ModelPatternRecord":
        """Create ModelPatternRecord from asyncpg Record."""
        return cls(
            id=record["id"],
            pattern_name=record["pattern_name"],
            pattern_type=record["pattern_type"],
            language=record["language"],
            category=record.get("category"),
            template_code=record["template_code"],
            description=record.get("description"),
            example_usage=record.get("example_usage"),
            source=record.get("source"),
            confidence_score=float(record["confidence_score"]),
            usage_count=record["usage_count"],
            success_rate=float(record["success_rate"]),
            complexity_score=record.get("complexity_score"),
            maintainability_score=(
                float(record["maintainability_score"])
                if record.get("maintainability_score")
                else None
            ),
            performance_score=(
                float(record["performance_score"])
                if record.get("performance_score")
                else None
            ),
            parent_pattern_id=record.get("parent_pattern_id"),
            is_deprecated=record["is_deprecated"],
            created_by=record.get("created_by"),
            tags=list(record.get("tags", [])),
            context=dict(record.get("context", {})),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "id": str(self.id),
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type,
            "language": self.language,
            "category": self.category,
            "template_code": self.template_code,
            "description": self.description,
            "example_usage": self.example_usage,
            "source": self.source,
            "confidence_score": self.confidence_score,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "complexity_score": self.complexity_score,
            "maintainability_score": self.maintainability_score,
            "performance_score": self.performance_score,
            "parent_pattern_id": (
                str(self.parent_pattern_id) if self.parent_pattern_id else None
            ),
            "is_deprecated": self.is_deprecated,
            "created_by": self.created_by,
            "tags": self.tags,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
