# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Stub launcher for ONEX node containers.

This module provides a minimal health-check-only process for containerized
nodes that are awaiting RuntimeHostProcess integration from omnibase_infra.

Usage:
    python -m omniintelligence.runtime.stub_launcher --node-type orchestrator
    python -m omniintelligence.runtime.stub_launcher --node-type reducer
    python -m omniintelligence.runtime.stub_launcher --node-type effect --node-name pattern_storage

Why this exists:
    Node directories must NOT contain __main__.py (that's an anti-pattern).
    Nodes are run via RuntimeHostProcess, which is not yet available as a
    dependency. This shared stub launcher provides container health checks
    until RuntimeHostProcess integration is complete.

This module will be removed when BaseRuntimeHostProcess (from omnibase_infra)
is available and wired into the deployment entrypoints.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def _get_log_level() -> int:
    """Get log level from environment with safe fallback."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        return logging.INFO
    return level


logging.basicConfig(
    level=_get_log_level(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _run_health_server(
    service_name: str,
    host: str = "0.0.0.0",
    port: int = 8000,
) -> HTTPServer:
    """Run a health check HTTP server in a daemon thread.

    NOTE: Binds to 0.0.0.0 for container health probes (Kubernetes/Docker).
    No authentication -- intended for internal network only.
    """

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path in ("/health", "/"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response: dict[str, object] = {
                    "status": "healthy",
                    "service": service_name,
                    "mode": "stub",
                }
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            logger.debug("Health check: %s", format % args)

    try:
        server = HTTPServer((host, port), HealthHandler)
    except OSError as exc:
        logger.error("Health server failed to bind to port %d: %s", port, exc)
        raise

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check server running on http://%s:%d/health", host, port)
    return server


async def run_stub(node_type: str, node_name: str | None = None) -> None:
    """Run stub node process with health check endpoint."""
    service_name = f"intelligence-{node_type}"
    if node_name:
        service_name = f"intelligence-{node_name}"

    logger.info("=" * 60)
    logger.info("Starting %s (stub mode)", service_name)
    logger.info("=" * 60)
    logger.warning(
        "STUB MODE: Awaiting RuntimeHostProcess integration from omnibase_infra. "
        "This process responds to health checks but does not process requests."
    )

    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def handle_signal(sig_name: str) -> None:
        logger.info("Received %s, initiating shutdown", sig_name)
        shutdown_event.set()

    try:
        loop.add_signal_handler(signal.SIGTERM, handle_signal, "SIGTERM")
        loop.add_signal_handler(signal.SIGINT, handle_signal, "SIGINT")
    except NotImplementedError:
        signal.signal(signal.SIGTERM, lambda *_: shutdown_event.set())
        signal.signal(signal.SIGINT, lambda *_: shutdown_event.set())

    try:
        health_port = int(os.getenv("HEALTH_PORT", "8000"))
    except ValueError:
        logger.warning("Invalid HEALTH_PORT value, using default 8000")
        health_port = 8000
    health_server = _run_health_server(service_name, port=health_port)

    try:
        logger.info("%s ready - waiting for shutdown signal", service_name)
        await shutdown_event.wait()
    finally:
        logger.info("Shutting down health server...")
        shutdown_thread = threading.Thread(target=health_server.shutdown)
        shutdown_thread.start()
        shutdown_thread.join(timeout=5.0)
        if shutdown_thread.is_alive():
            logger.warning("Health server shutdown timed out after 5s")
        logger.info("%s shutdown complete", service_name)


def main() -> None:
    """Parse arguments and run the stub launcher."""
    parser = argparse.ArgumentParser(description="ONEX node stub launcher")
    parser.add_argument(
        "--node-type",
        required=True,
        choices=["orchestrator", "reducer", "compute", "effect"],
        help="Type of node to launch",
    )
    parser.add_argument(
        "--node-name",
        default=None,
        help="Specific node name (for compute/effect types)",
    )
    args = parser.parse_args()

    if args.node_type in ("compute", "effect") and not args.node_name:
        parser.error(f"--node-name is required for {args.node_type} nodes")

    asyncio.run(run_stub(args.node_type, args.node_name))


if __name__ == "__main__":
    main()
