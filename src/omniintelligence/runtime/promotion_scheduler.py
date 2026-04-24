# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Periodic promotion-check command emitter.

Emits promotion-check-requested commands at a configurable interval
so the dispatch engine triggers the auto-promote handler.

Reference: OMN-5499 - Add periodic promotion-check scheduler to plugin lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from omniintelligence.constants import TOPIC_PROMOTION_CHECK_CMD_V1
from omniintelligence.protocols import ProtocolKafkaPublisher

logger = logging.getLogger(__name__)

PROMOTION_CHECK_TOPIC = (
    TOPIC_PROMOTION_CHECK_CMD_V1  # onex-topic-allow: re-exported alias
)
DEFAULT_INTERVAL_SECONDS: float = 300.0  # 5 minutes


async def run_promotion_scheduler(
    *,
    publisher: ProtocolKafkaPublisher,
    topic: str = PROMOTION_CHECK_TOPIC,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
) -> None:
    """Emit promotion-check commands on a periodic interval.

    Runs as a background asyncio task. Cancel the task to stop.

    Args:
        publisher: Kafka publisher for emitting commands.
        topic: Target topic for promotion-check commands.
        interval_seconds: Interval between emissions (default: 300s / 5 minutes).
    """
    logger.info(
        "Promotion scheduler started",
        extra={"interval_seconds": interval_seconds, "topic": topic},
    )

    while True:
        await asyncio.sleep(interval_seconds)

        correlation_id = str(uuid4())
        payload: dict[str, object] = {
            "correlation_id": correlation_id,
            "dry_run": False,
        }

        try:
            await publisher.publish(
                topic=topic,
                key=correlation_id,
                value=payload,
            )
            logger.debug(
                "Emitted promotion-check command",
                extra={"correlation_id": correlation_id},
            )
        except Exception:
            logger.exception("Failed to emit promotion-check command")


__all__ = [
    "DEFAULT_INTERVAL_SECONDS",
    "PROMOTION_CHECK_TOPIC",
    "run_promotion_scheduler",
]
