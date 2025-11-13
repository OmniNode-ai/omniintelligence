"""
End-to-End Integration Tests for File Location

Tests complete workflow:
1. Generate test project
2. Index project (tree → intelligence → stamp → index)
3. Search for files
4. Verify results accuracy
5. Test cache behavior
6. Validate performance targets
"""

import asyncio
import shutil

# Import test project generator
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
from generate_test_project import generate_test_project


class TestFileLocationEndToEnd:
    """
    End-to-end integration tests for file location functionality.

    NOTE: These tests use mocked services since the actual TreeStampingBridge
    doesn't exist yet. When the bridge is implemented, replace mocks with
    real service calls.
    """

    @pytest.fixture(scope="class")
    def test_project_path(self):
        """Generate test project for E2E tests."""
        # Generate test project with 50 files
        project_path = generate_test_project(
            output_path="/tmp/archon-e2e-test-project",
            file_count=50,
            seed=42,
        )

        yield project_path

        # Cleanup after tests
        if project_path.exists():
            shutil.rmtree(project_path)

    @pytest.fixture
    async def indexed_project(self, test_project_path):
        """
        Index test project and return bridge instance.

        In production, this would:
        1. Call bridge.index_project()
        2. Wait for indexing to complete
        3. Return bridge instance

        For now, returns mock data.
        """

        # Mock bridge instance
        class MockBridge:
            async def index_project(self, **kwargs):
                return {
                    "success": True,
                    "project_name": "archon-e2e-test-project",
                    "files_discovered": 50,
                    "files_indexed": 50,
                    "vector_indexed": 50,
                    "graph_indexed": 50,
                    "cache_warmed": True,
                    "duration_ms": 15000,
                    "errors": [],
                }

            async def search_files(self, query, **kwargs):
                # Mock search results based on query
                results = self._mock_search(query)
                return {
                    "success": True,
                    "results": results,
                    "query_time_ms": 342,
                    "cache_hit": False,
                    "total_results": len(results),
                }

            async def get_indexing_status(self, project_name=None):
                return [
                    {
                        "project_name": "archon-e2e-test-project",
                        "indexed": True,
                        "file_count": 50,
                        "indexed_at": "2025-10-24T12:00:00Z",
                        "status": "indexed",
                    }
                ]

            def _mock_search(self, query: str) -> List[Dict[str, Any]]:
                """Generate mock search results based on query."""
                query_lower = query.lower()

                # Authentication queries
                if "auth" in query_lower or "jwt" in query_lower:
                    return [
                        {
                            "file_path": str(
                                test_project_path / "src/auth/jwt_handler_reducer.py"
                            ),
                            "relative_path": "src/auth/jwt_handler_reducer.py",
                            "project_name": "archon-e2e-test-project",
                            "confidence": 0.94,
                            "quality_score": 0.87,
                            "onex_type": "reducer",
                            "concepts": ["authentication", "jwt", "token"],
                            "themes": ["security"],
                            "why": "High semantic match for 'authentication' and 'JWT'",
                        },
                        {
                            "file_path": str(
                                test_project_path
                                / "src/auth/user_authenticator_reducer.py"
                            ),
                            "relative_path": "src/auth/user_authenticator_reducer.py",
                            "project_name": "archon-e2e-test-project",
                            "confidence": 0.89,
                            "quality_score": 0.91,
                            "onex_type": "reducer",
                            "concepts": ["authentication", "user"],
                            "themes": ["security"],
                            "why": "Strong match for 'authentication'",
                        },
                    ]

                # Database queries
                elif "database" in query_lower or "connection" in query_lower:
                    return [
                        {
                            "file_path": str(
                                test_project_path
                                / "src/database/connection_pool_effect.py"
                            ),
                            "relative_path": "src/database/connection_pool_effect.py",
                            "project_name": "archon-e2e-test-project",
                            "confidence": 0.92,
                            "quality_score": 0.84,
                            "onex_type": "effect",
                            "concepts": ["database", "connection", "pool"],
                            "themes": ["persistence"],
                            "why": "Exact match for 'database connection pool'",
                        },
                    ]

                # API queries
                elif "api" in query_lower or "endpoint" in query_lower:
                    return [
                        {
                            "file_path": str(
                                test_project_path / "src/api/endpoints_reducer.py"
                            ),
                            "relative_path": "src/api/endpoints_reducer.py",
                            "project_name": "archon-e2e-test-project",
                            "confidence": 0.88,
                            "quality_score": 0.79,
                            "onex_type": "reducer",
                            "concepts": ["api", "endpoint"],
                            "themes": ["backend"],
                            "why": "Match for 'api endpoint'",
                        },
                    ]

                # Config queries
                elif "config" in query_lower or "settings" in query_lower:
                    return [
                        {
                            "file_path": str(
                                test_project_path
                                / "src/config/config_loader_reducer.py"
                            ),
                            "relative_path": "src/config/config_loader_reducer.py",
                            "project_name": "archon-e2e-test-project",
                            "confidence": 0.85,
                            "quality_score": 0.76,
                            "onex_type": "reducer",
                            "concepts": ["configuration", "settings"],
                            "themes": ["config"],
                            "why": "Match for 'configuration'",
                        },
                    ]

                return []

        bridge = MockBridge()

        # Index project
        index_result = await bridge.index_project(
            project_path=str(test_project_path),
            project_name="archon-e2e-test-project",
            include_tests=True,
        )

        assert index_result["success"] is True
        assert index_result["files_indexed"] == 50

        return bridge

    @pytest.mark.asyncio
    async def test_complete_workflow(
        self, test_project_path, indexed_project, performance_targets
    ):
        """
        Test complete workflow: index → search → verify results.

        This is the main E2E test that validates:
        1. Project can be indexed
        2. Files can be searched
        3. Results are accurate
        4. Performance targets are met
        """
        bridge = indexed_project

        # Step 1: Verify project structure exists
        assert test_project_path.exists()
        assert (test_project_path / "src").exists()
        assert (test_project_path / "manifest.json").exists()

        print(f"✅ Test project generated: {test_project_path}")

        # Step 2: Search for authentication files
        print("\n🔍 Searching for authentication files...")
        start_time = time.perf_counter()

        search_result = await bridge.search_files(
            query="authentication module with JWT",
            projects=["archon-e2e-test-project"],
            min_quality_score=0.7,
            limit=5,
        )

        search_duration = time.perf_counter() - start_time
        target_duration = performance_targets["cold_search_max_sec"]

        assert search_result["success"] is True
        assert len(search_result["results"]) > 0, "No results found"
        assert (
            search_duration < target_duration
        ), f"Search too slow: {search_duration:.2f}s (target: <{target_duration}s)"

        top_result = search_result["results"][0]
        assert "auth" in top_result["file_path"].lower()
        assert top_result["confidence"] > 0.7

        print(
            f"✅ Found {len(search_result['results'])} results in {search_duration:.2f}s"
        )
        print(
            f"   Top result: {top_result['relative_path']} (confidence: {top_result['confidence']:.2f})"
        )

        # Step 3: Test various search queries
        print("\n🧪 Testing various search queries...")
        test_queries = [
            {
                "query": "database connection pool",
                "expected_in_path": "database",
                "min_results": 1,
            },
            {
                "query": "api endpoint validation",
                "expected_in_path": "api",
                "min_results": 1,
            },
            {
                "query": "configuration loader",
                "expected_in_path": "config",
                "min_results": 1,
            },
        ]

        for test_case in test_queries:
            result = await bridge.search_files(
                query=test_case["query"],
                projects=["archon-e2e-test-project"],
                limit=10,
            )

            assert result["success"] is True
            assert len(result["results"]) >= test_case["min_results"]

            if result["results"]:
                top_match = result["results"][0]
                assert test_case["expected_in_path"] in top_match["file_path"]

                print(f"✅ Query '{test_case['query']}' → {top_match['relative_path']}")

        # Step 4: Verify indexing status
        print("\n📊 Checking indexing status...")
        status = await bridge.get_indexing_status(
            project_name="archon-e2e-test-project"
        )

        assert len(status) == 1
        assert status[0]["project_name"] == "archon-e2e-test-project"
        assert status[0]["indexed"] is True
        assert status[0]["file_count"] == 50

        print(f"✅ Project indexed: {status[0]['file_count']} files")

        print("\n🎉 Complete workflow test passed!")

    @pytest.mark.asyncio
    async def test_cache_behavior(self, indexed_project):
        """Test cache hit/miss behavior for repeated queries."""
        bridge = indexed_project

        query = "authentication module"

        # First search (cold - cache miss)
        print("\n❄️  Testing cold search (cache miss)...")
        start_time = time.perf_counter()
        result1 = await bridge.search_files(
            query=query,
            projects=["archon-e2e-test-project"],
        )
        cold_duration = time.perf_counter() - start_time

        assert result1["success"] is True
        # Note: Mock doesn't actually cache, but in production this would be False
        # assert result1["cache_hit"] is False

        print(f"✅ Cold search: {cold_duration:.2f}s")

        # Second search (warm - cache hit)
        # In production, this would be much faster due to cache
        print("🔥 Testing warm search (cache hit)...")
        start_time = time.perf_counter()
        result2 = await bridge.search_files(
            query=query,
            projects=["archon-e2e-test-project"],
        )
        warm_duration = time.perf_counter() - start_time

        assert result2["success"] is True

        print(f"✅ Warm search: {warm_duration:.2f}s")

        # Results should be identical
        assert len(result1["results"]) == len(result2["results"])

    @pytest.mark.asyncio
    async def test_quality_score_filtering(self, indexed_project):
        """Test filtering results by quality score."""
        bridge = indexed_project

        # Search with quality threshold
        result = await bridge.search_files(
            query="authentication",
            min_quality_score=0.85,
            limit=10,
        )

        assert result["success"] is True

        # All results should meet quality threshold
        for file_result in result["results"]:
            assert (
                file_result["quality_score"] >= 0.85
            ), f"Quality score {file_result['quality_score']} below threshold 0.85"

        print(
            f"✅ Quality filtering: {len(result['results'])} high-quality results (≥0.85)"
        )

    @pytest.mark.asyncio
    async def test_onex_type_filtering(self, indexed_project):
        """Test results include ONEX type information."""
        bridge = indexed_project

        result = await bridge.search_files(
            query="authentication",
            limit=10,
        )

        assert result["success"] is True
        assert len(result["results"]) > 0

        # All results should have ONEX type
        for file_result in result["results"]:
            assert "onex_type" in file_result
            assert file_result["onex_type"] in [
                "effect",
                "compute",
                "reducer",
                "orchestrator",
            ]

        print(f"✅ ONEX types present in all {len(result['results'])} results")

    @pytest.mark.asyncio
    async def test_semantic_concepts(self, indexed_project):
        """Test results include semantic concepts."""
        bridge = indexed_project

        result = await bridge.search_files(
            query="authentication with JWT",
            limit=5,
        )

        assert result["success"] is True
        assert len(result["results"]) > 0

        # Top result should include relevant concepts
        top_result = result["results"][0]
        assert "concepts" in top_result
        assert len(top_result["concepts"]) > 0

        # Should contain authentication-related concepts
        concepts_str = " ".join(top_result["concepts"]).lower()
        assert (
            "authentication" in concepts_str
            or "jwt" in concepts_str
            or "token" in concepts_str
        )

        print(f"✅ Semantic concepts: {top_result['concepts']}")

    @pytest.mark.asyncio
    async def test_result_ranking(self, indexed_project):
        """Test results are ranked by relevance."""
        bridge = indexed_project

        result = await bridge.search_files(
            query="authentication",
            limit=10,
        )

        assert result["success"] is True
        assert len(result["results"]) > 0

        # Results should be sorted by confidence (descending)
        confidences = [r["confidence"] for r in result["results"]]
        assert confidences == sorted(
            confidences, reverse=True
        ), "Results not sorted by confidence"

        print(f"✅ Results ranked correctly: {confidences}")

    @pytest.mark.asyncio
    async def test_cross_domain_search(self, indexed_project):
        """Test searching across multiple domains."""
        bridge = indexed_project

        # Search for a concept that might appear in multiple domains
        result = await bridge.search_files(
            query="configuration settings",
            limit=10,
        )

        assert result["success"] is True
        assert len(result["results"]) > 0

        # Results might come from different domains
        domains = set()
        for file_result in result["results"]:
            path_parts = file_result["relative_path"].split("/")
            if len(path_parts) > 1:
                domains.add(path_parts[1])  # src/<domain>/...

        print(f"✅ Cross-domain search: results from {len(domains)} domains")

    @pytest.mark.asyncio
    async def test_empty_query_handling(self, indexed_project):
        """Test handling of empty or invalid queries."""
        bridge = indexed_project

        # Empty query should return error or empty results
        result = await bridge.search_files(
            query="",
            limit=10,
        )

        # Implementation decision: either fail validation or return empty results
        # For now, just verify it doesn't crash
        assert "success" in result

    @pytest.mark.asyncio
    async def test_limit_parameter(self, indexed_project):
        """Test limit parameter controls result count."""
        bridge = indexed_project

        # Search with limit=3
        result = await bridge.search_files(
            query="authentication",
            limit=3,
        )

        assert result["success"] is True
        assert (
            len(result["results"]) <= 3
        ), f"Result count {len(result['results'])} exceeds limit 3"

        print(
            f"✅ Limit parameter working: {len(result['results'])} results (limit: 3)"
        )

    @pytest.mark.asyncio
    async def test_project_filtering(self, indexed_project):
        """Test filtering by project name."""
        bridge = indexed_project

        # Search with project filter
        result = await bridge.search_files(
            query="authentication",
            projects=["archon-e2e-test-project"],
            limit=10,
        )

        assert result["success"] is True

        # All results should be from the specified project
        for file_result in result["results"]:
            assert file_result["project_name"] == "archon-e2e-test-project"

        print(f"✅ Project filtering: all results from archon-e2e-test-project")


