# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for Part 2 enrichment repository methods (OMN-5676).

These tests verify the repository method signatures and SQL generation
without requiring a live database connection.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.repository.repository_code_entity import (
    RepositoryCodeEntity,
)


@pytest.fixture
def mock_pool() -> MagicMock:
    """Create a mock asyncpg pool."""
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="UPDATE 1")
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[])
    return pool


@pytest.mark.unit
class TestRepositoryEnrichment:
    """Tests for Part 2 enrichment repository methods."""

    @pytest.mark.asyncio
    async def test_update_deterministic_classification(
        self, mock_pool: MagicMock
    ) -> None:
        """update_deterministic_classification writes correct columns."""
        repo = RepositoryCodeEntity(mock_pool)
        alternatives = json.dumps({"compute": 0.45, "reducer": 0.2})
        meta_patch = json.dumps(
            {"classify": {"config_hash": "abc123", "stage_version": "1.0.0"}}
        )

        await repo.update_deterministic_classification(
            entity_id="550e8400-e29b-41d4-a716-446655440000",
            node_type="effect",
            confidence=0.82,
            alternatives=alternatives,
            enrichment_meta_patch=meta_patch,
        )

        mock_pool.execute.assert_called_once()
        call_args = mock_pool.execute.call_args
        sql = call_args[0][0]
        assert "deterministic_node_type" in sql
        assert "deterministic_confidence" in sql
        assert "deterministic_alternatives" in sql
        assert "enrichment_metadata" in sql
        # Verify positional args
        assert call_args[0][2] == "effect"  # $2 = node_type
        assert call_args[0][3] == 0.82  # $3 = confidence

    @pytest.mark.asyncio
    async def test_update_quality_score(self, mock_pool: MagicMock) -> None:
        """update_quality_score writes correct columns."""
        repo = RepositoryCodeEntity(mock_pool)
        dimensions = json.dumps({"complexity": 0.7, "maintainability": 0.8})
        meta_patch = json.dumps(
            {"quality": {"config_hash": "def456", "stage_version": "1.0.0"}}
        )

        await repo.update_quality_score(
            entity_id="550e8400-e29b-41d4-a716-446655440000",
            quality_score=0.75,
            quality_dimensions=dimensions,
            enrichment_meta_patch=meta_patch,
        )

        mock_pool.execute.assert_called_once()
        call_args = mock_pool.execute.call_args
        sql = call_args[0][0]
        assert "quality_score" in sql
        assert "quality_dimensions" in sql
        assert "enrichment_metadata" in sql
        assert call_args[0][2] == 0.75  # $2 = quality_score

    @pytest.mark.asyncio
    async def test_get_entity_enrichment_metadata(self, mock_pool: MagicMock) -> None:
        """get_entity_enrichment_metadata returns file_hash and metadata."""
        mock_pool.fetchrow.return_value = {
            "file_hash": "abc123",
            "enrichment_metadata": {"classify": {"config_hash": "x"}},
        }
        repo = RepositoryCodeEntity(mock_pool)

        result = await repo.get_entity_enrichment_metadata(
            "550e8400-e29b-41d4-a716-446655440000"
        )

        assert result is not None
        assert result["file_hash"] == "abc123"
        assert result["enrichment_metadata"]["classify"]["config_hash"] == "x"

    @pytest.mark.asyncio
    async def test_get_entity_enrichment_metadata_not_found(
        self, mock_pool: MagicMock
    ) -> None:
        """get_entity_enrichment_metadata returns None if entity not found."""
        mock_pool.fetchrow.return_value = None
        repo = RepositoryCodeEntity(mock_pool)

        result = await repo.get_entity_enrichment_metadata("nonexistent")
        assert result is None
