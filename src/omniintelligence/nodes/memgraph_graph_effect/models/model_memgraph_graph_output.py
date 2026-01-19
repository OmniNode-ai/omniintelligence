"""Output model for Memgraph Graph Effect."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class QueryResultRowDict(TypedDict, total=False):
    """Typed structure for a query result row.

    Provides type-safe fields for Cypher query results.
    """

    # Node properties
    node_id: str
    node_type: str
    node_name: str
    node_properties: dict[str, str | int | float | bool | None]

    # Relationship properties
    relationship_id: str
    relationship_type: str
    source_id: str
    target_id: str

    # Aggregation results
    count: int
    sum: float
    avg: float
    min: float
    max: float

    # Path results
    path_length: int
    path_nodes: list[str]


class GraphOperationMetadataDict(TypedDict, total=False):
    """Typed structure for graph operation metadata.

    Provides type-safe fields for operation metadata.
    """

    # Processing info
    processing_time_ms: int
    timestamp: str

    # Operation stats
    query_execution_ms: int
    nodes_matched: int
    relationships_matched: int

    # Status
    status: str
    message: str


class ModelMemgraphGraphOutput(BaseModel):
    """Output model for Memgraph graph operations.

    This model represents the result of graph storage operations.

    All fields use strong typing without dict[str, Any].
    """

    success: bool = Field(
        ...,
        description="Whether the graph operation succeeded",
    )
    nodes_created: int = Field(
        default=0,
        description="Number of nodes created",
    )
    relationships_created: int = Field(
        default=0,
        description="Number of relationships created",
    )
    query_results: list[QueryResultRowDict] = Field(
        default_factory=list,
        description="Results from Cypher query execution with typed fields",
    )
    metadata: GraphOperationMetadataDict | None = Field(
        default=None,
        description="Additional metadata about the operation with typed fields",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "GraphOperationMetadataDict",
    "ModelMemgraphGraphOutput",
    "QueryResultRowDict",
]
