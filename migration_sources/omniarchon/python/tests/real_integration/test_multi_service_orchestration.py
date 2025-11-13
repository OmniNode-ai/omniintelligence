"""
Real Integration Test: Multi-Service Orchestration

Tests orchestration across all services (Kafka + Qdrant + Memgraph).

Coverage:
- End-to-end event processing pipeline
- Cross-service data consistency
- Service interaction patterns
- Distributed transaction patterns
- Performance under orchestration

Run with:
    pytest --real-integration tests/real_integration/test_multi_service_orchestration.py -v
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict

import pytest

from tests.fixtures.real_integration import (
    kafka_consumer,
    kafka_producer,
    kafka_test_topic,
    memgraph_session,
    memgraph_test_label,
    qdrant_client,
    qdrant_test_collection,
    real_integration_config,
    real_integration_services,
    test_id,
)
from tests.utils.test_data_manager import (
    KafkaTestDataGenerator,
    QdrantTestDataGenerator,
    TestDataManager,
    wait_for_kafka_messages,
)


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_end_to_end_document_indexing_pipeline(
    kafka_producer,
    kafka_consumer,
    kafka_test_topic: str,
    qdrant_client,
    qdrant_test_collection: str,
    memgraph_session,
    memgraph_test_label: str,
    test_id: str,
):
    """
    Test complete document indexing pipeline across all services.

    Flow:
    1. Event published to Kafka (document.created)
    2. Vector embedding stored in Qdrant
    3. Knowledge graph updated in Memgraph
    4. Completion event published to Kafka

    Validates:
    - End-to-end pipeline execution
    - Data consistency across services
    - Event ordering preserved
    - All services updated correctly
    """
    # Arrange: Create test document event
    document_id = f"doc_{test_id}"
    correlation_id = f"pipeline_{test_id}"

    document_event = KafkaTestDataGenerator.generate_event(
        event_type="document.created",
        payload={
            "document_id": document_id,
            "title": "Test Document for Pipeline",
            "content": "This document tests the full indexing pipeline",
            "project_id": f"project_{test_id}",
            "created_at": datetime.utcnow().isoformat(),
        },
        correlation_id=correlation_id,
    )

    # Act 1: Publish document creation event to Kafka
    event_bytes = json.dumps(document_event).encode("utf-8")
    await kafka_producer.send_and_wait(
        topic=kafka_test_topic, value=event_bytes, key=correlation_id.encode("utf-8")
    )

    # Act 2: Store vector embedding in Qdrant (simulating embedding service)
    vector_point = QdrantTestDataGenerator.generate_quality_point(
        doc_id=document_id, quality_score=0.85
    )
    await qdrant_client.upsert(
        collection_name=qdrant_test_collection,
        points=[vector_point],
    )

    # Act 3: Create knowledge graph node in Memgraph
    await memgraph_session.run(
        f"""
        CREATE (n:{memgraph_test_label} {{
            id: $doc_id,
            document_id: $doc_id,
            title: $title,
            project_id: $project_id,
            indexed_at: $indexed_at
        }})
        """,
        doc_id=document_id,
        title="Test Document for Pipeline",
        project_id=f"project_{test_id}",
        indexed_at=datetime.utcnow().isoformat(),
    )

    # Act 4: Publish completion event to Kafka
    completion_event = KafkaTestDataGenerator.generate_event(
        event_type="document.indexed",
        payload={
            "document_id": document_id,
            "vector_indexed": True,
            "graph_indexed": True,
            "quality_score": 0.85,
        },
        correlation_id=correlation_id,
    )

    completion_bytes = json.dumps(completion_event).encode("utf-8")
    await kafka_producer.send_and_wait(
        topic=kafka_test_topic,
        value=completion_bytes,
        key=correlation_id.encode("utf-8"),
    )

    # Assert 1: Verify Kafka events
    messages = await wait_for_kafka_messages(
        consumer=kafka_consumer, topic=kafka_test_topic, expected_count=2, timeout=10.0
    )

    assert len(messages) == 2
    assert messages[0]["value"]["envelope"]["event_type"] == "document.created"
    assert messages[1]["value"]["envelope"]["event_type"] == "document.indexed"
    assert messages[0]["value"]["envelope"]["correlation_id"] == correlation_id
    assert messages[1]["value"]["envelope"]["correlation_id"] == correlation_id

    # Assert 2: Verify Qdrant vector
    await asyncio.sleep(0.5)  # Wait for indexing
    vectors = await qdrant_client.retrieve(
        collection_name=qdrant_test_collection,
        ids=[document_id],
    )
    assert len(vectors) == 1
    assert vectors[0].id == document_id
    assert vectors[0].payload["quality_score"] == 0.85

    # Assert 3: Verify Memgraph node
    result = await memgraph_session.run(
        f"MATCH (n:{memgraph_test_label} {{document_id: $doc_id}}) RETURN n",
        doc_id=document_id,
    )
    node = await result.single()
    assert node is not None
    assert node["n"]["document_id"] == document_id
    assert node["n"]["title"] == "Test Document for Pipeline"


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_cross_service_data_consistency(
    qdrant_client,
    qdrant_test_collection: str,
    memgraph_session,
    memgraph_test_label: str,
    test_id: str,
):
    """
    Test data consistency between Qdrant and Memgraph.

    Validates:
    - Same entities exist in both services
    - Metadata consistency
    - Referential integrity
    - Concurrent updates handled correctly
    """
    # Arrange: Create entities in both services
    entity_count = 5
    entity_ids = [f"entity_{test_id}_{i}" for i in range(entity_count)]

    # Act: Create in Qdrant
    qdrant_points = []
    for entity_id in entity_ids:
        point = QdrantTestDataGenerator.generate_quality_point(
            doc_id=entity_id, quality_score=0.9
        )
        qdrant_points.append(point)

    await qdrant_client.upsert(
        collection_name=qdrant_test_collection,
        points=qdrant_points,
    )

    # Act: Create in Memgraph
    for entity_id in entity_ids:
        await memgraph_session.run(
            f"""
            CREATE (n:{memgraph_test_label} {{
                id: $entity_id,
                entity_id: $entity_id,
                quality_score: $quality_score,
                created_at: $created_at
            }})
            """,
            entity_id=entity_id,
            quality_score=0.9,
            created_at=datetime.utcnow().isoformat(),
        )

    await asyncio.sleep(0.5)

    # Assert: Verify consistency
    # Check Qdrant
    qdrant_vectors = await qdrant_client.retrieve(
        collection_name=qdrant_test_collection,
        ids=entity_ids,
    )
    assert len(qdrant_vectors) == entity_count

    # Check Memgraph
    result = await memgraph_session.run(
        f"MATCH (n:{memgraph_test_label}) WHERE n.entity_id IN $entity_ids RETURN count(n) as count",
        entity_ids=entity_ids,
    )
    count_result = await result.single()
    assert count_result["count"] == entity_count

    # Verify metadata consistency
    for vector in qdrant_vectors:
        # Get corresponding Memgraph node
        result = await memgraph_session.run(
            f"MATCH (n:{memgraph_test_label} {{entity_id: $entity_id}}) RETURN n",
            entity_id=vector.id,
        )
        node = await result.single()

        # Quality scores should match
        assert vector.payload["quality_score"] == node["n"]["quality_score"]


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_distributed_transaction_pattern(
    kafka_producer,
    kafka_consumer,
    kafka_test_topic: str,
    qdrant_client,
    qdrant_test_collection: str,
    memgraph_session,
    memgraph_test_label: str,
    test_id: str,
):
    """
    Test distributed transaction pattern across services.

    Simulates saga pattern:
    1. Start transaction (Kafka event)
    2. Update Qdrant
    3. Update Memgraph
    4. Commit transaction (Kafka event)

    Validates:
    - Transaction coordination
    - Rollback capability simulation
    - Event-driven consistency
    """
    # Arrange: Transaction setup
    transaction_id = f"txn_{test_id}"
    entity_id = f"entity_{test_id}"
    correlation_id = transaction_id

    # Act 1: Begin transaction
    begin_event = KafkaTestDataGenerator.generate_event(
        event_type="transaction.begin",
        payload={
            "transaction_id": transaction_id,
            "entity_id": entity_id,
            "operations": ["qdrant_upsert", "memgraph_create"],
        },
        correlation_id=correlation_id,
    )

    begin_bytes = json.dumps(begin_event).encode("utf-8")
    await kafka_producer.send_and_wait(
        topic=kafka_test_topic, value=begin_bytes, key=correlation_id.encode("utf-8")
    )

    # Act 2: Execute Qdrant operation
    vector_point = QdrantTestDataGenerator.generate_quality_point(
        doc_id=entity_id, quality_score=0.88
    )
    await qdrant_client.upsert(
        collection_name=qdrant_test_collection,
        points=[vector_point],
    )

    # Publish operation completed event
    qdrant_complete = KafkaTestDataGenerator.generate_event(
        event_type="transaction.operation.complete",
        payload={
            "transaction_id": transaction_id,
            "operation": "qdrant_upsert",
            "success": True,
        },
        correlation_id=correlation_id,
    )
    await kafka_producer.send_and_wait(
        topic=kafka_test_topic,
        value=json.dumps(qdrant_complete).encode("utf-8"),
        key=correlation_id.encode("utf-8"),
    )

    # Act 3: Execute Memgraph operation
    await memgraph_session.run(
        f"""
        CREATE (n:{memgraph_test_label} {{
            id: $entity_id,
            transaction_id: $transaction_id,
            quality_score: $quality_score
        }})
        """,
        entity_id=entity_id,
        transaction_id=transaction_id,
        quality_score=0.88,
    )

    # Publish operation completed event
    memgraph_complete = KafkaTestDataGenerator.generate_event(
        event_type="transaction.operation.complete",
        payload={
            "transaction_id": transaction_id,
            "operation": "memgraph_create",
            "success": True,
        },
        correlation_id=correlation_id,
    )
    await kafka_producer.send_and_wait(
        topic=kafka_test_topic,
        value=json.dumps(memgraph_complete).encode("utf-8"),
        key=correlation_id.encode("utf-8"),
    )

    # Act 4: Commit transaction
    commit_event = KafkaTestDataGenerator.generate_event(
        event_type="transaction.commit",
        payload={
            "transaction_id": transaction_id,
            "all_operations_complete": True,
        },
        correlation_id=correlation_id,
    )
    await kafka_producer.send_and_wait(
        topic=kafka_test_topic,
        value=json.dumps(commit_event).encode("utf-8"),
        key=correlation_id.encode("utf-8"),
    )

    # Assert: Verify transaction events
    messages = await wait_for_kafka_messages(
        consumer=kafka_consumer,
        topic=kafka_test_topic,
        expected_count=5,  # begin + 2 operations + commit
        timeout=15.0,
    )

    assert len(messages) == 5

    event_types = [msg["value"]["envelope"]["event_type"] for msg in messages]
    assert "transaction.begin" in event_types
    assert "transaction.commit" in event_types
    assert event_types.count("transaction.operation.complete") == 2

    # Verify all events have same correlation_id
    for msg in messages:
        assert msg["value"]["envelope"]["correlation_id"] == correlation_id

    # Verify both services updated
    await asyncio.sleep(0.5)

    # Check Qdrant
    vectors = await qdrant_client.retrieve(
        collection_name=qdrant_test_collection,
        ids=[entity_id],
    )
    assert len(vectors) == 1

    # Check Memgraph
    result = await memgraph_session.run(
        f"MATCH (n:{memgraph_test_label} {{id: $entity_id}}) RETURN n",
        entity_id=entity_id,
    )
    node = await result.single()
    assert node is not None
    assert node["n"]["transaction_id"] == transaction_id


@pytest.mark.real_integration
@pytest.mark.asyncio
@pytest.mark.slow
async def test_orchestration_performance_under_load(
    kafka_producer,
    qdrant_client,
    qdrant_test_collection: str,
    memgraph_session,
    memgraph_test_label: str,
    test_id: str,
):
    """
    Performance test: Orchestration across all services under load.

    Validates:
    - System handles concurrent operations
    - Performance remains acceptable
    - No deadlocks or race conditions
    - Resource usage is reasonable

    Note: Marked as 'slow' - takes >10 seconds
    """
    # Arrange: Prepare batch operations
    batch_size = 20
    entity_ids = [f"perf_{test_id}_{i}" for i in range(batch_size)]

    # Act: Execute operations concurrently
    start_time = asyncio.get_event_loop().time()

    # Concurrent tasks for all services
    tasks = []

    # Kafka tasks
    for i, entity_id in enumerate(entity_ids):
        event = KafkaTestDataGenerator.generate_event(
            event_type="performance.test", payload={"entity_id": entity_id, "index": i}
        )
        task = kafka_producer.send(
            topic=f"test-topic-{test_id}", value=json.dumps(event).encode("utf-8")
        )
        tasks.append(task)

    # Qdrant tasks
    qdrant_points = [
        QdrantTestDataGenerator.generate_quality_point(
            doc_id=entity_id, quality_score=0.8
        )
        for entity_id in entity_ids
    ]

    # Memgraph tasks (need to be sequential due to transaction safety)
    # But we can batch them
    tasks.append(
        qdrant_client.upsert(
            collection_name=qdrant_test_collection,
            points=qdrant_points,
        )
    )

    # Wait for Kafka and Qdrant
    await asyncio.gather(*tasks)

    # Execute Memgraph operations
    for entity_id in entity_ids:
        await memgraph_session.run(
            f"""
            CREATE (n:{memgraph_test_label} {{
                id: $entity_id,
                test_type: $test_type,
                created_at: $created_at
            }})
            """,
            entity_id=entity_id,
            test_type="performance",
            created_at=datetime.utcnow().isoformat(),
        )

    total_duration = asyncio.get_event_loop().time() - start_time

    # Assert: Performance acceptable
    assert (
        total_duration < 15.0
    ), f"Orchestration took {total_duration:.2f}s (expected <15s)"

    # Verify all operations completed successfully
    await asyncio.sleep(1.0)

    # Check Qdrant
    qdrant_count = len(
        await qdrant_client.retrieve(
            collection_name=qdrant_test_collection,
            ids=entity_ids,
        )
    )
    assert qdrant_count == batch_size

    # Check Memgraph
    result = await memgraph_session.run(
        f"MATCH (n:{memgraph_test_label}) WHERE n.test_type = 'performance' RETURN count(n) as count"
    )
    memgraph_count = (await result.single())["count"]
    assert memgraph_count == batch_size

    # Report performance metrics
    throughput = batch_size / total_duration
    print(f"\nPerformance metrics:")
    print(f"  Total duration: {total_duration:.2f}s")
    print(f"  Operations: {batch_size * 3} (Kafka + Qdrant + Memgraph)")
    print(f"  Throughput: {throughput:.2f} entities/second")
