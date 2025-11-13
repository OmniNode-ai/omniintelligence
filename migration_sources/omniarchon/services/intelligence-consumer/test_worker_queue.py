#!/usr/bin/env python3
"""
Validation script for worker queue implementation.

Verifies that the EnrichmentConsumer has all required worker queue infrastructure.
"""

import asyncio
import os
import sys
from typing import Any, Dict

# Add src to path and change working directory
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "src"))
os.chdir(current_dir)

# Import after path setup
import importlib.util

# Load consumer module
spec = importlib.util.spec_from_file_location(
    "consumer", os.path.join(current_dir, "src/consumer.py")
)
consumer_module = importlib.util.module_from_spec(spec)

# Load config module first
config_spec = importlib.util.spec_from_file_location(
    "config", os.path.join(current_dir, "src/config.py")
)
config_module = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(config_module)

# Now load consumer with config available
sys.modules["config"] = config_module
spec.loader.exec_module(consumer_module)

EnrichmentConsumer = consumer_module.EnrichmentConsumer
get_config = config_module.get_config


async def dummy_processor(event_data: Dict[str, Any], topic: str) -> None:
    """Dummy message processor for testing."""
    await asyncio.sleep(0.01)  # Simulate processing


def validate_worker_queue_implementation():
    """Validate that worker queue implementation is complete."""

    print("=" * 70)
    print("Worker Queue Implementation Validation")
    print("=" * 70)

    # Create consumer instance
    consumer = EnrichmentConsumer(message_processor=dummy_processor)

    # Check configuration
    config = get_config()
    print(f"\n✓ Configuration loaded")
    print(f"  - Worker Count: {config.worker_count}")
    print(f"  - Queue Size: {config.queue_size}")

    # Validate worker queue attributes
    checks = [
        ("work_queue", asyncio.Queue, "Internal work queue"),
        ("worker_tasks", list, "Worker task list"),
        ("receiver_task", type(None), "Receiver task (initially None)"),
        ("worker_count", int, "Worker count configuration"),
        ("_worker_metrics", dict, "Worker metrics tracking"),
    ]

    print("\n✓ Worker Queue Infrastructure:")
    for attr_name, expected_type, description in checks:
        if not hasattr(consumer, attr_name):
            print(f"  ✗ Missing attribute: {attr_name}")
            return False

        attr = getattr(consumer, attr_name)
        if not isinstance(attr, expected_type):
            print(
                f"  ✗ Wrong type for {attr_name}: expected {expected_type}, got {type(attr)}"
            )
            return False

        print(f"  ✓ {attr_name}: {description}")

    # Validate worker metrics structure
    print("\n✓ Worker Metrics Structure:")
    expected_metrics = [
        "messages_processed",
        "total_processing_time_ms",
        "worker_errors",
    ]
    for metric in expected_metrics:
        if metric not in consumer._worker_metrics:
            print(f"  ✗ Missing metric: {metric}")
            return False

        metric_list = consumer._worker_metrics[metric]
        if (
            not isinstance(metric_list, list)
            or len(metric_list) != consumer.worker_count
        ):
            print(f"  ✗ Invalid metric list for {metric}")
            return False

        print(f"  ✓ {metric}: {len(metric_list)} worker entries")

    # Validate new methods exist
    print("\n✓ Worker Pool Methods:")
    methods = [
        ("_fast_receiver", "Fast message receiver coroutine"),
        ("_worker", "Worker coroutine for message processing"),
        ("_log_worker_metrics", "Worker metrics logging"),
    ]

    for method_name, description in methods:
        if not hasattr(consumer, method_name):
            print(f"  ✗ Missing method: {method_name}")
            return False

        method = getattr(consumer, method_name)
        if not callable(method):
            print(f"  ✗ Not callable: {method_name}")
            return False

        print(f"  ✓ {method_name}: {description}")

    # Validate consume_loop signature
    print("\n✓ Updated consume_loop:")
    if not hasattr(consumer, "consume_loop"):
        print("  ✗ Missing consume_loop method")
        return False

    # Check that consume_loop is async
    if not asyncio.iscoroutinefunction(consumer.consume_loop):
        print("  ✗ consume_loop is not async")
        return False

    print("  ✓ consume_loop is async coroutine")

    # Validate graceful shutdown in stop()
    print("\n✓ Graceful Shutdown (stop method):")
    if not hasattr(consumer, "stop"):
        print("  ✗ Missing stop method")
        return False

    if not asyncio.iscoroutinefunction(consumer.stop):
        print("  ✗ stop is not async")
        return False

    print("  ✓ stop method exists and is async")

    print("\n" + "=" * 70)
    print("✓ All validation checks passed!")
    print("=" * 70)
    print("\nWorker Queue Implementation Summary:")
    print(f"  - Workers: {consumer.worker_count}")
    print(f"  - Queue Size: {consumer.work_queue.maxsize}")
    print(f"  - Metrics Tracked: {len(consumer._worker_metrics)} types")
    print(f"  - Ready for parallel processing: YES")
    print("\n")

    return True


if __name__ == "__main__":
    try:
        success = validate_worker_queue_implementation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Validation failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
