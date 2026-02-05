# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""E2E tests verifying real Kafka integration.

This module tests the real Kafka integration infrastructure provided by the
E2E fixtures. It verifies that:
- The RealKafkaPublisher can connect to Kafka and publish events
- Events are properly recorded for test assertion
- The consumer can verify events were actually published
- Topic isolation via prefix works correctly

These tests require real Kafka infrastructure at 192.168.86.200:29092.
Tests are skipped gracefully when Kafka is unavailable.

Reference:
    - OMN-1800: E2E integration tests for pattern learning pipeline
    - tests/integration/e2e/conftest.py: Kafka fixture definitions
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest

from tests.integration.conftest import RealKafkaPublisher
from tests.integration.e2e.conftest import requires_e2e_kafka


# =============================================================================
# Constants
# =============================================================================

UUID_STRING_LENGTH: int = 36
"""Length of a UUID string in standard format (8-4-4-4-12 with dashes)."""


# =============================================================================
# Kafka Publisher Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_real_kafka_publisher_publishes_events(
    e2e_kafka_publisher: RealKafkaPublisher,
    e2e_topic_prefix: str,
) -> None:
    """Test that RealKafkaPublisher successfully publishes events to Kafka.

    Verifies:
    - The publisher can connect and publish without errors
    - Published events are recorded in published_events list
    - The full topic (with prefix) is used
    """
    # Arrange
    topic = "test-topic"
    key = "test-key"
    value = {"event_type": "test", "data": "hello"}

    # Act
    await e2e_kafka_publisher.publish(topic, key, value)

    # Assert: Event is recorded
    assert len(e2e_kafka_publisher.published_events) == 1

    recorded = e2e_kafka_publisher.published_events[0]
    recorded_topic, recorded_key, recorded_value = recorded
    assert recorded_topic == f"{e2e_topic_prefix}{topic}"
    assert recorded_key == key
    assert recorded_value == value


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_real_kafka_publisher_multiple_events(
    e2e_kafka_publisher: RealKafkaPublisher,
) -> None:
    """Test publishing multiple events to different topics.

    Verifies that the publisher can handle multiple sequential publishes
    and that get_events_for_topic correctly filters by topic.
    """
    # Arrange
    events = [
        ("topic-a", "key-1", {"type": "A", "id": 1}),
        ("topic-b", "key-2", {"type": "B", "id": 2}),
        ("topic-a", "key-3", {"type": "A", "id": 3}),
    ]

    # Act
    for topic, key, value in events:
        await e2e_kafka_publisher.publish(topic, key, value)

    # Assert: All events recorded
    assert len(e2e_kafka_publisher.published_events) == 3

    # Assert: Filter by topic works
    topic_a_events = e2e_kafka_publisher.get_events_for_topic("topic-a")
    assert len(topic_a_events) == 2

    topic_b_events = e2e_kafka_publisher.get_events_for_topic("topic-b")
    assert len(topic_b_events) == 1


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_real_kafka_publisher_reset(
    e2e_kafka_publisher: RealKafkaPublisher,
) -> None:
    """Test that reset() clears published events.

    Useful for tests that need to verify events in phases.
    """
    # Arrange: Publish some events
    await e2e_kafka_publisher.publish("topic", "key", {"data": 1})
    await e2e_kafka_publisher.publish("topic", "key", {"data": 2})
    assert len(e2e_kafka_publisher.published_events) == 2

    # Act: Reset
    e2e_kafka_publisher.reset()

    # Assert: Events cleared
    assert len(e2e_kafka_publisher.published_events) == 0


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_topic_prefix_provides_isolation(
    e2e_topic_prefix: str,
) -> None:
    """Test that topic prefix is unique per session.

    Verifies the isolation mechanism that prevents test pollution.
    """
    # Assert: Prefix has expected format
    assert e2e_topic_prefix.startswith("e2e_test_")
    assert e2e_topic_prefix.endswith("_")

    # Assert: Contains a unique identifier (8 hex chars)
    middle = e2e_topic_prefix[9:-1]  # Remove "e2e_test_" and "_"
    assert len(middle) == 8
    int(middle, 16)  # Should parse as hex


# =============================================================================
# Kafka Consumer Verification Tests
# =============================================================================


