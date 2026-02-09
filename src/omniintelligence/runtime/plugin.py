# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Intelligence domain plugin for kernel-level initialization.

This module provides the PluginIntelligence class, which implements
ProtocolDomainPlugin for the Intelligence domain. It encapsulates all
Intelligence-specific initialization code for kernel bootstrap.

The plugin handles:
    - PostgreSQL pool creation for pattern storage
    - Message type registration with RegistryMessageType (OMN-2039)
    - Pattern lifecycle management handler wiring
    - Session feedback processing handler wiring
    - Claude hook event processing handler wiring
    - MessageDispatchEngine wiring for topic-based routing (OMN-2031)
    - Kafka topic subscriptions for intelligence events

Design Pattern:
    The plugin pattern enables the kernel to remain generic while allowing
    domain-specific initialization to be encapsulated in domain modules.
    This follows the dependency inversion principle - the kernel depends
    on the abstract ProtocolDomainPlugin protocol, not this concrete class.

Topic Discovery (OMN-2033):
    Subscribe topics are declared in individual effect node ``contract.yaml``
    files under ``event_bus.subscribe_topics`` and collected at import time
    via ``collect_subscribe_topics_from_contracts()``.  There are no
    hardcoded topic lists in this module.

Configuration:
    The plugin activates based on environment variables:
    - POSTGRES_HOST: Required for plugin activation (pattern storage needs DB)
    - POSTGRES_PORT: Optional (default: 5432)
    - POSTGRES_USER: Optional (default: postgres)
    - POSTGRES_PASSWORD: Required when POSTGRES_HOST is set
    - POSTGRES_DATABASE: Optional (default: omninode_bridge)

Example Usage:
    ```python
    from omniintelligence.runtime.plugin import PluginIntelligence
    from omnibase_infra.runtime.protocol_domain_plugin import (
        ModelDomainPluginConfig,
        RegistryDomainPlugin,
    )

    # Register plugin
    registry = RegistryDomainPlugin()
    registry.register(PluginIntelligence())

    # During kernel bootstrap
    config = ModelDomainPluginConfig(container=container, event_bus=event_bus, ...)
    plugin = registry.get("intelligence")

    if plugin and plugin.should_activate(config):
        await plugin.initialize(config)
        await plugin.wire_handlers(config)
        await plugin.start_consumers(config)
    ```

Related:
    - OMN-1978: Integration test: kernel boots with PluginIntelligence
    - OMN-2031: Replace _noop_handler with MessageDispatchEngine routing
    - OMN-2033: Move intelligence topics to contract.yaml declarations
    - OMN-2039: Register intelligence message types in RegistryMessageType
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg
    from omnibase_core.runtime.runtime_message_dispatch import MessageDispatchEngine
    from omnibase_infra.runtime.registry import RegistryMessageType

from omnibase_infra.runtime.protocol_domain_plugin import (
    ModelDomainPluginConfig,
    ModelDomainPluginResult,
    ProtocolDomainPlugin,
)

