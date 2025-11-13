"""
REAL Integration Test for Document Indexing Event Flow.

This is a TRUE integration test that:
- Uses REAL Redpanda/Kafka (no mocks!)
- Publishes DOCUMENT_INDEX_REQUESTED events to actual event bus
- Listens for DOCUMENT_INDEX_COMPLETED/FAILED events from Document Indexing Handler
- Verifies end-to-end event flow with correlation ID tracking
- Tests full intelligence pipeline (metadata, entities, vectors, KG, quality)

Requirements:
    - Redpanda running on 192.168.86.200:29092 (or configured via KAFKA_BOOTSTRAP_SERVERS)
    - Intelligence service running on localhost:8053
    - Bridge service running on localhost:8057
    - LangExtract service running on localhost:8156
    - Qdrant running on localhost:6333
    - Memgraph running on localhost:7687
    - Document Indexing Handler subscribed to topics

Usage:
    # Run with pytest
    pytest python/tests/intelligence/integration/test_document_indexing_flow.py -v -s

    # Run with markers
    pytest -m "integration and kafka" python/tests/intelligence/integration/test_document_indexing_flow.py -v -s

Created: 2025-10-22
Pattern: Real Integration Testing (no mocks!)
"""

import asyncio
import json
import logging
import os

# Import event models from contract
import sys
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

