"""
Test Data Manager

Provides utilities for managing test data across multiple services (Kafka, Qdrant, Memgraph).

Features:
- Centralized test data creation and cleanup
- Automatic resource tracking
- Bulk cleanup operations
- Test data generators
- Idempotent cleanup (safe to call multiple times)
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

logger = logging.getLogger(__name__)


@dataclass
class TestResource:
    """Track a test resource for cleanup."""

    resource_type: str  # "kafka_topic", "qdrant_collection", "memgraph_node"
    resource_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TestDataStats:
    """Statistics about test data creation."""

    total_resources: int = 0
    kafka_topics: int = 0
    qdrant_points: int = 0
    memgraph_nodes: int = 0
    cleanup_duration_ms: float = 0.0


class TestDataManager:
    """
    Manage test data lifecycle across multiple services.

    Automatically tracks created resources and cleans them up.
    Thread-safe and async-compatible.
    """

    def __init__(self, test_id: str):
        self.test_id = test_id
        self.resources: List[TestResource] = []
        self._lock = asyncio.Lock()

    def track_resource(
        self,
        resource_type: str,
        resource_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track a resource for cleanup."""
        resource = TestResource(
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {},
        )
        self.resources.append(resource)
        logger.debug(f"Tracking {resource_type}: {resource_id}")

    async def cleanup_all(
        self,
        kafka_producer: Optional[AIOKafkaProducer] = None,
        qdrant_client: Optional[AsyncQdrantClient] = None,
        memgraph_session: Optional[Any] = None,
        timeout: float = 10.0,
    ) -> TestDataStats:
        """
        Clean up all tracked resources.

        Args:
            kafka_producer: Kafka producer for topic cleanup (optional)
            qdrant_client: Qdrant client for collection cleanup (optional)
            memgraph_session: Memgraph session for node cleanup (optional)
            timeout: Timeout for cleanup operations

        Returns:
            Statistics about cleanup operation
        """
        start_time = datetime.utcnow()
        stats = TestDataStats()

        async with self._lock:
            # Group resources by type for batch cleanup
            kafka_resources = [
                r for r in self.resources if r.resource_type == "kafka_topic"
            ]
            qdrant_resources = [
                r for r in self.resources if r.resource_type == "qdrant_collection"
            ]
            memgraph_resources = [
                r for r in self.resources if r.resource_type == "memgraph_node"
            ]

            # Cleanup Kafka topics
            if kafka_resources and kafka_producer:
                stats.kafka_topics = await self._cleanup_kafka_topics(
                    kafka_resources, kafka_producer, timeout
                )

            # Cleanup Qdrant collections
            if qdrant_resources and qdrant_client:
                stats.qdrant_points = await self._cleanup_qdrant_collections(
                    qdrant_resources, qdrant_client, timeout
                )

            # Cleanup Memgraph nodes
            if memgraph_resources and memgraph_session:
                stats.memgraph_nodes = await self._cleanup_memgraph_nodes(
                    memgraph_resources, memgraph_session, timeout
                )

            stats.total_resources = len(self.resources)
            stats.cleanup_duration_ms = (
                datetime.utcnow() - start_time
            ).total_seconds() * 1000

            # Clear tracked resources
            self.resources.clear()

            logger.info(
                f"Cleanup completed: {stats.total_resources} resources in {stats.cleanup_duration_ms:.0f}ms"
            )

        return stats

    async def _cleanup_kafka_topics(
        self, resources: List[TestResource], producer: AIOKafkaProducer, timeout: float
    ) -> int:
        """Clean up Kafka topics (best effort - topics may not be deletable)."""
        # Note: Kafka topic deletion requires admin API
        # For now, we just log the topics that should be cleaned up
        # In production, you'd use AdminClient to delete topics
        for resource in resources:
            logger.debug(f"Kafka topic should be cleaned up: {resource.resource_id}")
        return len(resources)

    async def _cleanup_qdrant_collections(
        self, resources: List[TestResource], client: AsyncQdrantClient, timeout: float
    ) -> int:
        """Clean up Qdrant collections."""
        cleaned = 0
        for resource in resources:
            try:
                await asyncio.wait_for(
                    client.delete_collection(collection_name=resource.resource_id),
                    timeout=timeout,
                )
                cleaned += 1
                logger.debug(f"Cleaned up Qdrant collection: {resource.resource_id}")
            except Exception as e:
                logger.warning(
                    f"Failed to clean up Qdrant collection {resource.resource_id}: {e}"
                )
        return cleaned

    async def _cleanup_memgraph_nodes(
        self, resources: List[TestResource], session: Any, timeout: float
    ) -> int:
        """Clean up Memgraph nodes."""
        cleaned = 0
        for resource in resources:
            try:
                # Delete nodes by label
                await asyncio.wait_for(
                    session.run(f"MATCH (n:{resource.resource_id}) DETACH DELETE n"),
                    timeout=timeout,
                )
                cleaned += 1
                logger.debug(f"Cleaned up Memgraph nodes: {resource.resource_id}")
            except Exception as e:
                logger.warning(
                    f"Failed to clean up Memgraph nodes {resource.resource_id}: {e}"
                )
        return cleaned

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about tracked resources."""
        resource_counts = {}
        for resource in self.resources:
            resource_counts[resource.resource_type] = (
                resource_counts.get(resource.resource_type, 0) + 1
            )

        return {
            "test_id": self.test_id,
            "total_resources": len(self.resources),
            "resource_counts": resource_counts,
            "resources": [
                {
                    "type": r.resource_type,
                    "id": r.resource_id,
                    "created_at": r.created_at.isoformat(),
                    "metadata": r.metadata,
                }
                for r in self.resources
            ],
        }


# ============================================================================
# Test Data Generators
# ============================================================================


class KafkaTestDataGenerator:
    """Generate test data for Kafka."""

    @staticmethod
    def generate_event(
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a Kafka event with envelope."""
        return {
            "envelope": {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "correlation_id": correlation_id or str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0",
            },
            "payload": payload or {},
        }

    @staticmethod
    def generate_routing_decision_event(
        agent_name: str, confidence: float, user_request: str
    ) -> Dict[str, Any]:
        """Generate agent routing decision event."""
        return KafkaTestDataGenerator.generate_event(
            event_type="agent.routing.decision",
            payload={
                "user_request": user_request,
                "selected_agent": agent_name,
                "confidence_score": confidence,
                "routing_strategy": "test",
                "alternatives": [],
                "reasoning": "Test routing decision",
                "routing_time_ms": 50,
            },
        )

    @staticmethod
    def generate_transformation_event(
        from_agent: str, to_agent: str, success: bool = True
    ) -> Dict[str, Any]:
        """Generate agent transformation event."""
        return KafkaTestDataGenerator.generate_event(
            event_type="agent.transformation",
            payload={
                "source_agent": from_agent,
                "target_agent": to_agent,
                "transformation_reason": "Test transformation",
                "confidence_score": 0.95,
                "transformation_duration_ms": 100,
                "success": success,
            },
        )


