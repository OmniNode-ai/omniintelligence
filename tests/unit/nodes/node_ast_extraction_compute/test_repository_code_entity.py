# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Unit tests for RepositoryCodeEntity.

Tests verify SQL calls with correct parameters using mocked asyncpg pool.
No real database required.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.repository.repository_code_entity import (
    RepositoryCodeEntity,
)


def _make_pool() -> AsyncMock:
    """Create a mock asyncpg pool with async methods."""
    pool = AsyncMock()
    pool.fetchrow = AsyncMock()
    pool.fetch = AsyncMock()
    pool.execute = AsyncMock()
    return pool


def _sample_entity(
    *,
    qualified_name: str = "omnibase_core.models.MyModel",
    file_hash: str = "abc123",
) -> dict[str, Any]:
    return {
        "entity_name": "MyModel",
        "entity_type": "class",
        "qualified_name": qualified_name,
        "source_repo": "omnibase_core",
        "source_path": "src/omnibase_core/models/my_model.py",
        "line_number": 10,
        "bases": ["BaseModel"],
        "methods": [
            {
                "name": "__init__",
                "args": ["self"],
                "return_type": "None",
                "decorators": [],
            }
        ],
        "fields": [{"name": "id", "type": "UUID", "default": None}],
        "decorators": [],
        "docstring": "A sample model.",
        "signature": None,
        "file_hash": file_hash,
    }


@pytest.mark.unit
class TestUpsertEntity:
    """Test upsert_entity inserts and updates correctly."""

    async def test_upsert_entity_returns_uuid(self) -> None:
        """upsert_entity calls fetchrow with correct SQL and returns UUID string."""
        pool = _make_pool()
        entity_id = uuid4()
        pool.fetchrow.return_value = {"id": entity_id}

        repo = RepositoryCodeEntity(pool)
        entity = _sample_entity()
        result = await repo.upsert_entity(entity)

        assert result == str(entity_id)
        pool.fetchrow.assert_called_once()

        # Verify the positional args match entity values
        call_args = pool.fetchrow.call_args
        positional = call_args[0]
        sql = positional[0]
        assert "INSERT INTO code_entities" in sql
        assert "ON CONFLICT (qualified_name, source_repo) DO UPDATE" in sql
        assert "RETURNING id" in sql

        # Args after SQL: entity_name, entity_type, qualified_name, source_repo, source_path,
        # line_number, bases, methods(json), fields(json), decorators, docstring, signature, file_hash
        assert positional[1] == "MyModel"
        assert positional[2] == "class"
        assert positional[3] == "omnibase_core.models.MyModel"
        assert positional[4] == "omnibase_core"
        assert positional[5] == "src/omnibase_core/models/my_model.py"
        assert positional[6] == 10
        assert positional[7] == ["BaseModel"]
        # methods and fields are JSON-serialized
        assert json.loads(positional[8]) == entity["methods"]
        assert json.loads(positional[9]) == entity["fields"]
        assert positional[13] == "abc123"

    async def test_upsert_entity_same_id_on_re_upsert(self) -> None:
        """Re-upserting with different file_hash returns same id (row updated, not duplicated)."""
        pool = _make_pool()
        entity_id = uuid4()
        pool.fetchrow.return_value = {"id": entity_id}

        repo = RepositoryCodeEntity(pool)

        # First upsert
        entity_v1 = _sample_entity(file_hash="hash_v1")
        result_v1 = await repo.upsert_entity(entity_v1)

        # Second upsert with different hash (simulates file change)
        entity_v2 = _sample_entity(file_hash="hash_v2")
        result_v2 = await repo.upsert_entity(entity_v2)

        # Both should return the same entity ID (ON CONFLICT updates, doesn't insert new)
        assert result_v1 == str(entity_id)
        assert result_v2 == str(entity_id)
        assert pool.fetchrow.call_count == 2

        # Verify the second call used the new file_hash
        second_call_args = pool.fetchrow.call_args_list[1][0]
        assert second_call_args[13] == "hash_v2"

    async def test_upsert_entity_none_jsonb_fields(self) -> None:
        """upsert_entity handles None methods/fields (passes None, not 'null')."""
        pool = _make_pool()
        pool.fetchrow.return_value = {"id": uuid4()}

        repo = RepositoryCodeEntity(pool)
        entity = _sample_entity()
        entity["methods"] = None
        entity["fields"] = None

        await repo.upsert_entity(entity)

        call_args = pool.fetchrow.call_args[0]
        # methods and fields should be None, not "null"
        assert call_args[8] is None
        assert call_args[9] is None


