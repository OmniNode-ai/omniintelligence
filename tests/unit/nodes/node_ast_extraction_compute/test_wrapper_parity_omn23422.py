# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity: the contract-bound AST extraction wrapper matches the preserved function.

``HandlerAstExtract.handle`` must return exactly what ``handle_ast_extract``
returns for the same request. Non-deterministic names (``uuid4`` and the wall
clock) are replaced in the handler modules with counters and a fixed instant;
the full result objects are compared with equality.

Ticket: OMN-23422
"""

import importlib
import json
import textwrap
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_ast_extract import (
    AstExtractInput,
    ExtractorConfig,
    handle_ast_extract,
)

MODULE = (
    "omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_ast_extract"
)
RELATIONSHIP_MODULE = (
    "omniintelligence.nodes.node_ast_extraction_compute.handlers."
    "handler_relationship_detect"
)
CLASS_NAME = "HandlerAstExtract"

_FIXED_TIME = datetime(2025, 1, 1, tzinfo=UTC)

_SOURCE_RICH = textwrap.dedent(
    """\
    import os
    from typing import Protocol
    from pydantic import BaseModel
    from collections import *

    MAX_ITEMS = 10
    lower_name = 3

    class Greeter(Protocol):
        def greet(self, name: str) -> str: ...

    class Settings(BaseModel):
        \"\"\"Settings model.\"\"\"

        host: str = "localhost"
        port: int

    class Plain:
        \"\"\"A plain class.\"\"\"

        def run(self, x: int) -> int:
            return helper(x)

    @staticmethod
    def helper(x: int) -> int:
        \"\"\"Double it.\"\"\"
        return x * 2

    async def fetch(url: str) -> bytes:
        return b""
    """
)


def _make_input(
    source: str,
    *,
    path: str = "src/pkg/mod.py",
    config: ExtractorConfig | None = None,
) -> AstExtractInput:
    kwargs: dict[str, Any] = {
        "source_content": source,
        "source_path": path,
        "source_repo": "omniintelligence",
        "file_hash": "hash-123",
        "crawl_id": "crawl-1",
        "event_id": "event-1",
    }
    if config is not None:
        kwargs["config"] = config
    return AstExtractInput(**kwargs)


def _no_deps() -> dict[str, Any]:
    return {}


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], AstExtractInput],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "rich-module",
        CLASS_NAME,
        lambda: _make_input(_SOURCE_RICH),
        _no_deps,
    ),
    (
        "init-path-module",
        CLASS_NAME,
        lambda: _make_input(
            "import json\nVALUE = 1\n\ndef f():\n    return VALUE\n",
            path="src/pkg/__init__.py",
        ),
        _no_deps,
    ),
    (
        "windows-path-no-src",
        CLASS_NAME,
        lambda: _make_input("X = 1\n", path="pkg\\sub\\mod.py"),
        _no_deps,
    ),
    (
        "all-extractors-disabled",
        CLASS_NAME,
        lambda: _make_input(
            _SOURCE_RICH,
            config=ExtractorConfig(
                classes_enabled=False,
                protocols_enabled=False,
                pydantic_models_enabled=False,
                functions_enabled=False,
                imports_enabled=False,
                module_constants_enabled=False,
            ),
        ),
        _no_deps,
    ),
    (
        "minimal-class-options",
        CLASS_NAME,
        lambda: _make_input(
            _SOURCE_RICH,
            config=ExtractorConfig(
                extract_bases=False,
                extract_methods=False,
                extract_decorators=False,
                extract_docstrings=False,
                extract_fields=False,
                extract_signatures=False,
                extract_function_decorators=False,
            ),
        ),
        _no_deps,
    ),
    (
        "syntax-error",
        CLASS_NAME,
        lambda: _make_input("def broken(:\n    pass\n"),
        _no_deps,
    ),
    (
        "empty-source",
        CLASS_NAME,
        lambda: _make_input(""),
        _no_deps,
    ),
]


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(json.dumps(asdict(request_builder()), default=str)),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


def _install_determinism(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Patch uuid4 and the clock in the handler modules; return a counter reset."""
    counter = {"n": 0}

    def fake_uuid4() -> str:
        counter["n"] += 1
        return f"00000000-0000-0000-0000-{counter['n']:012d}"

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, *_args: Any, **_kwargs: Any) -> datetime:
            return _FIXED_TIME

    for module_name in (MODULE, RELATIONSHIP_MODULE):
        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, "uuid", SimpleNamespace(uuid4=fake_uuid4))
    monkeypatch.setattr(importlib.import_module(MODULE), "datetime", _FixedDatetime)

    def reset() -> None:
        counter["n"] = 0

    return reset


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], AstExtractInput],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wrapper returns exactly what the preserved function returns."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    reset = _install_determinism(monkeypatch)
    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    reset()
    wrapper_result = wrapper_cls(**deps_a).handle(request_a)
    reset()
    function_result = handle_ast_extract(request_b, **deps_b)

    assert wrapper_result == function_result
    assert wrapper_result.model_dump(mode="json") == function_result.model_dump(
        mode="json"
    )
    if case_id == "syntax-error":
        assert wrapper_result.parse_status == "syntax_error"
    if case_id == "rich-module":
        assert wrapper_result.entities
        assert wrapper_result.relationships
