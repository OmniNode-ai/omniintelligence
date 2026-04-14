# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for code entity bridge dispatch handler.

Validates:
    - Handler fires on code-entities-extracted.v1 events and calls upsert_pattern
    - Handler skips files with parse_status == syntax_error
    - Handler skips events with no entities
    - Bridge route is registered on canonical code-entities-extracted dispatch alias
      (OMN-8706: was broken — registered on an unreachable virtual alias)

Related:
    - OMN-7863: code-entities-extracted → learned_patterns bridge
    - OMN-8706: Fix bridge route topic_pattern so fan-out actually fires
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.constants import TOPIC_CODE_ENTITIES_EXTRACTED_V1
from omniintelligence.runtime.contract_topics import canonical_topic_to_dispatch_alias
from omniintelligence.runtime.dispatch_handler_code_entity_bridge import (
    create_code_entity_bridge_dispatch_handler,
)


def _make_entity_dict(
    name: str = "MyClass",
    entity_type: str = "class",
    confidence: float = 1.0,
) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "entity_name": name,
        "entity_type": entity_type,
        "qualified_name": f"omniintelligence.nodes.foo.{name}",
        "source_repo": "omniintelligence",
        "source_path": "src/omniintelligence/nodes/foo/node.py",
        "line_number": 10,
        "bases": [],
        "methods": [],
        "fields": [],
        "decorators": [],
        "docstring": f"The {name} entity.",
        "signature": None,
        "file_hash": "abc123def456",
        "source_language": "python",
        "confidence": confidence,
    }


def _make_extracted_payload(
    *,
    parse_status: str = "success",
    entity_count: int = 2,
) -> dict[str, object]:
    return {
        "event_id": str(uuid4()),
        "crawl_id": "crawl_test_001",
        "repo_name": "omniintelligence",
        "file_path": "src/omniintelligence/nodes/foo/node.py",
        "file_hash": "abc123def456",
        "entities": [_make_entity_dict(f"Entity{i}") for i in range(entity_count)],
        "relationships": [],
        "entity_count": entity_count,
        "relationship_count": 0,
        "parse_status": parse_status,
        "parse_error": None,
    }


def _make_envelope(payload: dict[str, object]) -> ModelEventEnvelope[object]:
    return ModelEventEnvelope(payload=payload, correlation_id=uuid4())


def _make_context() -> ProtocolHandlerContext:
    ctx = MagicMock(spec=ProtocolHandlerContext)
    ctx.correlation_id = uuid4()
    return ctx


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bridge_handler_calls_upsert_for_each_entity() -> None:
    """Handler derives patterns from AST entities and calls upsert_pattern for each."""
    pattern_store = AsyncMock()
    pattern_store.upsert_pattern = AsyncMock(return_value=None)

    handler = create_code_entity_bridge_dispatch_handler(pattern_store=pattern_store)

    payload = _make_extracted_payload(entity_count=3)
    envelope = _make_envelope(payload)
    ctx = _make_context()

    result = await handler(envelope, ctx)

    assert result == "ok"
    assert pattern_store.upsert_pattern.call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bridge_handler_skips_syntax_error_files() -> None:
    """Handler skips files where parse_status is syntax_error — no upserts."""
    pattern_store = AsyncMock()
    pattern_store.upsert_pattern = AsyncMock(return_value=None)

    handler = create_code_entity_bridge_dispatch_handler(pattern_store=pattern_store)

    payload = _make_extracted_payload(parse_status="syntax_error", entity_count=2)
    envelope = _make_envelope(payload)
    ctx = _make_context()

    result = await handler(envelope, ctx)

    assert result == "ok"
    pattern_store.upsert_pattern.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bridge_handler_skips_empty_entity_list() -> None:
    """Handler skips events with no entities — nothing to derive."""
    pattern_store = AsyncMock()
    pattern_store.upsert_pattern = AsyncMock(return_value=None)

    handler = create_code_entity_bridge_dispatch_handler(pattern_store=pattern_store)

    payload = _make_extracted_payload(entity_count=0)
    envelope = _make_envelope(payload)
    ctx = _make_context()

    result = await handler(envelope, ctx)

    assert result == "ok"
    pattern_store.upsert_pattern.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bridge_handler_works_without_pattern_store() -> None:
    """Handler runs in dry-run mode when pattern_store is None — no errors."""
    handler = create_code_entity_bridge_dispatch_handler(pattern_store=None)

    payload = _make_extracted_payload(entity_count=2)
    envelope = _make_envelope(payload)
    ctx = _make_context()

    result = await handler(envelope, ctx)

    assert result == "ok"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bridge_handler_handles_invalid_payload_gracefully() -> None:
    """Handler returns 'ok' without crashing on non-dict payloads."""
    pattern_store = AsyncMock()
    handler = create_code_entity_bridge_dispatch_handler(pattern_store=pattern_store)

    envelope = ModelEventEnvelope(payload="not-a-dict", correlation_id=uuid4())
    ctx = _make_context()

    result = await handler(envelope, ctx)

    assert result == "ok"
    pattern_store.upsert_pattern.assert_not_called()


@pytest.mark.unit
def test_bridge_route_uses_canonical_extracted_dispatch_alias() -> None:
    """Bridge route topic_pattern must equal the canonical code-entities-extracted alias.

    OMN-8706: Was previously registered on DISPATCH_ALIAS_CODE_ENTITY_BRIDGE
    (onex.events.omniintelligence.code-entities-extracted-bridge.v1) which is
    a virtual alias never published to Kafka. The dispatch engine fan-out only
    fires when multiple routes share the canonical topic_pattern.
    """
    from omniintelligence.protocols import (
        ProtocolIdempotencyStore,
        ProtocolIntentClassifier,
        ProtocolPatternRepository,
        ProtocolPatternUpsertStore,
    )
    from omniintelligence.runtime.dispatch_handlers import (
        create_intelligence_dispatch_engine,
    )

    repo = MagicMock(spec=ProtocolPatternRepository)
    idempotency = MagicMock(spec=ProtocolIdempotencyStore)
    classifier = MagicMock(spec=ProtocolIntentClassifier)
    upsert_store = MagicMock(spec=ProtocolPatternUpsertStore)

    engine = create_intelligence_dispatch_engine(
        repository=repo,
        idempotency_store=idempotency,
        intent_classifier=classifier,
        pattern_upsert_store=upsert_store,
    )

    expected_alias = canonical_topic_to_dispatch_alias(TOPIC_CODE_ENTITIES_EXTRACTED_V1)

    bridge_route = None
    for route in engine._routes.values():  # type: ignore[attr-defined]
        if route.route_id == "intelligence-code-entity-bridge-route":
            bridge_route = route
            break

    assert bridge_route is not None, "Bridge route not registered in dispatch engine"
    assert bridge_route.topic_pattern == expected_alias, (
        f"Bridge route topic_pattern '{bridge_route.topic_pattern}' "
        f"!= canonical alias '{expected_alias}'. "
        "OMN-8706: Bridge handler will never fire if not on canonical topic."
    )
