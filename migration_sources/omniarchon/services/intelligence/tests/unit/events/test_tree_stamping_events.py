"""
Unit Tests for Tree Stamping Event Models

Tests event payload serialization, deserialization, and validation:
- Request payload models
- Response payload models
- Event type enums
- Field validation
- JSON serialization
- Error handling

Created: 2025-10-24
Purpose: Stream E - Testing Infrastructure
"""

import json
from datetime import UTC, datetime
from enum import Enum
from typing import List, Optional

import pytest
from pydantic import BaseModel, Field, ValidationError, field_validator

# ==============================================================================
# Mock Event Models (for testing when real models don't exist yet)
# ==============================================================================


class EnumTreeStampingEventType(str, Enum):
    """Event types for tree stamping operations."""

    INDEX_PROJECT_REQUESTED = "INDEX_PROJECT_REQUESTED"
    INDEX_PROJECT_COMPLETED = "INDEX_PROJECT_COMPLETED"
    INDEX_PROJECT_FAILED = "INDEX_PROJECT_FAILED"

    # Intermediate Pipeline Events (Phase 3)
    TREE_DISCOVERED = "TREE_DISCOVERED"
    TREE_DISCOVERED_FAILED = "TREE_DISCOVERED_FAILED"
    TREE_STAMPED = "TREE_STAMPED"
    TREE_STAMPED_FAILED = "TREE_STAMPED_FAILED"
    TREE_INDEXED = "TREE_INDEXED"
    TREE_INDEXED_FAILED = "TREE_INDEXED_FAILED"

    SEARCH_FILES_REQUESTED = "SEARCH_FILES_REQUESTED"
    SEARCH_FILES_COMPLETED = "SEARCH_FILES_COMPLETED"
    SEARCH_FILES_FAILED = "SEARCH_FILES_FAILED"
    GET_STATUS_REQUESTED = "GET_STATUS_REQUESTED"
    GET_STATUS_COMPLETED = "GET_STATUS_COMPLETED"
    GET_STATUS_FAILED = "GET_STATUS_FAILED"

    def __str__(self) -> str:
        """Return just the enum value when converted to string."""
        return self.value


class EnumIndexingErrorCode(str, Enum):
    """Error codes for indexing operations."""

    TREE_DISCOVERY_FAILED = "TREE_DISCOVERY_FAILED"
    INTELLIGENCE_GENERATION_FAILED = "INTELLIGENCE_GENERATION_FAILED"
    STAMPING_FAILED = "STAMPING_FAILED"
    VECTOR_INDEXING_FAILED = "VECTOR_INDEXING_FAILED"
    GRAPH_INDEXING_FAILED = "GRAPH_INDEXING_FAILED"
    CACHE_WARMING_FAILED = "CACHE_WARMING_FAILED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INVALID_PROJECT_PATH = "INVALID_PROJECT_PATH"


class ModelIndexProjectRequestPayload(BaseModel):
    """Payload for INDEX_PROJECT_REQUESTED event."""

    project_path: str = Field(
        ...,
        description="Absolute path to project root",
        min_length=1,
    )
    project_name: str = Field(
        ...,
        description="Unique project identifier",
        min_length=1,
        max_length=100,
    )
    include_tests: bool = Field(
        default=True,
        description="Include test files in indexing",
    )
    force_reindex: bool = Field(
        default=False,
        description="Force reindex even if already indexed",
    )

    @field_validator("project_path")
    @classmethod
    def validate_project_path(cls, v: str) -> str:
        """Prevent path traversal attacks."""
        if ".." in v or not v.startswith("/"):
            raise ValueError(
                "Invalid project path: must be absolute, no path traversal"
            )
        return v


