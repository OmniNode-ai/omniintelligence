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

from omniintelligence.models.runtime_timeouts import runtime_timeouts
from omniintelligence.models.topics import read_contract_topic
from omniintelligence.protocols import ProtocolKafkaPublisher

logger = logging.getLogger(__name__)

PROMOTION_CHECK_TOPIC = read_contract_topic(
    "node_pattern_promotion_effect", "cmd", "promotion-check-requested"
)


async def run_promotion_scheduler(
    *,
    publisher: ProtocolKafkaPublisher,
    topic: str = PROMOTION_CHECK_TOPIC,
    interval_seconds: float | None = None,
) -> None:
    """Emit promotion-check commands on a periodic interval.

    Runs as a background asyncio task. Cancel the task to stop.

    Args:
        publisher: Kafka publisher for emitting commands.
        topic: Target topic for promotion-check commands.
        interval_seconds: Interval between emissions (default: promotion_interval_s of
            runtime_timeouts.yaml).
    """
    interval_seconds = interval_seconds or runtime_timeouts().promotion_interval_s
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
            await publisher.publish(topic=topic, key=correlation_id, value=payload)
            logger.debug(
                "Emitted promotion-check command",
                extra={"correlation_id": correlation_id},
            )
        except Exception:
            logger.exception("Failed to emit promotion-check command")


__all__ = [
    "PROMOTION_CHECK_TOPIC",
    "run_promotion_scheduler",
]
