"""Input model for Memgraph Graph Effect."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ModelMemgraphGraphInput(BaseModel):
    """Input model for Memgraph graph operations.

    This model represents the input for graph storage operations.
    """

    operation: Literal["create_nodes", "create_relationships", "execute_query"] = Field(
        default="create_nodes",
        description="Type of graph operation",
    )
    entities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Entities to create as graph nodes",
    )
    relationships: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Relationships to create between nodes",
    )
    cypher_query: Optional[str] = Field(
        default=None,
        description="Cypher query to execute (for execute_query operation)",
    )
    query_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the Cypher query",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelMemgraphGraphInput"]
