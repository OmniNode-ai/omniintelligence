"""
REAL Integration Test for Repository Crawler Event Flow.

This is a TRUE integration test that:
- Uses REAL Redpanda/Kafka (no mocks!)
- Publishes REPOSITORY_SCAN_REQUESTED events to actual event bus
- Listens for REPOSITORY_SCAN_COMPLETED/FAILED events from Repository Crawler
- Verifies end-to-end event flow with correlation ID tracking
- Tests batch publishing of DOCUMENT_INDEX_REQUESTED events

Requirements:
    - Redpanda running on 192.168.86.200:29092 (or configured via KAFKA_BOOTSTRAP_SERVERS)
    - Intelligence service running on localhost:8053
    - Repository Crawler Handler subscribed to topics

Usage:
    # Run with pytest
    pytest python/tests/intelligence/integration/test_repository_crawler_flow.py -v -s

    # Run with markers
    pytest -m "integration and kafka" python/tests/intelligence/integration/test_repository_crawler_flow.py -v -s

Created: 2025-10-22
Pattern: Real Integration Testing (no mocks!)
"""

import asyncio
import json
import logging
import os

# Import event models from contract
import sys
import tempfile
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

from events.models.repository_crawler_events import (
    EnumCrawlerErrorCode,
    EnumRepositoryCrawlerEventType,
    EnumScanScope,
    ModelRepositoryScanCompletedPayload,
    ModelRepositoryScanFailedPayload,
    ModelRepositoryScanRequestPayload,
    RepositoryCrawlerEventHelpers,
    create_completed_event,
    create_failed_event,
    create_request_event,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka/Redpanda configuration - use centralized config (NO hardcoded values!)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", KAFKA_HOST_SERVERS)
REQUEST_TOPIC = "dev.archon-intelligence.intelligence.repository-scan-requested.v1"
COMPLETED_TOPIC = "dev.archon-intelligence.intelligence.repository-scan-completed.v1"
FAILED_TOPIC = "dev.archon-intelligence.intelligence.repository-scan-failed.v1"
DOCUMENT_INDEX_TOPIC = (
    "dev.archon-intelligence.intelligence.document-index-requested.v1"
)

# Test configuration
TEST_TIMEOUT_SECONDS = 30
CONSUMER_GROUP_PREFIX = "test-repository-crawler-flow"


@pytest.mark.integration
@pytest.mark.kafka
@pytest.mark.asyncio
class TestRealRepositoryCrawlerFlow:
    """
    REAL integration tests for Repository Crawler event flow.

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

    def _create_test_repository(self, temp_dir: str) -> str:
        """
        Create a test repository with sample files.

        Args:
            temp_dir: Temporary directory path

        Returns:
            Path to test repository
        """
        repo_path = os.path.join(temp_dir, "test-repo")
        os.makedirs(repo_path, exist_ok=True)

        # Create sample Python files
        with open(os.path.join(repo_path, "main.py"), "w") as f:
            f.write("def main():\n    print('Hello World')\n")

        with open(os.path.join(repo_path, "utils.py"), "w") as f:
            f.write("def calculate(a, b):\n    return a + b\n")

        # Create subdirectory
        src_dir = os.path.join(repo_path, "src")
        os.makedirs(src_dir, exist_ok=True)

        with open(os.path.join(src_dir, "api.py"), "w") as f:
            f.write("class API:\n    def get(self):\n        pass\n")

        # Create files that should be excluded
        pycache_dir = os.path.join(repo_path, "__pycache__")
        os.makedirs(pycache_dir, exist_ok=True)
        with open(os.path.join(pycache_dir, "main.pyc"), "w") as f:
            f.write("compiled")

        logger.info(f"Created test repository at {repo_path}")
        return repo_path

    async def test_repository_crawler_success_flow(self):
        """
        REAL E2E test: Publish REPOSITORY_SCAN_REQUESTED → Receive REPOSITORY_SCAN_COMPLETED.

        This test:
        1. Creates a temporary test repository with sample files
        2. Publishes REPOSITORY_SCAN_REQUESTED to real Redpanda
        3. Repository Crawler consumes it and processes
        4. Listens for REPOSITORY_SCAN_COMPLETED event
        5. Verifies correlation ID tracking and file statistics

        NO MOCKS - uses real Kafka/Redpanda!
        """
        correlation_id = str(uuid4())
        logger.info(f"\n{'='*70}")
        logger.info(f"🧪 TEST: Repository Crawler Success Flow (REAL Kafka)")
        logger.info(f"Correlation ID: {correlation_id}")
        logger.info(f"{'='*70}\n")

        producer = None
        consumer = None
        temp_dir = None

        try:
            # ===================================================================
            # Step 1: Create test repository
            # ===================================================================
            temp_dir = tempfile.mkdtemp()
            repo_path = self._create_test_repository(temp_dir)

            # ===================================================================
            # Step 2: Create Kafka producer and consumer
            # ===================================================================
            producer = await self._create_kafka_producer()
            consumer = await self._create_kafka_consumer(
                topics=[COMPLETED_TOPIC, FAILED_TOPIC, DOCUMENT_INDEX_TOPIC],
                group_id=f"{CONSUMER_GROUP_PREFIX}-{correlation_id}",
            )

            # Give consumer time to subscribe
            await asyncio.sleep(1)

            # ===================================================================
            # Step 3: Publish REPOSITORY_SCAN_REQUESTED event to real Kafka
            # ===================================================================
            request_event = create_request_event(
                repository_path=repo_path,
                project_id="test-project",
                scan_scope=EnumScanScope.FULL,
                file_patterns=["**/*.py"],
                exclude_patterns=["**/__pycache__/**"],
                batch_size=10,
                correlation_id=uuid4(),
            )

            # Override correlation_id with string for tracking
            request_event["correlation_id"] = correlation_id

            logger.info(f"📤 Publishing REPOSITORY_SCAN_REQUESTED event...")
            logger.info(f"   Topic: {REQUEST_TOPIC}")
            logger.info(f"   Repository: {repo_path}")
            logger.info(f"   Correlation ID: {correlation_id}")

            await producer.send_and_wait(REQUEST_TOPIC, value=request_event)
            logger.info(f"✅ Event published successfully")

            # ===================================================================
            # Step 4: Consume REPOSITORY_SCAN_COMPLETED or FAILED event
            # ===================================================================
            logger.info(f"\n📥 Listening for response event...")

            response_event = await self._consume_event_with_correlation_id(
                consumer=consumer,
                correlation_id=correlation_id,
                timeout_seconds=TEST_TIMEOUT_SECONDS,
            )

            # ===================================================================
            # Step 5: Verify response
            # ===================================================================
            assert response_event is not None, (
                f"❌ No response event received within {TEST_TIMEOUT_SECONDS}s. "
                f"Is Repository Crawler running and subscribed to {REQUEST_TOPIC}?"
            )

            event_type = response_event.get("event_type")
            logger.info(f"\n✅ Response received: {event_type}")

            # Verify it's a success event (ONEX-compliant qualified event type)
            assert (
                event_type == "omninode.intelligence.event.repository_scan_completed.v1"
            ), f"Expected omninode.intelligence.event.repository_scan_completed.v1 event, got: {event_type}"

            # Verify payload structure
            payload = response_event.get("payload", {})
            assert "files_discovered" in payload, "Missing files_discovered in payload"
            assert "files_published" in payload, "Missing files_published in payload"
            assert "batches_created" in payload, "Missing batches_created in payload"
            assert "processing_time_ms" in payload, "Missing processing_time_ms"

            # Verify correlation ID preserved
            assert (
                response_event.get("correlation_id") == correlation_id
            ), "Correlation ID mismatch!"

            # Verify file statistics
            files_discovered = payload.get("files_discovered")
            assert (
                files_discovered == 3
            ), f"Expected 3 files discovered, got {files_discovered}"

            logger.info(f"\n{'='*70}")
            logger.info(f"🎉 TEST PASSED: Repository Crawler Success Flow")
            logger.info(f"   Files Discovered: {payload.get('files_discovered')}")
            logger.info(f"   Files Published: {payload.get('files_published')}")
            logger.info(f"   Batches Created: {payload.get('batches_created')}")
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
            if temp_dir:
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"🗑️  Cleaned up temp directory: {temp_dir}")

    async def test_repository_crawler_no_files_found(self):
        """
        REAL E2E test: Publish REQUEST for empty repository → Receive COMPLETED with 0 files.

        This test:
        1. Creates an empty repository
        2. Publishes REPOSITORY_SCAN_REQUESTED
        3. Verifies REPOSITORY_SCAN_COMPLETED with 0 files discovered

        NO MOCKS - uses real Kafka/Redpanda!
        """
        correlation_id = str(uuid4())
        logger.info(f"\n{'='*70}")
        logger.info(f"🧪 TEST: Repository Crawler No Files Found (REAL Kafka)")
        logger.info(f"Correlation ID: {correlation_id}")
        logger.info(f"{'='*70}\n")

        producer = None
        consumer = None
        temp_dir = None

        try:
            # Create empty repository
            temp_dir = tempfile.mkdtemp()
            repo_path = os.path.join(temp_dir, "empty-repo")
            os.makedirs(repo_path, exist_ok=True)

            # Create producer and consumer
            producer = await self._create_kafka_producer()
            consumer = await self._create_kafka_consumer(
                topics=[COMPLETED_TOPIC, FAILED_TOPIC],
                group_id=f"{CONSUMER_GROUP_PREFIX}-{correlation_id}",
            )

            await asyncio.sleep(1)

            # Publish request
            request_event = create_request_event(
                repository_path=repo_path,
                project_id="test-project-empty",
                scan_scope=EnumScanScope.FULL,
                file_patterns=["**/*.py"],
                correlation_id=uuid4(),
            )
            request_event["correlation_id"] = correlation_id

            await producer.send_and_wait(REQUEST_TOPIC, value=request_event)
            logger.info(f"✅ Event published successfully")

            # Consume response
            response_event = await self._consume_event_with_correlation_id(
                consumer=consumer,
                correlation_id=correlation_id,
                timeout_seconds=TEST_TIMEOUT_SECONDS,
            )

            # Verify response
            assert response_event is not None, "No response event received"

            event_type = response_event.get("event_type")
            assert (
                event_type == "omninode.intelligence.event.repository_scan_completed.v1"
            ), f"Expected completed event, got: {event_type}"

            payload = response_event.get("payload", {})
            assert payload.get("files_discovered") == 0, "Expected 0 files discovered"
            assert payload.get("files_published") == 0, "Expected 0 files published"

            logger.info(f"\n🎉 TEST PASSED: No Files Found Scenario")

        finally:
            if producer:
                await producer.stop()
            if consumer:
                await consumer.stop()
            if temp_dir:
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)

    async def test_repository_crawler_batch_publishing(self):
        """
        REAL E2E test: Verify batch publishing of DOCUMENT_INDEX_REQUESTED events.

        This test:
        1. Creates a repository with multiple files
        2. Publishes REPOSITORY_SCAN_REQUESTED with small batch size
        3. Consumes DOCUMENT_INDEX_REQUESTED events
        4. Verifies correct number of document index events published

        NO MOCKS - uses real Kafka/Redpanda!
        """
        correlation_id = str(uuid4())
        logger.info(f"\n{'='*70}")
        logger.info(f"🧪 TEST: Repository Crawler Batch Publishing (REAL Kafka)")
        logger.info(f"Correlation ID: {correlation_id}")
        logger.info(f"{'='*70}\n")

        producer = None
        consumer = None
        temp_dir = None

        try:
            # Create test repository with multiple files
            temp_dir = tempfile.mkdtemp()
            repo_path = os.path.join(temp_dir, "batch-test-repo")
            os.makedirs(repo_path, exist_ok=True)

            # Create 5 Python files
            for i in range(5):
                with open(os.path.join(repo_path, f"file{i}.py"), "w") as f:
                    f.write(f"def func{i}():\n    pass\n")

            # Create producer and consumer
            producer = await self._create_kafka_producer()
            consumer = await self._create_kafka_consumer(
                topics=[COMPLETED_TOPIC, DOCUMENT_INDEX_TOPIC],
                group_id=f"{CONSUMER_GROUP_PREFIX}-{correlation_id}",
            )

            await asyncio.sleep(1)

            # Publish request with small batch size
            request_event = create_request_event(
                repository_path=repo_path,
                project_id="test-project-batch",
                scan_scope=EnumScanScope.FULL,
                file_patterns=["**/*.py"],
                batch_size=2,  # Small batch size to test batching
                correlation_id=uuid4(),
            )
            request_event["correlation_id"] = correlation_id

            await producer.send_and_wait(REQUEST_TOPIC, value=request_event)
            logger.info(f"✅ Event published successfully")

            # Count DOCUMENT_INDEX_REQUESTED events
            doc_index_count = 0

            async def count_events():
                nonlocal doc_index_count
                async for message in consumer:
                    event = message.value
                    event_type = event.get("event_type")

                    if "document_index_requested" in event_type:
                        doc_index_count += 1
                        logger.info(
                            f"📄 Received DOCUMENT_INDEX_REQUESTED #{doc_index_count}"
                        )

                    if "repository_scan_completed" in event_type:
                        logger.info(f"✅ Received REPOSITORY_SCAN_COMPLETED")
                        return

            await asyncio.wait_for(count_events(), timeout=TEST_TIMEOUT_SECONDS)

            # Verify batch publishing worked
            assert (
                doc_index_count == 5
            ), f"Expected 5 document index events, got {doc_index_count}"

            logger.info(f"\n🎉 TEST PASSED: Batch Publishing")
            logger.info(f"   Document Index Events: {doc_index_count}")

        except asyncio.TimeoutError:
            logger.error(
                f"❌ Timeout - received {doc_index_count} document index events"
            )
            raise

        finally:
            if producer:
                await producer.stop()
            if consumer:
                await consumer.stop()
            if temp_dir:
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)
