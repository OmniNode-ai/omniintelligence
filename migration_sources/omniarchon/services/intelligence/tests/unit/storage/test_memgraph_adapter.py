"""
Unit tests for MemgraphKnowledgeAdapter.

These tests validate critical Memgraph operations without requiring a live database.
All tests use mocking to ensure fast, isolated test execution.

CRITICAL: These tests prevent bugs like the project_name="unknown" issue by validating
field VALUES in Cypher queries, not just node creation.
"""

import asyncio
from datetime import datetime, timezone
from typing import List
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from models.entity_models import (
    EntityMetadata,
    EntityType,
    KnowledgeEntity,
    KnowledgeRelationship,
    RelationshipType,
)
from storage.memgraph_adapter import MemgraphKnowledgeAdapter, retry_on_transient_error

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_driver():
    """Mock Neo4j AsyncGraphDatabase driver."""
    driver = AsyncMock()
    driver.verify_connectivity = AsyncMock()
    driver.close = AsyncMock()
    return driver


@pytest.fixture
def mock_session():
    """Mock Neo4j async session."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    return session


@pytest.fixture
async def adapter(mock_driver):
    """Create MemgraphKnowledgeAdapter with mocked driver."""
    with patch(
        "storage.memgraph_adapter.AsyncGraphDatabase.driver", return_value=mock_driver
    ):
        adapter = MemgraphKnowledgeAdapter(uri="bolt://localhost:7687")
        await adapter.initialize()
        yield adapter
        await adapter.close()


# ============================================================================
# INITIALIZATION & HEALTH CHECKS
# ============================================================================


@pytest.mark.asyncio
async def test_initialize_success(mock_driver):
    """Test successful adapter initialization."""
    with patch(
        "storage.memgraph_adapter.AsyncGraphDatabase.driver", return_value=mock_driver
    ):
        adapter = MemgraphKnowledgeAdapter(uri="bolt://localhost:7687")
        await adapter.initialize()

        # Verify driver was created and connectivity was verified
        mock_driver.verify_connectivity.assert_called_once()
        assert adapter.driver is not None


@pytest.mark.asyncio
async def test_initialize_with_auth():
    """Test initialization with authentication credentials."""
    mock_driver = AsyncMock()
    mock_driver.verify_connectivity = AsyncMock()

    with patch(
        "storage.memgraph_adapter.AsyncGraphDatabase.driver", return_value=mock_driver
    ) as mock_driver_factory:
        adapter = MemgraphKnowledgeAdapter(
            uri="bolt://localhost:7687", username="test_user", password="test_pass"
        )
        await adapter.initialize()

        # Verify auth tuple was passed
        call_args = mock_driver_factory.call_args
        assert call_args[1]["auth"] == ("test_user", "test_pass")


@pytest.mark.asyncio
async def test_health_check_success(adapter, mock_session):
    """Test health check with successful response."""
    # Setup mock to return health check record
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value={"status": "health_check"})
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    result = await adapter.health_check()

    assert result is True
    mock_session.run.assert_called_once_with("RETURN 'health_check' as status")


@pytest.mark.asyncio
async def test_health_check_failure(adapter):
    """Test health check when database is unavailable."""
    adapter.driver.session = MagicMock(side_effect=Exception("Connection refused"))

    result = await adapter.health_check()

    assert result is False


@pytest.mark.asyncio
async def test_health_check_no_driver():
    """Test health check when driver is not initialized."""
    adapter = MemgraphKnowledgeAdapter()
    result = await adapter.health_check()

    assert result is False


# ============================================================================
# FILE NODE OPERATIONS - CRITICAL for project_name bug prevention
# ============================================================================


@pytest.mark.asyncio
async def test_create_file_node_preserves_project_name(adapter, mock_session):
    """
    CRITICAL TEST: Validates that project_name field is set correctly.

    This test would have caught the project_name="unknown" bug by asserting
    the actual parameter value passed to Memgraph.
    """
    file_data = {
        "entity_id": "file:omniarchon:services/app.py",
        "name": "app.py",
        "path": "services/intelligence/app.py",
        "relative_path": "services/intelligence/app.py",
        "project_name": "omniarchon",  # CRITICAL: Must be preserved
        "file_size": 125000,
        "language": "python",
        "line_count": 2800,
    }

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={
            "file_id": file_data["entity_id"],
            "name": "app.py",
            "language": "python",
        }
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_node(file_data)

    # Assert success
    assert success is True

    # CRITICAL: Verify project_name parameter was set correctly
    mock_session.run.assert_called_once()
    call_args = mock_session.run.call_args
    params = call_args[0][1]  # Second argument is params dict

    # This assertion would have FAILED with the bug (value would be "unknown")
    assert params["project_name"] == "omniarchon", (
        f"project_name should be 'omniarchon' but was '{params['project_name']}'. "
        "The fallback to 'unknown' should NEVER happen when project_name is provided!"
    )


@pytest.mark.asyncio
async def test_create_file_node_rejects_unknown_project_name(adapter, mock_session):
    """
    CRITICAL TEST: Should never accept 'unknown' as valid project_name.

    This test validates that when project_name is explicitly provided,
    it should NEVER fall back to "unknown".
    """
    file_data = {
        "entity_id": "file:myproject:src/main.py",
        "name": "main.py",
        "path": "src/main.py",
        "project_name": "myproject",  # Explicit project provided
    }

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={
            "file_id": file_data["entity_id"],
            "name": "main.py",
            "language": "unknown",
        }
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_node(file_data)

    # Assert
    assert success is True
    call_args = mock_session.run.call_args
    params = call_args[0][1]

    # CRITICAL: Must NOT be "unknown" when project_name was provided
    assert (
        params["project_name"] != "unknown"
    ), "project_name should NEVER be 'unknown' when explicitly provided in file_data"
    assert params["project_name"] == "myproject"


@pytest.mark.asyncio
async def test_create_file_node_fallback_to_project_id(adapter, mock_session):
    """Test fallback to project_id when project_name is missing."""
    file_data = {
        "entity_id": "file:test_project:main.py",
        "name": "main.py",
        "path": "main.py",
        "project_id": "test_project",  # Fallback value
        # Note: project_name is intentionally missing
    }

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={
            "file_id": file_data["entity_id"],
            "name": "main.py",
            "language": "unknown",
        }
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_node(file_data)

    # Assert
    assert success is True
    call_args = mock_session.run.call_args
    params = call_args[0][1]

    # Should use project_id as fallback
    assert params["project_name"] == "test_project"


@pytest.mark.asyncio
async def test_create_file_node_fallback_to_unknown_only_when_no_metadata(
    adapter, mock_session
):
    """Test that 'unknown' fallback only happens when NO project metadata exists."""
    file_data = {
        "entity_id": "file:unknown:orphan.py",
        "name": "orphan.py",
        "path": "orphan.py",
        # Both project_name and project_id are intentionally missing
    }

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={
            "file_id": file_data["entity_id"],
            "name": "orphan.py",
            "language": "unknown",
        }
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_node(file_data)

    # Assert
    assert success is True
    call_args = mock_session.run.call_args
    params = call_args[0][1]

    # Only in this case should it be "unknown"
    assert params["project_name"] == "unknown"


@pytest.mark.asyncio
async def test_create_file_node_validates_required_fields(adapter):
    """Test that required fields are validated before execution."""
    # Missing required field: path
    file_data = {
        "entity_id": "file:test:main.py",
        "name": "main.py",
        # path is missing
    }

    success = await adapter.create_file_node(file_data)

    # Should fail due to missing required field
    assert success is False


@pytest.mark.asyncio
async def test_create_file_node_handles_empty_data(adapter):
    """Test handling of empty file_data."""
    success = await adapter.create_file_node({})
    assert success is False

    success = await adapter.create_file_node(None)
    assert success is False


@pytest.mark.asyncio
async def test_create_file_node_on_match_updates_project_name(adapter, mock_session):
    """
    CRITICAL TEST: Validates that ON MATCH clause updates project_name.

    This ensures that if a file node exists but has wrong project_name,
    it gets corrected on update.
    """
    file_data = {
        "entity_id": "file:corrected_project:main.py",
        "name": "main.py",
        "path": "main.py",
        "project_name": "corrected_project",  # Should update existing node
        "file_size": 1000,
        "line_count": 50,
    }

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={
            "file_id": file_data["entity_id"],
            "name": "main.py",
            "language": "unknown",
        }
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_node(file_data)

    # Assert
    assert success is True
    call_args = mock_session.run.call_args
    query = call_args[0][0]
    params = call_args[0][1]

    # Verify ON MATCH clause includes project_name update
    assert "ON MATCH SET" in query
    assert "f.project_name = $project_name" in query
    assert params["project_name"] == "corrected_project"


@pytest.mark.asyncio
async def test_create_file_node_handles_special_characters_in_project_name(
    adapter, mock_session
):
    """Test handling of special characters in project_name."""
    file_data = {
        "entity_id": "file:my-project_2.0:main.py",
        "name": "main.py",
        "path": "main.py",
        "project_name": "my-project_2.0",  # Special chars: dash, underscore, dot
    }

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={
            "file_id": file_data["entity_id"],
            "name": "main.py",
            "language": "unknown",
        }
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_node(file_data)

    # Assert
    assert success is True
    call_args = mock_session.run.call_args
    params = call_args[0][1]

    # Special characters should be preserved
    assert params["project_name"] == "my-project_2.0"


@pytest.mark.asyncio
async def test_create_file_node_comprehensive_metadata(adapter, mock_session):
    """Test that all metadata fields are properly set."""
    timestamp = datetime.now(timezone.utc).isoformat()
    file_data = {
        "entity_id": "file:test:complete.py",
        "name": "complete.py",
        "path": "src/complete.py",
        "relative_path": "src/complete.py",
        "project_name": "test_project",
        "file_size": 5000,
        "language": "python",
        "file_hash": "abc123def456",
        "last_modified": timestamp,
        "indexed_at": timestamp,
        "content_type": "code",
        "line_count": 150,
        "entity_count": 25,
        "import_count": 10,
    }

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={
            "file_id": file_data["entity_id"],
            "name": "complete.py",
            "language": "python",
        }
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_node(file_data)

    # Assert
    assert success is True
    call_args = mock_session.run.call_args
    params = call_args[0][1]

    # Validate all fields are passed correctly
    assert params["entity_id"] == "file:test:complete.py"
    assert params["name"] == "complete.py"
    assert params["path"] == "src/complete.py"
    assert params["relative_path"] == "src/complete.py"
    assert params["project_name"] == "test_project"
    assert params["file_size"] == 5000
    assert params["language"] == "python"
    assert params["file_hash"] == "abc123def456"
    assert params["last_modified"] == timestamp
    assert params["indexed_at"] == timestamp
    assert params["content_type"] == "code"
    assert params["line_count"] == 150
    assert params["entity_count"] == 25
    assert params["import_count"] == 10


# ============================================================================
# FILE IMPORT RELATIONSHIP OPERATIONS
# ============================================================================


@pytest.mark.asyncio
async def test_create_file_import_relationship_success(adapter, mock_session):
    """Test successful creation of IMPORTS relationship."""
    source_id = "file:myproject:src/main.py"
    target_id = "file:myproject:src/utils.py"

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={"source": source_id, "target": target_id}
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_import_relationship(
        source_id=source_id,
        target_id=target_id,
        import_type="module",
        confidence=1.0,
    )

    # Assert
    assert success is True
    mock_session.run.assert_called_once()


@pytest.mark.asyncio
async def test_create_file_import_relationship_extracts_project_name(
    adapter, mock_session
):
    """Test that project_name is correctly extracted from entity_id."""
    source_id = "file:project_alpha:main.py"
    target_id = "file:project_beta:utils.py"

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={"source": source_id, "target": target_id}
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_import_relationship(
        source_id=source_id, target_id=target_id
    )

    # Assert
    assert success is True
    call_args = mock_session.run.call_args
    params = call_args[0][1]

    # Verify project names extracted correctly
    assert params["source_project_name"] == "project_alpha"
    assert params["target_project_name"] == "project_beta"


@pytest.mark.asyncio
async def test_create_file_import_relationship_creates_placeholder_nodes(
    adapter, mock_session
):
    """Test that placeholder FILE nodes are created for missing targets."""
    source_id = "file:project:source.py"
    target_id = "file:project:nonexistent.py"

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={"source": source_id, "target": target_id}
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_import_relationship(
        source_id=source_id, target_id=target_id
    )

    # Assert
    assert success is True
    call_args = mock_session.run.call_args
    query = call_args[0][0]

    # Verify MERGE creates nodes if they don't exist
    assert "MERGE (source:File {entity_id: $source_id})" in query
    assert "MERGE (target:File {entity_id: $target_id})" in query
    assert "ON CREATE SET" in query


@pytest.mark.asyncio
async def test_create_file_import_relationship_validates_parameters(adapter):
    """Test validation of required parameters."""
    # Missing source_id
    success = await adapter.create_file_import_relationship(
        source_id="", target_id="file:test:target.py"
    )
    assert success is False

    # Missing target_id
    success = await adapter.create_file_import_relationship(
        source_id="file:test:source.py", target_id=""
    )
    assert success is False


# ============================================================================
# ENTITY OPERATIONS
# ============================================================================


@pytest.mark.asyncio
async def test_store_entities_success(adapter, mock_session):
    """Test successful storage of multiple entities."""
    entities = [
        KnowledgeEntity(
            entity_id="entity_1",
            name="TestClass",
            entity_type=EntityType.CLASS,
            description="Test class",
            source_path="test.py",
            confidence_score=0.95,
            metadata=EntityMetadata(),
        ),
        KnowledgeEntity(
            entity_id="entity_2",
            name="test_function",
            entity_type=EntityType.FUNCTION,
            description="Test function",
            source_path="test.py",
            confidence_score=0.90,
            metadata=EntityMetadata(),
        ),
    ]

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        side_effect=[{"stored_id": "entity_1"}, {"stored_id": "entity_2"}]
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    stored_count = await adapter.store_entities(entities)

    # Assert
    assert stored_count == 2
    assert mock_session.run.call_count == 2


@pytest.mark.asyncio
async def test_store_entities_handles_empty_list(adapter):
    """Test handling of empty entity list."""
    stored_count = await adapter.store_entities([])
    assert stored_count == 0


@pytest.mark.asyncio
async def test_store_entities_continues_on_individual_failure(adapter, mock_session):
    """Test that entity storage continues after individual entity failures."""
    entities = [
        KnowledgeEntity(
            entity_id="entity_1",
            name="Success",
            entity_type=EntityType.CLASS,
            description="Will succeed",
            source_path="test.py",
            confidence_score=0.95,
            metadata=EntityMetadata(),
        ),
        KnowledgeEntity(
            entity_id="entity_2",
            name="Failure",
            entity_type=EntityType.CLASS,
            description="Will fail",
            source_path="test.py",
            confidence_score=0.95,
            metadata=EntityMetadata(),
        ),
        KnowledgeEntity(
            entity_id="entity_3",
            name="Success2",
            entity_type=EntityType.CLASS,
            description="Will succeed",
            source_path="test.py",
            confidence_score=0.95,
            metadata=EntityMetadata(),
        ),
    ]

    # Setup mock: second entity fails
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        side_effect=[
            {"stored_id": "entity_1"},
            Exception("Database error"),
            {"stored_id": "entity_3"},
        ]
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    stored_count = await adapter.store_entities(entities)

    # Assert: 2 succeeded, 1 failed
    assert stored_count == 2


# ============================================================================
# RELATIONSHIP OPERATIONS
# ============================================================================


@pytest.mark.asyncio
async def test_store_relationships_success(adapter, mock_session):
    """Test successful storage of relationships."""
    relationships = [
        KnowledgeRelationship(
            relationship_id="rel_1",
            source_entity_id="entity_1",
            target_entity_id="entity_2",
            relationship_type=RelationshipType.CALLS,
            confidence_score=0.95,
        ),
    ]

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value={"stored_id": "rel_1"})
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    stored_count = await adapter.store_relationships(relationships)

    # Assert
    assert stored_count == 1
    mock_session.run.assert_called_once()


@pytest.mark.asyncio
async def test_store_relationships_creates_stub_nodes(adapter, mock_session):
    """Test that stub nodes are created for missing entities."""
    relationships = [
        KnowledgeRelationship(
            relationship_id="rel_1",
            source_entity_id="missing_source",
            target_entity_id="missing_target",
            relationship_type=RelationshipType.DEPENDS_ON,
            confidence_score=0.80,
        ),
    ]

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value={"stored_id": "rel_1"})
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    stored_count = await adapter.store_relationships(relationships)

    # Assert
    assert stored_count == 1
    call_args = mock_session.run.call_args
    query = call_args[0][0]

    # Verify stub node creation
    assert "ON CREATE SET source.name = $source_id" in query
    assert "source.is_stub = true" in query
    assert "target.is_stub = true" in query


@pytest.mark.asyncio
async def test_store_relationships_handles_empty_list(adapter):
    """Test handling of empty relationship list."""
    stored_count = await adapter.store_relationships([])
    assert stored_count == 0


# ============================================================================
# SEARCH & QUERY OPERATIONS
# ============================================================================


@pytest.mark.asyncio
async def test_search_entities_success(adapter, mock_session):
    """Test successful entity search."""
    # Setup mock
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(
        return_value=[
            {
                "e": {
                    "entity_id": "entity_1",
                    "name": "TestClass",
                    "entity_type": "CLASS",
                    "description": "A test class",
                    "source_path": "test.py",
                    "confidence_score": 0.95,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        ]
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    results = await adapter.search_entities(query="TestClass", limit=10)

    # Assert
    assert len(results) == 1
    assert results[0].name == "TestClass"
    assert results[0].entity_type == EntityType.CLASS


@pytest.mark.asyncio
async def test_search_entities_with_filters(adapter, mock_session):
    """Test entity search with entity_type filter."""
    # Setup mock
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(return_value=[])
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    results = await adapter.search_entities(
        query="test", entity_type="FUNCTION", min_confidence=0.8, limit=5
    )

    # Assert
    call_args = mock_session.run.call_args
    params = call_args[0][1]
    assert params["entity_type"] == "FUNCTION"
    assert params["min_confidence"] == 0.8
    assert params["limit"] == 5


@pytest.mark.asyncio
async def test_get_entity_relationships_success(adapter, mock_session):
    """Test retrieval of entity relationships."""
    # Setup mock
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(
        return_value=[
            {
                "r": {"relationship_type": "CALLS", "confidence_score": 0.95},
                "source": {
                    "entity_id": "entity_1",
                    "name": "Source",
                    "entity_type": "FUNCTION",
                    "confidence_score": 0.95,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                "target": {
                    "entity_id": "entity_2",
                    "name": "Target",
                    "entity_type": "FUNCTION",
                    "confidence_score": 0.95,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            }
        ]
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    results = await adapter.get_entity_relationships(entity_id="entity_1", limit=20)

    # Assert
    assert len(results) == 1
    assert results[0]["source_entity"].name == "Source"
    assert results[0]["target_entity"].name == "Target"


# ============================================================================
# STATISTICS & ANALYTICS
# ============================================================================


@pytest.mark.asyncio
async def test_get_entity_statistics_success(adapter, mock_session):
    """Test retrieval of entity statistics."""
    # Setup mock
    mock_entity_stats = AsyncMock()
    mock_entity_stats.data = AsyncMock(
        return_value=[
            {"type": "FUNCTION", "count": 100},
            {"type": "CLASS", "count": 50},
        ]
    )

    mock_rel_stats = AsyncMock()
    mock_rel_stats.data = AsyncMock(
        return_value=[
            {"type": "CALLS", "count": 200},
            {"type": "USES", "count": 150},
        ]
    )

    mock_total_entities = AsyncMock()
    mock_total_entities.single = AsyncMock(return_value={"total": 150})

    mock_total_rels = AsyncMock()
    mock_total_rels.single = AsyncMock(return_value={"total": 350})

    mock_session.run = AsyncMock(
        side_effect=[
            mock_entity_stats,
            mock_rel_stats,
            mock_total_entities,
            mock_total_rels,
        ]
    )
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    stats = await adapter.get_entity_statistics()

    # Assert
    assert stats["total_entities"] == 150
    assert stats["total_relationships"] == 350
    assert stats["entity_counts_by_type"]["FUNCTION"] == 100
    assert stats["entity_counts_by_type"]["CLASS"] == 50
    assert stats["relationship_counts_by_type"]["CALLS"] == 200


# ============================================================================
# RETRY LOGIC & ERROR HANDLING
# ============================================================================


@pytest.mark.asyncio
async def test_retry_decorator_handles_transient_error():
    """Test retry decorator retries on TransientError."""
    attempt_count = 0

    @retry_on_transient_error(max_attempts=3, initial_backoff=0.01)
    async def flaky_function():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise Exception("TransientError: conflicting transactions")
        return "success"

    result = await flaky_function()

    assert result == "success"
    assert attempt_count == 3  # Succeeded on 3rd attempt


@pytest.mark.asyncio
async def test_retry_decorator_raises_non_transient_error():
    """Test retry decorator raises non-transient errors immediately."""
    attempt_count = 0

    @retry_on_transient_error(max_attempts=3, initial_backoff=0.01)
    async def failing_function():
        nonlocal attempt_count
        attempt_count += 1
        raise ValueError("Database connection failed")

    with pytest.raises(ValueError, match="Database connection failed"):
        await failing_function()

    # Should not retry non-transient errors
    assert attempt_count == 1


@pytest.mark.asyncio
async def test_retry_decorator_exhausts_retries():
    """Test retry decorator raises after exhausting retries."""

    @retry_on_transient_error(max_attempts=2, initial_backoff=0.01)
    async def always_fails():
        raise Exception("TransientError: always fails")

    with pytest.raises(Exception, match="TransientError"):
        await always_fails()


# NOTE: Retry logic for create_file_node is tested via the retry decorator tests.
# Testing retry through the full method is complex due to internal exception handling.
# The decorator tests (test_retry_decorator_*) provide comprehensive retry coverage.


# ============================================================================
# EDGE CASES & VALIDATION
# ============================================================================


@pytest.mark.asyncio
async def test_create_file_node_handles_null_optional_fields(adapter, mock_session):
    """Test handling of null/missing optional fields."""
    file_data = {
        "entity_id": "file:test:minimal.py",
        "name": "minimal.py",
        "path": "minimal.py",
        # All optional fields missing
    }

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(
        return_value={
            "file_id": "file:test:minimal.py",
            "name": "minimal.py",
            "language": "unknown",
        }
    )
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    success = await adapter.create_file_node(file_data)

    # Assert
    assert success is True
    call_args = mock_session.run.call_args
    params = call_args[0][1]

    # Verify defaults are applied
    assert params["file_size"] == 0
    assert params["language"] == "unknown"
    assert params["line_count"] == 0
    assert params["entity_count"] == 0
    assert params["import_count"] == 0
    assert params["content_type"] == "code"


@pytest.mark.asyncio
async def test_concurrency_throttling(adapter):
    """Test that write semaphore limits concurrent operations."""
    # Adapter should have semaphore configured
    assert adapter._write_semaphore is not None
    assert adapter._max_concurrent_writes == int(
        adapter._write_semaphore._value
    )  # Default 10


# ============================================================================
# PERFORMANCE & METRICS
# ============================================================================


@pytest.mark.asyncio
async def test_store_entities_tracks_metrics(adapter, mock_session):
    """Test that entity storage tracks success/failure metrics."""
    entities = [
        KnowledgeEntity(
            entity_id="entity_1",
            name="Test",
            entity_type=EntityType.CLASS,
            description="Test",
            source_path="test.py",
            confidence_score=0.95,
            metadata=EntityMetadata(),
        ),
    ]

    # Setup mock
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value={"stored_id": "entity_1"})
    mock_session.run = AsyncMock(return_value=mock_result)
    adapter.driver.session = MagicMock(return_value=mock_session)

    # Execute
    initial_writes = adapter._total_writes
    stored_count = await adapter.store_entities(entities)

    # Assert metrics tracked
    assert stored_count == 1
    assert adapter._total_writes == initial_writes + 1
