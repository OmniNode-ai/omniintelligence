# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Registry for Pattern Demotion Node Dependencies.

This module provides RegistryPatternDemotionEffect, which creates a registry
of handlers for the NodePatternDemotionEffect node.

Architecture:
    The registry follows ONEX container-based dependency injection:
    - Creates handlers with explicit dependencies (no setters)
    - Uses static factory pattern for registry creation
    - Validates dependencies at registry creation time (fail-fast)
    - Returns a frozen registry that cannot be modified

Kafka Optionality:
    The node contract marks ``kafka_producer`` as ``required: false``, meaning
    the node can operate without Kafka. However, the registry factory method
    requires a producer to ensure registry-based usage always has Kafka
    capability.

    **When Kafka is unavailable**, use the handler functions directly instead
    of the registry:

    .. code-block:: python

        from omniintelligence.nodes.node_pattern_demotion_effect.handlers import (
            check_and_demote_patterns,
        )

        # Direct handler call - producer=None is explicitly allowed
        result = await check_and_demote_patterns(
            repository=db_connection,
            producer=None,  # Demotions succeed, Kafka events skipped
            request=request,
            topic_env_prefix="dev",  # Required: environment prefix for Kafka topics
        )

    **Implications of running without Kafka:**
    - Database demotions succeed normally
    - No ``PatternDeprecated`` events are emitted to Kafka
    - Downstream caches relying on Kafka for invalidation become stale
    - See ``handler_demotion.py`` module docstring for reconciliation strategy

Usage:
    >>> from omniintelligence.nodes.node_pattern_demotion_effect.registry import (
    ...     RegistryPatternDemotionEffect,
    ... )
    >>>
    >>> # Create registry with dependencies (requires Kafka producer)
    >>> registry = RegistryPatternDemotionEffect.create_registry(
    ...     repository=db_connection,
    ...     producer=kafka_producer,
    ... )
    >>>
    >>> # Get handler from registry
    >>> handler = registry.get_handler("check_and_demote_patterns")
    >>> result = await handler(request)

Testing:
    This module uses module-level state for handler storage. Tests MUST call
    ``RegistryPatternDemotionEffect.clear()`` in setup and teardown fixtures
    to prevent test pollution between test cases.

    Recommended fixture pattern:

    .. code-block:: python

        @pytest.fixture(autouse=True)
        def clear_registry():
            RegistryPatternDemotionEffect.clear()
            yield
            RegistryPatternDemotionEffect.clear()

    **For testing without Kafka**, call handlers directly with ``producer=None``
    rather than using the registry.

Related:
    - NodePatternDemotionEffect: Effect node that uses these dependencies
    - handler_demotion: Handler functions for pattern demotion
    - ProtocolPatternRepository: Repository protocol for database operations
    - ProtocolKafkaPublisher: Publisher protocol for Kafka events
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any  # any-ok: Coroutine[Any, Any, T] is standard async type alias

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_demotion_effect.handlers.handler_demotion import (
        ProtocolKafkaPublisher,
        ProtocolPatternRepository,
    )
    from omniintelligence.nodes.node_pattern_demotion_effect.models import (
        ModelDemotionCheckRequest,
        ModelDemotionCheckResult,
    )

logger = logging.getLogger(__name__)

__all__ = ["RegistryPatternDemotionEffect", "RegistryDemotionHandlers"]


# Type alias for handler function signature
HandlerFunction = Callable[
    ["ModelDemotionCheckRequest"],
    Coroutine[Any, Any, "ModelDemotionCheckResult"],
]


@dataclass(frozen=True)
class RegistryDemotionHandlers:
    """Frozen registry of handler functions for pattern demotion.

    This class holds the wired handler functions with their dependencies
    already bound. Once created, it cannot be modified (frozen dataclass).

    Attributes:
        check_and_demote: Handler function for checking and demoting patterns.
            Dependencies (repository, producer) are already bound.
        topic_env_prefix: Environment prefix for Kafka topics.
    """

    check_and_demote: HandlerFunction
    topic_env_prefix: str = "dev"

    _handlers: dict[str, HandlerFunction] = field(
        default_factory=dict, repr=False, compare=False, hash=False
    )

    def __post_init__(self) -> None:
        """Initialize the handlers dict after creation."""
        # Use object.__setattr__ because dataclass is frozen
        handlers = {"check_and_demote_patterns": self.check_and_demote}
        object.__setattr__(self, "_handlers", handlers)

    def get_handler(self, operation: str) -> HandlerFunction | None:
        """Get a handler function by operation name.

        Args:
            operation: The operation name (e.g., "check_and_demote_patterns").

        Returns:
            The handler function if found, None otherwise.
        """
        return self._handlers.get(operation)


# Module-level storage for registry (similar to omnibase_infra pattern)
_REGISTRY_STORAGE: dict[str, RegistryDemotionHandlers] = {}


class RegistryPatternDemotionEffect:
    """Registry for pattern demotion node dependencies.

    Provides a static factory method to create a RegistryDemotionHandlers
    with all dependencies wired. The registry is immutable once created.

    This follows the ONEX declarative pattern:
    - Dependencies are validated at registry creation time (fail-fast)
    - No setter methods - dependencies are injected via factory
    - Registry is frozen after creation

    Example:
        >>> registry = RegistryPatternDemotionEffect.create_registry(
        ...     repository=db_connection,
        ...     producer=kafka_producer,
        ...     topic_env_prefix="prod",
        ... )
        >>> handler = registry.get_handler("check_and_demote_patterns")
        >>> result = await handler(request)
    """

    # Registry key for storage
    REGISTRY_KEY = "pattern_demotion"

    @staticmethod
    def create_registry(
        repository: ProtocolPatternRepository,
        producer: ProtocolKafkaPublisher,
        *,
        topic_env_prefix: str = "dev",
    ) -> RegistryDemotionHandlers:
        """Create a frozen registry with all handlers wired.

        This factory method:
        1. Validates that repository and producer are not None
        2. Creates handler functions with dependencies bound
        3. Returns a frozen RegistryDemotionHandlers

        Args:
            repository: Pattern repository implementing ProtocolPatternRepository.
                Required for database operations (fetch, execute).
            producer: Kafka producer implementing ProtocolKafkaPublisher.
                Required at the registry level to ensure registry-based usage
                always has full Kafka capability. While the underlying handler
                accepts None (contract marks kafka_producer as required=false),
                the registry enforces Kafka availability to guarantee event
                emission in production deployments.
            topic_env_prefix: Environment prefix for Kafka topics.
                Defaults to "dev". Must be non-empty alphanumeric with - or _.

        Returns:
            A frozen RegistryDemotionHandlers with handlers wired.

        Raises:
            ValueError: If repository or producer is None.
            ValueError: If topic_env_prefix is invalid.

        Note:
            To run demotions without Kafka (testing, migrations, degraded mode),
            call the handler functions directly with ``producer=None`` instead of
            using the registry. See module docstring "Kafka Optionality" section.
        """
        # Import here to avoid circular imports
        from omniintelligence.nodes.node_pattern_demotion_effect.handlers.handler_demotion import (
            check_and_demote_patterns,
        )

        # Validate dependencies (fail-fast)
        if repository is None:
            raise ValueError(
                "repository is required for RegistryPatternDemotionEffect. "
                "Provide a ProtocolPatternRepository implementation."
            )

        if producer is None:
            raise ValueError(
                "producer is required for RegistryPatternDemotionEffect. "
                "Provide a ProtocolKafkaPublisher implementation."
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
        async def bound_check_and_demote(
            request: ModelDemotionCheckRequest,
        ) -> ModelDemotionCheckResult:
            """Handler with repository and producer bound."""
            return await check_and_demote_patterns(
                repository=repository,
                producer=producer,
                request=request,
                topic_env_prefix=topic_env_prefix,
            )

        # Create frozen registry
        registry = RegistryDemotionHandlers(
            check_and_demote=bound_check_and_demote,
            topic_env_prefix=topic_env_prefix,
        )

        # Store in module-level storage
        _REGISTRY_STORAGE[RegistryPatternDemotionEffect.REGISTRY_KEY] = registry

        return registry

    @staticmethod
    def get_registry() -> RegistryDemotionHandlers | None:
        """Retrieve the current registry from module-level storage.

        Returns:
            The stored RegistryDemotionHandlers, or None if not created.
        """
        return _REGISTRY_STORAGE.get(RegistryPatternDemotionEffect.REGISTRY_KEY)

    @staticmethod
    def clear() -> None:
        """Clear all stored registries.

        This method MUST be called in test setup and teardown to prevent
        test pollution. Module-level state persists across test cases.

        Example:
            .. code-block:: python

                @pytest.fixture(autouse=True)
                def clear_registry():
                    RegistryPatternDemotionEffect.clear()
                    yield
                    RegistryPatternDemotionEffect.clear()
        """
        _REGISTRY_STORAGE.clear()
