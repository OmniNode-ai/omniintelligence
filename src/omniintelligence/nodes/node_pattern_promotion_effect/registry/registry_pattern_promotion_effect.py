# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Registry for Pattern Promotion Node Dependencies.

This module provides RegistryPatternPromotionEffect, which creates a registry
of handlers for the NodePatternPromotionEffect node.

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

        from omniintelligence.nodes.node_pattern_promotion_effect.handlers import (
            check_and_promote_patterns,
        )

        # Direct handler call - producer=None is explicitly allowed
        result = await check_and_promote_patterns(
            repository=db_connection,
            producer=None,  # Promotions succeed, Kafka events skipped
            dry_run=False,
        )

    **Implications of running without Kafka:**
    - Database promotions succeed normally
    - No ``PatternPromoted`` events are emitted to Kafka
    - Downstream caches relying on Kafka for invalidation become stale
    - See ``handler_promotion.py`` module docstring for reconciliation strategy

Usage:
    >>> from omniintelligence.nodes.node_pattern_promotion_effect.registry import (
    ...     RegistryPatternPromotionEffect,
    ... )
    >>>
    >>> # Create registry with dependencies (requires Kafka producer)
    >>> registry = RegistryPatternPromotionEffect.create_registry(
    ...     repository=db_connection,
    ...     producer=kafka_producer,
    ... )
    >>>
    >>> # Get handler from registry
    >>> handler = registry.get_handler("check_and_promote_patterns")
    >>> result = await handler(request)

Testing:
    This module uses module-level state for handler storage. Tests MUST call
    ``RegistryPatternPromotionEffect.clear()`` in setup and teardown fixtures
    to prevent test pollution between test cases.

    Recommended fixture pattern:

    .. code-block:: python

        @pytest.fixture(autouse=True)
        def clear_registry():
            RegistryPatternPromotionEffect.clear()
            yield
            RegistryPatternPromotionEffect.clear()

    **For testing without Kafka**, call handlers directly with ``producer=None``
    rather than using the registry.

Related:
    - NodePatternPromotionEffect: Effect node that uses these dependencies
    - handler_promotion: Handler functions for pattern promotion
    - ProtocolPatternRepository: Repository protocol for database operations
    - ProtocolKafkaPublisher: Publisher protocol for Kafka events
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any  # any-ok: Coroutine[Any, Any, T] is standard async type alias

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_promotion import (
        ProtocolKafkaPublisher,
        ProtocolPatternRepository,
    )
    from omniintelligence.nodes.node_pattern_promotion_effect.models import (
        ModelPromotionCheckRequest,
        ModelPromotionCheckResult,
    )

logger = logging.getLogger(__name__)

__all__ = ["RegistryPatternPromotionEffect", "RegistryPromotionHandlers"]


# Type alias for handler function signature
HandlerFunction = Callable[
    ["ModelPromotionCheckRequest"],
    Coroutine[Any, Any, "ModelPromotionCheckResult"],
]


@dataclass(frozen=True)
class RegistryPromotionHandlers:
    """Frozen registry of handler functions for pattern promotion.

    This class holds the wired handler functions with their dependencies
    already bound. Once created, it cannot be modified (frozen dataclass).

    Attributes:
        check_and_promote: Handler function for checking and promoting patterns.
            Dependencies (repository, producer) are already bound.
        topic_env_prefix: Environment prefix for Kafka topics.
    """

    check_and_promote: HandlerFunction
    topic_env_prefix: str = "dev"

    _handlers: dict[str, HandlerFunction] = field(
        default_factory=dict, repr=False, compare=False, hash=False
    )

    def __post_init__(self) -> None:
        """Initialize the handlers dict after creation."""
        # Use object.__setattr__ because dataclass is frozen
        handlers = {"check_and_promote_patterns": self.check_and_promote}
        object.__setattr__(self, "_handlers", handlers)

    def get_handler(self, operation: str) -> HandlerFunction | None:
        """Get a handler function by operation name.

        Args:
            operation: The operation name (e.g., "check_and_promote_patterns").

        Returns:
            The handler function if found, None otherwise.
        """
        return self._handlers.get(operation)


