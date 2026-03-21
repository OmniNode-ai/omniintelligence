# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for code embedding dispatch handler.

Validates:
    - Embedding text assembly from tiered fields (primary + secondary)
    - Qdrant upsert with correct PointStruct (point ID = entity UUID, payload metadata)

Related:
    - OMN-5665: Embedding generation and Qdrant storage
    - OMN-5657: AST-based code pattern extraction system (epic)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from omniintelligence.runtime.dispatch_handler_code_embedding import (
    QDRANT_COLLECTION,
    build_embedding_text,
    handle_code_embedding,
)

# =============================================================================
# Fixtures
# =============================================================================


def _make_entity(**overrides: Any) -> dict[str, Any]:
    """Create a test entity dict with sensible defaults."""
    entity: dict[str, Any] = {
        "id": overrides.pop("id", uuid4()),
        "entity_name": "MyClass",
        "entity_type": "class",
        "qualified_name": "mypackage.mymodule.MyClass",
        "source_repo": "omniintelligence",
        "source_path": "src/omniintelligence/models/my_class.py",
        "docstring": "A sample class for testing.",
        "signature": "class MyClass(BaseModel):",
        "classification": "model",
        "llm_description": None,
    }
    entity.update(overrides)
    return entity


# =============================================================================
# Test: embedding text assembly
# =============================================================================


@pytest.mark.unit
class TestBuildEmbeddingText:
    """Test build_embedding_text tiered field concatenation."""

    def test_primary_fields_only(self) -> None:
        """Entity without llm_description uses primary fields only."""
        entity = _make_entity(llm_description=None)
        text = build_embedding_text(entity)

        assert "MyClass" in text
        assert "class MyClass(BaseModel):" in text
        assert "A sample class for testing." in text
        # No newline separator when no secondary fields
        assert "\n" not in text

    def test_primary_and_secondary_fields(self) -> None:
        """Entity with llm_description includes secondary after newline."""
        entity = _make_entity(llm_description="An LLM-generated description.")
        text = build_embedding_text(entity)

        assert "MyClass" in text
        assert "class MyClass(BaseModel):" in text
        assert "A sample class for testing." in text
        # Secondary field after newline
        assert "\n" in text
        assert "An LLM-generated description." in text.split("\n")[1]

    def test_empty_entity_returns_empty(self) -> None:
        """Entity with no text fields returns empty string."""
        entity = _make_entity(
            entity_name="",
            signature=None,
            docstring=None,
            llm_description=None,
        )
        text = build_embedding_text(entity)
        assert text.strip() == ""

    def test_partial_primary_fields(self) -> None:
        """Entity with only entity_name still produces text."""
        entity = _make_entity(signature=None, docstring=None, llm_description=None)
        text = build_embedding_text(entity)
        assert text == "MyClass"


# =============================================================================
# Test: Qdrant upsert
# =============================================================================


@pytest.mark.unit
class TestHandleCodeEmbedding:
    """Test handle_code_embedding Qdrant upsert and repository update."""

    @pytest.mark.asyncio
    async def test_upsert_called_with_correct_point(self) -> None:
        """Verify Qdrant upsert receives PointStruct with entity UUID as point ID."""
        entity_id = uuid4()
        entity = _make_entity(id=entity_id)

        mock_repository = MagicMock()
        mock_repository.get_entities_needing_embedding = AsyncMock(
            return_value=[entity]
        )
        mock_repository.update_embedded_at = AsyncMock()

        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value = MagicMock(
            collections=[MagicMock(name=QDRANT_COLLECTION)]
        )
        mock_qdrant.upsert = MagicMock()

        fake_embedding = [0.1] * 4096

        with patch(
            "omniintelligence.runtime.dispatch_handler_code_embedding.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"data": [{"embedding": fake_embedding}]}

            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_http

            result = await handle_code_embedding(
                repository=mock_repository,
                qdrant_client=mock_qdrant,
                embedding_endpoint="http://test:8100",
            )

        assert result == {"embedded_count": 1, "failed_count": 0}

        # Verify upsert call
        mock_qdrant.upsert.assert_called_once()
        call_kwargs = mock_qdrant.upsert.call_args
        assert call_kwargs.kwargs["collection_name"] == QDRANT_COLLECTION

        points = call_kwargs.kwargs["points"]
        assert len(points) == 1
        point = points[0]
        assert point.id == str(entity_id)
        assert point.vector == fake_embedding
        assert point.payload["entity_id"] == str(entity_id)
        assert point.payload["entity_name"] == "MyClass"
        assert point.payload["entity_type"] == "class"
        assert point.payload["qualified_name"] == "mypackage.mymodule.MyClass"
        assert point.payload["source_repo"] == "omniintelligence"

        # Verify repository timestamp update
        mock_repository.update_embedded_at.assert_awaited_once_with([str(entity_id)])

    @pytest.mark.asyncio
    async def test_embedding_failure_increments_failed_count(self) -> None:
        """When embedding endpoint fails, entity is counted as failed."""
        entity = _make_entity()

        mock_repository = MagicMock()
        mock_repository.get_entities_needing_embedding = AsyncMock(
            return_value=[entity]
        )
        mock_repository.update_embedded_at = AsyncMock()

        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value = MagicMock(
            collections=[MagicMock(name=QDRANT_COLLECTION)]
        )

        with patch(
            "omniintelligence.runtime.dispatch_handler_code_embedding.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post.side_effect = Exception("Connection refused")
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_http

            result = await handle_code_embedding(
                repository=mock_repository,
                qdrant_client=mock_qdrant,
                embedding_endpoint="http://test:8100",
            )

        assert result == {"embedded_count": 0, "failed_count": 1}
        mock_repository.update_embedded_at.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_entities_returns_zero_counts(self) -> None:
        """When no entities need embedding, return zero counts immediately."""
        mock_repository = MagicMock()
        mock_repository.get_entities_needing_embedding = AsyncMock(return_value=[])

        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value = MagicMock(
            collections=[MagicMock(name=QDRANT_COLLECTION)]
        )

        result = await handle_code_embedding(
            repository=mock_repository,
            qdrant_client=mock_qdrant,
            embedding_endpoint="http://test:8100",
        )

        assert result == {"embedded_count": 0, "failed_count": 0}