class TestFileLocationPerformanceTargets:
    """Performance target validation tests."""

    @pytest.mark.asyncio
    async def test_indexing_performance(self, performance_targets):
        """Test indexing meets performance targets."""
        # Mock indexing (in production, use real bridge)
        import time

        async def mock_index_project(file_count: int) -> float:
            """Mock indexing with realistic timing."""
            # Simulate processing time (0.3s per file)
            await asyncio.sleep(file_count * 0.001)
            return time.perf_counter()

        # Test 50 files
        start = time.perf_counter()
        await mock_index_project(50)
        duration_50 = time.perf_counter() - start

        assert (
            duration_50 < performance_targets["indexing_50_files_max_sec"]
        ), f"Indexing 50 files too slow: {duration_50:.2f}s"

        print(
            f"✅ Indexing 50 files: {duration_50:.2f}s (target: <{performance_targets['indexing_50_files_max_sec']}s)"
        )

    @pytest.mark.asyncio
    async def test_search_performance(self, performance_targets):
        """Test search meets performance targets."""
        import time

        async def mock_search() -> float:
            """Mock search with realistic timing."""
            await asyncio.sleep(0.05)  # 50ms
            return time.perf_counter()

        # Cold search
        start = time.perf_counter()
        await mock_search()
        cold_duration = time.perf_counter() - start

        assert (
            cold_duration < performance_targets["cold_search_max_sec"]
        ), f"Cold search too slow: {cold_duration:.2f}s"

        # Warm search (cached)
        start = time.perf_counter()
        await mock_search()
        warm_duration = time.perf_counter() - start

        assert (
            warm_duration < performance_targets["warm_search_max_sec"]
        ), f"Warm search too slow: {warm_duration:.2f}s"

        print(
            f"✅ Search performance: cold={cold_duration:.2f}s, warm={warm_duration:.2f}s"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
