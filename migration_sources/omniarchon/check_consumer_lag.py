#!/usr/bin/env python3
"""Check consumer group lag for archon-intelligence consumers."""

import sys

from confluent_kafka import Consumer, KafkaError, TopicPartition


def check_lag():
    """Check consumer group lag."""
    conf = {
        "bootstrap.servers": "192.168.86.200:29092",
        "group.id": "archon-intelligence-consumer-group",
        "auto.offset.reset": "earliest",
    }

    consumer = Consumer(conf)

    try:
        # Get committed offsets for the consumer group
        topic = "dev.archon-intelligence.enrich-document.v1"
        partition = TopicPartition(topic, 0)

        # Get committed offset
        committed = consumer.committed([partition], timeout=10.0)
        committed_offset = (
            committed[0].offset if committed and committed[0].offset >= 0 else 0
        )

        # Get high watermark (end offset)
        low, high = consumer.get_watermark_offsets(partition, timeout=10.0)

        lag = high - committed_offset

        print(f"Topic: {topic}")
        print(f"Partition: 0")
        print(f"Committed Offset: {committed_offset}")
        print(f"High Watermark: {high}")
        print(f"Lag: {lag} messages")
        print(f"\n{lag} messages remaining to be consumed")

        return lag

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None
    finally:
        consumer.close()


if __name__ == "__main__":
    check_lag()
