#!/usr/bin/env python3
"""
Correlation ID Tracking Script

Tracks a correlation ID across all Kafka topics to verify end-to-end tracking.
Useful for debugging event flow and verifying correlation ID preservation.

Usage:
    python scripts/track_correlation_id.py <correlation_id>
    python scripts/track_correlation_id.py <correlation_id> --bootstrap-servers localhost:19092
    python scripts/track_correlation_id.py <correlation_id> --timeout 60
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

try:
    from kafka import KafkaConsumer
    from kafka.admin import KafkaAdminClient
except ImportError:
    print("❌ Error: kafka-python not installed")
    print("Install with: pip install kafka-python")
    sys.exit(1)


@dataclass
class EventOccurrence:
    """Single event occurrence with correlation ID"""

    topic: str
    partition: int
    offset: int
    timestamp: int
    event_type: str
    event_data: Dict[str, Any]

    @property
    def timestamp_str(self) -> str:
        """Human-readable timestamp"""
        return datetime.fromtimestamp(self.timestamp / 1000).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]


class CorrelationIDTracker:
    """Track correlation ID across Kafka topics"""

    # All topics to monitor (based on KafkaTestConfig)
    ALL_TOPICS = [
        # Request topics
        "omninode.codegen.request.validate.v1",
        "omninode.codegen.request.analyze.v1",
        "omninode.codegen.request.pattern.v1",
        "omninode.codegen.request.mixin.v1",
        # Response topics
        "omninode.codegen.response.validate.v1",
        "omninode.codegen.response.analyze.v1",
        "omninode.codegen.response.pattern.v1",
        "omninode.codegen.response.mixin.v1",
        # System topics (if needed)
        "omninode.service.lifecycle",
        "omninode.tool.updates",
        "omninode.system.events",
        "omninode.bridge.events",
    ]

    def __init__(
        self,
        correlation_id: str,
        bootstrap_servers: str = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:9092"
        ),
        timeout_seconds: int = 30,
    ):
        """
        Initialize correlation ID tracker

        Args:
            correlation_id: Correlation ID to track
            bootstrap_servers: Kafka bootstrap servers (default: 192.168.86.200:9092 for host machine)
            timeout_seconds: Timeout for tracking
        """
        self.correlation_id = correlation_id
        self.bootstrap_servers = bootstrap_servers
        self.timeout_seconds = timeout_seconds
        self.occurrences: List[EventOccurrence] = []

    def verify_kafka_connectivity(self) -> bool:
        """
        Verify Kafka connectivity

        Returns:
            True if connected, False otherwise
        """
        try:
            print("🔍 Verifying Kafka connectivity...")
            print(f"   Bootstrap servers: {self.bootstrap_servers}")

            admin = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers, request_timeout_ms=5000
            )

            topics = admin.list_topics()
            print(f"   ✅ Connected! Found {len(topics)} topics")

            admin.close()
            return True

        except Exception as e:
            print(f"   ❌ Connection failed: {e}")
            return False

    def get_available_topics(self) -> List[str]:
        """
        Get list of available topics from configured topics

        Returns:
            List of available topic names
        """
        try:
            admin = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers, request_timeout_ms=5000
            )

            all_topics = admin.list_topics()
            admin.close()

            # Filter to only our configured topics
            available = [topic for topic in self.ALL_TOPICS if topic in all_topics]
            return available

        except Exception as e:
            print(f"⚠️  Could not get topics: {e}")
            return self.ALL_TOPICS  # Return all configured topics as fallback

    def track(self) -> bool:
        """
        Track correlation ID across topics

        Returns:
            True if correlation ID found, False otherwise
        """
        print("=" * 70)
        print("🔍 CORRELATION ID TRACKER")
        print("=" * 70)
        print(f"Tracking: {self.correlation_id}")
        print(f"Timeout: {self.timeout_seconds}s")
        print("=" * 70)
        print()

        # Verify connectivity
        if not self.verify_kafka_connectivity():
            print("\n❌ Cannot proceed - Kafka not available")
            return False

        # Get available topics
        topics_to_monitor = self.get_available_topics()

        if not topics_to_monitor:
            print("❌ No topics available to monitor")
            return False

        print(f"\n📡 Monitoring {len(topics_to_monitor)} topics:")
        for topic in topics_to_monitor:
            print(f"   • {topic}")
        print()

        # Create consumer
        try:
            consumer = KafkaConsumer(
                *topics_to_monitor,
                bootstrap_servers=self.bootstrap_servers,
                group_id=f"correlation-tracker-{self.correlation_id}",
                auto_offset_reset="earliest",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                consumer_timeout_ms=1000,
                enable_auto_commit=False,
            )
        except Exception as e:
            print(f"❌ Failed to create consumer: {e}")
            return False

        print(f"⏳ Searching for correlation ID (timeout: {self.timeout_seconds}s)...")
        print()

        start_time = time.time()
        messages_checked = 0

        try:
            while time.time() - start_time < self.timeout_seconds:
                messages = consumer.poll(timeout_ms=1000)

                for topic_partition, records in messages.items():
                    for record in records:
                        messages_checked += 1

                        # Check if correlation ID matches
                        event = record.value
                        if event.get("correlation_id") == self.correlation_id:
                            occurrence = EventOccurrence(
                                topic=record.topic,
                                partition=record.partition,
                                offset=record.offset,
                                timestamp=record.timestamp,
                                event_type=event.get("event_type", "unknown"),
                                event_data=event,
                            )

                            self.occurrences.append(occurrence)

                            # Print immediately when found
                            print(f"✅ Found occurrence #{len(self.occurrences)}")
                            print(f"   Topic: {occurrence.topic}")
                            print(f"   Event Type: {occurrence.event_type}")
                            print(f"   Timestamp: {occurrence.timestamp_str}")
                            print(
                                f"   Partition: {occurrence.partition}, Offset: {occurrence.offset}"
                            )
                            print()

                # Show progress every 5 seconds
                if messages_checked > 0 and int(time.time() - start_time) % 5 == 0:
                    elapsed = int(time.time() - start_time)
                    print(
                        f"   Progress: {messages_checked} messages checked, {elapsed}s elapsed"
                    )

        except KeyboardInterrupt:
            print("\n⚠️  Tracking interrupted by user")
        except Exception as e:
            print(f"\n❌ Error during tracking: {e}")
        finally:
            consumer.close()

        print()
        print(
            f"📊 Checked {messages_checked} messages in {int(time.time() - start_time)}s"
        )
        print()

        # Generate report
        self._print_report()

        return len(self.occurrences) > 0

    def _print_report(self):
        """Print tracking report"""
        print("=" * 70)
        print("📋 TRACKING REPORT")
        print("=" * 70)
        print(f"Correlation ID: {self.correlation_id}")
        print(f"Occurrences Found: {len(self.occurrences)}")
        print("=" * 70)
        print()

        if not self.occurrences:
            print("❌ Correlation ID NOT FOUND in any topic")
            print()
            print("Possible reasons:")
            print("  • Event not yet published")
            print("  • Correlation ID mismatch")
            print("  • Event already expired/deleted")
            print("  • Wrong Kafka bootstrap servers")
            return

        print("✅ Correlation ID FOUND!")
        print()

        # Sort by timestamp
        sorted_occurrences = sorted(self.occurrences, key=lambda x: x.timestamp)

        # Display journey
        print("🚀 Event Journey:")
        print("-" * 70)

        for i, occurrence in enumerate(sorted_occurrences, 1):
            print(f"\n{i}. {occurrence.topic}")
            print(f"   Event Type: {occurrence.event_type}")
            print(f"   Timestamp: {occurrence.timestamp_str}")
            print(
                f"   Location: partition={occurrence.partition}, offset={occurrence.offset}"
            )

            # Show key payload fields
            payload = occurrence.event_data.get("payload", {})
            if payload:
                print(f"   Payload Keys: {', '.join(payload.keys())}")

        print()
        print("-" * 70)

        # Analyze journey
        request_topics = [o for o in sorted_occurrences if "request" in o.topic]
        response_topics = [o for o in sorted_occurrences if "response" in o.topic]

        print("\n📊 Journey Analysis:")
        print(f"   Request Events: {len(request_topics)}")
        print(f"   Response Events: {len(response_topics)}")

        if request_topics and response_topics:
            # Calculate latency
            first_request = request_topics[0]
            first_response = response_topics[0]
            latency_ms = first_response.timestamp - first_request.timestamp

            print(f"   Request → Response Latency: {latency_ms}ms")
            print()
            print("✅ Complete end-to-end tracking verified!")
        elif request_topics and not response_topics:
            print()
            print("⚠️  Request found but no response yet")
            print("   Handler may still be processing or failed")
        elif response_topics and not request_topics:
            print()
            print("⚠️  Response found but no request")
            print("   Request may have expired or been deleted")

        print()
        print("=" * 70)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Track correlation ID across Kafka topics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s abc-123-def
  %(prog)s abc-123-def --bootstrap-servers localhost:9092
  %(prog)s abc-123-def --timeout 60
        """,
    )

    parser.add_argument("correlation_id", help="Correlation ID to track")
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:9092"),
        help="Kafka bootstrap servers (default: 192.168.86.200:9092 for host machine)",
    )
    parser.add_argument(
        "--timeout", type=int, default=30, help="Timeout in seconds (default: 30)"
    )

    args = parser.parse_args()

    # Create tracker
    tracker = CorrelationIDTracker(
        correlation_id=args.correlation_id,
        bootstrap_servers=args.bootstrap_servers,
        timeout_seconds=args.timeout,
    )

    # Track correlation ID
    success = tracker.track()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
