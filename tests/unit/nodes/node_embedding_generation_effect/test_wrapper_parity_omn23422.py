# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity checks for the HandlerEmbeddingGenerate wrapper (OMN-23422).

The contract-bound wrapper must return exactly what the preserved module
function ``handle_embedding_generate`` returns for the same request and the
same dependencies. Embedding clients are in-memory fakes that record every
call; no network is used. The "own client" cases leave the ``client``
dependency unset and patch ``_create_client_for_provider`` on the handler
module so the production path (connect/close) is exercised against fakes.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel

from omniintelligence.adapters.embedding_client import (
    EmbeddingClientError,
    EmbeddingConnectionError,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.enum_context_item_type import (
    EnumContextItemType,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.model_classified_chunk import (
    ModelClassifiedChunk,
)
from omniintelligence.nodes.node_embedding_generation_effect.handlers import (
    handler_embedding_generate as handler_module,
)
from omniintelligence.nodes.node_embedding_generation_effect.handlers.handler_embedding_generate import (
    handle_embedding_generate,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.enum_embedding_provider import (
    EnumEmbeddingProvider,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedding_generate_input import (
    ModelEmbeddingGenerateInput,
)

MODULE = (
    "omniintelligence.nodes.node_embedding_generation_effect.handlers."
    "handler_embedding_generate"
)
WRAPPER_CLASS = "HandlerEmbeddingGenerate"

_ENDPOINTS_FILE = (
    Path(handler_module.__file__).parents[1] / "node_tests" / "test_endpoints.yaml"
)
_EMBEDDING_URL = yaml.safe_load(_ENDPOINTS_FILE.read_text())["embedding_url"]


class _FakeClient:
    """In-memory embedding client that records every call."""

    def __init__(
        self,
        batch_error: Exception | None = None,
        batch_vectors: list[list[float]] | None = None,
        individual: list[Exception | list[float]] | None = None,
    ) -> None:
        self._batch_error = batch_error
        self._batch_vectors = batch_vectors
        self._individual = list(individual or [])
        self.calls: list[tuple[str, Any]] = []

    async def connect(self) -> None:
        self.calls.append(("connect", None))

    async def close(self) -> None:
        self.calls.append(("close", None))

    async def get_embedding(self, text: str) -> list[float]:
        self.calls.append(("get_embedding", text))
        item = self._individual.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(("get_embeddings_batch", list(texts)))
        if self._batch_error is not None:
            raise self._batch_error
        if self._batch_vectors is not None:
            return self._batch_vectors
        return [[0.1 * (i + 1), 0.5] for i, _ in enumerate(texts)]


def _chunk(content: str, index: int = 0) -> ModelClassifiedChunk:
    return ModelClassifiedChunk(
        content=content,
        section_heading="Overview",
        item_type=EnumContextItemType.DOC_EXCERPT,
        rule_version="v1",
        tags=("source:docs/CLAUDE.md", "doctype:general_markdown"),
        content_fingerprint=f"fp-{index}",
        version_hash=f"vh-{index}",
        character_offset_start=index * 100,
        character_offset_end=index * 100 + len(content),
        token_estimate=len(content) // 4,
        has_code_fence=False,
        code_fence_language=None,
        source_ref="docs/CLAUDE.md",
        crawl_scope="omninode/omniintelligence",
        source_version="sha-abc123",
        correlation_id="test-corr-01",
    )


def _input(
    contents: list[str],
    provider: EnumEmbeddingProvider = EnumEmbeddingProvider.QWEN3,
) -> ModelEmbeddingGenerateInput:
    return ModelEmbeddingGenerateInput(
        classified_chunks=tuple(_chunk(c, i) for i, c in enumerate(contents)),
        embedding_url=_EMBEDDING_URL,
        embedding_provider=provider,
        source_ref="docs/CLAUDE.md",
        correlation_id="test-corr-01",
    )


# case id -> fresh fake client builder (used injected or as the created client)
CLIENT_BUILDERS: dict[str, Callable[[], _FakeClient]] = {
    "batch-success": lambda: _FakeClient(),
    "skips-empty-chunks": lambda: _FakeClient(),
    "all-chunks-empty": lambda: _FakeClient(),
    "no-chunks": lambda: _FakeClient(),
    "batch-fails-individual-ok": lambda: _FakeClient(
        batch_error=EmbeddingClientError("batch down"),
        individual=[[1.0, 2.0], [3.0, 4.0]],
    ),
    "batch-fails-one-dead-lettered": lambda: _FakeClient(
        batch_error=EmbeddingClientError("batch down"),
        individual=[[1.0, 2.0], EmbeddingClientError("bad chunk")],
    ),
    "batch-length-mismatch-raises": lambda: _FakeClient(batch_vectors=[[1.0]]),
    "batch-connection-error-propagates": lambda: _FakeClient(
        batch_error=EmbeddingConnectionError("refused")
    ),
    "own-client-local-openai": lambda: _FakeClient(),
    "own-client-batch-fails": lambda: _FakeClient(
        batch_error=EmbeddingClientError("batch down"),
        individual=[[9.0, 8.0], EmbeddingClientError("bad chunk")],
    ),
    "own-client-closed-on-error": lambda: _FakeClient(
        batch_error=EmbeddingConnectionError("refused")
    ),
    "own-client-all-empty-never-created": lambda: _FakeClient(),
}

OWN_CLIENT_CASES = frozenset(
    case for case in CLIENT_BUILDERS if case.startswith("own-client")
)


def _deps_for(case_id: str) -> Callable[[], dict[str, Any]]:
    if case_id in OWN_CLIENT_CASES:
        return dict
    return lambda: {"client": CLIENT_BUILDERS[case_id]()}


PARITY_CASES: list[
    tuple[str, str, Callable[[], BaseModel], Callable[[], dict[str, Any]]]
] = [
    (
        "batch-success",
        WRAPPER_CLASS,
        lambda: _input(["first chunk text", "second chunk text"]),
        _deps_for("batch-success"),
    ),
    (
        "skips-empty-chunks",
        WRAPPER_CLASS,
        lambda: _input(["real content", "", "   \n", "more content"]),
        _deps_for("skips-empty-chunks"),
    ),
    (
        "all-chunks-empty",
        WRAPPER_CLASS,
        lambda: _input(["", "  "]),
        _deps_for("all-chunks-empty"),
    ),
    (
        "no-chunks",
        WRAPPER_CLASS,
        lambda: _input([]),
        _deps_for("no-chunks"),
    ),
    (
        "batch-fails-individual-ok",
        WRAPPER_CLASS,
        lambda: _input(["alpha", "beta"]),
        _deps_for("batch-fails-individual-ok"),
    ),
    (
        "batch-fails-one-dead-lettered",
        WRAPPER_CLASS,
        lambda: _input(["alpha", "beta"]),
        _deps_for("batch-fails-one-dead-lettered"),
    ),
    (
        "batch-length-mismatch-raises",
        WRAPPER_CLASS,
        lambda: _input(["alpha", "beta"]),
        _deps_for("batch-length-mismatch-raises"),
    ),
    (
        "batch-connection-error-propagates",
        WRAPPER_CLASS,
        lambda: _input(["alpha"]),
        _deps_for("batch-connection-error-propagates"),
    ),
    (
        "own-client-local-openai",
        WRAPPER_CLASS,
        lambda: _input(["gamma", "delta"], EnumEmbeddingProvider.LOCAL_OPENAI),
        _deps_for("own-client-local-openai"),
    ),
    (
        "own-client-batch-fails",
        WRAPPER_CLASS,
        lambda: _input(["alpha", "beta"]),
        _deps_for("own-client-batch-fails"),
    ),
    (
        "own-client-closed-on-error",
        WRAPPER_CLASS,
        lambda: _input(["alpha"]),
        _deps_for("own-client-closed-on-error"),
    ),
    (
        "own-client-all-empty-never-created",
        WRAPPER_CLASS,
        lambda: _input([""]),
        _deps_for("own-client-all-empty-never-created"),
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper and preserved function return or raise alike with equal calls."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    created: list[_FakeClient] = []

    def fake_factory(provider: EnumEmbeddingProvider, config: Any) -> _FakeClient:
        client = CLIENT_BUILDERS[case_id]()
        created.append(client)
        assert config.base_url == _EMBEDDING_URL
        return client

    monkeypatch.setattr(handler_module, "_create_client_for_provider", fake_factory)

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = function_result = None

    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    wrapper_created, created[:] = list(created), []
    try:
        function_result = await handle_embedding_generate(request_b, **deps_b)
    except Exception as exc:
        function_error = exc
    function_created = list(created)

    if function_error is not None:
        assert wrapper_error is not None, "wrapper must raise like the function"
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result

    if case_id in OWN_CLIENT_CASES:
        assert len(wrapper_created) == len(function_created)
        calls_a = [c.calls for c in wrapper_created]
        calls_b = [c.calls for c in function_created]
    else:
        assert wrapper_created == [] and function_created == []
        calls_a = [deps_a["client"].calls]
        calls_b = [deps_b["client"].calls]
    assert calls_a == calls_b
