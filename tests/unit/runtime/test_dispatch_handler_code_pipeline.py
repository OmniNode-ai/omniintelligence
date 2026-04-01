# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the code crawl -> extract -> persist dispatch pipeline.

Tests the three dispatch bridge handlers:
    1. dispatch_handler_code_crawl: crawl-requested -> file-discovered
    2. dispatch_handler_code_extract: file-discovered -> entities-extracted
    3. dispatch_handler_code_persist: entities-extracted -> Postgres upsert

Ticket: OMN-5662
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entities_extracted_event import (
    ModelCodeEntitiesExtractedEvent,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_relationship import (
    ModelCodeRelationship,
)
from omniintelligence.nodes.node_code_crawler_effect.models.model_code_file_discovered_event import (
    ModelCodeFileDiscoveredEvent,
)


def _make_context() -> MagicMock:
    """Create a mock ProtocolHandlerContext."""
    ctx = MagicMock()
    ctx.correlation_id = uuid.uuid4()
    return ctx


def _make_envelope(payload: dict[str, Any]) -> ModelEventEnvelope[object]:
    """Create a ModelEventEnvelope with the given payload dict."""
    return ModelEventEnvelope(
        payload=payload,
        correlation_id=uuid.uuid4(),
    )


# =============================================================================
# Test 1: crawl handler emits correct number of file-discovered events
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_crawl_handler_emits_file_discovered_events() -> None:
    """Mock OnexTree generator returns 3 files. Verify 3 events published."""
    from omniintelligence.runtime.dispatch_handler_code_crawl import (
        create_code_crawl_dispatch_handler,
    )

    # Create 3 mock discovered events
    mock_events = [
        ModelCodeFileDiscoveredEvent(
            event_id=str(uuid.uuid4()),
            crawl_id="crawl-001",
            repo_name="test_repo",
            file_path=f"src/module_{i}.py",
            file_hash=f"hash_{i}",
            file_size_bytes=100 * (i + 1),
            source_content=f"# module {i}\nclass Mod{i}: pass\n",
            timestamp=datetime.now(tz=timezone.utc),
        )
        for i in range(3)
    ]

    mock_publisher = AsyncMock()
    mock_publisher.publish = AsyncMock()

    handler = create_code_crawl_dispatch_handler(
        kafka_publisher=mock_publisher,
        publish_topic="onex.evt.omniintelligence.code-file-discovered.v1",
    )

    envelope = _make_envelope({"repo": "test_repo"})
    context = _make_context()

    with (
        patch(
            "omniintelligence.runtime.dispatch_handler_code_crawl._load_repos_config",
            return_value=[
                {
                    "name": "test_repo",
                    "path": "/fake/path",
                    "include": ["src/**/*.py"],
                    "exclude": [],
                }
            ],
        ),
        patch(
            "omniintelligence.nodes.node_code_crawler_effect.handlers.handler_onextree_generator.handle_code_crawl",
            new_callable=AsyncMock,
            return_value=mock_events,
        ),
    ):
        result = await handler(envelope, context)

    assert result == "ok"
    assert mock_publisher.publish.call_count == 3

    # Verify published events have correct keys
    for i, call in enumerate(mock_publisher.publish.call_args_list):
        assert (
            call.kwargs["topic"] == "onex.evt.omniintelligence.code-file-discovered.v1"
        )
        assert f"test_repo:src/module_{i}.py" == call.kwargs["key"]


# =============================================================================
# Test 2: extract handler produces entities-extracted event
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_handler_produces_entities_extracted_event() -> None:
    """Mock file content, AST extractor returns 2 entities + 1 relationship."""
    from omniintelligence.runtime.dispatch_handler_code_extract import (
        create_code_extract_dispatch_handler,
    )

    mock_entities = [
        ModelCodeEntity(
            id=str(uuid.uuid4()),
            entity_name="MyClass",
            entity_type="class",
            qualified_name="src.module.MyClass",
            source_repo="test_repo",
            source_path="src/module.py",
            file_hash="abc123",
        ),
        ModelCodeEntity(
            id=str(uuid.uuid4()),
            entity_name="my_function",
            entity_type="function",
            qualified_name="src.module.my_function",
            source_repo="test_repo",
            source_path="src/module.py",
            file_hash="abc123",
        ),
    ]
    mock_relationships = [
        ModelCodeRelationship(
            id=str(uuid.uuid4()),
            source_entity="src.module.MyClass",
            target_entity="src.module.my_function",
            relationship_type="calls",
            trust_tier="weak",
            confidence=0.5,
        ),
    ]

    mock_extraction_result = ModelCodeEntitiesExtractedEvent(
        event_id=str(uuid.uuid4()),
        crawl_id="crawl-001",
        repo_name="test_repo",
        file_path="src/module.py",
        file_hash="abc123",
        entities=mock_entities,
        relationships=[],  # base extraction has no cross-relationships
        parse_status="success",
        extractor_version="1.0.0",
        timestamp=datetime.now(tz=timezone.utc),
    )

    mock_publisher = AsyncMock()
    mock_publisher.publish = AsyncMock()

    handler = create_code_extract_dispatch_handler(
        repo_paths={"test_repo": "/fake/repo"},
        kafka_publisher=mock_publisher,
        publish_topic="onex.evt.omniintelligence.code-entities-extracted.v1",
    )

    payload = ModelCodeFileDiscoveredEvent(
        event_id=str(uuid.uuid4()),
        crawl_id="crawl-001",
        repo_name="test_repo",
        file_path="src/module.py",
        file_hash="abc123",
        file_size_bytes=500,
        source_content="class MyClass:\n    pass\n",
        timestamp=datetime.now(tz=timezone.utc),
    ).model_dump(mode="json")

    envelope = _make_envelope(payload)
    context = _make_context()

    with (
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.read_text", return_value="class MyClass:\n    pass\n"),
        patch(
            "omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_ast_extract.handle_ast_extract",
            return_value=mock_extraction_result,
        ),
        patch(
            "omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_relationship_detect.detect_relationships",
            return_value=mock_relationships,
        ),
    ):
        result = await handler(envelope, context)

    assert result == "ok"
    assert mock_publisher.publish.call_count == 1

    published_value = mock_publisher.publish.call_args.kwargs["value"]
    assert published_value["parse_status"] == "success"
    assert len(published_value["entities"]) == 2
    # Relationships should include the additional ones from detect_relationships
    assert len(published_value["relationships"]) == 1


# =============================================================================
# Test 3: persist handler upserts entities and runs reconciliation
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persist_handler_upserts_and_reconciles() -> None:
    """Mock repository, 2 entities. Verify upsert + reconciliation calls."""
    from omniintelligence.runtime.dispatch_handler_code_persist import (
        create_code_persist_dispatch_handler,
    )

    mock_repo = AsyncMock()
    mock_repo.upsert_entity = AsyncMock(return_value=str(uuid.uuid4()))
    mock_repo.get_entity_id_by_qualified_name = AsyncMock(
        side_effect=lambda _qn, _repo: str(uuid.uuid4())
    )
    mock_repo.upsert_relationship = AsyncMock(return_value=str(uuid.uuid4()))
    mock_repo.delete_stale_entities = AsyncMock(return_value=0)
    mock_repo.delete_stale_relationships_for_file = AsyncMock(return_value=0)

    handler = create_code_persist_dispatch_handler(repository=mock_repo)

    entities = [
        ModelCodeEntity(
            id=str(uuid.uuid4()),
            entity_name="ClassA",
            entity_type="class",
            qualified_name="mod.ClassA",
            source_repo="test_repo",
            source_path="src/mod.py",
            file_hash="hash1",
        ),
        ModelCodeEntity(
            id=str(uuid.uuid4()),
            entity_name="func_b",
            entity_type="function",
            qualified_name="mod.func_b",
            source_repo="test_repo",
            source_path="src/mod.py",
            file_hash="hash1",
        ),
    ]
    relationships = [
        ModelCodeRelationship(
            id=str(uuid.uuid4()),
            source_entity="mod.ClassA",
            target_entity="mod.func_b",
            relationship_type="calls",
            trust_tier="weak",
            confidence=0.5,
        ),
    ]

    event = ModelCodeEntitiesExtractedEvent(
        event_id=str(uuid.uuid4()),
        crawl_id="crawl-001",
        repo_name="test_repo",
        file_path="src/mod.py",
        file_hash="hash1",
        entities=entities,
        relationships=relationships,
        parse_status="success",
        timestamp=datetime.now(tz=timezone.utc),
    )

    payload = event.model_dump(mode="json")
    envelope = _make_envelope(payload)
    context = _make_context()

    result = await handler(envelope, context)

    assert result == "ok"
    # 2 entities upserted
    assert mock_repo.upsert_entity.call_count == 2
    # 1 relationship upserted
    assert mock_repo.upsert_relationship.call_count == 1
    # Reconciliation called (parse_status == "success")
    mock_repo.delete_stale_entities.assert_called_once_with(
        source_path="src/mod.py",
        source_repo="test_repo",
        current_qualified_names=["mod.ClassA", "mod.func_b"],
    )
    mock_repo.delete_stale_relationships_for_file.assert_called_once()


# =============================================================================
# Test 4: persist handler skips reconciliation on partial parse
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persist_handler_skips_reconciliation_on_partial() -> None:
    """Mock event with parse_status='partial'. Verify upsert but NO reconciliation."""
    from omniintelligence.runtime.dispatch_handler_code_persist import (
        create_code_persist_dispatch_handler,
    )

    mock_repo = AsyncMock()
    mock_repo.upsert_entity = AsyncMock(return_value=str(uuid.uuid4()))
    mock_repo.get_entity_id_by_qualified_name = AsyncMock(return_value=None)
    mock_repo.upsert_relationship = AsyncMock(return_value=str(uuid.uuid4()))
    mock_repo.delete_stale_entities = AsyncMock(return_value=0)
    mock_repo.delete_stale_relationships_for_file = AsyncMock(return_value=0)

    handler = create_code_persist_dispatch_handler(repository=mock_repo)

    entities = [
        ModelCodeEntity(
            id=str(uuid.uuid4()),
            entity_name="PartialClass",
            entity_type="class",
            qualified_name="mod.PartialClass",
            source_repo="test_repo",
            source_path="src/mod.py",
            file_hash="hash2",
        ),
    ]

    event = ModelCodeEntitiesExtractedEvent(
        event_id=str(uuid.uuid4()),
        crawl_id="crawl-002",
        repo_name="test_repo",
        file_path="src/mod.py",
        file_hash="hash2",
        entities=entities,
        relationships=[],
        parse_status="partial",
        timestamp=datetime.now(tz=timezone.utc),
    )

    payload = event.model_dump(mode="json")
    envelope = _make_envelope(payload)
    context = _make_context()

    result = await handler(envelope, context)

    assert result == "ok"
    # Entity upserted
    assert mock_repo.upsert_entity.call_count == 1
    # Reconciliation NOT called (parse_status == "partial")
    mock_repo.delete_stale_entities.assert_not_called()
    mock_repo.delete_stale_relationships_for_file.assert_not_called()
