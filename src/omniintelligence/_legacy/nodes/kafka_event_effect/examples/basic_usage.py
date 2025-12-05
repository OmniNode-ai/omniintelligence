"""
Basic usage examples for Kafka Event Effect Node.

This file demonstrates various usage patterns for the Kafka event effect node,
including basic publishing, error handling, and integration with workflows.
"""

from uuid import uuid4

from omniintelligence.nodes.kafka_event_effect import (
    ModelKafkaEventConfig,
    ModelKafkaEventInput,
    NodeKafkaEventEffect,
)


async def example_basic_publishing() -> None:
    """Example: Basic event publishing."""
    print("\n=== Example: Basic Event Publishing ===\n")

    # Create and initialize node
    node = NodeKafkaEventEffect(container=None)
    await node.initialize()

    # Publish quality assessment event
    input_data = ModelKafkaEventInput(
        topic="quality.assessed.v1",
        event_type="QUALITY_ASSESSED",
        payload={
            "quality_score": 0.87,
            "entity_id": "abc-123",
            "onex_compliance": 0.92,
            "issues_count": 3,
            "recommendations_count": 5,
        },
        correlation_id=uuid4(),
    )

    output = await node.execute_effect(input_data)

    if output.success:
        print("✅ Event published successfully!")
        print(f"   Topic: {output.topic}")
        print(f"   Partition: {output.partition}")
        print(f"   Offset: {output.offset}")
        print(f"   Correlation ID: {output.correlation_id}")
    else:
        print(f"❌ Event publishing failed: {output.error}")

    # Display metrics
    metrics = node.get_metrics()
    print("\n📊 Metrics:")
    print(f"   Events published: {metrics['events_published']}")
    print(f"   Events failed: {metrics['events_failed']}")
    print(f"   Avg publish time: {metrics['avg_publish_time_ms']:.2f}ms")

    await node.shutdown()


async def example_custom_configuration() -> None:
    """Example: Custom configuration."""
    print("\n=== Example: Custom Configuration ===\n")

    # Create custom configuration
    config = ModelKafkaEventConfig(
        bootstrap_servers="localhost:9092",
        topic_prefix="test",
        enable_idempotence=True,
        acks="all",
        max_retries=5,
        retry_backoff_ms=2000,
        circuit_breaker_threshold=10,
        circuit_breaker_timeout_s=120,
        enable_dlq=True,
    )

    # Create node with custom config
    node = NodeKafkaEventEffect(container=None, config=config)
    await node.initialize()

    print("✅ Node initialized with custom config:")
    print(f"   Bootstrap servers: {config.bootstrap_servers}")
    print(f"   Topic prefix: {config.topic_prefix}")
    print(f"   Max retries: {config.max_retries}")
    print(f"   Circuit breaker threshold: {config.circuit_breaker_threshold}")

    await node.shutdown()


async def example_batch_publishing() -> None:
    """Example: Publishing multiple events."""
    print("\n=== Example: Batch Event Publishing ===\n")

    node = NodeKafkaEventEffect(container=None)
    await node.initialize()

    correlation_id = uuid4()

    # Event types to publish
    events = [
        {
            "topic": "enrichment.completed.v1",
            "event_type": "DOCUMENT_INGESTED",
            "payload": {
                "document_id": "doc-123",
                "entities_count": 42,
                "relationships_count": 18,
            },
        },
        {
            "topic": "pattern.extracted.v1",
            "event_type": "PATTERN_EXTRACTED",
            "payload": {
                "pattern_type": "architectural",
                "confidence": 0.95,
            },
        },
        {
            "topic": "quality.assessed.v1",
            "event_type": "QUALITY_ASSESSED",
            "payload": {
                "quality_score": 0.87,
                "onex_compliance": 0.92,
            },
        },
    ]

    # Publish all events
    for event in events:
        input_data = ModelKafkaEventInput(
            topic=str(event["topic"]),
            event_type=str(event["event_type"]),
            payload=event["payload"],  # type: ignore[arg-type]
            correlation_id=correlation_id,
        )

        output = await node.execute_effect(input_data)

        if output.success:
            print(f"✅ {event['event_type']} published (partition={output.partition}, offset={output.offset})")
        else:
            print(f"❌ {event['event_type']} failed: {output.error}")

    # Display final metrics
    metrics = node.get_metrics()
    print("\n📊 Final Metrics:")
    print(f"   Events published: {metrics['events_published']}")
    print(f"   Events failed: {metrics['events_failed']}")
    print(f"   Avg publish time: {metrics['avg_publish_time_ms']:.2f}ms")

    await node.shutdown()


