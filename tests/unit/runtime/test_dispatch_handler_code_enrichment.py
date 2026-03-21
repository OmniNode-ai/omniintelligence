# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for code entity LLM enrichment dispatch handler.

Validates:
    - Successful enrichment: LLM returns valid classification, repository updated
    - Low confidence fallback: confidence < 0.7 stores "other"
    - LLM failure: httpx error -> entity stays unenriched, failed_count incremented

Related:
    - OMN-5664: LLM enrichment handler for code entities
    - OMN-5657: AST-based code pattern extraction system (epic)
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from omniintelligence.runtime.dispatch_handler_code_enrichment import (
    LOW_CONFIDENCE_THRESHOLD,
    handle_code_enrichment,
)

# =============================================================================
# Fixtures
# =============================================================================


def _make_entity(
    *,
    entity_name: str = "MyHandler",
    bases: list[str] | None = None,
    methods: list[dict[str, str]] | None = None,
    docstring: str | None = "Handles incoming requests.",
) -> dict[str, Any]:
    """Create a fake entity dict matching RepositoryCodeEntity.get_entities_needing_enrichment() shape."""
    return {
        "id": uuid4(),
        "entity_name": entity_name,
        "entity_type": "class",
        "qualified_name": f"mymodule.{entity_name}",
        "source_repo": "omniintelligence",
        "source_path": "src/mymodule.py",
        "docstring": docstring,
        "signature": None,
        "bases": bases or ["BaseHandler"],
        "methods": methods or [{"name": "handle"}, {"name": "validate"}],
        "fields": None,
        "decorators": None,
    }


def _make_llm_response(
    *,
    classification: str = "handler",
    confidence: float = 0.85,
    description: str = "Handles incoming HTTP requests.",
    pattern: str = "handler",
) -> httpx.Response:
    """Create a mock httpx.Response with LLM JSON payload."""
    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "classification": classification,
                            "confidence": confidence,
                            "description": description,
                            "pattern": pattern,
                        }
                    )
                }
            }
        ]
    }
    response = httpx.Response(
        status_code=200,
        json=payload,
        request=httpx.Request("POST", "http://test/v1/chat/completions"),
    )
    return response


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_successful_enrichment() -> None:
    """LLM returns valid classification -> repository.update_enrichment called with correct params."""
    entity_1 = _make_entity(entity_name="HandlerA")
    entity_2 = _make_entity(entity_name="HandlerB")

    repository = MagicMock()
    repository.get_entities_needing_enrichment = AsyncMock(
        return_value=[entity_1, entity_2]
    )
    repository.update_enrichment = AsyncMock()

    mock_response = _make_llm_response(classification="handler", confidence=0.85)
    mock_transport = MagicMock()
    mock_transport.handle_async_request = AsyncMock(return_value=mock_response)

    async with httpx.AsyncClient(transport=mock_transport) as client:
        # Patch AsyncClient to use our mock
        pass

    # Use monkeypatch on httpx.AsyncClient to return our controlled responses
    original_post = httpx.AsyncClient.post

    call_count = 0

    async def mock_post(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return _make_llm_response(
            classification="handler",
            confidence=0.85,
            description=f"Description for entity {call_count}",
            pattern="handler",
        )

    httpx.AsyncClient.post = mock_post  # type: ignore[assignment]
    try:
        result = await handle_code_enrichment(
            repository=repository,
            llm_endpoint="http://test:8001",
            batch_size=10,
        )
    finally:
        httpx.AsyncClient.post = original_post  # type: ignore[assignment]

    assert result["enriched_count"] == 2
    assert result["failed_count"] == 0
    assert repository.update_enrichment.call_count == 2

    # Verify first call args
    first_call = repository.update_enrichment.call_args_list[0]
    assert first_call.kwargs["entity_id"] == str(entity_1["id"])
    assert first_call.kwargs["classification"] == "handler"
    assert first_call.kwargs["classification_confidence"] == 0.85
    assert first_call.kwargs["enrichment_version"] == "1.0.0"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_low_confidence_fallback() -> None:
    """Confidence below threshold -> classification stored as 'other'."""
    entity = _make_entity(entity_name="AmbiguousThing")

    repository = MagicMock()
    repository.get_entities_needing_enrichment = AsyncMock(return_value=[entity])
    repository.update_enrichment = AsyncMock()

    low_confidence = LOW_CONFIDENCE_THRESHOLD - 0.1

    original_post = httpx.AsyncClient.post

    async def mock_post(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        return _make_llm_response(
            classification="adapter",
            confidence=low_confidence,
            description="Some adapter thing.",
            pattern="adapter",
        )

    httpx.AsyncClient.post = mock_post  # type: ignore[assignment]
    try:
        result = await handle_code_enrichment(
            repository=repository,
            llm_endpoint="http://test:8001",
        )
    finally:
        httpx.AsyncClient.post = original_post  # type: ignore[assignment]

    assert result["enriched_count"] == 1
    assert result["failed_count"] == 0

    call_kwargs = repository.update_enrichment.call_args.kwargs
    # Classification should be "other", NOT "adapter"
    assert call_kwargs["classification"] == "other"
    # But confidence should still be the original low value
    assert call_kwargs["classification_confidence"] == low_confidence


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_failure_increments_failed_count() -> None:
    """LLM HTTP error -> entity not enriched, failed_count incremented."""
    entity = _make_entity(entity_name="FailEntity")

    repository = MagicMock()
    repository.get_entities_needing_enrichment = AsyncMock(return_value=[entity])
    repository.update_enrichment = AsyncMock()

    original_post = httpx.AsyncClient.post

    async def mock_post(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    httpx.AsyncClient.post = mock_post  # type: ignore[assignment]
    try:
        result = await handle_code_enrichment(
            repository=repository,
            llm_endpoint="http://test:8001",
        )
    finally:
        httpx.AsyncClient.post = original_post  # type: ignore[assignment]

    assert result["enriched_count"] == 0
    assert result["failed_count"] == 1
    # update_enrichment should NOT have been called
    repository.update_enrichment.assert_not_called()