class ModelIndexProjectCompletedPayload(BaseModel):
    """Payload for INDEX_PROJECT_COMPLETED event."""

    project_name: str
    files_discovered: int = Field(ge=0)
    files_indexed: int = Field(ge=0)
    vector_indexed: int = Field(ge=0)
    graph_indexed: int = Field(ge=0)
    cache_warmed: bool
    duration_ms: int = Field(ge=0)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ModelIndexProjectFailedPayload(BaseModel):
    """Payload for INDEX_PROJECT_FAILED event."""

    project_name: str
    error_code: EnumIndexingErrorCode
    error_message: str
    duration_ms: int = Field(ge=0)
    retry_recommended: bool = Field(default=False)
    retry_after_seconds: Optional[int] = Field(default=None, ge=0)


class ModelSearchFilesRequestPayload(BaseModel):
    """Payload for SEARCH_FILES_REQUESTED event."""

    query: str = Field(..., min_length=1)
    projects: Optional[List[str]] = Field(default=None)
    file_types: Optional[List[str]] = Field(default=None)
    min_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=1000)


class ModelSearchFilesCompletedPayload(BaseModel):
    """Payload for SEARCH_FILES_COMPLETED event."""

    query: str
    results_count: int = Field(ge=0)
    cache_hit: bool
    duration_ms: int = Field(ge=0)


class ModelSearchFilesFailedPayload(BaseModel):
    """Payload for SEARCH_FILES_FAILED event."""

    query: str
    error_code: str
    error_message: str
    duration_ms: int = Field(ge=0)


class ModelGetStatusRequestPayload(BaseModel):
    """Payload for GET_STATUS_REQUESTED event."""

    project_name: Optional[str] = Field(default=None)


class ModelGetStatusCompletedPayload(BaseModel):
    """Payload for GET_STATUS_COMPLETED event."""

    project_name: str
    indexed: bool
    file_count: int = Field(ge=0)
    status: str


class ModelGetStatusFailedPayload(BaseModel):
    """Payload for GET_STATUS_FAILED event."""

    project_name: Optional[str]
    error_code: str
    error_message: str


# ==============================================================================
# Test Suite: Request Payloads
# ==============================================================================


class TestIndexProjectRequestPayload:
    """Test IndexProjectRequestPayload model."""

    def test_valid_payload(self):
        """Test valid index project request payload."""
        payload = ModelIndexProjectRequestPayload(
            project_path="/tmp/test-project",
            project_name="test-project",
            include_tests=True,
            force_reindex=False,
        )

        assert payload.project_path == "/tmp/test-project"
        assert payload.project_name == "test-project"
        assert payload.include_tests is True
        assert payload.force_reindex is False

    def test_defaults(self):
        """Test default values."""
        payload = ModelIndexProjectRequestPayload(
            project_path="/tmp/test",
            project_name="test",
        )

        assert payload.include_tests is True
        assert payload.force_reindex is False

    def test_path_traversal_prevention(self):
        """Test path traversal attack prevention."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIndexProjectRequestPayload(
                project_path="/tmp/../etc/passwd",
                project_name="test",
            )

        assert "path traversal" in str(exc_info.value).lower()

    def test_relative_path_rejection(self):
        """Test relative paths are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIndexProjectRequestPayload(
                project_path="relative/path",
                project_name="test",
            )

        assert "absolute" in str(exc_info.value).lower()

    def test_empty_project_name(self):
        """Test empty project name is rejected."""
        with pytest.raises(ValidationError):
            ModelIndexProjectRequestPayload(
                project_path="/tmp/test",
                project_name="",
            )

    def test_json_serialization(self):
        """Test JSON serialization."""
        payload = ModelIndexProjectRequestPayload(
            project_path="/tmp/test",
            project_name="test",
        )

        json_str = payload.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["project_path"] == "/tmp/test"
        assert parsed["project_name"] == "test"
        assert parsed["include_tests"] is True

    def test_json_deserialization(self):
        """Test JSON deserialization."""
        json_data = {
            "project_path": "/tmp/test",
            "project_name": "test",
            "include_tests": False,
            "force_reindex": True,
        }

        payload = ModelIndexProjectRequestPayload(**json_data)

        assert payload.project_path == "/tmp/test"
        assert payload.include_tests is False
        assert payload.force_reindex is True


