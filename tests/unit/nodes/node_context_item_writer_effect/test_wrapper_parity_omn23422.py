# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerContextItemWrite (OMN-23422).

The contract-bound handler ``HandlerContextItemWrite.handle`` must return exactly
what the preserved function ``handle_context_item_write`` returns for the same
request and the same injected stores, and must drive the stores identically.
``uuid.uuid4`` is replaced by a deterministic sequence so the generated item ids
(which appear in the recorded store calls) are comparable. Cases cover the
create, update and skip outcomes, per-chunk store failures, the event emitter
branches, and a missing required dependency.
"""

import importlib
import json
import uuid
from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_chunk_classifier_compute.models.enum_context_item_type import (
    EnumContextItemType,
)
from omniintelligence.nodes.node_context_item_writer_effect.handlers.handler_context_item_writer import (
    handle_context_item_write,
)
from omniintelligence.nodes.node_context_item_writer_effect.models.enum_bootstrap_tier import (
    EnumBootstrapTier,
)
from omniintelligence.nodes.node_context_item_writer_effect.models.model_context_item_write_input import (
    ModelContextItemWriteInput,
)
from omniintelligence.nodes.node_context_item_writer_effect.models.model_tier_policy import (
    ModelTierPolicy,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedded_chunk import (
    ModelEmbeddedChunk,
)

_MODULE = (
    "omniintelligence.nodes.node_context_item_writer_effect.handlers."
    "handler_context_item_writer"
)
_WRAPPER_CLASS = "HandlerContextItemWrite"
_SOURCE_REF = "docs/guide.md"
_QDRANT_URL = "http://qdrant.invalid:6333"
_EXISTING_ID = UUID("00000000-0000-0000-0000-0000000000aa")


class FakeContextStore:
    """In-memory ``ProtocolContextStore`` recording each call."""

    def __init__(
        self,
        existing: dict[tuple[int, int], tuple[UUID, str]] | None = None,
        lookup_error: Exception | None = None,
        insert_error: Exception | None = None,
    ) -> None:
        self._existing = existing or {}
        self._lookup_error = lookup_error
        self._insert_error = insert_error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def lookup_by_position(
        self, *, source_ref: str, offset_start: int, offset_end: int
    ) -> tuple[UUID, str] | None:
        self.calls.append(
            (
                "lookup_by_position",
                {
                    "source_ref": source_ref,
                    "offset_start": offset_start,
                    "offset_end": offset_end,
                },
            )
        )
        if self._lookup_error is not None:
            raise self._lookup_error
        return self._existing.get((offset_start, offset_end))

    async def insert_item(
        self, *, chunk: ModelEmbeddedChunk, tier_policy: ModelTierPolicy, item_id: UUID
    ) -> None:
        self.calls.append(
            (
                "insert_item",
                {"chunk": chunk, "tier_policy": tier_policy, "item_id": item_id},
            )
        )
        if self._insert_error is not None:
            raise self._insert_error

    async def update_item_fingerprint(
        self, *, item_id: UUID, chunk: ModelEmbeddedChunk
    ) -> None:
        self.calls.append(
            ("update_item_fingerprint", {"item_id": item_id, "chunk": chunk})
        )


class FakeVectorStore:
    """In-memory ``ProtocolVectorStore`` recording each call."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def upsert_vector(
        self,
        *,
        point_id: UUID,
        vector: tuple[float, ...],
        payload: dict[str, object],
        collection: str,
    ) -> None:
        self.calls.append(
            {
                "point_id": point_id,
                "vector": vector,
                "payload": payload,
                "collection": collection,
            }
        )
        if self._error is not None:
            raise self._error


