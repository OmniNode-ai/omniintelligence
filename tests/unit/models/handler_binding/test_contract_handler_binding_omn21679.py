# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Handlers are bound through the node contract that declares them (OMN-21679)."""

from __future__ import annotations

import pytest

from omniintelligence.models.handler_binding import (
    ModelContractHandlerBinding,
    bind_contract_handler,
)
from omniintelligence.nodes.node_ci_fingerprint_compute.handlers.handler_fingerprint import (
    HandlerCiFingerprint,
)
from omniintelligence.nodes.node_claude_code_review_effect.handlers.handler_claude_code_review import (
    HandlerClaudeCodeReview,
)
from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    HandlerClaudeHookEvent,
)
from omniintelligence.nodes.node_cursor_hook_event_effect.handlers.handler_cursor_event import (
    HandlerCursorHookEvent,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers import (
    HandlerExtractAllPatterns,
    HandlerPatternExtractionCore,
)

# (node, operation, class) for every binding the code resolves through the contract.
_BINDINGS: tuple[tuple[str, str, type], ...] = (
    ("node_ci_fingerprint_compute", "compute_fingerprint", HandlerCiFingerprint),
    (
        "node_pattern_extraction_compute",
        "extract_patterns",
        HandlerExtractAllPatterns,
    ),
    (
        "node_pattern_extraction_compute",
        "extract_core_patterns",
        HandlerPatternExtractionCore,
    ),
    (
        "node_claude_code_review_effect",
        "review_with_host_configuration",
        HandlerClaudeCodeReview,
    ),
    ("node_claude_hook_event_effect", "handle_hook_event", HandlerClaudeHookEvent),
    ("node_cursor_hook_event_effect", "handle_hook_event", HandlerCursorHookEvent),
)


@pytest.mark.unit
@pytest.mark.parametrize(("node", "operation", "expected"), _BINDINGS)
def test_contract_binds_the_expected_handler_class(
    node: str, operation: str, expected: type
) -> None:
    bound = bind_contract_handler(operation, expected, node=node)

    assert type(bound) is expected


@pytest.mark.unit
def test_dependencies_are_injected_into_the_bound_handler() -> None:
    handler = bind_contract_handler(
        "review_with_host_configuration",
        HandlerClaudeCodeReview,
        pool_python="/pool/python",
        environment={"KEY": "value"},
    )

    assert isinstance(handler, HandlerClaudeCodeReview)


@pytest.mark.unit
def test_operation_missing_from_the_contract_fails_the_lookup() -> None:
    with pytest.raises(LookupError, match="declares no handler for operation"):
        bind_contract_handler("no_such_operation", HandlerCiFingerprint)


@pytest.mark.unit
def test_class_the_contract_does_not_bind_is_refused() -> None:
    """Positive control: the contract binds HandlerCiFingerprint, not this class."""
    with pytest.raises(TypeError, match="which is not a HandlerCursorHookEvent"):
        bind_contract_handler(
            "compute_fingerprint",
            HandlerCursorHookEvent,
            node="node_ci_fingerprint_compute",
        )


@pytest.mark.unit
def test_node_without_a_contract_file_fails() -> None:
    with pytest.raises(FileNotFoundError):
        ModelContractHandlerBinding().bind(
            "compute", HandlerCiFingerprint, node="node_does_not_exist"
        )


@pytest.mark.unit
def test_handler_outside_the_node_packages_needs_its_node_named() -> None:
    class HandlerLocal:
        pass

    with pytest.raises(LookupError, match="name its node"):
        bind_contract_handler("compute", HandlerLocal)
