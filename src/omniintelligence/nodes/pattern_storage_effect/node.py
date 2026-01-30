# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Storage Effect - Persist learned patterns with governance.

This node follows the ONEX declarative pattern:
    - EFFECT node for database I/O operations
    - Enforces governance invariants (confidence, uniqueness, versioning)
    - Lightweight shell that delegates to handlers via DI
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
Handler routing is driven by operation type matching.

Handler Routing Pattern:
    1. Receive pattern storage input (ModelPatternStorageInput)
    2. Validate governance invariants (confidence >= 0.5)
    3. Delegate to appropriate handler (store or promote)
    4. Return structured event (ModelPatternStoredEvent or ModelPatternPromotedEvent)

Design Decisions:
    - Separate handlers for store and promote operations
    - Governance validation is enforced at handler level
    - External adapters injected via setter methods
    - Idempotent storage via (pattern_id, signature_hash) key

Node Responsibilities:
    - Define I/O model contract
    - Provide dependency injection points for adapters
    - Delegate execution to handlers

Reference:
    - OMN-1668: Pattern storage effect node implementation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omnibase_core.nodes.node_effect import NodeEffect

from omniintelligence.nodes.pattern_storage_effect.contract_loader import (
    ContractLoader,
    get_contract_loader,
)
from omniintelligence.nodes.pattern_storage_effect.handlers import (
    ProtocolPatternStateManager,
    ProtocolPatternStore,
)
from omniintelligence.nodes.pattern_storage_effect.handlers.handler_pattern_storage import (
    PatternStorageRouter,
    route_storage_operation,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodePatternStorageEffect(NodeEffect):
    """Effect node for pattern storage with governance invariants.

    This effect node handles pattern storage and state promotion operations
    with full governance enforcement. It is a lightweight shell that delegates
    actual processing to handler functions via the contract-driven execute() method.

    Supported Operations (via execute()):
        - store_pattern: Store a learned pattern with governance validation
        - promote_pattern: Promote pattern state with audit trail

    Governance Invariants (enforced by handlers):
        - Confidence >= 0.5 (MIN_CONFIDENCE)
        - UNIQUE(domain, signature_hash, version)
        - UNIQUE(domain, signature_hash) WHERE is_current = true
        - Idempotent storage via (pattern_id, signature_hash)

    State Transitions:
        - CANDIDATE -> PROVISIONAL: Pattern passes verification
        - PROVISIONAL -> VALIDATED: Pattern meets all validation criteria
        - VALIDATED is terminal (no further transitions)

    Dependency Injection:
        Adapters are injected via setter methods:
        - set_pattern_store(): Database access for pattern persistence
        - set_state_manager(): State transition management

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.pattern_storage_effect import (
            NodePatternStorageEffect,
        )

        # Create effect node
        container = ModelONEXContainer()
        effect = NodePatternStorageEffect(container)

        # Wire dependencies
        effect.set_pattern_store(pattern_store)
        effect.set_state_manager(state_manager)

        # Store a pattern via contract-driven dispatch
        result = await effect.execute(
            operation="store_pattern",
            input_data={
                "pattern_id": str(uuid4()),
                "signature": "def.*return.*None",
                "signature_hash": "abc123",
                "domain": "code_patterns",
                "confidence": 0.85,
            },
        )
        assert result["success"]
        assert result["event_type"] == "pattern_stored"

        # Promote a pattern via contract-driven dispatch
        result = await effect.execute(
            operation="promote_pattern",
            input_data={
                "pattern_id": str(uuid4()),
                "to_state": "provisional",
                "reason": "Pattern met verification criteria",
                "actor": "system",
            },
        )
        assert result["success"]
        assert result["event_type"] == "pattern_promoted"
        ```
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the pattern storage effect node.

        Args:
            container: ONEX dependency injection container.
        """
        super().__init__(container)

        # Contract-driven configuration
        self._contract_loader = get_contract_loader()
        self._router = PatternStorageRouter()

        # Injected dependencies (optional - node works without them in test mode)
        self._pattern_store: ProtocolPatternStore | None = None
        self._state_manager: ProtocolPatternStateManager | None = None

    # =========================================================================
    # Dependency Injection Setters
    # =========================================================================

    def set_pattern_store(self, store: ProtocolPatternStore) -> None:
        """Set the pattern store for database operations.

        The pattern store implements ProtocolPatternStore and provides methods
        for persisting patterns with version tracking and idempotency.

        Also wires the store to the internal router for contract-driven dispatch.

        Args:
            store: Pattern store instance implementing ProtocolPatternStore.
        """
        self._pattern_store = store
        self._router.set_pattern_store(store)

    def set_state_manager(self, manager: ProtocolPatternStateManager) -> None:
        """Set the state manager for state transition operations.

        The state manager implements ProtocolPatternStateManager and provides
        methods for reading/updating pattern states and recording transitions.

        Also wires the manager to the internal router for contract-driven dispatch.

        Args:
            manager: State manager instance implementing ProtocolPatternStateManager.
        """
        self._state_manager = manager
        self._router.set_state_manager(manager)

    # =========================================================================
    # Property Accessors
    # =========================================================================

    @property
    def pattern_store(self) -> ProtocolPatternStore | None:
        """Get the pattern store if configured."""
        return self._pattern_store

    @property
    def state_manager(self) -> ProtocolPatternStateManager | None:
        """Get the state manager if configured."""
        return self._state_manager

    @property
    def has_pattern_store(self) -> bool:
        """Check if pattern store is configured."""
        return self._pattern_store is not None

    @property
    def has_state_manager(self) -> bool:
        """Check if state manager is configured."""
        return self._state_manager is not None

    # =========================================================================
    # Contract Introspection Properties
    # =========================================================================

    @property
    def contract_loader(self) -> ContractLoader:
        """Access the contract loader for introspection.

        Returns:
            The ContractLoader instance for this node.
        """
        return self._contract_loader

    @property
    def subscribe_topics(self) -> list[str]:
        """Topics this node subscribes to (from contract).

        Returns:
            List of Kafka topic names for subscription.
        """
        return self._contract_loader.subscribe_topics

    @property
    def publish_topics(self) -> list[str]:
        """Topics this node publishes to (from contract).

        Returns:
            List of Kafka topic names for publishing.
        """
        return self._contract_loader.publish_topics

    @property
    def supported_operations(self) -> list[str]:
        """List of operations supported by this node (from contract).

        Returns:
            List of operation names that have handlers configured.
        """
        return self._contract_loader.list_operations()

    # =========================================================================
    # Main Execution Entry Point
    # =========================================================================

    async def execute(
        self,
        operation: str,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a pattern storage operation via contract-driven dispatch.

        Routes the operation to the appropriate handler based on operation type
        and returns the processing result. This is the single entry point for
        all pattern storage operations following the ONEX declarative pattern.

        Supported operations (from contract.yaml):
            - store_pattern: Persist a learned pattern to storage
            - promote_pattern: Promote pattern state (candidate->provisional->validated)

        Args:
            operation: The operation to perform. Must match an operation
                defined in contract.yaml handler_routing.handlers.
            input_data: Dictionary containing operation-specific input fields.
                For store_pattern: pattern_id, signature, signature_hash,
                    domain, confidence, etc.
                For promote_pattern: pattern_id, to_state, reason, actor, etc.

        Returns:
            Dictionary containing operation result with fields:
                - operation: The operation that was performed
                - success: Whether the operation succeeded
                - event_type: "pattern_stored" or "pattern_promoted"
                - event: Serialized event data
                - error_message: Error message if failed
                - error_code: Error code if failed
        """
        return await route_storage_operation(
            operation=operation,
            input_data=input_data,
            pattern_store=self._pattern_store,
            state_manager=self._state_manager,
        )


__all__ = ["NodePatternStorageEffect"]
