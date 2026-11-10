# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity: the contract-bound navigation-retrieve wrapper matches the preserved function.

``HandlerNavigationRetrieve.handle`` forwards its request and injected
embedder/vector-store dependencies to ``handle_navigation_retrieve``. Both are
run with identical requests and fresh in-memory fakes; the outputs and the
calls recorded by the fakes must be identical.

Ticket: OMN-23422
"""

import asyncio
import importlib
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_navigation_retriever_effect.handlers.handler_navigation_retrieve import (
    handle_navigation_retrieve,
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

MODULE = (
    "omniintelligence.nodes.node_navigation_retriever_effect.handlers."
    "handler_navigation_retrieve"
)
CLASS_NAME = "HandlerNavigationRetrieve"

_FAKE_EMBEDDING = [0.1] * 1024


class FakeEmbedder:
    """Embedder fake: returns a vector, raises, or hangs; records the texts."""

    def __init__(self, error: Exception | None = None, hang: bool = False) -> None:
        self.error = error
        self.hang = hang
        self.texts: list[str] = []

    async def embed_text(self, text: str) -> list[float]:
        self.texts.append(text)
        if self.hang:
            await asyncio.Event().wait()
        if self.error is not None:
            raise self.error
        return list(_FAKE_EMBEDDING)


class FakeVectorStore:
    """Vector-store fake that records ensure/search calls."""

    def __init__(
        self,
        results: list[dict[str, Any]] | None = None,
        *,
        ensure_result: bool = True,
        search_error: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.ensure_result = ensure_result
        self.search_error = search_error
        self.ensure_calls: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []

    async def ensure_collection(
        self, collection: str, dimension: int, distance: str
    ) -> bool:
        self.ensure_calls.append(
            {"collection": collection, "dimension": dimension, "distance": distance}
        )
        return self.ensure_result

    async def search_similar(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int,
        filter_must: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        self.search_calls.append(
            {
                "collection": collection,
                "query_vector": list(query_vector),
                "top_k": top_k,
                "filter_must": filter_must,
            }
        )
        if self.search_error is not None:
            raise self.search_error
        return [dict(r) for r in self.results]


def _goal(component_type: str = "api_gateway") -> GoalCondition:
    return GoalCondition(
        goal_id="goal-001",
        target_component_type=component_type,
        target_datasource_class="rest",
        target_policy_tier="tier_2",
        description="Test goal",
    )


def _step(
    from_node: str = "node-start", to_node: str = "node-auth", action: str = "to_auth"
) -> PlanStep:
    return PlanStep(
        from_node_id=from_node,
        to_node_id=to_node,
        action=action,
        component_type="api_gateway",
        datasource_class="rest",
        policy_tier="tier_2",
    )


def _request(
    top_k: int = 3, timeout_seconds: float = 5.0
) -> ModelNavigationRetrieveInput:
    return ModelNavigationRetrieveInput(
        goal=_goal(),
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
            valid_transitions=frozenset(
                [("node-start", "to_auth"), ("node-auth", "to_cache")]
            ),
        ),
        top_k=top_k,
        timeout_seconds=timeout_seconds,
        correlation_id="corr-001",
        embedding_url="http://localhost:8100",
        qdrant_url="http://localhost:6333",
    )


def _result(
    point_id: str = "path-001",
    score: Any = 0.9,
    steps: list[PlanStep] | None = None,
    outcome: str = "success",
    steps_json: str | None = None,
    goal_json: str | None = None,
) -> dict[str, Any]:
    chosen_steps = [_step()] if steps is None else steps
    return {
        "id": point_id,
        "score": score,
        "payload": {
            "outcome": outcome,
            "graph_fingerprint": "sha256:abc123",
            "steps_json": (
                json.dumps([s.model_dump() for s in chosen_steps])
                if steps_json is None
                else steps_json
            ),
            "goal_json": _goal().model_dump_json() if goal_json is None else goal_json,
        },
    }


def _deps(
    results: list[dict[str, Any]] | None = None,
    *,
    ensure_result: bool = True,
    embed_error: Exception | None = None,
    hang: bool = False,
    search_error: Exception | None = None,
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        return {
            "embedder": FakeEmbedder(error=embed_error, hang=hang),
            "vector_store": FakeVectorStore(
                [dict(r) for r in results] if results else None,
                ensure_result=ensure_result,
                search_error=search_error,
            ),
        }

    return build


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], ModelNavigationRetrieveInput],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "single-path",
        CLASS_NAME,
        _request,
        _deps([_result(score=0.9)]),
    ),
    (
        "sorted-and-capped-to-top-k",
        CLASS_NAME,
        lambda: _request(top_k=2),
        _deps(
            [
                _result("p1", 0.7),
                _result("p2", 0.95),
                _result("p3", 0.8),
                _result("p4", 0.6),
            ]
        ),
    ),
    (
        "stale-steps-filtered",
        CLASS_NAME,
        _request,
        _deps(
            [
                _result(
                    "stale",
                    0.8,
                    steps=[_step(), _step("node-gone", "node-x", "to_removed")],
                )
            ]
        ),
    ),
    (
        "unknown-outcome-and-score-clamped",
        CLASS_NAME,
        _request,
        _deps(
            [
                _result("hi", 1.7, outcome="bogus"),
                _result("lo", -0.4, outcome="failure"),
            ]
        ),
    ),
    (
        "bad-goal-json-skipped",
        CLASS_NAME,
        _request,
        _deps(
            [
                _result("bad-goal", 0.9, goal_json="not json"),
                _result("good", 0.5),
            ]
        ),
    ),
    (
        "bad-steps-json-yields-no-steps",
        CLASS_NAME,
        _request,
        _deps([_result("bad-steps", 0.9, steps_json="{broken")]),
    ),
    (
        "non-numeric-score-skipped",
        CLASS_NAME,
        _request,
        _deps([_result("nan-score", "high"), _result("ok", 0.4)]),
    ),
    (
        "cold-start-empty-results",
        CLASS_NAME,
        _request,
        _deps([]),
    ),
    (
        "collection-unavailable",
        CLASS_NAME,
        _request,
        _deps([_result()], ensure_result=False),
    ),
    (
        "embedding-fails",
        CLASS_NAME,
        _request,
        _deps([_result()], embed_error=RuntimeError("embedder down")),
    ),
    (
        "search-fails",
        CLASS_NAME,
        _request,
        _deps(search_error=ConnectionError("qdrant down")),
    ),
    (
        "retrieval-times-out",
        CLASS_NAME,
        lambda: _request(timeout_seconds=0.01),
        _deps([_result()], hang=True),
    ),
]


def _jsonable(value: Any) -> Any:
    """Convert a model dump to JSON data with set members in sorted order."""
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_jsonable(item) for item in value), key=lambda item: json.dumps(item)
        )
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(_jsonable(request_builder()), default=str)
            ),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], ModelNavigationRetrieveInput],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """The wrapper returns (or raises) exactly what the preserved function does."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = function_result = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = await handle_navigation_retrieve(request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
    assert deps_a["embedder"].texts == deps_b["embedder"].texts
    assert deps_a["vector_store"].ensure_calls == deps_b["vector_store"].ensure_calls
    assert deps_a["vector_store"].search_calls == deps_b["vector_store"].search_calls
    if case_id == "retrieval-times-out":
        assert function_result is not None
        assert function_result.timed_out is True
