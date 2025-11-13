#!/usr/bin/env python3
"""
Load Testing Script for Archon Intelligence Kafka Handlers

Supports two modes:
1. Concurrent: Fixed number of concurrent requests
2. Sustained: Fixed rate over time (requests per minute)

Configuration:
    Uses centralized config from config/kafka_helper.py
    Override with KAFKA_BOOTSTRAP_SERVERS environment variable
    Default: 192.168.86.200:29092 (host machine, external port)

Usage:
    python scripts/load_test.py --concurrent 100 --duration 300 --event-type validate
    python scripts/load_test.py --rate 500 --duration 600 --event-type validate
"""

import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import centralized configuration
from config.kafka_helper import KAFKA_HOST_SERVERS

# Try to import kafka-python, provide helpful error if missing
try:
    from kafka import KafkaConsumer, KafkaProducer
    from kafka.errors import KafkaError
except ImportError:
    print("Error: kafka-python not installed. Install with: pip install kafka-python")
    sys.exit(1)


@dataclass
class LoadTestResult:
    """Single test result"""

    correlation_id: str
    latency_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class LoadTestReport:
    """Complete load test report"""

    test_mode: str
    event_type: str
    start_time: str
    end_time: str
    duration_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    latency_mean: float
    latency_min: float
    latency_max: float
    requests_per_second: float
    errors: List[str]


