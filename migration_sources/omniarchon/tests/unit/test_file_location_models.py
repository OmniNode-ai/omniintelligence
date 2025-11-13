"""
Unit Tests for File Location Data Models

Tests all Pydantic models, validation logic, and schema definitions
for the Tree-Stamping Integration POC.

Coverage Target: 80%+
"""

import os
import sys
from datetime import datetime

import pytest
from pydantic import ValidationError

# Add service path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "../../services/intelligence/src")
)

from models.file_location import (
    ErrorResponse,
    FileMatch,
    FileMetadata,
    FileSearchRequest,
    FileSearchResult,
    IndexingProgress,
    ProjectIndexRequest,
    ProjectIndexResult,
    ProjectIndexStatus,
    ProjectStatusRequest,
)
from schemas import CacheSchemas, MemgraphSchemas, QdrantSchemas


class TestProjectIndexRequest:
    """Test ProjectIndexRequest model validation."""

    def test_valid_request(self):
        """Test valid project index request."""
        request = ProjectIndexRequest(
            project_path="/Volumes/PRO-G40/Code/omniarchon",
            project_name="omniarchon",
            include_tests=True,
            force_reindex=False,
        )
        assert request.project_path == "/Volumes/PRO-G40/Code/omniarchon"
        assert request.project_name == "omniarchon"
        assert request.include_tests is True
        assert request.force_reindex is False

    def test_defaults(self):
        """Test default values."""
        request = ProjectIndexRequest(project_path="/test/path", project_name="test")
        assert request.include_tests is True  # Default
        assert request.force_reindex is False  # Default

    def test_invalid_project_path_relative(self):
        """Test that relative paths are rejected."""
        with pytest.raises(ValidationError) as exc:
            ProjectIndexRequest(project_path="relative/path", project_name="test")
        assert "must be absolute path" in str(exc.value)

    def test_invalid_project_name_too_short(self):
        """Test that project names must be >= 2 characters."""
        with pytest.raises(ValidationError) as exc:
            ProjectIndexRequest(project_path="/valid/path", project_name="a")
        assert "at least 2 characters" in str(exc.value)

    def test_invalid_project_name_with_separator(self):
        """Test that project names cannot contain path separators."""
        with pytest.raises(ValidationError) as exc:
            ProjectIndexRequest(project_path="/valid/path", project_name="proj/ect")
        assert "cannot contain path separators" in str(exc.value)

    def test_whitespace_stripping(self):
        """Test that whitespace is stripped from strings."""
        request = ProjectIndexRequest(
            project_path=" /test/path ", project_name=" test "
        )
        assert request.project_path == "/test/path"
        assert request.project_name == "test"


class TestFileSearchRequest:
    """Test FileSearchRequest model validation."""

    def test_valid_search_request(self):
        """Test valid file search request."""
        request = FileSearchRequest(
            query="authentication module",
            projects=["omniarchon"],
            file_types=[".py", ".ts"],
            min_quality_score=0.7,
            limit=10,
        )
        assert request.query == "authentication module"
        assert request.projects == ["omniarchon"]
        assert request.file_types == [".py", ".ts"]
        assert request.min_quality_score == 0.7
        assert request.limit == 10

    def test_defaults(self):
        """Test default values."""
        request = FileSearchRequest(query="test")
        assert request.projects is None
        assert request.file_types is None
        assert request.min_quality_score == 0.0
        assert request.limit == 10

    def test_file_types_auto_correction(self):
        """Test that file types without dots get dots added."""
        request = FileSearchRequest(query="test", file_types=["py", ".ts", "md"])
        assert request.file_types == [".py", ".ts", ".md"]

    def test_quality_score_validation_too_high(self):
        """Test quality score must be <= 1.0."""
        with pytest.raises(ValidationError):
            FileSearchRequest(query="test", min_quality_score=1.5)

    def test_quality_score_validation_negative(self):
        """Test quality score must be >= 0.0."""
        with pytest.raises(ValidationError):
            FileSearchRequest(query="test", min_quality_score=-0.1)

    def test_limit_validation_too_low(self):
        """Test limit must be >= 1."""
        with pytest.raises(ValidationError):
            FileSearchRequest(query="test", limit=0)

    def test_limit_validation_too_high(self):
        """Test limit must be <= 100."""
        with pytest.raises(ValidationError):
            FileSearchRequest(query="test", limit=101)


