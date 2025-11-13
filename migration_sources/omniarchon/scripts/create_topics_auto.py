#!/usr/bin/env python3
"""
Auto-create Kafka topics by producing to them.
Redpanda has auto_create_topics enabled, so topics will be created on first produce.
"""

import os
import sys

from confluent_kafka import Producer

# Add parent directory to path for config imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.kafka_helper import KAFKA_HOST_SERVERS

# Redpanda connection (use external port from host)
conf = {"bootstrap.servers": KAFKA_HOST_SERVERS, "client.id": "topic-creator"}

# Topics to create
topics = [
    "dev.archon-intelligence.enrich-document.v1",
    "dev.archon-intelligence.enrich-document-completed.v1",
    "dev.archon-intelligence.enrich-document-dlq.v1",
]


def delivery_report(err, msg):
    """Called once for each message produced to indicate delivery result."""
    if err is not None:
        print(f"❌ Message delivery failed: {err}")
    else:
        print(f"✅ Created topic: {msg.topic()} (partition {msg.partition()})")


producer = Producer(conf)

print("Creating topics by producing initial messages...")
print("(Redpanda will auto-create topics on first produce)\n")

for topic in topics:
    try:
        # Produce a dummy message to trigger topic creation
        producer.produce(
            topic, key="init", value="Topic initialized", callback=delivery_report
        )
    except Exception as e:
        print(f"❌ Failed to produce to {topic}: {e}")
        sys.exit(1)

# Wait for all messages to be delivered
producer.flush(timeout=10)

print("\n✅ All topics created successfully!")
print(
    "\nVerify with: docker exec omninode-bridge-redpanda rpk topic list | grep enrich"
)
