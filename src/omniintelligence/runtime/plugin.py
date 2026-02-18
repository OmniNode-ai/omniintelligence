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
    - OMNIINTELLIGENCE_DB_URL: Required for plugin activation (pattern storage needs DB)
      Format: postgresql://user:password@host:port/database
    - OMNIINTELLIGENCE_PUBLISH_INTROSPECTION: Controls whether this container publishes
      node introspection events and starts heartbeat loops. Defaults to false/off.
      Only the single designated container (omninode-runtime) should set this to true.
      Worker and effects containers leave this unset so they process intelligence events
      without emitting duplicate heartbeats for the same deterministic node IDs.
      Valid truthy values: "true", "1", "yes" (case-insensitive).

      Rationale (OMN-2342): All runtime containers share x-runtime-env and thus all
      activate PluginIntelligence. Without this gate, every container independently
      calls publish_intelligence_introspection() and starts heartbeat loops for the
      same UUID5-derived node IDs, producing 3x the expected heartbeat traffic.

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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnibase_core.protocols.event_bus.protocol_event_bus import ProtocolEventBus
    from omnibase_core.runtime.runtime_message_dispatch import MessageDispatchEngine
    from omnibase_infra.idempotency.store_postgres import StoreIdempotencyPostgres
    from omnibase_infra.runtime.db import PostgresRepositoryRuntime
    from omnibase_infra.runtime.registry import RegistryMessageType

    from omniintelligence.runtime.introspection import (
        IntelligenceNodeIntrospectionProxy,
    )

from omnibase_infra.runtime.protocol_domain_plugin import (
    ModelDomainPluginConfig,
    ModelDomainPluginResult,
    ProtocolDomainPlugin,
)

from omniintelligence.runtime.contract_topics import (
    canonical_topic_to_dispatch_alias,
    collect_subscribe_topics_from_contracts,
)
from omniintelligence.utils.db_url import safe_db_url_display as _safe_db_url_display
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)

_PUBLISH_INTROSPECTION_ENV_VAR = "OMNIINTELLIGENCE_PUBLISH_INTROSPECTION"
_TRUTHY_VALUES = frozenset({"true", "1", "yes"})


def _introspection_publishing_enabled() -> bool:
    """Return True if this container is designated to publish introspection events.

    Reads the OMNIINTELLIGENCE_PUBLISH_INTROSPECTION environment variable.
    Defaults to False (safe/off) when absent or set to a non-truthy value.

    This gate ensures that only the single designated container (omninode-runtime)
    publishes node introspection events and starts heartbeat loops. Worker and
    effects containers set this to false (or leave it unset) so that they
    continue processing intelligence events without emitting duplicate heartbeats
    for the same deterministic node IDs (OMN-2342).

    Returns:
        True if the env var is set to a truthy value ("true", "1", "yes").
        False otherwise (absent, empty, or any other value).
    """
    value = os.getenv(_PUBLISH_INTROSPECTION_ENV_VAR, "").strip().lower()
    return value in _TRUTHY_VALUES


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
#   - node_pattern_learning_effect/contract.yaml
#   - node_pattern_lifecycle_effect/contract.yaml
#   - node_pattern_storage_effect/contract.yaml

try:
    INTELLIGENCE_SUBSCRIBE_TOPICS: list[str] = collect_subscribe_topics_from_contracts()
except Exception:
    logger.error(
        "Failed to collect subscribe topics from contracts — plugin will not receive events",
        exc_info=True,
    )
    INTELLIGENCE_SUBSCRIBE_TOPICS: list[str] = []  # type: ignore[no-redef]
"""All input topics the intelligence plugin subscribes to (contract-driven)."""


