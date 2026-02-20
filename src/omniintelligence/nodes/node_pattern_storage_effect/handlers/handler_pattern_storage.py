# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern storage operation router - contract-driven dispatch.

This module provides the entry point for contract-driven handler routing as
defined in contract.yaml. The route_storage_operation function is the main
entry point that dispatches to the appropriate handler based on operation type.

Contract Reference (handler_routing section):
    - Entry point: route_storage_operation
    - Operations:
        - store_pattern -> handle_store_pattern
        - promote_pattern -> handle_promote_pattern
    - Default: handle_store_pattern (for unrecognized operations)

Usage:
    # Direct function call (contract entry point)
    result = await route_storage_operation(
        operation="store_pattern",
        input_data={"pattern_id": "...", "signature": "...", ...},
        pattern_store=store_impl,
    )

    # Class-based usage (for dependency injection)
    router = PatternStorageRouter(
        pattern_store=store_impl,
        state_manager=manager_impl,
    )
    result = await router.route(operation="store_pattern", input_data={...})

Reference:
    - OMN-1668: Pattern storage effect node implementation
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID

if TYPE_CHECKING:
    from psycopg import AsyncConnection

from pydantic import ValidationError

from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_promote_pattern import (
    DEFAULT_ACTOR,
    PromotePatternResult,
    ProtocolPatternStateManager,
    handle_promote_pattern,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern import (
    ProtocolPatternStore,
    StorePatternResult,
    handle_store_pattern,
)
from omniintelligence.nodes.node_pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternMetricsSnapshot,
    ModelPatternPromotedEvent,
    ModelPatternStorageInput,
    ModelPatternStoredEvent,
)

# =============================================================================
# Logging Configuration
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

OPERATION_STORE_PATTERN: Final[str] = "store_pattern"
OPERATION_PROMOTE_PATTERN: Final[str] = "promote_pattern"

# Error codes for programmatic exception routing (avoid fragile string matching)
ERROR_CODE_PATTERN_NOT_FOUND: Final[str] = "PATTERN_NOT_FOUND"
ERROR_CODE_INVALID_TRANSITION: Final[str] = "INVALID_TRANSITION"
ERROR_CODE_GOVERNANCE_VIOLATION: Final[str] = "GOVERNANCE_VIOLATION"
ERROR_CODE_VALIDATION_ERROR: Final[str] = "VALIDATION_ERROR"
ERROR_CODE_STORAGE_ERROR: Final[str] = "STORAGE_ERROR"
# PATSTOR_001 is declared in contract.yaml (PatternStorageError) but has no active
# emission path — the only previous emitter (pattern_store is None guard) was removed
# when pattern_store became a required constructor parameter.
ERROR_CODE_PATSTOR_001: Final[str] = "PATSTOR_001"
ERROR_CODE_PATSTOR_002: Final[str] = "PATSTOR_002"
ERROR_CODE_PATSTOR_003: Final[str] = "PATSTOR_003"


# =============================================================================
# Result Types
# =============================================================================


