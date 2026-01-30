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

from omniintelligence.nodes.pattern_storage_effect.handlers.handler_pattern_storage import (
    OPERATION_PROMOTE_PATTERN,
    OPERATION_STORE_PATTERN,
    PatternStorageRouter,
    StorageOperationResult,
    route_storage_operation,
)
from omniintelligence.nodes.pattern_storage_effect.handlers.handler_promote_pattern import (
    DEFAULT_ACTOR,
    ModelStateTransition,
    PatternNotFoundError,
    PatternStateTransitionError,
    ProtocolPatternStateManager,
    VALID_TRANSITIONS,
    get_valid_targets,
    handle_promote_pattern,
    is_valid_transition,
)
from omniintelligence.nodes.pattern_storage_effect.handlers.handler_store_pattern import (
    GovernanceResult,
    GovernanceViolation,
    PatternStateTransition,
    ProtocolPatternStore,
    StorePatternResult,
    create_initial_storage_transition,
    handle_store_pattern,
    validate_governance,
)

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
    # Router
    "PatternStorageRouter",
    # Protocols
    "ProtocolPatternStateManager",
    "ProtocolPatternStore",
    "StorageOperationResult",
    "StorePatternResult",
    # Functions (store)
    "create_initial_storage_transition",
    # Functions (promote)
    "get_valid_targets",
    "handle_promote_pattern",
    "handle_store_pattern",
    "is_valid_transition",
    # Functions (router - entry point)
    "route_storage_operation",
    "validate_governance",
]
