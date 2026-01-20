"""Input model for Memgraph Graph Effect."""

from __future__ import annotations

from typing import Literal, Self, TypedDict

from pydantic import BaseModel, Field, model_validator


class GraphEntityDict(TypedDict, total=False):
    """Typed structure for a graph entity (node).

    Provides type-safe fields for graph node creation.
    """

    # Identification
    entity_id: str
    entity_type: str
    name: str

    # Properties
    description: str
    source_file: str
    language: str

    # Classification
    category: str
    tags: list[str]

    # Metadata
    confidence: float
    created_at: str
    updated_at: str


class GraphRelationshipDict(TypedDict, total=False):
    """Typed structure for a graph relationship (edge).

    Provides type-safe fields for graph edge creation.
    """

    # Identification
    relationship_id: str
    relationship_type: str

    # Endpoints
    source_id: str
    target_id: str

    # Properties
    weight: float
    label: str
    description: str

    # Metadata
    confidence: float
    created_at: str


class QueryParametersDict(TypedDict, total=False):
    """Typed structure for Cypher query parameters.

    Provides type-safe fields for parameterized queries.
    """

    # Common parameters
    node_id: str
    node_type: str
    relationship_type: str
    limit: int
    offset: int

    # Search parameters
    name_pattern: str
    min_confidence: float
    max_results: int

    # Time filters
    since_timestamp: str
    until_timestamp: str


class ModelMemgraphGraphInput(BaseModel):
    """Input model for Memgraph graph operations.

    This model represents the input for graph storage operations.

    Operation-specific requirements:
        - create_nodes: requires entities (non-empty list)
        - create_relationships: requires relationships (non-empty list)
        - execute_query: requires cypher_query (non-empty string)

    All fields use strong typing without dict[str, Any].
    """

    operation: Literal["create_nodes", "create_relationships", "execute_query"] = Field(
        default="create_nodes",
        description="Type of graph operation",
    )
    entities: list[GraphEntityDict] = Field(
        default_factory=list,
        description="Entities to create as graph nodes with typed fields",
    )
    relationships: list[GraphRelationshipDict] = Field(
        default_factory=list,
        description="Relationships to create between nodes with typed fields",
    )
    cypher_query: str | None = Field(
        default=None,
        min_length=1,
        description="Cypher query to execute (for execute_query operation)",
    )
    query_parameters: QueryParametersDict = Field(
        default_factory=lambda: QueryParametersDict(),
        description="Parameters for the Cypher query with typed fields",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    @model_validator(mode="after")
    def validate_operation_requirements(self) -> Self:
        """Validate that required fields are provided for each operation type."""
        if self.operation == "create_nodes" and not self.entities:
            raise ValueError("create_nodes operation requires entities")
        if self.operation == "create_relationships" and not self.relationships:
            raise ValueError("create_relationships operation requires relationships")
        if self.operation == "execute_query" and not self.cypher_query:
            raise ValueError("execute_query operation requires cypher_query")
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "GraphEntityDict",
    "GraphRelationshipDict",
    "ModelMemgraphGraphInput",
    "QueryParametersDict",
]