class QdrantTestDataGenerator:
    """Generate test data for Qdrant."""

    @staticmethod
    def generate_points(
        count: int, dimension: int = 1536, start_id: int = 0
    ) -> List[PointStruct]:
        """Generate test vector points."""
        import random

        points = []
        for i in range(count):
            vector = [random.random() for _ in range(dimension)]
            points.append(
                PointStruct(
                    id=start_id + i,
                    vector=vector,
                    payload={
                        "text": f"Test document {i}",
                        "category": "test",
                        "index": i,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
            )
        return points

    @staticmethod
    def generate_quality_point(
        doc_id: str, quality_score: float, dimension: int = 1536
    ) -> PointStruct:
        """Generate quality-scored vector point."""
        import random

        vector = [random.random() for _ in range(dimension)]
        return PointStruct(
            id=doc_id,
            vector=vector,
            payload={
                "document_id": doc_id,
                "quality_score": quality_score,
                "complexity": random.choice(["low", "medium", "high"]),
                "onex_compliant": quality_score > 0.7,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


class MemgraphTestDataGenerator:
    """Generate test data for Memgraph."""

    @staticmethod
    def generate_create_node_query(label: str, properties: Dict[str, Any]) -> str:
        """Generate Cypher query to create node."""
        props_str = ", ".join([f"{key}: ${key}" for key in properties.keys()])
        return f"CREATE (n:{label} {{{props_str}}}) RETURN n"

    @staticmethod
    def generate_create_relationship_query(
        from_label: str,
        to_label: str,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate Cypher query to create relationship."""
        props = properties or {}
        props_str = (
            ", ".join([f"{key}: ${key}" for key in props.keys()]) if props else ""
        )

        return (
            f"MATCH (a:{from_label} {{id: $from_id}}), (b:{to_label} {{id: $to_id}}) "
            f"CREATE (a)-[r:{relationship_type} {{{props_str}}}]->(b) "
            f"RETURN r"
        )

    @staticmethod
    def generate_test_graph(test_id: str, node_count: int = 5) -> List[Dict[str, Any]]:
        """Generate test graph structure."""
        nodes = []
        for i in range(node_count):
            nodes.append(
                {
                    "label": f"TestNode_{test_id}",
                    "properties": {
                        "id": f"{test_id}_node_{i}",
                        "name": f"Test Node {i}",
                        "created_at": datetime.utcnow().isoformat(),
                    },
                }
            )
        return nodes


# ============================================================================
# Helper Functions
# ============================================================================


async def wait_for_kafka_messages(
    consumer: AIOKafkaConsumer, topic: str, expected_count: int, timeout: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Wait for specified number of messages on Kafka topic.

    Args:
        consumer: Kafka consumer
        topic: Topic to consume from
        expected_count: Number of messages to wait for
        timeout: Maximum time to wait

    Returns:
        List of consumed messages

    Raises:
        TimeoutError: If expected messages not received within timeout
    """
    consumer.subscribe([topic])
    messages = []

    try:
        async with asyncio.timeout(timeout):
            async for message in consumer:
                messages.append(
                    {
                        "topic": message.topic,
                        "partition": message.partition,
                        "offset": message.offset,
                        "key": message.key.decode("utf-8") if message.key else None,
                        "value": (
                            json.loads(message.value.decode("utf-8"))
                            if message.value
                            else None
                        ),
                        "timestamp": message.timestamp,
                    }
                )

                if len(messages) >= expected_count:
                    break
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"Expected {expected_count} messages, received {len(messages)} within {timeout}s"
        )

    return messages


async def verify_qdrant_points(
    client: AsyncQdrantClient,
    collection_name: str,
    point_ids: List[int],
    timeout: float = 5.0,
) -> bool:
    """
    Verify that points exist in Qdrant collection.

    Args:
        client: Qdrant client
        collection_name: Collection to check
        point_ids: List of point IDs to verify
        timeout: Operation timeout

    Returns:
        True if all points exist
    """
    try:
        points = await asyncio.wait_for(
            client.retrieve(
                collection_name=collection_name,
                ids=point_ids,
            ),
            timeout=timeout,
        )
        return len(points) == len(point_ids)
    except Exception as e:
        logger.error(f"Failed to verify Qdrant points: {e}")
        return False


async def verify_memgraph_nodes(
    session: Any, label: str, expected_count: int, timeout: float = 5.0
) -> bool:
    """
    Verify that expected number of nodes exist in Memgraph.

    Args:
        session: Memgraph session
        label: Node label to check
        expected_count: Expected number of nodes
        timeout: Operation timeout

    Returns:
        True if expected nodes exist
    """
    try:
        result = await asyncio.wait_for(
            session.run(f"MATCH (n:{label}) RETURN count(n) as count"), timeout=timeout
        )
        async for record in result:
            return record["count"] == expected_count
        return False
    except Exception as e:
        logger.error(f"Failed to verify Memgraph nodes: {e}")
        return False
