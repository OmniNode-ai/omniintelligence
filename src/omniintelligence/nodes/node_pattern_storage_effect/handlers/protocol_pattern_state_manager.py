# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""ProtocolPatternStateManager - protocol for pattern state management operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

from omniintelligence.nodes.node_pattern_storage_effect.models.model_pattern_state import (
    EnumPatternState,
)

if TYPE_CHECKING:
    from psycopg import AsyncConnection

    from omniintelligence.nodes.node_pattern_storage_effect.handlers.model_state_transition import (
        ModelStateTransition,
    )


@runtime_checkable
class ProtocolPatternStateManager(Protocol):
    """Protocol for pattern state management operations.

    This protocol defines the interface for managing pattern states in
    a storage backend (database). Implementations must provide methods
    for reading current state, updating state, and recording transitions.

    The protocol is runtime-checkable for isinstance() validation.

    IMPORTANT: Implementations MUST ensure that update_state() and record_transition()
    are executed atomically (within a single database transaction). If record_transition
    fails after update_state succeeds, the pattern state would be updated without an
    audit trail, violating governance compliance requirements.

    Transaction Control:
        All methods require a `conn` parameter for transaction control. The caller
        (e.g., infra wiring) owns the transaction spanning idempotency checks and
        pattern state operations. This ensures atomic operations.
    """

    async def get_current_state(
        self,
        pattern_id: UUID,
        conn: AsyncConnection,
    ) -> EnumPatternState | None:
        """Get the current state of a pattern.

        Args:
            pattern_id: The pattern to query.
            conn: Database connection for transaction control.

        Returns:
            The current state of the pattern, or None if not found.
        """
        ...

    async def update_state(
        self,
        pattern_id: UUID,
        new_state: EnumPatternState,
        conn: AsyncConnection,
    ) -> None:
        """Update the state of a pattern.

        Args:
            pattern_id: The pattern to update.
            new_state: The new state to set.
            conn: Database connection for transaction control.

        Raises:
            PatternNotFoundError: If the pattern does not exist.
        """
        ...

    async def record_transition(
        self,
        transition: ModelStateTransition,
        conn: AsyncConnection,
    ) -> None:
        """Record a state transition in the audit table.

        Args:
            transition: The transition record to insert.
            conn: Database connection for transaction control.

        Raises:
            Exception: If the insert fails (e.g., duplicate event_id).
        """
        ...
