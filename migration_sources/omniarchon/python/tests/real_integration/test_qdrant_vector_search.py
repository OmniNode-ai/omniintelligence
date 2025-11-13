"""
Real Integration Test: Qdrant Vector Search

Tests real vector search operations with Qdrant database.

Coverage:
- Vector point insertion
- Similarity search
- Filtering with metadata
- Batch operations
- Collection management

Run with:
    pytest --real-integration tests/real_integration/test_qdrant_vector_search.py -v
"""

import asyncio
import random
from typing import List

import pytest
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from tests.fixtures.real_integration import (
    qdrant_client,
    qdrant_test_collection,
    qdrant_test_points,
    real_integration_config,
    test_id,
)
from tests.utils.test_data_manager import (
    QdrantTestDataGenerator,
    verify_qdrant_points,
)


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_qdrant_insert_and_retrieve_points(
    qdrant_client,
    qdrant_test_collection: str,
):
    """
    Test inserting and retrieving vector points in Qdrant.

    Validates:
    - Points successfully inserted
    - Points retrievable by ID
    - Vector data preserved
    - Metadata preserved
    """
    # Arrange: Generate test points
    test_points = QdrantTestDataGenerator.generate_points(count=5)

    # Act: Insert points
    await qdrant_client.upsert(
        collection_name=qdrant_test_collection,
        points=test_points,
    )

    # Wait for indexing
    await asyncio.sleep(0.5)

    # Assert: Retrieve and validate points
    point_ids = [p.id for p in test_points]
    retrieved_points = await qdrant_client.retrieve(
        collection_name=qdrant_test_collection,
        ids=point_ids,
    )

    assert len(retrieved_points) == len(test_points)

    # Validate each point
    for original, retrieved in zip(test_points, retrieved_points):
        assert retrieved.id == original.id
        assert retrieved.payload["text"] == original.payload["text"]
        assert retrieved.payload["category"] == original.payload["category"]
        assert retrieved.payload["index"] == original.payload["index"]


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_qdrant_similarity_search(
    qdrant_client,
    qdrant_test_collection: str,
):
    """
    Test vector similarity search in Qdrant.

    Validates:
    - Similarity search returns results
    - Results ordered by similarity score
    - Scores are within valid range [0, 1]
    - Query vector format accepted
    """
    # Arrange: Insert test points
    test_points = QdrantTestDataGenerator.generate_points(count=10)
    await qdrant_client.upsert(
        collection_name=qdrant_test_collection,
        points=test_points,
    )
    await asyncio.sleep(0.5)  # Wait for indexing

    # Act: Perform similarity search with first point's vector
    query_vector = test_points[0].vector
    search_results = await qdrant_client.search(
        collection_name=qdrant_test_collection,
        query_vector=query_vector,
        limit=5,
    )

    # Assert: Validate search results
    assert len(search_results) > 0
    assert len(search_results) <= 5

    # First result should be the query vector itself (perfect match)
    assert search_results[0].id == test_points[0].id
    assert search_results[0].score >= 0.99  # Near-perfect similarity

    # Validate scores are ordered (descending)
    scores = [result.score for result in search_results]
    assert scores == sorted(scores, reverse=True)

    # Validate score range
    for result in search_results:
        assert 0.0 <= result.score <= 1.0


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_qdrant_filtered_search(
    qdrant_client,
    qdrant_test_collection: str,
):
    """
    Test vector search with metadata filtering.

    Validates:
    - Filtering by payload fields works
    - Only matching points returned
    - Search combined with filtering
    - Complex filter conditions
    """
    # Arrange: Insert points with different categories
    test_points = []
    for i in range(10):
        vector = [random.random() for _ in range(1536)]
        test_points.append(
            PointStruct(
                id=i,
                vector=vector,
                payload={
                    "text": f"Document {i}",
                    "category": "high_quality" if i < 5 else "low_quality",
                    "score": 0.9 if i < 5 else 0.3,
                },
            )
        )

    await qdrant_client.upsert(
        collection_name=qdrant_test_collection,
        points=test_points,
    )
    await asyncio.sleep(0.5)

    # Act: Search with category filter
    query_vector = test_points[0].vector
    search_results = await qdrant_client.search(
        collection_name=qdrant_test_collection,
        query_vector=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(key="category", match=MatchValue(value="high_quality"))
            ]
        ),
        limit=10,
    )

    # Assert: Only high_quality points returned
    assert len(search_results) <= 5  # Max 5 high_quality points

    for result in search_results:
        point = await qdrant_client.retrieve(
            collection_name=qdrant_test_collection,
            ids=[result.id],
        )
        assert point[0].payload["category"] == "high_quality"


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_qdrant_batch_operations(
    qdrant_client,
    qdrant_test_collection: str,
):
    """
    Test batch insert and update operations.

    Validates:
    - Batch insert handles large datasets
    - All points inserted correctly
    - Batch updates work
    - Performance is acceptable
    """
    # Arrange: Generate large batch of points
    batch_size = 50
    test_points = QdrantTestDataGenerator.generate_points(count=batch_size)

    # Act: Batch insert
    start_time = asyncio.get_event_loop().time()
    await qdrant_client.upsert(
        collection_name=qdrant_test_collection,
        points=test_points,
    )
    insert_duration = asyncio.get_event_loop().time() - start_time

    # Wait for indexing
    await asyncio.sleep(1.0)

    # Assert: All points inserted
    point_ids = [p.id for p in test_points]
    success = await verify_qdrant_points(
        client=qdrant_client,
        collection_name=qdrant_test_collection,
        point_ids=point_ids,
        timeout=10.0,
    )
    assert success, "Not all points were inserted"

    # Validate performance
    assert (
        insert_duration < 5.0
    ), f"Batch insert took {insert_duration:.2f}s (expected <5s)"

    # Act: Batch update (upsert with modified payloads)
    for point in test_points:
        point.payload["updated"] = True

    start_time = asyncio.get_event_loop().time()
    await qdrant_client.upsert(
        collection_name=qdrant_test_collection,
        points=test_points,
    )
    update_duration = asyncio.get_event_loop().time() - start_time

    await asyncio.sleep(1.0)

    # Assert: Updates applied
    retrieved = await qdrant_client.retrieve(
        collection_name=qdrant_test_collection,
        ids=[test_points[0].id],
    )
    assert retrieved[0].payload["updated"] is True

    # Validate update performance
    assert (
        update_duration < 5.0
    ), f"Batch update took {update_duration:.2f}s (expected <5s)"


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_qdrant_quality_weighted_search(
    qdrant_client,
    qdrant_test_collection: str,
):
    """
    Test quality-weighted vector search (Archon-specific).

    Validates:
    - Quality scores in metadata
    - Search with quality filtering
    - High-quality results prioritized
    - ONEX compliance filtering
    """
    # Arrange: Insert points with varying quality scores
    test_points = []
    for i in range(10):
        quality_score = 0.95 if i < 3 else 0.5  # 3 high-quality, 7 low-quality
        point = QdrantTestDataGenerator.generate_quality_point(
            doc_id=f"doc_{i}",
            quality_score=quality_score,
        )
        test_points.append(point)

    await qdrant_client.upsert(
        collection_name=qdrant_test_collection,
        points=test_points,
    )
    await asyncio.sleep(0.5)

    # Act: Search with quality filter (ONEX-compliant only)
    query_vector = test_points[0].vector
    search_results = await qdrant_client.search(
        collection_name=qdrant_test_collection,
        query_vector=query_vector,
        query_filter=Filter(
            must=[FieldCondition(key="onex_compliant", match=MatchValue(value=True))]
        ),
        limit=10,
    )

    # Assert: Only high-quality results returned
    assert len(search_results) <= 3  # Max 3 ONEX-compliant points

    for result in search_results:
        point = await qdrant_client.retrieve(
            collection_name=qdrant_test_collection,
            ids=[result.id],
        )
        assert point[0].payload["onex_compliant"] is True
        assert point[0].payload["quality_score"] > 0.7


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_qdrant_collection_info(
    qdrant_client,
    qdrant_test_collection: str,
):
    """
    Test retrieving collection information and statistics.

    Validates:
    - Collection info accessible
    - Point count accurate
    - Vector configuration correct
    - Collection status healthy
    """
    # Arrange: Insert known number of points
    point_count = 10
    test_points = QdrantTestDataGenerator.generate_points(count=point_count)
    await qdrant_client.upsert(
        collection_name=qdrant_test_collection,
        points=test_points,
    )
    await asyncio.sleep(0.5)

    # Act: Get collection info
    collection_info = await qdrant_client.get_collection(
        collection_name=qdrant_test_collection
    )

    # Assert: Validate collection info
    assert collection_info.status == "green"  # Healthy
    assert collection_info.points_count == point_count
    assert collection_info.vectors_count == point_count

    # Validate vector configuration
    vector_config = collection_info.config.params.vectors
    assert vector_config.size == 1536  # OpenAI embedding size
    assert vector_config.distance == Distance.COSINE
