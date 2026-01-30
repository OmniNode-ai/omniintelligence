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
from uuid import UUID

from omnibase_core.nodes.node_effect import NodeEffect

from omniintelligence.nodes.pattern_storage_effect.contract_loader import (
    ContractLoader,
    get_contract_loader,
)
from omniintelligence.nodes.pattern_storage_effect.handlers import (
    ProtocolPatternStateManager,
    ProtocolPatternStore,
)
from omniintelligence.nodes.pattern_storage_effect.handlers.handler_promote_pattern import (
    PatternNotFoundError,
    PatternStateTransitionError,
)
from omniintelligence.nodes.pattern_storage_effect.handlers.handler_pattern_storage import (
    OPERATION_PROMOTE_PATTERN,
    OPERATION_STORE_PATTERN,
    PatternStorageRouter,
    route_storage_operation,
)
from omniintelligence.nodes.pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternMetricsSnapshot,
    ModelPatternPromotedEvent,
    ModelPatternStorageInput,
    ModelPatternStoredEvent,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodePatternStorageEffect(NodeEffect):
    """Effect node for pattern storage with governance invariants.

    This effect node handles pattern storage and state promotion operations
    with full governance enforcement. It is a lightweight shell that delegates
    actual processing to handler functions.

    Supported Operations:
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

        # Store a pattern
        stored_event = await effect.store_pattern(input_data)

        # Promote a pattern
        promoted_event = await effect.promote_pattern(
            pattern_id=uuid,
            to_state=EnumPatternState.PROVISIONAL,
            reason="Pattern met verification criteria",
        )
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
    # Main Operations
    # =========================================================================

    async def execute(
        self,
        operation: str,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Contract-driven execution - dispatches via handler_routing.

        This is the fully declarative entry point. The contract.yaml defines
        which handler to call based on operation type. This method uses the
        route_storage_operation function which is the contract's entry_point.

        Supported operations (from contract.yaml):
            - store_pattern: Persist a learned pattern to storage
            - promote_pattern: Promote pattern state (candidate->provisional->validated)

        Args:
            operation: The operation to perform. Must match an operation
                defined in contract.yaml handler_routing.handlers.
            input_data: Dictionary containing operation-specific input fields.
                For store_pattern: ModelPatternStorageInput fields
                For promote_pattern: pattern_id, to_state, reason, etc.

        Returns:
            Dictionary containing operation result with fields:
                - operation: The operation that was performed
                - success: Whether the operation succeeded
                - event_type: "pattern_stored" or "pattern_promoted"
                - event: Serialized event data
                - error_message: Error message if failed

        Example:
            ```python
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
            ```
        """
        return await route_storage_operation(
            operation=operation,
            input_data=input_data,
            pattern_store=self._pattern_store,
            state_manager=self._state_manager,
        )

    async def store_pattern(
        self,
        input_data: ModelPatternStorageInput,
    ) -> ModelPatternStoredEvent:
        """Store a learned pattern with governance enforcement.

        This is a typed convenience method that delegates to the contract-driven
        execute() method for actual dispatch, then converts the result back to
        the typed event model.

        The underlying handler implements:
        1. Governance validation (confidence >= MIN_CONFIDENCE)
        2. Idempotency check (same pattern_id + signature_hash = same result)
        3. Version management (auto-increment, set previous not current)
        4. Pattern storage with is_current = true
        5. Audit trail creation

        Args:
            input_data: The pattern to store, validated against governance rules.

        Returns:
            ModelPatternStoredEvent with storage confirmation including
            pattern_id, version, state, and stored_at timestamp.

        Raises:
            ValueError: If governance validation fails (confidence below threshold).
            RuntimeError: If storage operation fails unexpectedly.

        Note:
            If pattern_store is not configured, the handler returns a mock
            response for testing purposes.
        """
        result = await self.execute(
            operation=OPERATION_STORE_PATTERN,
            input_data=input_data.model_dump(mode="json"),
        )
        if not result.get("success", False):
            error_msg = result.get("error_message", "Unknown error during store_pattern")
            # Governance failures raise ValueError (e.g., confidence below threshold)
            # Other unexpected failures raise RuntimeError
            if "governance" in error_msg.lower() or "confidence" in error_msg.lower():
                raise ValueError(error_msg)
            else:
                raise RuntimeError(error_msg)
        return ModelPatternStoredEvent(**result["event"])

    async def promote_pattern(
        self,
        pattern_id: UUID,
        to_state: EnumPatternState,
        reason: str,
        metrics_snapshot: ModelPatternMetricsSnapshot | None = None,
        *,
        actor: str = "system",
        correlation_id: UUID | None = None,
        domain: str | None = None,
        signature_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ModelPatternPromotedEvent:
        """Promote a pattern to a new state with audit trail.

        This is a typed convenience method that delegates to the contract-driven
        execute() method for actual dispatch, then converts the result back to
        the typed event model.

        The underlying handler implements:
        1. Get current state from state manager
        2. Validate transition is allowed (CANDIDATE->PROVISIONAL->VALIDATED)
        3. Update state in database
        4. Record transition in audit table
        5. Return event for Kafka broadcast

        Args:
            pattern_id: The pattern to promote.
            to_state: The target state for the promotion.
            reason: Human-readable reason for the promotion.
            metrics_snapshot: Optional metrics snapshot at promotion time.
                If not provided, a default snapshot with confidence=0.0 is created.
            actor: Identifier of the entity triggering the promotion.
                Defaults to "system".
            correlation_id: Optional correlation ID for distributed tracing.
            domain: Optional domain of the pattern (for audit context).
            signature_hash: Optional signature hash (for audit context).
            metadata: Optional additional context for the audit record.

        Returns:
            ModelPatternPromotedEvent ready for Kafka broadcast including
            from_state, to_state, reason, and metrics_snapshot.

        Raises:
            PatternNotFoundError: If the pattern does not exist in state manager.
            PatternStateTransitionError: If the transition is invalid.

        Note:
            If state_manager is not configured, the handler performs validation
            only (dry-run mode) and infers from_state based on to_state.
        """
        # Build input data dict for contract-driven dispatch
        input_data: dict[str, Any] = {
            "pattern_id": str(pattern_id),
            "to_state": to_state.value,
            "reason": reason,
            "actor": actor,
        }

        if metrics_snapshot is not None:
            input_data["metrics_snapshot"] = metrics_snapshot.model_dump(mode="json")

        if correlation_id is not None:
            input_data["correlation_id"] = str(correlation_id)

        if domain is not None:
            input_data["domain"] = domain

        if signature_hash is not None:
            input_data["signature_hash"] = signature_hash

        if metadata is not None:
            input_data["metadata"] = metadata

        result = await self.execute(
            operation=OPERATION_PROMOTE_PATTERN,
            input_data=input_data,
        )

        if not result.get("success", False):
            error_msg = result.get("error_message", "Unknown error during promote_pattern")
            # Match exception type to error content per docstring contract
            if "not found" in error_msg.lower():
                raise PatternNotFoundError(pattern_id)
            elif "invalid transition" in error_msg.lower() or "cannot transition" in error_msg.lower():
                raise PatternStateTransitionError(
                    pattern_id=pattern_id,
                    from_state=None,  # Unknown at this level
                    to_state=to_state,
                    message=error_msg,
                )
            else:
                raise ValueError(error_msg)

        return ModelPatternPromotedEvent(**result["event"])


__all__ = ["NodePatternStorageEffect"]
