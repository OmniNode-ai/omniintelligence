"""
REAL Integration Test for Intelligence Adapter Event Flow.

This is a TRUE integration test that:
- Uses REAL Redpanda/Kafka (no mocks!)
- Publishes CODE_ANALYSIS_REQUESTED events to actual event bus
- Listens for CODE_ANALYSIS_COMPLETED/FAILED events from Intelligence Adapter
- Verifies end-to-end event flow with correlation ID tracking

Requirements:
    - Redpanda running on 192.168.86.200:29092 (or configured via KAFKA_BOOTSTRAP_SERVERS)
    - Intelligence service running on localhost:8053
    - Intelligence Adapter Effect Node subscribed to topics

Usage:
    # Run with pytest
    pytest python/tests/intelligence/integration/test_intelligence_event_flow_real.py -v -s

    # Run with markers
    pytest -m "integration and kafka" python/tests/intelligence/integration/test_intelligence_event_flow_real.py -v -s

Created: 2025-10-21
Pattern: Real Integration Testing (no mocks!)
"""

import asyncio
import json
import logging
import os

# Import event models from contract
# Note: Import path is relative to services/intelligence directory
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

# Import centralized Kafka configuration
from config.kafka_helper import KAFKA_HOST_SERVERS

# Add services/intelligence/src to path for imports
services_intelligence_path = (
    Path(__file__).parent.parent.parent.parent.parent
    / "services"
    / "intelligence"
    / "src"
)
sys.path.insert(0, str(services_intelligence_path))

