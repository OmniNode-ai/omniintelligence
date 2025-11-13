# Stream A: Data Models & Schemas

**Owner**: Poly-A
**Duration**: 2-3 hours
**Dependencies**: NONE (100% independent)
**Priority**: HIGH

---

## Objective

Implement all Pydantic data models and storage schemas for the POC Tree Stamping Integration.

---

## Success Criteria

- [x] All Pydantic models implemented with validation
- [x] Qdrant collection schema defined
- [x] Memgraph node/relationship schemas defined
- [x] Valkey cache key patterns documented
- [x] Unit tests passing (80%+ coverage)
- [x] All models importable without errors

---

## Contracts & Interfaces

**Reference**: `docs/planning/INTERFACES.md`

All type signatures, validation rules, and schemas are defined in the interfaces document.

---

## Tasks

### Task 1: Create Pydantic Models (60 min)

**File**: `services/intelligence/src/models/file_location.py`

**Models to Implement**:
1. `ProjectIndexRequest` - Request to index a project
2. `ProjectIndexResult` - Response from indexing operation
3. `FileSearchRequest` - Request to search for files
4. `FileSearchResult` - Response from search operation
5. `FileMatch` - Single file search result
6. `ProjectIndexStatus` - Status of project indexing
7. `ErrorResponse` - Standard error response format

**Implementation Checklist**:
- [ ] Import required dependencies (pydantic, typing, datetime)
- [ ] Implement all 7 models with complete field definitions
- [ ] Add field validation (validators for paths, scores, etc.)
- [ ] Add docstrings and examples
- [ ] Add `__repr__` methods for debugging
- [ ] Test serialization/deserialization

**Validation Requirements**:
- `project_path`: Must be absolute path starting with "/"
- `project_name`: Minimum 2 characters
- `quality_score`: Range 0.0-1.0
- `confidence`: Range 0.0-1.0
- `limit`: Range 1-100

---

### Task 2: Create Storage Schemas (30 min)

#### Qdrant Schema

**File**: `services/intelligence/src/schemas/qdrant_schemas.py`

```python
from qdrant_client.models import Distance, VectorParams

class QdrantSchemas:
    """Qdrant collection schemas for file location search."""

    FILE_LOCATIONS_COLLECTION = "file_locations"

    @staticmethod
    def get_file_locations_config():
        """Get configuration for file_locations collection."""
        return {
            "collection_name": "file_locations",
            "vectors_config": VectorParams(
                size=1536,  # OpenAI text-embedding-3-small
                distance=Distance.COSINE
            )
        }

    @staticmethod
    def get_payload_schema():
        """Get payload schema for file_locations collection."""
        return {
            "absolute_path": "keyword",
            "relative_path": "keyword",
            "file_hash": "keyword",
            "project_name": "keyword",
            "project_root": "keyword",
            "file_type": "keyword",
            "quality_score": "float",
            "onex_compliance": "float",
            "onex_type": "keyword",
            "concepts": "keyword[]",
            "themes": "keyword[]",
            "domains": "keyword[]",
            "pattern_types": "keyword[]",
            "indexed_at": "datetime",
            "last_modified": "datetime"
        }
```

**Checklist**:
- [ ] Create QdrantSchemas class
- [ ] Define collection configuration
- [ ] Define payload schema
- [ ] Add helper methods for collection creation

#### Memgraph Schema

**File**: `services/intelligence/src/schemas/memgraph_schemas.py`

```python
class MemgraphSchemas:
    """Memgraph node and relationship schemas for file location knowledge graph."""

    # Node creation queries
    CREATE_PROJECT_NODE = """
        MERGE (p:Project {name: $name})
        ON CREATE SET
            p.path = $path,
            p.indexed_at = datetime(),
            p.file_count = $file_count
        ON MATCH SET
            p.file_count = $file_count,
            p.last_updated = datetime()
        RETURN p
    """

    CREATE_FILE_NODE = """
        MERGE (f:File {absolute_path: $absolute_path})
        ON CREATE SET
            f.path = $path,
            f.hash = $hash,
            f.quality_score = $quality_score,
            f.onex_type = $onex_type,
            f.file_type = $file_type,
            f.indexed_at = datetime()
        ON MATCH SET
            f.quality_score = $quality_score,
            f.last_updated = datetime()
        RETURN f
    """

    # Relationship creation queries
    CREATE_CONTAINS_RELATIONSHIP = """
        MATCH (p:Project {name: $project_name})
        MATCH (f:File {absolute_path: $file_path})
        MERGE (p)-[r:CONTAINS]->(f)
        ON CREATE SET r.indexed_at = datetime()
        RETURN r
    """

    CREATE_HAS_CONCEPT_RELATIONSHIP = """
        MERGE (c:Concept {name: $concept_name})
        WITH c
        MATCH (f:File {absolute_path: $file_path})
        MERGE (f)-[r:HAS_CONCEPT]->(c)
        ON CREATE SET r.confidence = $confidence
        RETURN r
    """

    # Query patterns
    FIND_FILES_BY_PROJECT = """
        MATCH (p:Project {name: $project_name})-[:CONTAINS]->(f:File)
        RETURN f
    """

    FIND_FILES_BY_CONCEPT = """
        MATCH (f:File)-[:HAS_CONCEPT]->(c:Concept {name: $concept_name})
        WHERE f.quality_score >= $min_quality
        RETURN f
        ORDER BY f.quality_score DESC
        LIMIT $limit
    """
```

