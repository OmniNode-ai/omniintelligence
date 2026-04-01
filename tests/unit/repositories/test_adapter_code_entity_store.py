# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for AdapterCodeEntityStore."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.models import (
    ModelCodeEntity,
    ModelCodeRelationship,
)
from omniintelligence.repositories.adapter_code_entity_store import (
    AdapterCodeEntityStore,
    load_code_entities_contract,
)


@pytest.fixture
def mock_runtime() -> MagicMock:
    runtime = MagicMock()
    runtime.contract = load_code_entities_contract()
    runtime.call = AsyncMock(return_value={"id": "test-id"})
    return runtime


@pytest.mark.unit
class TestAdapterCodeEntityStore:
    async def test_upsert_entity(self, mock_runtime: MagicMock) -> None:
        adapter = AdapterCodeEntityStore(mock_runtime)
        entity = ModelCodeEntity(
            id="cls_Foo",
            entity_type="class",
            entity_name="Foo",
            qualified_name="src.foo.Foo",
            source_path="src/foo.py",
            file_hash="abc123",
            source_repo="omniintelligence",
            line_number=1,
            bases=["BaseModel"],
            methods=[
                {"name": "execute", "args": [], "return_type": "None", "decorators": []}
            ],
            decorators=["frozen"],
            docstring="A class.",
        )

        result = await adapter.upsert_entity(entity)
        assert result == "test-id"

        # Verify runtime.call was called with upsert_entity op
        mock_runtime.call.assert_called_once()
        call_args = mock_runtime.call.call_args
        assert call_args[0][0] == "upsert_entity"
        # Positional args should include id, entity_type, name, etc.
        assert call_args[0][1] == "cls_Foo"  # id
        assert call_args[0][2] == "class"  # entity_type
        assert call_args[0][3] == "Foo"  # name

    async def test_upsert_relationship(self, mock_runtime: MagicMock) -> None:
        adapter = AdapterCodeEntityStore(mock_runtime)
        rel = ModelCodeRelationship(
            id="rel_001",
            source_entity="cls_Foo",
            target_entity="cls_Bar",
            relationship_type="EXTENDS",
            confidence=1.0,
            trust_tier="conservative",
        )

        result = await adapter.upsert_relationship(rel)
        assert result == "test-id"

        mock_runtime.call.assert_called_once()
        call_args = mock_runtime.call.call_args
        assert call_args[0][0] == "upsert_relationship"
        assert call_args[0][1] == "rel_001"  # id
        assert call_args[0][2] == "cls_Foo"  # source
        assert call_args[0][3] == "cls_Bar"  # target