class TestSearchFilesRequestPayload:
    """Test SearchFilesRequestPayload model."""

    def test_valid_payload(self):
        """Test valid search files request payload."""
        payload = ModelSearchFilesRequestPayload(
            query="authentication",
            projects=["project1", "project2"],
            file_types=[".py", ".ts"],
            min_quality_score=0.7,
            limit=20,
        )

        assert payload.query == "authentication"
        assert payload.projects == ["project1", "project2"]
        assert payload.file_types == [".py", ".ts"]
        assert payload.min_quality_score == 0.7
        assert payload.limit == 20

    def test_defaults(self):
        """Test default values."""
        payload = ModelSearchFilesRequestPayload(query="test")

        assert payload.projects is None
        assert payload.file_types is None
        assert payload.min_quality_score == 0.0
        assert payload.limit == 10

    def test_quality_score_validation(self):
        """Test quality score is validated to 0.0-1.0 range."""
        # Valid scores
        ModelSearchFilesRequestPayload(query="test", min_quality_score=0.0)
        ModelSearchFilesRequestPayload(query="test", min_quality_score=0.5)
        ModelSearchFilesRequestPayload(query="test", min_quality_score=1.0)

        # Invalid scores
        with pytest.raises(ValidationError):
            ModelSearchFilesRequestPayload(query="test", min_quality_score=-0.1)

        with pytest.raises(ValidationError):
            ModelSearchFilesRequestPayload(query="test", min_quality_score=1.1)

    def test_limit_validation(self):
        """Test limit is validated to 1-1000 range."""
        # Valid limits
        ModelSearchFilesRequestPayload(query="test", limit=1)
        ModelSearchFilesRequestPayload(query="test", limit=500)
        ModelSearchFilesRequestPayload(query="test", limit=1000)

        # Invalid limits
        with pytest.raises(ValidationError):
            ModelSearchFilesRequestPayload(query="test", limit=0)

        with pytest.raises(ValidationError):
            ModelSearchFilesRequestPayload(query="test", limit=1001)

    def test_empty_query_rejected(self):
        """Test empty query is rejected."""
        with pytest.raises(ValidationError):
            ModelSearchFilesRequestPayload(query="")


class TestGetStatusRequestPayload:
    """Test GetStatusRequestPayload model."""

    def test_with_project_name(self):
        """Test with specific project name."""
        payload = ModelGetStatusRequestPayload(project_name="test-project")

        assert payload.project_name == "test-project"

    def test_without_project_name(self):
        """Test without project name (all projects)."""
        payload = ModelGetStatusRequestPayload()

        assert payload.project_name is None


# ==============================================================================
# Test Suite: Response Payloads
# ==============================================================================


class TestIndexProjectCompletedPayload:
    """Test IndexProjectCompletedPayload model."""

    def test_valid_payload(self):
        """Test valid completed payload."""
        payload = ModelIndexProjectCompletedPayload(
            project_name="test-project",
            files_discovered=100,
            files_indexed=98,
            vector_indexed=98,
            graph_indexed=98,
            cache_warmed=True,
            duration_ms=5000,
            errors=[],
            warnings=["2 files skipped"],
        )

        assert payload.project_name == "test-project"
        assert payload.files_discovered == 100
        assert payload.files_indexed == 98
        assert payload.cache_warmed is True
        assert len(payload.warnings) == 1

    def test_negative_counts_rejected(self):
        """Test negative counts are rejected."""
        with pytest.raises(ValidationError):
            ModelIndexProjectCompletedPayload(
                project_name="test",
                files_discovered=-1,
                files_indexed=0,
                vector_indexed=0,
                graph_indexed=0,
                cache_warmed=False,
                duration_ms=100,
            )

    def test_empty_errors_and_warnings(self):
        """Test empty errors and warnings lists."""
        payload = ModelIndexProjectCompletedPayload(
            project_name="test",
            files_discovered=10,
            files_indexed=10,
            vector_indexed=10,
            graph_indexed=10,
            cache_warmed=True,
            duration_ms=1000,
        )

        assert payload.errors == []
        assert payload.warnings == []


