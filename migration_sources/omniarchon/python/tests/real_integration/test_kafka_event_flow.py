"""
Real Integration Test: Kafka Event Flow

Tests end-to-end event flow through Kafka with real broker.

Coverage:
- Event production to real Kafka broker
- Event consumption from real Kafka topics
- Event envelope structure validation
- Multi-event ordering and correlation
- Consumer group isolation

Run with:
    pytest --real-integration tests/real_integration/test_kafka_event_flow.py -v
"""

import asyncio
import json
from typing import Any, Dict

import pytest

from tests.fixtures.real_integration import (
    kafka_consumer,
    kafka_producer,
    kafka_test_topic,
    real_integration_config,
    test_id,
    wait_for_kafka_message,
)
from tests.utils.test_data_manager import (
    KafkaTestDataGenerator,
    TestDataManager,
    wait_for_kafka_messages,
)


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_kafka_produce_consume_single_event(
    kafka_producer,
    kafka_consumer,
    kafka_test_topic: str,
    test_id: str,
):
    """
    Test producing and consuming a single event through real Kafka.

    Validates:
    - Event successfully produced to broker
    - Event successfully consumed from broker
    - Event data integrity maintained
    - Correlation ID preserved
    """
    # Arrange: Generate test event
    test_event = KafkaTestDataGenerator.generate_routing_decision_event(
        agent_name="test-agent",
        confidence=0.95,
        user_request="Test request for Kafka integration",
    )
    correlation_id = test_event["envelope"]["correlation_id"]

    # Act: Produce event to Kafka
    event_bytes = json.dumps(test_event).encode("utf-8")
    await kafka_producer.send_and_wait(
        topic=kafka_test_topic, value=event_bytes, key=correlation_id.encode("utf-8")
    )

    # Assert: Consume and validate event
    messages = await wait_for_kafka_messages(
        consumer=kafka_consumer, topic=kafka_test_topic, expected_count=1, timeout=10.0
    )

    assert len(messages) == 1
    received_event = messages[0]["value"]

    # Validate event structure
    assert "envelope" in received_event
    assert "payload" in received_event

    # Validate envelope
    assert received_event["envelope"]["correlation_id"] == correlation_id
    assert received_event["envelope"]["event_type"] == "agent.routing.decision"

    # Validate payload
    assert received_event["payload"]["selected_agent"] == "test-agent"
    assert received_event["payload"]["confidence_score"] == 0.95
    assert (
        received_event["payload"]["user_request"]
        == "Test request for Kafka integration"
    )


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_kafka_multiple_events_ordering(
    kafka_producer,
    kafka_consumer,
    kafka_test_topic: str,
    test_id: str,
):
    """
    Test producing and consuming multiple events with ordering validation.

    Validates:
    - Multiple events produced successfully
    - Events consumed in correct order (within partition)
    - Correlation tracking across multiple events
    - No events lost or duplicated
    """
    # Arrange: Generate multiple correlated events
    correlation_id = f"test-correlation-{test_id}"
    event_count = 5
    events = []

    for i in range(event_count):
        event = KafkaTestDataGenerator.generate_event(
            event_type="test.event.sequence",
            payload={
                "sequence_number": i,
                "message": f"Event {i} in sequence",
                "test_id": test_id,
            },
            correlation_id=correlation_id,
        )
        events.append(event)

    # Act: Produce all events
    for event in events:
        event_bytes = json.dumps(event).encode("utf-8")
        await kafka_producer.send_and_wait(
            topic=kafka_test_topic,
            value=event_bytes,
            key=correlation_id.encode("utf-8"),  # Same key = same partition = ordering
        )

    # Assert: Consume and validate all events
    messages = await wait_for_kafka_messages(
        consumer=kafka_consumer,
        topic=kafka_test_topic,
        expected_count=event_count,
        timeout=15.0,
    )

    assert len(messages) == event_count

    # Validate ordering (same key goes to same partition, ordering preserved)
    for i, message in enumerate(messages):
        received_event = message["value"]
        assert received_event["envelope"]["correlation_id"] == correlation_id
        assert received_event["payload"]["sequence_number"] == i
        assert received_event["payload"]["message"] == f"Event {i} in sequence"


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_kafka_event_envelope_structure(
    kafka_producer,
    kafka_consumer,
    kafka_test_topic: str,
):
    """
    Test event envelope structure compliance.

    Validates:
    - All required envelope fields present
    - Field types are correct
    - Timestamps are valid ISO format
    - Event IDs are unique UUIDs
    - Version information included
    """
    # Arrange: Generate event with full envelope
    test_event = KafkaTestDataGenerator.generate_transformation_event(
        from_agent="polymorphic-agent", to_agent="agent-performance", success=True
    )

    # Act: Produce event
    event_bytes = json.dumps(test_event).encode("utf-8")
    correlation_id = test_event["envelope"]["correlation_id"]
    await kafka_producer.send_and_wait(
        topic=kafka_test_topic, value=event_bytes, key=correlation_id.encode("utf-8")
    )

    # Assert: Consume and validate envelope structure
    messages = await wait_for_kafka_messages(
        consumer=kafka_consumer, topic=kafka_test_topic, expected_count=1, timeout=10.0
    )

    received_event = messages[0]["value"]
    envelope = received_event["envelope"]

    # Validate required fields
    assert "event_id" in envelope
    assert "event_type" in envelope
    assert "correlation_id" in envelope
    assert "timestamp" in envelope
    assert "version" in envelope

    # Validate field types
    assert isinstance(envelope["event_id"], str)
    assert isinstance(envelope["event_type"], str)
    assert isinstance(envelope["correlation_id"], str)
    assert isinstance(envelope["timestamp"], str)
    assert isinstance(envelope["version"], str)

    # Validate UUID format for event_id
    import uuid

    try:
        uuid.UUID(envelope["event_id"])
    except ValueError:
        pytest.fail(f"event_id is not a valid UUID: {envelope['event_id']}")

    # Validate ISO timestamp format
    from datetime import datetime

    try:
        datetime.fromisoformat(envelope["timestamp"].replace("Z", "+00:00"))
    except ValueError:
        pytest.fail(f"timestamp is not valid ISO format: {envelope['timestamp']}")


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_kafka_consumer_group_isolation(
    kafka_producer,
    kafka_test_topic: str,
    real_integration_config: Dict[str, Any],
    test_id: str,
):
    """
    Test consumer group isolation with multiple consumers.

    Validates:
    - Each consumer group receives all messages
    - Consumer groups are isolated
    - Multiple consumers can read same topic
    - No message loss between consumer groups
    """
    from aiokafka import AIOKafkaConsumer

    # Arrange: Create two separate consumer groups
    config = real_integration_config["kafka"]

    consumer1 = AIOKafkaConsumer(
        bootstrap_servers=config["bootstrap_servers"],
        group_id=f"test-group-1-{test_id}",
        auto_offset_reset="earliest",
    )
    await consumer1.start()

    consumer2 = AIOKafkaConsumer(
        bootstrap_servers=config["bootstrap_servers"],
        group_id=f"test-group-2-{test_id}",
        auto_offset_reset="earliest",
    )
    await consumer2.start()

    try:
        # Act: Produce test events
        test_events = [
            KafkaTestDataGenerator.generate_event(
                event_type="test.isolation",
                payload={"message": f"Message {i}", "test_id": test_id},
            )
            for i in range(3)
        ]

        for event in test_events:
            event_bytes = json.dumps(event).encode("utf-8")
            await kafka_producer.send_and_wait(
                topic=kafka_test_topic,
                value=event_bytes,
            )

        # Assert: Both consumers receive all messages
        messages1 = await wait_for_kafka_messages(
            consumer=consumer1, topic=kafka_test_topic, expected_count=3, timeout=10.0
        )

        messages2 = await wait_for_kafka_messages(
            consumer=consumer2, topic=kafka_test_topic, expected_count=3, timeout=10.0
        )

        # Both consumer groups should receive all messages
        assert len(messages1) == 3
        assert len(messages2) == 3

        # Validate messages are the same
        for msg1, msg2 in zip(messages1, messages2):
            assert msg1["value"]["payload"] == msg2["value"]["payload"]

    finally:
        # Cleanup
        await consumer1.stop()
        await consumer2.stop()


