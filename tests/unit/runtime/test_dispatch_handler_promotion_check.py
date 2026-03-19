# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Tests for promotion-check dispatch handler.

Reference: OMN-5498 - Create promotion-check dispatch handler.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from omniintelligence.runtime.dispatch_handler_promotion_check import (
    DISPATCH_ALIAS_PROMOTION_CHECK,
    create_promotion_check_dispatch_handler,
)


@pytest.mark.unit
async def test_promotion_check_dispatch_handler_calls_auto_promote() -> None:
    """Handler should call handle_auto_promote_check with correct args."""
    mock_repository = AsyncMock()
    mock_idempotency = AsyncMock()
    mock_producer = AsyncMock()

    handler = create_promotion_check_dispatch_handler(
        repository=mock_repository,
        idempotency_store=mock_idempotency,
        kafka_producer=mock_producer,
    )

    mock_result = {
        "candidates_checked": 10,
        "candidates_promoted": 3,
        "provisionals_checked": 5,
        "provisionals_promoted": 1,
        "results": [],
    }

    envelope = SimpleNamespace(
        payload={"correlation_id": str(uuid4())},
    )
    context = SimpleNamespace()

    with patch(
        "omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote.handle_auto_promote_check",
        new_callable=AsyncMock,
        return_value=mock_result,
    ) as mock_auto_promote:
        result = await handler(envelope, context)

    assert mock_auto_promote.called
    assert "candidates=3/10" in result
    assert "provisionals=1/5" in result


@pytest.mark.unit
async def test_promotion_check_dispatch_handler_generates_correlation_id() -> None:
    """Handler should generate a correlation ID when none is provided."""
    mock_repository = AsyncMock()
    mock_producer = AsyncMock()

    handler = create_promotion_check_dispatch_handler(
        repository=mock_repository,
        kafka_producer=mock_producer,
    )

    mock_result = {
        "candidates_checked": 0,
        "candidates_promoted": 0,
        "provisionals_checked": 0,
        "provisionals_promoted": 0,
        "results": [],
    }

    envelope = SimpleNamespace(payload={})
    context = SimpleNamespace()

    with patch(
        "omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote.handle_auto_promote_check",
        new_callable=AsyncMock,
        return_value=mock_result,
    ) as mock_auto_promote:
        result = await handler(envelope, context)

    # Should have been called with a UUID correlation_id
    call_kwargs = mock_auto_promote.call_args.kwargs
    assert call_kwargs["correlation_id"] is not None


@pytest.mark.unit
def test_dispatch_alias_follows_naming_convention() -> None:
    """Dispatch alias should follow the onex.commands.* naming convention."""
    assert DISPATCH_ALIAS_PROMOTION_CHECK.startswith("onex.commands.")
    assert "promotion-check-requested" in DISPATCH_ALIAS_PROMOTION_CHECK