from events.models.document_indexing_events import (
    DocumentIndexingEventHelpers,
    EnumDocumentIndexEventType,
    EnumIndexingErrorCode,
    ModelDocumentIndexCompletedPayload,
    ModelDocumentIndexFailedPayload,
    ModelDocumentIndexRequestPayload,
    create_completed_event,
    create_failed_event,
    create_request_event,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka/Redpanda configuration - use centralized config (NO hardcoded values!)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", KAFKA_HOST_SERVERS)
REQUEST_TOPIC = "dev.archon-intelligence.intelligence.document-index-requested.v1"
COMPLETED_TOPIC = "dev.archon-intelligence.intelligence.document-index-completed.v1"
FAILED_TOPIC = "dev.archon-intelligence.intelligence.document-index-failed.v1"

# Test configuration
TEST_TIMEOUT_SECONDS = 45  # Longer timeout for full intelligence pipeline
CONSUMER_GROUP_PREFIX = "test-document-indexing-flow"

# Sample Python code for testing
SAMPLE_PYTHON_CODE = '''
"""Sample module for testing document indexing."""

from typing import List, Optional


class DataProcessor:
    """Process data with various transformations."""

    def __init__(self, config: dict):
        """Initialize processor with configuration."""
        self.config = config
        self.cache = {}

    def process_items(self, items: List[str]) -> List[str]:
        """
        Process a list of items.

        Args:
            items: List of items to process

        Returns:
            Processed items
        """
        results = []
        for item in items:
            if item in self.cache:
                results.append(self.cache[item])
            else:
                processed = self._transform_item(item)
                self.cache[item] = processed
                results.append(processed)
        return results

    def _transform_item(self, item: str) -> str:
        """Transform a single item."""
        return item.upper()


def calculate_total(items: List[float]) -> float:
    """
    Calculate total of numeric items.

    Args:
        items: List of numbers

    Returns:
        Sum of all items
    """
    return sum(items)
'''


@pytest.mark.integration
@pytest.mark.kafka
@pytest.mark.asyncio
class TestDocumentIndexingFlow:
    """
    REAL integration tests for Document Indexing Handler event flow.

    These tests use the actual Redpanda event bus (NO MOCKS!).
    """

    async def _create_kafka_producer(self) -> AIOKafkaProducer:
        """Create and start real Kafka producer."""
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
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
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=True,
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
                    logger.info("✅ Found matching event!")
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

    async def test_document_indexing_success_flow(self):
        """
        REAL E2E test: Publish DOCUMENT_INDEX_REQUESTED → Receive COMPLETED.

        This test:
        1. Publishes DOCUMENT_INDEX_REQUESTED to real Redpanda
        2. Document Indexing Handler consumes it and processes through full pipeline
        3. Orchestrates 5 services: metadata, entities, vectors, KG, quality
        4. Listens for DOCUMENT_INDEX_COMPLETED event
        5. Verifies correlation ID tracking and results

        NO MOCKS - uses real Kafka/Redpanda!
        """
        correlation_id = str(uuid4())
        logger.info(f"\n{'='*70}")
        logger.info("🧪 TEST: Document Indexing Success Flow (REAL Kafka)")
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
            # Step 2: Publish DOCUMENT_INDEX_REQUESTED event to real Kafka
            # ===================================================================
            request_event = create_request_event(
                source_path="tests/integration/sample_processor.py",
                content=SAMPLE_PYTHON_CODE,
                language="python",
                project_id="omniarchon-test",
                repository_url="https://github.com/test/omniarchon",
                commit_sha="abc123def456",
                indexing_options={
                    "chunk_size": 1000,
                    "chunk_overlap": 200,
                    "skip_metadata_stamping": False,
                    "skip_vector_indexing": False,
                    "skip_knowledge_graph": False,
                    "skip_quality_assessment": False,
                },
                user_id="test-user",
                correlation_id=uuid4(),  # Use UUID object
            )

            # Override correlation_id with string for tracking
            request_event["correlation_id"] = correlation_id

            logger.info("📤 Publishing DOCUMENT_INDEX_REQUESTED event...")
            logger.info(f"   Topic: {REQUEST_TOPIC}")
            logger.info(f"   Correlation ID: {correlation_id}")
            logger.info(f"   Source Path: tests/integration/sample_processor.py")
            logger.info(f"   Content Length: {len(SAMPLE_PYTHON_CODE)} chars")

            await producer.send_and_wait(REQUEST_TOPIC, value=request_event)
            logger.info("✅ Event published successfully")

            # ===================================================================
            # Step 3: Consume DOCUMENT_INDEX_COMPLETED or FAILED event
            # ===================================================================
            logger.info("\n📥 Listening for response event...")

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
                f"Is Document Indexing Handler running and subscribed to {REQUEST_TOPIC}?"
            )

            event_type = response_event.get("event_type")
            logger.info(f"\n✅ Response received: {event_type}")

            # Verify it's a success event (ONEX-compliant qualified event type)
            assert (
                event_type == "omninode.intelligence.event.document_index_completed.v1"
            ), f"Expected omninode.intelligence.event.document_index_completed.v1 event, got: {event_type}"

            # Verify payload structure
            payload = response_event.get("payload", {})
            assert "document_hash" in payload, "Missing document_hash in payload"
            assert "entity_ids" in payload, "Missing entity_ids in payload"
            assert "vector_ids" in payload, "Missing vector_ids in payload"
            assert "entities_extracted" in payload, "Missing entities_extracted"
            assert "relationships_created" in payload, "Missing relationships_created"
            assert "chunks_indexed" in payload, "Missing chunks_indexed"
            assert "processing_time_ms" in payload, "Missing processing_time_ms"
            assert "service_timings" in payload, "Missing service_timings"

            # Verify correlation ID preserved
            assert (
                response_event.get("correlation_id") == correlation_id
            ), "Correlation ID mismatch!"

            logger.info(f"\n{'='*70}")
            logger.info("🎉 TEST PASSED: Document Indexing Success Flow")
            logger.info(
                f"   Document Hash: {payload.get('document_hash', 'N/A')[:24]}..."
            )
            logger.info(f"   Entities Extracted: {payload.get('entities_extracted')}")
            logger.info(
                f"   Relationships Created: {payload.get('relationships_created')}"
            )
            logger.info(f"   Chunks Indexed: {payload.get('chunks_indexed')}")
            logger.info(f"   Quality Score: {payload.get('quality_score')}")
            logger.info(f"   ONEX Compliance: {payload.get('onex_compliance')}")
            logger.info(f"   Processing Time: {payload.get('processing_time_ms')}ms")
            logger.info(f"   Cache Hit: {payload.get('cache_hit', False)}")
            logger.info(f"   Service Timings: {payload.get('service_timings')}")
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

    async def test_document_indexing_validation_error(self):
        """
        REAL E2E test: Publish invalid REQUEST → Receive FAILED.

        This test:
        1. Publishes DOCUMENT_INDEX_REQUESTED with missing required fields
        2. Document Indexing Handler validates and rejects
        3. Listens for DOCUMENT_INDEX_FAILED event
        4. Verifies error code and message

        NO MOCKS - uses real Kafka/Redpanda!
        """
        correlation_id = str(uuid4())
        logger.info(f"\n{'='*70}")
        logger.info("🧪 TEST: Document Indexing Validation Error (REAL Kafka)")
        logger.info(f"Correlation ID: {correlation_id}")
        logger.info(f"{'='*70}\n")

        producer = None
        consumer = None

        try:
            # Create producer and consumer
            producer = await self._create_kafka_producer()
            consumer = await self._create_kafka_consumer(
                topics=[COMPLETED_TOPIC, FAILED_TOPIC],
                group_id=f"{CONSUMER_GROUP_PREFIX}-{correlation_id}",
            )

            # Give consumer time to subscribe
            await asyncio.sleep(1)

            # ===================================================================
            # Publish INVALID request (missing content)
            # ===================================================================
            request_event = create_request_event(
                source_path="tests/integration/missing_content.py",
                content=None,  # Missing content!
                language="python",
                correlation_id=uuid4(),
            )

            # Override correlation_id
            request_event["correlation_id"] = correlation_id

            logger.info("📤 Publishing INVALID DOCUMENT_INDEX_REQUESTED event...")
            logger.info(f"   Topic: {REQUEST_TOPIC}")
            logger.info(f"   Correlation ID: {correlation_id}")
            logger.info("   Error: Missing content field")

            await producer.send_and_wait(REQUEST_TOPIC, value=request_event)
            logger.info("✅ Event published successfully")

            # ===================================================================
            # Consume DOCUMENT_INDEX_FAILED event
            # ===================================================================
            logger.info("\n📥 Listening for FAILED event...")

            response_event = await self._consume_event_with_correlation_id(
                consumer=consumer,
                correlation_id=correlation_id,
                timeout_seconds=TEST_TIMEOUT_SECONDS,
            )

            # ===================================================================
            # Verify failure response
            # ===================================================================
            assert (
                response_event is not None
            ), f"❌ No response event received within {TEST_TIMEOUT_SECONDS}s"

            event_type = response_event.get("event_type")
            logger.info(f"\n✅ Response received: {event_type}")

            # Verify it's a failure event
            assert (
                event_type == "omninode.intelligence.event.document_index_failed.v1"
            ), f"Expected omninode.intelligence.event.document_index_failed.v1 event, got: {event_type}"

            # Verify payload structure
            payload = response_event.get("payload", {})
            assert "error_message" in payload, "Missing error_message in payload"
            assert "error_code" in payload, "Missing error_code in payload"
            assert "retry_allowed" in payload, "Missing retry_allowed"
            assert "processing_time_ms" in payload, "Missing processing_time_ms"

            # Verify error code
            assert (
                payload.get("error_code") == "INVALID_INPUT"
            ), f"Expected INVALID_INPUT error code, got: {payload.get('error_code')}"

            # Verify correlation ID preserved
            assert (
                response_event.get("correlation_id") == correlation_id
            ), "Correlation ID mismatch!"

            logger.info(f"\n{'='*70}")
            logger.info("🎉 TEST PASSED: Document Indexing Validation Error")
            logger.info(f"   Error Code: {payload.get('error_code')}")
            logger.info(f"   Error Message: {payload.get('error_message')}")
            logger.info(f"   Retry Allowed: {payload.get('retry_allowed')}")
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

    async def test_document_indexing_service_failure(self):
        """
        REAL E2E test: Test graceful degradation when services fail.

        This test:
        1. Publishes DOCUMENT_INDEX_REQUESTED with unsupported language
        2. Document Indexing Handler attempts processing
        3. Some services may fail (entity extraction for unsupported language)
        4. Handler should handle gracefully with partial results
        5. Listens for DOCUMENT_INDEX_COMPLETED or FAILED

        NO MOCKS - uses real Kafka/Redpanda!
        """
        correlation_id = str(uuid4())
        logger.info(f"\n{'='*70}")
        logger.info("🧪 TEST: Document Indexing Service Failure (REAL Kafka)")
        logger.info(f"Correlation ID: {correlation_id}")
        logger.info(f"{'='*70}\n")

        producer = None
        consumer = None

        try:
            # Create producer and consumer
            producer = await self._create_kafka_producer()
            consumer = await self._create_kafka_consumer(
                topics=[COMPLETED_TOPIC, FAILED_TOPIC],
                group_id=f"{CONSUMER_GROUP_PREFIX}-{correlation_id}",
            )

            # Give consumer time to subscribe
            await asyncio.sleep(1)

            # ===================================================================
            # Publish request with unsupported language
            # ===================================================================
            request_event = create_request_event(
                source_path="tests/integration/test.xyz",
                content="some content that may fail parsing",
                language="unsupported-language",  # Likely to cause entity extraction failure
                correlation_id=uuid4(),
            )

            # Override correlation_id
            request_event["correlation_id"] = correlation_id

            logger.info(
                "📤 Publishing DOCUMENT_INDEX_REQUESTED with unsupported language..."
            )
            logger.info(f"   Topic: {REQUEST_TOPIC}")
            logger.info(f"   Correlation ID: {correlation_id}")
            logger.info("   Language: unsupported-language")

            await producer.send_and_wait(REQUEST_TOPIC, value=request_event)
            logger.info("✅ Event published successfully")

            # ===================================================================
            # Consume response event (could be COMPLETED with partial results or FAILED)
            # ===================================================================
            logger.info("\n📥 Listening for response event...")

            response_event = await self._consume_event_with_correlation_id(
                consumer=consumer,
                correlation_id=correlation_id,
                timeout_seconds=TEST_TIMEOUT_SECONDS,
            )

            # ===================================================================
            # Verify response (either partial success or failure)
            # ===================================================================
            assert (
                response_event is not None
            ), f"❌ No response event received within {TEST_TIMEOUT_SECONDS}s"

            event_type = response_event.get("event_type")
            logger.info(f"\n✅ Response received: {event_type}")

            # Verify correlation ID preserved
            assert (
                response_event.get("correlation_id") == correlation_id
            ), "Correlation ID mismatch!"

            payload = response_event.get("payload", {})

            if "document_index_completed" in event_type:
                # Graceful degradation: completed with partial results
                logger.info("✅ Handler completed with graceful degradation")
                logger.info(
                    f"   Document Hash: {payload.get('document_hash', 'N/A')[:24]}..."
                )
                logger.info(
                    f"   Entities Extracted: {payload.get('entities_extracted', 0)}"
                )
                logger.info(f"   Partial Results: {payload.get('service_timings', {})}")
            elif "document_index_failed" in event_type:
                # Service failure: expected behavior
                logger.info("✅ Handler failed as expected")
                logger.info(f"   Error Code: {payload.get('error_code')}")
                logger.info(f"   Error Message: {payload.get('error_message')}")
                logger.info(f"   Failed Service: {payload.get('failed_service')}")
                logger.info(f"   Partial Results: {payload.get('partial_results', {})}")
            else:
                pytest.fail(f"Unexpected event type: {event_type}")

            logger.info(f"\n{'='*70}")
            logger.info("🎉 TEST PASSED: Document Indexing Service Failure Handling")
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


if __name__ == "__main__":
    """Run tests directly with asyncio."""
    import sys

    async def run_tests():
        """Run all tests."""
        test_suite = TestDocumentIndexingFlow()

        logger.info("\n" + "=" * 70)
        logger.info("🚀 Running Document Indexing Integration Tests")
        logger.info("=" * 70 + "\n")

        try:
            # Test 1: Success flow
            await test_suite.test_document_indexing_success_flow()

            # Test 2: Validation error
            await test_suite.test_document_indexing_validation_error()

            # Test 3: Service failure handling
            await test_suite.test_document_indexing_service_failure()

            logger.info("\n" + "=" * 70)
            logger.info("✅ ALL TESTS PASSED!")
            logger.info("=" * 70 + "\n")

        except Exception as e:
            logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
            sys.exit(1)

    # Run tests
    asyncio.run(run_tests())
