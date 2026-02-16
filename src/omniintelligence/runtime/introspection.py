# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Intelligence node introspection registration.

Publishes introspection events for all intelligence nodes during plugin
initialization, enabling them to be discovered by the registration
orchestrator in omnibase_infra.

This module bridges the gap between intelligence nodes (which run inside
the plugin lifecycle, not as standalone processes) and the platform
registration system (which discovers nodes via introspection events on
``onex.evt.platform.node-introspection.v1``).

Design Decisions:
    - Introspection is published per-node, not per-plugin. Each intelligence
      node gets its own introspection event with its own node_id.
    - The plugin owns the event bus reference and passes it to this module.
    - Heartbeat is enabled for effect nodes only (they have long-running
      consumers). Compute nodes are stateless and do not need heartbeats.
    - Node IDs are deterministic UUIDs derived from the node name using
      uuid5(NAMESPACE_DNS, node_name) for stable registration across restarts.

Related:
    - OMN-2210: Wire intelligence nodes into registration + pattern extraction
    - PR #316: MixinNodeIntrospection with heartbeat and capability discovery
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import NAMESPACE_DNS, UUID, uuid5

from omnibase_core.enums import EnumNodeKind
from omnibase_infra.enums import EnumIntrospectionReason
from omnibase_infra.mixins.mixin_node_introspection import MixinNodeIntrospection
from omnibase_infra.models.discovery import ModelIntrospectionConfig

from omniintelligence.utils.log_sanitizer import get_log_sanitizer

if TYPE_CHECKING:
    from omnibase_core.protocols.event_bus.protocol_event_bus import ProtocolEventBus

logger = logging.getLogger(__name__)

# Guard for single-call invariant on publish_intelligence_introspection.
# See the function docstring for rationale: calling it more than once orphans
# heartbeat tasks from the first call, leaking asyncio tasks.
# Thread-safety: the lock protects the check-and-set of _introspection_published
# to prevent races when multiple plugins or test runners share the same module.
_introspection_lock = threading.Lock()
_introspection_published: bool = False

# Standard DNS namespace for deterministic UUID5 generation.
# Node name prefixed with "omniintelligence." ensures uniqueness across domains.
_NAMESPACE_INTELLIGENCE = NAMESPACE_DNS


# =============================================================================
# Intelligence Node Descriptors
# =============================================================================
# Each entry describes a node that should publish introspection events.
# Fields: (node_name, node_type, version)


class _NodeDescriptor:
    """Describes an intelligence node for introspection registration."""

    __slots__ = ("name", "node_type", "version")

    def __init__(
        self,
        name: str,
        node_type: EnumNodeKind,
        version: str = "1.0.0",
    ) -> None:
        self.name = name
        self.node_type = node_type
        self.version = version

    @property
    def node_id(self) -> UUID:
        """Deterministic node ID derived from node name."""
        return uuid5(_NAMESPACE_INTELLIGENCE, f"omniintelligence.{self.name}")


INTELLIGENCE_NODES: tuple[_NodeDescriptor, ...] = (
    # Orchestrators
    _NodeDescriptor("node_intelligence_orchestrator", EnumNodeKind.ORCHESTRATOR),
    _NodeDescriptor("node_pattern_assembler_orchestrator", EnumNodeKind.ORCHESTRATOR),
    # Reducer
    _NodeDescriptor("node_intelligence_reducer", EnumNodeKind.REDUCER),
    # Compute nodes
    _NodeDescriptor("node_quality_scoring_compute", EnumNodeKind.COMPUTE),
    _NodeDescriptor("node_semantic_analysis_compute", EnumNodeKind.COMPUTE),
    _NodeDescriptor("node_pattern_extraction_compute", EnumNodeKind.COMPUTE),
    _NodeDescriptor("node_pattern_learning_compute", EnumNodeKind.COMPUTE),
    _NodeDescriptor("node_pattern_matching_compute", EnumNodeKind.COMPUTE),
    _NodeDescriptor("node_intent_classifier_compute", EnumNodeKind.COMPUTE),
    _NodeDescriptor("node_execution_trace_parser_compute", EnumNodeKind.COMPUTE),
    _NodeDescriptor("node_success_criteria_matcher_compute", EnumNodeKind.COMPUTE),
    # Effect nodes
    _NodeDescriptor("node_claude_hook_event_effect", EnumNodeKind.EFFECT),
    _NodeDescriptor("node_pattern_storage_effect", EnumNodeKind.EFFECT),
    _NodeDescriptor("node_pattern_promotion_effect", EnumNodeKind.EFFECT),
    _NodeDescriptor("node_pattern_demotion_effect", EnumNodeKind.EFFECT),
    _NodeDescriptor("node_pattern_feedback_effect", EnumNodeKind.EFFECT),
    _NodeDescriptor("node_pattern_lifecycle_effect", EnumNodeKind.EFFECT),
)