class TestIndexProjectFailedPayload:
    """Test IndexProjectFailedPayload model."""

    def test_valid_payload(self):
        """Test valid failed payload."""
        payload = ModelIndexProjectFailedPayload(
            project_name="test-project",
            error_code=EnumIndexingErrorCode.TREE_DISCOVERY_FAILED,
            error_message="OnexTree service unavailable",
            duration_ms=100,
            retry_recommended=True,
            retry_after_seconds=60,
        )

        assert payload.project_name == "test-project"
        assert payload.error_code == EnumIndexingErrorCode.TREE_DISCOVERY_FAILED
        assert payload.retry_recommended is True
        assert payload.retry_after_seconds == 60

    def test_error_code_enum(self):
        """Test error code uses enum values."""
        payload = ModelIndexProjectFailedPayload(
            project_name="test",
            error_code=EnumIndexingErrorCode.SERVICE_UNAVAILABLE,
            error_message="Error",
            duration_ms=100,
        )

        assert isinstance(payload.error_code, EnumIndexingErrorCode)
        assert payload.error_code.value == "SERVICE_UNAVAILABLE"

    def test_retry_after_validation(self):
        """Test retry_after_seconds must be non-negative."""
        # Valid
        ModelIndexProjectFailedPayload(
            project_name="test",
            error_code=EnumIndexingErrorCode.SERVICE_UNAVAILABLE,
            error_message="Error",
            duration_ms=100,
            retry_after_seconds=0,
        )

        # Invalid
        with pytest.raises(ValidationError):
            ModelIndexProjectFailedPayload(
                project_name="test",
                error_code=EnumIndexingErrorCode.SERVICE_UNAVAILABLE,
                error_message="Error",
                duration_ms=100,
                retry_after_seconds=-1,
            )


# ==============================================================================
# Test Suite: Event Type Enum
# ==============================================================================


class TestEventTypeEnum:
    """Test EnumTreeStampingEventType enum."""

    def test_all_event_types_defined(self):
        """Test all expected event types are defined."""
        expected_types = [
            "INDEX_PROJECT_REQUESTED",
            "INDEX_PROJECT_COMPLETED",
            "INDEX_PROJECT_FAILED",
            "SEARCH_FILES_REQUESTED",
            "SEARCH_FILES_COMPLETED",
            "SEARCH_FILES_FAILED",
            "GET_STATUS_REQUESTED",
            "GET_STATUS_COMPLETED",
            "GET_STATUS_FAILED",
        ]

        enum_values = [e.value for e in EnumTreeStampingEventType]

        for expected in expected_types:
            assert expected in enum_values

    def test_enum_string_conversion(self):
        """Test enum can be used as string."""
        event_type = EnumTreeStampingEventType.INDEX_PROJECT_REQUESTED

        assert event_type == "INDEX_PROJECT_REQUESTED"
        assert str(event_type) == "INDEX_PROJECT_REQUESTED"

    def test_enum_comparison(self):
        """Test enum comparison."""
        assert (
            EnumTreeStampingEventType.INDEX_PROJECT_REQUESTED
            != EnumTreeStampingEventType.INDEX_PROJECT_COMPLETED
        )

        assert (
            EnumTreeStampingEventType.INDEX_PROJECT_REQUESTED
            == EnumTreeStampingEventType.INDEX_PROJECT_REQUESTED
        )


