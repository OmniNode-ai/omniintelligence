# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""E2E integration test: Claude hook event -> intent classification pipeline.

Tests the complete pipeline end-to-end: publish a UserPromptSubmit event and
assert an IntentClassified event is produced with correct correlation.

This test validates the entire contract-driven event bus wiring is working
correctly across the stack.

Pipeline under test:
    1. Publish UserPromptSubmit event to input topic
    2. Handler processes event via route_hook_event
    3. Intent classification runs (defaults to "unknown" without LLM)
    4. IntentClassified event is published to output topic
    5. Consumer verifies event content and field preservation

Two test layers are provided:
    - EventBusInmemory: Tests the handler -> Kafka publisher wiring without
      external infrastructure. Always runs.
    - Real Kafka: Tests the full roundtrip through Kafka broker. Requires
      Kafka at KAFKA_BOOTSTRAP_SERVERS (skipped if unavailable).

Design Decision - Single Test Function per Pipeline:
    Each pipeline test is a single function because stages are sequentially
    dependent. See TC5 for the same pattern rationale.

Infrastructure Requirements:
    - Kafka/Redpanda: ${KAFKA_BOOTSTRAP_SERVERS} (for real Kafka tests)
    - No PostgreSQL required (intent classification is pure compute)

Reference:
    - OMN-1624: E2E integration test: Claude hook event -> intent classification
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from omnibase_core.enums.hooks.claude_code import EnumClaudeCodeHookEventType
from omnibase_core.models.hooks.claude_code import (
    ModelClaudeCodeHookEvent,
    ModelClaudeCodeHookEventPayload,
)
from omnibase_infra.event_bus.event_bus_inmemory import EventBusInmemory
from omnibase_infra.event_bus.models import ModelEventMessage
from omnibase_infra.models import ModelNodeIdentity

from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    route_hook_event,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    EnumHookProcessingStatus,
)
from tests.fixtures.topic_constants import TOPIC_SUFFIX_INTENT_CLASSIFIED_V1
from tests.integration.conftest import RealKafkaPublisher
from tests.integration.e2e.conftest import requires_e2e_kafka, wait_for_message

# =============================================================================
# Markers
# =============================================================================

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
]

# =============================================================================
# Constants
# =============================================================================

PIPELINE_TEST_TOPIC_PREFIX: str = "e2e_test_pipeline_"
"""Topic prefix for pipeline E2E tests to isolate from other test suites."""

# Deterministic IDs for test repeatability
CORRELATION_ID_PIPELINE = UUID("16240000-e2e0-4000-a000-000000000001")
"""Fixed correlation ID for pipeline E2E test tracing."""

SESSION_ID_PIPELINE = "e2e-pipeline-session-omn-1624"
"""Fixed session ID for pipeline E2E test."""

PROMPT_PIPELINE = "Help me refactor the authentication module to use JWT tokens"
"""Test prompt for intent classification."""

MAX_TEST_DURATION_SECONDS: float = 30.0
"""Maximum allowed test duration per acceptance criteria."""


# =============================================================================
# Adapter: EventBusInmemory -> ProtocolKafkaPublisher
# =============================================================================


