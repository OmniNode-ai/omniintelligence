#!/usr/bin/env python3
"""
End-to-End Event Flow Testing Script

Tests event flow validation for all 4 event types:
- Validation (codegen.request.validate)
- Analysis (codegen.request.analyze)
- Pattern (codegen.request.pattern)
- Mixin (codegen.request.mixin)

Usage:
    python scripts/test_e2e_event_flow.py
    python scripts/test_e2e_event_flow.py --bootstrap-servers localhost:19092
    python scripts/test_e2e_event_flow.py --event-type validate
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from kafka import KafkaConsumer, KafkaProducer
    from kafka.admin import KafkaAdminClient
except ImportError:
    print("❌ Error: kafka-python not installed")
    print("Install with: pip install kafka-python")
    sys.exit(1)


@dataclass
class EventFlowResult:
    """Result of a single event flow test"""

    event_type: str
    correlation_id: str
    request_sent: bool
    response_received: bool
    correlation_matched: bool
    latency_ms: float
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Test success if all conditions met"""
        return (
            self.request_sent
            and self.response_received
            and self.correlation_matched
            and self.error is None
        )


class E2EEventFlowTester:
    """End-to-end event flow testing for Kafka integration"""

    # Topic configuration based on KafkaTestConfig from workflow plan
    TOPICS = {
        "validation": {
            "request": "omninode.codegen.request.validate.v1",
            "response": "omninode.codegen.response.validate.v1",
        },
        "analysis": {
            "request": "omninode.codegen.request.analyze.v1",
            "response": "omninode.codegen.response.analyze.v1",
        },
        "pattern": {
            "request": "omninode.codegen.request.pattern.v1",
            "response": "omninode.codegen.response.pattern.v1",
        },
        "mixin": {
            "request": "omninode.codegen.request.mixin.v1",
            "response": "omninode.codegen.response.mixin.v1",
        },
    }

    def __init__(
        self,
        bootstrap_servers: str = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:9092"
        ),
        timeout_seconds: int = 30,
    ):
        """
        Initialize E2E tester

        Args:
            bootstrap_servers: Kafka bootstrap servers (default: 192.168.86.200:9092 for host machine)
            timeout_seconds: Timeout for waiting for responses
        """
        self.bootstrap_servers = bootstrap_servers
        self.timeout_seconds = timeout_seconds
        self.results: List[EventFlowResult] = []

    async def test_validation_flow(self) -> EventFlowResult:
        """Test validation request → response flow"""
        correlation_id = str(uuid.uuid4())
        print("\n🧪 Testing Validation Flow")
        print(f"   Correlation ID: {correlation_id}")

        start_time = time.time()
        request_sent = False
        response_received = False
        correlation_matched = False
        error = None

        try:
            # 1. Publish validation request
            producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )

            request_event = {
                "correlation_id": correlation_id,
                "event_type": "codegen.request.validate",
                "payload": {
                    "code_content": "class TestNode(NodeBase): pass",
                    "node_type": "effect",
                    "language": "python",
                },
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"source": "e2e_test", "test_type": "validation"},
            }

            future = producer.send(
                self.TOPICS["validation"]["request"], value=request_event
            )
            producer.flush()
            future.get(timeout=10)  # Wait for send confirmation
            request_sent = True
            print("   ✅ Published validation request")

            producer.close()

            # 2. Consume validation response
            consumer = KafkaConsumer(
                self.TOPICS["validation"]["response"],
                bootstrap_servers=self.bootstrap_servers,
                group_id=f"e2e-test-{correlation_id}",
                auto_offset_reset="latest",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                consumer_timeout_ms=1000,
            )

            print(
                f"   ⏳ Waiting for validation response (timeout: {self.timeout_seconds}s)..."
            )

            response = await self._consume_with_timeout(
                consumer, correlation_id, self.timeout_seconds
            )

            consumer.close()

            if response:
                response_received = True
                print("   ✅ Received validation response")
                print(f"      Correlation ID: {response.get('correlation_id')}")

                # Verify correlation ID matches
                if response.get("correlation_id") == correlation_id:
                    correlation_matched = True
                    print("   ✅ Correlation ID tracking verified")
                else:
                    error = f"Correlation ID mismatch: expected {correlation_id}, got {response.get('correlation_id')}"
                    print(f"   ❌ {error}")
            else:
                error = "No response received (timeout)"
                print(f"   ❌ {error}")

        except Exception as e:
            error = str(e)
            print(f"   ❌ Error: {error}")

        latency_ms = (time.time() - start_time) * 1000

        result = EventFlowResult(
            event_type="validation",
            correlation_id=correlation_id,
            request_sent=request_sent,
            response_received=response_received,
            correlation_matched=correlation_matched,
            latency_ms=latency_ms,
            error=error,
        )

        self.results.append(result)
        return result

    async def test_analysis_flow(self) -> EventFlowResult:
        """Test analysis request → response flow"""
        correlation_id = str(uuid.uuid4())
        print("\n🧪 Testing Analysis Flow")
        print(f"   Correlation ID: {correlation_id}")

        start_time = time.time()
        request_sent = False
        response_received = False
        correlation_matched = False
        error = None

        try:
            producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )

            request_event = {
                "correlation_id": correlation_id,
                "event_type": "codegen.request.analyze",
                "payload": {
                    "code_content": "def calculate_total(items): return sum(items)",
                    "analysis_type": "quality",
                    "language": "python",
                },
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"source": "e2e_test", "test_type": "analysis"},
            }

            future = producer.send(
                self.TOPICS["analysis"]["request"], value=request_event
            )
            producer.flush()
            future.get(timeout=10)
            request_sent = True
            print("   ✅ Published analysis request")

            producer.close()

            consumer = KafkaConsumer(
                self.TOPICS["analysis"]["response"],
                bootstrap_servers=self.bootstrap_servers,
                group_id=f"e2e-test-{correlation_id}",
                auto_offset_reset="latest",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                consumer_timeout_ms=1000,
            )

            print(
                f"   ⏳ Waiting for analysis response (timeout: {self.timeout_seconds}s)..."
            )

            response = await self._consume_with_timeout(
                consumer, correlation_id, self.timeout_seconds
            )

            consumer.close()

            if response:
                response_received = True
                print("   ✅ Received analysis response")

                if response.get("correlation_id") == correlation_id:
                    correlation_matched = True
                    print("   ✅ Correlation ID tracking verified")
                else:
                    error = "Correlation ID mismatch"
                    print(f"   ❌ {error}")
            else:
                error = "No response received (timeout)"
                print(f"   ❌ {error}")

        except Exception as e:
            error = str(e)
            print(f"   ❌ Error: {error}")

        latency_ms = (time.time() - start_time) * 1000

        result = EventFlowResult(
            event_type="analysis",
            correlation_id=correlation_id,
            request_sent=request_sent,
            response_received=response_received,
            correlation_matched=correlation_matched,
            latency_ms=latency_ms,
            error=error,
        )

        self.results.append(result)
        return result

    async def test_pattern_flow(self) -> EventFlowResult:
        """Test pattern request → response flow"""
        correlation_id = str(uuid.uuid4())
        print("\n🧪 Testing Pattern Flow")
        print(f"   Correlation ID: {correlation_id}")

        start_time = time.time()
        request_sent = False
        response_received = False
        correlation_matched = False
        error = None

        try:
            producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )

            request_event = {
                "correlation_id": correlation_id,
                "event_type": "codegen.request.pattern",
                "payload": {
                    "pattern_type": "node_structure",
                    "context": "ONEX architecture",
                },
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"source": "e2e_test", "test_type": "pattern"},
            }

            future = producer.send(
                self.TOPICS["pattern"]["request"], value=request_event
            )
            producer.flush()
            future.get(timeout=10)
            request_sent = True
            print("   ✅ Published pattern request")

            producer.close()

            consumer = KafkaConsumer(
                self.TOPICS["pattern"]["response"],
                bootstrap_servers=self.bootstrap_servers,
                group_id=f"e2e-test-{correlation_id}",
                auto_offset_reset="latest",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                consumer_timeout_ms=1000,
            )

            print(
                f"   ⏳ Waiting for pattern response (timeout: {self.timeout_seconds}s)..."
            )

            response = await self._consume_with_timeout(
                consumer, correlation_id, self.timeout_seconds
            )

            consumer.close()

            if response:
                response_received = True
                print("   ✅ Received pattern response")

                if response.get("correlation_id") == correlation_id:
                    correlation_matched = True
                    print("   ✅ Correlation ID tracking verified")
                else:
                    error = "Correlation ID mismatch"
                    print(f"   ❌ {error}")
            else:
                error = "No response received (timeout)"
                print(f"   ❌ {error}")

        except Exception as e:
            error = str(e)
            print(f"   ❌ Error: {error}")

        latency_ms = (time.time() - start_time) * 1000

        result = EventFlowResult(
            event_type="pattern",
            correlation_id=correlation_id,
            request_sent=request_sent,
            response_received=response_received,
            correlation_matched=correlation_matched,
            latency_ms=latency_ms,
            error=error,
        )

        self.results.append(result)
        return result

    async def test_mixin_flow(self) -> EventFlowResult:
        """Test mixin request → response flow"""
        correlation_id = str(uuid.uuid4())
        print("\n🧪 Testing Mixin Flow")
        print(f"   Correlation ID: {correlation_id}")

        start_time = time.time()
        request_sent = False
        response_received = False
        correlation_matched = False
        error = None

        try:
            producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )

            request_event = {
                "correlation_id": correlation_id,
                "event_type": "codegen.request.mixin",
                "payload": {"mixin_type": "logging", "target_class": "NodeEffect"},
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"source": "e2e_test", "test_type": "mixin"},
            }

            future = producer.send(self.TOPICS["mixin"]["request"], value=request_event)
            producer.flush()
            future.get(timeout=10)
            request_sent = True
            print("   ✅ Published mixin request")

            producer.close()

            consumer = KafkaConsumer(
                self.TOPICS["mixin"]["response"],
                bootstrap_servers=self.bootstrap_servers,
                group_id=f"e2e-test-{correlation_id}",
                auto_offset_reset="latest",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                consumer_timeout_ms=1000,
            )

            print(
                f"   ⏳ Waiting for mixin response (timeout: {self.timeout_seconds}s)..."
            )

            response = await self._consume_with_timeout(
                consumer, correlation_id, self.timeout_seconds
            )

            consumer.close()

            if response:
                response_received = True
                print("   ✅ Received mixin response")

                if response.get("correlation_id") == correlation_id:
                    correlation_matched = True
                    print("   ✅ Correlation ID tracking verified")
                else:
                    error = "Correlation ID mismatch"
                    print(f"   ❌ {error}")
            else:
                error = "No response received (timeout)"
                print(f"   ❌ {error}")

        except Exception as e:
            error = str(e)
            print(f"   ❌ Error: {error}")

        latency_ms = (time.time() - start_time) * 1000

        result = EventFlowResult(
            event_type="mixin",
            correlation_id=correlation_id,
            request_sent=request_sent,
            response_received=response_received,
            correlation_matched=correlation_matched,
            latency_ms=latency_ms,
            error=error,
        )

        self.results.append(result)
        return result

    async def _consume_with_timeout(
        self, consumer: KafkaConsumer, correlation_id: str, timeout_seconds: int
    ) -> Optional[Dict[str, Any]]:
        """
        Consume message with timeout, filtering by correlation ID

        Args:
            consumer: Kafka consumer instance
            correlation_id: Expected correlation ID
            timeout_seconds: Timeout in seconds

        Returns:
            Message dict if found, None if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                # Poll for messages
                messages = consumer.poll(timeout_ms=1000)

                for topic_partition, records in messages.items():
                    for record in records:
                        # Check if correlation ID matches
                        if record.value.get("correlation_id") == correlation_id:
                            return record.value

            except Exception as e:
                print(f"   ⚠️  Poll error: {e}")

            # Small sleep to avoid tight loop
            await asyncio.sleep(0.1)

        return None

    def verify_kafka_connectivity(self) -> bool:
        """
        Verify Kafka connectivity before running tests

        Returns:
            True if Kafka is accessible, False otherwise
        """
        try:
            print("\n🔍 Verifying Kafka connectivity...")
            print(f"   Bootstrap servers: {self.bootstrap_servers}")

            admin = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers, request_timeout_ms=5000
            )

            topics = admin.list_topics()
            print(f"   ✅ Connected! Found {len(topics)} topics")

            admin.close()
            return True

        except Exception as e:
            print(f"   ❌ Kafka connectivity check failed: {e}")
            return False

    async def run_all_tests(self) -> bool:
        """
        Run all E2E tests

        Returns:
            True if all tests pass, False otherwise
        """
        print("=" * 70)
        print("E2E EVENT FLOW VALIDATION")
        print("=" * 70)

        # Verify connectivity first
        if not self.verify_kafka_connectivity():
            print("\n❌ Cannot proceed - Kafka not available")
            return False

        print("\n🚀 Running E2E tests for all 4 event types...")

        # Run all tests
        await self.test_validation_flow()
        await self.test_analysis_flow()
        await self.test_pattern_flow()
        await self.test_mixin_flow()

        # Generate summary report
        self._print_summary()

        # Return overall success
        return all(result.success for result in self.results)

    def _print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 70)
        print("📊 E2E TEST RESULTS SUMMARY")
        print("=" * 70)

        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests

        for result in self.results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"\n{result.event_type.upper()} Flow: {status}")
            print(f"  Correlation ID: {result.correlation_id}")
            print(f"  Request Sent: {'✅' if result.request_sent else '❌'}")
            print(f"  Response Received: {'✅' if result.response_received else '❌'}")
            print(
                f"  Correlation Matched: {'✅' if result.correlation_matched else '❌'}"
            )
            print(f"  Latency: {result.latency_ms:.2f}ms")
            if result.error:
                print(f"  Error: {result.error}")

        print("\n" + "-" * 70)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests / total_tests * 100):.1f}%")

        if passed_tests == total_tests:
            print("\n🎉 All E2E tests passed!")
        else:
            print(f"\n⚠️  {failed_tests} test(s) failed")

        print("=" * 70)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="End-to-End Event Flow Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:9092"),
        help="Kafka bootstrap servers (default: 192.168.86.200:9092 for host machine)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds for waiting for responses (default: 30)",
    )
    parser.add_argument(
        "--event-type",
        choices=["validation", "analysis", "pattern", "mixin", "all"],
        default="all",
        help="Event type to test (default: all)",
    )

    args = parser.parse_args()

    # Create tester
    tester = E2EEventFlowTester(
        bootstrap_servers=args.bootstrap_servers, timeout_seconds=args.timeout
    )

    # Run tests based on selection
    if args.event_type == "all":
        success = asyncio.run(tester.run_all_tests())
    else:
        # Run single test
        print("=" * 70)
        print(f"E2E EVENT FLOW VALIDATION - {args.event_type.upper()}")
        print("=" * 70)

        if not tester.verify_kafka_connectivity():
            print("\n❌ Cannot proceed - Kafka not available")
            sys.exit(1)

        if args.event_type == "validation":
            result = asyncio.run(tester.test_validation_flow())
        elif args.event_type == "analysis":
            result = asyncio.run(tester.test_analysis_flow())
        elif args.event_type == "pattern":
            result = asyncio.run(tester.test_pattern_flow())
        elif args.event_type == "mixin":
            result = asyncio.run(tester.test_mixin_flow())

        success = result.success
        tester._print_summary()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
