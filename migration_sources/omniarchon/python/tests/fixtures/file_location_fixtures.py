"""
Test fixtures for file location tests.

Provides reusable mock data for:
- Tree discovery results
- Intelligence generation results
- Stamping results
- Search queries
- Expected results
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest


class AttrDict(dict):
    """Dictionary subclass supporting both dict[key] and obj.attr access patterns.

    This hybrid approach enables:
    - Attribute access: result.tree_structure (for real bridge code)
    - Dictionary access: result["files"] (for test code)
    - Membership testing: "files" in result (for test code)
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{key}'"
            )

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{key}'"
            )


@pytest.fixture
def mock_tree_result() -> Dict[str, Any]:
    """Mock tree discovery result."""
    files = [
        "src/auth/jwt_handler_effect.py",
        "src/auth/user_authenticator_compute.py",
        "src/auth/session_manager_reducer.py",
        "src/api/endpoints_effect.py",
        "src/api/validators_compute.py",
        "src/api/rate_limiter_reducer.py",
        "src/database/connection_pool_effect.py",
        "src/database/query_builder_compute.py",
        "src/database/result_aggregator_reducer.py",
        "src/config/config_loader_effect.py",
        "src/config/env_validator_compute.py",
    ]

    return {
        "success": True,
        "files_tracked": 50,
        "files": files,  # Add files list
        "tree_structure": {
            "src/auth/": [
                "jwt_handler_effect.py",
                "user_authenticator_compute.py",
                "session_manager_reducer.py",
            ],
            "src/api/": [
                "endpoints_effect.py",
                "validators_compute.py",
                "rate_limiter_reducer.py",
            ],
            "src/database/": [
                "connection_pool_effect.py",
                "query_builder_compute.py",
                "result_aggregator_reducer.py",
            ],
            "src/config/": [
                "config_loader_effect.py",
                "env_validator_compute.py",
            ],
        },
        "processing_time_ms": 342,
    }


@pytest.fixture
def mock_intelligence_metadata() -> Dict[str, Any]:
    """Mock intelligence generation result for a single file."""
    return {
        "file_path": "/tmp/test-project/src/auth/jwt_handler_effect.py",
        "file_hash": "blake3_abc123def456",
        "quality_score": 0.87,
        "onex_compliance": 0.92,
        "onex_type": "effect",
        "semantic_intelligence": {
            "concepts": ["authentication", "jwt", "token", "security"],
            "themes": ["security", "api"],
            "domains": ["backend.auth"],
        },
        "pattern_intelligence": {
            "pattern_types": ["effect", "async"],
            "complexity": "medium",
        },
        "compliance": {
            "onex_compliant": True,
            "issues": [],
            "recommendations": ["Add error handling", "Improve documentation"],
        },
    }


@pytest.fixture
def mock_batch_intelligence() -> List[Dict[str, Any]]:
    """Mock batch intelligence generation results."""
    files = [
        {
            "path": "src/auth/jwt_handler_effect.py",
            "onex_type": "effect",
            "quality": 0.87,
            "concepts": ["authentication", "jwt", "token"],
        },
        {
            "path": "src/auth/user_authenticator_compute.py",
            "onex_type": "compute",
            "quality": 0.91,
            "concepts": ["authentication", "validation", "user"],
        },
        {
            "path": "src/api/endpoints_effect.py",
            "onex_type": "effect",
            "quality": 0.84,
            "concepts": ["api", "endpoint", "request", "response"],
        },
        {
            "path": "src/database/connection_pool_effect.py",
            "onex_type": "effect",
            "quality": 0.79,
            "concepts": ["database", "connection", "pool", "persistence"],
        },
        {
            "path": "src/config/config_loader_effect.py",
            "onex_type": "effect",
            "quality": 0.73,
            "concepts": ["configuration", "settings", "environment"],
        },
    ]

    return [
        {
            "file_path": f"/tmp/test-project/{f['path']}",
            "file_hash": f"blake3_{i:06d}",
            "quality_score": f["quality"],
            "onex_compliance": min(1.0, f["quality"] + 0.05),
            "onex_type": f["onex_type"],
            "semantic_intelligence": {
                "concepts": f["concepts"],
                "themes": ["backend"],
                "domains": [f["path"].split("/")[1]],
            },
            "pattern_intelligence": {
                "pattern_types": [f["onex_type"]],
                "complexity": "medium",
            },
        }
        for i, f in enumerate(files, start=1)
    ]


