# SPDX-License-Identifier: Apache-2.0
"""Tests for stub_launcher module.

Covers argument parsing validation, HEALTH_PORT fallback,
service_name construction, and health endpoint responses.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from omniintelligence.runtime.stub_launcher import (
    _get_log_level,
    _run_health_server,
    main,
    run_stub,
)

pytestmark = pytest.mark.unit


def _make_pre_set_event() -> asyncio.Event:
    """Create an asyncio.Event that is already set (for immediate shutdown)."""
    event = asyncio.Event()
    event.set()
    return event


def _fake_server() -> MagicMock:
    """Create a fake health server with a no-op shutdown."""
    server = MagicMock()
    server.shutdown = MagicMock()
    return server


# ---------------------------------------------------------------------------
# _get_log_level
# ---------------------------------------------------------------------------


class TestGetLogLevel:
    def test_default_is_info(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LOG_LEVEL", None)
            assert _get_log_level() == 20  # logging.INFO

    def test_debug_level(self) -> None:
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            assert _get_log_level() == 10

    def test_case_insensitive(self) -> None:
        with patch.dict(os.environ, {"LOG_LEVEL": "warning"}):
            assert _get_log_level() == 30  # logging.WARNING

    def test_invalid_falls_back_to_info(self) -> None:
        with patch.dict(os.environ, {"LOG_LEVEL": "NONSENSE"}):
            assert _get_log_level() == 20


# ---------------------------------------------------------------------------
# _run_health_server
# ---------------------------------------------------------------------------


class TestHealthServer:
    def test_health_endpoint_returns_200(self) -> None:
        server = _run_health_server("test-service", port=0)
        port = server.server_address[1]
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as resp:
                assert resp.status == 200
                body = json.loads(resp.read())
                assert body["status"] == "healthy"
                assert body["service"] == "test-service"
                assert body["mode"] == "stub"
        finally:
            server.shutdown()

    def test_root_endpoint_returns_200(self) -> None:
        server = _run_health_server("test-service", port=0)
        port = server.server_address[1]
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
                assert resp.status == 200
        finally:
            server.shutdown()

    def test_unknown_path_returns_404(self) -> None:
        server = _run_health_server("test-service", port=0)
        port = server.server_address[1]
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/unknown")
            with pytest.raises(urllib.error.HTTPError, match="404"):
                urllib.request.urlopen(req)
        finally:
            server.shutdown()


# ---------------------------------------------------------------------------
# run_stub - service_name construction
# ---------------------------------------------------------------------------


class TestRunStubServiceName:
    def test_service_name_with_node_type_only(self) -> None:
        """node_type alone -> intelligence-{node_type}."""
        captured: list[str] = []

        def capture(name: str, **_kwargs: object) -> MagicMock:
            captured.append(name)
            return _fake_server()

        async def _run() -> None:
            with (
                patch("asyncio.Event", return_value=_make_pre_set_event()),
                patch(
                    "omniintelligence.runtime.stub_launcher._run_health_server",
                    side_effect=capture,
                ),
            ):
                await run_stub("orchestrator")

        asyncio.run(_run())
        assert captured[0] == "intelligence-orchestrator"

    def test_service_name_with_node_name(self) -> None:
        """node_name overrides -> intelligence-{node_name}."""
        captured: list[str] = []

        def capture(name: str, **_kwargs: object) -> MagicMock:
            captured.append(name)
            return _fake_server()

        async def _run() -> None:
            with (
                patch("asyncio.Event", return_value=_make_pre_set_event()),
                patch(
                    "omniintelligence.runtime.stub_launcher._run_health_server",
                    side_effect=capture,
                ),
            ):
                await run_stub("effect", node_name="pattern_storage")

        asyncio.run(_run())
        assert captured[0] == "intelligence-pattern_storage"


# ---------------------------------------------------------------------------
# HEALTH_PORT fallback
# ---------------------------------------------------------------------------


class TestHealthPortFallback:
    def test_invalid_health_port_uses_default(self) -> None:
        """Invalid HEALTH_PORT should fall back to 8000."""
        captured_ports: list[int] = []

        def capture(_name: str, **kwargs: object) -> MagicMock:
            captured_ports.append(kwargs.get("port", -1))
            return _fake_server()

        async def _run() -> None:
            with (
                patch.dict(os.environ, {"HEALTH_PORT": "not_a_number"}),
                patch("asyncio.Event", return_value=_make_pre_set_event()),
                patch(
                    "omniintelligence.runtime.stub_launcher._run_health_server",
                    side_effect=capture,
                ),
            ):
                await run_stub("orchestrator")

        asyncio.run(_run())
        assert captured_ports[0] == 8000

    def test_valid_health_port_is_used(self) -> None:
        """Valid HEALTH_PORT should be passed through."""
        captured_ports: list[int] = []

        def capture(_name: str, **kwargs: object) -> MagicMock:
            captured_ports.append(kwargs.get("port", -1))
            return _fake_server()

        async def _run() -> None:
            with (
                patch.dict(os.environ, {"HEALTH_PORT": "9999"}),
                patch("asyncio.Event", return_value=_make_pre_set_event()),
                patch(
                    "omniintelligence.runtime.stub_launcher._run_health_server",
                    side_effect=capture,
                ),
            ):
                await run_stub("orchestrator")

        asyncio.run(_run())
        assert captured_ports[0] == 9999


# ---------------------------------------------------------------------------
# main() argument parsing
# ---------------------------------------------------------------------------


class TestMainArgParsing:
    def test_compute_without_node_name_errors(self) -> None:
        """compute type requires --node-name."""
        with (
            patch("sys.argv", ["stub_launcher", "--node-type", "compute"]),
            pytest.raises(SystemExit, match="2"),
        ):
            main()

    def test_effect_without_node_name_errors(self) -> None:
        """effect type requires --node-name."""
        with (
            patch("sys.argv", ["stub_launcher", "--node-type", "effect"]),
            pytest.raises(SystemExit, match="2"),
        ):
            main()

    def test_orchestrator_without_node_name_succeeds(self) -> None:
        """orchestrator does NOT require --node-name."""
        with (
            patch("sys.argv", ["stub_launcher", "--node-type", "orchestrator"]),
            patch("omniintelligence.runtime.stub_launcher.asyncio") as mock_asyncio,
        ):
            main()
            mock_asyncio.run.assert_called_once()

    def test_invalid_node_type_errors(self) -> None:
        with (
            patch("sys.argv", ["stub_launcher", "--node-type", "invalid"]),
            pytest.raises(SystemExit, match="2"),
        ):
            main()