async def wait_for_message(
    consumer: Any,
    topic: str,
    timeout_seconds: float = 10.0,
    poll_interval_ms: int = 500,
) -> dict[str, Any]:
    """Wait for a message on topic, raising AssertionError if not received.

    This helper polls the Kafka consumer with explicit timeouts and retry logic
    to reliably receive messages in E2E tests. Unlike relying on async iteration
    timeout behavior, this provides deterministic failure when messages aren't
    received.

    Args:
        consumer: AIOKafkaConsumer instance (already started and subscribed).
        topic: The topic to wait for a message on.
        timeout_seconds: Maximum time to wait for a message (default: 10s).
        poll_interval_ms: Time between poll attempts in milliseconds (default: 500ms).

    Returns:
        Dictionary with 'key', 'value', and 'topic' from the received message.

    Raises:
        AssertionError: If no message is received within the timeout period.
    """
    import time

    start_time = time.monotonic()
    max_attempts = int((timeout_seconds * 1000) / poll_interval_ms)

    for attempt in range(max_attempts):
        # Use getmany for explicit polling with timeout
        # This returns a dict of {TopicPartition: [messages]}
        records = await consumer.getmany(timeout_ms=poll_interval_ms, max_records=10)

        for tp, messages in records.items():
            for msg in messages:
                if msg.topic == topic:
                    return {
                        "key": msg.key.decode("utf-8") if msg.key else None,
                        "value": json.loads(msg.value.decode("utf-8")),
                        "topic": msg.topic,
                    }

        # Check if we've exceeded our timeout
        elapsed = time.monotonic() - start_time
        if elapsed >= timeout_seconds:
            break

    # Calculate actual elapsed time for the error message
    elapsed = time.monotonic() - start_time
    raise AssertionError(
        f"Kafka consumer did not receive message on topic '{topic}' "
        f"within {timeout_seconds}s timeout (elapsed: {elapsed:.2f}s, "
        f"attempts: {max_attempts}). This indicates a real infrastructure "
        f"issue - the message was not delivered to the broker or the consumer "
        f"failed to read it."
    )


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_kafka_consumer_can_verify_published_events(
    e2e_kafka_producer: Any,
    e2e_kafka_consumer: Any,
    e2e_topic_prefix: str,
) -> None:
    """Test end-to-end event verification via consumer.

    This test demonstrates the full flow:
    1. Subscribe consumer to the topic BEFORE publishing
    2. Publish an event via RealKafkaPublisher
    3. Verify the event was actually received from Kafka

    This provides stronger verification than just checking published_events,
    as it confirms the event made it to the Kafka broker AND was readable.

    IMPORTANT: This is a hard assertion test. If the consumer cannot receive
    the published message within the timeout, the test FAILS (not skips).
    A failure here indicates real infrastructure issues that must be addressed.
    """
    # Arrange
    test_id = uuid4().hex[:8]
    topic = f"{e2e_topic_prefix}verification-test-{test_id}"
    key = f"test-key-{test_id}"
    value = {
        "event_type": "verification",
        "test_id": test_id,
        "timestamp": str(uuid4()),
    }

    # Create publisher directly (not via fixture, to control topic naming)
    publisher = RealKafkaPublisher(e2e_kafka_producer, topic_prefix="")

    # Subscribe consumer to topic BEFORE publishing (critical for catching the message)
    e2e_kafka_consumer.subscribe([topic])

    # -------------------------------------------------------------------------
    # KAFKA CONSUMER GROUP PROTOCOL: Why we need this sleep
    # -------------------------------------------------------------------------
    # Kafka's subscribe() initiates partition assignment but does NOT block until
    # partitions are assigned. The consumer group protocol requires multiple
    # broker round-trips:
    #
    # 1. JoinGroup request  -> Consumer announces intent to join group
    # 2. SyncGroup request  -> Group coordinator assigns partitions
    # 3. Heartbeat begins   -> Consumer starts heartbeat loop
    # 4. Fetch begins       -> Consumer can now receive messages
    #
    # This typically takes 200-500ms depending on network latency and broker load.
    # We use 1.0s as a pragmatic buffer for CI environments with variable timing.
    #
    # PRODUCTION ALTERNATIVES (not suitable for tests):
    # - Use assign() for explicit partition assignment (bypasses group protocol)
    # - Use seek() to position at specific offset after assignment callback
    # - Poll in a loop until assignment() returns non-empty (adds complexity)
    #
    # For test reliability, a simple sleep is the clearest and most maintainable
    # approach. The 10s timeout in wait_for_message() provides the safety net.
    # -------------------------------------------------------------------------
    await asyncio.sleep(1.0)

    # Act: Publish event
    await publisher.publish(topic, key, value)

    # Verify: Publisher recorded the event locally
    event_count = len(publisher.published_events)
    assert event_count == 1, (
        f"Publisher should have recorded exactly 1 event, got {event_count}"
    )

    # Assert: Consumer receives the event from Kafka broker
    # This is the critical E2E verification - message roundtrip through Kafka
    received = await wait_for_message(
        consumer=e2e_kafka_consumer,
        topic=topic,
        timeout_seconds=10.0,  # 10 second timeout - generous for CI environments
        poll_interval_ms=500,  # Poll every 500ms
    )

    # Verify message content matches what was published
    assert received["topic"] == topic, (
        f"Expected topic '{topic}', got '{received['topic']}'"
    )
    assert received["key"] == key, f"Expected key '{key}', got '{received['key']}'"
    assert received["value"] == value, (
        f"Expected value {value}, got {received['value']}"
    )