class LoadTester:
    """Kafka load testing framework"""

    # Topic mappings (using dot-delimited format)
    TOPICS = {
        "validate": {
            "request": "omninode.codegen.request.validate.v1",
            "response": "omninode.codegen.response.validate.v1",
        },
        "analyze": {
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
            "KAFKA_BOOTSTRAP_SERVERS", KAFKA_HOST_SERVERS
        ),
        event_type: str = "validate",
    ):
        self.bootstrap_servers = bootstrap_servers
        self.event_type = event_type
        self.results: List[LoadTestResult] = []

        # Validate event type
        if event_type not in self.TOPICS:
            raise ValueError(
                f"Invalid event_type: {event_type}. Must be one of: {list(self.TOPICS.keys())}"
            )

        # Get topics for this event type
        self.request_topic = self.TOPICS[event_type]["request"]
        self.response_topic = self.TOPICS[event_type]["response"]

        print("🔧 Load Tester Configuration:")
        print(f"   Bootstrap Servers: {bootstrap_servers}")
        print(f"   Event Type: {event_type}")
        print(f"   Request Topic: {self.request_topic}")
        print(f"   Response Topic: {self.response_topic}")
        print()

        # Create reusable producer for all requests
        print("🔌 Initializing KafkaProducer...")
        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3,
            max_in_flight_requests_per_connection=5,
        )
        print("✅ KafkaProducer ready")
        print()

    async def run_concurrent_load_test(
        self, concurrent: int, duration_seconds: int
    ) -> LoadTestReport:
        """Run concurrent load test"""
        print("🚀 Starting Concurrent Load Test")
        print(f"   Concurrency: {concurrent} requests")
        print(f"   Duration: {duration_seconds} seconds")
        print(f"   Event Type: {self.event_type}")
        print()

        start_time = time.time()
        end_time = start_time + duration_seconds

        # Create task pool
        tasks = []

        while time.time() < end_time:
            # Maintain concurrent level
            if len(tasks) < concurrent:
                task = asyncio.create_task(self._send_and_measure())
                tasks.append(task)

            # Clean completed tasks
            tasks = [t for t in tasks if not t.done()]

            await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning

        # Wait for remaining tasks
        if tasks:
            print(f"⏳ Waiting for {len(tasks)} remaining tasks...")
            await asyncio.gather(*tasks, return_exceptions=True)

        actual_duration = time.time() - start_time
        return self._generate_report("concurrent", actual_duration)

    async def run_sustained_load_test(
        self, rate_per_minute: int, duration_seconds: int
    ) -> LoadTestReport:
        """Run sustained rate load test"""
        print("🚀 Starting Sustained Load Test")
        print(f"   Rate: {rate_per_minute} req/min ({rate_per_minute/60:.1f} req/sec)")
        print(f"   Duration: {duration_seconds} seconds")
        print(
            f"   Expected Total: {int(rate_per_minute * duration_seconds / 60)} requests"
        )
        print(f"   Event Type: {self.event_type}")
        print()

        interval_seconds = 60.0 / rate_per_minute
        start_time = time.time()
        end_time = start_time + duration_seconds

        tasks = []
        request_count = 0

        while time.time() < end_time:
            task = asyncio.create_task(self._send_and_measure())
            tasks.append(task)
            request_count += 1

            # Progress indicator
            if request_count % 100 == 0:
                elapsed = time.time() - start_time
                actual_rate = (request_count / elapsed) * 60
                print(
                    f"   📊 Progress: {request_count} requests sent, {elapsed:.1f}s elapsed, {actual_rate:.1f} req/min"
                )

            await asyncio.sleep(interval_seconds)

        # Wait for all tasks
        if tasks:
            print(f"⏳ Waiting for {len(tasks)} remaining tasks...")
            await asyncio.gather(*tasks, return_exceptions=True)

        actual_duration = time.time() - start_time
        return self._generate_report("sustained", actual_duration)

    async def _send_and_measure(self) -> LoadTestResult:
        """Send event and measure latency"""
        correlation_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # Create test event
            event = self._create_test_event(correlation_id)

            # Send to Kafka using reusable producer
            future = self.producer.send(self.request_topic, value=event)
            future.get(timeout=10)  # Wait for send confirmation

            # Note: We're not waiting for response in this simplified version
            # Real e2e testing would consume responses
            latency_ms = (time.time() - start_time) * 1000

            result = LoadTestResult(
                correlation_id=correlation_id, latency_ms=latency_ms, success=True
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            result = LoadTestResult(
                correlation_id=correlation_id,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
            )

        self.results.append(result)
        return result

    def _create_test_event(self, correlation_id: str) -> Dict[str, Any]:
        """Create test event based on event type"""
        base_event = {
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "load_test",
            "version": "1.0",
        }

        # Event-specific payloads (updated to match handler expectations)
        payloads = {
            "validate": {
                "event_type": "codegen.request.validate",
                "payload": {
                    "code_content": "class TestNode(NodeEffect): pass",
                    "node_type": "effect",
                    "language": "python",
                },
            },
            "analyze": {
                "event_type": "codegen.request.analyze",
                "payload": {
                    "prd_content": "User needs: process orders and send confirmations via email.",
                    "analysis_type": "full",
                    "context": {"domain": "ecommerce"},
                },
            },
            "pattern": {
                "event_type": "codegen.request.pattern",
                "payload": {
                    "node_description": "Factory method for creating order processing nodes",
                    "node_type": "effect",
                    "limit": 5,
                    "score_threshold": 0.7,
                },
            },
            "mixin": {
                "event_type": "codegen.request.mixin",
                "payload": {
                    "requirements": ["logging", "error handling"],
                    "node_type": "effect",
                },
            },
        }

        return {**base_event, **payloads[self.event_type]}

    def _generate_report(self, test_mode: str, duration: float) -> LoadTestReport:
        """Generate performance report"""
        if not self.results:
            print("❌ No results to report")
            # Return empty report with zero values instead of None
            return LoadTestReport(
                test_mode=test_mode,
                event_type=self.event_type,
                start_time="",
                end_time="",
                duration_seconds=duration,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                success_rate=0.0,
                latency_p50=0.0,
                latency_p95=0.0,
                latency_p99=0.0,
                latency_mean=0.0,
                latency_min=0.0,
                latency_max=0.0,
                requests_per_second=0.0,
                errors=[],
            )

        latencies = [r.latency_ms for r in self.results]
        successes = sum(1 for r in self.results if r.success)
        failures = len(self.results) - successes

        # Extract error messages
        errors = [r.error for r in self.results if r.error]
        unique_errors = list(set(errors))[:10]  # Top 10 unique errors

        # Calculate percentiles
        sorted_latencies = sorted(latencies)
        p50 = sorted_latencies[len(sorted_latencies) // 2] if sorted_latencies else 0
        p95_idx = int(len(sorted_latencies) * 0.95)
        p95 = sorted_latencies[p95_idx] if sorted_latencies else 0
        p99_idx = int(len(sorted_latencies) * 0.99)
        p99 = sorted_latencies[p99_idx] if sorted_latencies else 0

        report = LoadTestReport(
            test_mode=test_mode,
            event_type=self.event_type,
            start_time=self.results[0].timestamp if self.results else "",
            end_time=self.results[-1].timestamp if self.results else "",
            duration_seconds=duration,
            total_requests=len(self.results),
            successful_requests=successes,
            failed_requests=failures,
            success_rate=successes / len(self.results) if self.results else 0,
            latency_p50=p50,
            latency_p95=p95,
            latency_p99=p99,
            latency_mean=statistics.mean(latencies) if latencies else 0,
            latency_min=min(latencies) if latencies else 0,
            latency_max=max(latencies) if latencies else 0,
            requests_per_second=len(self.results) / duration if duration > 0 else 0,
            errors=unique_errors,
        )

        return report

    def close(self):
        """Clean up resources"""
        if hasattr(self, "producer"):
            print("🔌 Closing KafkaProducer...")
            self.producer.flush()
            self.producer.close()
            print("✅ KafkaProducer closed")


def print_report(report: LoadTestReport) -> None:
    """Print formatted report"""
    print("\n" + "=" * 80)
    print("📊 LOAD TEST REPORT")
    print("=" * 80)
    print("\n🔧 Test Configuration:")
    print(f"   Mode: {report.test_mode}")
    print(f"   Event Type: {report.event_type}")
    print(f"   Duration: {report.duration_seconds:.2f} seconds")
    print()

    print("📈 Summary:")
    print(f"   Total Requests: {report.total_requests}")
    print(f"   Successful: {report.successful_requests} ({report.success_rate:.1%})")
    print(f"   Failed: {report.failed_requests}")
    print(f"   Throughput: {report.requests_per_second:.2f} req/sec")
    print()

    print("⏱️  Latency (ms):")
    print(f"   P50 (median): {report.latency_p50:.2f}")
    print(f"   P95: {report.latency_p95:.2f}")
    print(f"   P99: {report.latency_p99:.2f}")
    print(f"   Mean: {report.latency_mean:.2f}")
    print(f"   Min: {report.latency_min:.2f}")
    print(f"   Max: {report.latency_max:.2f}")
    print()

    if report.errors:
        print(f"❌ Errors ({len(report.errors)} unique):")
        for error in report.errors[:5]:
            print(f"   - {error}")
        print()

    # Success criteria
    print("✅ Success Criteria:")
    success_rate_pass = report.success_rate >= 0.95
    print(
        f"   Success Rate ≥ 95%: {'✅ PASS' if success_rate_pass else '❌ FAIL'} ({report.success_rate:.1%})"
    )

    print("\n" + "=" * 80)


def save_report(report: LoadTestReport, output_file: Path) -> None:
    """Save report to JSON file"""
    report_dict = asdict(report)

    with open(output_file, "w") as f:
        json.dump(report_dict, f, indent=2)

    print(f"💾 Report saved to: {output_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Kafka Load Tester for Archon Intelligence"
    )
    parser.add_argument("--concurrent", type=int, help="Number of concurrent requests")
    parser.add_argument("--rate", type=int, help="Requests per minute (sustained mode)")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    parser.add_argument(
        "--event-type",
        default="validate",
        choices=["validate", "analyze", "pattern", "mixin"],
        help="Event type to test",
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", KAFKA_HOST_SERVERS),
        help=f"Kafka bootstrap servers (default: {KAFKA_HOST_SERVERS} for host machine)",
    )
    parser.add_argument("--output", type=str, help="Output JSON file path")

    args = parser.parse_args()

    # Validate mode
    if not args.concurrent and not args.rate:
        print("Error: Must specify either --concurrent or --rate")
        parser.print_help()
        sys.exit(1)

    if args.concurrent and args.rate:
        print("Error: Cannot specify both --concurrent and --rate")
        parser.print_help()
        sys.exit(1)

    # Create tester
    tester = LoadTester(
        bootstrap_servers=args.bootstrap_servers, event_type=args.event_type
    )

    # Run test
    try:
        if args.concurrent:
            report = asyncio.run(
                tester.run_concurrent_load_test(args.concurrent, args.duration)
            )
        else:
            report = asyncio.run(
                tester.run_sustained_load_test(args.rate, args.duration)
            )

        # Print report
        if report:
            print_report(report)

            # Save to file
            if args.output:
                output_path = Path(args.output)
            else:
                # Auto-generate filename
                mode = "concurrent" if args.concurrent else "sustained"
                value = args.concurrent if args.concurrent else args.rate
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = Path(
                    f"load_test_{mode}_{value}_{args.event_type}_{timestamp}.json"
                )

            save_report(report, output_path)

            # Exit code based on success
            sys.exit(0 if report.success_rate >= 0.95 else 1)
        else:
            print("❌ Failed to generate report")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up resources
        tester.close()


if __name__ == "__main__":
    main()