from events.models.intelligence_adapter_events import (
    EnumAnalysisErrorCode,
    EnumAnalysisOperationType,
    EnumCodeAnalysisEventType,
    IntelligenceAdapterEventHelpers,
    ModelCodeAnalysisCompletedPayload,
    ModelCodeAnalysisFailedPayload,
    ModelCodeAnalysisRequestPayload,
    create_completed_event,
    create_failed_event,
    create_request_event,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka/Redpanda configuration - use centralized config (NO hardcoded values!)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", KAFKA_HOST_SERVERS)
REQUEST_TOPIC = "dev.archon-intelligence.intelligence.code-analysis-requested.v1"
COMPLETED_TOPIC = "dev.archon-intelligence.intelligence.code-analysis-completed.v1"
FAILED_TOPIC = "dev.archon-intelligence.intelligence.code-analysis-failed.v1"

# Test configuration
TEST_TIMEOUT_SECONDS = 30
CONSUMER_GROUP_PREFIX = "test-intelligence-flow"


@pytest.mark.integration
@pytest.mark.kafka
@pytest.mark.asyncio
class TestRealIntelligenceEventFlow:
    """
    REAL integration tests for Intelligence Adapter event flow.

    These tests use the actual Redpanda event bus (NO MOCKS!).
    """

    async def _create_kafka_producer(self) -> AIOKafkaProducer:
        """Create and start real Kafka producer."""
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            # Explicitly set API version for Redpanda compatibility
            api_version="2.5.0",
        )
        await producer.start()
        logger.info(f"✅ Kafka producer started: {KAFKA_BOOTSTRAP_SERVERS}")
        return producer

    async def _create_kafka_consumer(
        self, topics: list[str], group_id: str
    ) -> AIOKafkaConsumer:
        """Create and start real Kafka consumer."""
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=group_id,
            auto_offset_reset="earliest",  # Read from beginning for new consumer groups
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=True,
            # Explicitly set API version for Redpanda compatibility
            api_version="2.5.0",
        )
        await consumer.start()
        logger.info(f"✅ Kafka consumer started: topics={topics}, group_id={group_id}")
        return consumer

    async def _consume_event_with_correlation_id(
        self,
        consumer: AIOKafkaConsumer,
        correlation_id: str,
        timeout_seconds: int = TEST_TIMEOUT_SECONDS,
    ) -> Optional[dict]:
        """
        Consume events from Kafka until one matching correlation_id is found.

        Args:
            consumer: Kafka consumer instance
            correlation_id: Expected correlation ID
            timeout_seconds: Maximum time to wait for matching event

        Returns:
            Event dict if found, None if timeout
        """
        logger.info(
            f"🔍 Waiting for event with correlation_id={correlation_id} (timeout={timeout_seconds}s)"
        )

        async def consume_messages():
            """Inner function to consume messages without timeout check."""
            async for message in consumer:
                event = message.value
                event_correlation_id = event.get("correlation_id")

                logger.info(
                    f"📨 Received event: type={event.get('event_type')}, "
                    f"correlation_id={event_correlation_id}"
                )

                # Check if correlation ID matches
                if event_correlation_id == correlation_id:
                    logger.info(f"✅ Found matching event!")
                    return event

            return None

        try:
            # Use asyncio.wait_for to enforce timeout
            return await asyncio.wait_for(consume_messages(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.error(
                f"❌ Timeout after {timeout_seconds}s - no matching event found"
            )
            return None

    async def test_end_to_end_success_flow_real(self):
        """
        REAL E2E test: Publish REQUEST → Receive COMPLETED.

        This test:
        1. Publishes CODE_ANALYSIS_REQUESTED to real Redpanda
        2. Intelligence Adapter consumes it and processes
        3. Listens for CODE_ANALYSIS_COMPLETED event
        4. Verifies correlation ID tracking

        NO MOCKS - uses real Kafka/Redpanda!
        """
        correlation_id = str(uuid4())
        logger.info(f"\n{'='*70}")
        logger.info(f"🧪 TEST: End-to-End Success Flow (REAL Kafka)")
        logger.info(f"Correlation ID: {correlation_id}")
        logger.info(f"{'='*70}\n")

        producer = None
        consumer = None

        try:
            # ===================================================================
            # Step 1: Create Kafka producer and consumer
            # ===================================================================
            producer = await self._create_kafka_producer()
            consumer = await self._create_kafka_consumer(
                topics=[COMPLETED_TOPIC, FAILED_TOPIC],
                group_id=f"{CONSUMER_GROUP_PREFIX}-{correlation_id}",
            )

            # Give consumer time to subscribe
            await asyncio.sleep(1)

            # ===================================================================
            # Step 2: Publish CODE_ANALYSIS_REQUESTED event to real Kafka
            # ===================================================================
            request_event = create_request_event(
                source_path="tests/integration/sample_code.py",
                content="def calculate_total(items):\n    return sum(items)",
                language="python",
                operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
                correlation_id=uuid4(),  # Use UUID object
                options={
                    "test": True,
                    "integration_test": True,
                },
            )

            # Override correlation_id with string for tracking
            request_event["correlation_id"] = correlation_id

            logger.info(f"📤 Publishing CODE_ANALYSIS_REQUESTED event...")
            logger.info(f"   Topic: {REQUEST_TOPIC}")
            logger.info(f"   Correlation ID: {correlation_id}")

            await producer.send_and_wait(REQUEST_TOPIC, value=request_event)
            logger.info(f"✅ Event published successfully")

            # ===================================================================
            # Step 3: Consume CODE_ANALYSIS_COMPLETED or FAILED event
            # ===================================================================
            logger.info(f"\n📥 Listening for response event...")

            response_event = await self._consume_event_with_correlation_id(
                consumer=consumer,
                correlation_id=correlation_id,
                timeout_seconds=TEST_TIMEOUT_SECONDS,
            )

            # ===================================================================
            # Step 4: Verify response
            # ===================================================================
            assert response_event is not None, (
                f"❌ No response event received within {TEST_TIMEOUT_SECONDS}s. "
                f"Is Intelligence Adapter running and subscribed to {REQUEST_TOPIC}?"
            )

            event_type = response_event.get("event_type")
            logger.info(f"\n✅ Response received: {event_type}")

            # Verify it's a success event (ONEX-compliant qualified event type)
            assert (
                event_type == "omninode.intelligence.event.code_analysis_completed.v1"
            ), f"Expected omninode.intelligence.event.code_analysis_completed.v1 event, got: {event_type}"

            # Verify payload structure
            payload = response_event.get("payload", {})
            assert "quality_score" in payload, "Missing quality_score in payload"
            assert "onex_compliance" in payload, "Missing onex_compliance in payload"
            assert "processing_time_ms" in payload, "Missing processing_time_ms"

            # Verify correlation ID preserved
            assert (
                response_event.get("correlation_id") == correlation_id
            ), "Correlation ID mismatch!"

            logger.info(f"\n{'='*70}")
            logger.info(f"🎉 TEST PASSED: End-to-End Success Flow")
            logger.info(f"   Quality Score: {payload.get('quality_score')}")
            logger.info(f"   ONEX Compliance: {payload.get('onex_compliance')}")
            logger.info(f"   Processing Time: {payload.get('processing_time_ms')}ms")
            logger.info(f"   Correlation ID: {correlation_id}")
            logger.info(f"{'='*70}\n")

        finally:
            # Cleanup
            if producer:
                await producer.stop()
                logger.info("🛑 Producer stopped")
            if consumer:
                await consumer.stop()
                logger.info("🛑 Consumer stopped")

    async def test_end_to_end_failure_flow_real(self):
        """
        REAL E2E test: Publish invalid REQUEST → Receive FAILED.

        This test:
        1. Publishes CODE_ANALYSIS_REQUESTED with invalid content
        2. Intelligence Adapter processes and fails
        3. Listens for CODE_ANALYSIS_FAILED event
        4. Verifies error details and correlation ID

        NO MOCKS - uses real Kafka/Redpanda!
        """
        correlation_id = str(uuid4())
        logger.info(f"\n{'='*70}")
        logger.info(f"🧪 TEST: End-to-End Failure Flow (REAL Kafka)")
        logger.info(f"Correlation ID: {correlation_id}")
        logger.info(f"{'='*70}\n")

        producer = None
        consumer = None

        try:
            # Create producer and consumer
            producer = await self._create_kafka_producer()
            consumer = await self._create_kafka_consumer(
                topics=[FAILED_TOPIC],
                group_id=f"{CONSUMER_GROUP_PREFIX}-failure-{correlation_id}",
            )

            await asyncio.sleep(1)

            # Publish request with missing content field (should trigger FAILED event)
            request_event = create_request_event(
                source_path="tests/integration/broken_code.py",
                content="dummy",  # Will be removed to trigger validation error
                language="python",
                operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
                correlation_id=uuid4(),
            )
            # Remove content to trigger missing field validation error
            request_event["payload"]["content"] = None

            request_event["correlation_id"] = correlation_id

            logger.info(f"📤 Publishing CODE_ANALYSIS_REQUESTED (invalid code)...")
            await producer.send_and_wait(REQUEST_TOPIC, value=request_event)
            logger.info(f"✅ Event published")

            # Listen for FAILED event
            logger.info(f"\n📥 Listening for CODE_ANALYSIS_FAILED event...")

            response_event = await self._consume_event_with_correlation_id(
                consumer=consumer,
                correlation_id=correlation_id,
                timeout_seconds=TEST_TIMEOUT_SECONDS,
            )

            # Verify response
            assert (
                response_event is not None
            ), f"❌ No FAILED event received within {TEST_TIMEOUT_SECONDS}s"

            event_type = response_event.get("event_type")
            # Verify ONEX-compliant qualified event type
            assert (
                event_type == "omninode.intelligence.event.code_analysis_failed.v1"
            ), f"Expected omninode.intelligence.event.code_analysis_failed.v1 event, got: {event_type}"

            # Verify error payload
            payload = response_event.get("payload", {})
            assert "error_message" in payload, "Missing error_message"
            assert "error_code" in payload, "Missing error_code"
            assert "retry_allowed" in payload, "Missing retry_allowed"

            logger.info(f"\n{'='*70}")
            logger.info(f"🎉 TEST PASSED: End-to-End Failure Flow")
            logger.info(f"   Error Code: {payload.get('error_code')}")
            logger.info(f"   Error Message: {payload.get('error_message')}")
            logger.info(f"   Retry Allowed: {payload.get('retry_allowed')}")
            logger.info(f"   Correlation ID: {correlation_id}")
            logger.info(f"{'='*70}\n")

        finally:
            if producer:
                await producer.stop()
            if consumer:
                await consumer.stop()

    async def test_correlation_id_tracking_real(self):
        """
        REAL test: Verify correlation ID is preserved across event flow.

        Publishes request and verifies the same correlation ID appears
        in the response event.
        """
        correlation_id = str(uuid4())
        logger.info(f"\n{'='*70}")
        logger.info(f"🧪 TEST: Correlation ID Tracking (REAL Kafka)")
        logger.info(f"Correlation ID: {correlation_id}")
        logger.info(f"{'='*70}\n")

        producer = None
        consumer = None

        try:
            producer = await self._create_kafka_producer()
            consumer = await self._create_kafka_consumer(
                topics=[COMPLETED_TOPIC, FAILED_TOPIC],
                group_id=f"{CONSUMER_GROUP_PREFIX}-tracking-{correlation_id}",
            )

            await asyncio.sleep(1)

            # Publish simple request
            request_event = create_request_event(
                source_path="test.py",
                content="print('hello')",
                language="python",
                operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
                correlation_id=uuid4(),
            )

            request_event["correlation_id"] = correlation_id

            logger.info(f"📤 Publishing request with correlation_id={correlation_id}")
            await producer.send_and_wait(REQUEST_TOPIC, value=request_event)

            # Consume response
            response_event = await self._consume_event_with_correlation_id(
                consumer=consumer,
                correlation_id=correlation_id,
                timeout_seconds=TEST_TIMEOUT_SECONDS,
            )

            assert response_event is not None, "No response received"

            # Verify correlation ID match
            response_correlation_id = response_event.get("correlation_id")
            assert response_correlation_id == correlation_id, (
                f"Correlation ID mismatch! "
                f"Expected: {correlation_id}, Got: {response_correlation_id}"
            )

            logger.info(f"\n{'='*70}")
            logger.info(f"🎉 TEST PASSED: Correlation ID Tracking")
            logger.info(f"   Request Correlation ID:  {correlation_id}")
            logger.info(f"   Response Correlation ID: {response_correlation_id}")
            logger.info(f"   ✅ Match!")
            logger.info(f"{'='*70}\n")

        finally:
            if producer:
                await producer.stop()
            if consumer:
                await consumer.stop()


if __name__ == "__main__":
    # Run tests directly with asyncio
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    async def run_all_tests():
        """Run all integration tests."""
        test_suite = TestRealIntelligenceEventFlow()

        try:
            logger.info("🚀 Starting REAL Integration Tests\n")

            # Test 1: Success flow
            await test_suite.test_end_to_end_success_flow_real()

            # Test 2: Failure flow
            await test_suite.test_end_to_end_failure_flow_real()

            # Test 3: Correlation tracking
            await test_suite.test_correlation_id_tracking_real()

            logger.info("\n🎉 All integration tests PASSED!")
            sys.exit(0)

        except Exception as e:
            logger.error(f"\n❌ Integration tests FAILED: {e}", exc_info=True)
            sys.exit(1)

    asyncio.run(run_all_tests())