# =============================================================================
# Integration with Effect Node Handlers
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_publisher_implements_protocol(
    e2e_kafka_publisher: RealKafkaPublisher,
) -> None:
    """Test that RealKafkaPublisher implements ProtocolKafkaPublisher.

    Verifies that the adapter is compatible with ONEX effect node handlers.
    """
    # Verify the protocol exists (imported for documentation, not runtime check)
    from omniintelligence.nodes.node_pattern_promotion_effect.handlers import (  # noqa: F401
        ProtocolKafkaPublisher,
    )

    # The protocol check is structural (duck typing)
    # Verify the publisher has the required method signature
    assert hasattr(e2e_kafka_publisher, "publish")
    assert callable(e2e_kafka_publisher.publish)

    # Verify it works as the handlers expect
    await e2e_kafka_publisher.publish(
        topic="test.onex.evt.omniintelligence.pattern-promoted.v1",
        key="test-pattern-id",
        value={
            "event_type": "PatternPromoted",
            "pattern_id": str(uuid4()),
            "from_status": "provisional",
            "to_status": "validated",
        },
    )

    assert len(e2e_kafka_publisher.published_events) == 1


# =============================================================================
# Message Key Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_kafka_message_key_is_required(
    e2e_kafka_publisher: RealKafkaPublisher,
) -> None:
    """Test that published messages have non-empty keys.

    Keys are critical for:
    - Kafka partitioning (messages with same key go to same partition)
    - Ordering guarantees (within a partition)
    - Deduplication (key-based compaction)

    This test verifies that our publishing pattern always includes keys.
    """
    # Arrange
    test_key = "correlation-id-12345"
    test_value = {"event": "test", "data": 123}

    # Act
    await e2e_kafka_publisher.publish("test-topic", test_key, test_value)

    # Assert: Key is recorded
    events = e2e_kafka_publisher.published_events
    assert len(events) == 1

    _topic, key, _value = events[0]
    assert key is not None, "Message key must not be None"
    assert key != "", "Message key must not be empty"
    assert key == test_key, f"Key mismatch: expected '{test_key}', got '{key}'"


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_kafka_message_key_with_uuid_format(
    e2e_kafka_publisher: RealKafkaPublisher,
) -> None:
    """Test that UUID-based keys work correctly for correlation tracking.

    Most ONEX events use UUID correlation IDs as keys. This test verifies
    that the publisher handles UUID-format keys correctly.
    """
    # Arrange
    correlation_id = uuid4()
    test_key = str(correlation_id)
    test_value = {"event_type": "PatternStored", "correlation_id": test_key}

    # Act
    await e2e_kafka_publisher.publish(
        "onex.evt.omniintelligence.pattern-stored.v1",
        test_key,
        test_value,
    )

    # Assert
    events = e2e_kafka_publisher.published_events
    assert len(events) == 1

    _topic, key, _value = events[0]
    assert key == test_key
    assert len(key) == UUID_STRING_LENGTH


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_kafka_publisher_allows_empty_key_but_documents_behavior(
    e2e_kafka_publisher: RealKafkaPublisher,
) -> None:
    """Document that empty string keys become None (round-robin partitioning).

    IMPORTANT: This test documents current behavior, not best practice.

    When key is empty string:
    - RealKafkaPublisher converts it to None for the actual Kafka message
    - Kafka uses round-robin partition assignment
    - No ordering guarantees exist for messages with None keys
    - Key-based compaction does not work

    Production code SHOULD always provide meaningful keys for:
    - Correlation ID tracking
    - Ordering guarantees
    - Proper partitioning

    See: RealKafkaPublisher.publish() in conftest.py:
        key_bytes = key.encode("utf-8") if key else None
    """
    # Arrange - empty string key
    empty_key = ""
    test_value = {"event": "test_empty_key"}

    # Act - this succeeds but key becomes None in actual Kafka message
    await e2e_kafka_publisher.publish("test-topic", empty_key, test_value)

    # Assert: Key is recorded as empty string (not None) in tracking
    # Note: The underlying Kafka message has key=None due to the `if key` check
    events = e2e_kafka_publisher.published_events
    assert len(events) == 1

    _topic, recorded_key, _value = events[0]
    # The recorded_key is what was passed to publish(), not what went to Kafka
    assert recorded_key == ""

    # Document: In production, always use non-empty keys for:
    # 1. Consistent partition assignment (same key = same partition)
    # 2. Message ordering (guaranteed within partition)
    # 3. Log compaction (retains latest value per key)


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_kafka_multiple_events_preserve_individual_keys(
    e2e_kafka_publisher: RealKafkaPublisher,
) -> None:
    """Test that each message retains its own key when publishing multiple events.

    This verifies that keys are not shared or corrupted when publishing
    multiple events in sequence.
    """
    # Arrange
    events_to_publish = [
        ("topic-a", f"key-{uuid4().hex[:8]}", {"seq": 1}),
        ("topic-a", f"key-{uuid4().hex[:8]}", {"seq": 2}),
        ("topic-b", f"key-{uuid4().hex[:8]}", {"seq": 3}),
    ]

    # Act
    for topic, key, value in events_to_publish:
        await e2e_kafka_publisher.publish(topic, key, value)

    # Assert: Each event has its unique key
    recorded = e2e_kafka_publisher.published_events
    assert len(recorded) == 3

    for i, (expected_topic, expected_key, expected_value) in enumerate(
        events_to_publish
    ):
        _, recorded_key, recorded_value = recorded[i]
        assert recorded_key == expected_key, f"Key mismatch at index {i}"
        assert recorded_value == expected_value


