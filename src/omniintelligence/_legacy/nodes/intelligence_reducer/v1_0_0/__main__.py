"""Intelligence Reducer Node Entry Point.

This module allows running the reducer node as a standalone service:
    python -m omniintelligence.nodes.intelligence_reducer.v1_0_0
"""

import asyncio
import logging
import os
import signal
import sys

from omniintelligence._legacy.models import ModelReducerConfig
from omniintelligence.nodes.intelligence_reducer.v1_0_0.reducer import (
    IntelligenceReducer,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the intelligence reducer node."""
    logger.info("Starting Intelligence Reducer Node v1.0.0")

    # Load configuration from environment
    config = ModelReducerConfig(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:password@localhost:5432/omniintelligence",
        ),
        enable_lease_management=os.getenv("ENABLE_LEASE_MANAGEMENT", "true").lower() == "true",
        lease_timeout_seconds=int(os.getenv("LEASE_TIMEOUT_SECONDS", "300")),
        max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
    )

    # Create reducer instance
    reducer = IntelligenceReducer(config=config)

    # Initialize database connection
    await reducer.initialize()

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig: int, frame: object) -> None:
        logger.info(f"Received signal {sig}, initiating shutdown")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        logger.info("Intelligence Reducer Node ready - waiting for shutdown signal")
        # Keep the node running until shutdown signal
        await shutdown_event.wait()
    except Exception as e:
        logger.error(f"Node error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Graceful shutdown
        await reducer.shutdown()
        logger.info("Intelligence Reducer Node shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
