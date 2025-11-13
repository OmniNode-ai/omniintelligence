#!/usr/bin/env python3
"""
Kafka Topic Recreation Script
Purpose: Fix UnknownTopicOrPartitionError by recreating topic with correct configuration

Configuration:
    Uses centralized config from config/kafka_helper.py
    Override with KAFKA_BOOTSTRAP_SERVERS environment variable
    Default: 192.168.86.200:29092 (host machine, external port)

ONEX Pattern: Effect (external I/O operations with fail-fast validation)
Created: 2025-11-01
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, UnknownTopicOrPartitionError

# Import centralized configuration
from config.kafka_helper import KAFKA_HOST_SERVERS

# Configuration
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", KAFKA_HOST_SERVERS)
TOPIC_NAME = "dev.archon-intelligence.enrich-document.v1"
PARTITIONS = 4
REPLICATION_FACTOR = 1


def log_info(msg):
    print(f"\033[0;34m[INFO]\033[0m {msg}")


def log_success(msg):
    print(f"\033[0;32m[SUCCESS]\033[0m {msg}")


def log_warning(msg):
    print(f"\033[1;33m[WARNING]\033[0m {msg}")


def log_error(msg):
    print(f"\033[0;31m[ERROR]\033[0m {msg}", file=sys.stderr)


def log_section(msg):
    print(f"\n{'='*70}")
    print(msg)
    print("=" * 70)


def main():
    log_section("KAFKA TOPIC RECREATION WORKFLOW")
    log_info(f"Topic: {TOPIC_NAME}")
    log_info(f"Bootstrap servers: {BOOTSTRAP_SERVERS}")
    log_info(f"Partitions: {PARTITIONS}")
    log_info(f"Replication factor: {REPLICATION_FACTOR}")

    try:
        # Create admin client
        log_section("STEP 1: CONNECT TO KAFKA")
        log_info("Creating Kafka admin client...")
        admin_client = KafkaAdminClient(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            client_id="topic-recreation-script",
            request_timeout_ms=30000,
        )
        log_success("Connected to Kafka")

        # List existing topics
        log_section("STEP 2: CHECK EXISTING TOPICS")
        topics = admin_client.list_topics()
        log_info(f"Found {len(topics)} topics")

        if TOPIC_NAME in topics:
            log_warning(f"Topic {TOPIC_NAME} exists")

            # Delete existing topic
            log_section("STEP 3: DELETE EXISTING TOPIC")
            log_warning(f"Deleting topic: {TOPIC_NAME}")
            try:
                admin_client.delete_topics([TOPIC_NAME], timeout_ms=30000)
                log_success("Topic deleted successfully")

                # Wait a moment for deletion to propagate
                import time

                log_info("Waiting 5 seconds for deletion to propagate...")
                time.sleep(5)
            except Exception as e:
                log_error(f"Failed to delete topic: {e}")
                return 1
        else:
            log_info(f"Topic {TOPIC_NAME} does not exist")

        # Create new topic
        log_section("STEP 4: CREATE NEW TOPIC")
        log_info(f"Creating topic: {TOPIC_NAME}")
        log_info(f"  Partitions: {PARTITIONS}")
        log_info(f"  Replication factor: {REPLICATION_FACTOR}")

        new_topic = NewTopic(
            name=TOPIC_NAME,
            num_partitions=PARTITIONS,
            replication_factor=REPLICATION_FACTOR,
        )

        try:
            admin_client.create_topics([new_topic], timeout_ms=30000)
            log_success(f"Topic {TOPIC_NAME} created successfully")
        except TopicAlreadyExistsError:
            log_warning("Topic already exists (expected if just created)")
        except Exception as e:
            log_error(f"Failed to create topic: {e}")
            return 1

        # Verify topic creation
        log_section("STEP 5: VERIFY TOPIC CREATION")
        topics = admin_client.list_topics()
        if TOPIC_NAME in topics:
            log_success(f"Topic {TOPIC_NAME} verified in topic list")

            # Get topic metadata
            metadata = admin_client.describe_topics([TOPIC_NAME])
            if metadata:
                topic_meta = metadata[0]
                log_info(f"Topic details:")
                log_info(f"  Name: {topic_meta['topic']}")
                log_info(f"  Partitions: {len(topic_meta['partitions'])}")
                for partition in topic_meta["partitions"]:
                    log_info(
                        f"    Partition {partition['partition']}: leader={partition['leader']}"
                    )
        else:
            log_error(f"Topic {TOPIC_NAME} NOT found after creation")
            return 1

        log_section("TOPIC RECREATION COMPLETE")
        log_success(f"Topic {TOPIC_NAME} is ready")
        log_info("")
        log_info("Next steps:")
        log_info(
            "  1. Restart consumer containers: docker restart archon-intelligence-consumer-{1..4}"
        )
        log_info("  2. Monitor consumer logs for successful consumption")
        log_info("  3. Verify Qdrant vector count increases")

        return 0

    except Exception as e:
        log_error(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        try:
            admin_client.close()
        except:
            pass


if __name__ == "__main__":
    sys.exit(main())
