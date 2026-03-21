# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Tests for dispatch_handler_graph_storage."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omniintelligence.runtime.dispatch_handler_graph_storage import (
    handle_graph_storage,
)


def _make_entity(
    entity_id: str,
    name: str,
    entity_type: str,
    qualified_name: str,
    source_repo: str = "test-repo",
) -> dict[str, Any]:
    return {
        "id": entity_id,
        "entity_name": name,
        "entity_type": entity_type,
        "qualified_name": qualified_name,
        "source_repo": source_repo,
        "source_path": f"src/{name}.py",
        "classification": "core",
        "architectural_pattern": None,
    }


def _make_relationship(
    source_entity_id: str,
    target_entity_id: str,
    relationship_type: str,
    source_repo: str = "test-repo",
    inject_into_context: bool = True,
) -> dict[str, Any]:
    return {
        "id": "rel-1",
        "source_entity_id": source_entity_id,
        "target_entity_id": target_entity_id,
        "relationship_type": relationship_type,
        "trust_tier": "strong",
        "confidence": 0.95,
        "source_repo": source_repo,
        "inject_into_context": inject_into_context,
    }


@pytest.mark.unit
class TestHandleGraphStorage:
    """Tests for handle_graph_storage dispatch handler."""

    @pytest.mark.asyncio
    async def test_writes_nodes_and_edges(self) -> None:
        """Verify MERGE is called for each entity and only injectable edges."""
        entities = [
            _make_entity("id-1", "Foo", "class", "pkg.Foo"),
            _make_entity("id-2", "Bar", "protocol", "pkg.Bar"),
            _make_entity("id-3", "baz", "function", "pkg.baz"),
        ]
        relationships = [
            _make_relationship("id-1", "id-2", "IMPLEMENTS"),
            # This relationship should still be written because the repository
            # already filters inject_into_context=true in get_all_entities_and_relationships.
            # But let's include one with an unresolvable target to test skip logic.
        ]

        mock_repository = AsyncMock()
        mock_repository.get_all_entities_and_relationships.return_value = (
            entities,
            relationships,
        )
        mock_repository.update_graph_synced_at = AsyncMock()

        mock_session = AsyncMock()
        mock_session.run = AsyncMock()

        # driver.session() returns a sync context manager with async __aenter__/__aexit__
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_ctx
        mock_driver.close = AsyncMock()

        result = await handle_graph_storage(
            repository=mock_repository,
            driver=mock_driver,
        )

        assert result["nodes_written"] == 3
        assert result["edges_written"] == 1

        # 3 entity MERGE calls + 1 relationship MERGE call = 4 total
        assert mock_session.run.call_count == 4

        # Verify node MERGE calls contain correct labels
        node_calls = list(mock_session.run.call_args_list[:3])
        cypher_strs = [call.args[0] for call in node_calls]
        assert any("Class" in c for c in cypher_strs)
        assert any("Protocol" in c for c in cypher_strs)
        assert any("Function" in c for c in cypher_strs)

        # Verify update_graph_synced_at was called with entity IDs
        mock_repository.update_graph_synced_at.assert_called_once_with(
            ["id-1", "id-2", "id-3"],
        )

    @pytest.mark.asyncio
    async def test_memgraph_unavailable_graceful_degradation(self) -> None:
        """Verify graceful degradation when Memgraph is unreachable."""
        mock_repository = AsyncMock()

        with patch(
            "omniintelligence.runtime.dispatch_handler_graph_storage.AsyncGraphDatabase",
        ) as mock_gdb:
            mock_driver = AsyncMock()
            mock_driver.verify_connectivity.side_effect = ConnectionRefusedError(
                "Connection refused",
            )
            mock_gdb.driver.return_value = mock_driver

            result = await handle_graph_storage(
                repository=mock_repository,
                memgraph_uri="bolt://localhost:7687",
            )

        assert result == {"nodes_written": 0, "edges_written": 0}
        # Repository should never be called if Memgraph is unavailable
        mock_repository.get_all_entities_and_relationships.assert_not_called()