# =============================================================================
# Introspection Publisher
# =============================================================================


class IntelligenceNodeIntrospectionProxy(MixinNodeIntrospection):  # type: ignore[misc]  # omnibase_infra does not export py.typed
    """Proxy that uses MixinNodeIntrospection to publish on behalf of a node.

    Intelligence nodes are thin shells that run inside the plugin lifecycle.
    They do not own event bus references or background tasks. This proxy
    creates a lightweight MixinNodeIntrospection instance for each node
    to publish startup introspection and optionally run heartbeats.

    The proxy is intentionally minimal: it only provides the introspection
    mixin surface. It does not implement any node business logic.

    Note on mixin usage: This is an intentional proxy pattern, not a proper
    mixin usage. The proxy deliberately provides only the subset of the node
    interface that the mixin requires (the ``initialize_introspection`` call
    and the ``name`` property). The ``# type: ignore[misc]`` suppresses the
    mypy error from inheriting a mixin without a full node base class.
    """

    def __init__(
        self,
        descriptor: _NodeDescriptor,
        event_bus: ProtocolEventBus | None,
    ) -> None:
        config = ModelIntrospectionConfig(
            node_id=descriptor.node_id,
            node_type=descriptor.node_type,
            node_name=descriptor.name,
            event_bus=event_bus,
            version=descriptor.version,
        )
        self.initialize_introspection(config)
        self._descriptor = descriptor

    @property
    def name(self) -> str:
        """Return the node name from the descriptor."""
        return self._descriptor.name


@dataclass
class IntrospectionResult:
    """Result of intelligence introspection publishing.

    Holds both the list of registered node names and the proxy references
    needed to stop heartbeat tasks during shutdown.

    Design constraint on ``proxies``:
        The ``proxies`` list contains **only effect node proxies** that have
        running heartbeat background tasks (started via
        ``start_introspection_tasks``). Compute, orchestrator, and reducer
        nodes publish a one-shot STARTUP introspection event but do not start
        heartbeat tasks, so their proxies are not retained here.

        During shutdown (``publish_intelligence_shutdown``), fresh proxy
        instances are created for ALL nodes to publish SHUTDOWN events.
        Identity correlation between STARTUP and SHUTDOWN events is maintained
        through deterministic ``node_id`` values (UUID5 derived from the node
        name via ``_NodeDescriptor.node_id``), not through object identity.
        The registration orchestrator matches events by ``node_id``, so the
        distinct proxy instances produce correct correlation.

    Attributes:
        registered_nodes: Names of nodes that successfully published
            STARTUP introspection events.
        proxies: Effect node proxies with active heartbeat tasks. These
            must be passed to ``publish_intelligence_shutdown`` so their
            background tasks are stopped before the process exits.
    """

    registered_nodes: list[str] = field(default_factory=list)
    proxies: list[IntelligenceNodeIntrospectionProxy] = field(default_factory=list)


