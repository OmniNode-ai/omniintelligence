#!/usr/bin/env python3
"""
Test Intelligence Request System - Verify fix for manifest_injector

This script tests that:
1. PATTERN_EXTRACTION works without content
2. INFRASTRUCTURE_SCAN works without content
3. MODEL_DISCOVERY works without content
4. SCHEMA_DISCOVERY works without content
5. QUALITY_ASSESSMENT requires content

Usage:
    python3 scripts/test_intelligence_request_system.py
"""

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntelligenceRequestTester:
    """Test intelligence request system end-to-end."""

    KAFKA_BROKERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:9092")
    REQUEST_TOPIC = "dev.archon-intelligence.intelligence.code-analysis-requested.v1"
    COMPLETED_TOPIC = "dev.archon-intelligence.intelligence.code-analysis-completed.v1"
    FAILED_TOPIC = "dev.archon-intelligence.intelligence.code-analysis-failed.v1"

    def __init__(self):
        self.producer = None
        self.consumer = None
        self.test_results = []

    async def start(self):
        """Initialize Kafka producer and consumer."""
        logger.info(f"Connecting to Kafka: {self.KAFKA_BROKERS}")

        # Create producer
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.KAFKA_BROKERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            compression_type="gzip",
        )
        await self.producer.start()
        logger.info("Producer started")

        # Create consumer for response topics
        self.consumer = AIOKafkaConsumer(
            self.COMPLETED_TOPIC,
            self.FAILED_TOPIC,
            bootstrap_servers=self.KAFKA_BROKERS,
            group_id=f"intelligence-test-{uuid4().hex[:8]}",
            auto_offset_reset="latest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await self.consumer.start()
        logger.info("Consumer started")

    async def stop(self):
        """Stop Kafka connections."""
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()
        logger.info("Kafka connections closed")

    async def send_request(
        self,
        operation_type: str,
        source_path: str,
        content: str = None,
        language: str = "python",
        options: dict = None,
    ) -> str:
        """Send CODE_ANALYSIS_REQUESTED event."""
        correlation_id = str(uuid4())

        event = {
            "event_id": str(uuid4()),
            "event_type": "CODE_ANALYSIS_REQUESTED",
            "correlation_id": correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "service": "test-client",
            "payload": {
                "source_path": source_path,
                "content": content,
                "language": language,
                "operation_type": operation_type,
                "options": options or {},
                "project_id": "test",
                "user_id": "test",
            },
        }

        logger.info(
            f"Sending {operation_type} request | correlation_id={correlation_id} | "
            f"source_path={source_path} | content={'present' if content else 'empty'}"
        )

        await self.producer.send_and_wait(self.REQUEST_TOPIC, event)
        return correlation_id

    async def wait_for_response(
        self, correlation_id: str, timeout: float = 10.0
    ) -> dict:
        """Wait for response event with timeout."""
        logger.info(f"Waiting for response | correlation_id={correlation_id}")

        async def consume_with_timeout():
            async for msg in self.consumer:
                response = msg.value
                resp_corr_id = response.get("correlation_id")

                if resp_corr_id == correlation_id:
                    event_type = response.get("event_type", "")
                    is_completed = (
                        "completed" in event_type.lower()
                        or msg.topic == self.COMPLETED_TOPIC
                    )
                    is_failed = (
                        "failed" in event_type.lower() or msg.topic == self.FAILED_TOPIC
                    )

                    logger.info(
                        f"Received response | correlation_id={correlation_id} | "
                        f"event_type={event_type} | topic={msg.topic}"
                    )

                    return {
                        "success": is_completed,
                        "failed": is_failed,
                        "response": response,
                    }

        try:
            result = await asyncio.wait_for(consume_with_timeout(), timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(f"Response timeout | correlation_id={correlation_id}")
            return {
                "success": False,
                "failed": True,
                "response": {"error": "timeout"},
            }

    async def test_pattern_extraction(self):
        """Test PATTERN_EXTRACTION without content (should succeed)."""
        logger.info("\n=== TEST 1: PATTERN_EXTRACTION (no content) ===")

        correlation_id = await self.send_request(
            operation_type="PATTERN_EXTRACTION",
            source_path="node_*_*.py",
            content="",  # Empty string
            options={
                "include_patterns": True,
                "pattern_types": ["CRUD", "Transformation"],
            },
        )

        result = await self.wait_for_response(correlation_id)

        if result["success"]:
            logger.info("✅ PATTERN_EXTRACTION test PASSED (succeeded without content)")
            self.test_results.append(("PATTERN_EXTRACTION", True))
        else:
            logger.error(
                f"❌ PATTERN_EXTRACTION test FAILED (expected success): {result.get('response', {})}"
            )
            self.test_results.append(("PATTERN_EXTRACTION", False))

    async def test_infrastructure_scan(self):
        """Test INFRASTRUCTURE_SCAN without content (should succeed)."""
        logger.info("\n=== TEST 2: INFRASTRUCTURE_SCAN (no content) ===")

        correlation_id = await self.send_request(
            operation_type="INFRASTRUCTURE_SCAN",
            source_path="infrastructure",
            content=None,  # None
            language="yaml",
            options={
                "include_databases": True,
                "include_kafka_topics": True,
            },
        )

        result = await self.wait_for_response(correlation_id)

        if result["success"]:
            logger.info(
                "✅ INFRASTRUCTURE_SCAN test PASSED (succeeded without content)"
            )
            self.test_results.append(("INFRASTRUCTURE_SCAN", True))
        else:
            logger.error(
                f"❌ INFRASTRUCTURE_SCAN test FAILED (expected success): {result.get('response', {})}"
            )
            self.test_results.append(("INFRASTRUCTURE_SCAN", False))

    async def test_model_discovery(self):
        """Test MODEL_DISCOVERY without content (should succeed)."""
        logger.info("\n=== TEST 3: MODEL_DISCOVERY (no content) ===")

        correlation_id = await self.send_request(
            operation_type="MODEL_DISCOVERY",
            source_path="models",
            content="",  # Empty string
            options={
                "include_ai_models": True,
                "include_onex_models": True,
            },
        )

        result = await self.wait_for_response(correlation_id)

        if result["success"]:
            logger.info("✅ MODEL_DISCOVERY test PASSED (succeeded without content)")
            self.test_results.append(("MODEL_DISCOVERY", True))
        else:
            logger.error(
                f"❌ MODEL_DISCOVERY test FAILED (expected success): {result.get('response', {})}"
            )
            self.test_results.append(("MODEL_DISCOVERY", False))

    async def test_schema_discovery(self):
        """Test SCHEMA_DISCOVERY without content (should succeed)."""
        logger.info("\n=== TEST 4: SCHEMA_DISCOVERY (no content) ===")

        correlation_id = await self.send_request(
            operation_type="SCHEMA_DISCOVERY",
            source_path="database_schemas",
            content=None,  # None
            language="sql",
            options={
                "include_tables": True,
                "include_columns": True,
            },
        )

        result = await self.wait_for_response(correlation_id)

        if result["success"]:
            logger.info("✅ SCHEMA_DISCOVERY test PASSED (succeeded without content)")
            self.test_results.append(("SCHEMA_DISCOVERY", True))
        else:
            logger.error(
                f"❌ SCHEMA_DISCOVERY test FAILED (expected success): {result.get('response', {})}"
            )
            self.test_results.append(("SCHEMA_DISCOVERY", False))

    async def test_quality_assessment_without_content(self):
        """Test QUALITY_ASSESSMENT without content (should fail)."""
        logger.info("\n=== TEST 5: QUALITY_ASSESSMENT (no content - should fail) ===")

        correlation_id = await self.send_request(
            operation_type="QUALITY_ASSESSMENT",
            source_path="test.py",
            content="",  # Empty string
            options={},
        )

        result = await self.wait_for_response(correlation_id)

        if result["failed"]:
            logger.info(
                "✅ QUALITY_ASSESSMENT test PASSED (correctly failed without content)"
            )
            self.test_results.append(("QUALITY_ASSESSMENT_NO_CONTENT", True))
        else:
            logger.error(
                f"❌ QUALITY_ASSESSMENT test FAILED (expected failure): {result.get('response', {})}"
            )
            self.test_results.append(("QUALITY_ASSESSMENT_NO_CONTENT", False))

    async def test_quality_assessment_with_content(self):
        """Test QUALITY_ASSESSMENT with content (should succeed)."""
        logger.info(
            "\n=== TEST 6: QUALITY_ASSESSMENT (with content - should succeed) ==="
        )

        correlation_id = await self.send_request(
            operation_type="QUALITY_ASSESSMENT",
            source_path="test.py",
            content="def hello():\n    pass\n",  # Valid content
            options={},
        )

        result = await self.wait_for_response(correlation_id)

        if result["success"]:
            logger.info("✅ QUALITY_ASSESSMENT test PASSED (succeeded with content)")
            self.test_results.append(("QUALITY_ASSESSMENT_WITH_CONTENT", True))
        else:
            logger.error(
                f"❌ QUALITY_ASSESSMENT test FAILED (expected success): {result.get('response', {})}"
            )
            self.test_results.append(("QUALITY_ASSESSMENT_WITH_CONTENT", False))

    async def run_all_tests(self):
        """Run all test cases."""
        logger.info("=" * 70)
        logger.info("INTELLIGENCE REQUEST SYSTEM TEST SUITE")
        logger.info("=" * 70)

        try:
            await self.start()

            # Run all tests
            await self.test_pattern_extraction()
            await self.test_infrastructure_scan()
            await self.test_model_discovery()
            await self.test_schema_discovery()
            await self.test_quality_assessment_without_content()
            await self.test_quality_assessment_with_content()

        finally:
            await self.stop()

        # Print summary
        logger.info("\n" + "=" * 70)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("=" * 70)

        passed = sum(1 for _, result in self.test_results if result)
        total = len(self.test_results)

        for test_name, result in self.test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{status}: {test_name}")

        logger.info(f"\nTotal: {passed}/{total} tests passed")
        logger.info("=" * 70)

        return passed == total


async def main():
    """Main test runner."""
    tester = IntelligenceRequestTester()

    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