@pytest.mark.asyncio
@pytest.mark.integration
@requires_e2e_kafka
async def test_kafka_key_is_used_for_partitioning_documentation(
    e2e_kafka_publisher: RealKafkaPublisher,
) -> None:
    """Document how keys affect Kafka partitioning behavior.

    This test serves as documentation for key-based partitioning:

    1. Messages with the SAME key go to the SAME partition
       - Guarantees ordering for that key
       - Enables pattern-based consumers

    2. Messages with DIFFERENT keys may go to different partitions
       - Enables parallel processing
       - No ordering between keys

    3. Messages with NULL keys use round-robin
       - No ordering guarantees
       - Maximum parallelism but no correlation

    For ONEX events, we use correlation_id as key to ensure:
    - All events for a workflow go to same partition
    - Workflow events are processed in order
    """
    # Arrange - same correlation_id for related events
    correlation_id = str(uuid4())

    events = [
        {"event_type": "WorkflowStarted", "step": 1},
        {"event_type": "PatternMatched", "step": 2},
        {"event_type": "WorkflowCompleted", "step": 3},
    ]

    # Act - publish all with same key
    for event in events:
        await e2e_kafka_publisher.publish(
            "onex.evt.omniintelligence.workflow.v1",
            correlation_id,  # Same key ensures same partition
            event,
        )

    # Assert: All events have the same key
    recorded = e2e_kafka_publisher.published_events
    assert len(recorded) == 3

    keys = [r[1] for r in recorded]
    assert all(k == correlation_id for k in keys), "All events should have same key"

    # This guarantees in Kafka:
    # - All 3 messages go to the same partition
    # - Consumer receives them in order: step 1, 2, 3
