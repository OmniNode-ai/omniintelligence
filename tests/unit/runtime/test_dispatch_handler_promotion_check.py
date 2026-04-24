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


@pytest.mark.unit
def test_dispatch_alias_is_not_canonical_publisher_topic() -> None:
    """Dispatch routes use legacy engine aliases; publishers keep canonical cmd topics."""
    from omniintelligence.constants import TOPIC_PROMOTION_CHECK_CMD_V1

    assert TOPIC_PROMOTION_CHECK_CMD_V1.startswith("onex.cmd.")
    assert DISPATCH_ALIAS_PROMOTION_CHECK != TOPIC_PROMOTION_CHECK_CMD_V1


@pytest.mark.unit
def test_utilization_route_uses_dispatch_alias() -> None:
    """Utilization route should bridge canonical cmd topic to dispatch alias."""
    import re
    from pathlib import Path

    dispatch_handlers_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "omniintelligence"
        / "runtime"
        / "dispatch_handlers.py"
    )
    dispatch_handlers_source = dispatch_handlers_path.read_text()

    assert re.search(
        r"route_id=\"intelligence-utilization-scoring-route\".*?"
        r"topic_pattern=canonical_topic_to_dispatch_alias\(\s*"
        r"TOPIC_UTILIZATION_SCORING_CMD_V1\s*\)",
        dispatch_handlers_source,
        flags=re.DOTALL,
    )
