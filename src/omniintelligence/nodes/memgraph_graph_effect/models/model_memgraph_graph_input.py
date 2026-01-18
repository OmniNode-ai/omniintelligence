"""Input model for Memgraph Graph Effect."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


class ModelMemgraphGraphInput(BaseModel):
    """Input model for Memgraph graph operations.

    This model represents the input for graph storage operations.

    Operation-specific requirements:
        - create_nodes: requires entities (non-empty list)
        - create_relationships: requires relationships (non-empty list)
        - execute_query: requires cypher_query (non-empty string)
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
    cypher_query: str | None = Field(
        default=None,
        min_length=1,
        description="Cypher query to execute (for execute_query operation)",
    )
    query_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the Cypher query",
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


__all__ = ["ModelMemgraphGraphInput"]
