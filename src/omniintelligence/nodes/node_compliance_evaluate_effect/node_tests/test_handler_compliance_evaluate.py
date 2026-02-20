# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handle_compliance_evaluate_command.

Covers:
- Compliant evaluation (no violations) — 3 tests
- Violating evaluation (violations found, signature enriched) — 2 tests
- LLM error path (structured error output) — 1 test
- Kafka publish on compliant and violating results — 2 tests
- Kafka publish failure -> DLQ routing — 1 test
- Kafka and DLQ both fail -> swallowed, no raise — 1 test
- No kafka_producer (graceful degradation) — 1 test
- Idempotency key fields present in event — 1 test
- Multi-pattern evaluation (patterns_checked count) — 1 test
- Processing timing (processing_time_ms populated) — 1 test
- evaluated_at timestamp (ISO-8601 string) — 1 test

Protocol conformance is asserted inline in Mock constructors
(MockLlmClient, MockKafkaProducer) via isinstance() checks.

Ticket: OMN-2339
"""

from __future__ import annotations

# _make_command and _make_pattern are imported directly as module-level helpers
# rather than being wrapped in pytest fixtures. This is intentional: these
# helpers accept arguments (e.g. custom patterns list, custom content), which
# makes them unsuitable as zero-argument pytest fixtures. Exposing them as
# fixtures would either require parameterization or force callers to import them
# anyway. Direct import keeps the test code explicit and avoids fixture overhead
# for helpers that build test data inline.
import hashlib
from uuid import UUID

import pytest

from omniintelligence.nodes.node_compliance_evaluate_effect.handlers import (
    handle_compliance_evaluate_command,
)
from omniintelligence.nodes.node_compliance_evaluate_effect.handlers.handler_compliance_evaluate import (
    DLQ_TOPIC,
    PUBLISH_TOPIC,
)
from omniintelligence.nodes.node_compliance_evaluate_effect.models import (
    ModelComplianceEvaluateCommand,
    ModelComplianceEvaluatedEvent,
)
from omniintelligence.nodes.node_compliance_evaluate_effect.node_tests.conftest import (
    FIXED_CONTENT_SHA256,
    FIXED_CORRELATION_ID,
    MockKafkaProducer,
    MockLlmClient,
    MockLlmClientError,
    _make_command,
    _make_pattern,
    sha256_of,
)

pytestmark = pytest.mark.unit

# =============================================================================
# Topic constants
# =============================================================================


def test_publish_topic_matches_contract() -> None:
    """PUBLISH_TOPIC constant matches contract.yaml publish_topics[0]."""
    assert PUBLISH_TOPIC == "onex.evt.omniintelligence.compliance-evaluated.v1"


def test_dlq_topic_is_publish_topic_with_dlq_suffix() -> None:
    """DLQ_TOPIC is PUBLISH_TOPIC with .dlq appended."""
    assert f"{PUBLISH_TOPIC}.dlq" == DLQ_TOPIC
    assert DLQ_TOPIC == "onex.evt.omniintelligence.compliance-evaluated.v1.dlq"


def test_fixed_content_sha256_matches_hash() -> None:
    """FIXED_CONTENT_SHA256 constant matches the actual SHA-256 of 'class Foo: pass'.

    Guards against the constant becoming stale if the literal content changes.
    This replaces the module-level bare assert that was stripped by Python's -O flag.
    """
    assert hashlib.sha256(b"class Foo: pass").hexdigest() == FIXED_CONTENT_SHA256, (
        "FIXED_CONTENT_SHA256 constant is stale — recompute sha256('class Foo: pass')"
    )


# =============================================================================
# Compliant path
# =============================================================================


@pytest.mark.asyncio
async def test_compliant_evaluation_returns_success(
    sample_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
) -> None:
    """Compliant code -> success=True, compliant=True, violations=[]."""
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=compliant_llm_client,
    )

    assert result.success is True
    assert result.compliant is True
    assert result.violations == []
    assert result.confidence > 0.0


@pytest.mark.asyncio
async def test_compliant_evaluation_propagates_identifiers(
    sample_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
    sample_correlation_id: UUID,
) -> None:
    """Event carries correct correlation_id, source_path, content_sha256."""
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=compliant_llm_client,
    )

    assert result.correlation_id == sample_correlation_id
    assert result.source_path == sample_command.source_path
    assert result.content_sha256 == FIXED_CONTENT_SHA256


@pytest.mark.asyncio
async def test_compliant_evaluation_event_type(
    sample_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
) -> None:
    """event_type is always 'ComplianceEvaluated'."""
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=compliant_llm_client,
    )

    assert result.event_type == "ComplianceEvaluated"


# =============================================================================
# Violating path
# =============================================================================


@pytest.mark.asyncio
async def test_violating_evaluation_returns_violations(
    sample_command: ModelComplianceEvaluateCommand,
    violating_llm_client: MockLlmClient,
) -> None:
    """Violating code -> success=True, compliant=False, violations non-empty."""
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=violating_llm_client,
    )

    assert result.success is True
    assert result.compliant is False
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.pattern_id == "P001"
    assert violation.severity == "major"
    assert violation.line_reference == "line 5"


@pytest.mark.asyncio
async def test_violation_pattern_signature_enriched(
    sample_command: ModelComplianceEvaluateCommand,
    violating_llm_client: MockLlmClient,
) -> None:
    """Violation includes pattern_signature from input patterns."""
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=violating_llm_client,
    )

    assert result.violations[0].pattern_signature == "Use frozen Pydantic models"


# =============================================================================
# LLM error path
# =============================================================================


@pytest.mark.asyncio
async def test_llm_error_returns_structured_failure(
    sample_command: ModelComplianceEvaluateCommand,
    error_llm_client: MockLlmClientError,
) -> None:
    """LLM inference failure -> success=False, confidence=0.0."""
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=error_llm_client,
    )

    assert result.success is False
    assert result.confidence == 0.0
    assert result.violations == []
    # Status reflects LLM inference failure
    assert result.status == "llm_error"


# =============================================================================
# Kafka publish
# =============================================================================


@pytest.mark.asyncio
async def test_kafka_publish_on_compliant_result(
    sample_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
    mock_kafka_producer: MockKafkaProducer,
) -> None:
    """When kafka_producer is provided, event is published to PUBLISH_TOPIC."""
    await handle_compliance_evaluate_command(
        sample_command,
        llm_client=compliant_llm_client,
        kafka_producer=mock_kafka_producer,
    )

    assert len(mock_kafka_producer.published) == 1
    publish_call = mock_kafka_producer.published[0]
    assert publish_call["topic"] == PUBLISH_TOPIC
    value = publish_call["value"]
    assert isinstance(value, dict)
    assert value["event_type"] == "ComplianceEvaluated"
    assert value["compliant"] is True


@pytest.mark.asyncio
async def test_kafka_publish_on_violating_result(
    sample_command: ModelComplianceEvaluateCommand,
    violating_llm_client: MockLlmClient,
    mock_kafka_producer: MockKafkaProducer,
) -> None:
    """Violation result is also published to Kafka."""
    await handle_compliance_evaluate_command(
        sample_command,
        llm_client=violating_llm_client,
        kafka_producer=mock_kafka_producer,
    )

    assert len(mock_kafka_producer.published) == 1
    value = mock_kafka_producer.published[0]["value"]
    assert isinstance(value, dict)
    assert value["compliant"] is False
    violations = value.get("violations")
    assert isinstance(violations, list)
    assert len(violations) == 1


@pytest.mark.asyncio
async def test_no_kafka_producer_no_publish(
    sample_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
) -> None:
    """When kafka_producer is None, no publish is attempted (graceful degradation)."""
    # Should not raise; handler returns event without publishing
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=compliant_llm_client,
        kafka_producer=None,
    )

    assert result.success is True


@pytest.mark.asyncio
async def test_kafka_publish_failure_routes_to_dlq(
    sample_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
    mock_kafka_producer: MockKafkaProducer,
) -> None:
    """When kafka publish fails, DLQ entry is published and no exception raised."""
    # First call (publish) fails; second call (DLQ) succeeds
    call_count = 0
    original_publish = mock_kafka_producer.publish

    async def fail_first_then_succeed(
        topic: str, key: str, value: dict[str, object]
    ) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Kafka unavailable")
        mock_kafka_producer.published.append(
            {"topic": topic, "key": key, "value": value}
        )

    mock_kafka_producer.publish = fail_first_then_succeed  # type: ignore[method-assign]

    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=compliant_llm_client,
        kafka_producer=mock_kafka_producer,
    )

    # Handler should succeed (event returned) even when publish fails
    assert result.success is True
    # DLQ should have received one publish
    assert len(mock_kafka_producer.published) == 1
    assert mock_kafka_producer.published[0]["topic"] == DLQ_TOPIC

    # Restore original publish (cleanup)
    mock_kafka_producer.publish = original_publish  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_kafka_and_dlq_failure_is_swallowed(
    sample_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
    mock_kafka_producer: MockKafkaProducer,
) -> None:
    """When both kafka publish and DLQ publish fail, no exception propagates."""
    mock_kafka_producer.simulate_error = RuntimeError("total Kafka failure")

    # Should not raise
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=compliant_llm_client,
        kafka_producer=mock_kafka_producer,
    )

    assert result.success is True


# =============================================================================
# Idempotency key fields
# =============================================================================


@pytest.mark.asyncio
async def test_idempotency_fields_match_command_source_and_sha256(
    sample_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
) -> None:
    """Event includes source_path and content_sha256 for idempotency keying."""
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=compliant_llm_client,
    )

    assert result.source_path == sample_command.source_path
    assert result.content_sha256 == sample_command.content_sha256


@pytest.mark.asyncio
async def test_real_sha256_matches_content(
    real_sha256_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
) -> None:
    """content_sha256 is the actual SHA-256 of content, not a placeholder."""
    expected_sha256 = sha256_of(real_sha256_command.content)
    assert real_sha256_command.content_sha256 == expected_sha256

    result = await handle_compliance_evaluate_command(
        real_sha256_command,
        llm_client=compliant_llm_client,
    )

    assert result.content_sha256 == expected_sha256


# =============================================================================
# Multi-pattern evaluation
# =============================================================================


@pytest.mark.asyncio
async def test_patterns_checked_reflects_applicable_patterns_count(
    compliant_llm_client: MockLlmClient,
) -> None:
    """patterns_checked in event reflects number of applicable_patterns."""
    patterns = [
        _make_pattern("P001"),
        _make_pattern("P002", signature="Handlers must not raise"),
    ]
    command = _make_command(patterns=patterns)

    result = await handle_compliance_evaluate_command(
        command,
        llm_client=compliant_llm_client,
    )

    assert result.patterns_checked == 2


# =============================================================================
# Processing timing
# =============================================================================


@pytest.mark.asyncio
async def test_processing_time_is_populated(
    sample_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
) -> None:
    """processing_time_ms is a non-negative float."""
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=compliant_llm_client,
    )

    assert result.processing_time_ms is not None
    assert result.processing_time_ms >= 0.0


# =============================================================================
# evaluated_at timestamp
# =============================================================================


@pytest.mark.asyncio
async def test_evaluated_at_is_iso_string(
    sample_command: ModelComplianceEvaluateCommand,
    compliant_llm_client: MockLlmClient,
) -> None:
    """evaluated_at is a non-empty ISO-8601 string."""
    result = await handle_compliance_evaluate_command(
        sample_command,
        llm_client=compliant_llm_client,
    )

    assert isinstance(result.evaluated_at, str)
    assert "T" in result.evaluated_at  # basic ISO-8601 check


# =============================================================================
# session_id propagation (OMN-2368)
# =============================================================================


def test_compliance_evaluate_command_accepts_session_id() -> None:
    """ModelComplianceEvaluateCommand accepts and stores session_id."""
    cmd = _make_command(session_id="test-session-123")
    assert cmd.session_id == "test-session-123"


def test_compliance_evaluate_command_session_id_defaults_to_none() -> None:
    """session_id defaults to None when not provided."""
    cmd = _make_command()
    assert cmd.session_id is None


def test_compliance_evaluated_event_carries_session_id() -> None:
    """ModelComplianceEvaluatedEvent accepts and stores session_id."""
    evt = ModelComplianceEvaluatedEvent(
        correlation_id=FIXED_CORRELATION_ID,
        source_path="foo.py",
        content_sha256="a" * 64,
        success=True,
        evaluated_at="2026-02-19T00:00:00Z",
        session_id="test-session-123",
    )
    assert evt.session_id == "test-session-123"


def test_compliance_evaluated_event_session_id_defaults_to_none() -> None:
    """ModelComplianceEvaluatedEvent session_id defaults to None."""
    evt = ModelComplianceEvaluatedEvent(
        correlation_id=FIXED_CORRELATION_ID,
        source_path="foo.py",
        content_sha256="a" * 64,
        success=True,
        evaluated_at="2026-02-19T00:00:00Z",
    )
    assert evt.session_id is None


@pytest.mark.asyncio
async def test_session_id_propagated_from_command_to_event(
    compliant_llm_client: MockLlmClient,
) -> None:
    """Handler propagates session_id from command to the returned event."""
    command = _make_command(session_id="session-abc-456")
    result = await handle_compliance_evaluate_command(
        command,
        llm_client=compliant_llm_client,
    )
    assert result.session_id == "session-abc-456"


@pytest.mark.asyncio
async def test_session_id_none_propagated_from_command_to_event(
    compliant_llm_client: MockLlmClient,
) -> None:
    """Handler propagates session_id=None from command when not set."""
    command = _make_command()
    result = await handle_compliance_evaluate_command(
        command,
        llm_client=compliant_llm_client,
    )
    assert result.session_id is None


@pytest.mark.asyncio
async def test_session_id_in_kafka_payload(
    compliant_llm_client: MockLlmClient,
    mock_kafka_producer: MockKafkaProducer,
) -> None:
    """session_id is included in the published Kafka payload."""
    command = _make_command(session_id="kafka-session-789")
    await handle_compliance_evaluate_command(
        command,
        llm_client=compliant_llm_client,
        kafka_producer=mock_kafka_producer,
    )
    assert len(mock_kafka_producer.published) == 1
    payload = mock_kafka_producer.published[0]["value"]
    assert isinstance(payload, dict)
    assert payload.get("session_id") == "kafka-session-789"


# =============================================================================
# sha256 mismatch validation
# =============================================================================


@pytest.mark.asyncio
async def test_sha256_mismatch_returns_validation_error(
    compliant_llm_client: MockLlmClient,
    mock_kafka_producer: MockKafkaProducer,
) -> None:
    """A content_sha256 that does not match the actual SHA-256 of content
    returns success=False with status='validation_error' and never calls the LLM.
    A DLQ entry is also published when kafka_producer is available.
    """
    # "b" * 64 is a valid 64-char lowercase hex string but intentionally wrong
    # for the content "class Foo: pass" (whose real sha256 is FIXED_CONTENT_SHA256).
    wrong_sha256 = "b" * 64
    assert wrong_sha256 != FIXED_CONTENT_SHA256, (
        "Sanity: wrong_sha256 must differ from the actual sha256 of the content"
    )

    command = _make_command(
        content="class Foo: pass",
        content_sha256=wrong_sha256,
    )

    result = await handle_compliance_evaluate_command(
        command,
        llm_client=compliant_llm_client,
        kafka_producer=mock_kafka_producer,
    )

    assert result.success is False
    assert result.status == "validation_error"
    # LLM must not have been called — mismatch is caught before inference
    assert compliant_llm_client.call_count == 0
    # DLQ must have received exactly one entry
    assert len(mock_kafka_producer.published) == 1
    dlq_entry = mock_kafka_producer.published[0]
    assert dlq_entry["topic"] == DLQ_TOPIC