class PluginIntelligence:
    """Intelligence domain plugin for ONEX kernel initialization.

    Provides pattern learning pipeline integration:
    - Pattern storage (PostgreSQL)
    - Pattern lifecycle management
    - Session feedback processing
    - Claude hook event processing

    Resources Created:
        - PostgreSQL connection pool (via omnibase_infra effect boundary)
        - Intelligence domain handlers (via wiring module)

    Thread Safety:
        This class is NOT thread-safe. The kernel calls plugin methods
        sequentially during bootstrap. Resource access during runtime
        should be via container-resolved handlers.

    Attributes:
        _pool: PostgreSQL connection pool (shared from idempotency store)
        _pattern_runtime: Contract-driven repository runtime
        _idempotency_store: omnibase_infra idempotency store (owns the pool)
        _unsubscribe_callbacks: Callbacks for Kafka unsubscription
        _shutdown_in_progress: Guard against concurrent shutdown calls
    """

    def __init__(self) -> None:
        """Initialize the plugin with empty state."""
        self._pool: object | None = None  # shared from idempotency store
        self._pattern_runtime: PostgresRepositoryRuntime | None = None
        self._idempotency_store: StoreIdempotencyPostgres | None = None
        self._unsubscribe_callbacks: list[Callable[[], Awaitable[None]]] = []
        self._shutdown_in_progress: bool = False
        self._services_registered: list[str] = []
        self._dispatch_engine: MessageDispatchEngine | None = None
        self._message_type_registry: RegistryMessageType | None = None
        self._event_bus: ProtocolEventBus | None = None
        self._introspection_nodes: list[str] = []
        self._introspection_proxies: list[IntelligenceNodeIntrospectionProxy] = []

    @property
    def plugin_id(self) -> str:
        """Return unique identifier for this plugin."""
        return "intelligence"

    @property
    def display_name(self) -> str:
        """Return human-readable name for this plugin."""
        return "Intelligence"

    @property
    def postgres_pool(self) -> object | None:
        """Return the PostgreSQL pool (for external access)."""
        return self._pool

    @property
    def message_type_registry(self) -> RegistryMessageType | None:
        """Return the message type registry (for external access)."""
        return self._message_type_registry

    def should_activate(self, config: ModelDomainPluginConfig) -> bool:
        """Check if Intelligence should activate based on environment.

        Returns True if OMNIINTELLIGENCE_DB_URL is set, indicating PostgreSQL
        is configured for pattern storage support.

        Args:
            config: Plugin configuration (not used for this check).

        Returns:
            True if OMNIINTELLIGENCE_DB_URL environment variable is set.
        """
        db_url = os.getenv("OMNIINTELLIGENCE_DB_URL")
        if not db_url:
            logger.debug(
                "Intelligence plugin inactive: OMNIINTELLIGENCE_DB_URL not set "
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
        - StoreIdempotencyPostgres for pattern lifecycle idempotency (owns its pool)
        - PostgresRepositoryRuntime for contract-driven DB access (shares idempotency pool)

        All database access flows through omnibase_infra's effect boundary.
        No direct database driver imports in this module.

        Args:
            config: Plugin configuration with container and correlation_id.

        Returns:
            Result with resources_created list on success.
        """
        from omnibase_infra.idempotency.models.model_postgres_idempotency_store_config import (
            ModelPostgresIdempotencyStoreConfig,
        )
        from omnibase_infra.idempotency.store_postgres import StoreIdempotencyPostgres
        from omnibase_infra.runtime.db import PostgresRepositoryRuntime

        from omniintelligence.repositories.adapter_pattern_store import load_contract

        start_time = time.time()
        resources_created: list[str] = []
        correlation_id = config.correlation_id

        try:
            # Read DB URL from environment
            db_url = os.getenv("OMNIINTELLIGENCE_DB_URL")
            if not db_url:
                duration = time.time() - start_time
                return ModelDomainPluginResult.failed(
                    plugin_id=self.plugin_id,
                    error_message=(
                        "OMNIINTELLIGENCE_DB_URL is not set. "
                        "Set it to a postgresql:// connection URL."
                    ),
                    duration_seconds=duration,
                )

            try:
                min_pool = int(os.getenv("POSTGRES_MIN_POOL_SIZE", "2"))
            except ValueError:
                min_pool = 2
                logger.warning(
                    "Invalid POSTGRES_MIN_POOL_SIZE, using default: %d",
                    min_pool,
                )
            try:
                max_pool = int(os.getenv("POSTGRES_MAX_POOL_SIZE", "10"))
            except ValueError:
                max_pool = 10
                logger.warning(
                    "Invalid POSTGRES_MAX_POOL_SIZE, using default: %d",
                    max_pool,
                )

            try:
                command_timeout = float(os.getenv("POSTGRES_COMMAND_TIMEOUT", "60.0"))
            except ValueError:
                command_timeout = 60.0
                logger.warning(
                    "Invalid POSTGRES_COMMAND_TIMEOUT, using default: %s",
                    command_timeout,
                )

            # Create idempotency store via omnibase_infra (owns its own pool)
            idempotency_config = ModelPostgresIdempotencyStoreConfig(
                dsn=db_url,
                pool_min_size=min_pool,
                pool_max_size=max_pool,
                command_timeout=command_timeout,
            )
            idempotency_store = StoreIdempotencyPostgres(config=idempotency_config)
            await idempotency_store.initialize()
            self._idempotency_store = idempotency_store
            resources_created.append("idempotency_store")

            # Share the idempotency store's pool for the repository runtime.
            # This avoids creating a second pool while keeping all DB access
            # behind the omnibase_infra effect boundary.
            pool = idempotency_store._pool
            if pool is None:
                duration = time.time() - start_time
                return ModelDomainPluginResult.failed(
                    plugin_id=self.plugin_id,
                    error_message=(
                        "Idempotency store pool is None after initialization"
                    ),
                    duration_seconds=duration,
                )

            self._pool = pool  # kept for lifecycle management (close on shutdown)
            resources_created.append("postgres_pool")
            logger.info(
                "Intelligence PostgreSQL pool created via infra (correlation_id=%s)",
                correlation_id,
                extra={
                    "db_url": _safe_db_url_display(db_url),
                },
            )

            # Create PostgresRepositoryRuntime for contract-driven DB access
            contract = load_contract()
            self._pattern_runtime = PostgresRepositoryRuntime(
                pool=pool, contract=contract
            )
            resources_created.append("pattern_runtime")

            # Register intelligence message types (OMN-2039)
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
                error_message=get_log_sanitizer().sanitize(str(e)),
                duration_seconds=duration,
            )

    async def _cleanup_on_failure(self, config: ModelDomainPluginConfig) -> None:
        """Clean up resources if initialization fails."""
        correlation_id = config.correlation_id

        self._message_type_registry = None
        self._pattern_runtime = None

        # Pool is owned by idempotency store -- just clear the reference
        self._pool = None

        if self._idempotency_store is not None:
            try:
                await self._idempotency_store.shutdown()
            except Exception as cleanup_error:
                logger.warning(
                    "Cleanup failed for idempotency store shutdown: %s (correlation_id=%s)",
                    cleanup_error,
                    correlation_id,
                )
            self._idempotency_store = None

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
                error_message=get_log_sanitizer().sanitize(str(e)),
                duration_seconds=duration,
            )

    async def wire_dispatchers(
        self,
        config: ModelDomainPluginConfig,
    ) -> ModelDomainPluginResult:
        """Wire intelligence domain dispatchers with real dependencies.

        Creates protocol adapters from infrastructure (effect boundary, event bus),
        reads publish topics from contracts, and builds a MessageDispatchEngine
        with all 5 intelligence domain handlers (7 routes) wired to real
        business logic.

        Dispatchers registered:
            1. claude-hook-event → route_hook_event() with classifier + publisher
            2. session-outcome → record_session_outcome() with DB repository
            3. pattern-lifecycle-transition → apply_transition() with DB + idempotency
            4. pattern-storage → store_pattern() for pattern-learned + pattern.discovered
            5. pattern-learning-cmd → pattern extraction + Kafka publish

        All required dependencies (repository, idempotency store, intent classifier)
        are created from the PostgreSQL pool. If the pool is not initialized,
        this method fails fast. Kafka publisher is optional (graceful degradation).

        Args:
            config: Plugin configuration.

        Returns:
            Result indicating success/failure and dispatchers registered.
        """
        from omniintelligence.repositories.adapter_pattern_store import (
            AdapterPatternStore,
        )
        from omniintelligence.runtime.adapters import (
            AdapterIdempotencyStoreInfra,
            AdapterIntentClassifier,
            AdapterKafkaPublisher,
            AdapterPatternRepositoryRuntime,
        )
        from omniintelligence.runtime.contract_topics import (
            collect_publish_topics_for_dispatch,
        )
        from omniintelligence.runtime.dispatch_handlers import (
            create_intelligence_dispatch_engine,
        )

        start_time = time.time()
        correlation_id = config.correlation_id

        if self._pool is None or self._pattern_runtime is None:
            return ModelDomainPluginResult.failed(
                plugin_id=self.plugin_id,
                error_message=(
                    "Cannot wire dispatchers: PostgreSQL pool or runtime not initialized"
                ),
            )

        try:
            # Create protocol adapters from infra effect boundary
            repository = AdapterPatternRepositoryRuntime(self._pattern_runtime)

            # Create contract-driven upsert store for pattern storage handler
            pattern_upsert_store = AdapterPatternStore(self._pattern_runtime)

            # Create idempotency adapter from infra store
            if self._idempotency_store is not None:
                idempotency_store = AdapterIdempotencyStoreInfra(
                    self._idempotency_store
                )
            else:
                # Fallback: should not happen if initialize() succeeded
                logger.warning(
                    "Idempotency store not initialized, creating in-memory fallback "
                    "(correlation_id=%s)",
                    correlation_id,
                )
                from omnibase_infra.idempotency.store_inmemory import (
                    StoreIdempotencyInmemory,
                )

                idempotency_store = AdapterIdempotencyStoreInfra(
                    StoreIdempotencyInmemory()
                )

            intent_classifier = AdapterIntentClassifier()

            # Kafka publisher: optional (graceful degradation in handlers).
            # Use isinstance against ProtocolEventBusPublish (runtime_checkable)
            # to verify the event bus exposes the correct publish signature,
            # not just any attribute named "publish".
            from omniintelligence.runtime.adapters import ProtocolEventBusPublish

            kafka_publisher = None
            if isinstance(config.event_bus, ProtocolEventBusPublish):
                kafka_publisher = AdapterKafkaPublisher(config.event_bus)

            # Read publish topics from contract.yaml declarations
            publish_topics = collect_publish_topics_for_dispatch()

            self._dispatch_engine = create_intelligence_dispatch_engine(
                repository=repository,
                idempotency_store=idempotency_store,
                intent_classifier=intent_classifier,
                kafka_producer=kafka_publisher,
                publish_topics=publish_topics,
                pattern_upsert_store=pattern_upsert_store,
            )

            # Publish introspection events for all intelligence nodes
            # (OMN-2210: Wire intelligence nodes into registration)
            #
            # Gate on OMNIINTELLIGENCE_PUBLISH_INTROSPECTION (OMN-2342):
            # Only the designated container (omninode-runtime) publishes
            # introspection. Worker/effects containers leave this var unset
            # so they process events without starting duplicate heartbeat loops
            # for the same deterministic node IDs.
            #
            # _event_bus is captured only when publishing is enabled so that
            # the shutdown path (which gates on _event_bus is not None) does
            # not emit spurious shutdown events from worker containers.
            from omniintelligence.runtime.introspection import (
                publish_intelligence_introspection,
            )

            if _introspection_publishing_enabled():
                # Capture event_bus for shutdown path only when this container
                # is the designated introspection publisher.
                self._event_bus = config.event_bus
                introspection_result = await publish_intelligence_introspection(
                    event_bus=config.event_bus,
                    correlation_id=correlation_id,
                )
                self._introspection_nodes = introspection_result.registered_nodes
                self._introspection_proxies = introspection_result.proxies
            else:
                logger.info(
                    "Intelligence introspection publishing skipped: "
                    "%s is not set to a truthy value "
                    "(correlation_id=%s)",
                    _PUBLISH_INTROSPECTION_ENV_VAR,
                    correlation_id,
                )
                self._introspection_nodes = []
                self._introspection_proxies = []

            duration = time.time() - start_time
            logger.info(
                "Intelligence dispatch engine wired "
                "(routes=%d, handlers=%d, kafka=%s, introspection=%d, "
                "correlation_id=%s)",
                self._dispatch_engine.route_count,
                self._dispatch_engine.handler_count,
                kafka_publisher is not None,
                len(self._introspection_nodes),
                correlation_id,
                extra={"publish_topics": publish_topics},
            )

            resources_created = [
                "dispatch_engine",
                "repository_adapter",
                "idempotency_store",
                "intent_classifier",
            ]
            if self._introspection_nodes:
                resources_created.append("node_introspection")

            return ModelDomainPluginResult(
                plugin_id=self.plugin_id,
                success=True,
                message="Intelligence dispatch engine wired",
                resources_created=resources_created,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(
                "Failed to wire intelligence dispatch engine (correlation_id=%s)",
                correlation_id,
            )
            # Clean up partially-captured state to avoid stale references.
            # If the failure occurred after capturing event_bus or after
            # introspection publishing, these references would dangle and
            # could cause shutdown to operate on stale/inconsistent state.
            #
            # Stop heartbeat tasks on any introspection proxies that were
            # started before the failure, then reset the single-call guard
            # so a retry is not permanently blocked (follows the same
            # pattern as _do_shutdown).
            for proxy in self._introspection_proxies:
                try:
                    await proxy.stop_introspection_tasks()
                except Exception as stop_error:
                    sanitized = get_log_sanitizer().sanitize(str(stop_error))
                    logger.debug(
                        "Error stopping introspection tasks for %s during "
                        "wire_dispatchers cleanup: %s (correlation_id=%s)",
                        proxy.name,
                        sanitized,
                        correlation_id,
                    )

            from omniintelligence.runtime.introspection import (
                reset_introspection_guard,
            )

            reset_introspection_guard()

            self._event_bus = None
            self._introspection_nodes = []
            self._introspection_proxies = []
            self._dispatch_engine = None
            return ModelDomainPluginResult.failed(
                plugin_id=self.plugin_id,
                error_message=get_log_sanitizer().sanitize(str(e)),
                duration_seconds=duration,
            )

    async def start_consumers(
        self,
        config: ModelDomainPluginConfig,
    ) -> ModelDomainPluginResult:
        """Start intelligence event consumers.

        Subscribes to intelligence input topics via MessageDispatchEngine.
        All topics are routed through the dispatch engine — there is no
        noop fallback. If the dispatch engine is not wired, consumers
        are not started (returns skipped).

        Args:
            config: Plugin configuration with event_bus.

        Returns:
            Result with unsubscribe_callbacks for cleanup.
        """
        start_time = time.time()
        correlation_id = config.correlation_id

        # Strict gating: no dispatch engine = no consumers
        if self._dispatch_engine is None:
            return ModelDomainPluginResult.skipped(
                plugin_id=self.plugin_id,
                reason="Dispatch engine not wired; consumers not started",
            )

        # Duck typing: check for subscribe capability
        if not hasattr(config.event_bus, "subscribe"):
            return ModelDomainPluginResult.skipped(
                plugin_id=self.plugin_id,
                reason="Event bus does not support subscribe",
            )

        try:
            # Build per-topic handler map (dispatch engine guaranteed non-None)
            topic_handlers = self._build_topic_handlers(correlation_id)

            unsubscribe_callbacks: list[Callable[[], Awaitable[None]]] = []

            for topic in INTELLIGENCE_SUBSCRIBE_TOPICS:
                if topic not in topic_handlers:
                    logger.warning(
                        "Topic %s declared in contract but has no registered "
                        "dispatch route, skipping (correlation_id=%s)",
                        topic,
                        correlation_id,
                    )
                    continue
                handler = topic_handlers[topic]
                logger.info(
                    "Subscribing to intelligence topic: %s "
                    "(mode=dispatch_engine, correlation_id=%s)",
                    topic,
                    correlation_id,
                )
                unsub = await config.event_bus.subscribe(
                    topic=topic,
                    group_id=f"{config.consumer_group}-intelligence",
                    on_message=handler,
                )
                unsubscribe_callbacks.append(unsub)

            self._unsubscribe_callbacks = unsubscribe_callbacks

            duration = time.time() - start_time
            logger.info(
                "Intelligence consumers started: %d topics "
                "(all dispatched, correlation_id=%s)",
                len(INTELLIGENCE_SUBSCRIBE_TOPICS),
                correlation_id,
            )

            return ModelDomainPluginResult(
                plugin_id=self.plugin_id,
                success=True,
                message=(
                    f"Intelligence consumers started "
                    f"({len(INTELLIGENCE_SUBSCRIBE_TOPICS)} dispatched)"
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
                error_message=get_log_sanitizer().sanitize(str(e)),
                duration_seconds=duration,
            )

    def _build_topic_handlers(
        self,
        correlation_id: object,
    ) -> dict[str, Callable[[object], Awaitable[None]]]:
        """Build handler map for each intelligence topic.

        Returns a dict mapping topic -> async callback. All intelligence
        topics are routed through the dispatch engine. This method must
        only be called when ``self._dispatch_engine`` is not None
        (enforced by ``start_consumers()``).

        Topic -> dispatch alias conversion is handled generically by
        ``canonical_topic_to_dispatch_alias`` (OMN-2033).

        Args:
            correlation_id: Correlation ID for tracing.

        Returns:
            Dict mapping each INTELLIGENCE_SUBSCRIBE_TOPICS entry to a handler.

        Raises:
            RuntimeError: If dispatch engine is not wired (invariant violation).
        """
        if self._dispatch_engine is None:
            raise RuntimeError(
                "_build_topic_handlers called without dispatch engine "
                f"(correlation_id={correlation_id})"
            )

        from omniintelligence.runtime.dispatch_handlers import (
            create_dispatch_callback,
        )

        handlers: dict[str, Callable[[object], Awaitable[None]]] = {}

        for topic in INTELLIGENCE_SUBSCRIBE_TOPICS:
            dispatch_alias = canonical_topic_to_dispatch_alias(topic)
            handlers[topic] = create_dispatch_callback(
                engine=self._dispatch_engine,
                dispatch_topic=dispatch_alias,
            )

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
        except Exception:
            # Reset on failure so shutdown can be retried
            self._shutdown_in_progress = False
            raise

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

        # Publish shutdown introspection for all intelligence nodes.
        # Gate on _event_bus (set in wire_dispatchers only when introspection
        # publishing is enabled), NOT on _introspection_nodes. If all individual
        # publish calls failed, _introspection_nodes is empty but the
        # single-call guard (_introspection_published) is still set.
        # publish_intelligence_shutdown resets that guard, so we must call
        # it whenever introspection was attempted, even if no nodes
        # registered successfully.
        if self._event_bus is not None:
            try:
                from omniintelligence.runtime.introspection import (
                    publish_intelligence_shutdown,
                )

                await publish_intelligence_shutdown(
                    event_bus=self._event_bus,
                    proxies=self._introspection_proxies,
                    correlation_id=correlation_id,
                )
            except Exception as shutdown_intro_error:
                sanitized = get_log_sanitizer().sanitize(str(shutdown_intro_error))
                errors.append(f"introspection_shutdown: {sanitized}")
                logger.warning(
                    "Failed to publish shutdown introspection: %s (correlation_id=%s)",
                    sanitized,
                    correlation_id,
                )
        else:
            logger.debug(
                "Introspection shutdown skipped: wire_dispatchers was never "
                "called or did not capture event_bus "
                "(correlation_id=%s)",
                correlation_id,
            )

        # Unsubscribe from topics
        for unsub in self._unsubscribe_callbacks:
            try:
                await unsub()
            except Exception as unsub_error:
                sanitized_unsub = get_log_sanitizer().sanitize(str(unsub_error))
                errors.append(f"unsubscribe: {sanitized_unsub}")
                logger.warning(
                    "Failed to unsubscribe intelligence consumer: %s "
                    "(correlation_id=%s)",
                    sanitized_unsub,
                    correlation_id,
                )
        self._unsubscribe_callbacks = []

        # Clear runtime reference (must happen before pool shutdown)
        self._pattern_runtime = None

        # Shutdown idempotency store (owns the shared pool, closes it on shutdown)
        if self._idempotency_store is not None:
            try:
                await self._idempotency_store.shutdown()
                logger.debug(
                    "Intelligence idempotency store shut down (correlation_id=%s)",
                    correlation_id,
                )
            except Exception as idemp_error:
                sanitized_idemp = get_log_sanitizer().sanitize(str(idemp_error))
                errors.append(f"idempotency_shutdown: {sanitized_idemp}")
                logger.warning(
                    "Failed to shut down idempotency store: %s (correlation_id=%s)",
                    sanitized_idemp,
                    correlation_id,
                )
            self._idempotency_store = None

        # Pool is owned by the idempotency store -- just clear the reference
        self._pool = None

        self._services_registered = []
        self._dispatch_engine = None
        self._message_type_registry = None
        self._event_bus = None
        self._introspection_nodes = []
        self._introspection_proxies = []

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
        db_url = os.getenv("OMNIINTELLIGENCE_DB_URL", "")
        host_part = _safe_db_url_display(db_url)
        return f"enabled ({host_part})"


# Verify protocol compliance at module load time
_: ProtocolDomainPlugin = PluginIntelligence()

__all__: list[str] = [
    "INTELLIGENCE_SUBSCRIBE_TOPICS",
    "PluginIntelligence",
]
