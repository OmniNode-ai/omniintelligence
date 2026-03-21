# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for code extract dispatch handler.

Validates:
    - Handler reads file, extracts entities via AST, publishes extracted event
    - Non-.py files are skipped

Related:
    - OMN-5715: Dispatch handler — extract AST entities
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.runtime.dispatch_handler_code_extract import (
    create_code_extract_dispatch_handler,
)

SAMPLE_PYTHON = """
from pydantic import BaseModel


class MyModel(BaseModel):
    \"\"\"A test model.\"\"\"
    name: str


def helper() -> str:
    return "hello"


MY_CONSTANT = 42
"""


def _make_envelope(payload: dict[str, object]) -> ModelEventEnvelope[object]:
    return ModelEventEnvelope(
        payload=payload,
        correlation_id=uuid4(),
    )


def _make_context() -> ProtocolHandlerContext:
    ctx = MagicMock(spec=ProtocolHandlerContext)
    ctx.correlation_id = uuid4()
    return ctx


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_publishes_entities() -> None:
    """Handler reads file, extracts via AST, publishes entities-extracted event."""
    kafka_producer = AsyncMock()
    kafka_producer.publish = AsyncMock()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        (src_dir / "models.py").write_text(SAMPLE_PYTHON)

        handler = create_code_extract_dispatch_handler(
            kafka_producer=kafka_producer,
            publish_topic="test.code-entities-extracted.v1",
            repo_paths={"test_repo": tmpdir},
        )

        envelope = _make_envelope(
            {
                "event_id": "evt_test",
                "crawl_id": "crawl_test",
                "repo_name": "test_repo",
                "file_path": "src/models.py",
                "file_hash": "abc123",
                "file_extension": ".py",
            }
        )

        result = await handler(envelope, _make_context())

    assert result == "ok"
    assert kafka_producer.publish.call_count == 1

    call_kwargs = kafka_producer.publish.call_args.kwargs
    assert call_kwargs["topic"] == "test.code-entities-extracted.v1"
    value = call_kwargs["value"]
    assert value["repo_name"] == "test_repo"
    assert value["file_path"] == "src/models.py"
    assert value["entity_count"] > 0
    assert value["relationship_count"] > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skips_non_python_files() -> None:
    """Non-.py files are skipped with a warning."""
    kafka_producer = AsyncMock()

    handler = create_code_extract_dispatch_handler(
        kafka_producer=kafka_producer,
        repo_paths={"test_repo": "/tmp"},
    )

    envelope = _make_envelope(
        {
            "event_id": "evt_test",
            "crawl_id": "crawl_test",
            "repo_name": "test_repo",
            "file_path": "README.md",
            "file_hash": "abc123",
            "file_extension": ".md",
        }
    )

    result = await handler(envelope, _make_context())
    assert result == "ok"
    kafka_producer.publish.assert_not_called()
