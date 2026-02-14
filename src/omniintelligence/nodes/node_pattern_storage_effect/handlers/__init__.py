# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handlers for Pattern Storage Effect node.

This module exports all handlers used by the NodePatternStorageEffect,
including pattern storage with governance enforcement and state promotion
with audit trail functionality.

Entry Point:
    - route_storage_operation: Contract-driven operation router (entry point)
    - PatternStorageRouter: Class-based router for dependency injection

Handlers:
    - handle_store_pattern: Store learned patterns with governance enforcement
    - handle_promote_pattern: Promote pattern state with audit trail
    - validate_governance: Validate inputs against governance invariants
    - validate_promotion_transition: Pure validation for state transitions (no DB required)
    - is_valid_transition: Validate state transitions
    - get_valid_targets: Get valid target states

Protocols:
    - ProtocolPatternStore: Interface for pattern storage backends
    - ProtocolPatternStateManager: Interface for state management backends

Models:
    - GovernanceResult: Result of governance validation
    - GovernanceViolation: Single governance rule violation
    - PatternStateTransition: Audit record for state transitions (store)
    - ModelStateTransition: Audit record for state transitions (promote)
    - TransitionValidationResult: Result of pure transition validation (canonical)
    - PromotionValidationResult: Backwards compatibility alias for TransitionValidationResult
    - StorePatternResult: Internal result from store operation
    - StorageOperationResult: Result wrapper for router dispatch

Exceptions:
    - PatternStateTransitionError: Invalid state transition
    - PatternNotFoundError: Pattern not found

Constants:
    - VALID_TRANSITIONS: Valid state transition map
    - DEFAULT_ACTOR: Default actor for transitions
    - OPERATION_STORE_PATTERN: Operation constant for store
    - OPERATION_PROMOTE_PATTERN: Operation constant for promote

Governance Invariants:
    - Confidence >= 0.5 (MIN_CONFIDENCE)
    - UNIQUE(domain, signature_hash, version)
    - UNIQUE(domain, signature_hash) WHERE is_current = true
    - Idempotent storage via (event_id, signature_hash)

Reference:
    - OMN-1668: Pattern storage effect node implementation
"""

# =============================================================================
# Import Error Handling
# =============================================================================
# Wrap imports with contextual error messages to help diagnose dependency issues.
# This is particularly important for complex node packages with multiple handlers.

try:
    from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_pattern_storage import (
        OPERATION_PROMOTE_PATTERN,
        OPERATION_STORE_PATTERN,
        PatternStorageRouter,
        StorageOperationResult,
        route_storage_operation,
    )
except ImportError as e:
    raise ImportError(
        f"Failed to import handler_pattern_storage: {e}. "
        "This handler provides the main routing logic for pattern storage operations. "
        "Ensure all dependencies (models, constants) are properly installed."
    ) from e

# State transition constants and validation (canonical source: constants.py)
try:
    from omniintelligence.nodes.node_pattern_storage_effect.constants import (
        VALID_TRANSITIONS,
        TransitionValidationResult,
        get_valid_targets,
        is_valid_transition,
        validate_promotion_transition,
    )
except ImportError as e:
    raise ImportError(
        f"Failed to import constants: {e}. "
        "The constants module defines state transition rules (VALID_TRANSITIONS). "
        "This is a core dependency required for state validation."
    ) from e

try:
    from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_promote_pattern import (
        DEFAULT_ACTOR,
        ModelStateTransition,
        PatternNotFoundError,
        PatternStateTransitionError,
        PromotePatternResult,
        ProtocolPatternStateManager,
        handle_promote_pattern,
    )
except ImportError as e:
    raise ImportError(
        f"Failed to import handler_promote_pattern: {e}. "
        "This handler provides pattern state promotion with audit trail. "
        "Ensure the models module (EnumPatternState, ModelPatternPromotedEvent) is available."
    ) from e

# Backwards compatibility alias (deprecated, use TransitionValidationResult)
PromotionValidationResult = TransitionValidationResult

try:
    from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern import (
        GovernanceResult,
        GovernanceViolation,
        PatternStateTransition,
        ProtocolPatternStore,
        StorePatternResult,
        create_initial_storage_transition,
        handle_store_pattern,
        validate_governance,
    )
except ImportError as e:
    raise ImportError(
        f"Failed to import handler_store_pattern: {e}. "
        "This handler provides pattern storage with governance enforcement. "
        "Ensure the models module (ModelPatternStorageInput, ModelPatternStoredEvent) is available."
    ) from e

try:
    from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_consume_discovered import (
        handle_consume_discovered,
    )
except ImportError as e:
    raise ImportError(
        f"Failed to import handler_consume_discovered: {e}. "
        "This handler consumes pattern.discovered events from external systems. "
        "Ensure ModelPatternDiscoveredEvent is available."
    ) from e

__all__ = [
    # Constants
    "DEFAULT_ACTOR",
    "OPERATION_PROMOTE_PATTERN",
    "OPERATION_STORE_PATTERN",
    "VALID_TRANSITIONS",
    # Governance (store)
    "GovernanceResult",
    "GovernanceViolation",
    # Models
    "ModelStateTransition",
    # Exceptions
    "PatternNotFoundError",
    "PatternStateTransition",
    "PatternStateTransitionError",
    # Result types (promote)
    "PromotePatternResult",
    # Router
    "PatternStorageRouter",
    "PromotionValidationResult",  # Backwards compat alias for TransitionValidationResult
    # Protocols
    "ProtocolPatternStateManager",
    "ProtocolPatternStore",
    "StorageOperationResult",
    "StorePatternResult",
    # Validation result types (TransitionValidationResult is canonical)
    "TransitionValidationResult",
    # Functions (store)
    "create_initial_storage_transition",
    # Functions (consume discovered)
    "handle_consume_discovered",
    # Functions (promote)
    "get_valid_targets",
    "handle_promote_pattern",
    "handle_store_pattern",
    "is_valid_transition",
    # Functions (router - entry point)
    "route_storage_operation",
    "validate_governance",
    "validate_promotion_transition",
]