class TestErrorCodeEnum:
    """Test EnumIndexingErrorCode enum."""

    def test_all_error_codes_defined(self):
        """Test all expected error codes are defined."""
        expected_codes = [
            "TREE_DISCOVERY_FAILED",
            "INTELLIGENCE_GENERATION_FAILED",
            "STAMPING_FAILED",
            "VECTOR_INDEXING_FAILED",
            "GRAPH_INDEXING_FAILED",
            "CACHE_WARMING_FAILED",
            "SERVICE_UNAVAILABLE",
            "INVALID_PROJECT_PATH",
        ]

        enum_values = [e.value for e in EnumIndexingErrorCode]

        for expected in expected_codes:
            assert expected in enum_values


# ==============================================================================
# Test Suite: Cross-Model Validation
# ==============================================================================


class TestCrossModelValidation:
    """Test validation across multiple event models."""

    def test_request_response_correlation(self):
        """Test request and response payloads can be correlated."""
        # Create request
        request = ModelIndexProjectRequestPayload(
            project_path="/tmp/test",
            project_name="test-project",
        )

        # Create successful response
        response = ModelIndexProjectCompletedPayload(
            project_name=request.project_name,
            files_discovered=10,
            files_indexed=10,
            vector_indexed=10,
            graph_indexed=10,
            cache_warmed=True,
            duration_ms=1000,
        )

        assert request.project_name == response.project_name

    def test_failed_response_with_error_code(self):
        """Test failed response includes proper error code."""
        failed = ModelIndexProjectFailedPayload(
            project_name="test",
            error_code=EnumIndexingErrorCode.TREE_DISCOVERY_FAILED,
            error_message="Service unavailable",
            duration_ms=100,
        )

        assert failed.error_code in EnumIndexingErrorCode
        assert failed.error_message != ""


# ==============================================================================
# Test Suite: JSON Serialization/Deserialization
# ==============================================================================


class TestJSONSerialization:
    """Test JSON serialization and deserialization for all models."""

    def test_index_request_roundtrip(self):
        """Test index request serialization roundtrip."""
        original = ModelIndexProjectRequestPayload(
            project_path="/tmp/test",
            project_name="test",
            include_tests=False,
        )

        json_str = original.model_dump_json()
        restored = ModelIndexProjectRequestPayload.model_validate_json(json_str)

        assert restored.project_path == original.project_path
        assert restored.project_name == original.project_name
        assert restored.include_tests == original.include_tests

    def test_index_completed_roundtrip(self):
        """Test index completed serialization roundtrip."""
        original = ModelIndexProjectCompletedPayload(
            project_name="test",
            files_discovered=100,
            files_indexed=98,
            vector_indexed=98,
            graph_indexed=98,
            cache_warmed=True,
            duration_ms=5000,
            errors=["error1"],
            warnings=["warning1"],
        )

        json_str = original.model_dump_json()
        restored = ModelIndexProjectCompletedPayload.model_validate_json(json_str)

        assert restored.project_name == original.project_name
        assert restored.files_discovered == original.files_discovered
        assert restored.errors == original.errors

    def test_search_request_roundtrip(self):
        """Test search request serialization roundtrip."""
        original = ModelSearchFilesRequestPayload(
            query="test",
            projects=["p1", "p2"],
            file_types=[".py"],
            min_quality_score=0.8,
            limit=50,
        )

        json_str = original.model_dump_json()
        restored = ModelSearchFilesRequestPayload.model_validate_json(json_str)

        assert restored.query == original.query
        assert restored.projects == original.projects
        assert restored.min_quality_score == original.min_quality_score


# ==============================================================================
# Test Suite: Intermediate Pipeline Events (Phase 3)
# ==============================================================================


