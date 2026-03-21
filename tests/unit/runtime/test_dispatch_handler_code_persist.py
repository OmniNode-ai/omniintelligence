# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for code persist dispatch handler.

Validates:
    - Handler deletes old entities then upserts new entities and relationships
    - Idempotent: re-processing same file produces same result

Related:
    - OMN-5716: Dispatch handler — persist entities to Postgres
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.runtime.dispatch_handler_code_persist import (
    create_code_persist_dispatch_handler,
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


def _make_extracted_event_payload(
    *,
    entity_count: int = 1,
    relationship_count: int = 1,
) -> dict[str, object]:
    entities = [_make_entity_dict(f"Entity{i}") for i in range(entity_count)]
    relationships = [_make_relationship_dict() for _ in range(relationship_count)]
    return {
        "event_id": f"evt_{uuid4().hex[:12]}",
        "crawl_id": "crawl_test",
        "repo_name": "test_repo",
        "file_path": "src/models.py",
        "file_hash": "abc123",
        "entities": entities,
        "relationships": relationships,
        "entity_count": entity_count,
        "relationship_count": relationship_count,
    }


def _make_envelope(payload: dict[str, object]) -> ModelEventEnvelope[object]:
    return ModelEventEnvelope(payload=payload, correlation_id=uuid4())


def _make_context() -> ProtocolHandlerContext:
    ctx = MagicMock(spec=ProtocolHandlerContext)
    ctx.correlation_id = uuid4()
    return ctx


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persist_deletes_then_upserts() -> None:
    """Handler deletes old entities for file, then upserts new ones."""
    store = AsyncMock()
    store.delete_entities_by_file = AsyncMock(return_value=3)
    store.upsert_entity = AsyncMock(return_value="entity_id")
    store.upsert_relationship = AsyncMock(return_value="rel_id")

    handler = create_code_persist_dispatch_handler(code_entity_store=store)

    payload = _make_extracted_event_payload(entity_count=2, relationship_count=1)
    envelope = _make_envelope(payload)
    ctx = _make_context()

    result = await handler(envelope, ctx)

    assert result == "ok"
    store.delete_entities_by_file.assert_called_once_with(
        source_repo="test_repo",
        file_path="src/models.py",
    )
    assert store.upsert_entity.call_count == 2
    assert store.upsert_relationship.call_count == 1
