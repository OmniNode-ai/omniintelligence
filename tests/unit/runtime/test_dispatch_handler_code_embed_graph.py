# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for code embed+graph dispatch handler.

Validates:
    - Handler embeds entities in Qdrant and writes to Memgraph
    - Graceful degradation when Qdrant/Memgraph unavailable

Related:
    - OMN-5717: Dispatch handler — embed to Qdrant + graph to Memgraph
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
        "entity_id": f"cls_{name}",
        "entity_type": "CLASS",
        "name": name,
        "file_path": "src/models.py",
        "file_hash": "abc123",
        "source_repo": "test_repo",
        "line_start": 1,
        "line_end": 10,
        "bases": ["BaseModel"],
        "methods": ["__init__"],
        "decorators": [],
        "docstring": "Test class.",
        "source_code": None,
        "confidence": 1.0,
    }


def _make_relationship_dict() -> dict[str, object]:
    return {
        "relationship_id": f"rel_{uuid4().hex[:12]}",
        "source_entity_id": "mod_src.models",
        "target_entity_id": "cls_MyClass",
        "relationship_type": "CONTAINS",
        "confidence": 1.0,
        "trust_tier": "moderate",
        "metadata": {},
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
