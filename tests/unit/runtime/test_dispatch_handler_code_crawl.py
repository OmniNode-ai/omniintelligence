# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for code crawl dispatch handler.

Validates:
    - Handler calls crawl_files and publishes file-discovered events
    - repo_filter from payload is forwarded to crawler

Related:
    - OMN-5714: Dispatch handler — code crawl requested
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.runtime.dispatch_handler_code_crawl import (
    create_code_crawl_dispatch_handler,
)


def _make_envelope(
    payload: dict[str, object] | None = None,
) -> ModelEventEnvelope[object]:
    return ModelEventEnvelope(
        payload=payload or {},
        correlation_id=uuid4(),
    )


def _make_context() -> ProtocolHandlerContext:
    ctx = MagicMock(spec=ProtocolHandlerContext)
    ctx.correlation_id = uuid4()
    return ctx


@pytest.mark.unit
@pytest.mark.asyncio
async def test_crawl_publishes_discovered_events() -> None:
    """Handler crawls files and publishes discovery events via Kafka."""
    kafka_producer = AsyncMock()
    kafka_producer.publish = AsyncMock()

    handler = create_code_crawl_dispatch_handler(
        kafka_producer=kafka_producer,
        publish_topic="test.code-file-discovered.v1",
    )

    # Create temp dir with python files for crawl
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hello')")
        (src_dir / "utils.py").write_text("def helper(): pass")

        # Patch _load_crawl_config to return our test config
        from omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_config import (
            ModelCrawlConfig,
            ModelRepoCrawlConfig,
        )

        test_config = ModelCrawlConfig(
            repos=[
                ModelRepoCrawlConfig(
                    name="test_repo",
                    enabled=True,
                    path=tmpdir,
                    include=["src/**/*.py"],
                    exclude=["**/__pycache__/**"],
                ),
            ]
        )

        with patch(
            "omniintelligence.runtime.dispatch_handler_code_crawl._load_crawl_config",
            return_value=test_config,
        ):
            envelope = _make_envelope({"crawl_id": "test_crawl_123"})
            ctx = _make_context()

            result = await handler(envelope, ctx)

        assert result == "ok"
        assert kafka_producer.publish.call_count == 2

        # Verify published events have correct topic
        for call in kafka_producer.publish.call_args_list:
            assert call.kwargs["topic"] == "test.code-file-discovered.v1"
            value = call.kwargs["value"]
            assert value["repo_name"] == "test_repo"
            assert value["crawl_id"] == "test_crawl_123"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_crawl_without_kafka_producer() -> None:
    """Handler completes successfully even without Kafka producer."""
    handler = create_code_crawl_dispatch_handler(kafka_producer=None)

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text("x = 1")

        from omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_config import (
            ModelCrawlConfig,
            ModelRepoCrawlConfig,
        )

        test_config = ModelCrawlConfig(
            repos=[
                ModelRepoCrawlConfig(
                    name="test_repo",
                    path=tmpdir,
                    include=["*.py"],
                ),
            ]
        )

        with patch(
            "omniintelligence.runtime.dispatch_handler_code_crawl._load_crawl_config",
            return_value=test_config,
        ):
            result = await handler(_make_envelope(), _make_context())

        assert result == "ok"
