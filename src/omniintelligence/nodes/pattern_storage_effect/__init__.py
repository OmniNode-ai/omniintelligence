# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Storage Effect node.

This module exports the pattern storage effect node and its supporting
models, handlers, and protocols. The node persists learned patterns
with governance enforcement and state promotion capabilities.

Key Components:
    - NodePatternStorageEffect: Main effect node for pattern storage
    - ModelPatternStorageInput: Input from pattern-learned.v1 events
    - ModelPatternStoredEvent: Output for pattern-stored.v1 events
    - ModelPatternPromotedEvent: Output for pattern-promoted.v1 events
    - EnumPatternState: Pattern lifecycle states (candidate/provisional/validated)
    - ProtocolPatternStore: Interface for pattern storage backends
    - ProtocolPatternStateManager: Interface for state management backends
    - ContractLoader: Declarative contract loading and handler dispatch

Governance Invariants:
    - Confidence >= 0.5 (MIN_CONFIDENCE)
    - UNIQUE(domain, signature_hash, version)
    - UNIQUE(domain, signature_hash) WHERE is_current = true

State Transitions:
    - CANDIDATE -> PROVISIONAL: Pattern passes verification
    - PROVISIONAL -> VALIDATED: Pattern meets all validation criteria

Usage:
    from omniintelligence.nodes.pattern_storage_effect import (
        NodePatternStorageEffect,
        ModelPatternStorageInput,
        EnumPatternState,
    )

    # Create and wire the node
    node = NodePatternStorageEffect(container)
    node.set_pattern_store(pattern_store)
    node.set_state_manager(state_manager)

    # Store a pattern
    event = await node.store_pattern(input_data)

    # Promote a pattern
    event = await node.promote_pattern(
        pattern_id=uuid,
        to_state=EnumPatternState.PROVISIONAL,
        reason="Pattern met verification criteria",
    )

    # Use declarative contract loading
    from omniintelligence.nodes.pattern_storage_effect import (
        ContractLoader,
        get_contract_loader,
    )

    loader = get_contract_loader()
    handler = loader.resolve_handler("store_pattern")
    topics = loader.subscribe_topics

Reference:
    - OMN-1668: Pattern storage effect node implementation
"""

from omniintelligence.nodes.pattern_storage_effect.contract_loader import (
    ContractLoader,
    EventBusConfig,
    HandlerConfig,
    HandlerRouting,
    OperationHandler,
    clear_loader_cache,
    get_contract_loader,
)
from omniintelligence.nodes.pattern_storage_effect.handlers import (
    DEFAULT_ACTOR,
    GovernanceResult,
    GovernanceViolation,
    ModelStateTransition,
    PatternNotFoundError,
    PatternStateTransitionError,
    PatternStateTransition,
    ProtocolPatternStateManager,
    ProtocolPatternStore,
    StorePatternResult,
    VALID_TRANSITIONS,
    get_valid_targets,
    handle_promote_pattern,
    handle_store_pattern,
    is_valid_transition,
    validate_governance,
)
from omniintelligence.nodes.pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternMetricsSnapshot,
    ModelPatternPromotedEvent,
    ModelPatternStorageInput,
    ModelPatternStorageMetadata,
    ModelPatternStoredEvent,
    PatternStorageGovernance,
)
from omniintelligence.nodes.pattern_storage_effect.node import (
    NodePatternStorageEffect,
)

__all__ = [
    "DEFAULT_ACTOR",
    "VALID_TRANSITIONS",
    "ContractLoader",
    "EnumPatternState",
    "EventBusConfig",
    "GovernanceResult",
    "GovernanceViolation",
    "HandlerConfig",
    "HandlerRouting",
    "ModelPatternMetricsSnapshot",
    "ModelPatternPromotedEvent",
    "ModelPatternStorageInput",
    "ModelPatternStorageMetadata",
    "ModelPatternStoredEvent",
    "ModelStateTransition",
    "NodePatternStorageEffect",
    "OperationHandler",
    "PatternNotFoundError",
    "PatternStateTransition",
    "PatternStateTransitionError",
    "PatternStorageGovernance",
    "ProtocolPatternStateManager",
    "ProtocolPatternStore",
    "StorePatternResult",
    "clear_loader_cache",
    "get_contract_loader",
    "get_valid_targets",
    "handle_promote_pattern",
    "handle_store_pattern",
    "is_valid_transition",
    "validate_governance",
]
