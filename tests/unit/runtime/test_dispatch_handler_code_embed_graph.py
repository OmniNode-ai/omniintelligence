# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for code embed+graph dispatch handler.

Validates:
    - Handler embeds entities in Qdrant and writes to Memgraph
    - Graceful degradation when Qdrant/Memgraph unavailable
    - Qdrant payload uses canonical rich schema field names [OMN-5765]

Related:
    - OMN-5717: Dispatch handler — embed to Qdrant + graph to Memgraph
    - OMN-5765: Migration schema conflict resolution
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.runtime.dispatch_handler_code_embed_graph import (
    create_code_embed_graph_dispatch_handler,
)


def _make_entity_dict(name: str = "MyClass") -> dict[str, object]:
    return {
        "id": f"cls_{name}",
        "entity_type": "CLASS",
        "entity_name": name,
        "qualified_name": f"src.models.{name}",
        "source_path": "src/models.py",
        "file_hash": "abc123",
        "source_repo": "test_repo",
        "line_number": 1,
        "bases": ["BaseModel"],
        "methods": [
            {"name": "__init__", "args": [], "return_type": "None", "decorators": []}
        ],
        "decorators": [],
        "docstring": "Test class.",
        "signature": None,
        "confidence": 1.0,
    }


def _make_relationship_dict() -> dict[str, object]:
    return {
        "id": f"rel_{uuid4().hex[:12]}",
        "source_entity": "mod_src.models",
        "target_entity": "cls_MyClass",
        "relationship_type": "CONTAINS",
        "confidence": 1.0,
        "trust_tier": "strong",
        "evidence": [],
        "inject_into_context": True,
    }


def _make_extracted_payload() -> dict[str, object]:
    return {
        "event_id": f"evt_{uuid4().hex[:12]}",
        "crawl_id": "crawl_test",
        "repo_name": "test_repo",
        "file_path": "src/models.py",
        "file_hash": "abc123",
        "entities": [_make_entity_dict("ClassA"), _make_entity_dict("ClassB")],
        "relationships": [_make_relationship_dict()],
        "entity_count": 2,
        "relationship_count": 1,
    }


def _make_envelope(payload: dict[str, object]) -> ModelEventEnvelope[object]:
    return ModelEventEnvelope(payload=payload, correlation_id=uuid4())


def _make_context() -> ProtocolHandlerContext:
    ctx = MagicMock(spec=ProtocolHandlerContext)
    ctx.correlation_id = uuid4()
    return ctx


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embed_graph_with_mocked_clients() -> None:
    """Handler embeds entities in Qdrant and writes to Memgraph."""
    qdrant_client = AsyncMock()
    qdrant_client.upsert = AsyncMock()

    bolt_handler = AsyncMock()
    bolt_handler.write = AsyncMock()

    # Mock embedding endpoint
    mock_embedding = [0.1] * 128

    handler = create_code_embed_graph_dispatch_handler(
        qdrant_client=qdrant_client,
        bolt_handler=bolt_handler,
        embedding_url="http://test:8100",
    )

    with patch(
        "omniintelligence.runtime.dispatch_handler_code_embed_graph._get_embedding",
        AsyncMock(return_value=mock_embedding),
    ):
        result = await handler(
            _make_envelope(_make_extracted_payload()),
            _make_context(),
        )

    assert result == "ok"

    # Qdrant should receive upsert call
    qdrant_client.upsert.assert_called_once()
    call_kwargs = qdrant_client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == "code_patterns"
    assert len(call_kwargs["points"]) == 2

    # Memgraph should receive writes: 2 entities + 1 relationship
    assert bolt_handler.write.call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_graceful_degradation_no_clients() -> None:
    """Handler works without Qdrant/Memgraph (graceful degradation)."""
    handler = create_code_embed_graph_dispatch_handler(
        qdrant_client=None,
        bolt_handler=None,
    )

    result = await handler(
        _make_envelope(_make_extracted_payload()),
        _make_context(),
    )

    assert result == "ok"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_qdrant_payload_uses_rich_schema_fields() -> None:
    """Qdrant payload must use canonical rich schema field names [OMN-5765].

    The Qdrant payload written by _embed_entities() is the read-side contract
    consumed by omniclaude's code_graph_query.py (semantic mode). If the payload
    field names drift from the canonical schema, semantic search silently breaks.

    This test asserts that the payload contains the canonical rich field names
    and does NOT contain any legacy field names from the simple schema.
    """
    qdrant_client = AsyncMock()
    qdrant_client.upsert = AsyncMock()

    mock_embedding = [0.1] * 128

    handler = create_code_embed_graph_dispatch_handler(
        qdrant_client=qdrant_client,
        bolt_handler=None,
        embedding_url="http://test:8100",
    )

    with patch(
        "omniintelligence.runtime.dispatch_handler_code_embed_graph._get_embedding",
        AsyncMock(return_value=mock_embedding),
    ):
        await handler(
            _make_envelope(_make_extracted_payload()),
            _make_context(),
        )

    qdrant_client.upsert.assert_called_once()
    points = qdrant_client.upsert.call_args.kwargs["points"]
    assert len(points) >= 1

    payload = points[0]["payload"]

    # Canonical rich schema fields MUST be present
    assert "entity_id" in payload
    assert "entity_type" in payload
    assert "entity_name" in payload
    assert "qualified_name" in payload
    assert "source_path" in payload
    assert "source_repo" in payload
    assert "line_number" in payload

    # Legacy simple schema fields MUST NOT be present
    assert "name" not in payload, "Legacy field 'name' found — use 'entity_name'"
    assert "file_path" not in payload, (
        "Legacy field 'file_path' found — use 'source_path'"
    )
    assert "line_start" not in payload, (
        "Legacy field 'line_start' found — use 'line_number'"
    )