class TestTreeDiscoveredEvent:
    """Test TREE_DISCOVERED event creation and serialization."""

    def test_create_tree_discovered_event(self):
        """Test creating TREE_DISCOVERED event envelope."""
        from uuid import uuid4

        from events.models.tree_stamping_events import (
            EnumTreeStampingEventType,
            create_tree_discovered,
        )

        files_discovered = [
            {
                "file_path": "/project/src/main.py",
                "relative_path": "src/main.py",
                "language": "python",
                "size_bytes": 1024,
                "last_modified": datetime.now(UTC),
            }
        ]

        envelope = create_tree_discovered(
            project_name="test-project",
            project_path="/project",
            files_discovered=files_discovered,
            discovery_duration_ms=1500.5,
            total_files=1,
            language_breakdown={"python": 1},
            correlation_id=uuid4(),
        )

        # Verify envelope structure
        assert envelope.payload["project_name"] == "test-project"
        assert envelope.payload["project_path"] == "/project"
        assert envelope.payload["total_files"] == 1
        assert envelope.payload["discovery_duration_ms"] == 1500.5
        assert envelope.payload["language_breakdown"] == {"python": 1}
        assert len(envelope.payload["files_discovered"]) == 1

        # Verify metadata
        assert envelope.metadata["schema_version"] == "v1"
        assert (
            envelope.metadata["topic"] == "dev.archon-intelligence.tree.discovered.v1"
        )

    def test_tree_discovered_correlation_id_propagation(self):
        """Test correlation_id is properly propagated."""
        from uuid import uuid4

        from events.models.tree_stamping_events import create_tree_discovered

        correlation_id = uuid4()

        envelope = create_tree_discovered(
            project_name="test",
            project_path="/test",
            files_discovered=[],
            discovery_duration_ms=100.0,
            total_files=0,
            language_breakdown={},
            correlation_id=correlation_id,
        )

        assert envelope.correlation_id == correlation_id


class TestTreeDiscoveredFailedEvent:
    """Test TREE_DISCOVERED_FAILED event creation."""

    def test_create_tree_discovered_failed_event(self):
        """Test creating TREE_DISCOVERED_FAILED event envelope."""
        from uuid import uuid4

        from events.models.tree_stamping_events import (
            EnumIndexingErrorCode,
            create_tree_discovered_failed,
        )

        envelope = create_tree_discovered_failed(
            project_name="test-project",
            project_path="/project",
            error_code=EnumIndexingErrorCode.TREE_DISCOVERY_FAILED,
            error_message="OnexTree service unavailable",
            duration_ms=500.0,
            correlation_id=uuid4(),
            retry_recommended=True,
            retry_after_seconds=60,
            error_details={"service": "onextree", "status_code": 503},
        )

        # Verify payload
        assert envelope.payload["project_name"] == "test-project"
        assert envelope.payload["project_path"] == "/project"
        assert envelope.payload["error_code"] == "TREE_DISCOVERY_FAILED"
        assert envelope.payload["error_message"] == "OnexTree service unavailable"
        assert envelope.payload["retry_recommended"] is True
        assert envelope.payload["retry_after_seconds"] == 60
        assert envelope.payload["error_details"]["service"] == "onextree"


class TestTreeStampedEvent:
    """Test TREE_STAMPED event creation and serialization."""

    def test_create_tree_stamped_event(self):
        """Test creating TREE_STAMPED event envelope."""
        from uuid import uuid4

        from events.models.tree_stamping_events import create_tree_stamped

        stamped_files = [
            {
                "file_path": "/project/src/main.py",
                "relative_path": "src/main.py",
                "quality_score": 0.85,
                "onex_type": "Effect",
                "complexity_score": 0.6,
                "concepts": ["authentication", "jwt"],
                "stamping_duration_ms": 250.0,
            }
        ]

        envelope = create_tree_stamped(
            project_name="test-project",
            files_stamped=1,
            stamped_files=stamped_files,
            stamping_duration_ms=2500.0,
            intelligence_summary={
                "avg_quality": 0.85,
                "onex_distribution": {"Effect": 1},
            },
            correlation_id=uuid4(),
        )

        # Verify payload
        assert envelope.payload["project_name"] == "test-project"
        assert envelope.payload["files_stamped"] == 1
        assert envelope.payload["stamping_duration_ms"] == 2500.0
        assert len(envelope.payload["stamped_files"]) == 1
        assert envelope.payload["stamped_files"][0]["quality_score"] == 0.85
        assert envelope.payload["stamped_files"][0]["onex_type"] == "Effect"
        assert envelope.payload["intelligence_summary"]["avg_quality"] == 0.85


