# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for persist handler event emission (OMN-5677)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from omniintelligence.constants import TOPIC_CODE_ENTITIES_PERSISTED_V1
from omniintelligence.runtime.dispatch_handler_code_persist import (
    create_code_persist_dispatch_handler,
)


def _make_envelope(payload: dict) -> MagicMock:  # type: ignore[type-arg]
    """Create a mock envelope with dict payload."""
    envelope = MagicMock()
    envelope.payload = payload
    return envelope


def _make_context() -> MagicMock:
    """Create a mock handler context."""
    ctx = MagicMock()
    ctx.correlation_id = "test-correlation-id"
    return ctx


@pytest.mark.unit
class TestPersistHandlerEvent:
    """Tests for code-entities-persisted.v1 event emission."""

    @pytest.mark.asyncio
    async def test_emits_persisted_event_on_success(self) -> None:
        """Persist handler emits code-entities-persisted.v1 after upsert."""
        mock_repo = MagicMock()
        mock_repo.upsert_entity = AsyncMock(return_value="entity-uuid-1")
        mock_repo.upsert_relationship = AsyncMock(return_value="rel-uuid-1")
        mock_repo.get_entity_id_by_qualified_name = AsyncMock(
            return_value="entity-uuid-1"
        )
        mock_repo.delete_stale_entities = AsyncMock(return_value=0)
        mock_repo.delete_stale_relationships_for_file = AsyncMock(return_value=0)

        mock_publisher = MagicMock()
        mock_publisher.publish = AsyncMock()

        handler = create_code_persist_dispatch_handler(
            repository=mock_repo,
            publisher=mock_publisher,
        )

        payload = {
            "event_id": "evt-001",
            "crawl_id": "crawl-123",
            "repo_name": "omniintelligence",
            "file_path": "src/foo/bar.py",
            "file_hash": "abc123",
            "parse_status": "success",
            "parse_error": None,
            "entities": [
                {
                    "id": "e1",
                    "entity_name": "MyClass",
                    "entity_type": "class",
                    "qualified_name": "foo.bar.MyClass",
                    "source_repo": "omniintelligence",
                    "source_path": "src/foo/bar.py",
                    "file_hash": "abc123",
                    "line_number": 10,
                    "bases": [],
                    "methods": [],
                    "fields": [],
                    "decorators": [],
                    "docstring": None,
                    "signature": None,
                },
            ],
            "relationships": [],
        }

        result = await handler(_make_envelope(payload), _make_context())
        assert result == "ok"

        # Verify event was published
        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        assert call_args[0][0] == TOPIC_CODE_ENTITIES_PERSISTED_V1
        event_data = call_args[0][1]
        assert event_data["repo_name"] == "omniintelligence"
        assert event_data["file_path"] == "src/foo/bar.py"
        assert event_data["persisted_count"] == 1
        assert len(event_data["entity_ids"]) == 1

    @pytest.mark.asyncio
    async def test_no_event_on_syntax_error(self) -> None:
        """No event emitted when parse_status is syntax_error."""
        mock_repo = MagicMock()
        mock_publisher = MagicMock()
        mock_publisher.publish = AsyncMock()

        handler = create_code_persist_dispatch_handler(
            repository=mock_repo,
            publisher=mock_publisher,
        )

        payload = {
            "event_id": "evt-002",
            "crawl_id": "crawl-123",
            "repo_name": "test",
            "file_path": "bad.py",
            "file_hash": "xyz",
            "parse_status": "syntax_error",
            "parse_error": "SyntaxError: invalid syntax",
            "entities": [],
            "relationships": [],
        }

        result = await handler(_make_envelope(payload), _make_context())
        assert result == "ok"
        mock_publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_event_without_publisher(self) -> None:
        """Works without publisher (backwards compatible with Part 1)."""
        mock_repo = MagicMock()
        mock_repo.upsert_entity = AsyncMock(return_value="entity-uuid-1")
        mock_repo.get_entity_id_by_qualified_name = AsyncMock(
            return_value="entity-uuid-1"
        )
        mock_repo.delete_stale_entities = AsyncMock(return_value=0)
        mock_repo.delete_stale_relationships_for_file = AsyncMock(return_value=0)

        handler = create_code_persist_dispatch_handler(
            repository=mock_repo,
            # No publisher
        )

        payload = {
            "event_id": "evt-003",
            "crawl_id": "crawl-123",
            "repo_name": "test",
            "file_path": "ok.py",
            "file_hash": "abc",
            "parse_status": "success",
            "parse_error": None,
            "entities": [
                {
                    "id": "e1",
                    "entity_name": "Foo",
                    "entity_type": "function",
                    "qualified_name": "ok.Foo",
                    "source_repo": "test",
                    "source_path": "ok.py",
                    "file_hash": "abc",
                    "line_number": 1,
                    "bases": [],
                    "methods": [],
                    "fields": [],
                    "decorators": [],
                    "docstring": None,
                    "signature": None,
                },
            ],
            "relationships": [],
        }

        result = await handler(_make_envelope(payload), _make_context())
        assert result == "ok"
