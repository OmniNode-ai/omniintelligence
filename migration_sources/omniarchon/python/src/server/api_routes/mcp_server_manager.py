"""
MCP Server Manager

Manages the MCP Docker container lifecycle, including:
- Container start/stop operations
- Log streaming
- Status monitoring
- WebSocket log broadcasting
"""

import asyncio
import time
from collections import deque
from datetime import datetime
from typing import Any

from docker.errors import APIError, NotFound
from fastapi import WebSocket
from server.config.logfire_config import mcp_logger, safe_set_attribute, safe_span

import docker


class MCPServerManager:
    """Manages the MCP Docker container lifecycle."""

    def __init__(self):
        self.container_name = None  # Will be resolved dynamically
        self.docker_client = None
        self.container = None
        self.status: str = "stopped"
        self.start_time: float | None = None
        self.logs: deque = deque(maxlen=1000)  # Keep last 1000 log entries
        self.log_websockets: list[WebSocket] = []
        self.log_reader_task: asyncio.Task | None = None
        self._operation_lock = (
            asyncio.Lock()
        )  # Prevent concurrent start/stop operations
        self._last_operation_time = 0
        self._min_operation_interval = 2.0  # Minimum 2 seconds between operations
        self._initialize_docker_client()

    def _resolve_container(self):
        """Simple container resolution - just use fixed name."""
        if not self.docker_client:
            return None

        try:
            # Simple: Just look for the fixed container name
            container = self.docker_client.containers.get("archon-mcp")
            self.container_name = "archon-mcp"
            mcp_logger.info("Found MCP container")
            return container
        except NotFound:
            mcp_logger.warning("MCP container not found - is it running?")
            self.container_name = "archon-mcp"
            return None

    def _initialize_docker_client(self):
        """Initialize Docker client and get container reference."""
        try:
            self.docker_client = docker.from_env()
            self.container = self._resolve_container()
            if not self.container:
                mcp_logger.warning("MCP container not found during initialization")
        except Exception as e:
            mcp_logger.error(f"Failed to initialize Docker client: {e!s}")
            self.docker_client = None

    def _get_container_status(self) -> str:
        """Get the current status of the MCP container."""
        if not self.docker_client:
            return "docker_unavailable"

        try:
            if self.container:
                self.container.reload()  # Refresh container info
            else:
                # Try to resolve container again if we don't have it
                self.container = self._resolve_container()
                if not self.container:
                    return "not_found"

            return self.container.status
        except NotFound:
            # Try to resolve again in case container was recreated
            self.container = self._resolve_container()
            if self.container:
                return self.container.status
            return "not_found"
        except Exception as e:
            mcp_logger.error(f"Error getting container status: {e!s}")
            return "error"

    def _is_log_reader_active(self) -> bool:
        """Check if the log reader task is active."""
        return self.log_reader_task is not None and not self.log_reader_task.done()

    async def _ensure_log_reader_running(self):
        """Ensure the log reader task is running if container is active."""
        if not self.container:
            return

        # Cancel existing task if any
        if self.log_reader_task:
            self.log_reader_task.cancel()
            try:
                await self.log_reader_task
            except asyncio.CancelledError:
                pass

        # Start new log reader task
        self.log_reader_task = asyncio.create_task(self._read_container_logs())
        self._add_log("INFO", "Connected to MCP container logs")
        mcp_logger.info(
            f"Started log reader for already-running container: {self.container_name}"
        )

    async def start_server(self) -> dict[str, Any]:
        """Start the MCP Docker container."""
        async with self._operation_lock:
            # Check throttling
            current_time = time.time()
            if current_time - self._last_operation_time < self._min_operation_interval:
                wait_time = self._min_operation_interval - (
                    current_time - self._last_operation_time
                )
                mcp_logger.warning(
                    f"Start operation throttled, please wait {wait_time:.1f}s"
                )
                return {
                    "success": False,
                    "status": self.status,
                    "message": f"Please wait {wait_time:.1f}s before starting server again",
                }

            with safe_span("mcp_server_start") as span:
                safe_set_attribute(span, "action", "start_server")

                if not self.docker_client:
                    mcp_logger.error("Docker client not available")
                    return {
                        "success": False,
                        "status": "docker_unavailable",
                        "message": "Docker is not available. Is Docker socket mounted?",
                    }

                # Check current container status
                container_status = self._get_container_status()

                if container_status == "not_found":
                    mcp_logger.error(f"Container {self.container_name} not found")
                    return {
                        "success": False,
                        "status": "not_found",
                        "message": f"MCP container {self.container_name} not found. Run docker-compose up -d archon-mcp",
                    }

                if container_status == "running":
                    mcp_logger.warning(
                        "MCP server start attempted while already running"
                    )
                    return {
                        "success": False,
                        "status": "running",
                        "message": "MCP server is already running",
                    }

                try:
                    # Start the container
                    self.container.start()
                    self.status = "starting"
                    self.start_time = time.time()
                    self._last_operation_time = time.time()
                    self._add_log("INFO", "MCP container starting...")
                    mcp_logger.info(f"Starting MCP container: {self.container_name}")
                    safe_set_attribute(span, "container_id", self.container.id)

                    # Start reading logs from the container
                    if self.log_reader_task:
                        self.log_reader_task.cancel()
                    self.log_reader_task = asyncio.create_task(
                        self._read_container_logs()
                    )

                    # Give it a moment to start
                    await asyncio.sleep(2)

                    # Check if container is running
                    self.container.reload()
                    if self.container.status == "running":
                        self.status = "running"
                        self._add_log("INFO", "MCP container started successfully")
                        mcp_logger.info(
                            f"MCP container started successfully - container_id={self.container.id}"
                        )
                        safe_set_attribute(span, "success", True)
                        safe_set_attribute(span, "status", "running")
                        return {
                            "success": True,
                            "status": self.status,
                            "message": "MCP server started successfully",
                            "container_id": self.container.id[:12],
                        }
                    else:
                        self.status = "failed"
                        self._add_log(
                            "ERROR",
                            f"MCP container failed to start. Status: {self.container.status}",
                        )
                        mcp_logger.error(
                            f"MCP container failed to start - status: {self.container.status}"
                        )
                        safe_set_attribute(span, "success", False)
                        safe_set_attribute(span, "status", self.container.status)
                        return {
                            "success": False,
                            "status": self.status,
                            "message": f"MCP container failed to start. Status: {self.container.status}",
                        }

                except APIError as e:
                    self.status = "failed"
                    self._add_log("ERROR", f"Docker API error: {e!s}")
                    mcp_logger.error(
                        f"Docker API error during MCP startup - error={e!s}"
                    )
                    safe_set_attribute(span, "success", False)
                    safe_set_attribute(span, "error", str(e))
                    return {
                        "success": False,
                        "status": self.status,
                        "message": f"Docker API error: {e!s}",
                    }
                except Exception as e:
                    self.status = "failed"
                    self._add_log("ERROR", f"Failed to start MCP server: {e!s}")
                    mcp_logger.error(
                        f"Exception during MCP server startup - error={e!s}, error_type={type(e).__name__}"
                    )
                    safe_set_attribute(span, "success", False)
                    safe_set_attribute(span, "error", str(e))
                    return {
                        "success": False,
                        "status": self.status,
                        "message": f"Failed to start MCP server: {e!s}",
                    }

    async def stop_server(self) -> dict[str, Any]:
        """Stop the MCP Docker container."""
        async with self._operation_lock:
            # Check throttling
            current_time = time.time()
            if current_time - self._last_operation_time < self._min_operation_interval:
                wait_time = self._min_operation_interval - (
                    current_time - self._last_operation_time
                )
                mcp_logger.warning(
                    f"Stop operation throttled, please wait {wait_time:.1f}s"
                )
                return {
                    "success": False,
                    "status": self.status,
                    "message": f"Please wait {wait_time:.1f}s before stopping server again",
                }

            with safe_span("mcp_server_stop") as span:
                safe_set_attribute(span, "action", "stop_server")

                if not self.docker_client:
                    mcp_logger.error("Docker client not available")
                    return {
                        "success": False,
                        "status": "docker_unavailable",
                        "message": "Docker is not available",
                    }

                # Check current container status
                container_status = self._get_container_status()

                if container_status not in ["running", "restarting"]:
                    mcp_logger.warning(
                        f"MCP server stop attempted when not running. Status: {container_status}"
                    )
                    return {
                        "success": False,
                        "status": container_status,
                        "message": f"MCP server is not running (status: {container_status})",
                    }

                try:
                    self.status = "stopping"
                    self._add_log("INFO", "Stopping MCP container...")
                    mcp_logger.info(f"Stopping MCP container: {self.container_name}")
                    safe_set_attribute(span, "container_id", self.container.id)

                    # Cancel log reading task
                    if self.log_reader_task:
                        self.log_reader_task.cancel()
                        try:
                            await self.log_reader_task
                        except asyncio.CancelledError:
                            pass

                    # Stop the container with timeout
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.container.stop(timeout=10),  # 10 second timeout
                    )

                    self.status = "stopped"
                    self.start_time = None
                    self._last_operation_time = time.time()
                    self._add_log("INFO", "MCP container stopped")
                    mcp_logger.info("MCP container stopped successfully")
                    safe_set_attribute(span, "success", True)
                    safe_set_attribute(span, "status", "stopped")

                    return {
                        "success": True,
                        "status": self.status,
                        "message": "MCP server stopped successfully",
                    }

                except APIError as e:
                    self._add_log("ERROR", f"Docker API error: {e!s}")
                    mcp_logger.error(f"Docker API error during MCP stop - error={e!s}")
                    safe_set_attribute(span, "success", False)
                    safe_set_attribute(span, "error", str(e))
                    return {
                        "success": False,
                        "status": self.status,
                        "message": f"Docker API error: {e!s}",
                    }
                except Exception as e:
                    self._add_log("ERROR", f"Error stopping MCP server: {e!s}")
                    mcp_logger.error(
                        f"Exception during MCP server stop - error={e!s}, error_type={type(e).__name__}"
                    )
                    safe_set_attribute(span, "success", False)
                    safe_set_attribute(span, "error", str(e))
                    return {
                        "success": False,
                        "status": self.status,
                        "message": f"Error stopping MCP server: {e!s}",
                    }

    def get_status(self) -> dict[str, Any]:
        """Get the current server status."""
        # Update status based on actual container state
        container_status = self._get_container_status()

        # Map Docker statuses to our statuses
        status_map = {
            "running": "running",
            "restarting": "restarting",
            "paused": "paused",
            "exited": "stopped",
            "dead": "stopped",
            "created": "stopped",
            "removing": "stopping",
            "not_found": "not_found",
            "docker_unavailable": "docker_unavailable",
            "error": "error",
        }

        self.status = status_map.get(container_status, "unknown")

        # If container is running but log reader isn't active, start it
        if self.status == "running" and not self._is_log_reader_active():
            asyncio.create_task(self._ensure_log_reader_running())

        uptime = None
        if self.status == "running" and self.start_time:
            uptime = int(time.time() - self.start_time)
        elif self.status == "running" and self.container:
            # Try to get uptime from container info
            try:
                self.container.reload()
                started_at = self.container.attrs["State"]["StartedAt"]
                # Parse ISO format datetime
                from datetime import datetime

                started_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                uptime = int(
                    (datetime.now(started_time.tzinfo) - started_time).total_seconds()
                )
            except Exception:
                pass

        # Convert log entries to strings for backward compatibility
        recent_logs = []
        for log in list(self.logs)[-10:]:
            if isinstance(log, dict):
                recent_logs.append(f"[{log['level']}] {log['message']}")
            else:
                recent_logs.append(str(log))

        return {
            "status": self.status,
            "uptime": uptime,
            "logs": recent_logs,
            "container_status": container_status,  # Include raw Docker status
        }

    def _add_log(self, level: str, message: str):
        """Add a log entry and broadcast to connected WebSockets."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message,
        }
        self.logs.append(log_entry)

        # Broadcast to all connected WebSockets
        asyncio.create_task(self._broadcast_log(log_entry))

    async def _broadcast_log(self, log_entry: dict[str, Any]):
        """Broadcast log entry to all connected WebSockets."""
        disconnected = []
        for ws in self.log_websockets:
            try:
                await ws.send_json(log_entry)
            except Exception:
                disconnected.append(ws)

        # Remove disconnected WebSockets
        for ws in disconnected:
            self.log_websockets.remove(ws)

    async def _read_container_logs(self):
        """Read logs from Docker container."""
        if not self.container:
            return

        try:
            # Stream logs from container
            log_generator = self.container.logs(stream=True, follow=True, tail=100)

            while True:
                try:
                    log_line = await asyncio.get_event_loop().run_in_executor(
                        None, next, log_generator, None
                    )

                    if log_line is None:
                        break

                    # Decode bytes to string
                    if isinstance(log_line, bytes):
                        log_line = log_line.decode("utf-8").strip()

                    if log_line:
                        level, message = self._parse_log_line(log_line)
                        self._add_log(level, message)

                except StopIteration:
                    break
                except Exception as e:
                    self._add_log("ERROR", f"Log reading error: {e!s}")
                    break

        except asyncio.CancelledError:
            pass
        except APIError as e:
            if "container not found" not in str(e).lower():
                self._add_log("ERROR", f"Docker API error reading logs: {e!s}")
        except Exception as e:
            self._add_log("ERROR", f"Error reading container logs: {e!s}")
        finally:
            # Check if container stopped
            try:
                self.container.reload()
                if self.container.status not in ["running", "restarting"]:
                    self._add_log(
                        "INFO",
                        f"MCP container stopped with status: {self.container.status}",
                    )
            except Exception:
                pass

    def _parse_log_line(self, line: str) -> tuple[str, str]:
        """Parse a log line to extract level and message."""
        line = line.strip()
        if not line:
            return "INFO", ""

        # Try to extract log level from common formats
        if line.startswith("[") and "]" in line:
            end_bracket = line.find("]")
            potential_level = line[1:end_bracket].upper()
            if potential_level in ["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"]:
                return potential_level, line[end_bracket + 1 :].strip()

        # Check for common log level indicators
        line_lower = line.lower()
        if any(
            word in line_lower for word in ["error", "exception", "failed", "critical"]
        ):
            return "ERROR", line
        elif any(word in line_lower for word in ["warning", "warn"]):
            return "WARNING", line
        elif any(word in line_lower for word in ["debug"]):
            return "DEBUG", line
        else:
            return "INFO", line

    def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get historical logs."""
        logs = list(self.logs)
        if limit > 0:
            logs = logs[-limit:]
        return logs

    def clear_logs(self):
        """Clear the log buffer."""
        self.logs.clear()
        self._add_log("INFO", "Logs cleared")

    async def add_websocket(self, websocket: WebSocket):
        """Add a WebSocket connection for log streaming."""
        await websocket.accept()
        self.log_websockets.append(websocket)

        # Send connection info but NOT historical logs
        # The frontend already fetches historical logs via the /logs endpoint
        await websocket.send_json(
            {
                "type": "connection",
                "message": "WebSocket connected for log streaming",
            }
        )

    def remove_websocket(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.log_websockets:
            self.log_websockets.remove(websocket)
