#!/usr/bin/env python3
"""
Publish test events to Kafka/Redpanda for testing intelligence handlers.

Configuration:
    Uses centralized config from config/kafka_helper.py
    Override with KAFKA_BOOTSTRAP_SERVERS environment variable
    Default: 192.168.86.200:29092 (host machine, external port)

Usage:
    python scripts/publish_test_event.py --event-type analyze --prd "Build a user authentication service"
    python scripts/publish_test_event.py --event-type validate --code-file path/to/code.py
    python scripts/publish_test_event.py --event-type pattern --description "cache service"

No need for docker exec - publishes directly to Redpanda.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import centralized configuration
from config.kafka_helper import KAFKA_HOST_SERVERS

try:
    from confluent_kafka import Producer
except ImportError:
    print("Error: confluent-kafka not installed. Install with:")
    print("  uv pip install confluent-kafka")
    print("  or: pip install confluent-kafka")
    sys.exit(1)


class EventPublisher:
    """Publish events to Kafka/Redpanda without docker exec."""

    def __init__(
        self,
        bootstrap_servers: str = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", KAFKA_HOST_SERVERS
        ),
    ):
        """
        Initialize event publisher.

        Args:
            bootstrap_servers: Kafka bootstrap servers (default from config: 192.168.86.200:29092 for host machine)
        """
        self.config = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": "archon-test-publisher",
            "acks": "all",  # Wait for all replicas
            "compression.type": "snappy",
            "linger.ms": 10,  # Small batch delay
        }
        self.producer = Producer(self.config)

    def publish(self, topic: str, event: Dict[str, Any]) -> None:
        """
        Publish event to Kafka topic.

        Args:
            topic: Kafka topic name
            event: Event payload dictionary
        """
        try:
            # Serialize event to JSON
            value = json.dumps(event).encode("utf-8")

            # Produce message
            self.producer.produce(
                topic=topic,
                value=value,
                key=event.get("correlation_id", str(uuid.uuid4())).encode("utf-8"),
                callback=self._delivery_callback,
            )

            # Wait for delivery
            self.producer.flush()

            print(f"✅ Published to {topic}")
            print(f"   Correlation ID: {event.get('correlation_id')}")
            print(f"   Event Type: {event.get('event_type')}")

        except Exception as e:
            print(f"❌ Failed to publish: {e}", file=sys.stderr)
            raise

    def _delivery_callback(self, err, msg):
        """Delivery callback for async confirmation."""
        if err:
            print(f"❌ Delivery failed: {err}", file=sys.stderr)
        else:
            print(
                f"   Delivered to partition {msg.partition()} at offset {msg.offset()}"
            )


def create_analysis_event(prd_content: str) -> Dict[str, Any]:
    """Create CodegenAnalysisRequest event."""
    return {
        "correlation_id": str(uuid.uuid4()),
        "event_type": "codegen.request.analyze",
        "timestamp": datetime.utcnow().isoformat(),
        "payload": {
            "prd_content": prd_content,
            "analysis_type": "full",
            "workspace_context": {
                "project": "test_project",
                "language": "python",
            },
        },
        "metadata": {
            "source": "test_publisher",
            "version": "1.0.0",
        },
    }


def create_validation_event(
    code_content: str, node_type: str = "effect"
) -> Dict[str, Any]:
    """Create CodegenValidationRequest event."""
    return {
        "correlation_id": str(uuid.uuid4()),
        "event_type": "codegen.request.validate",
        "timestamp": datetime.utcnow().isoformat(),
        "payload": {
            "code_content": code_content,
            "node_type": node_type,
            "validation_level": "full",
        },
        "metadata": {
            "source": "test_publisher",
            "version": "1.0.0",
        },
    }


def create_pattern_event(description: str, node_type: str = "effect") -> Dict[str, Any]:
    """Create CodegenPatternRequest event."""
    return {
        "correlation_id": str(uuid.uuid4()),
        "event_type": "codegen.request.pattern",
        "timestamp": datetime.utcnow().isoformat(),
        "payload": {
            "node_description": description,
            "node_type": node_type,
            "limit": 5,
        },
        "metadata": {
            "source": "test_publisher",
            "version": "1.0.0",
        },
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Publish test events to Kafka/Redpanda for intelligence handler testing"
    )
    parser.add_argument(
        "--event-type",
        choices=["analyze", "validate", "pattern", "mixin"],
        required=True,
        help="Type of event to publish",
    )
    parser.add_argument(
        "--prd",
        help="PRD content for analysis events",
    )
    parser.add_argument(
        "--code",
        help="Code content for validation (inline string)",
    )
    parser.add_argument(
        "--code-file",
        help="Path to code file for validation",
    )
    parser.add_argument(
        "--description",
        help="Node description for pattern matching",
    )
    parser.add_argument(
        "--node-type",
        default="effect",
        help="Node type (effect, compute, reducer, orchestrator)",
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", KAFKA_HOST_SERVERS),
        help=f"Kafka bootstrap servers (default: {KAFKA_HOST_SERVERS} for host machine)",
    )
    parser.add_argument(
        "--topic",
        help="Override default topic (auto-generated from event type)",
    )

    args = parser.parse_args()

    # Create event based on type
    if args.event_type == "analyze":
        if not args.prd:
            parser.error("--prd required for analyze events")
        event = create_analysis_event(args.prd)
        topic = args.topic or "omninode.codegen.request.analyze.v1"

    elif args.event_type == "validate":
        if args.code_file:
            code_path = Path(args.code_file)
            if not code_path.exists():
                parser.error(f"Code file not found: {args.code_file}")
            code_content = code_path.read_text()
        elif args.code:
            code_content = args.code
        else:
            parser.error("--code or --code-file required for validate events")

        event = create_validation_event(code_content, args.node_type)
        topic = args.topic or "omninode.codegen.request.validate.v1"

    elif args.event_type == "pattern":
        if not args.description:
            parser.error("--description required for pattern events")
        event = create_pattern_event(args.description, args.node_type)
        topic = args.topic or "omninode.codegen.request.pattern.v1"

    elif args.event_type == "mixin":
        if not args.description:
            parser.error("--description required for mixin events")
        # Similar to pattern but different topic
        event = create_pattern_event(args.description, args.node_type)
        event["event_type"] = "codegen.request.mixin"
        topic = args.topic or "omninode.codegen.request.mixin.v1"

    # Publish event
    publisher = EventPublisher(bootstrap_servers=args.bootstrap_servers)

    print(f"\n📨 Publishing {args.event_type} event to {topic}...")
    print(f"   Bootstrap: {args.bootstrap_servers}")
    print()

    try:
        publisher.publish(topic, event)
        print("\n✨ Event published successfully!")
        print("\n📋 Event Summary:")
        print(json.dumps(event, indent=2))

    except Exception as e:
        print(f"\n❌ Failed to publish event: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
