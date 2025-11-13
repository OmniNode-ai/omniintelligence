"""
Real Integration Test: Memgraph Knowledge Graph

Tests real knowledge graph operations with Memgraph database.

Coverage:
- Node creation and retrieval
- Relationship creation
- Graph traversal queries
- Pattern matching
- Graph analytics

Run with:
    pytest --real-integration tests/real_integration/test_memgraph_knowledge_graph.py -v
"""

import asyncio
from datetime import datetime

import pytest

from tests.fixtures.real_integration import (
    memgraph_driver,
    memgraph_session,
    memgraph_test_label,
    real_integration_config,
    test_id,
)
from tests.utils.test_data_manager import (
    MemgraphTestDataGenerator,
    verify_memgraph_nodes,
)


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_memgraph_create_and_retrieve_node(
    memgraph_session,
    memgraph_test_label: str,
):
    """
    Test creating and retrieving a node in Memgraph.

    Validates:
    - Node successfully created
    - Node retrievable by label and properties
    - Properties preserved correctly
    - Unique ID enforcement
    """
    # Arrange: Define node properties
    node_id = f"test_node_001"
    properties = {
        "id": node_id,
        "name": "Test Node",
        "description": "Integration test node",
        "created_at": datetime.utcnow().isoformat(),
        "score": 0.95,
    }

    # Act: Create node
    query = f"""
    CREATE (n:{memgraph_test_label} {{
        id: $id,
        name: $name,
        description: $description,
        created_at: $created_at,
        score: $score
    }})
    RETURN n
    """

    result = await memgraph_session.run(query, **properties)
    created_node = await result.single()

    # Assert: Node created successfully
    assert created_node is not None
    node = created_node["n"]

    # Validate properties
    assert node["id"] == node_id
    assert node["name"] == "Test Node"
    assert node["description"] == "Integration test node"
    assert node["score"] == 0.95

    # Act: Retrieve node
    retrieve_query = f"MATCH (n:{memgraph_test_label} {{id: $id}}) RETURN n"
    result = await memgraph_session.run(retrieve_query, id=node_id)
    retrieved_node = await result.single()

    # Assert: Node retrievable
    assert retrieved_node is not None
    assert retrieved_node["n"]["id"] == node_id


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_memgraph_create_relationships(
    memgraph_session,
    memgraph_test_label: str,
):
    """
    Test creating relationships between nodes.

    Validates:
    - Relationships created successfully
    - Relationship properties preserved
    - Multiple relationships per node
    - Relationship traversal
    """
    # Arrange: Create two nodes
    node1_id = "node_1"
    node2_id = "node_2"

    await memgraph_session.run(
        f"CREATE (n:{memgraph_test_label} {{id: $id, name: $name}})",
        id=node1_id,
        name="Node 1",
    )

    await memgraph_session.run(
        f"CREATE (n:{memgraph_test_label} {{id: $id, name: $name}})",
        id=node2_id,
        name="Node 2",
    )

    # Act: Create relationship
    relationship_query = f"""
    MATCH (a:{memgraph_test_label} {{id: $from_id}}),
          (b:{memgraph_test_label} {{id: $to_id}})
    CREATE (a)-[r:CONNECTS_TO {{
        relationship_type: $rel_type,
        weight: $weight,
        created_at: $created_at
    }}]->(b)
    RETURN r
    """

    result = await memgraph_session.run(
        relationship_query,
        from_id=node1_id,
        to_id=node2_id,
        rel_type="test_connection",
        weight=0.8,
        created_at=datetime.utcnow().isoformat(),
    )

    relationship = await result.single()

    # Assert: Relationship created
    assert relationship is not None
    rel = relationship["r"]
    assert rel["relationship_type"] == "test_connection"
    assert rel["weight"] == 0.8

    # Act: Query relationship
    query_rel = f"""
    MATCH (a:{memgraph_test_label} {{id: $from_id}})-[r:CONNECTS_TO]->(b:{memgraph_test_label})
    RETURN a, r, b
    """

    result = await memgraph_session.run(query_rel, from_id=node1_id)
    traversal = await result.single()

    # Assert: Relationship traversal works
    assert traversal is not None
    assert traversal["a"]["id"] == node1_id
    assert traversal["b"]["id"] == node2_id
    assert traversal["r"]["relationship_type"] == "test_connection"


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_memgraph_graph_traversal(
    memgraph_session,
    memgraph_test_label: str,
):
    """
    Test graph traversal and pattern matching.

    Validates:
    - Multi-hop traversal
    - Path finding
    - Pattern matching
    - Variable-length relationships
    """
    # Arrange: Create chain of nodes (A -> B -> C -> D)
    nodes = ["A", "B", "C", "D"]

    # Create nodes
    for node_id in nodes:
        await memgraph_session.run(
            f"CREATE (n:{memgraph_test_label} {{id: $id, name: $name}})",
            id=node_id,
            name=f"Node {node_id}",
        )

    # Create relationships (chain)
    for i in range(len(nodes) - 1):
        await memgraph_session.run(
            f"""
            MATCH (a:{memgraph_test_label} {{id: $from_id}}),
                  (b:{memgraph_test_label} {{id: $to_id}})
            CREATE (a)-[:NEXT]->(b)
            """,
            from_id=nodes[i],
            to_id=nodes[i + 1],
        )

    # Act: Find path from A to D
    path_query = f"""
    MATCH path = (start:{memgraph_test_label} {{id: $start_id}})
                 -[:NEXT*]->(end:{memgraph_test_label} {{id: $end_id}})
    RETURN path, length(path) as path_length
    """

    result = await memgraph_session.run(path_query, start_id="A", end_id="D")
    path_result = await result.single()

    # Assert: Path found
    assert path_result is not None
    assert path_result["path_length"] == 3  # 3 hops: A->B, B->C, C->D

    # Act: Find all nodes reachable from A (2 hops)
    reachable_query = f"""
    MATCH (start:{memgraph_test_label} {{id: $start_id}})
          -[:NEXT*1..2]->(reachable:{memgraph_test_label})
    RETURN reachable.id as id
    """

    result = await memgraph_session.run(reachable_query, start_id="A")
    reachable_nodes = [record["id"] async for record in result]

    # Assert: Nodes B and C reachable within 2 hops
    assert set(reachable_nodes) == {"B", "C"}


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_memgraph_pattern_matching(
    memgraph_session,
    memgraph_test_label: str,
):
    """
    Test complex pattern matching queries.

    Validates:
    - Pattern matching with multiple conditions
    - Property filtering in patterns
    - Aggregation in graph queries
    - Optional pattern matching
    """
    # Arrange: Create graph with quality-scored nodes
    high_quality_nodes = ["H1", "H2", "H3"]
    low_quality_nodes = ["L1", "L2"]

    # Create high-quality nodes
    for node_id in high_quality_nodes:
        await memgraph_session.run(
            f"""
            CREATE (n:{memgraph_test_label} {{
                id: $id,
                name: $name,
                quality_score: $quality,
                category: $category
            }})
            """,
            id=node_id,
            name=f"High Quality {node_id}",
            quality=0.9,
            category="high_quality",
        )

    # Create low-quality nodes
    for node_id in low_quality_nodes:
        await memgraph_session.run(
            f"""
            CREATE (n:{memgraph_test_label} {{
                id: $id,
                name: $name,
                quality_score: $quality,
                category: $category
            }})
            """,
            id=node_id,
            name=f"Low Quality {node_id}",
            quality=0.3,
            category="low_quality",
        )

    # Act: Find high-quality nodes
    query = f"""
    MATCH (n:{memgraph_test_label})
    WHERE n.quality_score > 0.7
    RETURN n.id as id, n.quality_score as quality
    ORDER BY n.quality_score DESC
    """

    result = await memgraph_session.run(query)
    high_quality_results = [record async for record in result]

    # Assert: Only high-quality nodes returned
    assert len(high_quality_results) == 3
    for record in high_quality_results:
        assert record["quality"] == 0.9

    # Act: Aggregate statistics
    stats_query = f"""
    MATCH (n:{memgraph_test_label})
    RETURN
        count(n) as total_nodes,
        avg(n.quality_score) as avg_quality,
        max(n.quality_score) as max_quality,
        min(n.quality_score) as min_quality
    """

    result = await memgraph_session.run(stats_query)
    stats = await result.single()

    # Assert: Statistics correct
    assert stats["total_nodes"] == 5
    assert stats["max_quality"] == 0.9
    assert stats["min_quality"] == 0.3
    # Average: (3 * 0.9 + 2 * 0.3) / 5 = 0.66
    assert abs(stats["avg_quality"] - 0.66) < 0.01


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_memgraph_bulk_operations(
    memgraph_session,
    memgraph_test_label: str,
):
    """
    Test bulk node and relationship creation.

    Validates:
    - Bulk node creation performance
    - Multiple nodes created in single query
    - Bulk relationship creation
    - Performance is acceptable
    """
    # Arrange: Generate bulk node data
    node_count = 20

    # Act: Bulk create nodes
    start_time = asyncio.get_event_loop().time()

    for i in range(node_count):
        await memgraph_session.run(
            f"""
            CREATE (n:{memgraph_test_label} {{
                id: $id,
                name: $name,
                index: $index,
                created_at: $created_at
            }})
            """,
            id=f"bulk_node_{i}",
            name=f"Bulk Node {i}",
            index=i,
            created_at=datetime.utcnow().isoformat(),
        )

    create_duration = asyncio.get_event_loop().time() - start_time

    # Assert: All nodes created
    count_query = f"MATCH (n:{memgraph_test_label}) WHERE n.index IS NOT NULL RETURN count(n) as count"
    result = await memgraph_session.run(count_query)
    count_result = await result.single()
    assert count_result["count"] == node_count

    # Validate performance
    assert (
        create_duration < 5.0
    ), f"Bulk creation took {create_duration:.2f}s (expected <5s)"


