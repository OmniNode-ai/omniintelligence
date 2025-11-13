"""
Test fixtures for intelligence document data.

Provides realistic intelligence document structures for testing,
covering various formats and edge cases.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest


@pytest.fixture
def sample_mcp_intelligence_document() -> dict[str, Any]:
    """Sample intelligence document in MCP format."""
    # Use recent timestamp (within last 24 hours)
    now = datetime.now(UTC)
    recent_time = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    return {
        "id": "doc-mcp-001",
        "document_type": "intelligence",
        "tags": ["intelligence", "pre-push", "rag-indexing"],
        "created_at": recent_time,
        "updated_at": recent_time,
        "author": "Enhanced Intelligence Hook",
        "content": {
            "metadata": {
                "repository": "Archon",
                "commit": "abc123def456",
                "author": "john.doe",
                "timestamp": recent_time,
                "change_type": "feature",
                "branch": "main",
            },
            "code_changes_analysis": {
                "changed_files": [
                    "src/server/api_routes/intelligence_api.py",
                    "src/server/data/intelligence_data_access.py",
                    "tests/test_intelligence_integration.py",
                ],
                "analysis": "Added new intelligence API endpoints and data access layer",
            },
            "cross_repository_correlation": {
                "temporal_correlations": [
                    {
                        "repository": "Related-Service",
                        "commit": "def456abc789",
                        "time_window": "6h",
                        "correlation_strength": "high",
                        "shared_patterns": ["API changes", "error handling"],
                    },
                    {
                        "repository": "Frontend-App",
                        "commit": "789ghi012jkl",
                        "time_window": "24h",
                        "correlation_strength": "medium",
                        "shared_patterns": ["authentication", "user management"],
                    },
                ],
                "semantic_correlations": [
                    {
                        "repository": "Auth-Service",
                        "commit": "mno345pqr678",
                        "shared_keywords": "authentication user token security",
                        "semantic_similarity": 0.85,
                    }
                ],
                "breaking_changes": [
                    {
                        "type": "API_CHANGE",
                        "severity": "HIGH",
                        "description": "Modified endpoint response structure in /api/intelligence/documents",
                        "files_affected": ["src/server/api_routes/intelligence_api.py"],
                    }
                ],
            },
            "security_analysis": {
                "patterns_detected": ["JWT token validation", "Input sanitization"],
                "risk_level": "LOW",
                "secure_patterns": 2,
                "vulnerabilities": [],
            },
            "quality_metrics": {
                "code_coverage": 95.2,
                "complexity_score": "LOW",
                "maintainability_index": 87.5,
            },
        },
    }


@pytest.fixture
def sample_legacy_intelligence_document() -> dict[str, Any]:
    """Sample intelligence document in legacy git hook format."""
    # Use recent timestamp (within last 24 hours)
    now = datetime.now(UTC)
    recent_time = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")

    return {
        "id": "doc-legacy-001",
        "document_type": "intelligence",
        "tags": ["intelligence-initialization", "quality-assessment"],
        "created_at": recent_time,
        "updated_at": recent_time,
        "author": "Git Hook Intelligence v2.1",
        "content": {
            "diff_analysis": {
                "total_changes": 5,
                "added_lines": 142,
                "removed_lines": 38,
                "modified_files": [
                    "python/src/server/services/intelligence_service.py",
                    "python/src/server/data/intelligence_data_access.py",
                    "python/tests/test_intelligence_data_access.py",
                ],
            },
            "correlation_analysis": {
                "temporal_correlations": [
                    {
                        "repository": "Data-Pipeline",
                        "commit_sha": "stu901vwx234",
                        "time_diff_hours": 4.5,
                        "correlation_strength": 0.9,
                        "correlation_type": "temporal",
                    }
                ],
                "semantic_correlations": [
                    {
                        "repository": "Analytics-Service",
                        "commit_sha": "yz234abc567",
                        "semantic_similarity": 0.72,
                        "common_keywords": [
                            "data",
                            "analysis",
                            "intelligence",
                            "correlation",
                        ],
                    }
                ],
                "breaking_changes": [],
            },
            "security_analysis": {
                "patterns_detected": ["SQL parameterization", "XSS prevention"],
                "risk_level": "MEDIUM",
                "secure_patterns": 3,
                "vulnerability_scan": "clean",
            },
            "repository_info": {
                "repository": "Archon-Legacy",
                "commit": "stu901vwx234",
                "files_changed": 3,
                "branch": "development",
            },
        },
    }


@pytest.fixture
def sample_project_intelligence_document() -> dict[str, Any]:
    """Sample intelligence document from project quality assessment."""
    # Use recent timestamp (within last 24 hours)
    now = datetime.now(UTC)
    recent_time = (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z")

    return {
        "id": "doc-project-001",
        "document_type": "spec",
        "tags": ["quality-assessment", "intelligence-update"],
        "created_at": recent_time,
        "updated_at": recent_time,
        "author": "Quality Assessment Bot",
        "content": {
            "quality_baseline": {
                "code_quality_metrics": {
                    "anti_patterns_found": 0,
                    "architectural_compliance": "High",
                    "type_safety": "Strong",
                    "test_coverage": 91.5,
                    "cyclomatic_complexity": 2.3,
                }
            },
            "repository_info": {
                "repository": "Test-Project",
                "commit": "def890ghi123",
                "files_changed": 2,
                "last_analysis": recent_time,
            },
            "changed_files": ["src/core/validators.py", "tests/test_validators.py"],
            "performance_metrics": {
                "response_time_p95": 145.2,
                "memory_usage_mb": 32.1,
                "cpu_utilization": 12.8,
            },
        },
    }


@pytest.fixture
def sample_malformed_document() -> dict[str, Any]:
    """Sample malformed intelligence document for error handling tests."""
    # Use recent timestamp (within last 24 hours)
    now = datetime.now(UTC)
    recent_time = (now - timedelta(hours=4)).isoformat().replace("+00:00", "Z")

    return {
        "id": "doc-malformed-001",
        "document_type": "intelligence",
        "tags": ["intelligence"],
        "created_at": recent_time,
        "content": {
            # Missing metadata
            "correlation_analysis": {
                "temporal_correlations": [
                    {
                        # Missing repository and commit_sha
                        "time_diff_hours": 2.0
                        # Missing correlation_strength
                    }
                ]
            },
            "diff_analysis": {
                # Missing required fields
                "modified_files": []
            },
        },
    }


@pytest.fixture
def sample_empty_document() -> dict[str, Any]:
    """Sample empty intelligence document."""
    # Use recent timestamp (within last 24 hours)
    now = datetime.now(UTC)
    recent_time = (now - timedelta(hours=5)).isoformat().replace("+00:00", "Z")

    return {
        "id": "doc-empty-001",
        "document_type": "intelligence",
        "tags": ["intelligence"],
        "created_at": recent_time,
        "content": {},
    }


@pytest.fixture
def sample_project_with_intelligence_docs() -> dict[str, Any]:
    """Sample project containing multiple intelligence documents."""
    # Use recent timestamps (within last 24 hours)
    now = datetime.now(UTC)
    recent_time_1 = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    recent_time_2 = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    recent_time_3 = (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z")

    return {
        "id": "proj-001",
        "title": "Test Intelligence Project",
        "created_at": recent_time_3,
        "updated_at": recent_time_1,
        "docs": [
            {
                "id": "doc-001",
                "tags": ["intelligence", "pre-push"],
                "created_at": recent_time_1,
                "content": {
                    "metadata": {
                        "repository": "Main-Repo",
                        "commit": "abc123",
                        "timestamp": recent_time_1,
                    },
                    "diff_analysis": {
                        "total_changes": 3,
                        "added_lines": 50,
                        "removed_lines": 10,
                        "modified_files": ["main.py", "utils.py", "tests.py"],
                    },
                },
            },
            {
                "id": "doc-002",
                "tags": ["documentation"],  # Should be filtered out
                "created_at": recent_time_2,
                "content": {"description": "User guide documentation"},
            },
            {
                "id": "doc-003",
                "tags": ["quality-assessment"],
                "created_at": recent_time_3,
                "content": {
                    "quality_baseline": {
                        "code_quality_metrics": {
                            "anti_patterns_found": 1,
                            "architectural_compliance": "Medium",
                            "type_safety": "Moderate",
                        }
                    },
                    "repository_info": {
                        "repository": "Quality-Repo",
                        "commit": "def456",
                    },
                },
            },
        ],
    }


@pytest.fixture
def correlation_algorithm_test_data() -> list[dict[str, Any]]:
    """Test data specifically for correlation algorithm testing."""
    return [
        {
            "name": "High Temporal Correlation",
            "documents": [
                {
                    "repository": "Service-A",
                    "timestamp": "2023-01-01T12:00:00Z",
                    "commit": "commit-a-1",
                    "changes": ["api.py", "models.py"],
                },
                {
                    "repository": "Service-B",
                    "timestamp": "2023-01-01T12:30:00Z",  # 30 minutes later
                    "commit": "commit-b-1",
                    "changes": ["client.py", "tests.py"],
                },
            ],
            "expected_correlation": 0.9,
            "expected_time_diff": 0.5,
        },
        {
            "name": "Medium Semantic Correlation",
            "documents": [
                {
                    "repository": "Auth-Service",
                    "keywords": ["authentication", "user", "token", "login"],
                    "commit": "auth-commit-1",
                },
                {
                    "repository": "User-Service",
                    "keywords": ["user", "profile", "authentication", "session"],
                    "commit": "user-commit-1",
                },
            ],
            "expected_semantic_similarity": 0.6,
            "common_keywords": ["authentication", "user"],
        },
        {
            "name": "Breaking Change Detection",
            "changes": [
                {
                    "type": "API_SIGNATURE_CHANGE",
                    "file": "api/endpoints.py",
                    "old_signature": "def get_user(id: int)",
                    "new_signature": "def get_user(user_id: str, include_profile: bool = False)",
                    "severity": "HIGH",
                },
                {
                    "type": "DATABASE_SCHEMA_CHANGE",
                    "file": "models/user.py",
                    "description": "Added required field 'email_verified'",
                    "severity": "MEDIUM",
                },
            ],
            "expected_breaking_changes": 2,
        },
    ]


@pytest.fixture
def performance_test_dataset() -> dict[str, Any]:
    """Large dataset for performance testing."""
    documents = []
    repositories = ["Repo-A", "Repo-B", "Repo-C", "Repo-D", "Repo-E"]

    base_time = datetime.now(UTC)

    for i in range(1000):  # 1000 documents for performance testing
        repo = repositories[i % len(repositories)]
        timestamp = base_time - timedelta(hours=i * 0.1)

        doc = {
            "id": f"perf-doc-{i:04d}",
            "document_type": "intelligence",
            "tags": ["intelligence", "pre-push"],
            "created_at": timestamp.isoformat(),
            "content": {
                "metadata": {
                    "repository": repo,
                    "commit": f"commit-{i:04d}",
                    "timestamp": timestamp.isoformat(),
                },
                "diff_analysis": {
                    "total_changes": (i % 10) + 1,
                    "added_lines": (i % 100) + 10,
                    "removed_lines": (i % 50) + 1,
                    "modified_files": [f"file-{j}.py" for j in range((i % 5) + 1)],
                },
                "correlation_analysis": {
                    "temporal_correlations": (
                        [
                            {
                                "repository": repositories[(i + 1) % len(repositories)],
                                "commit_sha": f"corr-commit-{i:04d}",
                                "time_diff_hours": float((i % 24) + 1),
                                "correlation_strength": 0.5 + (i % 50) / 100.0,
                            }
                        ]
                        if i % 3 == 0
                        else []
                    )  # Only some documents have correlations
                },
            },
        }
        documents.append(doc)

    return {
        "documents": documents,
        "expected_total_changes": 1000,
        "expected_repositories": len(repositories),
        "expected_correlations": len([i for i in range(1000) if i % 3 == 0]),
    }


@pytest.fixture
def mock_database_responses() -> dict[str, Any]:
    """Mock database responses for testing."""
    return {
        "empty_response": {"data": []},
        "single_project_response": {
            "data": [
                {
                    "id": "proj-001",
                    "title": "Test Project",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T12:00:00Z",
                    "docs": [],
                }
            ]
        },
        "error_response": {
            "error": {
                "message": "Database connection failed",
                "code": "DB_CONNECTION_ERROR",
            }
        },
    }
