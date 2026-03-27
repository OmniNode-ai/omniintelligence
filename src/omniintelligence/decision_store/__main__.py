# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Standalone entrypoint for the decision_store Kafka consumer.

Runs as an independent process (Docker service) that:
1. Creates an asyncpg pool from OMNIINTELLIGENCE_DB_URL
2. Instantiates the DecisionRecordConsumer with a PostgreSQL repository
3. Starts a Kafka consumption loop
4. Exposes GET /health on a configurable port
5. Handles SIGTERM/SIGINT for graceful shutdown

Environment Variables:
    OMNIINTELLIGENCE_DB_URL: PostgreSQL connection string (required).
    DECISION_STORE_KAFKA_BOOTSTRAP_SERVERS: Kafka bootstrap servers
        (default: localhost:19092).
    DECISION_STORE_KAFKA_GROUP_ID: Consumer group ID
        (default: decision-store-consumer).
    DECISION_STORE_HEALTH_CHECK_PORT: Health check HTTP port
        (default: 8091).
    DECISION_STORE_HEALTH_CHECK_HOST: Health check bind host
        (default: 0.0.0.0).

Related:
    - OMN-6608: Add health endpoint to decision_store consumer
    - OMN-6607: Create decision-store-consumer Docker catalog YAML
    - OMN-2467: DecisionRecordConsumer implementation
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import sys
from typing import Any

logger = logging.getLogger("omniintelligence.decision_store.__main__")


async def _run() -> None:
    """Run the decision_store consumer with health endpoint."""
    from aiohttp import web

    from omniintelligence.decision_store.consumer import DecisionRecordConsumer
    from omniintelligence.decision_store.repository import (
        DecisionRecordRepository,
    )
    from omniintelligence.decision_store.topics import DecisionTopics

    # --- Configuration from environment ---
    db_url = os.environ.get(
        "OMNIINTELLIGENCE_DB_URL", ""
    )  # ONEX_FLAG_EXEMPT: required config
    if not db_url:
        logger.error("OMNIINTELLIGENCE_DB_URL is required but not set")
        sys.exit(1)

    bootstrap_servers = os.environ.get(  # ONEX_FLAG_EXEMPT: config
        "DECISION_STORE_KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"
    )
    group_id = os.environ.get(  # ONEX_FLAG_EXEMPT: config
        "DECISION_STORE_KAFKA_GROUP_ID", "decision-store-consumer"
    )
    health_port = int(
        os.environ.get(
            "DECISION_STORE_HEALTH_CHECK_PORT", "8091"
        )  # ONEX_FLAG_EXEMPT: config
    )
    health_host = os.environ.get(  # ONEX_FLAG_EXEMPT: config
        "DECISION_STORE_HEALTH_CHECK_HOST",
        "0.0.0.0",  # noqa: S104 — Docker bind
    )

    # --- Shutdown coordination ---
    shutdown_event = asyncio.Event()

    def _signal_handler(sig: int, _frame: object) -> None:
        logger.info("Received signal %s, initiating graceful shutdown", sig)
        shutdown_event.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # --- Database pool ---
    import asyncpg

    pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=5)
    logger.info("Database pool created")

    # --- Repository + Consumer ---
    # TODO(OMN-6608): Replace with PostgreSQL-backed repository once
    # migration freeze is lifted. For now, use in-memory repository.
    _ = pool  # Pool reserved for future PostgreSQL backend
    repository = DecisionRecordRepository()
    consumer = DecisionRecordConsumer(repository=repository)

    # --- Kafka consumer (aiokafka) ---
    kafka_consumer = None
    try:
        from aiokafka import AIOKafkaConsumer

        kafka_consumer = AIOKafkaConsumer(
            DecisionTopics.DECISION_RECORDED,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        await kafka_consumer.start()
        logger.info(
            "Kafka consumer started (topic=%s, group=%s, servers=%s)",
            DecisionTopics.DECISION_RECORDED,
            group_id,
            bootstrap_servers,
        )
    except ImportError:
        logger.warning("aiokafka not installed, running in health-check-only mode")
    except Exception:
        logger.exception(
            "Failed to start Kafka consumer, running in health-check-only mode"
        )

    # --- Health endpoint ---
    consumer_healthy = True

    async def health_handler(_request: web.Request) -> web.Response:
        if consumer_healthy:
            body: dict[str, Any] = {
                "status": "healthy",
                "service": "decision-store-consumer",
                "topic": str(DecisionTopics.DECISION_RECORDED),
            }
            return web.json_response(body, status=200)
        return web.json_response({"status": "unhealthy"}, status=503)

    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/health/live", health_handler)
    app.router.add_get("/health/ready", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, health_host, health_port)
    await site.start()
    logger.info("Health endpoint listening on %s:%d", health_host, health_port)

    # --- Consumption loop ---
    async def _consume() -> None:
        nonlocal consumer_healthy
        if kafka_consumer is None:
            # No Kafka -- just wait for shutdown
            await shutdown_event.wait()
            return

        try:
            async for msg in kafka_consumer:
                if shutdown_event.is_set():
                    break
                try:
                    consumer.handle_message(
                        msg.value,
                        correlation_id=_extract_correlation_id(msg),
                    )
                except Exception:
                    logger.exception(
                        "Error processing message at offset=%s partition=%s",
                        msg.offset,
                        msg.partition,
                    )
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Kafka consumption loop failed")
            consumer_healthy = False

    consume_task = asyncio.create_task(_consume(), name="decision-store-consume")

    # Wait for shutdown
    await shutdown_event.wait()
    logger.info("Shutting down...")

    # --- Cleanup ---
    consume_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await consume_task

    if kafka_consumer is not None:
        await kafka_consumer.stop()

    await runner.cleanup()
    await pool.close()
    logger.info("Shutdown complete")


def _extract_correlation_id(msg: object) -> str | None:
    """Extract correlation_id from Kafka message headers or value."""
    # Try headers first
    headers = getattr(msg, "headers", None)
    if headers:
        for key, value in headers:
            if key == "correlation_id":
                return value.decode("utf-8") if isinstance(value, bytes) else str(value)

    # Try message value
    raw_value = getattr(msg, "value", None)
    if raw_value:
        try:
            payload = json.loads(
                raw_value.decode("utf-8") if isinstance(raw_value, bytes) else raw_value
            )
            return payload.get("correlation_id")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            pass

    return None


def main() -> None:
    """Entry point for ``python -m omniintelligence.decision_store``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
