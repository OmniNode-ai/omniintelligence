#!/usr/bin/env python3
"""
Kafka Integration Tests - Phase 3

Tests complete end-to-end flow with real Kafka/Redpanda:
1. Publish validation request to Kafka
2. Intelligence handler processes request
3. Response published back to Kafka
4. Validate response structure and content

Requires: Redpanda/Kafka available (configured via KAFKA_BOOTSTRAP_SERVERS or centralized config)

Part of MVP Day 3 - Full Integration Testing

Author: Archon Intelligence Team
Date: 2025-10-14
"""

import asyncio
import json

# Kafka Configuration
# Uses centralized config: 192.168.86.200:29092 for host machine
# Use omninode-bridge-redpanda:9092 when running from Docker container
import os
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

# Import centralized Kafka configuration
from config.kafka_helper import KAFKA_HOST_SERVERS

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", KAFKA_HOST_SERVERS)
REQUEST_TOPIC = "test.archon.codegen.request.validate.v1"
RESPONSE_TOPIC = "test.archon.codegen.response.validate.v1"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def kafka_connection_check():
    """Check Kafka connectivity before running tests."""
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            request_timeout_ms=5000,
            connections_max_idle_ms=9000,
            api_version="2.5.0",  # Redpanda-compatible API version
        )
        await producer.start()
        await producer.stop()
        return True
    except Exception as e:
        pytest.skip(f"Kafka not available: {e}")


@pytest.fixture
async def kafka_producer(kafka_connection_check):
    """Create Kafka producer for publishing test events."""
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        request_timeout_ms=10000,
        api_version="2.5.0",  # Redpanda-compatible API version
    )
    await producer.start()
    yield producer
    await producer.stop()


@pytest.fixture
async def kafka_consumer(kafka_connection_check):
    """Create Kafka consumer for reading response events."""
    consumer = AIOKafkaConsumer(
        RESPONSE_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=f"test-consumer-{uuid4().hex[:8]}",
        auto_offset_reset="latest",
        enable_auto_commit=False,
        consumer_timeout_ms=1000,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        api_version="2.5.0",  # Redpanda-compatible API version
    )
    await consumer.start()

    # Ensure we're at the latest offset
    await consumer.seek_to_end()

    yield consumer
    await consumer.stop()


def create_validation_request(
    code_content: str, node_type: str = "effect", file_path: str = "test.py"
) -> Dict[str, Any]:
    """
    Create a validation request event.

    Args:
        code_content: Code to validate
        node_type: ONEX node type
        file_path: File path

    Returns:
        Event dictionary
    """
    correlation_id = str(uuid4())

    return {
        "event_id": str(uuid4()),
        "event_type": "CUSTOM",
        "topic": REQUEST_TOPIC,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "source_service": "test-client",
        "source_version": "1.0.0",
        "payload_type": "CodegenValidationRequest",
        "payload": {
            "code_content": code_content,
            "node_type": node_type,
            "file_path": file_path,
        },
        "priority": "NORMAL",
        "schema_version": "1.0.0",
    }


# ============================================================================
# Basic Connectivity Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.requires_kafka
class TestKafkaConnectivity:
    """Test basic Kafka connectivity and operations."""

    async def test_kafka_producer_connection(self, kafka_producer):
        """Test that producer can connect to Kafka."""
        # Producer is already connected via fixture
        assert kafka_producer is not None

    async def test_kafka_consumer_connection(self, kafka_consumer):
        """Test that consumer can connect to Kafka."""
        # Consumer is already connected via fixture
        assert kafka_consumer is not None

    async def test_kafka_publish_consume_roundtrip(
        self, kafka_producer, kafka_consumer
    ):
        """Test basic publish-consume roundtrip."""
        # Publish test message
        test_message = {
            "test": "roundtrip",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "id": str(uuid4()),
        }

        await kafka_producer.send_and_wait(RESPONSE_TOPIC, test_message)

        # Consume message
        message_found = False
        async for msg in kafka_consumer:
            if msg.value.get("id") == test_message["id"]:
                assert msg.value["test"] == "roundtrip"
                message_found = True
                break

        assert message_found, "Published message not found in consumer"


