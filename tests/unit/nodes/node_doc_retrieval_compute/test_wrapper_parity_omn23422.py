# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerDocRetrieval (OMN-23422).

The contract-bound handler ``HandlerDocRetrieval.handle`` must return exactly
what the preserved function ``handle_doc_retrieval`` returns for the same
request and the same dependencies. The function is pure, so results are
compared in full. Cases cover scoring (scope, tier, intent), the similarity and
tier filters, fingerprint de-duplication, the token budget, the item cap, the
empty-input edge, and an unexpected-dependency error.
"""

import importlib
import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_doc_retrieval_compute.handlers.handler_doc_retrieval import (
    handle_doc_retrieval,
)
from omniintelligence.nodes.node_doc_retrieval_compute.models.model_doc_retrieval_input import (
    DocSourceConfig,
    ModelDocRetrievalInput,
    ModelDocSearchResult,
)

_MODULE = (
    "omniintelligence.nodes.node_doc_retrieval_compute.handlers.handler_doc_retrieval"
)
_WRAPPER_CLASS = "HandlerDocRetrieval"
_SCOPE = "omninode/omniintelligence"


def _result(
    index: int,
    *,
    similarity: float = 0.8,
    tier: str = "validated",
    source_type: str = "RULE",
    crawl_scope: str = _SCOPE,
    token_estimate: int = 100,
    bootstrap_confidence: float = 0.0,
    fingerprint: str | None = None,
) -> ModelDocSearchResult:
    return ModelDocSearchResult(
        item_id=UUID(int=index),
        similarity=similarity,
        source_ref=f"docs/doc-{index}.md",
        tier=tier,
        source_type=source_type,
        crawl_scope=crawl_scope,
        content_fingerprint=fingerprint or f"fp-{index}",
        token_estimate=token_estimate,
        bootstrap_confidence=bootstrap_confidence,
        section_heading=f"Heading {index}" if index % 2 else None,
        correlation_id="corr-omn-23422" if index % 2 else None,
    )


def _build_request(
    results: tuple[ModelDocSearchResult, ...] = (),
    **overrides: Any,
) -> ModelDocRetrievalInput:
    values: dict[str, Any] = {
        "search_results": results,
        "query_scope": _SCOPE,
        "intent_category": "default",
        "total_token_budget": 4096,
        "correlation_id": "corr-omn-23422",
    }
    values.update(overrides)
    return ModelDocRetrievalInput(**values)


def _no_deps() -> dict[str, Any]:
    return {}


PARITY_CASES: list[
    tuple[str, str, Callable[[], ModelDocRetrievalInput], Callable[[], dict[str, Any]]]
] = [
    # Edge: no candidates at all.
    ("empty-results", _WRAPPER_CLASS, _build_request, _no_deps),
    # Normal path: two validated results rank by similarity.
    (
        "two-validated",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (_result(1, similarity=0.7), _result(2, similarity=0.9))
        ),
        _no_deps,
    ),
    # Scope boost: exact repo, same org other repo, and a different org.
    (
        "scope-boost-levels",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (
                _result(1, crawl_scope=_SCOPE),
                _result(2, crawl_scope="omninode/other-repo"),
                _result(3, crawl_scope="elsewhere/repo"),
                _result(4, crawl_scope=""),
            )
        ),
        _no_deps,
    ),
    # Scope boost with scope strings in a different case and without an org slash.
    (
        "scope-boost-case-and-bare-org",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (
                _result(1, crawl_scope="OmniNode/OmniIntelligence"),
                _result(2, crawl_scope="omninode"),
            )
        ),
        _no_deps,
    ),
    # Tier multipliers: shared, validated earned, validated bootstrapped.
    (
        "tier-multipliers",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (
                _result(1, tier="shared"),
                _result(2, tier="validated", bootstrap_confidence=0.0),
                _result(3, tier="validated", bootstrap_confidence=0.5),
            )
        ),
        _no_deps,
    ),
    # Filters: quarantine and unknown tiers are excluded, shared is kept.
    (
        "tier-filter",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (
                _result(1, tier="quarantine"),
                _result(2, tier="mystery"),
                _result(3, tier="SHARED"),
            )
        ),
        _no_deps,
    ),
    # Filters: a result below the minimum similarity is excluded.
    (
        "similarity-filter",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (_result(1, similarity=0.5), _result(2, similarity=0.65))
        ),
        _no_deps,
    ),
    # Filters: bootstrapped validated items are excluded when the config forbids them.
    (
        "bootstrap-validated-disallowed",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (
                _result(1, bootstrap_confidence=0.4),
                _result(2, bootstrap_confidence=0.0),
            ),
            config=DocSourceConfig(allow_bootstrap_validated=False),
        ),
        _no_deps,
    ),
    # Intent weights: debugging favors failure patterns; an unlisted source type gets 1.0.
    (
        "intent-weights-debugging",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (
                _result(1, source_type="FAILURE_PATTERN", token_estimate=10),
                _result(2, source_type="doc_excerpt", token_estimate=10),
                _result(3, source_type="UNLISTED", token_estimate=10),
            ),
            intent_category="Debugging",
        ),
        _no_deps,
    ),
    # Intent weights: an unknown intent category falls back to weight 1.0.
    (
        "intent-weights-unknown-intent",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (_result(1, source_type="EXAMPLE"), _result(2, source_type="RULE")),
            intent_category="unheard_of",
        ),
        _no_deps,
    ),
    # Budget fraction: an override for the intent shrinks the document budget.
    (
        "budget-override-fraction",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (_result(1, token_estimate=300), _result(2, token_estimate=300)),
            intent_category="debugging",
            total_token_budget=2000,
        ),
        _no_deps,
    ),
    # Budget: an item that would overflow is skipped while a smaller one still fits.
    (
        "budget-skips-oversized",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (
                _result(1, similarity=0.99, token_estimate=900),
                _result(2, similarity=0.9, token_estimate=900),
                _result(3, similarity=0.8, token_estimate=100),
            ),
            total_token_budget=1500,
        ),
        _no_deps,
    ),
    # De-duplication: the second result with the same fingerprint is dropped.
    (
        "dedup-fingerprint",
        _WRAPPER_CLASS,
        lambda: _build_request(
            (
                _result(1, similarity=0.9, fingerprint="shared-fp"),
                _result(2, similarity=0.8, fingerprint="shared-fp"),
                _result(3, similarity=0.7),
            )
        ),
        _no_deps,
    ),
    # Item cap: only max_doc_items survive.
    (
        "max-items-cap",
        _WRAPPER_CLASS,
        lambda: _build_request(
            tuple(_result(i, similarity=0.7 + i / 100) for i in range(1, 6)),
            config=DocSourceConfig(max_doc_items=2),
        ),
        _no_deps,
    ),
    # Error path: an unexpected dependency keyword reaches the function and raises.
    (
        "unexpected-dependency",
        _WRAPPER_CLASS,
        lambda: _build_request((_result(1),)),
        lambda: {"unknown_dependency": object},
    ),
]


async def _invoke_preserved(
    request: ModelDocRetrievalInput, dependencies: dict[str, Any]
) -> Any:
    """Call the preserved function exactly as the wrapper's forwarding line does."""
    return await handle_doc_retrieval(request, **dependencies)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _cls, _req, _deps in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], ModelDocRetrievalInput],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """Wrapper handle() and the preserved handle_doc_retrieval() agree."""
    module = importlib.import_module(_MODULE)
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_for_wrapper = request_builder()
    request_for_function = request_builder()
    deps_for_wrapper = deps_builder()
    deps_for_function = deps_builder()

    wrapper_result: Any = None
    wrapper_error: Exception | None = None
    try:
        wrapper_result = await wrapper_cls(**deps_for_wrapper).handle(
            request_for_wrapper
        )
    except Exception as exc:  # captured deliberately for parity comparison
        wrapper_error = exc

    function_result: Any = None
    function_error: Exception | None = None
    try:
        function_result = await _invoke_preserved(
            request_for_function, deps_for_function
        )
    except Exception as exc:  # captured deliberately for parity comparison
        function_error = exc

    if function_error is not None or wrapper_error is not None:
        assert wrapper_error is not None, (
            f"wrapper succeeded but function raised {function_error!r}"
        )
        assert function_error is not None, (
            f"function succeeded but wrapper raised {wrapper_error!r}"
        )
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_result == function_result

    for dep_name, function_dep in deps_for_function.items():
        function_calls = getattr(function_dep, "calls", None)
        if function_calls is not None:
            assert (
                getattr(deps_for_wrapper[dep_name], "calls", None) == function_calls
            ), f"dependency {dep_name} recorded different calls"


def corpus_inputs() -> list[dict[str, Any]]:
    """Return every PARITY_CASES request as a JSON-describable dict, in order."""
    rows: list[dict[str, Any]] = []
    for case_id, class_name, request_builder, _deps_builder in PARITY_CASES:
        request = request_builder()
        payload = (
            request.model_dump(mode="json")
            if isinstance(request, BaseModel)
            else request
        )
        rows.append(
            {
                "case": case_id,
                "wrapper": class_name,
                "request": json.loads(json.dumps(payload, default=str)),
            }
        )
    return rows