async def example_error_handling() -> None:
    """Example: Error handling and DLQ routing."""
    print("\n=== Example: Error Handling ===\n")

    node = NodeKafkaEventEffect(container=None)
    await node.initialize()

    # Publish event (would route to DLQ on failure)
    input_data = ModelKafkaEventInput(
        topic="enrichment.failed.v1",
        event_type="PROCESSING_FAILED",
        payload={
            "document_id": "doc-456",
            "error_message": "Vectorization failed",
            "failed_step": "vectorize_document",
        },
        correlation_id=uuid4(),
    )

    output = await node.execute_effect(input_data)

    if output.success:
        print(f"✅ Error event published to {output.topic}")
    else:
        print(f"❌ Failed to publish error event: {output.error}")

    # Display circuit breaker status
    metrics = node.get_metrics()
    print(f"\n🔌 Circuit Breaker Status: {metrics['circuit_breaker_status']}")
    print(f"   Current failures: {metrics['current_failures']}")
    print(f"   DLQ routed: {metrics['events_sent_to_dlq']}")

    await node.shutdown()


async def example_partition_key() -> None:
    """Example: Using partition keys for ordered delivery."""
    print("\n=== Example: Partition Keys for Ordering ===\n")

    node = NodeKafkaEventEffect(container=None)
    await node.initialize()

    # Publish events with same partition key for ordered delivery
    entity_id = "entity-123"

    events = [
        {"event_type": "ENTITY_CREATED", "status": "created"},
        {"event_type": "ENTITY_UPDATED", "status": "updated"},
        {"event_type": "ENTITY_DELETED", "status": "deleted"},
    ]

    for event in events:
        input_data = ModelKafkaEventInput(
            topic="entity.events.v1",
            event_type=event["event_type"],
            payload={
                "entity_id": entity_id,
                "status": event["status"],
            },
            correlation_id=uuid4(),
            key=entity_id,  # Same partition key ensures ordering
        )

        output = await node.execute_effect(input_data)

        if output.success:
            print(f"✅ {event['event_type']} → partition {output.partition} (ordered by key={entity_id})")

    await node.shutdown()


async def main() -> None:
    """Run all examples."""
    print("\n" + "=" * 70)
    print("Kafka Event Effect Node - Usage Examples")
    print("=" * 70)

    try:
        # Run examples
        await example_basic_publishing()
        await example_custom_configuration()
        await example_batch_publishing()
        await example_error_handling()
        await example_partition_key()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Note: These examples demonstrate the API but won't actually publish
    # to Kafka without a running Kafka/Redpanda instance.
    # To run against a real Kafka instance, set environment variables:
    #   export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
    #   export KAFKA_TOPIC_PREFIX=dev.test

    # Uncomment to run examples:
    # asyncio.run(main())

    print("\n" + "=" * 70)
    print("Kafka Event Effect Node - Usage Examples")
    print("=" * 70)
    print("\nTo run these examples:")
    print("1. Start a Kafka/Redpanda instance")
    print("2. Set environment variables:")
    print("   export KAFKA_BOOTSTRAP_SERVERS=localhost:9092")
    print("   export KAFKA_TOPIC_PREFIX=dev.test")
    print("3. Uncomment asyncio.run(main()) at the bottom of this file")
    print("4. Run: python basic_usage.py")
    print("\n" + "=" * 70 + "\n")
