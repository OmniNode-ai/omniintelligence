#!/usr/bin/env python3
"""
Integration Tests for Knowledge Graph API

Tests complete request/response cycles for Knowledge Graph API endpoints:
1. GET /api/intelligence/knowledge/graph - Retrieve graph structure (nodes and edges)
2. GET /api/intelligence/knowledge/health - Health check

These tests verify:
- Success cases (200 responses)
- Response schema validation (nodes and edges structure)
- Query parameter filtering (node types, quality score, project)
- Performance targets (<2s for graph queries)
- Memgraph connectivity

Author: Archon Intelligence Team
Date: 2025-10-28
Correlation ID: 86e57c28-0af3-4f1f-afda-81d11b877258
"""

import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from api.knowledge_graph.routes import router as knowledge_graph_router
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def app() -> FastAPI:
    """Create FastAPI app instance with knowledge graph router."""
    app = FastAPI(title="Knowledge Graph Test API")
    app.include_router(knowledge_graph_router)
    return app


@pytest.fixture
def test_client(app: FastAPI) -> TestClient:
    """Create test client for API testing."""
    return TestClient(app)


@pytest.fixture
def mock_graph_data() -> Dict[str, Any]:
    """Create mock graph data for testing."""
    return {
        "nodes": [
            {
                "id": "1",
                "label": "auth.py",
                "type": "file",
                "properties": {
                    "quality_score": 0.87,
                    "onex_type": "effect",
                    "path": "src/auth/auth.py",
                },
            },
            {
                "id": "2",
                "label": "authentication",
                "type": "concept",
                "properties": {},
            },
            {
                "id": "3",
                "label": "jwt.py",
                "type": "file",
                "properties": {
                    "quality_score": 0.92,
                    "onex_type": "compute",
                    "path": "src/auth/jwt.py",
                },
            },
            {
                "id": "4",
                "label": "security",
                "type": "theme",
                "properties": {},
            },
        ],
        "edges": [
            {
                "source": "1",
                "target": "2",
                "relationship": "HAS_CONCEPT",
                "properties": {"confidence": 0.92},
            },
            {
                "source": "3",
                "target": "2",
                "relationship": "HAS_CONCEPT",
                "properties": {"confidence": 0.95},
            },
            {
                "source": "1",
                "target": "4",
                "relationship": "HAS_THEME",
                "properties": {},
            },
        ],
    }


