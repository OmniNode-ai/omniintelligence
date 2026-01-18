"""Memgraph Graph Effect Node Entry Point.

This module allows running the effect node as a standalone service:
    python -m omniintelligence.nodes.memgraph_graph_effect.v1_0_0
"""

import asyncio
import logging
import os
import signal
import sys

from omniintelligence.nodes.memgraph_graph_effect.v1_0_0.effect import (
    NodeMemgraphGraphEffect,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the Memgraph graph effect node."""
    logger.info("Starting Memgraph Graph Effect Node v1.0.0")

    # Create effect node instance
    node = NodeMemgraphGraphEffect(container=None)

    # Initialize the node (connect to Memgraph)
    await node.initialize()

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig: int, frame: object) -> None:
        logger.info(f"Received signal {sig}, initiating shutdown")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        logger.info("Memgraph Graph Effect Node ready - waiting for shutdown signal")
        # Keep the node running until shutdown signal
        await shutdown_event.wait()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except asyncio.CancelledError:
        logger.info("Event loop cancelled, shutting down")
    except Exception as e:
        # Intentionally broad: top-level entry point catch-all for unexpected errors
        logger.error(f"Node error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Graceful shutdown
        await node.shutdown()
        logger.info("Memgraph Graph Effect Node shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
