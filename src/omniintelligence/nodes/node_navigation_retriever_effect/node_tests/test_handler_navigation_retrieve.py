# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handler_navigation_retrieve — NavigationRetrieverEffect.

All tests use mocked embedder and vector_store. No live embedding server
or Qdrant instance required.

Test coverage:
    - Happy path: paths returned and ranked by similarity
    - Hard filtering: incompatible types excluded
    - Staleness filtering: steps not in current graph removed
    - Cold start: empty collection returns empty list without error
    - Timeout: graceful fallback to empty list (timed_out=True)
    - Embedding failure: graceful fallback to empty list
    - Qdrant failure: graceful fallback to empty list
    - Top-K capping: returns at most top_k paths
    - Correlation ID propagation
    - Output model frozen

Ticket: OMN-2579
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from omniintelligence.nodes.node_navigation_retriever_effect.handlers.handler_navigation_retrieve import (
    ProtocolNavigationEmbedder,
    ProtocolNavigationVectorStore,
    _build_hard_filter,
    _filter_stale_steps,
    _serialize_goal_for_embedding,
    handle_navigation_retrieve,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.enum_navigation_outcome import (
    EnumNavigationOutcome,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_contract_graph import (
    ContractGraph,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_contract_state import (
    ContractState,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_goal_condition import (
    GoalCondition,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_navigation_retrieve_input import (
    ModelNavigationRetrieveInput,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_plan_step import (
    PlanStep,
)

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

_FAKE_EMBEDDING = [0.1] * 1024


def _make_goal(
    goal_id: str = "goal-001",
    component_type: str = "api_gateway",
    datasource_class: str = "rest",
    policy_tier: str = "tier_2",
) -> GoalCondition:
    return GoalCondition(
        goal_id=goal_id,
        target_component_type=component_type,
        target_datasource_class=datasource_class,
        target_policy_tier=policy_tier,
        description="Test goal",
    )


def _make_state(
    node_id: str = "node-start",
    component_type: str = "api_gateway",
    datasource_class: str = "rest",
    policy_tier: str = "tier_2",
    graph_fingerprint: str = "sha256:abc123",
    available_transitions: frozenset[str] | None = None,
) -> ContractState:
    return ContractState(
        node_id=node_id,
        component_type=component_type,
        datasource_class=datasource_class,
        policy_tier=policy_tier,
        graph_fingerprint=graph_fingerprint,
        available_transitions=available_transitions or frozenset(["to_auth", "to_cache"]),
    )


def _make_graph(
    graph_id: str = "graph-001",
    fingerprint: str = "sha256:abc123",
    valid_transitions: frozenset[tuple[str, str]] | None = None,
) -> ContractGraph:
    resolved = (
        frozenset([("node-start", "to_auth"), ("node-auth", "to_cache")])
        if valid_transitions is None
        else valid_transitions
    )
    return ContractGraph(
        graph_id=graph_id,
        fingerprint=fingerprint,
        valid_transitions=resolved,
    )


def _make_step(
    from_node: str = "node-start",
    to_node: str = "node-auth",
    action: str = "to_auth",
    component_type: str = "api_gateway",
    datasource_class: str = "rest",
    policy_tier: str = "tier_2",
) -> PlanStep:
    return PlanStep(
        from_node_id=from_node,
        to_node_id=to_node,
        action=action,
        component_type=component_type,
        datasource_class=datasource_class,
        policy_tier=policy_tier,
    )


def _make_qdrant_result(
    point_id: str = "path-001",
    score: float = 0.9,
    steps: list[PlanStep] | None = None,
    goal: GoalCondition | None = None,
    outcome: str = "success",
    graph_fingerprint: str = "sha256:abc123",
) -> dict[str, Any]:
    if steps is None:
        steps = [_make_step()]
    if goal is None:
        goal = _make_goal()
    return {
        "id": point_id,
        "score": score,
        "payload": {
            "component_type": goal.target_component_type,
            "datasource_class": goal.target_datasource_class,
            "policy_tier": goal.target_policy_tier,
            "outcome": outcome,
            "graph_fingerprint": graph_fingerprint,
            "steps_json": json.dumps([s.model_dump() for s in steps]),
            "goal_json": goal.model_dump_json(),
        },
    }


def _make_input(
    goal: GoalCondition | None = None,
    state: ContractState | None = None,
    graph: ContractGraph | None = None,
    top_k: int = 3,
    timeout_seconds: float = 2.0,
    correlation_id: str | None = "corr-001",
) -> ModelNavigationRetrieveInput:
    return ModelNavigationRetrieveInput(
        goal=goal or _make_goal(),
        current_state=state or _make_state(),
        graph=graph or _make_graph(),
        top_k=top_k,
        timeout_seconds=timeout_seconds,
        correlation_id=correlation_id,
    )


def _make_mock_embedder(
    embedding: list[float] | None = None,
    side_effect: Exception | None = None,
) -> ProtocolNavigationEmbedder:
    mock = MagicMock(spec=ProtocolNavigationEmbedder)
    if side_effect is not None:
        mock.embed_text = AsyncMock(side_effect=side_effect)
    else:
        mock.embed_text = AsyncMock(return_value=embedding or _FAKE_EMBEDDING)
    return mock


def _make_mock_vector_store(
    search_results: list[dict[str, Any]] | None = None,
    ensure_collection_result: bool = True,
    search_side_effect: Exception | None = None,
) -> ProtocolNavigationVectorStore:
    mock = MagicMock(spec=ProtocolNavigationVectorStore)
    mock.ensure_collection = AsyncMock(return_value=ensure_collection_result)
    if search_side_effect is not None:
        mock.search_similar = AsyncMock(side_effect=search_side_effect)
    else:
        mock.search_similar = AsyncMock(return_value=search_results or [])
    return mock


# ---------------------------------------------------------------------------
# Happy path tests
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Paths retrieved and returned sorted by similarity."""

    @pytest.mark.asyncio
    async def test_single_path_returned(self) -> None:
        result_data = [_make_qdrant_result(score=0.9)]
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=result_data)

        result = await handle_navigation_retrieve(
            _make_input(), embedder=embedder, vector_store=vector_store
        )

        assert len(result.paths) == 1
        assert result.paths[0].similarity_score == 0.9
        assert result.timed_out is False
        assert result.collection_exists is True

    @pytest.mark.asyncio
    async def test_paths_sorted_by_similarity_descending(self) -> None:
        result_data = [
            _make_qdrant_result(point_id="path-1", score=0.7),
            _make_qdrant_result(point_id="path-2", score=0.95),
            _make_qdrant_result(point_id="path-3", score=0.8),
        ]
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=result_data)

        result = await handle_navigation_retrieve(
            _make_input(top_k=3), embedder=embedder, vector_store=vector_store
        )

        assert len(result.paths) == 3
        assert result.paths[0].similarity_score == 0.95
        assert result.paths[1].similarity_score == 0.8
        assert result.paths[2].similarity_score == 0.7

    @pytest.mark.asyncio
    async def test_correlation_id_propagated(self) -> None:
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=[])

        result = await handle_navigation_retrieve(
            _make_input(correlation_id="test-corr-xyz"),
            embedder=embedder,
            vector_store=vector_store,
        )

        assert result.correlation_id == "test-corr-xyz"

    @pytest.mark.asyncio
    async def test_outcome_success_parsed(self) -> None:
        result_data = [_make_qdrant_result(outcome="success")]
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=result_data)

        result = await handle_navigation_retrieve(
            _make_input(), embedder=embedder, vector_store=vector_store
        )

        assert result.paths[0].outcome == EnumNavigationOutcome.SUCCESS

    @pytest.mark.asyncio
    async def test_outcome_failure_parsed(self) -> None:
        result_data = [_make_qdrant_result(outcome="failure")]
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=result_data)

        result = await handle_navigation_retrieve(
            _make_input(), embedder=embedder, vector_store=vector_store
        )

        assert result.paths[0].outcome == EnumNavigationOutcome.FAILURE

    @pytest.mark.asyncio
    async def test_unknown_outcome_on_invalid_string(self) -> None:
        result_data = [_make_qdrant_result(outcome="bogus_value")]
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=result_data)

        result = await handle_navigation_retrieve(
            _make_input(), embedder=embedder, vector_store=vector_store
        )

        assert result.paths[0].outcome == EnumNavigationOutcome.UNKNOWN


# ---------------------------------------------------------------------------
# Cold start tests
# ---------------------------------------------------------------------------


class TestColdStart:
    """Empty collection returns empty list without error."""

    @pytest.mark.asyncio
    async def test_empty_collection_returns_empty_list(self) -> None:
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=[])

        result = await handle_navigation_retrieve(
            _make_input(), embedder=embedder, vector_store=vector_store
        )

        assert result.paths == ()
        assert result.timed_out is False
        assert result.collection_exists is True
        assert result.total_candidates == 0

    @pytest.mark.asyncio
    async def test_cold_start_not_an_error(self) -> None:
        """Cold start must return successfully — no exceptions."""
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=[])

        result = await handle_navigation_retrieve(
            _make_input(), embedder=embedder, vector_store=vector_store
        )

        assert result is not None
        assert result.paths == ()

    @pytest.mark.asyncio
    async def test_collection_not_found_returns_empty(self) -> None:
        """When collection cannot be ensured, return empty with collection_exists=False."""
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(ensure_collection_result=False)

        result = await handle_navigation_retrieve(
            _make_input(), embedder=embedder, vector_store=vector_store
        )

        assert result.paths == ()
        assert result.collection_exists is False


# ---------------------------------------------------------------------------
# Timeout tests
# ---------------------------------------------------------------------------


class TestTimeout:
    """Graceful fallback to empty list on timeout."""

    @pytest.mark.asyncio
    async def test_timeout_returns_empty_list(self) -> None:
        """Retrieval exceeding timeout returns empty list with timed_out=True."""

        async def _slow_embed(_text: str) -> list[float]:
            await asyncio.sleep(10)  # Far exceeds timeout
            return _FAKE_EMBEDDING

        embedder = MagicMock(spec=ProtocolNavigationEmbedder)
        embedder.embed_text = _slow_embed
        vector_store = _make_mock_vector_store()

        result = await handle_navigation_retrieve(
            _make_input(timeout_seconds=0.05),  # 50ms timeout
            embedder=embedder,
            vector_store=vector_store,
        )

        assert result.paths == ()
        assert result.timed_out is True

    @pytest.mark.asyncio
    async def test_timeout_does_not_raise(self) -> None:
        """Timeout must never raise an exception."""

        async def _slow_embed(_text: str) -> list[float]:
            await asyncio.sleep(10)
            return _FAKE_EMBEDDING

        embedder = MagicMock(spec=ProtocolNavigationEmbedder)
        embedder.embed_text = _slow_embed
        vector_store = _make_mock_vector_store()

        # Should not raise
        result = await handle_navigation_retrieve(
            _make_input(timeout_seconds=0.05),
            embedder=embedder,
            vector_store=vector_store,
        )

        assert result is not None


# ---------------------------------------------------------------------------
# Embedding failure tests
# ---------------------------------------------------------------------------


class TestEmbeddingFailure:
    """Graceful fallback when embedding server fails."""

    @pytest.mark.asyncio
    async def test_embedding_failure_returns_empty_list(self) -> None:
        embedder = _make_mock_embedder(side_effect=Exception("connection refused"))
        vector_store = _make_mock_vector_store()

        result = await handle_navigation_retrieve(
            _make_input(), embedder=embedder, vector_store=vector_store
        )

        assert result.paths == ()
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_embedding_failure_does_not_raise(self) -> None:
        embedder = _make_mock_embedder(side_effect=RuntimeError("server down"))
        vector_store = _make_mock_vector_store()

        result = await handle_navigation_retrieve(
            _make_input(), embedder=embedder, vector_store=vector_store
        )

        assert result is not None


# ---------------------------------------------------------------------------
# Staleness filtering tests
# ---------------------------------------------------------------------------


class TestStalenessFiltering:
    """Steps not in current graph are removed from retrieved paths."""

    def test_valid_step_kept(self) -> None:
        step = _make_step(from_node="node-start", action="to_auth")
        graph = _make_graph(
            valid_transitions=frozenset([("node-start", "to_auth")])
        )

        filtered, stale_count = _filter_stale_steps([step], graph)

        assert len(filtered) == 1
        assert stale_count == 0

    def test_stale_step_removed(self) -> None:
        step = _make_step(from_node="node-start", action="to_old_endpoint")
        graph = _make_graph(
            valid_transitions=frozenset([("node-start", "to_auth")])
        )

        filtered, stale_count = _filter_stale_steps([step], graph)

        assert len(filtered) == 0
        assert stale_count == 1

    def test_mixed_steps_partial_filter(self) -> None:
        valid_step = _make_step(from_node="node-start", action="to_auth")
        stale_step = _make_step(from_node="node-start", action="to_deprecated")
        graph = _make_graph(
            valid_transitions=frozenset([("node-start", "to_auth")])
        )

        filtered, stale_count = _filter_stale_steps([valid_step, stale_step], graph)

        assert len(filtered) == 1
        assert filtered[0].action == "to_auth"
        assert stale_count == 1

    def test_empty_graph_transitions_removes_all(self) -> None:
        steps = [_make_step(), _make_step(action="to_cache")]
        graph = _make_graph(valid_transitions=frozenset())

        filtered, stale_count = _filter_stale_steps(steps, graph)

        assert len(filtered) == 0
        assert stale_count == 2

    @pytest.mark.asyncio
    async def test_stale_steps_counted_in_output(self) -> None:
        """Output.stale_steps_filtered reflects filtered steps across all paths."""
        stale_step = _make_step(from_node="node-start", action="old_action")
        valid_step = _make_step(from_node="node-start", action="to_auth")

        result_data = [
            _make_qdrant_result(
                point_id="path-1",
                score=0.9,
                steps=[valid_step, stale_step],
            )
        ]

        graph = _make_graph(
            valid_transitions=frozenset([("node-start", "to_auth")])
        )

        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=result_data)

        result = await handle_navigation_retrieve(
            _make_input(graph=graph), embedder=embedder, vector_store=vector_store
        )

        assert result.stale_steps_filtered == 1
        assert len(result.paths[0].steps) == 1
        assert result.paths[0].original_step_count == 2


# ---------------------------------------------------------------------------
# Hard filtering tests
# ---------------------------------------------------------------------------


class TestHardFiltering:
    """Hard filter conditions match goal target values."""

    def test_filter_uses_goal_component_type(self) -> None:
        goal = _make_goal(component_type="message_broker")
        input_data = _make_input(goal=goal)
        filters = _build_hard_filter(input_data)

        comp_filter = next(f for f in filters if f["key"] == "component_type")
        assert comp_filter["match"]["value"] == "message_broker"

    def test_filter_uses_goal_datasource_class(self) -> None:
        goal = _make_goal(datasource_class="kafka_stream")
        input_data = _make_input(goal=goal)
        filters = _build_hard_filter(input_data)

        ds_filter = next(f for f in filters if f["key"] == "datasource_class")
        assert ds_filter["match"]["value"] == "kafka_stream"

    def test_filter_uses_goal_policy_tier(self) -> None:
        goal = _make_goal(policy_tier="tier_1")
        input_data = _make_input(goal=goal)
        filters = _build_hard_filter(input_data)

        tier_filter = next(f for f in filters if f["key"] == "policy_tier")
        assert tier_filter["match"]["value"] == "tier_1"

    def test_filter_has_three_conditions(self) -> None:
        input_data = _make_input()
        filters = _build_hard_filter(input_data)

        assert len(filters) == 3


# ---------------------------------------------------------------------------
# Top-K capping tests
# ---------------------------------------------------------------------------


class TestTopKCapping:
    """Returns at most top_k paths."""

    @pytest.mark.asyncio
    async def test_top_k_limits_results(self) -> None:
        result_data = [
            _make_qdrant_result(point_id=f"path-{i}", score=float(i) / 10)
            for i in range(10)
        ]
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=result_data)

        result = await handle_navigation_retrieve(
            _make_input(top_k=3), embedder=embedder, vector_store=vector_store
        )

        assert len(result.paths) <= 3

    @pytest.mark.asyncio
    async def test_top_k_1_returns_single_best(self) -> None:
        result_data = [
            _make_qdrant_result(point_id="path-low", score=0.5),
            _make_qdrant_result(point_id="path-high", score=0.95),
        ]
        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=result_data)

        result = await handle_navigation_retrieve(
            _make_input(top_k=1), embedder=embedder, vector_store=vector_store
        )

        assert len(result.paths) == 1
        assert result.paths[0].similarity_score == 0.95


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------


class TestSerialization:
    """Goal serialization for embedding produces correct text."""

    def test_serialize_goal_includes_all_fields(self) -> None:
        goal = _make_goal(
            component_type="cache",
            datasource_class="redis",
            policy_tier="tier_3",
        )
        text = _serialize_goal_for_embedding(goal)

        assert "cache" in text
        assert "redis" in text
        assert "tier_3" in text

    def test_serialize_goal_produces_string(self) -> None:
        goal = _make_goal()
        text = _serialize_goal_for_embedding(goal)

        assert isinstance(text, str)
        assert len(text) > 0


# ---------------------------------------------------------------------------
# Output model immutability
# ---------------------------------------------------------------------------


class TestOutputImmutability:
    @pytest.mark.asyncio
    async def test_output_model_is_frozen(self) -> None:
        from pydantic import ValidationError

        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store(search_results=[])

        result = await handle_navigation_retrieve(
            _make_input(), embedder=embedder, vector_store=vector_store
        )

        # Pydantic frozen model raises ValidationError on attribute assignment
        setattr_fn = setattr
        with pytest.raises(ValidationError):
            setattr_fn(result, "timed_out", True)