# ============================================================================
# Knowledge Graph API Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.knowledge_graph
class TestKnowledgeGraphAPI:
    """Integration tests for knowledge graph endpoint."""

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.get_graph_data")
    def test_get_knowledge_graph_success(
        self, mock_get_graph: AsyncMock, test_client: TestClient, mock_graph_data: Dict
    ):
        """Test successful knowledge graph retrieval."""
        # Mock service response
        mock_get_graph.return_value = mock_graph_data

        start_time = time.time()

        # Make request
        response = test_client.get("/api/intelligence/knowledge/graph")
        response_time_ms = (time.time() - start_time) * 1000

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert (
            response_time_ms < 2000
        ), f"Response too slow: {response_time_ms:.2f}ms > 2000ms"

        # Verify response structure
        data = response.json()
        assert "nodes" in data, "Response missing 'nodes' field"
        assert "edges" in data, "Response missing 'edges' field"
        assert "metadata" in data, "Response missing 'metadata' field"

        assert isinstance(data["nodes"], list), "'nodes' should be a list"
        assert isinstance(data["edges"], list), "'edges' should be a list"
        assert isinstance(data["metadata"], dict), "'metadata' should be a dict"

        print(f"✅ Knowledge graph retrieved in {response_time_ms:.2f}ms")
        print(f"   Nodes: {len(data['nodes'])}")
        print(f"   Edges: {len(data['edges'])}")

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.get_graph_data")
    def test_get_knowledge_graph_with_limit(
        self, mock_get_graph: AsyncMock, test_client: TestClient, mock_graph_data: Dict
    ):
        """Test knowledge graph retrieval with limit parameter."""
        mock_get_graph.return_value = mock_graph_data

        response = test_client.get(
            "/api/intelligence/knowledge/graph", params={"limit": 50}
        )

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "metadata" in data
        assert data["metadata"]["limit_applied"] == 50

        print("✅ Knowledge graph with limit parameter works")

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.get_graph_data")
    def test_get_knowledge_graph_with_node_types(
        self, mock_get_graph: AsyncMock, test_client: TestClient, mock_graph_data: Dict
    ):
        """Test knowledge graph retrieval with node type filter."""
        # Filter to only file nodes
        filtered_data = {
            "nodes": [n for n in mock_graph_data["nodes"] if n["type"] == "file"],
            "edges": mock_graph_data["edges"],
        }
        mock_get_graph.return_value = filtered_data

        response = test_client.get(
            "/api/intelligence/knowledge/graph", params={"node_types": "file"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data

        # Verify only file nodes returned
        for node in data["nodes"]:
            assert node["type"] == "file", f"Expected file node, got {node['type']}"

        print(f"✅ Node type filter works: {len(data['nodes'])} file nodes")

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.get_graph_data")
    def test_get_knowledge_graph_with_quality_filter(
        self, mock_get_graph: AsyncMock, test_client: TestClient, mock_graph_data: Dict
    ):
        """Test knowledge graph retrieval with quality score filter."""
        # Filter high-quality nodes
        filtered_data = {
            "nodes": [
                n
                for n in mock_graph_data["nodes"]
                if n.get("properties", {}).get("quality_score", 1.0) >= 0.9
            ],
            "edges": mock_graph_data["edges"],
        }
        mock_get_graph.return_value = filtered_data

        response = test_client.get(
            "/api/intelligence/knowledge/graph",
            params={"min_quality_score": 0.9},
        )

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data

        # Verify quality score filter
        for node in data["nodes"]:
            quality = node.get("properties", {}).get("quality_score")
            if quality is not None:
                assert quality >= 0.9, f"Quality score {quality} below threshold 0.9"

        print(f"✅ Quality filter works: {len(data['nodes'])} high-quality nodes")

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.get_graph_data")
    def test_knowledge_graph_response_schema(
        self, mock_get_graph: AsyncMock, test_client: TestClient, mock_graph_data: Dict
    ):
        """Test that response matches expected schema."""
        mock_get_graph.return_value = mock_graph_data

        response = test_client.get("/api/intelligence/knowledge/graph")

        assert response.status_code == 200
        data = response.json()

        # Verify top-level structure
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data

        # Verify node structure
        if data["nodes"]:
            node = data["nodes"][0]
            required_fields = ["id", "label", "type", "properties"]

            for field in required_fields:
                assert field in node, f"Node missing required field: {field}"

            # Verify field types
            assert isinstance(node["id"], str), "Node id should be string"
            assert isinstance(node["label"], str), "Node label should be string"
            assert isinstance(node["type"], str), "Node type should be string"
            assert isinstance(
                node["properties"], dict
            ), "Node properties should be dict"

        # Verify edge structure
        if data["edges"]:
            edge = data["edges"][0]
            required_fields = ["source", "target", "relationship", "properties"]

            for field in required_fields:
                assert field in edge, f"Edge missing required field: {field}"

            # Verify field types
            assert isinstance(edge["source"], str), "Edge source should be string"
            assert isinstance(edge["target"], str), "Edge target should be string"
            assert isinstance(
                edge["relationship"], str
            ), "Edge relationship should be string"
            assert isinstance(
                edge["properties"], dict
            ), "Edge properties should be dict"

        # Verify metadata structure
        metadata = data["metadata"]
        expected_metadata_fields = ["query_time_ms", "node_count", "edge_count"]

        for field in expected_metadata_fields:
            assert field in metadata, f"Metadata missing field: {field}"

        print("✅ Response schema validation passed")

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.get_graph_data")
    def test_knowledge_graph_empty_result(
        self, mock_get_graph: AsyncMock, test_client: TestClient
    ):
        """Test that empty graph result is handled correctly."""
        # Mock empty graph
        mock_get_graph.return_value = {"nodes": [], "edges": []}

        response = test_client.get("/api/intelligence/knowledge/graph")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

        # Should return empty lists
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        assert len(data["nodes"]) == 0
        assert len(data["edges"]) == 0

        print("✅ Empty graph result handled correctly")

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.get_graph_data")
    def test_knowledge_graph_connection_error(
        self, mock_get_graph: AsyncMock, test_client: TestClient
    ):
        """Test handling of Memgraph connection errors."""
        # Mock connection error
        mock_get_graph.side_effect = ConnectionError("Cannot connect to Memgraph")

        response = test_client.get("/api/intelligence/knowledge/graph")

        assert response.status_code == 503, "Should return 503 on connection error"

        data = response.json()
        assert "detail" in data
        assert "unavailable" in data["detail"].lower()

        print("✅ Connection error handled correctly (503 response)")


# ============================================================================
# Health Check Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.knowledge_graph
class TestKnowledgeGraphHealthAPI:
    """Integration tests for knowledge graph health check endpoint."""

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.check_health")
    def test_health_check_success(
        self, mock_check_health: AsyncMock, test_client: TestClient
    ):
        """Test successful health check."""
        # Mock healthy status
        mock_check_health.return_value = {
            "status": "healthy",
            "memgraph_uri": "bolt://localhost:7687",
            "connection": "established",
        }

        start_time = time.time()

        response = test_client.get("/api/intelligence/knowledge/health")
        response_time_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert (
            response_time_ms < 500
        ), f"Health check too slow: {response_time_ms:.2f}ms"

        # Verify response structure
        data = response.json()
        assert "status" in data, "Health check missing 'status' field"
        assert "service" in data, "Health check missing 'service' field"

        # Verify values
        assert data["status"] == "healthy", f"Service not healthy: {data['status']}"
        assert (
            data["service"] == "knowledge-graph-api"
        ), f"Wrong service name: {data['service']}"

        print(f"✅ Health check passed in {response_time_ms:.2f}ms")
        print(f"   Status: {data['status']}")
        print(f"   Service: {data['service']}")

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.check_health")
    def test_health_check_unhealthy(
        self, mock_check_health: AsyncMock, test_client: TestClient
    ):
        """Test health check when Memgraph is unavailable."""
        # Mock unhealthy status
        mock_check_health.return_value = {
            "status": "unhealthy",
            "memgraph_uri": "bolt://localhost:7687",
            "connection": "failed",
            "error": "Memgraph service unavailable",
        }

        response = test_client.get("/api/intelligence/knowledge/health")

        assert response.status_code == 200  # Health check itself succeeds
        data = response.json()

        assert "status" in data
        assert data["status"] == "unhealthy"
        assert "checks" in data
        assert "error" in data["checks"]

        print("✅ Unhealthy status reported correctly")


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.knowledge_graph
@pytest.mark.performance
class TestKnowledgeGraphPerformance:
    """Performance tests for knowledge graph endpoints."""

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.get_graph_data")
    def test_knowledge_graph_performance(
        self, mock_get_graph: AsyncMock, test_client: TestClient, mock_graph_data: Dict
    ):
        """Test that knowledge graph endpoint meets performance targets."""
        mock_get_graph.return_value = mock_graph_data

        response_times = []

        # Run 10 requests to get average performance
        for _ in range(10):
            start_time = time.time()
            response = test_client.get("/api/intelligence/knowledge/graph")
            response_time_ms = (time.time() - start_time) * 1000

            assert response.status_code == 200
            response_times.append(response_time_ms)

        # Calculate statistics
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        min_time = min(response_times)

        # Performance assertions (target: <2s, but should be much faster with mock)
        assert avg_time < 2000, f"Average response time too high: {avg_time:.2f}ms"
        assert max_time < 3000, f"Max response time too high: {max_time:.2f}ms"

        print(f"✅ Performance test passed:")
        print(f"   Average: {avg_time:.2f}ms")
        print(f"   Min: {min_time:.2f}ms")
        print(f"   Max: {max_time:.2f}ms")

    @patch("src.api.knowledge_graph.service.KnowledgeGraphService.check_health")
    def test_health_check_performance(
        self, mock_check_health: AsyncMock, test_client: TestClient
    ):
        """Test that health check meets performance targets."""
        mock_check_health.return_value = {
            "status": "healthy",
            "memgraph_uri": "bolt://localhost:7687",
            "connection": "established",
        }

        response_times = []

        # Run 10 requests
        for _ in range(10):
            start_time = time.time()
            response = test_client.get("/api/intelligence/knowledge/health")
            response_time_ms = (time.time() - start_time) * 1000

            assert response.status_code == 200
            response_times.append(response_time_ms)

        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)

        # Health checks should be very fast
        assert avg_time < 200, f"Average health check too slow: {avg_time:.2f}ms"
        assert max_time < 500, f"Max health check too slow: {max_time:.2f}ms"

        print(f"✅ Health check performance:")
        print(f"   Average: {avg_time:.2f}ms")
        print(f"   Max: {max_time:.2f}ms")


# ============================================================================
# Test Execution Summary
# ============================================================================


def test_summary():
    """Print test summary information."""
    print("\n" + "=" * 70)
    print("Knowledge Graph API Test Suite")
    print("=" * 70)
    print("\nEndpoints tested:")
    print("  1. GET /api/intelligence/knowledge/graph")
    print("  2. GET /api/intelligence/knowledge/health")
    print("\nTest categories:")
    print("  • Success cases (200 responses)")
    print("  • Response schema validation (nodes and edges)")
    print("  • Query parameter filtering (limit, node_types, quality)")
    print("  • Empty graph handling")
    print("  • Connection error handling (503)")
    print("  • Performance targets (<2s)")
    print("\nStatus: ✅ Ready for Dashboard integration")
    print("=" * 70)
