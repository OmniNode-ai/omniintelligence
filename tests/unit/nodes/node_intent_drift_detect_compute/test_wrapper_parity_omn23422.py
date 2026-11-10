# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity of the contract-bound drift handler with the preserved ``detect_drift``.

OMN-23422: ``HandlerDetectDrift.handle`` forwards the request mapping as
keyword arguments, next to the sensitivity dependency, to ``detect_drift``.
It must return exactly what ``detect_drift`` returns (a drift signal or None)
and raise the same error for bad dependencies.
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from pydantic import BaseModel
from pydantic_core import to_jsonable_python

from omniintelligence.nodes.node_intent_drift_detect_compute.handlers.handler_drift_detect import (
    detect_drift,
)
from omniintelligence.nodes.node_intent_drift_detect_compute.models import (
    ModelDriftSensitivity,
    ModelIntentDriftInput,
)

MODULE = (
    "omniintelligence.nodes.node_intent_drift_detect_compute.handlers."
    "handler_drift_detect"
)
WRAPPER = "HandlerDetectDrift"

_DETECTED_AT = datetime(2026, 2, 21, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("00000000-0000-0000-0000-000000023422")


def _request(
    intent_class: EnumIntentClass,
    tool_name: str,
    files_modified: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "input_data": ModelIntentDriftInput(
            session_id="sess-omn23422",
            correlation_id=_CORRELATION_ID,
            intent_class=intent_class,
            tool_name=tool_name,
            files_modified=files_modified or [],
            detected_at=_DETECTED_AT,
        )
    }


def _sensitivity(
    tool_mismatch: float = 0.5, file_surface: float = 0.4, scope_expansion: float = 0.6
) -> Callable[[], dict[str, Any]]:
    return lambda: {
        "sensitivity": ModelDriftSensitivity(
            tool_mismatch_threshold=tool_mismatch,
            file_surface_threshold=file_surface,
            scope_expansion_threshold=scope_expansion,
        )
    }


_MANY_FILES = [f"src/mod_{n}.py" for n in range(7)]

PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], BaseModel | dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "tool-mismatch-warning",
        WRAPPER,
        lambda: _request(EnumIntentClass.REFACTOR, "Write", ["a.py"]),
        _sensitivity(),
    ),
    (
        "tool-mismatch-alert",
        WRAPPER,
        lambda: _request(EnumIntentClass.SECURITY, "Edit"),
        _sensitivity(tool_mismatch=0.9),
    ),
    (
        "tool-mismatch-info",
        WRAPPER,
        lambda: _request(EnumIntentClass.BUGFIX, "Write"),
        _sensitivity(tool_mismatch=0.1),
    ),
    (
        "tool-mismatch-disabled-falls-to-scope-expansion",
        WRAPPER,
        lambda: _request(EnumIntentClass.REFACTOR, "Write", ["new.py"]),
        _sensitivity(tool_mismatch=0.0),
    ),
    (
        "file-surface-documentation-code-files",
        WRAPPER,
        lambda: _request(
            EnumIntentClass.DOCUMENTATION,
            "Read",
            ["docs/a.md", "src/x.py", "pkg/__init__.py", "web/y.ts"],
        ),
        _sensitivity(file_surface=0.7),
    ),
    (
        "file-surface-bugfix-many-files",
        WRAPPER,
        lambda: _request(EnumIntentClass.BUGFIX, "Edit", _MANY_FILES),
        _sensitivity(),
    ),
    (
        "file-surface-disabled",
        WRAPPER,
        lambda: _request(EnumIntentClass.BUGFIX, "Edit", _MANY_FILES),
        _sensitivity(file_surface=0.0),
    ),
    (
        "no-drift-feature-intent",
        WRAPPER,
        lambda: _request(EnumIntentClass.FEATURE, "Write", _MANY_FILES),
        _sensitivity(),
    ),
    (
        "no-drift-documentation-markdown-only",
        WRAPPER,
        lambda: _request(EnumIntentClass.DOCUMENTATION, "Write", ["docs/a.md"]),
        _sensitivity(),
    ),
    (
        "no-drift-scope-expansion-disabled",
        WRAPPER,
        lambda: _request(EnumIntentClass.REFACTOR, "Write"),
        _sensitivity(tool_mismatch=0.0, scope_expansion=0.0),
    ),
    (
        "no-drift-empty-files-clean-tool",
        WRAPPER,
        lambda: _request(EnumIntentClass.ANALYSIS, "Read"),
        _sensitivity(),
    ),
    (
        "missing-sensitivity-raises",
        WRAPPER,
        lambda: _request(EnumIntentClass.REFACTOR, "Write"),
        lambda: {"sensitivity": None},
    ),
]


def _request_json(request: BaseModel | dict[str, Any]) -> Any:
    return json.loads(json.dumps(to_jsonable_python(request), default=str))


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
        function_result = detect_drift(**request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