class TestFileMatch:
    """Test FileMatch model validation."""

    def test_valid_file_match(self):
        """Test valid file match creation."""
        match = FileMatch(
            file_path="/path/to/file.py",
            relative_path="src/file.py",
            project_name="test",
            confidence=0.92,
            quality_score=0.87,
            onex_type="effect",
            concepts=["auth", "jwt"],
            themes=["security"],
            why="High semantic match",
        )
        assert match.file_path == "/path/to/file.py"
        assert match.confidence == 0.92
        assert match.quality_score == 0.87
        assert match.onex_type == "effect"

    def test_onex_type_normalization(self):
        """Test ONEX type is normalized to lowercase."""
        match = FileMatch(
            file_path="/path/to/file.py",
            relative_path="file.py",
            project_name="test",
            confidence=0.9,
            quality_score=0.8,
            onex_type="EFFECT",
            why="test",
        )
        assert match.onex_type == "effect"

    def test_invalid_onex_type(self):
        """Test invalid ONEX type is rejected."""
        with pytest.raises(ValidationError) as exc:
            FileMatch(
                file_path="/path/to/file.py",
                relative_path="file.py",
                project_name="test",
                confidence=0.9,
                quality_score=0.8,
                onex_type="invalid_type",
                why="test",
            )
        assert "onex_type must be one of" in str(exc.value)

    def test_default_lists(self):
        """Test default empty lists for concepts and themes."""
        match = FileMatch(
            file_path="/path/to/file.py",
            relative_path="file.py",
            project_name="test",
            confidence=0.9,
            quality_score=0.8,
            why="test",
        )
        assert match.concepts == []
        assert match.themes == []

    def test_serialization(self):
        """Test FileMatch serialization to dict."""
        match = FileMatch(
            file_path="/path/to/file.py",
            relative_path="file.py",
            project_name="test",
            confidence=0.92,
            quality_score=0.87,
            onex_type="effect",
            concepts=["auth"],
            themes=["security"],
            why="test",
        )
        data = match.model_dump()
        assert data["confidence"] == 0.92
        assert data["onex_type"] == "effect"

        # Test deserialization
        restored = FileMatch(**data)
        assert restored.file_path == match.file_path


class TestProjectIndexStatus:
    """Test ProjectIndexStatus model validation."""

    def test_valid_status(self):
        """Test valid project index status."""
        status = ProjectIndexStatus(
            project_name="omniarchon",
            indexed=True,
            file_count=1247,
            indexed_at=datetime.now(),
            last_updated=datetime.now(),
            status="indexed",
        )
        assert status.project_name == "omniarchon"
        assert status.status == "indexed"

    def test_status_validation(self):
        """Test status field validation."""
        valid_statuses = ["indexed", "in_progress", "failed", "unknown"]
        for valid_status in valid_statuses:
            status = ProjectIndexStatus(
                project_name="test", indexed=True, status=valid_status
            )
            assert status.status == valid_status

    def test_invalid_status(self):
        """Test invalid status is rejected."""
        with pytest.raises(ValidationError) as exc:
            ProjectIndexStatus(
                project_name="test", indexed=True, status="invalid_status"
            )
        assert "status must be one of" in str(exc.value)


class TestQdrantSchemas:
    """Test Qdrant schema definitions."""

    def test_file_locations_config(self):
        """Test Qdrant collection configuration."""
        config = QdrantSchemas.get_file_locations_config()
        assert config["collection_name"] == "archon_vectors"
        assert config["vectors_config"].size == 1536
        assert config["vectors_config"].distance.name == "COSINE"

    def test_payload_schema(self):
        """Test payload schema definition."""
        schema = QdrantSchemas.get_payload_schema()
        assert "absolute_path" in schema
        assert "quality_score" in schema
        assert schema["quality_score"] == "float"
        assert schema["concepts"] == "keyword[]"

    def test_example_payload_validation(self):
        """Test example payload passes validation."""
        example = QdrantSchemas.get_example_payload()
        assert QdrantSchemas.validate_payload(example) is True

    def test_invalid_payload_missing_fields(self):
        """Test invalid payload with missing required fields."""
        invalid = {"absolute_path": "/test"}
        assert QdrantSchemas.validate_payload(invalid) is False

    def test_invalid_payload_wrong_types(self):
        """Test invalid payload with wrong field types."""
        invalid = {
            "absolute_path": "/test",
            "relative_path": "test",
            "file_hash": "hash",
            "project_name": "test",
            "project_root": "/test",
            "file_type": ".py",
            "quality_score": "not_a_number",  # Wrong type
        }
        assert QdrantSchemas.validate_payload(invalid) is False


