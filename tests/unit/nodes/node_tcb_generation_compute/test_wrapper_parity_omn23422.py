# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for the TCB generation handlers (OMN-23422).

``HandlerScoreCandidate.handle`` and ``HandlerNormalizeIntent.handle`` splat the
request mapping into ``score_candidate`` and ``normalize_intent`` exactly like
the preserved functions are called, so each wrapper must return the same value
(or raise the same error) as its function for the same request and the same
dependencies. Both functions are pure and take no injected dependencies, so the
only dependency case is an unexpected keyword that must fail identically.
"""

import importlib
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic_core import to_jsonable_python

from omniintelligence.nodes.node_tcb_generation_compute.handlers.handler_candidate_scorer import (
    score_candidate,
)
from omniintelligence.nodes.node_tcb_generation_compute.handlers.handler_intent_normalizer import (
    normalize_intent,
)

_HANDLERS = "omniintelligence.nodes.node_tcb_generation_compute.handlers."
_SCORE = "HandlerScoreCandidate"
_NORMALIZE = "HandlerNormalizeIntent"

_WRAPPER_MODULES: dict[str, str] = {
    _SCORE: _HANDLERS + "handler_candidate_scorer",
    _NORMALIZE: _HANDLERS + "handler_intent_normalizer",
}
_PRESERVED: dict[str, Callable[..., Any]] = {
    _SCORE: score_candidate,
    _NORMALIZE: normalize_intent,
}

_MANIFEST: dict[str, list[str]] = {
    "omnibase_core": ["routing", "registry", "models"],
    "omniintelligence": ["intent", "pattern", "scoring"],
}


def _score_request(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "candidate_path": "src/omnibase_core/models/routing/model_route.py",
        "intent_modules": ["routing"],
        "intent_repos": ["omnibase_core"],
        "days_since_last_commit": 3,
    }
    values.update(overrides)
    return values


def _normalize_request(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "raw": "Add FK validation to the routing model in omnibase_core",
        "repo_manifest": {name: list(words) for name, words in _MANIFEST.items()},
    }
    values.update(overrides)
    return values


def _no_deps() -> dict[str, Any]:
    return {}


PARITY_CASES: list[
    tuple[str, str, Callable[[], dict[str, Any]], Callable[[], dict[str, Any]]]
] = [
    # --- score_candidate ------------------------------------------------------
    # Normal path: module keyword and repo both match, recent commit.
    ("score-full-match", _SCORE, _score_request, _no_deps),
    # Second branch: nothing matches and the file is old, so the score is zero.
    (
        "score-no-match-stale",
        _SCORE,
        lambda: _score_request(
            candidate_path="docs/readme.md",
            intent_modules=["scheduler"],
            intent_repos=["omniclaude"],
            days_since_last_commit=200,
        ),
        _no_deps,
    ),
    # Module keyword matches case-insensitively while the repo does not.
    (
        "score-module-only-mixed-case",
        _SCORE,
        lambda: _score_request(
            candidate_path="SRC/Pkg/ROUTING/Thing.py",
            intent_modules=["Routing"],
            intent_repos=[],
            days_since_last_commit=45,
        ),
        _no_deps,
    ),
    # Repo keyword matches while the module does not.
    (
        "score-repo-only",
        _SCORE,
        lambda: _score_request(intent_modules=["scheduler"], days_since_last_commit=10),
        _no_deps,
    ),
    # Volatility: a busy file saturates the volatility term.
    (
        "score-high-volatility",
        _SCORE,
        lambda: _score_request(commit_frequency_30d=25, days_since_last_commit=0),
        _no_deps,
    ),
    # Volatility: a few commits give a fractional volatility term.
    (
        "score-low-volatility",
        _SCORE,
        lambda: _score_request(commit_frequency_30d=2, days_since_last_commit=30),
        _no_deps,
    ),
    # Edge: empty candidate lists and path.
    (
        "score-empty-inputs",
        _SCORE,
        lambda: _score_request(
            candidate_path="",
            intent_modules=[],
            intent_repos=[],
            days_since_last_commit=0,
        ),
        _no_deps,
    ),
    # Error path: a non-numeric age raises a TypeError.
    (
        "score-invalid-age",
        _SCORE,
        lambda: _score_request(days_since_last_commit="three"),
        _no_deps,
    ),
    # Error path: a required keyword is missing from the request.
    (
        "score-missing-keyword",
        _SCORE,
        lambda: {"candidate_path": "src/x.py", "intent_modules": []},
        _no_deps,
    ),
    # Error path: an unexpected dependency keyword fails the call itself.
    (
        "score-unexpected-dependency",
        _SCORE,
        _score_request,
        lambda: {"unknown_dependency": object},
    ),
    # --- normalize_intent -----------------------------------------------------
    # Normal path: repo keyword match plus an explicit repo mention.
    ("normalize-repo-and-module", _NORMALIZE, _normalize_request, _no_deps),
    # Second branch: explicit repo name only, no manifest keyword in the text.
    (
        "normalize-explicit-repo-only",
        _NORMALIZE,
        lambda: _normalize_request(raw="Fix the thing in omniintelligence please"),
        _no_deps,
    ),
    # Several repos and keywords in the same text.
    (
        "normalize-multiple-repos",
        _NORMALIZE,
        lambda: _normalize_request(
            raw="Wire intent scoring into the registry and routing layers"
        ),
        _no_deps,
    ),
    # Risk and capability tags are derived from the text.
    (
        "normalize-risk-and-capability-tags",
        _NORMALIZE,
        lambda: _normalize_request(
            raw=(
                "Migrate auth token schema, optimize the kafka consumer cache, "
                "fix deadlock in async dispatch and add audit ledger embedding "
                "pattern feedback"
            ),
        ),
        _no_deps,
    ),
    # Edge: empty manifest and empty text.
    (
        "normalize-empty",
        _NORMALIZE,
        lambda: _normalize_request(raw="", repo_manifest={}),
        _no_deps,
    ),
    # Edge: text matches no repo keywords and no tag signals.
    (
        "normalize-no-matches",
        _NORMALIZE,
        lambda: _normalize_request(raw="Completely unrelated sentence"),
        _no_deps,
    ),
    # Error path: a missing manifest raises an AttributeError.
    (
        "normalize-invalid-manifest",
        _NORMALIZE,
        lambda: _normalize_request(repo_manifest=None),
        _no_deps,
    ),
    # Error path: a required keyword is missing from the request.
    (
        "normalize-missing-keyword",
        _NORMALIZE,
        lambda: {"raw": "Add routing"},
        _no_deps,
    ),
    # Error path: an unexpected dependency keyword fails the call itself.
    (
        "normalize-unexpected-dependency",
        _NORMALIZE,
        _normalize_request,
        lambda: {"unknown_dependency": object},
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _cls, _req, _deps in PARITY_CASES],
)
def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], dict[str, Any]],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """Wrapper handle() and the preserved function agree on value or error."""
    module = importlib.import_module(_WRAPPER_MODULES[class_name])
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"
    preserved = _PRESERVED[class_name]

    request_for_wrapper = request_builder()
    request_for_function = request_builder()
    deps_for_wrapper = deps_builder()
    deps_for_function = deps_builder()

    wrapper_result: Any = None
    wrapper_error: Exception | None = None
    try:
        wrapper_result = wrapper_cls(**deps_for_wrapper).handle(request_for_wrapper)
    except Exception as exc:  # captured deliberately for parity comparison
        wrapper_error = exc

    function_result: Any = None
    function_error: Exception | None = None
    try:
        function_result = preserved(**request_for_function, **deps_for_function)
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
        payload = to_jsonable_python(request_builder())
        rows.append(
            {
                "case": case_id,
                "wrapper": class_name,
                "request": json.loads(json.dumps(payload, default=str)),
            }
        )
    return rows