**Checklist**:
- [ ] Create MemgraphSchemas class
- [ ] Define node creation queries (Project, File, Concept, Theme, Domain, ONEXType)
- [ ] Define relationship creation queries (CONTAINS, HAS_CONCEPT, HAS_THEME, etc.)
- [ ] Define common query patterns
- [ ] Add docstrings explaining each query

#### Valkey Cache Schema

**File**: `services/intelligence/src/schemas/cache_schemas.py`

```python
import hashlib
import json
from datetime import datetime
from typing import Optional

class CacheSchemas:
    """Valkey cache key patterns and operations for file location search."""

    # TTLs (in seconds)
    SEARCH_RESULT_TTL = 300  # 5 minutes
    PROJECT_STATUS_TTL = 3600  # 1 hour

    @staticmethod
    def search_result_key(query: str) -> str:
        """Generate cache key for search result."""
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        return f"file_location:query:{query_hash}"

    @staticmethod
    def project_status_key(project_name: str) -> str:
        """Generate cache key for project status."""
        return f"file_location:project:{project_name}:status"

    @staticmethod
    def project_invalidation_key(project_name: str) -> str:
        """Generate invalidation key for project."""
        return f"file_location:project:{project_name}:invalidate"

    @staticmethod
    def serialize_search_result(result: dict) -> str:
        """Serialize search result for caching."""
        result["cached_at"] = datetime.now().isoformat()
        return json.dumps(result)

    @staticmethod
    def deserialize_search_result(cached: str) -> dict:
        """Deserialize cached search result."""
        return json.loads(cached)
```

**Checklist**:
- [ ] Create CacheSchemas class
- [ ] Define TTL constants
- [ ] Implement key generation methods
- [ ] Implement serialization/deserialization helpers
- [ ] Add cache invalidation pattern methods

---

### Task 3: Unit Tests (60 min)

**File**: `tests/unit/test_file_location_models.py`

**Test Cases**:

```python
import pytest
from pydantic import ValidationError
from models.file_location import (
    ProjectIndexRequest,
    ProjectIndexResult,
    FileSearchRequest,
    FileSearchResult,
    FileMatch,
    ProjectIndexStatus
)


class TestProjectIndexRequest:
    def test_valid_request(self):
        """Test valid project index request."""
        request = ProjectIndexRequest(
            project_path="/Volumes/PRO-G40/Code/omniarchon",
            project_name="omniarchon",
            include_tests=True,
            force_reindex=False
        )
        assert request.project_path == "/Volumes/PRO-G40/Code/omniarchon"
        assert request.project_name == "omniarchon"

    def test_invalid_project_path_relative(self):
        """Test that relative paths are rejected."""
        with pytest.raises(ValidationError) as exc:
            ProjectIndexRequest(
                project_path="relative/path",
                project_name="test"
            )
        assert "must be absolute path" in str(exc.value)

    def test_invalid_project_name_too_short(self):
        """Test that project names must be >= 2 characters."""
        with pytest.raises(ValidationError) as exc:
            ProjectIndexRequest(
                project_path="/valid/path",
                project_name="a"
            )
        assert "at least 2 characters" in str(exc.value)


class TestFileSearchRequest:
    def test_valid_search_request(self):
        """Test valid file search request."""
        request = FileSearchRequest(
            query="authentication module",
            projects=["omniarchon"],
            min_quality_score=0.7,
            limit=10
        )
        assert request.query == "authentication module"
        assert request.limit == 10

    def test_quality_score_validation(self):
        """Test quality score must be in range [0.0, 1.0]."""
        with pytest.raises(ValidationError):
            FileSearchRequest(
                query="test",
                min_quality_score=1.5  # Invalid: > 1.0
            )

    def test_limit_validation(self):
        """Test limit must be in range [1, 100]."""
        with pytest.raises(ValidationError):
            FileSearchRequest(
                query="test",
                limit=0  # Invalid: < 1
            )


class TestFileMatch:
    def test_serialization(self):
        """Test FileMatch serialization."""
        match = FileMatch(
            file_path="/path/to/file.py",
            relative_path="src/file.py",
            project_name="test",
            confidence=0.92,
            quality_score=0.87,
            onex_type="effect",
            concepts=["auth", "jwt"],
            themes=["security"],
            why="High semantic match for 'authentication'"
        )

        # Serialize to dict
        data = match.dict()
        assert data["confidence"] == 0.92

        # Deserialize from dict
        restored = FileMatch(**data)
        assert restored.file_path == match.file_path
```

**Test Checklist**:
- [ ] Test all models with valid data
- [ ] Test validation errors (invalid paths, scores, limits)
- [ ] Test serialization/deserialization (dict, JSON)
- [ ] Test field defaults
- [ ] Test optional vs required fields
- [ ] Achieve 80%+ code coverage

