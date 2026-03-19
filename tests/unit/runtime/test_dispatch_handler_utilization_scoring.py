# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Tests for LLM-based utilization scoring dispatch handler.

Reference: OMN-5506 - Create LLM-based utilization scoring handler.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from omniintelligence.runtime.dispatch_handler_utilization_scoring import (
    create_utilization_scoring_dispatch_handler,
)


@pytest.mark.unit
async def test_utilization_scoring_handler_calls_llm() -> None:
    """Handler should call LLM to score utilization and emit updated event."""
    mock_repo = AsyncMock()
    mock_repo.fetch.return_value = [
        {
            "id": str(uuid4()),
            "pattern_signature": "Always use structured logging with correlation IDs",
        },
        {
            "id": str(uuid4()),
            "pattern_signature": "Validate input at API boundaries, not internal functions",
        },
    ]

    mock_publisher = AsyncMock()
    mock_llm_client = AsyncMock()
    mock_llm_client.chat_completion.return_value = '{"utilization_score": 0.75, "reasoning": "Session used structured logging patterns"}'

    handler = create_utilization_scoring_dispatch_handler(
        repository=mock_repo,
        publisher=mock_publisher,
        llm_client=mock_llm_client,
    )

    message = {
        "session_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "session_outcome": "success",
        "injected_pattern_ids": [str(uuid4()), str(uuid4())],
    }

    result = await handler(message)

    assert result["status"] == "scored"
    assert result["utilization_score"] == 0.75
    assert result["detection_method"] == "llm_qwen3_14b"
    assert mock_llm_client.chat_completion.called
    assert mock_publisher.publish.called
    publish_call = mock_publisher.publish.call_args
    assert "context-utilization" in publish_call.kwargs.get("topic", "")


@pytest.mark.unit
async def test_utilization_scoring_handler_graceful_on_llm_failure() -> None:
    """Handler should emit score 0.0 if LLM call fails."""
    mock_repo = AsyncMock()
    mock_repo.fetch.return_value = [
        {"id": str(uuid4()), "pattern_signature": "test pattern"},
    ]

    mock_publisher = AsyncMock()
    mock_llm_client = AsyncMock()
    mock_llm_client.chat_completion.side_effect = Exception("LLM timeout")

    handler = create_utilization_scoring_dispatch_handler(
        repository=mock_repo,
        publisher=mock_publisher,
        llm_client=mock_llm_client,
    )

    message = {
        "session_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "session_outcome": "success",
        "injected_pattern_ids": [str(uuid4())],
    }

    result = await handler(message)

    assert result["status"] == "scored"
    assert result["utilization_score"] == 0.0
    assert result["detection_method"] == "llm_fallback"
    # Should still emit, with score 0.0 as fallback
    assert mock_publisher.publish.called


@pytest.mark.unit
async def test_utilization_scoring_handler_skips_no_patterns() -> None:
    """Handler should skip if no pattern IDs provided."""
    mock_repo = AsyncMock()
    mock_publisher = AsyncMock()
    mock_llm_client = AsyncMock()

    handler = create_utilization_scoring_dispatch_handler(
        repository=mock_repo,
        publisher=mock_publisher,
        llm_client=mock_llm_client,
    )

    message = {
        "session_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "session_outcome": "success",
        "injected_pattern_ids": [],
    }

    result = await handler(message)

    assert result["status"] == "skipped"
    assert result["reason"] == "no_patterns"
    assert not mock_llm_client.chat_completion.called
    assert not mock_publisher.publish.called


@pytest.mark.unit
async def test_utilization_scoring_handler_skips_patterns_not_found() -> None:
    """Handler should skip if pattern IDs are not found in DB."""
    mock_repo = AsyncMock()
    mock_repo.fetch.return_value = []

    mock_publisher = AsyncMock()
    mock_llm_client = AsyncMock()

    handler = create_utilization_scoring_dispatch_handler(
        repository=mock_repo,
        publisher=mock_publisher,
        llm_client=mock_llm_client,
    )

    message = {
        "session_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "session_outcome": "success",
        "injected_pattern_ids": [str(uuid4())],
    }

    result = await handler(message)

    assert result["status"] == "skipped"
    assert result["reason"] == "patterns_not_found"


@pytest.mark.unit
async def test_utilization_scoring_clamps_score() -> None:
    """Handler should clamp score to 0.0-1.0 range."""
    mock_repo = AsyncMock()
    mock_repo.fetch.return_value = [
        {"id": str(uuid4()), "pattern_signature": "test pattern"},
    ]

    mock_publisher = AsyncMock()
    mock_llm_client = AsyncMock()
    mock_llm_client.chat_completion.return_value = (
        '{"utilization_score": 1.5, "reasoning": "Over-scored"}'
    )

    handler = create_utilization_scoring_dispatch_handler(
        repository=mock_repo,
        publisher=mock_publisher,
        llm_client=mock_llm_client,
    )

    message = {
        "session_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "session_outcome": "success",
        "injected_pattern_ids": [str(uuid4())],
    }

    result = await handler(message)

    assert result["utilization_score"] == 1.0  # Clamped to max
