# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node NavigationRetrieverEffect — RAG retrieval of prior navigation paths.

Effect node for the local agent graph navigation system. Receives a goal
condition, current contract state, and contract graph; retrieves ranked
prior successful navigation paths for similar goals from OmniMemory (Qdrant).

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - I/O effect: calls Qwen3-Embedding HTTP API + Qdrant
    - Lightweight shell that delegates to handle_navigation_retrieve

Responsibilities:
    - Embed goal + current state structure via Qwen3-Embedding-8B (port 8100)
    - Query Qdrant `navigation_paths` collection with hard filters
    - Apply staleness filtering: remove steps not in current graph
    - Return top-K ranked RetrievedPath list (similarity descending)
    - Graceful timeout (2s default): return empty list, never block navigation

Does NOT:
    - Override graph boundary enforcement (retrieval is advisory only)
    - Store navigation paths to Qdrant (that is the history storage ticket)
    - Raise exceptions on failure (always returns empty list on error)

Related:
    - OMN-2579: This node implementation
    - OMN-2540: ContractGraph, ContractState, GoalCondition, PlanStep (omnibase_core)
    - OMN-2365: Local Agent Graph Navigation epic
    - OMN-2392: EmbeddingGenerationEffect (upstream EmbeddingClient)
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeNavigationRetrieverEffect(NodeEffect):
    """Declarative effect node for RAG-based navigation path retrieval.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - retrieve_paths: Retrieve ranked prior navigation paths from OmniMemory

    Dependency Injection:
        The ``handle_navigation_retrieve`` handler accepts optional
        ``embedder`` and ``vector_store`` instances for testing.
        In production, both are created from configuration fields.

    Example:
        ```python
        import os
        from omniintelligence.nodes.node_navigation_retriever_effect.handlers import (
            handle_navigation_retrieve,
        )
        from omniintelligence.nodes.node_navigation_retriever_effect.models import (
            ContractGraph,
            ContractState,
            GoalCondition,
            ModelNavigationRetrieveInput,
        )

        result = await handle_navigation_retrieve(
            ModelNavigationRetrieveInput(
                goal=GoalCondition(
                    goal_id="goal-001",
                    target_component_type="api_gateway",
                    target_datasource_class="rest",
                    target_policy_tier="tier_2",
                ),
                current_state=ContractState(
                    node_id="node-start",
                    component_type="api_gateway",
                    datasource_class="rest",
                    policy_tier="tier_2",
                    graph_fingerprint="sha256:abc123",
                    available_transitions=frozenset(["to_auth", "to_cache"]),
                ),
                graph=ContractGraph(
                    graph_id="graph-001",
                    fingerprint="sha256:abc123",
                    valid_transitions=frozenset([("node-start", "to_auth")]),
                ),
                embedding_url=os.environ.get("LLM_EMBEDDING_URL", "http://192.168.86.200:8100"),
                qdrant_url="http://localhost:6333",
            )
        )
        # result.paths — ranked list of RetrievedPath (may be empty on cold start)
        # result.timed_out — True if retrieval exceeded 2s timeout
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeNavigationRetrieverEffect"]
