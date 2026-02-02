# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Registry for Pattern Lifecycle Effect Node Dependencies.

This module provides RegistryPatternLifecycleEffect, which creates a registry
of handlers for the NodePatternLifecycleEffect node.

Architecture:
    The registry follows ONEX container-based dependency injection:
    - Creates handlers with explicit dependencies (no setters)
    - Uses static factory pattern for registry creation
    - Validates dependencies at registry creation time (fail-fast)
    - Returns a frozen registry that cannot be modified

Kafka Optionality:
    The node contract marks ``kafka_producer`` as ``required: false``, meaning
    the node can operate without Kafka. The registry factory accepts None for
    the producer parameter.

    **When Kafka is unavailable**, transitions still succeed in the database,
    but ``PatternLifecycleTransitioned`` events are NOT emitted.

Usage:
    >>> from omniintelligence.nodes.node_pattern_lifecycle_effect.registry import (
    ...     RegistryPatternLifecycleEffect,
    ... )
    >>>
    >>> # Create registry with dependencies
    >>> registry = RegistryPatternLifecycleEffect.create_registry(
    ...     repository=db_connection,
    ...     idempotency_store=idempotency_store,
    ...     producer=kafka_producer,  # Optional, can be None
    ... )
    >>>
    >>> # Get handler from registry
    >>> handler = registry.apply_transition
    >>> result = await handler(intent)

Testing:
    This module uses module-level state for handler storage. Tests MUST call
    ``RegistryPatternLifecycleEffect.clear()`` in setup and teardown fixtures
    to prevent test pollution between test cases.

    Recommended fixture pattern:

    .. code-block:: python

        @pytest.fixture(autouse=True)
        def clear_registry():
            RegistryPatternLifecycleEffect.clear()
            yield
            RegistryPatternLifecycleEffect.clear()

Ticket: OMN-1805
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from omniintelligence.nodes.intelligence_reducer.models import (
        ModelPayloadUpdatePatternStatus,
    )
    from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
        ProtocolIdempotencyStore,
        ProtocolKafkaPublisher,
        ProtocolPatternRepository,
    )
    from omniintelligence.nodes.node_pattern_lifecycle_effect.models import (
        ModelTransitionResult,
    )

logger = logging.getLogger(__name__)

__all__ = ["RegistryPatternLifecycleEffect", "ServiceHandlerRegistry"]


# Type alias for handler function signature
HandlerFunction = Callable[
    ["ModelPayloadUpdatePatternStatus"],
    Coroutine[Any, Any, "ModelTransitionResult"],
]


@dataclass(frozen=True)
class ServiceHandlerRegistry:
    """Frozen registry of handler functions for pattern lifecycle transitions.

    This class holds the wired handler functions with their dependencies
    already bound. Once created, it cannot be modified (frozen dataclass).

    Attributes:
        apply_transition: Handler function for applying pattern status transitions.
            Dependencies (repository, idempotency_store, producer) are already bound.
        topic_env_prefix: Environment prefix for Kafka topics.
    """

    apply_transition: HandlerFunction
    topic_env_prefix: str = "dev"

    _handlers: dict[str, HandlerFunction] = field(
        default_factory=dict, repr=False, compare=False, hash=False
    )

    def __post_init__(self) -> None:
        """Initialize the handlers dict after creation."""
        # Use object.__setattr__ because dataclass is frozen
        handlers = {"apply_transition": self.apply_transition}
        object.__setattr__(self, "_handlers", handlers)

    def get_handler(self, operation: str) -> HandlerFunction | None:
        """Get a handler function by operation name.

        Args:
            operation: The operation name (e.g., "apply_transition").

        Returns:
            The handler function if found, None otherwise.
        """
        return self._handlers.get(operation)


# Module-level storage for registry (similar to omnibase_infra pattern)
_REGISTRY_STORAGE: dict[str, ServiceHandlerRegistry] = {}


class RegistryPatternLifecycleEffect:
    """Registry for pattern lifecycle effect node dependencies.

    Provides a static factory method to create a ServiceHandlerRegistry
    with all dependencies wired. The registry is immutable once created.

    This follows the ONEX declarative pattern:
    - Dependencies are validated at registry creation time (fail-fast)
    - No setter methods - dependencies are injected via factory
    - Registry is frozen after creation

    Example:
        >>> registry = RegistryPatternLifecycleEffect.create_registry(
        ...     repository=db_connection,
        ...     idempotency_store=idempotency_store,
        ...     producer=kafka_producer,
        ...     topic_env_prefix="prod",
        ... )
        >>> handler = registry.apply_transition
        >>> result = await handler(intent)
    """

    # Registry key for storage
    REGISTRY_KEY = "pattern_lifecycle"

    @staticmethod
    def create_registry(
        repository: ProtocolPatternRepository,
        idempotency_store: ProtocolIdempotencyStore,
        producer: ProtocolKafkaPublisher | None = None,
        *,
        topic_env_prefix: str = "dev",
    ) -> ServiceHandlerRegistry:
        """Create a frozen registry with all handlers wired.

        This factory method:
        1. Validates that repository and idempotency_store are not None
        2. Creates handler functions with dependencies bound
        3. Returns a frozen ServiceHandlerRegistry

        Args:
            repository: Pattern repository implementing ProtocolPatternRepository.
                Required for database operations (fetch, fetchrow, execute).
            idempotency_store: Idempotency store implementing ProtocolIdempotencyStore.
                Required for request_id deduplication.
            producer: Kafka producer implementing ProtocolKafkaPublisher, or None.
                Optional - when None, transitions succeed but Kafka events are
                not emitted.
            topic_env_prefix: Environment prefix for Kafka topics.
                Defaults to "dev". Must be non-empty alphanumeric with - or _.

        Returns:
            A frozen ServiceHandlerRegistry with handlers wired.

        Raises:
            ValueError: If repository or idempotency_store is None.
            ValueError: If topic_env_prefix is invalid.
        """
        # Import here to avoid circular imports
        from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
            apply_transition,
        )

        # Validate dependencies (fail-fast)
        if repository is None:
            raise ValueError(
                "repository is required for RegistryPatternLifecycleEffect. "
                "Provide a ProtocolPatternRepository implementation."
            )

        if idempotency_store is None:
            raise ValueError(
                "idempotency_store is required for RegistryPatternLifecycleEffect. "
                "Provide a ProtocolIdempotencyStore implementation."
            )

        # Validate topic_env_prefix
        if not topic_env_prefix:
            raise ValueError("topic_env_prefix cannot be empty")
        if not all(c.isalnum() or c in "-_" for c in topic_env_prefix):
            raise ValueError(
                f"topic_env_prefix '{topic_env_prefix}' contains invalid characters. "
                "Only alphanumeric characters, hyphens, and underscores are allowed."
            )

        # Create handler with bound dependencies
        async def bound_apply_transition(
            intent: ModelPayloadUpdatePatternStatus,
        ) -> ModelTransitionResult:
            """Handler with repository, idempotency_store, and producer bound."""
            return await apply_transition(
                repository=repository,
                idempotency_store=idempotency_store,
                producer=producer,
                request_id=intent.request_id,
                correlation_id=intent.correlation_id,
                pattern_id=intent.pattern_id,
                from_status=intent.from_status,
                to_status=intent.to_status,
                trigger=intent.trigger,
                actor=intent.actor,
                reason=intent.reason,
                gate_snapshot=intent.gate_snapshot,
                transition_at=intent.transition_at,
                topic_env_prefix=topic_env_prefix,
            )

        # Create frozen registry
        registry = ServiceHandlerRegistry(
            apply_transition=bound_apply_transition,
            topic_env_prefix=topic_env_prefix,
        )

        # Store in module-level storage
        _REGISTRY_STORAGE[RegistryPatternLifecycleEffect.REGISTRY_KEY] = registry

        return registry

    @staticmethod
    def get_registry() -> ServiceHandlerRegistry | None:
        """Retrieve the current registry from module-level storage.

        Returns:
            The stored ServiceHandlerRegistry, or None if not created.
        """
        return _REGISTRY_STORAGE.get(RegistryPatternLifecycleEffect.REGISTRY_KEY)

    @staticmethod
    def clear() -> None:
        """Clear all stored registries.

        This method MUST be called in test setup and teardown to prevent
        test pollution. Module-level state persists across test cases.

        Example:
            .. code-block:: python

                @pytest.fixture(autouse=True)
                def clear_registry():
                    RegistryPatternLifecycleEffect.clear()
                    yield
                    RegistryPatternLifecycleEffect.clear()
        """
        _REGISTRY_STORAGE.clear()
