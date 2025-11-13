"""
Background Task Status Tracker Initialization

Provides async initialization function for the background task status tracker.
Separated from main app.py to avoid file modification conflicts during edits.

Created: 2025-11-12
"""

import logging
import os
from typing import Optional

from src.utils.background_task_status_tracker import (
    BackgroundTaskStatusTracker,
    set_global_tracker,
)

logger = logging.getLogger(__name__)


async def initialize_background_task_tracker() -> Optional[BackgroundTaskStatusTracker]:
    """
    Initialize the background task status tracker with Valkey/Redis cache.

    Returns:
        BackgroundTaskStatusTracker instance (with or without cache)

    Raises:
        Never - always returns a tracker instance (local-only if cache unavailable)
    """
    try:
        import redis.asyncio as aioredis

        cache_enabled = os.getenv("ENABLE_CACHE", "true").lower() == "true"
        valkey_url = os.getenv("VALKEY_URL", "redis://archon-valkey:6379/0")

        if cache_enabled:
            try:
                redis_client = await aioredis.from_url(
                    valkey_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )
                # Test connection
                await redis_client.ping()

                tracker = BackgroundTaskStatusTracker(
                    cache_client=redis_client, ttl_seconds=86400
                )
                set_global_tracker(tracker)

                logger.info(
                    "✅ Background task status tracker initialized with Redis cache"
                )
                return tracker

            except Exception as cache_error:
                logger.warning(
                    f"Failed to connect to Redis cache: {cache_error}. "
                    "Falling back to local-only tracking."
                )
                # Fall through to local-only mode

        # Initialize without cache (cache disabled or connection failed)
        tracker = BackgroundTaskStatusTracker(cache_client=None)
        set_global_tracker(tracker)

        logger.info("✅ Background task status tracker initialized (local-only mode)")
        return tracker

    except Exception as e:
        # Last resort fallback - always succeed
        logger.error(
            f"Unexpected error initializing background task tracker: {e}. "
            "Using minimal local-only tracker."
        )

        tracker = BackgroundTaskStatusTracker(cache_client=None)
        set_global_tracker(tracker)
        return tracker
