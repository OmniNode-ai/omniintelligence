# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for handler_bloom_eval_effect.run_bloom_eval.

Validates:
- Domain routing (CONTRACT_CREATION, AGENT_EXECUTION, MEMORY_SYSTEM)
- Kafka producer called with correct topic and payload shape (fire-and-forget)
- Payload contains required fields (event_type, suite_id, failure_mode, etc.)
- No os.getenv / os.environ in the handler module (ARCH-002)
- run_bloom_eval completes successfully when no producer is injected
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import omniintelligence.nodes.node_bloom_eval_orchestrator.handlers.handler_bloom_eval_effect as handler_mod
from omniintelligence.nodes.node_bloom_eval_orchestrator.handlers.handler_bloom_eval_effect import (
    ModelBloomEvalRunCommand,
    run_bloom_eval,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm_client(
    scenarios: list[str] | None = None,
    judgment: dict[str, Any] | None = None,
) -> MagicMock:
    """Return a mock EvalLLMClient that returns preset responses."""
    client = MagicMock()
    client.generate_scenarios = AsyncMock(
        return_value=scenarios or ["scenario text 0", "scenario text 1"]
    )
    client.judge_output = AsyncMock(
        return_value=judgment
        or {
            "metamorphic_stability_score": 0.9,
            "compliance_theater_risk": 0.1,
            "ambiguity_flags": [],
            "invented_requirements": [],
            "missing_acceptance_criteria": [],
            "schema_pass": True,
        }
    )
    return client


def _make_producer() -> MagicMock:
    producer = MagicMock()
    producer.publish = AsyncMock()
    return producer


def _make_command(
    failure_mode: EnumFailureMode = EnumFailureMode.REQUIREMENT_OMISSION,
    scenarios_per_spec: int = 2,
) -> ModelBloomEvalRunCommand:
    return ModelBloomEvalRunCommand(
        failure_mode=failure_mode,
        scenarios_per_spec=scenarios_per_spec,
    )


# ---------------------------------------------------------------------------
# Tests: producer called correctly
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_run_bloom_eval_calls_producer_with_correct_topic() -> None:
    """run_bloom_eval must publish to the command's publish_topic (fire-and-forget)."""
    command = _make_command()
    producer = _make_producer()
    llm = _make_llm_client()

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    # Yield to the event loop so the background publish task runs.
    await asyncio.sleep(0)

    producer.publish.assert_awaited_once()
    call_kwargs = producer.publish.call_args
    assert call_kwargs.kwargs["topic"] == command.publish_topic


@pytest.mark.unit
async def test_run_bloom_eval_payload_contains_required_fields() -> None:
    """Published payload must include all required BloomEvalCompleted fields."""
    command = _make_command()
    producer = _make_producer()
    llm = _make_llm_client()

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    await asyncio.sleep(0)

    payload: dict[str, Any] = producer.publish.call_args.kwargs["value"]
    assert payload["event_type"] == "BloomEvalCompleted"
    assert "suite_id" in payload
    assert "spec_id" in payload
    assert "failure_mode" in payload
    assert "total_scenarios" in payload
    assert "passed_count" in payload
    assert "failure_rate" in payload
    assert "passed_threshold" in payload
    assert "correlation_id" in payload
    assert "emitted_at" in payload


@pytest.mark.unit
async def test_run_bloom_eval_suite_id_matches_command() -> None:
    """Published suite_id must match the command's suite_id."""
    command = _make_command()
    producer = _make_producer()
    llm = _make_llm_client()

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    await asyncio.sleep(0)

    payload = producer.publish.call_args.kwargs["value"]
    assert payload["suite_id"] == str(command.suite_id)


@pytest.mark.unit
async def test_run_bloom_eval_key_is_suite_id() -> None:
    """Kafka message key must be the suite_id string."""
    command = _make_command()
    producer = _make_producer()
    llm = _make_llm_client()

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    await asyncio.sleep(0)

    call_kwargs = producer.publish.call_args.kwargs
    assert call_kwargs["key"] == str(command.suite_id)


# ---------------------------------------------------------------------------
# Tests: domain routing
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_contract_creation_domain_calls_generate_scenarios() -> None:
    """CONTRACT_CREATION domain must invoke generate_scenarios."""
    command = _make_command(failure_mode=EnumFailureMode.REQUIREMENT_OMISSION)
    producer = _make_producer()
    llm = _make_llm_client()

    await run_bloom_eval(command, producer=producer, llm_client=llm)

    llm.generate_scenarios.assert_awaited()


@pytest.mark.unit
async def test_agent_execution_domain_routes_correctly() -> None:
    """AGENT_EXECUTION domain must publish completed event."""
    command = _make_command(failure_mode=EnumFailureMode.UNSAFE_TOOL_SEQUENCING)
    producer = _make_producer()
    llm = _make_llm_client()

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    await asyncio.sleep(0)

    producer.publish.assert_awaited_once()
    payload = producer.publish.call_args.kwargs["value"]
    assert payload["failure_mode"] == EnumFailureMode.UNSAFE_TOOL_SEQUENCING.value


@pytest.mark.unit
async def test_memory_system_domain_routes_correctly() -> None:
    """MEMORY_SYSTEM domain must publish completed event."""
    command = _make_command(failure_mode=EnumFailureMode.REGRESSION_AMNESIA)
    producer = _make_producer()
    llm = _make_llm_client()

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    await asyncio.sleep(0)

    producer.publish.assert_awaited_once()
    payload = producer.publish.call_args.kwargs["value"]
    assert payload["failure_mode"] == EnumFailureMode.REGRESSION_AMNESIA.value


# ---------------------------------------------------------------------------
# Tests: scenario count wired through
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_scenarios_per_spec_passed_to_llm_client() -> None:
    """scenarios_per_spec on the command must be forwarded to generate_scenarios."""
    command = _make_command(scenarios_per_spec=3)
    producer = _make_producer()
    llm = _make_llm_client(scenarios=["s1", "s2", "s3"])

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    await asyncio.sleep(0)

    gen_call = llm.generate_scenarios.call_args
    assert gen_call.kwargs.get("n") == 3 or gen_call.args[1] == 3


@pytest.mark.unit
async def test_total_scenarios_matches_returned_results() -> None:
    """total_scenarios in the payload must equal len(scenarios returned by LLM)."""
    scenarios = ["a", "b", "c"]
    command = _make_command(scenarios_per_spec=3)
    producer = _make_producer()
    llm = _make_llm_client(scenarios=scenarios)

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    await asyncio.sleep(0)

    payload = producer.publish.call_args.kwargs["value"]
    assert payload["total_scenarios"] == len(scenarios)


# ---------------------------------------------------------------------------
# Tests: pass/fail accounting
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_all_passing_results_sets_passed_threshold_true() -> None:
    """When all scenarios pass, passed_threshold must be True."""
    command = _make_command(scenarios_per_spec=2)
    producer = _make_producer()
    llm = _make_llm_client(
        scenarios=["s1", "s2"],
        judgment={
            "metamorphic_stability_score": 0.95,
            "compliance_theater_risk": 0.05,
            "ambiguity_flags": [],
            "invented_requirements": [],
            "missing_acceptance_criteria": [],
            "schema_pass": True,
        },
    )

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    await asyncio.sleep(0)

    payload = producer.publish.call_args.kwargs["value"]
    assert payload["passed_threshold"] is True


@pytest.mark.unit
async def test_all_failing_results_sets_passed_threshold_false() -> None:
    """When all scenarios fail, passed_threshold must be False."""
    command = _make_command(scenarios_per_spec=2)
    producer = _make_producer()
    llm = _make_llm_client(
        scenarios=["s1", "s2"],
        judgment={
            "metamorphic_stability_score": 0.1,
            "compliance_theater_risk": 0.9,
            "ambiguity_flags": ["flag1"],
            "invented_requirements": ["req1"],
            "missing_acceptance_criteria": ["crit1"],
            "schema_pass": False,
        },
    )

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    await asyncio.sleep(0)

    payload = producer.publish.call_args.kwargs["value"]
    assert payload["passed_threshold"] is False


# ---------------------------------------------------------------------------
# Tests: correlation_id propagated
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_correlation_id_propagated_to_payload() -> None:
    """correlation_id from the command must appear in the published payload."""
    command = ModelBloomEvalRunCommand(
        failure_mode=EnumFailureMode.COMPLIANCE_THEATER,
        correlation_id="test-correlation-123",
        scenarios_per_spec=1,
    )
    producer = _make_producer()
    llm = _make_llm_client(scenarios=["s1"])

    await run_bloom_eval(command, producer=producer, llm_client=llm)
    await asyncio.sleep(0)

    payload = producer.publish.call_args.kwargs["value"]
    assert payload["correlation_id"] == "test-correlation-123"


@pytest.mark.unit
async def test_run_bloom_eval_succeeds_without_producer() -> None:
    """run_bloom_eval must complete without error when no producer is injected."""
    command = _make_command()
    llm = _make_llm_client()

    # Should not raise even without a producer.
    await run_bloom_eval(command, llm_client=llm)
    await asyncio.sleep(0)


# ---------------------------------------------------------------------------
# Tests: ARCH-002 compliance
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_os_getenv_in_handler_module() -> None:
    """ARCH-002: handler module must not read env vars directly."""
    source = inspect.getsource(handler_mod)
    assert "os.getenv" not in source
    assert "os.environ" not in source


# ---------------------------------------------------------------------------
# Tests: ModelBloomEvalRunCommand defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_command_default_publish_topic() -> None:
    """Default publish_topic must be the canonical bloom-eval-completed topic."""
    command = ModelBloomEvalRunCommand(
        failure_mode=EnumFailureMode.REQUIREMENT_OMISSION
    )
    assert command.publish_topic == "onex.evt.omniintelligence.bloom-eval-completed.v1"


@pytest.mark.unit
def test_command_generates_unique_suite_id() -> None:
    """Two commands with same params must have different suite_ids."""
    a = ModelBloomEvalRunCommand(failure_mode=EnumFailureMode.REQUIREMENT_OMISSION)
    b = ModelBloomEvalRunCommand(failure_mode=EnumFailureMode.REQUIREMENT_OMISSION)
    assert a.suite_id != b.suite_id


@pytest.mark.unit
def test_command_is_frozen() -> None:
    """ModelBloomEvalRunCommand must be immutable (frozen Pydantic model)."""
    from pydantic import ValidationError

    command = ModelBloomEvalRunCommand(
        failure_mode=EnumFailureMode.REQUIREMENT_OMISSION
    )
    with pytest.raises((ValidationError, AttributeError)):
        command.failure_mode = EnumFailureMode.INVENTED_REQUIREMENTS