async def publish_intelligence_introspection(
    event_bus: ProtocolEventBus | None,
    *,
    correlation_id: UUID | None = None,
    enable_heartbeat: bool = True,
    heartbeat_interval_seconds: float = 30.0,
) -> IntrospectionResult:
    """Publish introspection events for all intelligence nodes.

    Creates a proxy MixinNodeIntrospection instance for each intelligence
    node and publishes a STARTUP introspection event. For effect nodes,
    optionally starts heartbeat tasks.

    **Single-call invariant**: This function MUST only be called once per
    process lifecycle with a real event bus. Each call creates new proxy
    instances and starts new heartbeat background tasks for effect nodes.
    Calling it more than once would orphan the previous proxies and their
    running heartbeat tasks, leading to leaked asyncio tasks and duplicate
    introspection events. The caller is responsible for retaining the
    returned ``IntrospectionResult`` and passing its ``proxies`` to
    ``publish_intelligence_shutdown()`` during teardown.

    If ``event_bus`` is None, the function is a no-op and does not set the
    single-call guard, allowing a subsequent call with a real event bus to
    succeed. This is intentional: a no-op call creates no proxies or
    heartbeat tasks, so there is nothing to orphan.

    Args:
        event_bus: Event bus implementing ProtocolEventBus for publishing
            introspection events. If None, introspection is skipped.
        correlation_id: Optional correlation ID for tracing.
        enable_heartbeat: Whether to start heartbeat tasks for effect nodes.
        heartbeat_interval_seconds: Interval between heartbeats in seconds.

    Returns:
        IntrospectionResult with registered node names and proxy references
        for lifecycle management.
    """
    global _introspection_published
    with _introspection_lock:
        if _introspection_published:
            raise RuntimeError(
                "publish_intelligence_introspection() has already been called "
                "with a real event bus. Calling it again would orphan heartbeat "
                "tasks from the first invocation. This violates the single-call "
                "invariant documented in the function docstring. "
                "(Note: calls with event_bus=None are exempt from this guard "
                "because they are no-ops that create no proxies or tasks.)"
            )
        # Set guard BEFORE releasing the lock so that concurrent asyncio tasks
        # (which share the same thread) or other threads see the guard
        # immediately, not after the await-heavy registration loop below.
        # The guard is set optimistically: if the loop fails, the guard
        # remains set, which is correct (the function must not be retried).
        if event_bus is not None:
            _introspection_published = True

    if event_bus is None:
        # No-op path: intentionally does NOT set _introspection_published.
        # A no-op call creates no proxies or heartbeat tasks, so there is
        # nothing to orphan. A later call with a real event bus must still
        # be allowed to proceed.
        logger.info(
            "Skipping intelligence introspection: no event bus available "
            "(correlation_id=%s)",
            correlation_id,
        )
        return IntrospectionResult()

    result = IntrospectionResult()

    for descriptor in INTELLIGENCE_NODES:
        try:
            proxy = IntelligenceNodeIntrospectionProxy(
                descriptor=descriptor,
                event_bus=event_bus,
            )

            success = await proxy.publish_introspection(
                reason=EnumIntrospectionReason.STARTUP,
                correlation_id=correlation_id,
            )

            if success:
                result.registered_nodes.append(descriptor.name)
                logger.debug(
                    "Published introspection for %s (node_id=%s, type=%s, "
                    "correlation_id=%s)",
                    descriptor.name,
                    descriptor.node_id,
                    descriptor.node_type,
                    correlation_id,
                )

                # Start heartbeat for effect nodes only
                if enable_heartbeat and descriptor.node_type == EnumNodeKind.EFFECT:
                    await proxy.start_introspection_tasks(
                        enable_heartbeat=True,
                        heartbeat_interval_seconds=heartbeat_interval_seconds,
                        enable_registry_listener=False,
                    )
                    result.proxies.append(proxy)
            else:
                logger.warning(
                    "Failed to publish introspection for %s (correlation_id=%s)",
                    descriptor.name,
                    correlation_id,
                )

        except Exception as e:
            logger.warning(
                "Error publishing introspection for %s: %s (correlation_id=%s)",
                descriptor.name,
                get_log_sanitizer().sanitize(str(e)),
                correlation_id,
            )

    logger.info(
        "Intelligence introspection published: %d/%d nodes (correlation_id=%s)",
        len(result.registered_nodes),
        len(INTELLIGENCE_NODES),
        correlation_id,
    )

    return result


