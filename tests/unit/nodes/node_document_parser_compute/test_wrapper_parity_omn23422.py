# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity of the contract-bound document parser handler with the preserved function.

OMN-23422: ``HandlerDocumentParse.handle`` must return exactly what
``handle_document_parse`` returns for the same parse request. The parser is a
pure function with no dependencies, so the dependency dict is empty and the
comparison is full pydantic model equality of the parsed output.
"""

import importlib
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_document_parser_compute.handlers.handler_document_parser import (
    handle_document_parse,
)
from omniintelligence.nodes.node_document_parser_compute.models.enum_doc_type import (
    EnumDocType,
)
from omniintelligence.nodes.node_document_parser_compute.models.model_document_meta import (
    ModelDocumentMeta,
)
from omniintelligence.nodes.node_document_parser_compute.models.model_document_parse_input import (
    ModelDocumentParseInput,
)

MODULE = (
    "omniintelligence.nodes.node_document_parser_compute.handlers."
    "handler_document_parser"
)
WRAPPER = "HandlerDocumentParse"


def _request(
    raw_content: str,
    doc_type: EnumDocType = EnumDocType.GENERAL_MARKDOWN,
    correlation_id: str | None = "corr-omn23422",
) -> ModelDocumentParseInput:
    return ModelDocumentParseInput(
        doc_meta=ModelDocumentMeta(
            source_ref="docs/example.md",
            crawl_scope="omninode/test",
            doc_type=doc_type,
            source_version="abc123",
            correlation_id=correlation_id,
        ),
        raw_content=raw_content,
    )


def _prose(words: int, sentence_every: int = 12) -> str:
    """Deterministic prose of ``words`` words (about five characters each)."""
    parts = []
    for i in range(words):
        word = f"word{i % 10}"
        parts.append(word + ("." if i % sentence_every == sentence_every - 1 else ""))
    return " ".join(parts)


def _paragraphs(paragraph_count: int, words: int = 90) -> str:
    return "\n\n".join(_prose(words) for _ in range(paragraph_count))


def _fence(lines: int, lang: str = "python") -> str:
    blocks = []
    for block in range(lines):
        blocks.append(
            "\n".join(f"value_{block}_{n} = {n} * {block}" for n in range(40))
        )
    return f"```{lang}\n" + "\n\n".join(blocks) + "\n```"


_CLAUDE_BASIC = (
    "# Project\n\nIntro line.\n\n"
    f"## Setup\n\n{_prose(120)}\n\n"
    f"## Rules\n\n{_prose(150)}\n\n"
    "## Tiny\n\nshort\n"
)
_CLAUDE_H3_SMALL = (
    f"## Section\n\n{_prose(100)}\n\n### Sub one\n\n{_prose(100)}\n\n"
    f"### Sub two\n\n{_prose(100)}\n"
)
_CLAUDE_H3_BIG = (
    f"## Big\n\n{_prose(200)}\n\n### Alpha\n\n{_prose(400)}\n\n"
    f"### Beta\n\n{_prose(400)}\n\n## After\n\n{_prose(150)}\n"
)
_DESIGN_FENCES = (
    f"# Design\n\nPreamble text. {_prose(60)}\n\n"
    f"## API\n\n{_prose(80)}\n\n```yaml\nkey: value\nother: 1\n```\n\n"
    f"## Notes\n\n{_prose(130)}\n"
)
_GENERAL_HEADINGS = (
    f"Preamble {_prose(70)}\n\n## First\n\n{_prose(120)}\n\n### Nested\n\n"
    f"{_prose(120)}\n\n## Second\n\n{_prose(110)}\n"
)
_GENERAL_BIG_SECTION = f"## Huge\n\n{_paragraphs(8, 100)}\n"

PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], BaseModel | dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "claude-md-sections",
        WRAPPER,
        lambda: _request(_CLAUDE_BASIC, EnumDocType.CLAUDE_MD),
        dict,
    ),
    (
        "claude-md-h3-kept-with-parent",
        WRAPPER,
        lambda: _request(_CLAUDE_H3_SMALL, EnumDocType.CLAUDE_MD),
        dict,
    ),
    (
        "claude-md-h3-split-oversized",
        WRAPPER,
        lambda: _request(_CLAUDE_H3_BIG, EnumDocType.CLAUDE_MD),
        dict,
    ),
    (
        "claude-md-oversized-fence",
        WRAPPER,
        lambda: _request(
            f"## Code\n\n{_fence(8)}\n\n## Tail\n\n{_prose(130)}\n",
            EnumDocType.CLAUDE_MD,
        ),
        dict,
    ),
    (
        "design-doc-fences",
        WRAPPER,
        lambda: _request(_DESIGN_FENCES, EnumDocType.DESIGN_DOC),
        dict,
    ),
    (
        "design-doc-prose-sliding-window",
        WRAPPER,
        lambda: _request(
            f"## Long\n\n{_paragraphs(10, 100)}\n", EnumDocType.DESIGN_DOC
        ),
        dict,
    ),
    (
        "architecture-doc-oversized-fence",
        WRAPPER,
        lambda: _request(
            f"## Wiring\n\n{_fence(9, 'rust')}\n", EnumDocType.ARCHITECTURE_DOC
        ),
        dict,
    ),
    (
        "general-headings",
        WRAPPER,
        lambda: _request(_GENERAL_HEADINGS),
        dict,
    ),
    (
        "general-oversized-section-window",
        WRAPPER,
        lambda: _request(_GENERAL_BIG_SECTION),
        dict,
    ),
    (
        "general-paragraphs",
        WRAPPER,
        lambda: _request(_paragraphs(4, 60), correlation_id=None),
        dict,
    ),
    (
        "general-sliding-window-sentences",
        WRAPPER,
        lambda: _request(_prose(900, sentence_every=9)),
        dict,
    ),
    (
        "general-single-short-paragraph",
        WRAPPER,
        lambda: _request("Just one short line."),
        dict,
    ),
    (
        "empty-content",
        WRAPPER,
        lambda: _request("", EnumDocType.CLAUDE_MD),
        dict,
    ),
    (
        "whitespace-only-content",
        WRAPPER,
        lambda: _request("   \n\n  \n", EnumDocType.DESIGN_DOC),
        dict,
    ),
]


def _request_json(request: BaseModel | dict[str, Any]) -> Any:
    raw = request.model_dump(mode="json") if isinstance(request, BaseModel) else request
    return json.loads(json.dumps(raw, default=str))


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {"case": case_id, "wrapper": class_name, "request": _request_json(build())}
        for case_id, class_name, build, _ in PARITY_CASES
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], BaseModel | dict[str, Any]],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """The wrapper and the preserved function agree on result and on raising."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    wrapper_result: Any = None
    try:
        wrapper_result = wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc

    function_error: Exception | None = None
    function_result: Any = None
    try:
        function_result = handle_document_parse(request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
