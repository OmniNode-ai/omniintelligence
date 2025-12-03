"""Relationship Detection Compute Node Entry Point.

This module allows running the compute node as a standalone service:
    python -m omniintelligence.nodes.relationship_detection_compute.v1_0_0
"""

import asyncio
import logging
import os
import signal
import sys

from omniintelligence.nodes.relationship_detection_compute.v1_0_0.compute import (
    RelationshipDetectionCompute,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the relationship detection compute node."""
    logger.info("Starting Relationship Detection Compute Node v1.0.0")

    # Create compute node instance
    node = RelationshipDetectionCompute(container=None)

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig: int, frame: object) -> None:
        logger.info(f"Received signal {sig}, initiating shutdown")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        logger.info("Relationship Detection Compute Node ready - waiting for shutdown signal")
        # Keep the node running until shutdown signal
        await shutdown_event.wait()
    except Exception as e:
        logger.error(f"Node error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Relationship Detection Compute Node shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