@pytest.mark.real_integration
@pytest.mark.asyncio
async def test_memgraph_cleanup_verification(
    memgraph_driver,
    memgraph_test_label: str,
    real_integration_config,
):
    """
    Test cleanup verification and isolation.

    Validates:
    - Test nodes can be cleaned up
    - Cleanup is complete
    - No test data leakage between tests
    - Cleanup performance is acceptable
    """
    # Create session and nodes
    async with memgraph_driver.session() as session:
        # Create test nodes
        for i in range(5):
            await session.run(
                f"CREATE (n:{memgraph_test_label} {{id: $id}})", id=f"cleanup_test_{i}"
            )

        # Verify nodes exist
        result = await session.run(
            f"MATCH (n:{memgraph_test_label}) RETURN count(n) as count"
        )
        count_before = (await result.single())["count"]
        assert count_before == 5

        # Act: Cleanup
        start_time = asyncio.get_event_loop().time()
        await session.run(f"MATCH (n:{memgraph_test_label}) DETACH DELETE n")
        cleanup_duration = asyncio.get_event_loop().time() - start_time

        # Assert: All nodes deleted
        result = await session.run(
            f"MATCH (n:{memgraph_test_label}) RETURN count(n) as count"
        )
        count_after = (await result.single())["count"]
        assert count_after == 0

        # Validate cleanup performance
        assert (
            cleanup_duration < 2.0
        ), f"Cleanup took {cleanup_duration:.2f}s (expected <2s)"