**Run Tests**:
```bash
cd /Volumes/PRO-G40/Code/omniarchon
pytest tests/unit/test_file_location_models.py -v --cov=services/intelligence/src/models/file_location
```

---

### Task 4: Schema Tests (30 min)

**File**: `tests/unit/test_file_location_schemas.py`

**Test Cases**:

```python
import pytest
from schemas.qdrant_schemas import QdrantSchemas
from schemas.memgraph_schemas import MemgraphSchemas
from schemas.cache_schemas import CacheSchemas


class TestQdrantSchemas:
    def test_file_locations_config(self):
        """Test Qdrant collection configuration."""
        config = QdrantSchemas.get_file_locations_config()
        assert config["collection_name"] == "file_locations"
        assert config["vectors_config"].size == 1536
        assert config["vectors_config"].distance.name == "COSINE"

    def test_payload_schema(self):
        """Test payload schema definition."""
        schema = QdrantSchemas.get_payload_schema()
        assert "absolute_path" in schema
        assert schema["quality_score"] == "float"


class TestMemgraphSchemas:
    def test_node_creation_queries(self):
        """Test node creation query templates."""
        assert "MERGE (p:Project" in MemgraphSchemas.CREATE_PROJECT_NODE
        assert "MERGE (f:File" in MemgraphSchemas.CREATE_FILE_NODE

    def test_relationship_queries(self):
        """Test relationship creation queries."""
        assert "CONTAINS" in MemgraphSchemas.CREATE_CONTAINS_RELATIONSHIP
        assert "HAS_CONCEPT" in MemgraphSchemas.CREATE_HAS_CONCEPT_RELATIONSHIP


class TestCacheSchemas:
    def test_search_result_key_generation(self):
        """Test search result cache key generation."""
        query = "test query"
        key = CacheSchemas.search_result_key(query)
        assert key.startswith("file_location:query:")
        assert len(key) > 30  # Hash should be appended

        # Same query should generate same key
        key2 = CacheSchemas.search_result_key(query)
        assert key == key2

    def test_project_status_key(self):
        """Test project status cache key."""
        key = CacheSchemas.project_status_key("omniarchon")
        assert key == "file_location:project:omniarchon:status"

    def test_serialization(self):
        """Test result serialization/deserialization."""
        result = {"success": True, "results": []}
        serialized = CacheSchemas.serialize_search_result(result)
        assert "cached_at" in serialized

        deserialized = CacheSchemas.deserialize_search_result(serialized)
        assert deserialized["success"] is True
```

**Run Tests**:
```bash
pytest tests/unit/test_file_location_schemas.py -v
```

---

## Deliverables

1. **Models File** (`models/file_location.py`):
   - All 7 Pydantic models implemented
   - Validation logic working
   - Type hints complete

2. **Schema Files**:
   - `schemas/qdrant_schemas.py` - Qdrant collection configuration
   - `schemas/memgraph_schemas.py` - Cypher query templates
   - `schemas/cache_schemas.py` - Cache key patterns

3. **Test Files**:
   - `tests/unit/test_file_location_models.py` - Model tests (80%+ coverage)
   - `tests/unit/test_file_location_schemas.py` - Schema tests

4. **Documentation**:
   - Docstrings for all classes and methods
   - Type hints for all parameters and returns

---

## Execution Checklist

**Setup** (5 min):
- [ ] Read interfaces document (`docs/planning/INTERFACES.md`)
- [ ] Create directory structure if needed
- [ ] Set up Python environment

**Implementation** (120 min):
- [ ] Task 1: Implement Pydantic models (60 min)
- [ ] Task 2: Create storage schemas (30 min)
- [ ] Task 3: Write model unit tests (60 min)
- [ ] Task 4: Write schema tests (30 min)

**Validation** (15 min):
- [ ] Run all tests: `pytest tests/unit/test_file_location_*.py -v`
- [ ] Check test coverage: `pytest --cov=services/intelligence/src/models --cov=services/intelligence/src/schemas`
- [ ] Verify imports: `python -c "from models.file_location import *"`
- [ ] Run type checker: `mypy services/intelligence/src/models/ services/intelligence/src/schemas/`

**Success Criteria** (Must all pass):
- [ ] All tests passing
- [ ] Test coverage >= 80%
- [ ] No import errors
- [ ] No type checking errors
- [ ] All validation logic working correctly

---

## Time Estimate

- Setup: 5 minutes
- Implementation: 120 minutes (2 hours)
- Testing & Validation: 15 minutes
- **Total: ~2.5 hours**

---

## Dependencies

**None** - This stream is 100% independent and can start immediately.

---

## Next Stream

After completion, output will be used by:
- **Stream B** (Integration Service) - Imports models for type hints
- **Stream C** (REST API) - Uses models for request/response schemas
- **Stream E** (Tests) - Imports models for test fixtures

---

## Contact

**Stream Owner**: Poly-A
**Status**: Ready to Execute
**Priority**: HIGH (blocks other streams)

---

**Start Execution Now!**