# Module-level storage for registry (similar to omnibase_infra pattern)
_REGISTRY_STORAGE: dict[str, RegistryPromotionHandlers] = {}


class RegistryPatternPromotionEffect:
    """Registry for pattern promotion node dependencies.

    Provides a static factory method to create a RegistryPromotionHandlers
    with all dependencies wired. The registry is immutable once created.

    This follows the ONEX declarative pattern:
    - Dependencies are validated at registry creation time (fail-fast)
    - No setter methods - dependencies are injected via factory
    - Registry is frozen after creation

    Example:
        >>> registry = RegistryPatternPromotionEffect.create_registry(
        ...     repository=db_connection,
        ...     producer=kafka_producer,
        ...     topic_env_prefix="prod",
        ... )
        >>> handler = registry.get_handler("check_and_promote_patterns")
        >>> result = await handler(request)
    """

    # Registry key for storage
    REGISTRY_KEY = "pattern_promotion"

    @staticmethod
    def create_registry(
        repository: ProtocolPatternRepository,
        producer: ProtocolKafkaPublisher,
        *,
        topic_env_prefix: str = "dev",
    ) -> RegistryPromotionHandlers:
        """Create a frozen registry with all handlers wired.

        This factory method:
        1. Validates that repository and producer are not None
        2. Creates handler functions with dependencies bound
        3. Returns a frozen RegistryPromotionHandlers

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
            A frozen RegistryPromotionHandlers with handlers wired.

        Raises:
            ValueError: If repository or producer is None.
            ValueError: If topic_env_prefix is invalid.

        Note:
            To run promotions without Kafka (testing, migrations, degraded mode),
            call the handler functions directly with ``producer=None`` instead of
            using the registry. See module docstring "Kafka Optionality" section.
        """
        # Import here to avoid circular imports
        from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_promotion import (
            check_and_promote_patterns,
        )

        # Validate dependencies (fail-fast)
        if repository is None:
            raise ValueError(
                "repository is required for RegistryPatternPromotionEffect. "
                "Provide a ProtocolPatternRepository implementation."
            )

        if producer is None:
            raise ValueError(
                "producer is required for RegistryPatternPromotionEffect. "
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
        async def bound_check_and_promote(
            request: ModelPromotionCheckRequest,
        ) -> ModelPromotionCheckResult:
            """Handler with repository and producer bound."""
            return await check_and_promote_patterns(
                repository=repository,
                producer=producer,
                dry_run=request.dry_run,
                min_injection_count=request.min_injection_count,
                min_success_rate=request.min_success_rate,
                max_failure_streak=request.max_failure_streak,
                correlation_id=request.correlation_id,
                topic_env_prefix=topic_env_prefix,
            )

        # Create frozen registry
        registry = RegistryPromotionHandlers(
            check_and_promote=bound_check_and_promote,
            topic_env_prefix=topic_env_prefix,
        )

        # Store in module-level storage
        _REGISTRY_STORAGE[RegistryPatternPromotionEffect.REGISTRY_KEY] = registry

        return registry

    @staticmethod
    def get_registry() -> RegistryPromotionHandlers | None:
        """Retrieve the current registry from module-level storage.

        Returns:
            The stored RegistryPromotionHandlers, or None if not created.
        """
        return _REGISTRY_STORAGE.get(RegistryPatternPromotionEffect.REGISTRY_KEY)

    @staticmethod
    def clear() -> None:
        """Clear all stored registries.

        This method MUST be called in test setup and teardown to prevent
        test pollution. Module-level state persists across test cases.

        Example:
            .. code-block:: python

                @pytest.fixture(autouse=True)
                def clear_registry():
                    RegistryPatternPromotionEffect.clear()
                    yield
                    RegistryPatternPromotionEffect.clear()
        """
        _REGISTRY_STORAGE.clear()