@pytest.mark.real_integration
@pytest.mark.asyncio
@pytest.mark.slow
async def test_kafka_high_throughput_stress(
    kafka_producer,
    kafka_consumer,
    kafka_test_topic: str,
    test_id: str,
):
    """
    Stress test: High-throughput event production and consumption.

    Validates:
    - System handles high event volume
    - No events lost under load
    - Performance remains acceptable
    - No errors or timeouts under stress

    Note: Marked as 'slow' - takes >10 seconds
    """
    # Arrange: Generate large batch of events
    event_count = 100
    correlation_id = f"stress-test-{test_id}"

    # Act: Produce events in batch
    start_time = asyncio.get_event_loop().time()

    for i in range(event_count):
        event = KafkaTestDataGenerator.generate_event(
            event_type="test.stress",
            payload={"index": i, "test_id": test_id},
            correlation_id=correlation_id,
        )
        event_bytes = json.dumps(event).encode("utf-8")

        # Send without waiting (faster)
        await kafka_producer.send(
            topic=kafka_test_topic,
            value=event_bytes,
            key=correlation_id.encode("utf-8"),
        )

    # Flush to ensure all sent
    await kafka_producer.flush()
    produce_duration = asyncio.get_event_loop().time() - start_time

    # Assert: Consume all events
    consume_start = asyncio.get_event_loop().time()
    messages = await wait_for_kafka_messages(
        consumer=kafka_consumer,
        topic=kafka_test_topic,
        expected_count=event_count,
        timeout=30.0,  # Longer timeout for high volume
    )
    consume_duration = asyncio.get_event_loop().time() - consume_start

    # Validate all events received
    assert len(messages) == event_count

    # Validate performance (should be fast with real Kafka)
    assert (
        produce_duration < 10.0
    ), f"Production took {produce_duration:.2f}s (expected <10s)"
    assert (
        consume_duration < 15.0
    ), f"Consumption took {consume_duration:.2f}s (expected <15s)"

    # Validate all indices present (no duplicates or missing)
    indices = {msg["value"]["payload"]["index"] for msg in messages}
    assert indices == set(range(event_count))
