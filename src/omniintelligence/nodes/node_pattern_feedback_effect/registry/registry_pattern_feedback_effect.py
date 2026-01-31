# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Registry for Pattern Feedback Effect Node Dependencies.

This module provides RegistryPatternFeedbackEffect, which manages
handler registration and dependency injection for the NodePatternFeedbackEffect.

Architecture:
    The registry follows ONEX declarative dependency injection:
    - Static factory creates registry with pre-validated dependencies
    - Registry is frozen after creation (immutable)
    - Handlers receive explicit constructor-injected dependencies
    - No setters, no container lookups at runtime

Testing:
    This module uses module-level state for handler storage. Tests MUST call
    ``RegistryPatternFeedbackEffect.clear()`` in setup and teardown fixtures
    to prevent test pollution between test cases.

    Recommended fixture pattern:

    .. code-block:: python

        @pytest.fixture(autouse=True)
        def clear_registry():
            RegistryPatternFeedbackEffect.clear()
            yield
            RegistryPatternFeedbackEffect.clear()

Reference:
    - OMN-1678: Rolling window metric updates for session outcomes
    - OMN-1679: Contribution heuristic for outcome attribution
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        ProtocolPatternRepository,
    )

logger = logging.getLogger(__name__)

__all__ = ["RegistryPatternFeedbackEffect"]

# Module-level storage for handler dependencies
# This allows test isolation via clear() without requiring container v2.0 features
_HANDLER_STORAGE: dict[str, Any] = {}
_PROTOCOL_METADATA: dict[str, dict[str, object]] = {}


class RegistryPatternFeedbackEffect:
    """Registry for pattern feedback effect node dependencies.

    Manages handler registration with explicit dependency injection.
    The registry validates dependencies at registration time (fail-fast)
    and provides retrieval for use by the node.

    Usage:
        .. code-block:: python

            from omniintelligence.nodes.node_pattern_feedback_effect.registry import (
                RegistryPatternFeedbackEffect,
            )

            # Register repository dependency
            RegistryPatternFeedbackEffect.register_repository(db_connection)

            # Create node with registry-managed dependencies
            node = NodePatternFeedbackEffect(container)
            result = await node.execute(request)

    Note:
        This registry does NOT instantiate handlers. The repository must be
        created externally (e.g., asyncpg connection) and registered here.
        The node retrieves the repository via get_repository().
    """

    # Handler keys for registration
    REPOSITORY_KEY = "pattern_repository"

    @staticmethod
    def _is_registered(handler_key: str) -> bool:
        """Check if a handler is already registered for the given key.

        Args:
            handler_key: The handler key to check.

        Returns:
            True if a handler is registered for this key, False otherwise.
        """
        return handler_key in _HANDLER_STORAGE

    @staticmethod
    def register_repository(repository: ProtocolPatternRepository) -> None:
        """Register the pattern repository for database operations.

        The repository must implement ProtocolPatternRepository with:
        - async fetch(query, *args) -> list[Mapping[str, Any]]
        - async execute(query, *args) -> str

        Args:
            repository: Database repository implementing ProtocolPatternRepository.

        Raises:
            TypeError: If repository does not implement required protocol methods.

        Example:
            >>> import asyncpg
            >>> conn = await asyncpg.connect(...)
            >>> RegistryPatternFeedbackEffect.register_repository(conn)
        """
        # Protocol-based duck typing validation (fail-fast)
        required_methods = ["fetch", "execute"]
        missing = [
            m for m in required_methods if not callable(getattr(repository, m, None))
        ]
        if missing:
            raise TypeError(
                f"Repository missing required protocol methods: {missing}. "
                f"Got {type(repository).__name__}"
            )

        # Warn if re-registering over an existing repository
        if RegistryPatternFeedbackEffect._is_registered(
            RegistryPatternFeedbackEffect.REPOSITORY_KEY
        ):
            logger.warning(
                "Re-registering repository '%s'. This may indicate lifecycle "
                "issues or missing clear() calls in tests.",
                RegistryPatternFeedbackEffect.REPOSITORY_KEY,
            )

        _HANDLER_STORAGE[RegistryPatternFeedbackEffect.REPOSITORY_KEY] = repository

        # Store protocol metadata for introspection
        _PROTOCOL_METADATA[RegistryPatternFeedbackEffect.REPOSITORY_KEY] = {
            "protocol": "ProtocolPatternRepository",
            "module": "omniintelligence.nodes.node_pattern_feedback_effect.handlers",
            "description": "Pattern repository for database operations",
            "capabilities": [
                "fetch",
                "execute",
            ],
        }

    @staticmethod
    def get_repository() -> ProtocolPatternRepository | None:
        """Retrieve the registered pattern repository.

        Returns:
            The registered repository, or None if not registered.

        Example:
            >>> repository = RegistryPatternFeedbackEffect.get_repository()
            >>> if repository:
            ...     result = await repository.fetch(query, *args)
        """
        from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
            ProtocolPatternRepository,
        )

        result = _HANDLER_STORAGE.get(RegistryPatternFeedbackEffect.REPOSITORY_KEY)
        if result is not None and isinstance(result, ProtocolPatternRepository):
            return result
        return result  # May be None or a duck-typed object

    @staticmethod
    def has_repository() -> bool:
        """Check if a repository is registered.

        Returns:
            True if a repository is registered, False otherwise.
        """
        return RegistryPatternFeedbackEffect._is_registered(
            RegistryPatternFeedbackEffect.REPOSITORY_KEY
        )

    @staticmethod
    def clear() -> None:
        """Clear all registered handlers and protocol metadata.

        Resets all module-level state to empty dicts. This method is essential
        for test isolation.

        Warning:
            This method MUST be called in test setup and teardown to prevent
            test pollution. Module-level state persists across test cases within
            the same Python process.

        Example:
            .. code-block:: python

                @pytest.fixture(autouse=True)
                def clear_registry():
                    RegistryPatternFeedbackEffect.clear()
                    yield
                    RegistryPatternFeedbackEffect.clear()
        """
        _HANDLER_STORAGE.clear()
        _PROTOCOL_METADATA.clear()
