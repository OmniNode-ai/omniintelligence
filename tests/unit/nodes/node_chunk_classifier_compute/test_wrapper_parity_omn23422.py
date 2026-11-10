# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Deterministic parity checks for the HandlerChunkClassify wrapper (OMN-23422).

The contract-bound wrapper must return exactly what the preserved module
function ``handle_chunk_classify`` returns for the same request. The
function is pure (no I/O, no clock, no uuid), so results are compared
directly with pydantic model equality.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_chunk_classifier_compute.handlers.handler_chunk_classifier import (
    handle_chunk_classify,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.model_chunk_classify_input import (
    ModelChunkClassifyInput,
    ModelRawChunkRef,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.model_chunk_classify_output import (
    ModelChunkClassifyOutput,
)

MODULE = (
    "omniintelligence.nodes.node_chunk_classifier_compute.handlers."
    "handler_chunk_classifier"
)
WRAPPER_CLASS = "HandlerChunkClassify"


def _chunk(
    content: str,
    section_heading: str | None = None,
    has_code_fence: bool = False,
    code_fence_language: str | None = None,
) -> ModelRawChunkRef:
    """Raw chunk builder copied from the node_tests helpers."""
    return ModelRawChunkRef(
        content=content,
        section_heading=section_heading,
        has_code_fence=has_code_fence,
        code_fence_language=code_fence_language,
    )


def _input(
    chunks: list[ModelRawChunkRef],
    source_ref: str = "docs/CLAUDE.md",
    crawl_scope: str = "omninode/omniintelligence",
    source_version: str | None = "abc123",
    doc_type: str = "general_markdown",
    correlation_id: str | None = "test-corr-01",
) -> ModelChunkClassifyInput:
    """Classification request builder copied from the node_tests helpers."""
    return ModelChunkClassifyInput(
        source_ref=source_ref,
        crawl_scope=crawl_scope,
        source_version=source_version,
        doc_type=doc_type,
        raw_chunks=tuple(chunks),
        correlation_id=correlation_id,
    )


def _no_deps() -> dict[str, Any]:
    """The preserved function takes no dependencies — fresh empty dict per run."""
    return {}


PARITY_CASES: list[
    tuple[str, str, Callable[[], BaseModel], Callable[[], dict[str, Any]]]
] = [
    (
        "api-constraint-url",
        WRAPPER_CLASS,
        lambda: _input(
            [
                _chunk(
                    "Connect to https://kafka.example.com:9092 via "
                    "KAFKA_BOOTSTRAP_SERVERS in omniintelligence.",
                    section_heading="Broker endpoints",
                    has_code_fence=True,
                    code_fence_language="bash",
                )
            ]
        ),
        _no_deps,
    ),
    (
        "config-note-env",
        WRAPPER_CLASS,
        lambda: _input(
            [
                _chunk(
                    "Set POSTGRES_PASSWORD and DATABASE_URL from the .env file.",
                    section_heading="Env, vars!",
                )
            ],
            doc_type="engineering_doc",
        ),
        _no_deps,
    ),
    (
        "rule-invariant",
        WRAPPER_CLASS,
        lambda: _input(
            [_chunk("You must never commit secrets. INVARIANT: keys stay local.")]
        ),
        _no_deps,
    ),
    (
        "failure-pattern-gotcha-heading",
        WRAPPER_CLASS,
        lambda: _input(
            [
                _chunk(
                    "Ordinary prose about the parser internals.",
                    section_heading="Common gotchas and pitfalls",
                )
            ]
        ),
        _no_deps,
    ),
    (
        "example-heading-and-fence",
        WRAPPER_CLASS,
        lambda: _input(
            [
                _chunk("Run the indexer.", section_heading="Usage"),
                _chunk(
                    "Example:\n```\nmake index\n```",
                    has_code_fence=True,
                    code_fence_language="makefile",
                ),
            ]
        ),
        _no_deps,
    ),
    (
        "repo-map-tree",
        WRAPPER_CLASS,
        lambda: _input(
            [
                _chunk("omniintelligence/\n├── src/\n└── tests/"),
                _chunk(
                    "The layout below is authoritative.",
                    section_heading="Repository map",
                ),
            ]
        ),
        _no_deps,
    ),
    (
        "doc-excerpt-default",
        WRAPPER_CLASS,
        lambda: _input(
            [_chunk("Ordinary documentation prose with no rule triggers.")],
            source_ref="omninode/omniintelligence/README.md",
            crawl_scope="scratch",
            source_version=None,
        ),
        _no_deps,
    ),
    (
        "repo-name-unresolvable",
        WRAPPER_CLASS,
        lambda: _input(
            [_chunk("Plain text.")],
            source_ref="notes.md",
            crawl_scope="scratch",
        ),
        _no_deps,
    ),
    (
        "empty-chunks",
        WRAPPER_CLASS,
        lambda: _input([]),
        _no_deps,
    ),
    (
        "priority-config-over-rule",
        WRAPPER_CLASS,
        lambda: _input(
            [_chunk("Set KAFKA_HOST per environment; you must never hardcode it.")]
        ),
        _no_deps,
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _, _, _ in PARITY_CASES],
)
def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], BaseModel],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """The wrapper returns exactly what handle_chunk_classify returns."""
    module = importlib.import_module(MODULE)
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    via_wrapper = wrapper_cls(**deps_a).handle(request_a)
    via_function = handle_chunk_classify(request_b, **deps_b)

    assert isinstance(via_wrapper, ModelChunkClassifyOutput)
    assert via_wrapper == via_function
    assert via_wrapper.total_chunks == len(request_a.raw_chunks)


def corpus_inputs() -> list[dict[str, Any]]:
    """JSON-describable inputs of PARITY_CASES, in corpus order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(request_builder().model_dump(mode="json"))
            ),
        }
        for case_id, class_name, request_builder, _deps_builder in PARITY_CASES
    ]
