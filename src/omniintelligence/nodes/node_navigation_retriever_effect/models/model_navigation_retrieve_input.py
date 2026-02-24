# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input model for NavigationRetrieverEffect.

Ticket: OMN-2579
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_navigation_retriever_effect.models.model_contract_graph import (
    ContractGraph,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_contract_state import (
    ContractState,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_goal_condition import (
    GoalCondition,
)

_DEFAULT_TOP_K = 3
_DEFAULT_TIMEOUT_SECONDS = 2.0
_DEFAULT_COLLECTION = "navigation_paths"
_DEFAULT_EMBEDDING_URL = "http://192.168.86.200:8100"


class ModelNavigationRetrieveInput(BaseModel):
    """Input for a navigation path retrieval request.

    Attributes:
        goal: The goal condition the navigation is trying to satisfy.
        current_state: Current position in the contract graph.
        graph: The current contract graph (for staleness filtering).
        embedding_url: Base URL for the Qwen3-Embedding server.
        qdrant_url: Base URL for the Qdrant instance.
        qdrant_collection: Name of the Qdrant collection for navigation paths.
        top_k: Number of top paths to return (default 3).
        timeout_seconds: Max seconds to wait for retrieval (default 2.0).
        correlation_id: Optional correlation ID for tracing.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    goal: GoalCondition = Field(
        description="The goal condition the navigation is trying to satisfy.",
    )
    current_state: ContractState = Field(
        description="Current position in the contract graph.",
    )
    graph: ContractGraph = Field(
        description="The current contract graph (for staleness filtering).",
    )
    embedding_url: str = Field(
        default=_DEFAULT_EMBEDDING_URL,
        description="Base URL for the Qwen3-Embedding server (from LLM_EMBEDDING_URL).",
    )
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Base URL for the Qdrant instance.",
    )
    qdrant_collection: str = Field(
        default=_DEFAULT_COLLECTION,
        description="Qdrant collection name for navigation paths.",
    )
    top_k: int = Field(
        default=_DEFAULT_TOP_K,
        description="Number of top paths to return.",
        gt=0,
    )
    timeout_seconds: float = Field(
        default=_DEFAULT_TIMEOUT_SECONDS,
        description="Max seconds to wait for retrieval before graceful fallback.",
        gt=0.0,
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelNavigationRetrieveInput"]