# ============================================================================
# Handler Integration Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.requires_kafka
class TestCodegenKafkaIntegration:
    """Test complete codegen flow with real Kafka."""

    async def test_validation_request_response_flow(
        self, kafka_producer, kafka_consumer
    ):
        """
        Test end-to-end validation flow:
        1. Publish validation request
        2. Wait for handler to process
        3. Receive response
        4. Validate response structure
        """
        # Create validation request
        good_code = """
from omnibase.protocols import ProtocolToolBase
from omnibase.logging import emit_log_event

class NodeUserService(NodeBase):
    def __init__(self, registry: BaseOnexRegistry):
        super().__init__(registry)
        self.container = registry.get_container()

    @standard_error_handling
    async def execute(self):
        emit_log_event("Executing user service")
        return {"status": "success"}
        """

        request = create_validation_request(
            code_content=good_code,
            node_type="effect",
            file_path="src/nodes/node_user_service.py",
        )

        correlation_id = request["correlation_id"]

        # Publish request
        await kafka_producer.send_and_wait(REQUEST_TOPIC, request)

        # Wait for response (timeout 10s)
        response_received = False
        try:
            async for msg in asyncio.wait_for(kafka_consumer.__aiter__(), timeout=10.0):
                response = msg.value

                # Check if this is our response
                if response.get("correlation_id") == correlation_id:
                    # Validate response structure
                    assert "payload" in response
                    payload = response["payload"]

                    assert "is_valid" in payload
                    assert "quality_score" in payload
                    assert "onex_compliance_score" in payload
                    assert "violations" in payload
                    assert "warnings" in payload
                    assert "suggestions" in payload

                    # Validate good code should pass
                    assert payload["is_valid"] is True
                    assert payload["quality_score"] >= 0.7

                    response_received = True
                    break

        except asyncio.TimeoutError:
            pytest.fail(
                f"No response received for correlation_id {correlation_id} "
                "within 10s timeout. Handler may not be running or not "
                "subscribed to request topic."
            )

        assert response_received, "Response matching correlation_id not found"

    async def test_validation_with_bad_code(self, kafka_producer, kafka_consumer):
        """Test validation flow with low-quality code."""
        bad_code = """
from typing import Any

class myservice:  # Non-CamelCase
    def process(self, data: Any):  # Any type forbidden
        import os  # Direct import
        return data
        """

        request = create_validation_request(
            code_content=bad_code,
            node_type="effect",
            file_path="src/nodes/bad_service.py",
        )

        correlation_id = request["correlation_id"]

        # Publish request
        await kafka_producer.send_and_wait(REQUEST_TOPIC, request)

        # Wait for response
        response_received = False
        try:
            async for msg in asyncio.wait_for(kafka_consumer.__aiter__(), timeout=10.0):
                response = msg.value

                if response.get("correlation_id") == correlation_id:
                    payload = response["payload"]

                    # Bad code should fail validation
                    assert payload["is_valid"] is False
                    assert payload["quality_score"] < 0.7
                    assert len(payload["violations"]) > 0

                    response_received = True
                    break

        except asyncio.TimeoutError:
            pytest.fail(f"No response received for correlation_id {correlation_id}")

        assert response_received

    async def test_concurrent_validation_requests(self, kafka_producer, kafka_consumer):
        """Test handling multiple concurrent validation requests."""
        # Create multiple requests
        requests = []
        for i in range(5):
            request = create_validation_request(
                code_content=f"class Service{i}(NodeBase): pass",
                node_type="effect",
                file_path=f"src/nodes/service_{i}.py",
            )
            requests.append(request)

        # Publish all requests
        for request in requests:
            await kafka_producer.send_and_wait(REQUEST_TOPIC, request)

        # Collect responses
        correlation_ids = {req["correlation_id"] for req in requests}
        responses_received = set()

        try:
            async for msg in asyncio.wait_for(kafka_consumer.__aiter__(), timeout=15.0):
                response = msg.value
                correlation_id = response.get("correlation_id")

                if correlation_id in correlation_ids:
                    responses_received.add(correlation_id)

                    # Verify response structure
                    assert "payload" in response
                    assert "is_valid" in response["payload"]

                    # Stop if all responses received
                    if len(responses_received) == len(requests):
                        break

        except asyncio.TimeoutError:
            missing = correlation_ids - responses_received
            pytest.fail(
                f"Only received {len(responses_received)}/{len(requests)} "
                f"responses. Missing: {missing}"
            )

        assert len(responses_received) == len(requests)


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.requires_kafka
@pytest.mark.slow
class TestKafkaPerformance:
    """Performance tests for Kafka integration."""

    async def test_end_to_end_latency(self, kafka_producer, kafka_consumer):
        """
        Test end-to-end latency:
        - Request publish
        - Handler processing
        - Response receive

        Target: <500ms total E2E latency
        """
        import time

        request = create_validation_request(
            code_content="class SimpleService(NodeBase): pass", node_type="effect"
        )

        correlation_id = request["correlation_id"]

        # Measure E2E latency
        start = time.perf_counter()

        # Publish request
        await kafka_producer.send_and_wait(REQUEST_TOPIC, request)

        # Wait for response
        response_received = False
        try:
            async for msg in asyncio.wait_for(kafka_consumer.__aiter__(), timeout=5.0):
                if msg.value.get("correlation_id") == correlation_id:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    response_received = True
                    break

        except asyncio.TimeoutError:
            pytest.fail("Response timeout")

        assert response_received

        # Performance assertion
        assert elapsed_ms < 500, f"E2E latency {elapsed_ms:.2f}ms exceeds 500ms target"

        print(f"\n✓ E2E Latency: {elapsed_ms:.2f}ms")


# ============================================================================
# Main Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "requires_kafka", "--tb=short"])