class TestTreeStampedFailedEvent:
    """Test TREE_STAMPED_FAILED event creation."""

    def test_create_tree_stamped_failed_event(self):
        """Test creating TREE_STAMPED_FAILED event envelope."""
        from uuid import uuid4

        from events.models.tree_stamping_events import (
            EnumIndexingErrorCode,
            create_tree_stamped_failed,
        )

        envelope = create_tree_stamped_failed(
            project_name="test-project",
            files_attempted=100,
            files_succeeded=50,
            error_code=EnumIndexingErrorCode.STAMPING_FAILED,
            error_message="Intelligence generation timeout",
            duration_ms=30000.0,
            correlation_id=uuid4(),
            retry_recommended=True,
            retry_after_seconds=120,
        )

        # Verify payload
        assert envelope.payload["project_name"] == "test-project"
        assert envelope.payload["files_attempted"] == 100
        assert envelope.payload["files_succeeded"] == 50
        assert envelope.payload["error_code"] == "STAMPING_FAILED"
        assert envelope.payload["retry_recommended"] is True


class TestTreeIndexedEvent:
    """Test TREE_INDEXED event creation and serialization."""

    def test_create_tree_indexed_event(self):
        """Test creating TREE_INDEXED event envelope."""
        from uuid import uuid4

        from events.models.tree_stamping_events import create_tree_indexed

        envelope = create_tree_indexed(
            project_name="test-project",
            vector_indexed=98,
            graph_indexed=98,
            cache_warmed=True,
            indexing_duration_ms=5000.0,
            qdrant_points_created=98,
            memgraph_nodes_created=98,
            correlation_id=uuid4(),
        )

        # Verify payload
        assert envelope.payload["project_name"] == "test-project"
        assert envelope.payload["vector_indexed"] == 98
        assert envelope.payload["graph_indexed"] == 98
        assert envelope.payload["cache_warmed"] is True
        assert envelope.payload["indexing_duration_ms"] == 5000.0
        assert envelope.payload["qdrant_points_created"] == 98
        assert envelope.payload["memgraph_nodes_created"] == 98

        # Verify metadata
        assert envelope.metadata["schema_version"] == "v1"
        assert envelope.metadata["topic"] == "dev.archon-intelligence.tree.indexed.v1"


class TestTreeIndexedFailedEvent:
    """Test TREE_INDEXED_FAILED event creation."""

    def test_create_tree_indexed_failed_event(self):
        """Test creating TREE_INDEXED_FAILED event envelope."""
        from uuid import uuid4

        from events.models.tree_stamping_events import (
            EnumIndexingErrorCode,
            create_tree_indexed_failed,
        )

        envelope = create_tree_indexed_failed(
            project_name="test-project",
            vectors_attempted=100,
            vectors_succeeded=75,
            graph_items_attempted=100,
            graph_items_succeeded=60,
            error_code=EnumIndexingErrorCode.INDEXING_FAILED,
            error_message="Qdrant connection timeout",
            duration_ms=10000.0,
            correlation_id=uuid4(),
            retry_recommended=True,
            retry_after_seconds=90,
        )

        # Verify payload
        assert envelope.payload["project_name"] == "test-project"
        assert envelope.payload["vectors_attempted"] == 100
        assert envelope.payload["vectors_succeeded"] == 75
        assert envelope.payload["graph_items_attempted"] == 100
        assert envelope.payload["graph_items_succeeded"] == 60
        assert envelope.payload["error_code"] == "INDEXING_FAILED"


class TestIntermediateEventEnums:
    """Test intermediate event type enums."""

    def test_intermediate_event_types_defined(self):
        """Test intermediate event types are properly defined."""
        expected_types = [
            "TREE_DISCOVERED",
            "TREE_DISCOVERED_FAILED",
            "TREE_STAMPED",
            "TREE_STAMPED_FAILED",
            "TREE_INDEXED",
            "TREE_INDEXED_FAILED",
        ]

        enum_values = [e.value for e in EnumTreeStampingEventType]

        for expected in expected_types:
            assert expected in enum_values, f"Missing event type: {expected}"