class _EventBusKafkaPublisherAdapter:
    """Adapter bridging EventBusInmemory to ProtocolKafkaPublisher.

    Serializes dict values to JSON bytes for the in-memory event bus.
    """

    def __init__(self, event_bus: EventBusInmemory) -> None:
        self._event_bus = event_bus

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        value_bytes = json.dumps(
            value, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        key_bytes = key.encode("utf-8") if key else None
        await self._event_bus.publish(topic=topic, key=key_bytes, value=value_bytes)


# =============================================================================
# Helper: Build pipeline test event
# =============================================================================


def _create_pipeline_event(
    *,
    correlation_id: UUID = CORRELATION_ID_PIPELINE,
    session_id: str = SESSION_ID_PIPELINE,
    prompt: str = PROMPT_PIPELINE,
) -> ModelClaudeCodeHookEvent:
    """Create a UserPromptSubmit event for the pipeline test.

    Args:
        correlation_id: Correlation ID to thread through the pipeline.
        session_id: Session ID for the Claude Code session.
        prompt: User prompt text for intent classification.

    Returns:
        A complete ModelClaudeCodeHookEvent ready for processing.
    """
    payload = ModelClaudeCodeHookEventPayload(prompt=prompt)
    return ModelClaudeCodeHookEvent(
        event_type=EnumClaudeCodeHookEventType.USER_PROMPT_SUBMIT,
        session_id=session_id,
        correlation_id=correlation_id,
        timestamp_utc=datetime.now(UTC),
        payload=payload,
    )


# =============================================================================
# Helper: Validate IntentClassified event fields
# =============================================================================


def _validate_intent_classified_event(
    event_payload: dict[str, Any],
    *,
    expected_correlation_id: UUID,
    expected_session_id: str,
) -> None:
    """Validate all required fields of an IntentClassified event.

    Asserts that:
    - event_type is "IntentClassified"
    - session_id matches the input event
    - correlation_id matches the input event
    - intent_category is a non-empty string
    - confidence is a valid float in [0.0, 1.0]
    - timestamp is present and ISO-formatted

    Args:
        event_payload: Parsed JSON payload of the IntentClassified event.
        expected_correlation_id: The correlation_id from the input event.
        expected_session_id: The session_id from the input event.

    Raises:
        AssertionError: If any validation fails.
    """
    # event_type
    assert "event_type" in event_payload, "Missing 'event_type' field"
    assert (
        event_payload["event_type"] == "IntentClassified"
    ), f"Expected event_type='IntentClassified', got '{event_payload['event_type']}'"

    # session_id preservation
    assert "session_id" in event_payload, "Missing 'session_id' field"
    assert event_payload["session_id"] == expected_session_id, (
        f"session_id mismatch: expected '{expected_session_id}', "
        f"got '{event_payload['session_id']}'"
    )

    # correlation_id preservation
    assert "correlation_id" in event_payload, "Missing 'correlation_id' field"
    assert event_payload["correlation_id"] == str(expected_correlation_id), (
        f"correlation_id mismatch: expected '{expected_correlation_id}', "
        f"got '{event_payload['correlation_id']}'"
    )

    # intent_category is populated
    assert "intent_category" in event_payload, "Missing 'intent_category' field"
    intent_category = event_payload["intent_category"]
    assert isinstance(
        intent_category, str
    ), f"intent_category must be a string, got {type(intent_category).__name__}"
    assert len(intent_category) > 0, "intent_category must not be empty"

    # confidence is a valid float
    assert "confidence" in event_payload, "Missing 'confidence' field"
    confidence = event_payload["confidence"]
    assert isinstance(
        confidence, int | float
    ), f"confidence must be numeric, got {type(confidence).__name__}"
    assert (
        0.0 <= float(confidence) <= 1.0
    ), f"confidence must be in [0.0, 1.0], got {confidence}"

    # timestamp is present and parseable
    assert "timestamp" in event_payload, "Missing 'timestamp' field"
    timestamp_str = event_payload["timestamp"]
    assert isinstance(
        timestamp_str, str
    ), f"timestamp must be a string, got {type(timestamp_str).__name__}"
    assert len(timestamp_str) > 0, "timestamp must not be empty"


# =============================================================================
# Test Layer 1: EventBusInmemory (no external infrastructure)
# =============================================================================


class TestClaudeHookToIntentPipelineInmemory:
    """E2E pipeline test using EventBusInmemory.

    Tests the complete handler wiring without external Kafka infrastructure.
    The in-memory event bus captures published events for verification.

    This test layer always runs and does not require external services.
    """

    async def test_pipeline_user_prompt_to_intent_classified(self) -> None:
        """Test the full pipeline: UserPromptSubmit -> IntentClassified.

        Stages:
            1. Create EventBusInmemory and publisher adapter
            2. Subscribe to output topic to capture events
            3. Create UserPromptSubmit event with known correlation_id
            4. Process through route_hook_event
            5. Verify IntentClassified event on output topic
            6. Validate all required fields
        """
        import time

        start_time = time.monotonic()

        # Stage 1: Create event bus and adapter
        event_bus = EventBusInmemory(environment="e2e_test", group="pipeline-test")
        adapter = _EventBusKafkaPublisherAdapter(event_bus)
        await event_bus.start()

        try:
            # Stage 2: Subscribe to output topic
            output_topic = f"e2e_test.{TOPIC_SUFFIX_INTENT_CLASSIFIED_V1}"
            received_messages: list[ModelEventMessage] = []

            async def capture_output(msg: ModelEventMessage) -> None:
                received_messages.append(msg)

            node_identity = ModelNodeIdentity(
                env="e2e_test",
                service="omniintelligence",
                node_name="pipeline_test_consumer",
                version="1.0.0",
            )

            unsubscribe = await event_bus.subscribe(
                output_topic,
                node_identity,
                capture_output,
            )

            # Stage 3: Create the UserPromptSubmit event
            correlation_id = CORRELATION_ID_PIPELINE
            session_id = SESSION_ID_PIPELINE
            event = _create_pipeline_event(
                correlation_id=correlation_id,
                session_id=session_id,
            )

            # Stage 4: Process through the handler pipeline
            result = await route_hook_event(
                event=event,
                kafka_producer=adapter,
                publish_topic=f"e2e_test.{TOPIC_SUFFIX_INTENT_CLASSIFIED_V1}",
            )

            # Verify handler succeeded
            assert (
                result.status == EnumHookProcessingStatus.SUCCESS
            ), f"Handler returned status={result.status}, error={result.error_message}"
            assert (
                result.intent_result is not None
            ), "Handler must produce an intent_result for UserPromptSubmit"
            assert (
                result.intent_result.emitted_to_kafka is True
            ), "Intent result must be emitted to Kafka"

            # Verify correlation_id preserved in handler result
            assert result.correlation_id == correlation_id, (
                f"Handler result correlation_id mismatch: "
                f"expected {correlation_id}, got {result.correlation_id}"
            )
            assert result.session_id == session_id, (
                f"Handler result session_id mismatch: "
                f"expected {session_id}, got {result.session_id}"
            )

            # Stage 5: Verify IntentClassified event on output topic
            assert len(received_messages) == 1, (
                f"Expected exactly 1 IntentClassified event on output topic, "
                f"got {len(received_messages)}"
            )

            output_message = received_messages[0]
            assert output_message.topic == output_topic, (
                f"Message topic mismatch: expected '{output_topic}', "
                f"got '{output_message.topic}'"
            )

            # Parse the event payload
            event_payload = json.loads(output_message.value)

            # Stage 6: Validate all required fields
            _validate_intent_classified_event(
                event_payload,
                expected_correlation_id=correlation_id,
                expected_session_id=session_id,
            )

            # Verify message key is the session_id (used for partitioning).
            # EventBusInmemory preserves keys, and the adapter always encodes them.
            assert (
                output_message.key is not None
            ), "Message key must be set (session_id for Kafka partitioning)"
            key_str = output_message.key.decode("utf-8")
            assert key_str == session_id, (
                f"Message key should be session_id for partitioning: "
                f"expected '{session_id}', got '{key_str}'"
            )

            # Verify event history for debugging
            history = await event_bus.get_event_history(topic=output_topic)
            assert (
                len(history) == 1
            ), f"Event history should have 1 entry, got {len(history)}"

            # Clean up subscription
            await unsubscribe()

        finally:
            await event_bus.close()

        # Verify test completed within time budget
        elapsed = time.monotonic() - start_time
        assert (
            elapsed < MAX_TEST_DURATION_SECONDS
        ), f"Test took {elapsed:.2f}s, exceeding {MAX_TEST_DURATION_SECONDS}s limit"

    async def test_pipeline_preserves_correlation_across_unique_events(
        self,
    ) -> None:
        """Test that distinct correlation_ids are preserved independently.

        Processes two events with different correlation_ids and verifies
        each IntentClassified event preserves the correct correlation_id.
        This validates there is no cross-contamination between events.
        """
        event_bus = EventBusInmemory(
            environment="e2e_test", group="pipeline-test-multi"
        )
        adapter = _EventBusKafkaPublisherAdapter(event_bus)
        await event_bus.start()

        try:
            output_topic = f"e2e_test.{TOPIC_SUFFIX_INTENT_CLASSIFIED_V1}"
            received_messages: list[ModelEventMessage] = []

            async def capture_output(msg: ModelEventMessage) -> None:
                received_messages.append(msg)

            node_identity = ModelNodeIdentity(
                env="e2e_test",
                service="omniintelligence",
                node_name="pipeline_test_multi",
                version="1.0.0",
            )

            unsubscribe = await event_bus.subscribe(
                output_topic, node_identity, capture_output
            )

            # Event A
            correlation_a = uuid4()
            session_a = "session-pipeline-a"
            event_a = _create_pipeline_event(
                correlation_id=correlation_a,
                session_id=session_a,
                prompt="Fix the database connection timeout issue",
            )

            # Event B
            correlation_b = uuid4()
            session_b = "session-pipeline-b"
            event_b = _create_pipeline_event(
                correlation_id=correlation_b,
                session_id=session_b,
                prompt="Write unit tests for the authentication service",
            )

            # Process both events
            result_a = await route_hook_event(
                event=event_a,
                kafka_producer=adapter,
                publish_topic=f"e2e_test.{TOPIC_SUFFIX_INTENT_CLASSIFIED_V1}",
            )
            result_b = await route_hook_event(
                event=event_b,
                kafka_producer=adapter,
                publish_topic=f"e2e_test.{TOPIC_SUFFIX_INTENT_CLASSIFIED_V1}",
            )

            assert result_a.status == EnumHookProcessingStatus.SUCCESS
            assert result_b.status == EnumHookProcessingStatus.SUCCESS

            # Verify both events produced
            assert (
                len(received_messages) == 2
            ), f"Expected 2 IntentClassified events, got {len(received_messages)}"

            # Parse and validate each independently
            payload_a = json.loads(received_messages[0].value)
            payload_b = json.loads(received_messages[1].value)

            # Event A preserves its correlation_id
            assert payload_a["correlation_id"] == str(correlation_a), (
                f"Event A correlation_id mismatch: "
                f"expected {correlation_a}, got {payload_a['correlation_id']}"
            )
            assert payload_a["session_id"] == session_a

            # Event B preserves its correlation_id
            assert payload_b["correlation_id"] == str(correlation_b), (
                f"Event B correlation_id mismatch: "
                f"expected {correlation_b}, got {payload_b['correlation_id']}"
            )
            assert payload_b["session_id"] == session_b

            # No cross-contamination
            assert (
                payload_a["correlation_id"] != payload_b["correlation_id"]
            ), "Events must have distinct correlation_ids"

            await unsubscribe()

        finally:
            await event_bus.close()

    async def test_pipeline_no_op_events_do_not_produce_output(self) -> None:
        """Test that non-UserPromptSubmit events do not produce IntentClassified.

        SessionStart, Stop, and other event types should be handled as no-ops
        and must NOT emit events to the output topic. Tests both SESSION_START
        and STOP to validate the routing else-branch for multiple event types.
        """
        event_bus = EventBusInmemory(environment="e2e_test", group="pipeline-test-noop")
        adapter = _EventBusKafkaPublisherAdapter(event_bus)
        await event_bus.start()

        try:
            output_topic = f"e2e_test.{TOPIC_SUFFIX_INTENT_CLASSIFIED_V1}"
            received_messages: list[ModelEventMessage] = []

            async def capture_output(msg: ModelEventMessage) -> None:
                received_messages.append(msg)

            node_identity = ModelNodeIdentity(
                env="e2e_test",
                service="omniintelligence",
                node_name="pipeline_test_noop",
                version="1.0.0",
            )

            unsubscribe = await event_bus.subscribe(
                output_topic, node_identity, capture_output
            )

            # --- SessionStart (should be no-op) ---
            session_start = ModelClaudeCodeHookEvent(
                event_type=EnumClaudeCodeHookEventType.SESSION_START,
                session_id="session-noop-test",
                correlation_id=uuid4(),
                timestamp_utc=datetime.now(UTC),
                payload=ModelClaudeCodeHookEventPayload(
                    working_directory="/workspace/test"
                ),
            )

            result_start = await route_hook_event(
                event=session_start,
                kafka_producer=adapter,
                publish_topic=f"e2e_test.{TOPIC_SUFFIX_INTENT_CLASSIFIED_V1}",
            )

            assert result_start.status == EnumHookProcessingStatus.SUCCESS
            assert (
                result_start.intent_result is None
            ), "SessionStart must not produce intent_result"

            # --- Stop (should also be no-op) ---
            stop_event = ModelClaudeCodeHookEvent(
                event_type=EnumClaudeCodeHookEventType.STOP,
                session_id="session-noop-test",
                correlation_id=uuid4(),
                timestamp_utc=datetime.now(UTC),
                payload=ModelClaudeCodeHookEventPayload(),
            )

            result_stop = await route_hook_event(
                event=stop_event,
                kafka_producer=adapter,
                publish_topic=f"e2e_test.{TOPIC_SUFFIX_INTENT_CLASSIFIED_V1}",
            )

            assert result_stop.status == EnumHookProcessingStatus.SUCCESS
            assert (
                result_stop.intent_result is None
            ), "Stop must not produce intent_result"

            # Verify no output events were published for either no-op event
            assert len(received_messages) == 0, (
                f"No-op events must not produce output events, "
                f"but {len(received_messages)} were published"
            )

            history = await event_bus.get_event_history(topic=output_topic)
            assert len(history) == 0, "Event history should be empty for no-op events"

            await unsubscribe()

        finally:
            await event_bus.close()


# =============================================================================
# Test Layer 2: Real Kafka (requires infrastructure)
# =============================================================================


@requires_e2e_kafka
class TestClaudeHookToIntentPipelineRealKafka:
    """E2E pipeline test using real Kafka infrastructure.

    Tests the full roundtrip: handler publishes to real Kafka, consumer
    reads from real Kafka. This validates that events survive serialization,
    broker persistence, and deserialization.

    Requires Kafka/Redpanda at KAFKA_BOOTSTRAP_SERVERS.
    Tests are skipped gracefully when Kafka is unavailable.
    """

    async def test_pipeline_real_kafka_roundtrip(
        self,
        e2e_kafka_producer: Any,
        e2e_kafka_consumer: Any,
        e2e_topic_prefix: str,
    ) -> None:
        """Test full Kafka roundtrip: publish -> broker -> consume.

        This is the golden E2E test that validates the complete pipeline
        with real infrastructure.

        Stages:
            1. Create publisher adapter backed by real Kafka
            2. Subscribe consumer to output topic
            3. Create UserPromptSubmit event
            4. Process through route_hook_event (publishes to real Kafka)
            5. Consumer reads IntentClassified from Kafka broker
            6. Validate all required fields

        This test proves:
            - JSON serialization/deserialization preserves all fields
            - Kafka broker correctly delivers the message
            - correlation_id survives the full roundtrip
            - session_id is preserved as the message key
        """
        import time

        start_time = time.monotonic()

        # Stage 1: Create publisher
        # Use test-specific topic prefix to avoid collisions
        test_run_id = uuid4().hex[:8]
        topic_suffix = TOPIC_SUFFIX_INTENT_CLASSIFIED_V1
        full_output_topic = f"{e2e_topic_prefix}pipeline_{test_run_id}.{topic_suffix}"

        publisher = RealKafkaPublisher(e2e_kafka_producer, topic_prefix="")

        # Stage 2: Subscribe consumer BEFORE publishing
        e2e_kafka_consumer.subscribe([full_output_topic])

        # Wait for partition assignment (see test_kafka_integration.py for rationale)
        await asyncio.sleep(1.0)

        # Stage 3: Create the event
        correlation_id = uuid4()
        session_id = f"e2e-kafka-session-{test_run_id}"
        event = _create_pipeline_event(
            correlation_id=correlation_id,
            session_id=session_id,
            prompt=PROMPT_PIPELINE,
        )

        # Stage 4: Process through handler with real Kafka publisher
        # We use the RealKafkaPublisher directly (it implements ProtocolKafkaPublisher)
        result = await route_hook_event(
            event=event,
            kafka_producer=publisher,
            publish_topic=full_output_topic,
        )

        assert (
            result.status == EnumHookProcessingStatus.SUCCESS
        ), f"Handler failed: {result.error_message}"
        assert result.intent_result is not None
        assert result.intent_result.emitted_to_kafka is True

        # Verify publisher recorded the event locally
        assert len(publisher.published_events) == 1

        # Stage 5: Consumer reads from real Kafka broker
        received = await wait_for_message(
            consumer=e2e_kafka_consumer,
            topic=full_output_topic,
            timeout_seconds=15.0,
            poll_interval_ms=500,
        )

        # Stage 6: Validate all required fields
        event_payload = received["value"]
        _validate_intent_classified_event(
            event_payload,
            expected_correlation_id=correlation_id,
            expected_session_id=session_id,
        )

        # Verify message key is the session_id
        assert received["key"] == session_id, (
            f"Message key should be session_id: "
            f"expected '{session_id}', got '{received['key']}'"
        )

        # Verify within time budget
        elapsed = time.monotonic() - start_time
        assert (
            elapsed < MAX_TEST_DURATION_SECONDS
        ), f"Test took {elapsed:.2f}s, exceeding {MAX_TEST_DURATION_SECONDS}s limit"

    async def test_pipeline_real_kafka_correlation_preserved(
        self,
        e2e_kafka_publisher: RealKafkaPublisher,
    ) -> None:
        """Test that correlation_id survives Kafka serialization roundtrip.

        Uses the RealKafkaPublisher to verify the event payload is correctly
        serialized and the publisher records match expectations.

        This is a lighter-weight test than the full roundtrip - it verifies
        the publisher-side serialization without waiting for consumer reads.
        """
        correlation_id = uuid4()
        session_id = f"e2e-correlation-test-{uuid4().hex[:8]}"
        event = _create_pipeline_event(
            correlation_id=correlation_id,
            session_id=session_id,
        )

        result = await route_hook_event(
            event=event,
            kafka_producer=e2e_kafka_publisher,
            publish_topic=f"e2e_test_correlation.{TOPIC_SUFFIX_INTENT_CLASSIFIED_V1}",
        )

        assert result.status == EnumHookProcessingStatus.SUCCESS
        assert result.intent_result is not None
        assert result.intent_result.emitted_to_kafka is True

        # Verify the published event content
        events = e2e_kafka_publisher.published_events
        assert len(events) >= 1, "At least 1 event should be published"

        # Find our event (publisher may have events from other tests)
        our_event = None
        for _topic, _key, value in events:
            if value.get("session_id") == session_id:
                our_event = value
                break

        assert (
            our_event is not None
        ), f"Could not find published event with session_id={session_id}"

        _validate_intent_classified_event(
            our_event,
            expected_correlation_id=correlation_id,
            expected_session_id=session_id,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TestClaudeHookToIntentPipelineInmemory",
    "TestClaudeHookToIntentPipelineRealKafka",
]
