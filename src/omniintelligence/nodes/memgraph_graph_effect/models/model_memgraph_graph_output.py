"""Output model for Memgraph Graph Effect."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelMemgraphGraphOutput(BaseModel):
    """Output model for Memgraph graph operations.

    This model represents the result of graph storage operations.
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
    query_results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Results from Cypher query execution",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the operation",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelMemgraphGraphOutput"]
