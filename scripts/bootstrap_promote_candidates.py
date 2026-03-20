#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""One-time script to run promotion check on all candidate patterns.

This triggers the auto-promote handler which will use the bootstrap path
(confidence >= 0.8, recurrence >= 2, distinct_days >= 2) for candidates with
zero injection history.

Re-running is safe because the promotion handler is idempotent
(already-promoted patterns are filtered by SQL status check).

Usage:
    uv run python scripts/bootstrap_promote_candidates.py --dry-run
    uv run python scripts/bootstrap_promote_candidates.py --execute
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import uuid4


async def main(dry_run: bool) -> None:
    """Emit a promotion-check command to Kafka."""
    # Import from canonical constants to avoid hardcoded topic lint violation
    from omniintelligence.constants import TOPIC_PROMOTION_CHECK_CMD_V1

    topic = TOPIC_PROMOTION_CHECK_CMD_V1
    correlation_id = str(uuid4())

    payload = json.dumps(
        {
            "correlation_id": correlation_id,
            "dry_run": dry_run,
        }
    ).encode()

    if dry_run:
        print(f"[DRY RUN] Would emit promotion-check to {topic}")  # noqa: T201
        print(f"  correlation_id: {correlation_id}")  # noqa: T201
        print("  Run with --execute to actually emit")  # noqa: T201
        return

    from aiokafka import AIOKafkaProducer

    bootstrap_servers = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
    )
    await producer.start()
    try:
        await producer.send_and_wait(
            topic,
            key=correlation_id.encode(),
            value=payload,
        )
        print(f"Emitted promotion-check command")  # noqa: T201
        print(f"  topic: {topic}")  # noqa: T201
        print(f"  correlation_id: {correlation_id}")  # noqa: T201
        print(f"  bootstrap_servers: {bootstrap_servers}")  # noqa: T201
        print("  Monitor omniintelligence logs for results")  # noqa: T201
    finally:
        await producer.stop()


if __name__ == "__main__":
    execute = "--execute" in sys.argv
    asyncio.run(main(dry_run=not execute))
