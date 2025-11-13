"""
Kafka Test Utilities - Connectivity Verification and Test Helpers

This module provides utilities for Kafka integration testing, including
connectivity verification, topic management, and test data helpers.

Responsibilities:
- Kafka connectivity verification with retry logic
- Topic creation and cleanup helpers
- Test event publishing and consuming utilities
- Correlation ID tracking helpers

Author: Archon Intelligence Team
Version: 1.0.0
Created: 2025-10-15 (MVP Phase 4 - Workflow 1)
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import KafkaError

from .kafka_test_config import KafkaTestConfig

logger = logging.getLogger(__name__)


# ============================================================================
# Connectivity Verification
# ============================================================================


def verify_kafka_connectivity() -> bool:
    """
    Verify Kafka broker is accessible.

    Returns:
        True if Kafka is accessible, False otherwise

    Test:
    - Creates admin client
    - Lists topics (basic connectivity check)
    - Closes connection cleanly

    Example:
        if verify_kafka_connectivity():
            # Proceed with tests
            pass
        else:
            pytest.skip("Kafka not available")
    """
    try:
        admin = KafkaAdminClient(
            bootstrap_servers=KafkaTestConfig.BOOTSTRAP_SERVERS, request_timeout_ms=5000
        )
        try:
            # List topics to verify connectivity
            topics = admin.list_topics()
            logger.info(f"Kafka connectivity verified. Found {len(topics)} topics.")
            return True
        finally:
            admin.close()

    except Exception as e:
        logger.error(f"Kafka connectivity check failed: {e}")
        return False


def wait_for_kafka(max_retries: int = 10, delay_seconds: int = 2) -> bool:
    """
    Wait for Kafka to become available with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay_seconds: Initial delay between retries (doubles each attempt)

    Returns:
        True if Kafka becomes available, False if timeout

    Backoff Strategy:
    - Initial delay: delay_seconds
    - Each retry: delay *= 1.5
    - Example (delay=2): 2s, 3s, 4.5s, 6.75s, ...

    Example:
        if wait_for_kafka(max_retries=10, delay_seconds=2):
            # Kafka is ready
            pass
        else:
            pytest.skip("Kafka failed to start")
    """
    current_delay = delay_seconds

    for attempt in range(max_retries):
        if verify_kafka_connectivity():
            logger.info(f"Kafka became available after {attempt + 1} attempts")
            return True

        logger.warning(
            f"Kafka not ready, retry {attempt + 1}/{max_retries} "
            f"(waiting {current_delay:.1f}s)"
        )
        time.sleep(current_delay)
        current_delay *= 1.5  # Exponential backoff

    logger.error(f"Kafka failed to become available after {max_retries} retries")
    return False


# ============================================================================
# Topic Management
# ============================================================================


def create_test_topics(
    topics: Optional[List[str]] = None,
    num_partitions: int = 3,
    replication_factor: int = 1,
) -> bool:
    """
    Create test topics if they don't exist.

    Args:
        topics: List of topic names (defaults to DEFAULT_TOPICS)
        num_partitions: Number of partitions per topic
        replication_factor: Replication factor (1 for single-broker testing)

    Returns:
        True if topics created/exist, False on failure

    Note:
        Gracefully handles topics that already exist.
        Logs warnings but doesn't fail on existing topics.

    Example:
        # Create default topics
        create_test_topics()

        # Create custom topics
        create_test_topics(["test.topic.v1"], num_partitions=1)
    """
    if topics is None:
        topics = list(KafkaTestConfig.DEFAULT_TOPICS.values())

    try:
        admin = KafkaAdminClient(
            bootstrap_servers=KafkaTestConfig.BOOTSTRAP_SERVERS,
            request_timeout_ms=10000,
        )
        try:
            # Create NewTopic objects
            new_topics = [
                NewTopic(
                    name=topic_name,
                    num_partitions=num_partitions,
                    replication_factor=replication_factor,
                )
                for topic_name in topics
            ]

            # Attempt to create topics
            try:
                admin.create_topics(new_topics, validate_only=False)
                logger.info(f"Created {len(topics)} test topics successfully")
            except Exception as e:
                # Topics might already exist - this is okay
                logger.warning(f"Topic creation note: {e}")

            return True
        finally:
            admin.close()

    except Exception as e:
        logger.error(f"Failed to create test topics: {e}")
        return False


def delete_test_topics(topics: Optional[List[str]] = None) -> bool:
    """
    Delete test topics for cleanup.

    Args:
        topics: List of topic names (defaults to DEFAULT_TOPICS)

    Returns:
        True if topics deleted, False on failure

    Warning:
        Use with caution - deletes topics and all their data.
        Only call in teardown/cleanup phases.

    Example:
        # Delete default topics after tests
        delete_test_topics()
    """
    if topics is None:
        topics = list(KafkaTestConfig.DEFAULT_TOPICS.values())

    try:
        admin = KafkaAdminClient(
            bootstrap_servers=KafkaTestConfig.BOOTSTRAP_SERVERS,
            request_timeout_ms=10000,
        )
        try:
            admin.delete_topics(topics)
            logger.info(f"Deleted {len(topics)} test topics successfully")
            return True
        finally:
            admin.close()

    except Exception as e:
        logger.error(f"Failed to delete test topics: {e}")
        return False


# ============================================================================
# Test Event Helpers
# ============================================================================


async def publish_test_event(
    producer: KafkaProducer, topic: str, event: Dict[str, Any], correlation_id: str
) -> None:
    """
    Publish test event to Kafka with correlation ID.

    Args:
        producer: KafkaProducer instance
        topic: Topic name
        event: Event payload (will be serialized)
        correlation_id: Correlation ID for tracking

    Raises:
        KafkaError: If publish fails

    Note:
        Assumes producer has value_serializer configured.
        Flushes producer to ensure delivery.

    Example:
        producer = KafkaProducer(
            **KafkaTestConfig.get_producer_config(),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        await publish_test_event(
            producer,
            "test.topic.v1",
            {"data": "test"},
            "correlation-123"
        )
    """
    try:
        # Add correlation_id to event if not present
        if "correlation_id" not in event:
            event["correlation_id"] = correlation_id

        # Send event
        future = producer.send(topic, value=event)

        # Wait for delivery confirmation (non-blocking)
        record_metadata = await asyncio.to_thread(future.get, timeout=10)

        logger.debug(
            f"Published event to {topic}: "
            f"partition={record_metadata.partition}, "
            f"offset={record_metadata.offset}, "
            f"correlation_id={correlation_id}"
        )

        # Flush to ensure delivery (non-blocking)
        await asyncio.to_thread(producer.flush)

    except KafkaError as e:
        logger.error(f"Failed to publish event: {e}")
        raise


async def consume_response(
    consumer: KafkaConsumer, correlation_id: str, timeout_seconds: int = 10
) -> Optional[Dict[str, Any]]:
    """
    Consume response from Kafka matching correlation ID.

    Args:
        consumer: KafkaConsumer instance
        correlation_id: Expected correlation ID
        timeout_seconds: Maximum wait time

    Returns:
        Event payload if found, None if timeout

    Note:
        Polls consumer until matching correlation_id found or timeout.
        Returns first matching event.

    Example:
        consumer = KafkaConsumer(
            "response.topic.v1",
            **KafkaTestConfig.get_consumer_config("test-group"),
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )

        response = await consume_response(
            consumer,
            "correlation-123",
            timeout_seconds=10
        )

        if response:
            assert response["correlation_id"] == "correlation-123"
    """
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        # Poll for messages (non-blocking)
        messages = await asyncio.to_thread(consumer.poll, timeout_ms=1000)

        for topic_partition, records in messages.items():
            for record in records:
                # Check if correlation_id matches
                if isinstance(record.value, dict):
                    if record.value.get("correlation_id") == correlation_id:
                        logger.debug(
                            f"Found matching response: "
                            f"correlation_id={correlation_id}, "
                            f"offset={record.offset}"
                        )
                        return record.value

        # Small delay to avoid busy-waiting
        await asyncio.sleep(0.1)

    logger.warning(f"Timeout waiting for response with correlation_id={correlation_id}")
    return None


# ============================================================================
# Correlation ID Tracking
# ============================================================================


def track_event_flow(
    correlation_id: str,
    request_topic: str,
    response_topic: str,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """
    Track event flow from request to response using correlation ID.

    Args:
        correlation_id: Correlation ID to track
        request_topic: Request topic name
        response_topic: Response topic name
        timeout_seconds: Maximum wait time

    Returns:
        Dictionary with tracking results:
        - request_found: bool
        - response_found: bool
        - request_event: Dict (if found)
        - response_event: Dict (if found)
        - duration_ms: float (if both found)

    Example:
        tracking = track_event_flow(
            "correlation-123",
            "request.validate.v1",
            "response.validate.v1"
        )

        assert tracking["request_found"]
        assert tracking["response_found"]
        assert tracking["duration_ms"] < 1000
    """
    result = {
        "request_found": False,
        "response_found": False,
        "request_event": None,
        "response_event": None,
        "duration_ms": None,
    }

    try:
        # Create consumer for both topics
        consumer = KafkaConsumer(
            request_topic,
            response_topic,
            **KafkaTestConfig.get_consumer_config(f"tracker-{correlation_id}"),
            auto_offset_reset="earliest",
        )

        try:
            start_time = time.time()
            request_timestamp = None

            # Poll until both events found or timeout
            while time.time() - start_time < timeout_seconds:
                messages = consumer.poll(timeout_ms=1000)

                for topic_partition, records in messages.items():
                    for record in records:
                        if not hasattr(record.value, "get"):
                            continue

                        if record.value.get("correlation_id") != correlation_id:
                            continue

                        # Found matching event
                        if record.topic == request_topic:
                            result["request_found"] = True
                            result["request_event"] = record.value
                            request_timestamp = record.timestamp
                            logger.debug(f"Found request event: {request_topic}")

                        elif record.topic == response_topic:
                            result["response_found"] = True
                            result["response_event"] = record.value
                            logger.debug(f"Found response event: {response_topic}")

                            # Calculate duration if request already found
                            if request_timestamp:
                                result["duration_ms"] = (
                                    record.timestamp - request_timestamp
                                )

                # Both found - done
                if result["request_found"] and result["response_found"]:
                    break

        finally:
            consumer.close()

    except Exception as e:
        logger.error(f"Error tracking event flow: {e}")

    return result
