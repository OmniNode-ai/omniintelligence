"""Intelligence Reducer Node Entry Point.

This module allows running the reducer node as a standalone service:
    python -m omniintelligence.nodes.node_intelligence_reducer

WARNING: This is a stub entrypoint. The full reducer implementation requires:
    - ONEX container injection with proper dependencies
    - PostgreSQL connection for FSM state storage
    - Kafka consumer/producer configuration

For production use, the reducer should be initialized via RuntimeHostProcess
with a properly configured ModelONEXContainer.
"""

import asyncio
import logging
import os
import signal
import sys
from http.server import HTTPServer
from typing import Any


def _get_log_level() -> int:
    """Get log level from environment with safe fallback.

    Returns logging.INFO if LOG_LEVEL is invalid or not set.
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        # Invalid level name, fall back to INFO
        return logging.INFO
    return level


# Configure logging
logging.basicConfig(
    level=_get_log_level(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def run_health_server(host: str = "0.0.0.0", port: int = 8000) -> HTTPServer:
    """Run a simple health check HTTP server.

    Args:
        host: Host to bind to
        port: Port to bind to

    Returns:
        HTTPServer instance for shutdown management.
    """
    from http.server import BaseHTTPRequestHandler
    import json
    import threading

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/health" or self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response: dict[str, Any] = {
                    "status": "healthy",
                    "service": "intelligence-reducer",
                    "version": "1.0.0",
                }
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            logger.debug("Health check: %s", format % args)

    server = HTTPServer((host, port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health check server running on http://{host}:{port}/health")
    return server


def _shutdown_health_server(health_server: HTTPServer, timeout: float = 5.0) -> None:
    """Shut down health server with timeout.

    Args:
        health_server: The HTTPServer instance to shut down.
        timeout: Maximum time to wait for shutdown in seconds.
    """
    import threading

    shutdown_thread = threading.Thread(target=health_server.shutdown)
    shutdown_thread.start()
    shutdown_thread.join(timeout=timeout)
    if shutdown_thread.is_alive():
        logger.warning(f"Health server shutdown timed out after {timeout}s")


async def main() -> None:
    """Run the intelligence reducer node."""
    logger.info("=" * 60)
    logger.info("Starting Intelligence Reducer Node")
    logger.info("=" * 60)

    # WARNING: Stub mode - no actual FSM processing without container injection
    logger.warning(
        "STUB MODE: Running without ONEX container injection. "
        "This node will respond to health checks but not process state transitions."
    )

    # Setup signal handlers for graceful shutdown using asyncio-native approach
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def handle_signal(sig_name: str) -> None:
        logger.info(f"Received {sig_name}, initiating shutdown")
        shutdown_event.set()

    # Register signal handlers with the event loop (Unix-style, more robust for asyncio)
    try:
        loop.add_signal_handler(signal.SIGTERM, handle_signal, "SIGTERM")
        loop.add_signal_handler(signal.SIGINT, handle_signal, "SIGINT")
    except NotImplementedError:
        # Windows doesn't support add_signal_handler, fall back to signal.signal
        def signal_handler(sig: int, _frame: object) -> None:
            logger.info(f"Received signal {sig}, initiating shutdown")
            shutdown_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    # Start health check server (synchronous - runs in daemon thread)
    health_port = int(os.getenv("HEALTH_PORT", "8000"))
    health_server = run_health_server(port=health_port)

    try:
        logger.info("Intelligence Reducer Node ready - waiting for shutdown signal")
        logger.info("Health endpoint available at /health")
        # Keep the node running until shutdown signal
        await shutdown_event.wait()
    except asyncio.CancelledError:
        # Task cancellation during shutdown - must re-raise to preserve semantics
        logger.info("Event loop cancelled, shutting down")
        raise
    except Exception as e:
        # Intentionally broad: top-level entry point catch-all to ensure any
        # unexpected error is logged before exiting with error code. This is
        # the last line of defense for unhandled exceptions in the main loop.
        logger.error(f"Node error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Remove signal handlers to prevent issues during cleanup
        try:
            loop.remove_signal_handler(signal.SIGTERM)
            loop.remove_signal_handler(signal.SIGINT)
        except (NotImplementedError, ValueError):
            # Windows or handlers already removed
            pass

        # Shut down the health server cleanly with timeout
        logger.info("Shutting down health server...")
        _shutdown_health_server(health_server)
        logger.info("Intelligence Reducer Node shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
