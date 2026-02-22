# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration tests for PluginIntelligence domain plugin.

Validates the PluginIntelligence implementation against the ProtocolDomainPlugin
protocol, including lifecycle methods, environment-based activation, pool
creation, and idempotent shutdown.

Test Categories:
    - Protocol compliance: isinstance check against ProtocolDomainPlugin
    - Identity: plugin_id and display_name verification
    - Activation: environment-based should_activate behavior
    - Initialization: PostgreSQL pool creation (requires real DB or graceful skip)
    - Shutdown: idempotent cleanup, no-raise guarantees

Exit Criteria:
    - All 8 tests pass
    - Module-level compliance check passes at import time
    - No regressions in existing tests

Ticket: OMN-1978
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any
from uuid import UUID, uuid4

import pytest
from omnibase_infra.runtime.protocol_domain_plugin import ProtocolDomainPlugin

from omniintelligence.runtime.plugin import PluginIntelligence
from tests.integration.conftest import (
    OMNIINTELLIGENCE_DB_URL,
    POSTGRES_AVAILABLE,
)

# =============================================================================
# Minimal Config Stub
# =============================================================================


@dataclass
class _StubContainer:
    """Minimal container stub for plugin tests."""

    service_registry: Any = None


@dataclass
class _StubEventBus:
    """Minimal event bus stub for plugin tests."""

    pass


def _make_config(
    correlation_id: UUID | None = None,
) -> Any:
    """Create a minimal ModelDomainPluginConfig-compatible object for tests.

    Uses the real ModelDomainPluginConfig from omnibase_infra.
    """
    from omnibase_infra.runtime.models import ModelDomainPluginConfig

    return ModelDomainPluginConfig(
        container=_StubContainer(),  # type: ignore[arg-type]
        event_bus=_StubEventBus(),  # type: ignore[arg-type]
        correlation_id=correlation_id or uuid4(),
        input_topic="test.input",
        output_topic="test.output",
        consumer_group="test-consumer",
    )


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
class TestPluginIntelligence:
    """Validate PluginIntelligence against ProtocolDomainPlugin."""

    def test_protocol_compliance(self) -> None:
        """PluginIntelligence must satisfy ProtocolDomainPlugin isinstance check."""
        plugin = PluginIntelligence()
        assert isinstance(plugin, ProtocolDomainPlugin), (
            "PluginIntelligence does not satisfy ProtocolDomainPlugin. "
            "Missing methods or properties in the protocol."
        )

    def test_plugin_id_and_display_name(self) -> None:
        """Verify plugin_id and display_name return correct values."""
        plugin = PluginIntelligence()
        assert plugin.plugin_id == "intelligence"
        assert plugin.display_name == "Intelligence"

    def test_should_activate_with_db_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Plugin should activate when OMNIINTELLIGENCE_DB_URL is set."""
        monkeypatch.setenv(
            "OMNIINTELLIGENCE_DB_URL",
            "postgresql://postgres:pass@192.168.86.200:5436/omniintelligence",
        )
        plugin = PluginIntelligence()
        config = _make_config()
        assert plugin.should_activate(config) is True

    def test_should_not_activate_without_db_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plugin should not activate when OMNIINTELLIGENCE_DB_URL is missing."""
        monkeypatch.delenv("OMNIINTELLIGENCE_DB_URL", raising=False)
        plugin = PluginIntelligence()
        config = _make_config()
        assert plugin.should_activate(config) is False

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not POSTGRES_AVAILABLE or not OMNIINTELLIGENCE_DB_URL,
        reason="PostgreSQL not reachable or OMNIINTELLIGENCE_DB_URL not set",
    )
    async def test_initialize_creates_pool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Initialize should create a PostgreSQL connection pool.

        Requires real PostgreSQL (configured via OMNIINTELLIGENCE_DB_URL).
        Skips gracefully if database is unavailable.
        """
        monkeypatch.setenv("OMNIINTELLIGENCE_DB_URL", OMNIINTELLIGENCE_DB_URL)

        plugin = PluginIntelligence()
        config = _make_config()

        result = await plugin.initialize(config)

        assert result.success, f"Initialize failed: {result.error_message}"
        assert plugin.postgres_pool is not None, (
            "Pool should not be None after successful initialization"
        )
        assert "postgres_pool" in result.resources_created

        # Clean up
        await plugin.shutdown(config)

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not POSTGRES_AVAILABLE or not OMNIINTELLIGENCE_DB_URL,
        reason="PostgreSQL not reachable or OMNIINTELLIGENCE_DB_URL not set",
    )
    async def test_shutdown_closes_pool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Shutdown should close the PostgreSQL pool and clear state."""
        monkeypatch.setenv("OMNIINTELLIGENCE_DB_URL", OMNIINTELLIGENCE_DB_URL)

        plugin = PluginIntelligence()
        config = _make_config()

        # Initialize first
        init_result = await plugin.initialize(config)
        assert init_result.success, f"Initialize failed: {init_result.error_message}"
        assert plugin.postgres_pool is not None

        # Shutdown
        shutdown_result = await plugin.shutdown(config)
        assert shutdown_result.success, (
            f"Shutdown failed: {shutdown_result.error_message}"
        )
        assert plugin.postgres_pool is None, "Pool should be None after shutdown"

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self) -> None:
        """Double shutdown should not raise any exceptions."""
        plugin = PluginIntelligence()
        config = _make_config()

        # Shutdown without initialization - should not raise
        result1 = await plugin.shutdown(config)
        assert result1.success

        # Second shutdown - should also succeed
        result2 = await plugin.shutdown(config)
        assert result2.success

    @pytest.mark.asyncio
    async def test_shutdown_without_initialize(self) -> None:
        """Shutdown before initialize should complete without error."""
        plugin = PluginIntelligence()
        config = _make_config()

        result = await plugin.shutdown(config)
        assert result.success, (
            "Shutdown before initialize should succeed, "
            f"got error: {result.error_message}"
        )


@pytest.mark.integration
class TestEntryPointDiscovery:
    """Validate that PluginIntelligence is discoverable via entry_points."""

    def test_entry_point_discoverable(self) -> None:
        """Entry point 'intelligence' must exist in onex.domain_plugins group."""
        eps = entry_points(group="onex.domain_plugins")
        names = [ep.name for ep in eps]
        assert "intelligence" in names, (
            f"'intelligence' not found in onex.domain_plugins entry points. "
            f"Found: {names}"
        )

    def test_entry_point_loads_plugin_class(self) -> None:
        """Loading the entry point must return the PluginIntelligence class."""
        eps = entry_points(group="onex.domain_plugins")
        matches = [ep for ep in eps if ep.name == "intelligence"]
        assert matches, "No 'intelligence' entry point found"
        loaded = matches[0].load()
        assert loaded is PluginIntelligence, (
            f"Expected PluginIntelligence class, got {loaded!r}"
        )

    def test_entry_point_plugin_satisfies_protocol(self) -> None:
        """Instantiating the loaded class must satisfy ProtocolDomainPlugin."""
        eps = entry_points(group="onex.domain_plugins")
        matches = [ep for ep in eps if ep.name == "intelligence"]
        assert matches, "No 'intelligence' entry point found"
        cls = matches[0].load()
        plugin = cls()
        assert isinstance(plugin, ProtocolDomainPlugin), (
            f"Instance of {cls.__name__} does not satisfy ProtocolDomainPlugin"
        )
        assert plugin.plugin_id == "intelligence"
