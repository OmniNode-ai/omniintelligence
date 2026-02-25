# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for NavigationRetrieverEffect — RAG retrieval of prior navigation paths.

Behavior:
  - Receives a goal condition, current contract state, and contract graph
  - Embeds the goal + current state structure via Qwen3-Embedding-8B (port 8100)
  - Queries Qdrant `navigation_paths` collection for top-K similar paths
  - Applies hard filters: component type, datasource class, policy tier
  - Applies staleness filtering: removes steps not in the current graph
  - Returns ranked RetrievedPath list (similarity descending)

Cold start:
  - Empty Qdrant collection → returns empty list (not an error)
  - Collection not found → creates it, returns empty list

Timeout:
  - Retrieval exceeds timeout_seconds (default 2s) → graceful fallback to empty list
  - Navigation session continues unblocked

Error handling:
  - Embedding failure → graceful fallback (empty list, timed_out=False)
  - Qdrant query failure → graceful fallback (empty list)
  - No errors are propagated — retrieval is advisory only

Ticket: OMN-2579
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Protocol, runtime_checkable

from omniintelligence.nodes.node_navigation_retriever_effect.models.enum_navigation_outcome import (
    EnumNavigationOutcome,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_contract_graph import (
    ContractGraph,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_goal_condition import (
    GoalCondition,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_navigation_retrieve_input import (
    ModelNavigationRetrieveInput,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_navigation_retrieve_output import (
    ModelNavigationRetrieveOutput,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_plan_step import (
    PlanStep,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_retrieved_path import (
    RetrievedPath,
)

logger = logging.getLogger(__name__)

# Qdrant collection configuration
_COLLECTION_NAME = "navigation_paths"
_EMBEDDING_DIMENSION = 1024
_QDRANT_DISTANCE = "Cosine"

# Hard filter Qdrant payload field names
_FIELD_COMPONENT_TYPE = "component_type"
_FIELD_DATASOURCE_CLASS = "datasource_class"
_FIELD_POLICY_TIER = "policy_tier"
_FIELD_OUTCOME = "outcome"
_FIELD_GRAPH_FINGERPRINT = "graph_fingerprint"
_FIELD_STEPS_JSON = "steps_json"
_FIELD_GOAL_JSON = "goal_json"


# =============================================================================
# Protocol Definitions (dependency injection for testability)
# =============================================================================


@runtime_checkable
class ProtocolNavigationEmbedder(Protocol):
    """Protocol for embedding contract state structures for similarity search."""

    async def embed_text(self, text: str) -> list[float]:
        """Embed text and return a 1024-dimensional vector.

        Args:
            text: The text to embed (serialized goal + state structure).

        Returns:
            1024-dimensional embedding vector.

        Raises:
            Exception: On embedding failure (caller handles gracefully).
        """
        ...


@runtime_checkable
class ProtocolNavigationVectorStore(Protocol):
    """Protocol for Qdrant navigation path storage and retrieval."""

    async def ensure_collection(
        self, collection: str, dimension: int, distance: str
    ) -> bool:
        """Ensure the collection exists, create if not.

        Args:
            collection: Collection name.
            dimension: Embedding dimension.
            distance: Distance metric (e.g., "Cosine").

        Returns:
            True if collection exists or was created, False on error.
        """
        ...

    async def search_similar(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int,
        filter_must: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors in the collection.

        Args:
            collection: Collection name.
            query_vector: Query embedding vector.
            top_k: Number of results to return.
            filter_must: Optional list of Qdrant filter conditions.

        Returns:
            List of result dicts with keys: id, score, payload.
            Empty list on error or no results.
        """
        ...


# =============================================================================
# Text serialization for embedding
# =============================================================================


def _serialize_goal_for_embedding(goal: GoalCondition) -> str:
    """Serialize a goal condition to a text string for embedding.

    Produces a structured representation that captures the goal's
    structural properties for similarity comparison.

    Args:
        goal: The goal condition to serialize.

    Returns:
        Structured text string for embedding.
    """
    return (
        f"navigation_goal "
        f"component_type:{goal.target_component_type} "
        f"datasource_class:{goal.target_datasource_class} "
        f"policy_tier:{goal.target_policy_tier}"
    )


def _build_embedding_text(input_data: ModelNavigationRetrieveInput) -> str:
    """Build the text to embed for similarity search.

    Combines goal condition and current state structural properties
    for a rich structural similarity representation.

    Args:
        input_data: The retrieval request.

    Returns:
        Combined text for embedding.
    """
    goal = input_data.goal
    state = input_data.current_state

    return (
        f"navigation_query "
        f"goal_component:{goal.target_component_type} "
        f"goal_datasource:{goal.target_datasource_class} "
        f"goal_tier:{goal.target_policy_tier} "
        f"current_node:{state.node_id} "
        f"current_component:{state.component_type} "
        f"current_datasource:{state.datasource_class} "
        f"current_tier:{state.policy_tier}"
    )


# =============================================================================
# Hard filtering
# =============================================================================


def _build_hard_filter(
    input_data: ModelNavigationRetrieveInput,
) -> list[dict[str, Any]]:
    """Build Qdrant filter conditions for hard filtering.

    Hard filters exclude paths with incompatible:
    - component_type (from stored path)
    - datasource_class (from stored path)
    - policy_tier (from stored path)

    Matching is done against the goal's target values, since we want
    paths that were navigating toward the same structural configuration.

    Args:
        input_data: The retrieval request.

    Returns:
        List of Qdrant filter must-conditions.
    """
    goal = input_data.goal
    return [
        {
            "key": _FIELD_COMPONENT_TYPE,
            "match": {"value": goal.target_component_type},
        },
        {
            "key": _FIELD_DATASOURCE_CLASS,
            "match": {"value": goal.target_datasource_class},
        },
        {
            "key": _FIELD_POLICY_TIER,
            "match": {"value": goal.target_policy_tier},
        },
    ]


# =============================================================================
# Staleness filtering
# =============================================================================


def _filter_stale_steps(
    steps: list[PlanStep],
    graph: ContractGraph,
) -> tuple[tuple[PlanStep, ...], int]:
    """Remove steps whose transitions are no longer in the current graph.

    A step is considered stale if the (from_node_id, action) pair is
    not in the current graph's valid_transitions set.

    Args:
        steps: The prior path steps to filter.
        graph: The current contract graph.

    Returns:
        Tuple of (filtered_steps_tuple, stale_count).
    """
    filtered: list[PlanStep] = []
    stale_count = 0

    for step in steps:
        transition_key = (step.from_node_id, step.action)
        if transition_key in graph.valid_transitions:
            filtered.append(step)
        else:
            stale_count += 1
            logger.debug(
                "Filtering stale step: from_node=%s action=%s (not in current graph)",
                step.from_node_id,
                step.action,
            )

    return tuple(filtered), stale_count


# =============================================================================
# Result deserialization
# =============================================================================


def _deserialize_steps(steps_json: str) -> list[PlanStep]:
    """Deserialize JSON-encoded steps from Qdrant payload.

    Args:
        steps_json: JSON string of serialized PlanStep list.

    Returns:
        List of PlanStep objects. Empty list on parse failure.
    """
    try:
        raw: list[dict[str, Any]] = json.loads(steps_json)
        return [PlanStep.model_validate(s) for s in raw]
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning("Failed to deserialize steps: %s", exc)
        return []


def _deserialize_goal(goal_json: str) -> GoalCondition | None:
    """Deserialize JSON-encoded goal from Qdrant payload.

    Args:
        goal_json: JSON string of serialized GoalCondition.

    Returns:
        GoalCondition or None on parse failure.
    """
    try:
        raw: dict[str, Any] = json.loads(goal_json)
        return GoalCondition.model_validate(raw)
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning("Failed to deserialize goal: %s", exc)
        return None


def _build_retrieved_path(
    result: dict[str, Any],
    graph: ContractGraph,
) -> tuple[RetrievedPath, int] | None:
    """Build a RetrievedPath from a Qdrant search result.

    Applies staleness filtering to the steps.

    Args:
        result: Qdrant search result dict (id, score, payload).
        graph: Current contract graph for staleness checks.

    Returns:
        (RetrievedPath, stale_steps_count) or None on parse failure.
    """
    try:
        payload: dict[str, Any] = result.get("payload", {})
        score: float = float(result.get("score", 0.0))
        point_id: str = str(result.get("id", ""))

        steps_json: str = payload.get(_FIELD_STEPS_JSON, "[]")
        goal_json: str = payload.get(_FIELD_GOAL_JSON, "{}")
        outcome_str: str = payload.get(_FIELD_OUTCOME, "unknown")
        graph_fingerprint: str = payload.get(_FIELD_GRAPH_FINGERPRINT, "")

        raw_steps = _deserialize_steps(steps_json)
        goal = _deserialize_goal(goal_json)

        if goal is None:
            logger.warning("Skipping result %s: could not deserialize goal", point_id)
            return None

        filtered_steps, stale_count = _filter_stale_steps(raw_steps, graph)

        try:
            outcome = EnumNavigationOutcome(outcome_str)
        except ValueError:
            outcome = EnumNavigationOutcome.UNKNOWN

        path = RetrievedPath(
            path_id=point_id,
            steps=filtered_steps,
            original_step_count=len(raw_steps),
            goal=goal,
            similarity_score=max(0.0, min(1.0, score)),
            outcome=outcome,
            graph_fingerprint=graph_fingerprint,
        )
        return path, stale_count

    except Exception as exc:
        logger.warning("Failed to build RetrievedPath from result: %s", exc)
        return None


# =============================================================================
# Core retrieval logic
# =============================================================================


async def _retrieve_paths(
    input_data: ModelNavigationRetrieveInput,
    embedder: ProtocolNavigationEmbedder,
    vector_store: ProtocolNavigationVectorStore,
) -> ModelNavigationRetrieveOutput:
    """Core retrieval logic (no timeout wrapper).

    Args:
        input_data: The retrieval request.
        embedder: Embedding protocol implementation.
        vector_store: Qdrant vector store protocol implementation.

    Returns:
        ModelNavigationRetrieveOutput with retrieved paths.
    """
    # Ensure collection exists (creates if needed — cold start safe)
    collection_exists = await vector_store.ensure_collection(
        collection=input_data.qdrant_collection,
        dimension=_EMBEDDING_DIMENSION,
        distance=_QDRANT_DISTANCE,
    )

    if not collection_exists:
        logger.warning(
            "Could not ensure Qdrant collection %s — returning empty list",
            input_data.qdrant_collection,
        )
        return ModelNavigationRetrieveOutput(
            paths=(),
            collection_exists=False,
            correlation_id=input_data.correlation_id,
        )

    # Build embedding text and embed
    embedding_text = _build_embedding_text(input_data)
    try:
        query_vector = await embedder.embed_text(embedding_text)
    except Exception as exc:
        logger.warning(
            "Embedding failed for navigation query: %s",
            exc,
            extra={"correlation_id": input_data.correlation_id},
        )
        return ModelNavigationRetrieveOutput(
            paths=(),
            collection_exists=True,
            correlation_id=input_data.correlation_id,
        )

    # Build hard filters and query Qdrant
    hard_filter = _build_hard_filter(input_data)

    # Fetch more than top_k to account for hard filtering
    fetch_limit = input_data.top_k * 5

    raw_results = await vector_store.search_similar(
        collection=input_data.qdrant_collection,
        query_vector=query_vector,
        top_k=fetch_limit,
        filter_must=hard_filter,
    )

    total_candidates = len(raw_results)

    # Build RetrievedPath objects with staleness filtering.
    # Note: hard filters (component_type, datasource_class, policy_tier) are applied
    # at the Qdrant query level via filter_must. hard_filtered_count here tracks
    # results that could not be deserialized (parse failures), not Qdrant-level
    # hard-filter exclusions.
    paths: list[RetrievedPath] = []
    hard_filtered_count = 0
    total_stale_steps = 0

    for result in raw_results:
        built = _build_retrieved_path(result, input_data.graph)
        if built is None:
            # Count parse/deserialization failures separately from Qdrant hard filters
            hard_filtered_count += 1
            continue
        path, stale_count = built
        total_stale_steps += stale_count
        paths.append(path)

    # Sort by similarity descending (should already be sorted, but enforce)
    paths.sort(key=lambda p: p.similarity_score, reverse=True)

    # Take top_k
    top_paths = paths[: input_data.top_k]

    logger.info(
        "NavigationRetriever: retrieved %d paths (candidates=%d, hard_filtered=%d, "
        "stale_steps=%d, correlation_id=%s)",
        len(top_paths),
        total_candidates,
        hard_filtered_count,
        total_stale_steps,
        input_data.correlation_id,
    )

    return ModelNavigationRetrieveOutput(
        paths=tuple(top_paths),
        timed_out=False,
        collection_exists=True,
        total_candidates=total_candidates,
        hard_filtered_count=hard_filtered_count,
        stale_steps_filtered=total_stale_steps,
        correlation_id=input_data.correlation_id,
    )


# =============================================================================
# Main handler
# =============================================================================


async def handle_navigation_retrieve(
    input_data: ModelNavigationRetrieveInput,
    *,
    embedder: ProtocolNavigationEmbedder | None = None,
    vector_store: ProtocolNavigationVectorStore | None = None,
) -> ModelNavigationRetrieveOutput:
    """Retrieve ranked prior navigation paths from OmniMemory.

    Wraps core retrieval with a timeout. On timeout or any unhandled
    error, returns an empty list — retrieval is advisory only and must
    never block navigation.

    Args:
        input_data: Retrieval request with goal, state, graph, and config.
        embedder: Optional embedding client (injected for testing).
                  If None, creates a production EmbeddingClient.
        vector_store: Optional Qdrant client (injected for testing).
                      If None, creates a production QdrantNavigationStore.

    Returns:
        ModelNavigationRetrieveOutput. On timeout: timed_out=True, paths=().
        On cold start: paths=() with collection_exists=True.
    """
    # Late imports to avoid circular dependencies in production path
    if embedder is None:
        from omniintelligence.nodes.node_navigation_retriever_effect.handlers._production_clients import (
            ProductionNavigationEmbedder,
        )

        embedder = ProductionNavigationEmbedder(embedding_url=input_data.embedding_url)

    if vector_store is None:
        from omniintelligence.nodes.node_navigation_retriever_effect.handlers._production_clients import (
            ProductionNavigationVectorStore,
        )

        vector_store = ProductionNavigationVectorStore(qdrant_url=input_data.qdrant_url)

    try:
        result = await asyncio.wait_for(
            _retrieve_paths(input_data, embedder, vector_store),
            timeout=input_data.timeout_seconds,
        )
        return result

    except TimeoutError:
        logger.warning(
            "NavigationRetriever timed out after %.1fs (correlation_id=%s) — "
            "returning empty list",
            input_data.timeout_seconds,
            input_data.correlation_id,
        )
        return ModelNavigationRetrieveOutput(
            paths=(),
            timed_out=True,
            collection_exists=True,
            correlation_id=input_data.correlation_id,
        )

    except Exception as exc:
        logger.warning(
            "NavigationRetriever failed (correlation_id=%s): %s — returning empty list",
            input_data.correlation_id,
            exc,
        )
        return ModelNavigationRetrieveOutput(
            paths=(),
            timed_out=False,
            collection_exists=True,
            correlation_id=input_data.correlation_id,
        )


__all__ = [
    "handle_navigation_retrieve",
    "ProtocolNavigationEmbedder",
    "ProtocolNavigationVectorStore",
]