class TestMemgraphSchemas:
    """Test Memgraph schema definitions."""

    def test_node_creation_queries_defined(self):
        """Test node creation queries are defined."""
        assert "MERGE (p:Project" in MemgraphSchemas.CREATE_PROJECT_NODE
        assert "MERGE (f:File" in MemgraphSchemas.CREATE_FILE_NODE
        assert "MERGE (c:Concept" in MemgraphSchemas.CREATE_CONCEPT_NODE

    def test_relationship_queries_defined(self):
        """Test relationship creation queries are defined."""
        assert "CONTAINS" in MemgraphSchemas.CREATE_CONTAINS_RELATIONSHIP
        assert "HAS_CONCEPT" in MemgraphSchemas.CREATE_HAS_CONCEPT_RELATIONSHIP

    def test_query_patterns_defined(self):
        """Test common query patterns are defined."""
        assert "MATCH" in MemgraphSchemas.FIND_FILES_BY_PROJECT
        assert "MATCH" in MemgraphSchemas.FIND_FILES_BY_CONCEPT

    def test_node_type_validation(self):
        """Test node type validation."""
        assert MemgraphSchemas.validate_node_type("File") is True
        assert MemgraphSchemas.validate_node_type("Project") is True
        assert MemgraphSchemas.validate_node_type("InvalidNode") is False

    def test_relationship_type_validation(self):
        """Test relationship type validation."""
        assert MemgraphSchemas.validate_relationship_type("CONTAINS") is True
        assert MemgraphSchemas.validate_relationship_type("HAS_CONCEPT") is True
        assert MemgraphSchemas.validate_relationship_type("INVALID") is False

    def test_example_parameters(self):
        """Test example parameters are provided."""
        params = MemgraphSchemas.get_example_parameters()
        assert "create_project" in params
        assert "create_file" in params
        assert params["create_project"]["name"] == "omniarchon"


class TestCacheSchemas:
    """Test Valkey cache schema definitions."""

    def test_search_result_key_generation(self):
        """Test search result cache key generation."""
        query = "test query"
        key = CacheSchemas.search_result_key(query)
        assert key.startswith("file_location:query:")
        assert len(key) > 30  # Hash should be appended

    def test_search_result_key_consistency(self):
        """Test same query generates same key."""
        query = "test query"
        key1 = CacheSchemas.search_result_key(query)
        key2 = CacheSchemas.search_result_key(query)
        assert key1 == key2

    def test_search_result_key_different_queries(self):
        """Test different queries generate different keys."""
        key1 = CacheSchemas.search_result_key("query 1")
        key2 = CacheSchemas.search_result_key("query 2")
        assert key1 != key2

    def test_search_result_key_with_projects(self):
        """Test search result key includes project filters."""
        key1 = CacheSchemas.search_result_key("test")
        key2 = CacheSchemas.search_result_key("test", projects=["omniarchon"])
        assert key1 != key2

    def test_project_status_key(self):
        """Test project status cache key."""
        key = CacheSchemas.project_status_key("omniarchon")
        assert key == "file_location:project:omniarchon:status"

    def test_serialization_roundtrip(self):
        """Test result serialization/deserialization."""
        result = {"success": True, "results": []}
        serialized = CacheSchemas.serialize_search_result(result)
        assert "cached_at" in serialized

        deserialized = CacheSchemas.deserialize_search_result(serialized)
        assert deserialized["success"] is True
        assert "cached_at" in deserialized

    def test_ttl_validation(self):
        """Test TTL validation."""
        assert CacheSchemas.validate_ttl(300) is True  # Valid
        assert CacheSchemas.validate_ttl(50) is False  # Too low
        assert CacheSchemas.validate_ttl(100000) is False  # Too high

    def test_ttl_determination(self):
        """Test TTL determination based on key type."""
        search_key = CacheSchemas.search_result_key("test")
        status_key = CacheSchemas.project_status_key("test")

        search_ttl = CacheSchemas.get_ttl_for_key_type(search_key)
        status_ttl = CacheSchemas.get_ttl_for_key_type(status_key)

        assert search_ttl == CacheSchemas.SEARCH_RESULT_TTL
        assert status_ttl == CacheSchemas.PROJECT_STATUS_TTL


if __name__ == "__main__":
    # Run tests with pytest if available, otherwise run basic checks
    import subprocess

    try:
        result = subprocess.run(
            ["pytest", __file__, "-v", "--tb=short"], capture_output=True, text=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print("pytest not found, running basic test discovery...")
        # Count test methods
        test_count = sum(
            1
            for name in dir()
            if name.startswith("Test")
            for method in dir(eval(name))
            if method.startswith("test_")
        )
        print(f"✓ Discovered {test_count} test methods")
