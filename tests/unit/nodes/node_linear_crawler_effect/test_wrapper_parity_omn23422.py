# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity checks for the HandlerLinearCrawl wrapper (OMN-23422).

The contract-bound wrapper must return exactly what the preserved module
function ``handle_linear_crawl`` returns for the same request and the same
dependencies. The Linear client and state store are the in-memory fakes the
node's own tests use; the state store is wrapped to record every write so the
persisted state and the call sequence are compared as well as the output.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_linear_crawler_effect.handlers.handler_linear_crawl import (
    handle_linear_crawl,
)
from omniintelligence.nodes.node_linear_crawler_effect.handlers.protocol_linear_state import (
    ModelLinearStateEntry,
)
from omniintelligence.nodes.node_linear_crawler_effect.models.model_linear_crawl_input import (
    ModelLinearCrawlInput,
)
from omniintelligence.nodes.node_linear_crawler_effect.node_tests.conftest import (
    MockLinearClient,
)
from omniintelligence.nodes.node_linear_crawler_effect.node_tests.container.container_linear_state_store import (
    InMemoryLinearStateStore,
)

MODULE = (
    "omniintelligence.nodes.node_linear_crawler_effect.handlers.handler_linear_crawl"
)
WRAPPER_CLASS = "HandlerLinearCrawl"

SCOPE = "omninode/test"
TEAM_ID = "omninode"