@pytest.fixture
def mock_stamp_result() -> Dict[str, Any]:
    """Mock stamping result."""
    return {
        "success": True,
        "file_hash": "blake3_abc123def456",
        "metadata": {
            "absolute_path": "/tmp/test-project/src/auth/jwt_handler_effect.py",
            "relative_path": "src/auth/jwt_handler_effect.py",
            "project_name": "test-project",
            "quality_score": 0.87,
            "onex_type": "effect",
            "concepts": ["authentication", "jwt", "token", "security"],
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@pytest.fixture
def mock_batch_stamp_result() -> Dict[str, Any]:
    """Mock batch stamping result."""
    return {
        "success": True,
        "successful_stamps": 50,
        "failed_stamps": 0,
        "stamps": [
            {
                "file_hash": f"blake3_{i:06d}",
                "status": "success",
            }
            for i in range(1, 51)
        ],
        "duration_ms": 2340,
    }


@pytest.fixture
def mock_qdrant_index_result() -> Dict[str, Any]:
    """Mock Qdrant indexing result."""
    return {
        "success": True,
        "indexed": 50,
        "collection": "archon_vectors",
        "duration_ms": 1250,
    }


@pytest.fixture
def mock_memgraph_index_result() -> Dict[str, Any]:
    """Mock Memgraph indexing result."""
    return {
        "success": True,
        "nodes_created": 50,
        "relationships_created": 150,
        "duration_ms": 890,
    }


@pytest.fixture
def mock_search_query() -> str:
    """Mock search query."""
    return "authentication module with JWT"


@pytest.fixture
def mock_search_results() -> List[Dict[str, Any]]:
    """Mock search results."""
    return [
        {
            "file_path": "/tmp/test-project/src/auth/jwt_handler_effect.py",
            "relative_path": "src/auth/jwt_handler_effect.py",
            "project_name": "test-project",
            "confidence": 0.94,
            "quality_score": 0.87,
            "onex_type": "effect",
            "concepts": ["authentication", "jwt", "token", "security"],
            "themes": ["security", "api"],
            "why": "High semantic match for 'authentication' and 'JWT', ONEX Effect node with quality score 0.87",
        },
        {
            "file_path": "/tmp/test-project/src/auth/user_authenticator_compute.py",
            "relative_path": "src/auth/user_authenticator_compute.py",
            "project_name": "test-project",
            "confidence": 0.89,
            "quality_score": 0.91,
            "onex_type": "compute",
            "concepts": ["authentication", "validation", "user"],
            "themes": ["security"],
            "why": "Strong match for 'authentication', ONEX Compute node with high quality score",
        },
        {
            "file_path": "/tmp/test-project/src/auth/session_manager_reducer.py",
            "relative_path": "src/auth/session_manager_reducer.py",
            "project_name": "test-project",
            "confidence": 0.82,
            "quality_score": 0.75,
            "onex_type": "reducer",
            "concepts": ["authentication", "session", "state"],
            "themes": ["security"],
            "why": "Moderate match for 'authentication', session management related",
        },
    ]


@pytest.fixture
def mock_file_search_result() -> Dict[str, Any]:
    """Mock complete file search result."""
    return {
        "success": True,
        "results": [
            {
                "file_path": "/tmp/test-project/src/auth/jwt_handler_effect.py",
                "relative_path": "src/auth/jwt_handler_effect.py",
                "project_name": "test-project",
                "confidence": 0.94,
                "quality_score": 0.87,
                "onex_type": "effect",
                "concepts": ["authentication", "jwt", "token", "security"],
                "themes": ["security", "api"],
                "why": "High semantic match for 'authentication' and 'JWT', ONEX Effect node",
            },
        ],
        "query_time_ms": 342,
        "cache_hit": False,
        "total_results": 1,
    }


@pytest.fixture
def mock_project_index_result() -> Dict[str, Any]:
    """Mock project indexing result."""
    return {
        "success": True,
        "project_name": "test-project",
        "files_discovered": 50,
        "files_indexed": 50,
        "vector_indexed": 50,
        "graph_indexed": 50,
        "cache_warmed": True,
        "duration_ms": 15340,
        "errors": [],
        "warnings": [],
    }


@pytest.fixture
def mock_project_status() -> Dict[str, Any]:
    """Mock project indexing status."""
    return {
        "project_name": "test-project",
        "indexed": True,
        "file_count": 50,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "status": "indexed",
    }


@pytest.fixture
def sample_test_queries() -> List[Dict[str, Any]]:
    """Sample test queries with expected results."""
    return [
        {
            "query": "authentication module with JWT",
            "expected_file": "src/auth/jwt_handler_effect.py",
            "expected_concepts": ["authentication", "jwt", "token"],
            "min_confidence": 0.85,
        },
        {
            "query": "database connection pool",
            "expected_file": "src/database/connection_pool_effect.py",
            "expected_concepts": ["database", "connection", "pool"],
            "min_confidence": 0.80,
        },
        {
            "query": "api endpoint validation",
            "expected_file": "src/api/validators_compute.py",
            "expected_concepts": ["api", "validation"],
            "min_confidence": 0.75,
        },
        {
            "query": "configuration loader",
            "expected_file": "src/config/config_loader_effect.py",
            "expected_concepts": ["configuration", "settings"],
            "min_confidence": 0.70,
        },
    ]


@pytest.fixture
def mock_cache_key() -> str:
    """Mock Valkey cache key."""
    return "file_location:query:sha256_abc123"


@pytest.fixture
def mock_cached_result() -> Dict[str, Any]:
    """Mock cached search result."""
    return {
        "success": True,
        "results": [
            {
                "file_path": "/tmp/test-project/src/auth/jwt_handler_effect.py",
                "confidence": 0.94,
                "quality_score": 0.87,
                "onex_type": "effect",
                "concepts": ["authentication", "jwt"],
                "why": "Cached result from previous search",
            }
        ],
        "query_time_ms": 45,
        "cache_hit": True,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def mock_error_response() -> Dict[str, Any]:
    """Mock error response."""
    return {
        "success": False,
        "error": "Service unavailable",
        "error_code": "SERVICE_UNAVAILABLE",
        "details": "Failed to connect to OnexTree service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Performance test fixtures


@pytest.fixture
def performance_targets() -> Dict[str, float]:
    """Performance targets for benchmarking."""
    return {
        "indexing_50_files_max_sec": 30.0,
        "indexing_500_files_max_sec": 150.0,
        "indexing_1000_files_max_sec": 300.0,
        "cold_search_max_sec": 2.0,
        "warm_search_max_sec": 0.5,
        "cache_hit_rate_min": 0.40,
    }


@pytest.fixture
def mock_onex_tree_client():
    """Mock OnexTreeClient for testing.

    Returns mock client with objects supporting both attribute and dictionary access.
    Uses AttrDict to support both result.tree_structure and result["files"] patterns.
    """
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock()

    # Use AttrDict for hybrid dict/attribute access support
    # Supports: result.tree_structure (bridge code) AND "files" in result (test code)
    client.generate_tree = AsyncMock(
        return_value=AttrDict(
            success=True,
            files_tracked=50,
            tree_structure={"src/": ["file1.py", "file2.py"]},
            processing_time_ms=342,
        )
    )

    client.query_tree = AsyncMock(
        return_value=AttrDict(
            success=True,
            matches=["src/auth/jwt_handler.py"],
        )
    )

    # Support enrich_with_patterns method if needed
    client.enrich_with_patterns = AsyncMock(
        return_value=AttrDict(
            enriched_files=[],
            success=True,
        )
    )

    return client


@pytest.fixture
def mock_metadata_stamping_client():
    """Mock MetadataStampingClient for testing.

    Returns mock client with objects supporting both attribute and dictionary access.
    Uses AttrDict to support both obj.attr and obj["key"] patterns.
    """
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock()

    # Use AttrDict for hybrid dict/attribute access support
    client.generate_intelligence = AsyncMock(
        return_value=AttrDict(
            quality_score=0.87,
            onex_type="effect",
            concepts=["authentication", "jwt"],
        )
    )

    client.batch_stamp = AsyncMock(
        return_value=AttrDict(
            success=50,
            failed=0,
        )
    )

    return client


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for testing."""
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock()
    client.upsert = AsyncMock(return_value={"status": "success"})
    client.search = AsyncMock(
        return_value=[
            {
                "id": "file1",
                "score": 0.94,
                "payload": {
                    "file_path": "/tmp/test/file1.py",
                    "quality_score": 0.87,
                },
            }
        ]
    )

    return client


@pytest.fixture
def mock_memgraph_client():
    """Mock Memgraph client for testing."""
    from unittest.mock import MagicMock

    client = MagicMock()
    client.execute_query = MagicMock(return_value={"nodes_created": 50})

    return client


@pytest.fixture
def mock_valkey_client():
    """Mock Valkey (Redis) client for testing."""
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock()
    client.get = AsyncMock(return_value=None)  # Cache miss by default
    client.setex = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)

    return client