class FakeGraphStore:
    """In-memory ``ProtocolGraphStore`` recording each call."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def upsert_context_item_edge(
        self, *, item_id: UUID, source_ref: str, crawl_scope: str, item_type: str
    ) -> None:
        self.calls.append(
            {
                "item_id": item_id,
                "source_ref": source_ref,
                "crawl_scope": crawl_scope,
                "item_type": item_type,
            }
        )
        if self._error is not None:
            raise self._error


class FakeEventEmitter:
    """In-memory ``ProtocolEventEmitter`` recording each call."""

    def __init__(self, result: bool = True, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def emit_document_indexed(
        self,
        *,
        source_ref: str,
        items_created: int,
        items_updated: int,
        items_skipped: int,
        items_failed: int,
        correlation_id: str | None,
    ) -> bool:
        self.calls.append(
            {
                "source_ref": source_ref,
                "items_created": items_created,
                "items_updated": items_updated,
                "items_skipped": items_skipped,
                "items_failed": items_failed,
                "correlation_id": correlation_id,
            }
        )
        if self._error is not None:
            raise self._error
        return self._result


def _chunk(
    index: int,
    fingerprint: str | None = None,
    source_ref: str = _SOURCE_REF,
    item_type: EnumContextItemType = EnumContextItemType.DOC_EXCERPT,
) -> ModelEmbeddedChunk:
    start = index * 100
    return ModelEmbeddedChunk(
        content=f"chunk body {index}",
        section_heading=f"Section {index}",
        item_type=item_type,
        tags=("alpha", f"tag-{index}"),
        content_fingerprint=fingerprint or f"fp-{index}",
        version_hash=f"vh-{index}",
        character_offset_start=start,
        character_offset_end=start + 99,
        token_estimate=4,
        source_ref=source_ref,
        crawl_scope="omninode/omniintelligence",
        source_version="sha-1",
        embedding=(0.1 * (index + 1), 0.2, 0.3),
    )


def _build_request(
    chunks: tuple[ModelEmbeddedChunk, ...] = (),
    **overrides: Any,
) -> ModelContextItemWriteInput:
    values: dict[str, Any] = {
        "embedded_chunks": chunks,
        "source_ref": _SOURCE_REF,
        "crawl_scope": "omninode/omniintelligence",
        "qdrant_url": _QDRANT_URL,
        "correlation_id": "corr-omn-23422",
    }
    values.update(overrides)
    return ModelContextItemWriteInput(**values)


def _deps(
    *,
    context_store: FakeContextStore | None = None,
    vector_store: FakeVectorStore | None = None,
    graph_store: FakeGraphStore | None = None,
    event_emitter: FakeEventEmitter | None = None,
) -> dict[str, Any]:
    deps: dict[str, Any] = {
        "context_store": context_store or FakeContextStore(),
        "vector_store": vector_store or FakeVectorStore(),
        "graph_store": graph_store or FakeGraphStore(),
    }
    if event_emitter is not None:
        deps["event_emitter"] = event_emitter
    return deps


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], ModelContextItemWriteInput],
        Callable[[], dict[str, Any]],
    ]
] = [
    # Empty input short-circuits before any store is touched.
    (
        "empty-chunks",
        _WRAPPER_CLASS,
        _build_request,
        lambda: _deps(event_emitter=FakeEventEmitter()),
    ),
    # Normal path: two fresh chunks are created in all stores and the event is emitted.
    (
        "create-two-chunks",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0), _chunk(1))),
        lambda: _deps(event_emitter=FakeEventEmitter()),
    ),
    # Skip outcome: stored fingerprint equals the chunk fingerprint.
    (
        "skip-unchanged",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0, fingerprint="same"),)),
        lambda: _deps(
            context_store=FakeContextStore({(0, 99): (_EXISTING_ID, "same")}),
            event_emitter=FakeEventEmitter(),
        ),
    ),
    # Update outcome: stored fingerprint differs, vector replaced, no graph write.
    (
        "update-changed-fingerprint",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0, fingerprint="new"),)),
        lambda: _deps(
            context_store=FakeContextStore({(0, 99): (_EXISTING_ID, "old")}),
            event_emitter=FakeEventEmitter(),
        ),
    ),
    # All three outcomes in one document.
    (
        "mixed-create-update-skip",
        _WRAPPER_CLASS,
        lambda: _build_request(
            chunks=(
                _chunk(0, fingerprint="same"),
                _chunk(1, fingerprint="new"),
                _chunk(2),
            )
        ),
        lambda: _deps(
            context_store=FakeContextStore(
                {(0, 99): (_EXISTING_ID, "same"), (100, 199): (_EXISTING_ID, "old")}
            ),
            event_emitter=FakeEventEmitter(),
        ),
    ),
    # Tier policy: a CLAUDE.md source maps to the validated tier through a custom table.
    (
        "custom-tier-policy",
        _WRAPPER_CLASS,
        lambda: _build_request(
            chunks=(
                _chunk(
                    0,
                    source_ref="repo/CLAUDE.md",
                    item_type=EnumContextItemType.RULE,
                ),
            ),
            source_ref="repo/CLAUDE.md",
            tier_policies=(
                ModelTierPolicy(
                    pattern="*/CLAUDE.md",
                    tier=EnumBootstrapTier.VALIDATED,
                    bootstrap_confidence=0.9,
                    expires_after_runs=3,
                ),
            ),
        ),
        lambda: _deps(),
    ),
    # Event branch: emit_event disabled, emitter is never called.
    (
        "emit-disabled",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0),), emit_event=False),
        lambda: _deps(event_emitter=FakeEventEmitter()),
    ),
    # Event branch: no emitter injected.
    (
        "no-emitter",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0),)),
        lambda: _deps(),
    ),
    # Event branch: emitter reports that it did not emit.
    (
        "emitter-returns-false",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0),)),
        lambda: _deps(event_emitter=FakeEventEmitter(result=False)),
    ),
    # Error path: emitter raises, the failure is swallowed.
    (
        "emitter-raises",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0),)),
        lambda: _deps(
            event_emitter=FakeEventEmitter(error=RuntimeError("event bus down"))
        ),
    ),
    # Error path: the lookup raises, the chunk is counted as failed.
    (
        "lookup-failure",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0), _chunk(1))),
        lambda: _deps(
            context_store=FakeContextStore(lookup_error=RuntimeError("pg unavailable")),
            event_emitter=FakeEventEmitter(),
        ),
    ),
    # Error path: the insert raises before the vector and graph stores are reached.
    (
        "insert-failure",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0),)),
        lambda: _deps(
            context_store=FakeContextStore(insert_error=RuntimeError("insert failed")),
            event_emitter=FakeEventEmitter(),
        ),
    ),
    # Error path: the vector store raises for a fresh chunk.
    (
        "vector-failure",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0), _chunk(1))),
        lambda: _deps(
            vector_store=FakeVectorStore(error=RuntimeError("qdrant unavailable")),
            event_emitter=FakeEventEmitter(),
        ),
    ),
    # Error path: the graph store raises after the vector write.
    (
        "graph-failure",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0),)),
        lambda: _deps(
            graph_store=FakeGraphStore(error=RuntimeError("memgraph unavailable")),
            event_emitter=FakeEventEmitter(),
        ),
    ),
    # Error path: a required store dependency is missing, so the call itself fails.
    (
        "missing-graph-store",
        _WRAPPER_CLASS,
        lambda: _build_request(chunks=(_chunk(0),)),
        lambda: {
            "context_store": FakeContextStore(),
            "vector_store": FakeVectorStore(),
        },
    ),
]


def _deterministic_uuid4() -> Callable[[], UUID]:
    """Return a ``uuid4`` replacement yielding a fresh predictable sequence."""
    counter = iter(range(1, 10_000))

    def _next() -> UUID:
        return UUID(int=next(counter))

    return _next


async def _invoke_preserved(
    request: ModelContextItemWriteInput, dependencies: dict[str, Any]
) -> Any:
    """Call the preserved function exactly as the wrapper's forwarding line does."""
    return await handle_context_item_write(request, **dependencies)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _cls, _req, _deps in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], ModelContextItemWriteInput],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper handle() and the preserved handle_context_item_write() agree."""
    module = importlib.import_module(_MODULE)
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_for_wrapper = request_builder()
    request_for_function = request_builder()
    deps_for_wrapper = deps_builder()
    deps_for_function = deps_builder()

    wrapper_result: Any = None
    wrapper_error: Exception | None = None
    monkeypatch.setattr(uuid, "uuid4", _deterministic_uuid4())
    try:
        wrapper_result = await wrapper_cls(**deps_for_wrapper).handle(
            request_for_wrapper
        )
    except Exception as exc:  # captured deliberately for parity comparison
        wrapper_error = exc

    function_result: Any = None
    function_error: Exception | None = None
    monkeypatch.setattr(uuid, "uuid4", _deterministic_uuid4())
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