def _fp(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


class _RecordingStore(InMemoryLinearStateStore):
    """In-memory state store that records every mutating call."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, Any]] = []

    async def upsert_entry(self, entry: ModelLinearStateEntry) -> None:
        self.calls.append(("upsert", entry))
        await super().upsert_entry(entry)

    async def delete_entry(self, crawl_scope: str, source_ref: str) -> None:
        self.calls.append(("delete", (crawl_scope, source_ref)))
        await super().delete_entry(crawl_scope, source_ref)


def _request(project_id: str | None = None) -> ModelLinearCrawlInput:
    return ModelLinearCrawlInput(
        team_id=TEAM_ID,
        crawl_scope=SCOPE,
        project_id=project_id,
        correlation_id="corr-1",
    )


def _state_entry(ref: str, version: str, markdown: str) -> ModelLinearStateEntry:
    return ModelLinearStateEntry(
        crawl_scope=SCOPE,
        source_ref=ref,
        source_version=version,
        content_fingerprint=_fp(markdown),
    )


def _seed(store: _RecordingStore, entries: list[ModelLinearStateEntry]) -> None:
    for entry in entries:
        store._entries[(entry.crawl_scope, entry.source_ref)] = entry


def _deps_new_items() -> dict[str, Any]:
    client = MockLinearClient()
    client.add_issue("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1\n\nContent")
    client.add_document("doc-abc", "2026-01-15T00:00:00Z", "# Design Doc")
    return {"linear_state": _RecordingStore(), "linear_client": client}


def _deps_unchanged() -> dict[str, Any]:
    client = MockLinearClient()
    client.add_issue("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1")
    store = _RecordingStore()
    _seed(store, [_state_entry("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1")])
    return {"linear_state": store, "linear_client": client}


def _deps_content_changed() -> dict[str, Any]:
    client = MockLinearClient()
    client.add_issue("OMN-1", "2026-02-01T00:00:00Z", "# Ticket 1\n\nEdited body")
    client.add_document("doc-abc", "2026-02-02T00:00:00Z", "# Design Doc v2")
    store = _RecordingStore()
    _seed(
        store,
        [
            _state_entry("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1"),
            _state_entry("doc-abc", "2026-01-15T00:00:00Z", "# Design Doc"),
        ],
    )
    return {"linear_state": store, "linear_client": client}


def _deps_metadata_only() -> dict[str, Any]:
    client = MockLinearClient()
    client.add_issue("OMN-1", "2026-03-01T00:00:00Z", "# Ticket 1")
    store = _RecordingStore()
    _seed(store, [_state_entry("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1")])
    return {"linear_state": store, "linear_client": client}


def _deps_removed() -> dict[str, Any]:
    client = MockLinearClient()
    client.add_issue("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1")
    store = _RecordingStore()
    _seed(
        store,
        [
            _state_entry("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1"),
            _state_entry("OMN-GONE", "2025-12-01T00:00:00Z", "# Old"),
            _state_entry("doc-gone", "2025-12-02T00:00:00Z", "# Old doc"),
        ],
    )
    return {"linear_state": store, "linear_client": client}


def _deps_list_issues_error() -> dict[str, Any]:
    client = MockLinearClient()
    client.add_issue("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1")
    client.list_issues_error = RuntimeError("rate limited")
    return {"linear_state": _RecordingStore(), "linear_client": client}


def _deps_list_documents_error() -> dict[str, Any]:
    client = MockLinearClient()
    client.add_issue("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1")
    client.list_docs_error = ConnectionError("linear unreachable")
    return {"linear_state": _RecordingStore(), "linear_client": client}


def _deps_fetch_errors() -> dict[str, Any]:
    client = MockLinearClient()
    client.add_issue("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1")
    client.add_issue("OMN-2", "2026-01-02T00:00:00Z", "# Ticket 2")
    client.add_document("doc-missing", "2026-01-03T00:00:00Z", "# never served")
    del client.doc_contents["doc-missing"]
    client.fetch_errors["OMN-1"] = RuntimeError("fetch failed")
    return {"linear_state": _RecordingStore(), "linear_client": client}


def _deps_empty_remote_and_state() -> dict[str, Any]:
    return {"linear_state": _RecordingStore(), "linear_client": MockLinearClient()}


def _deps_everything() -> dict[str, Any]:
    client = MockLinearClient()
    client.add_issue("OMN-1", "2026-01-01T00:00:00Z", "# unchanged", project_id="p1")
    client.add_issue("OMN-2", "2026-04-01T00:00:00Z", "# changed body", project_id="p1")
    client.add_issue("OMN-3", "2026-04-02T00:00:00Z", "# brand new", project_id="p1")
    client.add_document("doc-1", "2026-04-03T00:00:00Z", "# doc meta only")
    store = _RecordingStore()
    _seed(
        store,
        [
            _state_entry("OMN-1", "2026-01-01T00:00:00Z", "# unchanged"),
            _state_entry("OMN-2", "2026-02-01T00:00:00Z", "# older body"),
            _state_entry("doc-1", "2026-02-02T00:00:00Z", "# doc meta only"),
            _state_entry("OMN-GONE", "2025-12-01T00:00:00Z", "# removed"),
        ],
    )
    return {"linear_state": store, "linear_client": client}


PARITY_CASES: list[
    tuple[str, str, Callable[[], BaseModel], Callable[[], dict[str, Any]]]
] = [
    ("new-items-discovered", WRAPPER_CLASS, _request, _deps_new_items),
    ("unchanged-updated-at-skipped", WRAPPER_CLASS, _request, _deps_unchanged),
    ("content-changed", WRAPPER_CLASS, _request, _deps_content_changed),
    ("metadata-only-update", WRAPPER_CLASS, _request, _deps_metadata_only),
    ("removed-items", WRAPPER_CLASS, _request, _deps_removed),
    ("list-issues-error", WRAPPER_CLASS, _request, _deps_list_issues_error),
    (
        "list-documents-error",
        WRAPPER_CLASS,
        lambda: _request("proj-1"),
        _deps_list_documents_error,
    ),
    ("per-item-fetch-errors", WRAPPER_CLASS, _request, _deps_fetch_errors),
    ("empty-remote-and-state", WRAPPER_CLASS, _request, _deps_empty_remote_and_state),
    (
        "mixed-all-branches",
        WRAPPER_CLASS,
        lambda: _request("p1"),
        _deps_everything,
    ),
]


def _to_json(value: Any) -> Any:
    def default(obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        return str(obj)

    return json.loads(json.dumps(value, default=default))


def corpus_inputs() -> list[dict[str, Any]]:
    """JSON-describable request per parity case, in PARITY_CASES order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": _to_json(request_builder()),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


def _observed(deps: dict[str, Any]) -> dict[str, Any]:
    """Everything the fakes recorded or persisted during one run."""
    store: _RecordingStore = deps["linear_state"]
    client: MockLinearClient = deps["linear_client"]
    return {
        "state": dict(store._entries),
        "store_calls": list(store.calls),
        "fetched_issues": list(client.fetched_issues),
        "fetched_docs": list(client.fetched_docs),
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], BaseModel],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """Wrapper and preserved function return or raise alike with equal effects."""
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
        function_result = await handle_linear_crawl(request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None, "wrapper must raise like the function"
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result

    assert _observed(deps_a) == _observed(deps_b)
