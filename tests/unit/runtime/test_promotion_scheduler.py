# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Tests for periodic promotion-check scheduler.

Reference: OMN-5499 - Add periodic promotion-check scheduler to plugin lifecycle.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from omniintelligence.runtime.promotion_scheduler import run_promotion_scheduler


@pytest.mark.unit
async def test_promotion_scheduler_emits_on_interval() -> None:
    """Scheduler should emit promotion-check command at configured interval."""
    mock_publisher = AsyncMock()

    task = asyncio.create_task(
        run_promotion_scheduler(
            publisher=mock_publisher,
            topic="onex.cmd.omniintelligence.promotion-check-requested.v1",
            interval_seconds=0.1,  # fast for testing
        )
    )

    await asyncio.sleep(0.35)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert mock_publisher.publish.call_count >= 2
    call_kwargs = mock_publisher.publish.call_args_list[0].kwargs
    assert (
        call_kwargs["topic"] == "onex.cmd.omniintelligence.promotion-check-requested.v1"
    )


@pytest.mark.unit
async def test_promotion_scheduler_survives_publish_failure() -> None:
    """Scheduler should continue after a publish failure."""
    mock_publisher = AsyncMock()
    # First call fails, subsequent calls succeed
    mock_publisher.publish.side_effect = [
        Exception("Kafka unavailable"),
        None,
        None,
    ]

    task = asyncio.create_task(
        run_promotion_scheduler(
            publisher=mock_publisher,
            interval_seconds=0.05,
        )
    )

    await asyncio.sleep(0.2)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    # Should have attempted multiple publishes despite the first failure
    assert mock_publisher.publish.call_count >= 2


@pytest.mark.unit
async def test_promotion_scheduler_payload_structure() -> None:
    """Emitted payload should contain correlation_id and dry_run=False."""
    import json

    mock_publisher = AsyncMock()

    task = asyncio.create_task(
        run_promotion_scheduler(
            publisher=mock_publisher,
            interval_seconds=0.05,
        )
    )

    await asyncio.sleep(0.1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert mock_publisher.publish.call_count >= 1
    call_kwargs = mock_publisher.publish.call_args_list[0].kwargs
    payload = json.loads(call_kwargs["value"])
    assert "correlation_id" in payload
    assert payload["dry_run"] is False