@pytest.mark.unit
class TestCheckFileHash:
    """Test check_file_hash skip optimization."""

    async def test_check_file_hash_returns_true_when_match(self) -> None:
        """check_file_hash returns True when entity exists with matching hash."""
        pool = _make_pool()
        pool.fetchrow.return_value = {"?column?": 1}

        repo = RepositoryCodeEntity(pool)
        result = await repo.check_file_hash(
            "omnibase_core.models.MyModel", "omnibase_core", "abc123"
        )

        assert result is True
        pool.fetchrow.assert_called_once()
        call_args = pool.fetchrow.call_args[0]
        assert "file_hash = $3" in call_args[0]
        assert call_args[1] == "omnibase_core.models.MyModel"
        assert call_args[2] == "omnibase_core"
        assert call_args[3] == "abc123"

    async def test_check_file_hash_returns_false_when_no_match(self) -> None:
        """check_file_hash returns False when no entity with matching hash."""
        pool = _make_pool()
        pool.fetchrow.return_value = None

        repo = RepositoryCodeEntity(pool)
        result = await repo.check_file_hash(
            "omnibase_core.models.MyModel", "omnibase_core", "different_hash"
        )

        assert result is False

    async def test_check_file_hash_returns_false_when_entity_missing(self) -> None:
        """check_file_hash returns False when entity does not exist at all."""
        pool = _make_pool()
        pool.fetchrow.return_value = None

        repo = RepositoryCodeEntity(pool)
        result = await repo.check_file_hash("nonexistent.Foo", "some_repo", "any_hash")

        assert result is False


@pytest.mark.unit
class TestGetEntityIdByQualifiedName:
    """Test entity ID lookup."""

    async def test_returns_id_when_found(self) -> None:
        pool = _make_pool()
        entity_id = uuid4()
        pool.fetchrow.return_value = {"id": entity_id}

        repo = RepositoryCodeEntity(pool)
        result = await repo.get_entity_id_by_qualified_name(
            "omnibase_core.models.MyModel", "omnibase_core"
        )

        assert result == str(entity_id)

    async def test_returns_none_when_not_found(self) -> None:
        pool = _make_pool()
        pool.fetchrow.return_value = None

        repo = RepositoryCodeEntity(pool)
        result = await repo.get_entity_id_by_qualified_name(
            "nonexistent.Foo", "some_repo"
        )

        assert result is None


@pytest.mark.unit
class TestDeleteStaleEntities:
    """Test zombie entity cleanup."""

    async def test_delete_stale_entities_with_current_names(self) -> None:
        pool = _make_pool()
        pool.execute.return_value = "DELETE 2"

        repo = RepositoryCodeEntity(pool)
        result = await repo.delete_stale_entities(
            "src/foo.py", "my_repo", ["foo.Bar", "foo.Baz"]
        )

        assert result == 2
        call_args = pool.execute.call_args[0]
        assert "!= ALL($3)" in call_args[0]

    async def test_delete_stale_entities_empty_list_deletes_all(self) -> None:
        pool = _make_pool()
        pool.execute.return_value = "DELETE 5"

        repo = RepositoryCodeEntity(pool)
        result = await repo.delete_stale_entities("src/foo.py", "my_repo", [])

        assert result == 5
        call_args = pool.execute.call_args[0]
        assert "ALL" not in call_args[0]


@pytest.mark.unit
class TestGetEntitiesNeeding:
    """Test query methods for enrichment and embedding pipelines."""

    async def test_get_entities_needing_enrichment(self) -> None:
        pool = _make_pool()
        pool.fetch.return_value = [
            {
                "id": uuid4(),
                "entity_name": "Foo",
                "entity_type": "class",
                "qualified_name": "mod.Foo",
                "source_repo": "repo",
                "source_path": "src/foo.py",
                "docstring": "A class",
                "signature": None,
                "bases": None,
                "methods": None,
                "fields": None,
                "decorators": None,
            },
        ]

        repo = RepositoryCodeEntity(pool)
        result = await repo.get_entities_needing_enrichment(limit=10)

        assert len(result) == 1
        assert result[0]["entity_name"] == "Foo"
        call_args = pool.fetch.call_args[0]
        assert "classification IS NULL" in call_args[0]
        assert call_args[1] == 10

    async def test_get_entities_needing_embedding(self) -> None:
        pool = _make_pool()
        pool.fetch.return_value = []

        repo = RepositoryCodeEntity(pool)
        result = await repo.get_entities_needing_embedding(limit=50)

        assert result == []
        call_args = pool.fetch.call_args[0]
        assert "last_embedded_at IS NULL" in call_args[0]
        assert call_args[1] == 50


@pytest.mark.unit
class TestUpdateMethods:
    """Test timestamp update methods."""

    async def test_update_enrichment(self) -> None:
        pool = _make_pool()
        repo = RepositoryCodeEntity(pool)

        await repo.update_enrichment(
            entity_id=str(uuid4()),
            classification="protocol",
            llm_description="A protocol for pattern storage",
            architectural_pattern="repository",
            classification_confidence=0.95,
            enrichment_version="v1",
        )

        pool.execute.assert_called_once()
        call_args = pool.execute.call_args[0]
        assert "classification = $2" in call_args[0]
        assert "last_enriched_at = NOW()" in call_args[0]

    async def test_update_embedded_at(self) -> None:
        pool = _make_pool()
        repo = RepositoryCodeEntity(pool)
        ids = [str(uuid4()), str(uuid4())]

        await repo.update_embedded_at(ids)

        pool.execute.assert_called_once()
        call_args = pool.execute.call_args[0]
        assert "last_embedded_at = NOW()" in call_args[0]
        assert call_args[1] == ids

    async def test_update_graph_synced_at(self) -> None:
        pool = _make_pool()
        repo = RepositoryCodeEntity(pool)
        ids = [str(uuid4())]

        await repo.update_graph_synced_at(ids)

        pool.execute.assert_called_once()
        call_args = pool.execute.call_args[0]
        assert "last_graph_synced_at = NOW()" in call_args[0]