class TestIntermediateEventPayloadModels:
    """Test intermediate event payload model validation."""

    def test_tree_discovered_payload_validation(self):
        """Test TreeDiscoveredPayload field validation."""
        from events.models.tree_stamping_events import (
            ModelTreeStampingFileInfo,
            ModelTreeStampingTreeDiscoveredPayload,
        )

        # Valid payload
        file_info = ModelTreeStampingFileInfo(
            file_path="/project/test.py",
            relative_path="test.py",
            language="python",
            size_bytes=1024,
            last_modified=datetime.now(UTC),
        )

        payload = ModelTreeStampingTreeDiscoveredPayload(
            project_name="test",
            project_path="/project",
            files_discovered=[file_info],
            discovery_duration_ms=1000.0,
            total_files=1,
            language_breakdown={"python": 1},
        )

        assert payload.total_files == 1
        assert len(payload.files_discovered) == 1

    def test_tree_stamped_payload_validation(self):
        """Test TreeStampedPayload field validation."""
        from events.models.tree_stamping_events import (
            ModelTreeStampingStampedFileInfo,
            ModelTreeStampingTreeStampedPayload,
        )

        # Valid payload
        stamped_file = ModelTreeStampingStampedFileInfo(
            file_path="/project/test.py",
            relative_path="test.py",
            quality_score=0.8,
            onex_type="Compute",
            complexity_score=0.5,
            concepts=["algorithm", "sorting"],
            stamping_duration_ms=200.0,
        )

        payload = ModelTreeStampingTreeStampedPayload(
            project_name="test",
            files_stamped=1,
            stamped_files=[stamped_file],
            stamping_duration_ms=2000.0,
            intelligence_summary={"avg_quality": 0.8},
        )

        assert payload.files_stamped == 1
        assert len(payload.stamped_files) == 1
        assert payload.stamped_files[0].quality_score == 0.8

    def test_tree_indexed_payload_validation(self):
        """Test TreeIndexedPayload field validation."""
        from events.models.tree_stamping_events import (
            ModelTreeStampingTreeIndexedPayload,
        )

        # Valid payload
        payload = ModelTreeStampingTreeIndexedPayload(
            project_name="test",
            vector_indexed=50,
            graph_indexed=50,
            cache_warmed=True,
            indexing_duration_ms=3000.0,
            qdrant_points_created=50,
            memgraph_nodes_created=50,
        )

        assert payload.vector_indexed == 50
        assert payload.graph_indexed == 50
        assert payload.cache_warmed is True

    def test_quality_score_range_validation(self):
        """Test quality score is validated to 0.0-1.0 range."""
        from events.models.tree_stamping_events import (
            ModelTreeStampingStampedFileInfo,
        )

        # Valid scores
        ModelTreeStampingStampedFileInfo(
            file_path="/test.py",
            relative_path="test.py",
            quality_score=0.0,
            complexity_score=0.5,
            stamping_duration_ms=100.0,
        )

        ModelTreeStampingStampedFileInfo(
            file_path="/test.py",
            relative_path="test.py",
            quality_score=1.0,
            complexity_score=0.5,
            stamping_duration_ms=100.0,
        )

        # Invalid scores
        with pytest.raises(ValidationError):
            ModelTreeStampingStampedFileInfo(
                file_path="/test.py",
                relative_path="test.py",
                quality_score=-0.1,
                complexity_score=0.5,
                stamping_duration_ms=100.0,
            )

        with pytest.raises(ValidationError):
            ModelTreeStampingStampedFileInfo(
                file_path="/test.py",
                relative_path="test.py",
                quality_score=1.1,
                complexity_score=0.5,
                stamping_duration_ms=100.0,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