class StorageOperationResult:
    """Result wrapper for storage operation dispatch.

    Provides a unified interface for both store and promote operations,
    allowing the caller to check which operation was performed and access
    the appropriate result.

    Attributes:
        operation: The operation that was performed.
        success: Whether the operation succeeded.
        stored_event: The stored event (if store_pattern operation).
        promoted_event: The promoted event (if promote_pattern operation).
        error_code: Machine-readable error code for programmatic handling.
            Standard codes:
            - "PATTERN_NOT_FOUND": Pattern does not exist
            - "INVALID_TRANSITION": State transition not allowed
            - "GOVERNANCE_VIOLATION": Governance rules violated (e.g., low confidence)
            - "VALIDATION_ERROR": Input validation failed
        error_message: Human-readable error message if operation failed.
    """

    def __init__(
        self,
        operation: str,
        success: bool = True,
        stored_event: ModelPatternStoredEvent | None = None,
        promoted_event: ModelPatternPromotedEvent | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Initialize the result.

        Args:
            operation: The operation that was performed.
            success: Whether the operation succeeded.
            stored_event: The stored event (if store_pattern operation).
            promoted_event: The promoted event (if promote_pattern operation).
            error_code: Machine-readable error code for programmatic handling.
            error_message: Human-readable error message if operation failed.
        """
        self.operation = operation
        self.success = success
        self.stored_event = stored_event
        self.promoted_event = promoted_event
        self.error_code = error_code
        self.error_message = error_message

    def to_dict(self) -> dict[str, object]:
        """Convert result to dictionary for serialization.

        Returns:
            Dictionary representation of the result.
        """
        result: dict[str, object] = {
            "operation": self.operation,
            "success": self.success,
        }

        if self.stored_event is not None:
            result["event_type"] = "pattern_stored"
            result["event"] = self.stored_event.model_dump(mode="json")
        elif self.promoted_event is not None:
            result["event_type"] = "pattern_promoted"
            result["event"] = self.promoted_event.model_dump(mode="json")

        if self.error_code is not None:
            result["error_code"] = self.error_code

        if self.error_message is not None:
            result["error_message"] = self.error_message

        return result


# =============================================================================
# Router Class
# =============================================================================


class PatternStorageRouter:
    """Contract-driven router for pattern storage operations.

    This class provides a dependency-injectable router for pattern storage
    operations. It maintains references to the pattern store and state manager,
    and routes operations to the appropriate handlers.

    Usage:
        router = PatternStorageRouter(
            pattern_store=store_impl,
            state_manager=manager_impl,
        )

        result = await router.route(
            operation="store_pattern",
            input_data={"pattern_id": "...", ...},
        )

    Attributes:
        _pattern_store: The pattern store for storage operations.
        _state_manager: The state manager for promotion operations.
    """

    def __init__(
        self,
        *,
        pattern_store: ProtocolPatternStore,
        state_manager: ProtocolPatternStateManager | None = None,
    ) -> None:
        """Initialize the router with dependencies.

        Args:
            pattern_store: Pattern store implementing ProtocolPatternStore.
                Required for store_pattern operations.
            state_manager: State manager implementing ProtocolPatternStateManager.
                Optional at construction time; required at the call-site level
                only for promote_pattern operations (returns structured error if absent).
        """
        self._pattern_store: ProtocolPatternStore = pattern_store
        self._state_manager: ProtocolPatternStateManager | None = state_manager

    async def route(
        self,
        operation: str,
        input_data: dict[
            str, Any
        ],  # any-ok: dynamic dispatch data, values are typed at call site
        *,
        conn: AsyncConnection[Any],  # any-ok: psycopg AsyncConnection row factory type
    ) -> StorageOperationResult:
        """Route operation to the appropriate handler.

        This method implements the routing logic defined in contract.yaml:
            - store_pattern -> handle_store_pattern
            - promote_pattern -> handle_promote_pattern
            - default -> handle_store_pattern

        Args:
            operation: The operation to perform (store_pattern, promote_pattern).
            input_data: The input data dictionary for the operation.
            conn: Database connection for transaction control. All operations
                use this connection for atomic idempotency + storage.

        Returns:
            StorageOperationResult with the operation outcome.

        Raises:
            ValueError: If input data is invalid for the operation.
            RuntimeError: If a required dependency is not set.
        """
        logger.debug(
            "Routing storage operation",
            extra={
                "operation": operation,
                "has_state_manager": self._state_manager is not None,
            },
        )

        if operation == OPERATION_STORE_PATTERN:
            return await self._handle_store(input_data, conn=conn)
        elif operation == OPERATION_PROMOTE_PATTERN:
            return await self._handle_promote(input_data, conn=conn)
        else:
            # Default to store_pattern per contract.yaml default_handler
            logger.info(
                "Unknown operation, defaulting to store_pattern",
                extra={"operation": operation},
            )
            return await self._handle_store(input_data, conn=conn)

    async def _handle_store(
        self,
        input_data: dict[
            str, Any
        ],  # any-ok: dynamic dispatch data, values are typed at call site
        *,
        conn: AsyncConnection[Any],  # any-ok: psycopg AsyncConnection row factory type
    ) -> StorageOperationResult:
        """Handle store_pattern operation.

        Converts input dict to ModelPatternStorageInput and delegates to
        handle_store_pattern handler.

        Args:
            input_data: Dictionary containing pattern storage input fields.
            conn: Database connection for transaction control. All operations
                use this connection for atomic idempotency + storage.

        Returns:
            StorageOperationResult with stored event, or failure result for
            governance violations and validation errors.
        """
        try:
            # Convert dict to typed input model
            storage_input = ModelPatternStorageInput.model_validate(input_data)
        except (ValidationError, ValueError) as e:
            error_msg = str(e)
            logger.warning(
                "Store pattern input validation failed",
                extra={"error": error_msg, "error_code": ERROR_CODE_VALIDATION_ERROR},
            )
            return StorageOperationResult(
                operation=OPERATION_STORE_PATTERN,
                success=False,
                error_code=ERROR_CODE_VALIDATION_ERROR,
                error_message=error_msg,
            )
        except Exception as e:
            error_msg = str(e)
            logger.warning(
                "Store pattern unexpected error during input processing",
                extra={"error": error_msg, "error_code": ERROR_CODE_STORAGE_ERROR},
            )
            return StorageOperationResult(
                operation=OPERATION_STORE_PATTERN,
                success=False,
                error_code=ERROR_CODE_STORAGE_ERROR,
                error_message=error_msg,
            )

        # Call the existing handler (returns structured result, not exceptions)
        store_result: StorePatternResult = await handle_store_pattern(
            input_data=storage_input,
            pattern_store=self._pattern_store,
            conn=conn,
        )

        if not store_result.success:
            # Distinguish governance violations from generic storage failures
            has_governance_violations = bool(store_result.governance_violations)
            if has_governance_violations:
                error_code = ERROR_CODE_GOVERNANCE_VIOLATION
                default_message = "Governance validation failed"
                log_message = "Store pattern governance validation failed"
            else:
                error_code = ERROR_CODE_PATSTOR_003
                default_message = "Pattern storage failed"
                log_message = "Store pattern operation failed"

            logger.warning(
                log_message,
                extra={
                    "error": store_result.error_message,
                    "error_code": error_code,
                },
            )
            return StorageOperationResult(
                operation=OPERATION_STORE_PATTERN,
                success=False,
                error_code=error_code,
                error_message=store_result.error_message or default_message,
            )

        stored_event = store_result.event
        if stored_event is None:
            raise RuntimeError(
                f"Invariant violation: store succeeded but event is None "
                f"(pattern_id={storage_input.pattern_id})"
            )

        logger.info(
            "Store pattern operation completed",
            extra={
                "pattern_id": str(stored_event.pattern_id),
                "domain": stored_event.domain,
                "version": stored_event.version,
            },
        )

        return StorageOperationResult(
            operation=OPERATION_STORE_PATTERN,
            success=True,
            stored_event=stored_event,
        )

    async def _handle_promote(
        self,
        input_data: dict[
            str, Any
        ],  # any-ok: dynamic dispatch data, values are typed at call site
        *,
        conn: AsyncConnection[Any],  # any-ok: psycopg AsyncConnection row factory type
    ) -> StorageOperationResult:
        """Handle promote_pattern operation.

        Extracts promotion parameters from input dict and delegates to
        handle_promote_pattern handler.

        Args:
            input_data: Dictionary containing promotion parameters:
                - pattern_id (required): UUID of pattern to promote
                - to_state (required): Target state (provisional, validated)
                - reason (required): Reason for promotion
                - metrics_snapshot (optional): Current metrics
                - actor (optional): Who triggered the promotion
                - correlation_id (optional): Correlation ID for tracing
                - domain (optional): Pattern domain
                - signature_hash (optional): Pattern signature hash
                - metadata (optional): Additional metadata
            conn: Database connection for transaction control.

        Returns:
            StorageOperationResult with promoted event.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        try:
            # Extract and validate required fields
            pattern_id_str = input_data.get("pattern_id")
            if pattern_id_str is None:
                msg = "pattern_id is required for promote_pattern operation"
                raise ValueError(msg)

            pattern_id = (
                UUID(pattern_id_str)
                if isinstance(pattern_id_str, str)
                else pattern_id_str
            )

            to_state_str = input_data.get("to_state")
            if to_state_str is None:
                msg = "to_state is required for promote_pattern operation"
                raise ValueError(msg)

            # Convert string to enum
            if isinstance(to_state_str, str):
                to_state = EnumPatternState(to_state_str.lower())
            elif isinstance(to_state_str, EnumPatternState):
                to_state = to_state_str
            else:
                msg = f"Invalid to_state type: {type(to_state_str)}"
                raise ValueError(msg)

            reason = input_data.get("reason")
            if reason is None:
                msg = "reason is required for promote_pattern operation"
                raise ValueError(msg)

            # Extract optional fields
            metrics_data = input_data.get("metrics_snapshot")
            metrics_snapshot = (
                ModelPatternMetricsSnapshot.model_validate(metrics_data)
                if metrics_data is not None
                else None
            )

            correlation_id_str = input_data.get("correlation_id")
            correlation_id = (
                UUID(correlation_id_str)
                if isinstance(correlation_id_str, str)
                else correlation_id_str
            )

            # Guard: Ensure state manager is initialized
            if self._state_manager is None:
                logger.error(
                    "State manager not initialized",
                    extra={"error_code": ERROR_CODE_PATSTOR_002},
                )
                return StorageOperationResult(
                    operation=OPERATION_PROMOTE_PATTERN,
                    success=False,
                    error_code=ERROR_CODE_PATSTOR_002,
                    error_message="State manager not initialized",
                )

            # Call the handler (returns structured result, not exceptions)
            promote_result: PromotePatternResult = await handle_promote_pattern(
                pattern_id=pattern_id,
                to_state=to_state,
                reason=reason,
                metrics_snapshot=metrics_snapshot,
                state_manager=self._state_manager,
                actor=input_data.get("actor", DEFAULT_ACTOR),
                correlation_id=correlation_id,
                domain=input_data.get("domain"),
                signature_hash=input_data.get("signature_hash"),
                metadata=input_data.get("metadata"),
                conn=conn,
            )

            if not promote_result.success:
                logger.warning(
                    "Promote pattern failed",
                    extra={
                        "error": promote_result.error_message,
                        "error_code": promote_result.error_code,
                        "pattern_id": str(promote_result.pattern_id),
                        "from_state": promote_result.from_state.value
                        if promote_result.from_state
                        else None,
                        "to_state": promote_result.to_state.value
                        if promote_result.to_state
                        else None,
                    },
                )
                return StorageOperationResult(
                    operation=OPERATION_PROMOTE_PATTERN,
                    success=False,
                    error_code=promote_result.error_code,
                    error_message=promote_result.error_message,
                )

            promoted_event = promote_result.event
            if promoted_event is None:
                raise RuntimeError(
                    f"Invariant violation: promote succeeded but event is None "
                    f"(pattern_id={pattern_id})"
                )

            logger.info(
                "Promote pattern operation completed",
                extra={
                    "pattern_id": str(promoted_event.pattern_id),
                    "from_state": promoted_event.from_state.value
                    if promoted_event.from_state
                    else None,
                    "to_state": promoted_event.to_state.value,
                },
            )

            return StorageOperationResult(
                operation=OPERATION_PROMOTE_PATTERN,
                success=True,
                promoted_event=promoted_event,
            )

        except ValueError as e:
            _corr_id = input_data.get("correlation_id")
            _pat_id = input_data.get("pattern_id")
            logger.warning(
                "Promote pattern validation failed",
                extra={
                    "error": str(e),
                    "correlation_id": str(_corr_id) if _corr_id is not None else None,
                    "pattern_id": str(_pat_id) if _pat_id is not None else None,
                },
            )
            return StorageOperationResult(
                operation=OPERATION_PROMOTE_PATTERN,
                success=False,
                error_code=ERROR_CODE_VALIDATION_ERROR,
                error_message=str(e),
            )


# =============================================================================
# Standalone Entry Point (Contract Reference)
# =============================================================================


async def route_storage_operation(
    operation: str,
    input_data: dict[
        str, Any
    ],  # any-ok: dynamic dispatch data, values are typed at call site
    *,
    pattern_store: ProtocolPatternStore,
    state_manager: ProtocolPatternStateManager,
    conn: AsyncConnection[Any],  # any-ok: psycopg AsyncConnection row factory type
) -> dict[str, object]:
    """Entry point for contract-driven handler routing.

    This function is referenced by contract.yaml handler_routing.entry_point
    and provides the main entry point for pattern storage operations.

    The function routes to the appropriate handler based on operation type:
        - store_pattern -> handle_store_pattern
        - promote_pattern -> handle_promote_pattern
        - default -> handle_store_pattern

    Args:
        operation: The operation to perform. Valid values:
            - "store_pattern": Persist a new pattern to storage
            - "promote_pattern": Promote pattern state (candidate->provisional->validated)
        input_data: Dictionary containing operation-specific input fields.
            For store_pattern: ModelPatternStorageInput fields
            For promote_pattern: pattern_id, to_state, reason, etc.
        pattern_store: Pattern store for storage operations.
        state_manager: State manager for promotion operations.
        conn: Database connection for transaction control. All operations
            use this connection for atomic idempotency + storage.

    Returns:
        Dictionary containing operation result with fields:
            - operation: The operation that was performed
            - success: Whether the operation succeeded
            - event_type: "pattern_stored" or "pattern_promoted"
            - event: Serialized event data
            - error_message: Error message if failed

    Example:
        >>> # Store a pattern
        >>> result = await route_storage_operation(
        ...     operation="store_pattern",
        ...     input_data={
        ...         "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
        ...         "signature": "def.*return.*None",
        ...         "signature_hash": "abc123",
        ...         "domain": "code_patterns",
        ...         "confidence": 0.85,
        ...     },
        ...     pattern_store=store_impl,
        ... )
        >>> result["success"]
        True
        >>> result["event_type"]
        'pattern_stored'

        >>> # Promote a pattern
        >>> result = await route_storage_operation(
        ...     operation="promote_pattern",
        ...     input_data={
        ...         "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
        ...         "to_state": "provisional",
        ...         "reason": "Pattern met verification criteria",
        ...     },
        ...     pattern_store=store_impl,
        ...     state_manager=manager_impl,
        ... )
        >>> result["success"]
        True
        >>> result["event_type"]
        'pattern_promoted'

        >>> # Transactional operation with shared connection
        >>> async with pool.connection() as conn:
        ...     result = await route_storage_operation(
        ...         operation="store_pattern",
        ...         input_data={...},
        ...         pattern_store=store_impl,
        ...         conn=conn,
        ...     )
    """
    logger.debug(
        "route_storage_operation called",
        extra={
            "operation": operation,
        },
    )

    # Create router with provided dependencies (all required)
    router = PatternStorageRouter(
        pattern_store=pattern_store,
        state_manager=state_manager,
    )

    # Route operation and return serialized result
    result = await router.route(operation=operation, input_data=input_data, conn=conn)
    return result.to_dict()


__all__ = [
    "ERROR_CODE_GOVERNANCE_VIOLATION",
    "ERROR_CODE_INVALID_TRANSITION",
    "ERROR_CODE_PATTERN_NOT_FOUND",
    "ERROR_CODE_STORAGE_ERROR",
    "ERROR_CODE_PATSTOR_002",
    "ERROR_CODE_PATSTOR_003",
    "ERROR_CODE_VALIDATION_ERROR",
    "OPERATION_PROMOTE_PATTERN",
    "OPERATION_STORE_PATTERN",
    "PatternStorageRouter",
    "StorageOperationResult",
    "route_storage_operation",
]