from omniintelligence.runtime.contract_topics import (
    canonical_topic_to_dispatch_alias,
    collect_subscribe_topics_from_contracts,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Intelligence Kafka Topics (contract-driven, OMN-2033)
# =============================================================================
# Topics are declared in individual effect node contract.yaml files under
# event_bus.subscribe_topics.  This list is populated at import time by
# scanning those contracts via importlib.resources.
#
# Source contracts:
#   - node_claude_hook_event_effect/contract.yaml
#   - node_pattern_feedback_effect/contract.yaml
#   - node_pattern_lifecycle_effect/contract.yaml

INTELLIGENCE_SUBSCRIBE_TOPICS: list[str] = collect_subscribe_topics_from_contracts()
"""All input topics the intelligence plugin subscribes to (contract-driven)."""


class PluginIntelligence:
    """Intelligence domain plugin for ONEX kernel initialization.

    Provides pattern learning pipeline integration:
    - Pattern storage (PostgreSQL)
    - Pattern lifecycle management
    - Session feedback processing
    - Claude hook event processing

    Resources Created:
        - PostgreSQL connection pool (asyncpg.Pool)
        - Intelligence domain handlers (via wiring module)

    Thread Safety:
        This class is NOT thread-safe. The kernel calls plugin methods
        sequentially during bootstrap. Resource access during runtime
        should be via container-resolved handlers.

    Attributes:
        _pool: PostgreSQL connection pool (created in initialize())
        _unsubscribe_callbacks: Callbacks for Kafka unsubscription
        _shutdown_in_progress: Guard against concurrent shutdown calls
    """

    def __init__(self) -> None:
        """Initialize the plugin with empty state."""
        self._pool: asyncpg.Pool | None = None
        self._unsubscribe_callbacks: list[Callable[[], Awaitable[None]]] = []
        self._shutdown_in_progress: bool = False
        self._services_registered: list[str] = []
        self._dispatch_engine: MessageDispatchEngine | None = None
        self._message_type_registry: RegistryMessageType | None = None

    @property
    def plugin_id(self) -> str:
        """Return unique identifier for this plugin."""
        return "intelligence"

    @property
    def display_name(self) -> str:
        """Return human-readable name for this plugin."""
        return "Intelligence"

    @property
    def postgres_pool(self) -> asyncpg.Pool | None:
        """Return the PostgreSQL pool (for external access)."""
        return self._pool

    @property
    def message_type_registry(self) -> RegistryMessageType | None:
        """Return the message type registry (for external access)."""
        return self._message_type_registry

    def should_activate(self, config: ModelDomainPluginConfig) -> bool:
        """Check if Intelligence should activate based on environment.

        Returns True if POSTGRES_HOST is set, indicating PostgreSQL
        is configured for pattern storage support.

        Args:
            config: Plugin configuration (not used for this check).

        Returns:
            True if POSTGRES_HOST environment variable is set.
        """
        postgres_host = os.getenv("POSTGRES_HOST")
        if not postgres_host:
            logger.debug(
                "Intelligence plugin inactive: POSTGRES_HOST not set "
                "(correlation_id=%s)",
                config.correlation_id,
            )
            return False
        return True

    async def initialize(
        self,
        config: ModelDomainPluginConfig,
    ) -> ModelDomainPluginResult:
        """Initialize Intelligence resources.

        Creates:
        - PostgreSQL connection pool for pattern storage

        Args:
            config: Plugin configuration with container and correlation_id.

        Returns:
            Result with resources_created list on success.
        """
        import asyncpg

        start_time = time.time()
        resources_created: list[str] = []
        correlation_id = config.correlation_id

        try:
            # Create PostgreSQL pool
            postgres_host = os.getenv("POSTGRES_HOST")
            postgres_dsn = (
                f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:"
                f"{os.getenv('POSTGRES_PASSWORD', '')}@"
                f"{postgres_host}:"
                f"{os.getenv('POSTGRES_PORT', '5432')}/"
                f"{os.getenv('POSTGRES_DATABASE', 'omninode_bridge')}"
            )

            self._pool = await asyncpg.create_pool(
                postgres_dsn,
                min_size=2,
                max_size=10,
            )

            # Validate pool creation succeeded
            if self._pool is None:
                duration = time.time() - start_time
                return ModelDomainPluginResult.failed(
                    plugin_id=self.plugin_id,
                    error_message=(
                        "PostgreSQL pool creation returned None - "
                        "connection may have failed"
                    ),
                    duration_seconds=duration,
                )

            resources_created.append("postgres_pool")
            logger.info(
                "Intelligence PostgreSQL pool created (correlation_id=%s)",
                correlation_id,
                extra={
                    "host": postgres_host,
                    "port": os.getenv("POSTGRES_PORT", "5432"),
                    "database": os.getenv("POSTGRES_DATABASE", "omninode_bridge"),
                },
            )

            # Register intelligence message types (OMN-2039)
            # NOTE: This creates a plugin-local registry for the intelligence
            # domain only.  Cross-domain validation requires a kernel-level
            # shared registry (future enhancement).
            from omnibase_infra.runtime.registry import RegistryMessageType

            from omniintelligence.runtime.message_type_registration import (
                register_intelligence_message_types,
            )

            registry = RegistryMessageType()
            registered_types = register_intelligence_message_types(registry)
            registry.freeze()

            # Validate startup -- log warnings but do not fail init
            warnings = registry.validate_startup()
            if warnings:
                for warning in warnings:
                    logger.warning(
                        "Message type registry warning: %s (correlation_id=%s)",
                        warning,
                        correlation_id,
                    )

            self._message_type_registry = registry
            resources_created.append("message_type_registry")

            logger.info(
                "Intelligence message type registry created and frozen "
                "(types=%d, warnings=%d, correlation_id=%s)",
                len(registered_types),
                len(warnings),
                correlation_id,
            )

            duration = time.time() - start_time
            return ModelDomainPluginResult(
                plugin_id=self.plugin_id,
                success=True,
                message="Intelligence plugin initialized",
                resources_created=resources_created,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(
                "Failed to initialize Intelligence plugin (correlation_id=%s)",
                correlation_id,
                extra={"error_type": type(e).__name__},
            )
            # Clean up any resources created before failure
            await self._cleanup_on_failure(config)
            return ModelDomainPluginResult.failed(
                plugin_id=self.plugin_id,
                error_message=str(e),
                duration_seconds=duration,
            )

    async def _cleanup_on_failure(self, config: ModelDomainPluginConfig) -> None:
        """Clean up resources if initialization fails."""
        correlation_id = config.correlation_id

        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception as cleanup_error:
                logger.warning(
                    "Cleanup failed for PostgreSQL pool close: %s (correlation_id=%s)",
                    cleanup_error,
                    correlation_id,
                )
            self._pool = None

    async def wire_handlers(
        self,
        config: ModelDomainPluginConfig,
    ) -> ModelDomainPluginResult:
        """Register Intelligence handlers with the container.

        Delegates to wire_intelligence_handlers from the wiring module to
        register pattern learning pipeline handlers.

        Args:
            config: Plugin configuration with container.

        Returns:
            Result with services_registered list on success.
        """
        from omniintelligence.runtime.wiring import wire_intelligence_handlers

        start_time = time.time()
        correlation_id = config.correlation_id

        if self._pool is None:
            return ModelDomainPluginResult.failed(
                plugin_id=self.plugin_id,
                error_message=("Cannot wire handlers: PostgreSQL pool not initialized"),
            )

        try:
            self._services_registered = await wire_intelligence_handlers(
                pool=self._pool,
                config=config,
            )
            duration = time.time() - start_time

            logger.info(
                "Intelligence handlers wired (correlation_id=%s)",
                correlation_id,
                extra={"services": self._services_registered},
            )

            return ModelDomainPluginResult(
                plugin_id=self.plugin_id,
                success=True,
                message="Intelligence handlers wired",
                services_registered=self._services_registered,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(
                "Failed to wire Intelligence handlers (correlation_id=%s)",
                correlation_id,
            )
            return ModelDomainPluginResult.failed(
                plugin_id=self.plugin_id,
                error_message=str(e),
                duration_seconds=duration,
            )

    async def wire_dispatchers(
        self,
        config: ModelDomainPluginConfig,
    ) -> ModelDomainPluginResult:
        """Wire intelligence domain dispatchers with MessageDispatchEngine.

        Creates a plugin-local MessageDispatchEngine and registers all 3
        intelligence domain handlers and routes. The engine is frozen after
        registration and stored for use in start_consumers().

        Dispatchers registered (OMN-2032):
            1. claude-hook-event: Claude Code hook event processing
            2. session-outcome: Session feedback recording (Phase 1 stub)
            3. pattern-lifecycle-transition: Pattern lifecycle transitions
               (Phase 1 stub)

        Args:
            config: Plugin configuration.

        Returns:
            Result indicating success/failure and dispatchers registered.
        """
        from omniintelligence.runtime.dispatch_handlers import (
            create_intelligence_dispatch_engine,
        )

        start_time = time.time()
        correlation_id = config.correlation_id

        try:
            self._dispatch_engine = create_intelligence_dispatch_engine()

            duration = time.time() - start_time
            logger.info(
                "Intelligence dispatch engine wired "
                "(routes=%d, handlers=%d, correlation_id=%s)",
                self._dispatch_engine.route_count,
                self._dispatch_engine.handler_count,
                correlation_id,
            )

            return ModelDomainPluginResult(
                plugin_id=self.plugin_id,
                success=True,
                message="Intelligence dispatch engine wired",
                resources_created=["dispatch_engine"],
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(
                "Failed to wire intelligence dispatch engine (correlation_id=%s)",
                correlation_id,
            )
            return ModelDomainPluginResult.failed(
                plugin_id=self.plugin_id,
                error_message=str(e),
                duration_seconds=duration,
            )

    async def start_consumers(
        self,
        config: ModelDomainPluginConfig,
    ) -> ModelDomainPluginResult:
        """Start intelligence event consumers.

        Subscribes to intelligence input topics:
        - onex.cmd.omniintelligence.claude-hook-event.v1 (dispatch engine)
        - onex.cmd.omniintelligence.session-outcome.v1 (dispatch engine)
        - onex.cmd.omniintelligence.pattern-lifecycle-transition.v1 (dispatch engine)

        All 3 topics are routed through MessageDispatchEngine when the
        dispatch engine is available (OMN-2032). Without the engine,
        topics fall back to noop handlers.

        Uses duck typing to check for subscribe capability on event_bus.

        Args:
            config: Plugin configuration with event_bus.

        Returns:
            Result with unsubscribe_callbacks for cleanup.
        """
        start_time = time.time()
        correlation_id = config.correlation_id

        # Duck typing: check for subscribe capability
        if not hasattr(config.event_bus, "subscribe"):
            return ModelDomainPluginResult.skipped(
                plugin_id=self.plugin_id,
                reason="Event bus does not support subscribe",
            )

        try:
            # Build per-topic handler map
            topic_handlers = self._build_topic_handlers(correlation_id)

            unsubscribe_callbacks: list[Callable[[], Awaitable[None]]] = []

            dispatched_topics: list[str] = []
            noop_topics: list[str] = []

            for topic in INTELLIGENCE_SUBSCRIBE_TOPICS:
                handler = topic_handlers[topic]
                is_dispatched = self._dispatch_engine is not None

                logger.info(
                    "Subscribing to intelligence topic: %s "
                    "(mode=%s, correlation_id=%s)",
                    topic,
                    "dispatch_engine" if is_dispatched else "noop",
                    correlation_id,
                )
                unsub = await config.event_bus.subscribe(
                    topic=topic,
                    group_id=f"{config.consumer_group}-intelligence",
                    on_message=handler,
                )
                unsubscribe_callbacks.append(unsub)

                if is_dispatched:
                    dispatched_topics.append(topic)
                else:
                    noop_topics.append(topic)

            self._unsubscribe_callbacks = unsubscribe_callbacks

            duration = time.time() - start_time
            logger.info(
                "Intelligence consumers started: %d topics "
                "(%d dispatched, %d noop, correlation_id=%s)",
                len(INTELLIGENCE_SUBSCRIBE_TOPICS),
                len(dispatched_topics),
                len(noop_topics),
                correlation_id,
            )

            return ModelDomainPluginResult(
                plugin_id=self.plugin_id,
                success=True,
                message=(
                    f"Intelligence consumers started "
                    f"({len(dispatched_topics)} dispatched, "
                    f"{len(noop_topics)} noop)"
                ),
                duration_seconds=duration,
                unsubscribe_callbacks=unsubscribe_callbacks,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(
                "Failed to start intelligence consumers (correlation_id=%s)",
                correlation_id,
            )
            return ModelDomainPluginResult.failed(
                plugin_id=self.plugin_id,
                error_message=str(e),
                duration_seconds=duration,
            )

    def _build_topic_handlers(
        self,
        correlation_id: Any,
    ) -> dict[str, Callable[[Any], Awaitable[None]]]:
        """Build handler map for each intelligence topic.

        Returns a dict mapping topic -> async callback. All intelligence
        topics use the dispatch engine when available (OMN-2032); without
        the engine, all topics fall back to a noop placeholder.

        Topic -> dispatch alias conversion is handled generically by
        ``canonical_topic_to_dispatch_alias`` (OMN-2033), removing the
        need for per-topic constant mappings.

        Args:
            correlation_id: Correlation ID for tracing in noop handler.

        Returns:
            Dict mapping each INTELLIGENCE_SUBSCRIBE_TOPICS entry to a handler.
        """

        async def _noop_handler(_msg: Any) -> None:
            """Placeholder handler for topics not yet routed via dispatch."""
            logger.debug(
                "Intelligence event received on noop handler "
                "(subscription_correlation_id=%s)",
                correlation_id,
            )

        handlers: dict[str, Callable[[Any], Awaitable[None]]] = {}

        # Dispatch engine routing: convert canonical topics (.cmd.) to
        # dispatch-compatible aliases (.commands.) generically.
        # _engine is captured as a local to allow mypy to narrow the type.
        _engine: MessageDispatchEngine | None = None
        if self._dispatch_engine is not None:
            from omniintelligence.runtime.dispatch_handlers import (
                create_dispatch_callback,
            )

            _engine = self._dispatch_engine

        for topic in INTELLIGENCE_SUBSCRIBE_TOPICS:
            if _engine is not None:
                dispatch_alias = canonical_topic_to_dispatch_alias(topic)
                handlers[topic] = create_dispatch_callback(
                    engine=_engine,
                    dispatch_topic=dispatch_alias,
                )
            else:
                handlers[topic] = _noop_handler

        return handlers

    async def shutdown(
        self,
        config: ModelDomainPluginConfig,
    ) -> ModelDomainPluginResult:
        """Clean up Intelligence resources.

        Closes the PostgreSQL pool. Guards against concurrent shutdown
        calls via _shutdown_in_progress flag.

        Args:
            config: Plugin configuration.

        Returns:
            Result indicating cleanup success/failure.
        """
        # Guard against concurrent shutdown calls
        if self._shutdown_in_progress:
            return ModelDomainPluginResult.skipped(
                plugin_id=self.plugin_id,
                reason="Shutdown already in progress",
            )
        self._shutdown_in_progress = True

        try:
            return await self._do_shutdown(config)
        finally:
            self._shutdown_in_progress = False

    async def _do_shutdown(
        self,
        config: ModelDomainPluginConfig,
    ) -> ModelDomainPluginResult:
        """Internal shutdown implementation.

        Args:
            config: Plugin configuration.

        Returns:
            Result indicating cleanup success/failure.
        """
        start_time = time.time()
        correlation_id = config.correlation_id
        errors: list[str] = []

        # Unsubscribe from topics
        for unsub in self._unsubscribe_callbacks:
            try:
                await unsub()
            except Exception as unsub_error:
                errors.append(f"unsubscribe: {unsub_error}")
                logger.warning(
                    "Failed to unsubscribe intelligence consumer: %s "
                    "(correlation_id=%s)",
                    unsub_error,
                    correlation_id,
                )
        self._unsubscribe_callbacks = []

        # Close pool
        if self._pool is not None:
            try:
                await self._pool.close()
                logger.debug(
                    "Intelligence PostgreSQL pool closed (correlation_id=%s)",
                    correlation_id,
                )
            except Exception as pool_close_error:
                errors.append(f"pool_close: {pool_close_error}")
                logger.warning(
                    "Failed to close Intelligence PostgreSQL pool: %s "
                    "(correlation_id=%s)",
                    pool_close_error,
                    correlation_id,
                )
            self._pool = None

        self._services_registered = []
        self._dispatch_engine = None
        self._message_type_registry = None

        duration = time.time() - start_time

        if errors:
            return ModelDomainPluginResult.failed(
                plugin_id=self.plugin_id,
                error_message="; ".join(errors),
                duration_seconds=duration,
            )

        return ModelDomainPluginResult.succeeded(
            plugin_id=self.plugin_id,
            message="Intelligence resources cleaned up",
            duration_seconds=duration,
        )

    def get_status_line(self) -> str:
        """Get status line for kernel banner.

        Returns:
            Status string indicating enabled state.
        """
        if self._pool is None:
            return "disabled"
        return "enabled (PostgreSQL)"


# Verify protocol compliance at module load time
_: ProtocolDomainPlugin = PluginIntelligence()

__all__: list[str] = [
    "INTELLIGENCE_SUBSCRIBE_TOPICS",
    "PluginIntelligence",
]
