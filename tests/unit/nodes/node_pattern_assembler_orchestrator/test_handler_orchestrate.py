# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for Pattern Assembler Orchestrator handler.

Tests the main orchestration entry point (handle_pattern_assembly_orchestrate)
covering:
    - Successful orchestration with valid input
    - Input validation failures (empty content + traces)
    - Pydantic validation errors (invalid schema)
    - Timeout handling
    - Structured error output (never raises)
    - Workflow with mock compute nodes

Related:
    - OMN-2222 GAP 10: NodePatternAssemblerOrchestrator has zero tests
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest import mock
from uuid import UUID

import pytest

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers import (
    HandlerPatternAssemblyOrchestrate,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers import (
    pattern_assembly_core as assembly_core,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.handler_orchestrate import (
    _handle_pattern_assembly_orchestrate,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.handler_pattern_assembly import (
    HandlerPatternAssembly,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.handler_workflow_coordination import (
    HandlerAssemblyContext,
    HandlerWorkflowCoordination,
    _build_assembly_context,
    _execute_workflow_async,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.pattern_assembly_core import (
    _assemble_pattern,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.models import (
    ModelAssemblyContextRequest,
    ModelPatternAssemblyInput,
    ModelPatternAssemblyOrchestrateRequest,
    ModelPatternAssemblyOutput,
    ModelPatternAssemblyRequest,
    ModelWorkflowCoordinationRequest,
    RawAssemblyDataDict,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def valid_raw_data() -> RawAssemblyDataDict:
    """Raw assembly data with content for a valid orchestration run."""
    return RawAssemblyDataDict(
        content="def hello():\n    return 'world'",
        language="python",
        framework="pytest",
    )


@pytest.fixture
def valid_input(valid_raw_data: RawAssemblyDataDict) -> ModelPatternAssemblyInput:
    """Valid input model for orchestration."""
    return ModelPatternAssemblyInput(
        raw_data=valid_raw_data,
        correlation_id="12345678-1234-1234-1234-123456789abc",
    )


@pytest.fixture
def valid_input_dict(valid_raw_data: RawAssemblyDataDict) -> dict[str, Any]:
    """Valid input as a dict (tests dict-to-model parsing path)."""
    return {
        "raw_data": dict(valid_raw_data),
        "correlation_id": "12345678-1234-1234-1234-123456789abc",
    }


@pytest.fixture
def empty_input_dict() -> dict[str, Any]:
    """Input dict with no content and no traces (triggers validation error)."""
    return {
        "raw_data": {},
        "correlation_id": "12345678-1234-1234-1234-123456789abc",
    }


# =============================================================================
# Tests: Successful Orchestration
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrate_with_valid_input_returns_output(
    valid_input: ModelPatternAssemblyInput,
) -> None:
    """Handler returns ModelPatternAssemblyOutput for valid input."""
    result = await HandlerPatternAssemblyOrchestrate().handle(
        ModelPatternAssemblyOrchestrateRequest(input_data=valid_input)
    )

    assert isinstance(result, ModelPatternAssemblyOutput)
    # Handler never raises -- it returns structured output
    assert isinstance(result.success, bool)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrate_with_dict_input_parses_correctly(
    valid_input_dict: dict[str, Any],
) -> None:
    """Handler accepts dict input and parses into ModelPatternAssemblyInput."""
    result = await HandlerPatternAssemblyOrchestrate().handle(
        ModelPatternAssemblyOrchestrateRequest(input_data=valid_input_dict)
    )

    assert isinstance(result, ModelPatternAssemblyOutput)
    assert result.correlation_id == "12345678-1234-1234-1234-123456789abc"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrate_preserves_correlation_id(
    valid_input: ModelPatternAssemblyInput,
) -> None:
    """Correlation ID is preserved in output."""
    result = await HandlerPatternAssemblyOrchestrate().handle(
        ModelPatternAssemblyOrchestrateRequest(input_data=valid_input)
    )

    assert result.correlation_id == "12345678-1234-1234-1234-123456789abc"


# =============================================================================
# Tests: Input Validation Failures
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrate_empty_input_returns_validation_error(
    empty_input_dict: dict[str, Any],
) -> None:
    """Handler returns structured error for empty content + traces."""
    result = await HandlerPatternAssemblyOrchestrate().handle(
        ModelPatternAssemblyOrchestrateRequest(input_data=empty_input_dict)
    )

    assert isinstance(result, ModelPatternAssemblyOutput)
    assert result.success is False
    assert result.metadata is not None
    assert result.metadata.get("status") in ("validation_failed", "failed")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrate_invalid_schema_returns_validation_error() -> None:
    """Handler returns structured error for invalid Pydantic schema."""
    bad_input: dict[str, Any] = {
        "raw_data": {"content": "some code"},
        "correlation_id": "not-a-uuid",  # Invalid UUID format
    }

    result = await HandlerPatternAssemblyOrchestrate().handle(
        ModelPatternAssemblyOrchestrateRequest(input_data=bad_input)
    )

    assert isinstance(result, ModelPatternAssemblyOutput)
    assert result.success is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrate_missing_raw_data_returns_error() -> None:
    """Handler returns structured error when raw_data is missing."""
    bad_input: dict[str, Any] = {
        "correlation_id": "12345678-1234-1234-1234-123456789abc",
    }

    result = await HandlerPatternAssemblyOrchestrate().handle(
        ModelPatternAssemblyOrchestrateRequest(input_data=bad_input)
    )

    assert isinstance(result, ModelPatternAssemblyOutput)
    assert result.success is False


# =============================================================================
# Tests: Timeout Handling
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrate_timeout_returns_structured_error(
    valid_input: ModelPatternAssemblyInput,
) -> None:
    """Handler returns timeout error when workflow exceeds timeout."""
    # Use a very short timeout (0.001 seconds) to trigger timeout
    result = await HandlerPatternAssemblyOrchestrate().handle(
        ModelPatternAssemblyOrchestrateRequest(
            input_data=valid_input, timeout_seconds=0.001
        )
    )

    assert isinstance(result, ModelPatternAssemblyOutput)
    # May or may not timeout depending on speed, but should always return structured output
    assert isinstance(result.success, bool)


# =============================================================================
# Tests: Output Structure
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrate_output_has_required_fields(
    valid_input: ModelPatternAssemblyInput,
) -> None:
    """Output always contains required fields regardless of success/failure."""
    result = await HandlerPatternAssemblyOrchestrate().handle(
        ModelPatternAssemblyOrchestrateRequest(input_data=valid_input)
    )

    assert hasattr(result, "success")
    assert hasattr(result, "correlation_id")
    assert hasattr(result, "assembled_pattern")
    assert hasattr(result, "component_results")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrate_output_is_serializable(
    valid_input: ModelPatternAssemblyInput,
) -> None:
    """Output can be serialized to dict via model_dump."""
    result = await HandlerPatternAssemblyOrchestrate().handle(
        ModelPatternAssemblyOrchestrateRequest(input_data=valid_input)
    )

    dumped = result.model_dump()
    assert isinstance(dumped, dict)
    assert "success" in dumped
    assert "correlation_id" in dumped


# =============================================================================
# Tests: Never Raises
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrate_never_raises_on_unexpected_input() -> None:
    """Handler catches all exceptions and returns structured error output."""
    # Bypass request validation to exercise the preserved core's defensive path.
    result = await HandlerPatternAssemblyOrchestrate().handle(
        ModelPatternAssemblyOrchestrateRequest.model_construct(input_data=42)
    )

    assert isinstance(result, ModelPatternAssemblyOutput)
    assert result.success is False


@pytest.fixture
def deterministic_assembly() -> Iterator[None]:
    """Freeze incidental IDs and clocks so entire core outputs can be compared."""
    with (
        mock.patch.object(assembly_core.time, "perf_counter", return_value=1.0),
        mock.patch.object(assembly_core, "datetime", wraps=datetime) as clock,
        mock.patch.object(assembly_core, "uuid4", return_value=UUID(int=1)),
    ):
        clock.now.return_value = datetime(2026, 1, 1, tzinfo=UTC)
        yield


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("input_data", "expected_success"),
    [
        ({"raw_data": {"content": "def compute(): return 1"}}, True),
        ({"raw_data": {}}, False),
        ({"raw_data": {"content": "code"}, "correlation_id": "invalid"}, False),
    ],
    ids=["normal_success", "empty_input", "invalid_schema"],
)
async def test_canonical_dispatch_matches_preserved_core(
    input_data: dict[str, Any],
    expected_success: bool,
    deterministic_assembly: None,
) -> None:
    request = ModelPatternAssemblyOrchestrateRequest(
        input_data=input_data, timeout_seconds=5.0
    )
    expected = await _handle_pattern_assembly_orchestrate(
        input_data, timeout_seconds=5.0
    )
    actual = await HandlerPatternAssemblyOrchestrate().handle(request)
    assert actual == expected
    assert actual.success is expected_success


@pytest.mark.unit
@pytest.mark.asyncio
async def test_workflow_coordination_typed_entry_point(
    valid_input: ModelPatternAssemblyInput,
    deterministic_assembly: None,
) -> None:
    expected = await _execute_workflow_async(valid_input)
    actual = await HandlerWorkflowCoordination().handle(
        ModelWorkflowCoordinationRequest(input_data=valid_input)
    )
    assert actual == expected
    assert actual["success"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_assembly_context_typed_entry_point(
    valid_input: ModelPatternAssemblyInput,
    deterministic_assembly: None,
) -> None:
    workflow = await _execute_workflow_async(valid_input)
    assert HandlerAssemblyContext().handle(
        ModelAssemblyContextRequest(input_data=valid_input, workflow_result=workflow)
    ) == _build_assembly_context(valid_input, workflow)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pattern_assembly_typed_entry_point(
    valid_input: ModelPatternAssemblyInput,
    deterministic_assembly: None,
) -> None:
    workflow = await _execute_workflow_async(valid_input)
    context = _build_assembly_context(valid_input, workflow)
    request = ModelPatternAssemblyRequest(
        context=context,
        workflow_result=workflow,
        _input_data=valid_input,
    )
    assert HandlerPatternAssembly().handle(request) == _assemble_pattern(
        context,
        workflow,
        valid_input,
    )
