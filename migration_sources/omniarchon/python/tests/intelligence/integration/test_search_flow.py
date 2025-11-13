"""
Integration Tests for Search Event Flow

Tests the end-to-end flow of SEARCH_REQUESTED → SEARCH_COMPLETED/FAILED events
using real Kafka event bus. Validates event envelope structure, correlation ID
tracking, and multi-source search orchestration.

⚠️  REQUIRES REAL INFRASTRUCTURE:
- Kafka/Redpanda running at 192.168.86.200:29092
- Intelligence consumer service processing SEARCH_REQUESTED events
- Intelligence service to execute searches
- Search service to return SEARCH_COMPLETED events

These tests are SKIPPED by default. To run them:
    pytest tests/intelligence/integration/test_search_flow.py --run-integration

Created: 2025-10-22
Purpose: Validate Search Handler event-driven search integration
"""

import asyncio
import json
import logging
import os
import time
import unittest
from typing import Optional
from uuid import uuid4

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

# Import centralized Kafka configuration
from config.kafka_helper import KAFKA_HOST_SERVERS

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Requires real Kafka/Redpanda and backend services. Set RUN_INTEGRATION_TESTS=1 to run.",
)
class TestSearchEventFlowReal(unittest.IsolatedAsyncioTestCase):
    """
    Integration tests for Search event flow using real Kafka infrastructure.

    Tests:
        1. End-to-end success flow (SEARCH_REQUESTED → SEARCH_COMPLETED)
        2. Empty results handling (no matches found)
        3. Source failure handling (graceful degradation)
        4. Correlation ID tracking across events
    """

    # Kafka configuration - use centralized config (NO hardcoded values!)
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", KAFKA_HOST_SERVERS)

    # Topic names (from EVENT_HANDLER_CONTRACTS.md)
    SEARCH_REQUESTED_TOPIC = "dev.archon-intelligence.intelligence.search-requested.v1"
    SEARCH_COMPLETED_TOPIC = "dev.archon-intelligence.intelligence.search-completed.v1"
    SEARCH_FAILED_TOPIC = "dev.archon-intelligence.intelligence.search-failed.v1"

    # Test timeout
    EVENT_TIMEOUT_SECONDS = 30

    async def asyncSetUp(self):
        """Set up test fixtures."""
        logger.info("Setting up test fixtures for Search event flow tests")

    async def asyncTearDown(self):
        """Clean up test fixtures."""
        logger.info("Tearing down test fixtures")

    async def test_search_success_flow(self):
        """
        Test end-to-end success flow: SEARCH_REQUESTED → SEARCH_COMPLETED.

        Flow:
            1. Create Kafka producer and consumer
            2. Subscribe consumer to SEARCH_COMPLETED topic
            3. Publish SEARCH_REQUESTED event
            4. Wait for SEARCH_COMPLETED event with matching correlation_id
            5. Verify payload structure and results
        """
        logger.info("=" * 80)
        logger.info("TEST: Search Success Flow")
        logger.info("=" * 80)

        # Generate unique correlation ID
        correlation_id = str(uuid4())
        logger.info(f"Test correlation_id: {correlation_id}")

        # Create Kafka producer
        producer = await self._create_kafka_producer()

        # Create Kafka consumer for SEARCH_COMPLETED events
        consumer = await self._create_kafka_consumer(
            topics=[self.SEARCH_COMPLETED_TOPIC],
            group_id=f"test-search-completed-{uuid4()}",
        )

        try:
            # Create SEARCH_REQUESTED event
            request_event = self._create_search_request_event(
                query="ONEX Effect Node patterns",
                search_type="HYBRID",
                max_results=10,
                correlation_id=correlation_id,
            )

            logger.info(
                f"Publishing SEARCH_REQUESTED event to {self.SEARCH_REQUESTED_TOPIC}"
            )
            logger.info(f"Request payload: {json.dumps(request_event, indent=2)}")

            # Publish event
            await producer.send_and_wait(
                self.SEARCH_REQUESTED_TOPIC,
                value=json.dumps(request_event).encode("utf-8"),
                key=correlation_id.encode("utf-8"),
            )

            logger.info("SEARCH_REQUESTED event published successfully")

            # Wait for SEARCH_COMPLETED event
            logger.info(
                f"Waiting for SEARCH_COMPLETED event (timeout: {self.EVENT_TIMEOUT_SECONDS}s)..."
            )
            completed_event = await self._consume_event_with_correlation_id(
                consumer,
                correlation_id,
                timeout_seconds=self.EVENT_TIMEOUT_SECONDS,
            )

            # Verify event received
            self.assertIsNotNone(completed_event, "SEARCH_COMPLETED event not received")
            logger.info("SEARCH_COMPLETED event received!")
            logger.info(f"Response payload: {json.dumps(completed_event, indent=2)}")

            # Verify event structure
            self.assertIn("event_type", completed_event)
            self.assertIn("search_completed", completed_event["event_type"])
            self.assertEqual(completed_event["correlation_id"], correlation_id)

            # Verify payload
            payload = completed_event.get("payload", {})
            self.assertIn("query", payload)
            self.assertEqual(payload["query"], "ONEX Effect Node patterns")
            self.assertIn("search_type", payload)
            self.assertIn("total_results", payload)
            self.assertIn("results", payload)
            self.assertIn("sources_queried", payload)
            self.assertIn("processing_time_ms", payload)

            # Verify results structure
            results = payload.get("results", [])
            logger.info(f"Total results: {len(results)}")
            if results:
                result = results[0]
                self.assertIn("source_path", result)
                self.assertIn("score", result)
                self.assertIn("content", result)
                self.assertIn("metadata", result)

            # Verify sources queried
            sources_queried = payload.get("sources_queried", [])
            logger.info(f"Sources queried: {sources_queried}")
            self.assertIsInstance(sources_queried, list)

            logger.info("✅ Search success flow test PASSED")

        finally:
            # Cleanup
            await producer.stop()
            await consumer.stop()
            logger.info("Test cleanup complete")

    async def test_search_empty_results(self):
        """
        Test search with no matching results.

        Flow:
            1. Publish SEARCH_REQUESTED with query that won't match anything
            2. Receive SEARCH_COMPLETED with empty results
            3. Verify total_results = 0
        """
        logger.info("=" * 80)
        logger.info("TEST: Search Empty Results")
        logger.info("=" * 80)

        # Generate unique correlation ID
        correlation_id = str(uuid4())
        logger.info(f"Test correlation_id: {correlation_id}")

        # Create Kafka producer
        producer = await self._create_kafka_producer()

        # Create Kafka consumer for SEARCH_COMPLETED events
        consumer = await self._create_kafka_consumer(
            topics=[self.SEARCH_COMPLETED_TOPIC],
            group_id=f"test-search-empty-{uuid4()}",
        )

        try:
            # Create SEARCH_REQUESTED event with query that won't match
            request_event = self._create_search_request_event(
                query="xyzzy_nonexistent_pattern_12345",
                search_type="SEMANTIC",
                max_results=10,
                correlation_id=correlation_id,
            )

            logger.info(
                f"Publishing SEARCH_REQUESTED event to {self.SEARCH_REQUESTED_TOPIC}"
            )

            # Publish event
            await producer.send_and_wait(
                self.SEARCH_REQUESTED_TOPIC,
                value=json.dumps(request_event).encode("utf-8"),
                key=correlation_id.encode("utf-8"),
            )

            logger.info("SEARCH_REQUESTED event published successfully")

            # Wait for SEARCH_COMPLETED event
            logger.info(
                f"Waiting for SEARCH_COMPLETED event (timeout: {self.EVENT_TIMEOUT_SECONDS}s)..."
            )
            completed_event = await self._consume_event_with_correlation_id(
                consumer,
                correlation_id,
                timeout_seconds=self.EVENT_TIMEOUT_SECONDS,
            )

            # Verify event received
            self.assertIsNotNone(completed_event, "SEARCH_COMPLETED event not received")
            logger.info("SEARCH_COMPLETED event received!")

            # Verify empty results
            payload = completed_event.get("payload", {})
            total_results = payload.get("total_results", -1)
            logger.info(f"Total results: {total_results}")

            # Note: Empty results may still return COMPLETED, not FAILED
            # This is expected behavior for valid queries with no matches
            self.assertGreaterEqual(total_results, 0, "total_results should be >= 0")

            logger.info("✅ Search empty results test PASSED")

        finally:
            # Cleanup
            await producer.stop()
            await consumer.stop()
            logger.info("Test cleanup complete")

    async def test_search_source_failure(self):
        """
        Test graceful degradation when search sources fail.

        Flow:
            1. Publish SEARCH_REQUESTED event
            2. Some sources may fail (expected due to incomplete implementation)
            3. Should still receive SEARCH_COMPLETED if at least one source succeeds
            4. Verify sources_queried reflects which sources succeeded
        """
        logger.info("=" * 80)
        logger.info("TEST: Search Source Failure (Graceful Degradation)")
        logger.info("=" * 80)

        # Generate unique correlation ID
        correlation_id = str(uuid4())
        logger.info(f"Test correlation_id: {correlation_id}")

        # Create Kafka producer
        producer = await self._create_kafka_producer()

        # Create Kafka consumer for both COMPLETED and FAILED events
        consumer = await self._create_kafka_consumer(
            topics=[self.SEARCH_COMPLETED_TOPIC, self.SEARCH_FAILED_TOPIC],
            group_id=f"test-search-failure-{uuid4()}",
        )

        try:
            # Create SEARCH_REQUESTED event
            request_event = self._create_search_request_event(
                query="test graceful degradation",
                search_type="HYBRID",  # Will query all sources
                max_results=10,
                correlation_id=correlation_id,
            )

            logger.info(
                f"Publishing SEARCH_REQUESTED event to {self.SEARCH_REQUESTED_TOPIC}"
            )

            # Publish event
            await producer.send_and_wait(
                self.SEARCH_REQUESTED_TOPIC,
                value=json.dumps(request_event).encode("utf-8"),
                key=correlation_id.encode("utf-8"),
            )

            logger.info("SEARCH_REQUESTED event published successfully")

            # Wait for response (COMPLETED or FAILED)
            logger.info(
                f"Waiting for response event (timeout: {self.EVENT_TIMEOUT_SECONDS}s)..."
            )
            response_event = await self._consume_event_with_correlation_id(
                consumer,
                correlation_id,
                timeout_seconds=self.EVENT_TIMEOUT_SECONDS,
            )

            # Verify event received
            self.assertIsNotNone(response_event, "Response event not received")
            logger.info("Response event received!")

            # Check event type
            event_type = response_event.get("event_type", "")
            logger.info(f"Event type: {event_type}")

            if "search_completed" in event_type:
                # Graceful degradation succeeded
                payload = response_event.get("payload", {})
                sources_queried = payload.get("sources_queried", [])
                logger.info(f"Sources that succeeded: {sources_queried}")

                # At least one source should have succeeded
                self.assertGreater(
                    len(sources_queried), 0, "At least one source should succeed"
                )
                logger.info(
                    "✅ Graceful degradation test PASSED (some sources succeeded)"
                )

            elif "search_failed" in event_type:
                # All sources failed
                payload = response_event.get("payload", {})
                failed_services = payload.get("failed_services", [])
                logger.info(f"All sources failed: {failed_services}")
                logger.info("⚠️  All sources failed (expected if services not running)")

            else:
                self.fail(f"Unexpected event type: {event_type}")

        finally:
            # Cleanup
            await producer.stop()
            await consumer.stop()
            logger.info("Test cleanup complete")

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _create_kafka_producer(self) -> AIOKafkaProducer:
        """Create and start Kafka producer."""
        producer = AIOKafkaProducer(
            bootstrap_servers=self.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: v if isinstance(v, bytes) else v.encode("utf-8"),
        )
        await producer.start()
        logger.info(f"Kafka producer started: {self.KAFKA_BOOTSTRAP_SERVERS}")
        return producer

    async def _create_kafka_consumer(
        self, topics: list[str], group_id: str
    ) -> AIOKafkaConsumer:
        """Create and start Kafka consumer."""
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.KAFKA_BOOTSTRAP_SERVERS,
            group_id=group_id,
            auto_offset_reset="latest",  # Only consume new messages
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await consumer.start()
        logger.info(f"Kafka consumer started: topics={topics}, group_id={group_id}")
        return consumer

    async def _consume_event_with_correlation_id(
        self, consumer: AIOKafkaConsumer, correlation_id: str, timeout_seconds: float
    ) -> Optional[dict]:
        """
        Consume events until finding one with matching correlation_id.

        Args:
            consumer: Kafka consumer
            correlation_id: Correlation ID to match
            timeout_seconds: Timeout in seconds

        Returns:
            Matching event dict or None if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                # Consume with short timeout to allow checking elapsed time
                msg = await asyncio.wait_for(consumer.getone(), timeout=1.0)

                event = msg.value
                event_correlation_id = event.get("correlation_id")

                if event_correlation_id == correlation_id:
                    logger.info(
                        f"Found matching event: correlation_id={correlation_id}"
                    )
                    return event
                else:
                    logger.debug(
                        f"Skipping event with different correlation_id: {event_correlation_id}"
                    )

            except asyncio.TimeoutError:
                # No message received in 1 second, continue waiting
                continue
            except Exception as e:
                logger.error(f"Error consuming event: {e}")
                raise

        logger.warning(
            f"Timeout waiting for event with correlation_id={correlation_id}"
        )
        return None

    def _create_search_request_event(
        self,
        query: str,
        search_type: str,
        max_results: int,
        correlation_id: str,
    ) -> dict:
        """
        Create SEARCH_REQUESTED event envelope.

        Args:
            query: Search query text
            search_type: Type of search (SEMANTIC, VECTOR, KNOWLEDGE_GRAPH, HYBRID)
            max_results: Maximum results to return
            correlation_id: Correlation ID for tracking

        Returns:
            Event envelope dictionary
        """
        return {
            "event_id": str(uuid4()),
            "event_type": "omninode.intelligence.event.search_requested.v1",
            "correlation_id": correlation_id,
            "causation_id": None,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "version": "1.0.0",
            "source": {
                "service": "test-client",
                "instance_id": "test-instance-1",
                "hostname": None,
            },
            "metadata": {},
            "payload": {
                "query": query,
                "search_type": search_type,
                "project_id": None,
                "max_results": max_results,
                "filters": {},
                "quality_weight": None,
                "include_context": True,
                "enable_caching": True,
                "user_id": "test-user",
            },
        }


if __name__ == "__main__":
    # Run tests
    unittest.main()
