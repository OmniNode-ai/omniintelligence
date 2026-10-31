# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The contract of node_pattern_extraction_compute binds handler classes (OMN-21536).

The five extraction operations of the node were bound to module functions that took
several positional arguments. Each now binds a handler class whose ``handle`` takes one
typed request. These tests resolve the class through the contract, as the runtime does,
and compare its output with the module function it delegates to. Nothing is imported
from the new classes at module level, so against the pre-change tree every test fails
on its own assertion.
"""

from __future__ import annotations

import importlib
import inspect
import typing
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel

from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelSessionSnapshot,
)

pytestmark = pytest.mark.unit

_NODE_PACKAGE = "omniintelligence.nodes.node_pattern_extraction_compute"
_CONTRACT = Path(__file__).resolve().parents[4] / (
    "src/omniintelligence/nodes/node_pattern_extraction_compute/contract.yaml"
)


_VOLATILE = frozenset({"pattern_id", "insight_id"})


def _masked(value: Any) -> Any:
    """The value with the ids a run generates (random UUIDs) removed, for comparison."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _masked(v) for k, v in value.items() if k not in _VOLATILE}
    if isinstance(value, (list, tuple)):
        return [_masked(v) for v in value]
    return value


# operation -> (bound class, module function the class delegates to, fixture name)
_OPERATIONS: dict[str, tuple[str, str, str]] = {
    "extract_patterns": (
        "HandlerExtractAllPatterns",
        "extract_all_patterns",
        "multiple_sessions",
    ),
    "extract_file_patterns": (
        "HandlerFilePatterns",
        "extract_file_access_patterns",
        "multiple_sessions",
    ),
    "extract_error_patterns": (
        "HandlerErrorPatterns",
        "extract_error_patterns",
        "sessions_with_errors",
    ),
    "extract_architecture_patterns": (
        "HandlerArchitecturePatterns",
        "extract_architecture_patterns",
        "sessions_with_architecture_patterns",
    ),
    "extract_tool_patterns": (
        "HandlerToolPatterns",
        "extract_tool_patterns",
        "sessions_with_diverse_tools",
    ),
}


def _entry(operation: str) -> dict[str, Any]:
    contract = yaml.safe_load(_CONTRACT.read_text(encoding="utf-8"))
    entries = [
        e["handler"]
        for e in contract["handler_routing"]["handlers"]
        if e["operation"] == operation
    ]
    assert len(entries) == 1, f"contract declares no single handler for {operation}"
    return entries[0]


def _bound(operation: str) -> tuple[Any, Any]:
    """The class the contract binds for an operation and its module."""
    expected = _OPERATIONS[operation][0]
    entry = _entry(operation)
    assert entry.get("class") == expected, f"{operation} binds {entry!r}"
    assert "function" not in entry, f"{operation} still binds a function"
    module = importlib.import_module(entry["module"])
    bound = getattr(module, expected, None)
    assert inspect.isclass(bound), f"{entry['module']} holds no class {expected}"
    return bound, module


@pytest.mark.parametrize("operation", sorted(_OPERATIONS))
def test_contract_binds_a_class_with_one_typed_request(operation: str) -> None:
    bound, _ = _bound(operation)

    parameters = list(inspect.signature(bound.handle).parameters)
    request_type = typing.get_type_hints(bound.handle)["request"]

    assert parameters == ["self", "request"]
    assert issubclass(request_type, BaseModel)


@pytest.mark.parametrize("operation", sorted(_OPERATIONS))
def test_bound_class_returns_what_the_module_function_returns(
    operation: str, request: pytest.FixtureRequest
) -> None:
    bound, module = _bound(operation)
    function = getattr(module, _OPERATIONS[operation][1])
    sessions: tuple[ModelSessionSnapshot, ...] = request.getfixturevalue(
        _OPERATIONS[operation][2]
    )
    request_type = typing.get_type_hints(bound.handle)["request"]

    if operation == "extract_patterns":
        typed_request = request_type(session_snapshots=sessions)
        handled = bound().handle(typed_request)
        direct = function(typed_request)
        assert handled.success == direct.success
        assert _masked(handled.new_insights) == _masked(direct.new_insights)
        assert _masked(handled.updated_insights) == _masked(direct.updated_insights)
        assert handled.new_insights, "positive control: the fixture yields insights"
    else:
        typed_request = request_type(
            sessions=sessions, min_occurrences=1, min_confidence=0.1
        )
        handled = bound().handle(typed_request)
        direct = function(sessions, min_occurrences=1, min_confidence=0.1)
        assert _masked(handled) == _masked(direct)
        assert handled, "positive control: the fixture yields patterns"