async def publish_intelligence_shutdown(
    event_bus: ProtocolEventBus | None,
    *,
    proxies: list[IntelligenceNodeIntrospectionProxy] | None = None,
    correlation_id: UUID | None = None,
) -> None:
    """Publish shutdown introspection events for all intelligence nodes.

    Called during plugin shutdown to notify the registration orchestrator
    that intelligence nodes are going offline. Also stops any running
    heartbeat tasks on the provided proxies.

    Shutdown is best-effort: heartbeat tasks are stopped unconditionally
    (so nodes stop advertising liveness), but if ``event_bus`` is None
    the SHUTDOWN introspection events are skipped. This means nodes will
    appear offline from the heartbeat perspective while the registration
    orchestrator never receives an explicit SHUTDOWN event. The
    orchestrator handles this via heartbeat TTL expiry.

    Args:
        event_bus: Event bus for publishing shutdown events. If None,
            heartbeat tasks are still stopped but SHUTDOWN events are
            not published.
        proxies: Proxy instances from startup that may have running
            heartbeat tasks. If provided, their tasks are stopped
            before publishing shutdown events.
        correlation_id: Optional correlation ID for tracing.
    """
    # Stop heartbeat tasks on proxies that were started at init time
    if proxies:
        for proxy in proxies:
            try:
                await proxy.stop_introspection_tasks()
            except Exception as e:
                logger.debug(
                    "Error stopping introspection tasks for %s: %s",
                    proxy.name,
                    get_log_sanitizer().sanitize(str(e)),
                )

    if event_bus is None:
        reset_introspection_guard()
        return

    # New proxies are created here because startup only retains proxies for
    # effect nodes (those with heartbeat tasks) in IntrospectionResult.proxies.
    # Non-effect nodes (compute, orchestrator, reducer) have no background tasks,
    # so their startup proxies are not stored. Creating lightweight proxies here
    # is simpler than refactoring startup to retain all proxies.
    #
    # Identity correlation: node_id (deterministic UUID5 from descriptor.name)
    # is the sole identity key used by the registration orchestrator to
    # correlate STARTUP and SHUTDOWN events for the same logical node. The
    # shutdown proxies created below are distinct object instances from the
    # startup proxies, but they produce the same node_id per descriptor,
    # ensuring the registration orchestrator correctly matches them.
    for descriptor in INTELLIGENCE_NODES:
        try:
            proxy = IntelligenceNodeIntrospectionProxy(
                descriptor=descriptor,
                event_bus=event_bus,
            )
            await proxy.publish_introspection(
                reason=EnumIntrospectionReason.SHUTDOWN,
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.debug(
                "Error publishing shutdown introspection for %s: %s",
                descriptor.name,
                get_log_sanitizer().sanitize(str(e)),
            )

    # Reset the single-call guard so the plugin can be re-initialized in the
    # same process (tests, hot-reload).  This MUST happen after all shutdown
    # events have been published so the guard remains set while shutdown is
    # in progress, preventing a concurrent re-init from racing with shutdown.
    reset_introspection_guard()


def reset_introspection_guard() -> None:
    """Reset the single-call guard for publish_intelligence_introspection.

    Called during shutdown to allow re-initialization, and in tests for
    isolation between test cases that invoke
    ``publish_intelligence_introspection``.

    **Not thread-safe by design**: This function is intended for sequential
    call sites (shutdown path, test teardown). It does not acquire
    ``_introspection_lock`` because the caller is responsible for ensuring
    no concurrent ``publish_intelligence_introspection`` calls are in flight.
    Using it concurrently with publish is a programming error.
    """
    global _introspection_published
    _introspection_published = False


__all__ = [
    "INTELLIGENCE_NODES",
    "IntelligenceNodeIntrospectionProxy",
    "IntrospectionResult",
    "publish_intelligence_introspection",
    "publish_intelligence_shutdown",
    "reset_introspection_guard",
]
