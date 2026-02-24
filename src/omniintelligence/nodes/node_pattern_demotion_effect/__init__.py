# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Pattern Demotion Effect node.

This module exports the pattern demotion effect node and its supporting
models, handlers, and protocols. The node demotes validated patterns to
deprecated status based on failure metrics and demotion gates.

Key Components:
    - NodePatternDemotionEffect: Pure declarative effect node (thin shell)
    - ModelDemotionCheckRequest: Input for demotion check operations
    - ModelDemotionCheckResult: Aggregated output with demotion outcomes
    - ModelDemotionResult: Individual pattern demotion result
    - ModelDemotionGateSnapshot: Gate values at evaluation time
    - ModelEffectiveThresholds: Effective thresholds used for demotion
    - ProtocolPatternRepository: Interface for database operations
    - ProtocolKafkaPublisher: Interface for Kafka event emission

Demotion Gates (evaluated in order):
    1. Manual Disable (HARD TRIGGER - bypasses cooldown)
    2. Failure Streak >= threshold (5 consecutive failures)
    3. Low Success Rate < threshold (40% with sufficient data)

Anti-Oscillation:
    - Cooldown period prevents demotion within 24 hours of promotion
    - Manual disable bypasses cooldown as hard override

Usage (Declarative Pattern):
    from omniintelligence.nodes.node_pattern_demotion_effect import (
        NodePatternDemotionEffect,
        check_and_demote_patterns,
        demote_pattern,
        ModelDemotionCheckRequest,
    )

    # Create node via container (pure declarative shell)
    from omnibase_core.models.container import ModelONEXContainer
    container = ModelONEXContainer()
    node = NodePatternDemotionEffect(container)

    # Handlers are called directly with their dependencies
    result = await check_and_demote_patterns(
        repository=db_connection,
        producer=kafka_producer,
        request=ModelDemotionCheckRequest(dry_run=False),
    )

    # For event-driven execution, use RuntimeHostProcess
    # which reads handler_routing from contract.yaml

Reference:
    - OMN-1681: Auto-demote logic for patterns failing quality thresholds
    - OMN-1805: Reducer-based status transitions
    - OMN-1757: Refactor to declarative pattern
"""

# Handler functions (for direct invocation)
from omniintelligence.nodes.node_pattern_demotion_effect.handlers import (
    # Constants
    DEFAULT_COOLDOWN_HOURS,
    FAILURE_STREAK_THRESHOLD_MAX,
    FAILURE_STREAK_THRESHOLD_MIN,
    MAX_SUCCESS_RATE_FOR_DEMOTION,
    MIN_FAILURE_STREAK_FOR_DEMOTION,
    MIN_INJECTION_COUNT_FOR_DEMOTION,
    SUCCESS_RATE_THRESHOLD_MAX,
    SUCCESS_RATE_THRESHOLD_MIN,
    # Protocols
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
    # Pure functions
    build_effective_thresholds,
    build_gate_snapshot,
    calculate_hours_since_promotion,
    calculate_success_rate,
    # Handler functions
    check_and_demote_patterns,
    demote_pattern,
    get_demotion_reason,
    is_cooldown_active,
    validate_threshold_overrides,
)

# Models
from omniintelligence.nodes.node_pattern_demotion_effect.models import (
    ModelDemotionCheckRequest,
    ModelDemotionCheckResult,
    ModelDemotionGateSnapshot,
    ModelDemotionResult,
    ModelEffectiveThresholds,
    ModelPatternDeprecatedEvent,
)

# Node (pure declarative shell)
from omniintelligence.nodes.node_pattern_demotion_effect.node import (
    NodePatternDemotionEffect,
)

__all__ = [
    "DEFAULT_COOLDOWN_HOURS",
    "FAILURE_STREAK_THRESHOLD_MAX",
    "FAILURE_STREAK_THRESHOLD_MIN",
    "MAX_SUCCESS_RATE_FOR_DEMOTION",
    "MIN_FAILURE_STREAK_FOR_DEMOTION",
    "MIN_INJECTION_COUNT_FOR_DEMOTION",
    "SUCCESS_RATE_THRESHOLD_MAX",
    "SUCCESS_RATE_THRESHOLD_MIN",
    "ModelDemotionCheckRequest",
    "ModelDemotionCheckResult",
    "ModelDemotionGateSnapshot",
    "ModelDemotionResult",
    "ModelEffectiveThresholds",
    "ModelPatternDeprecatedEvent",
    "NodePatternDemotionEffect",
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    "build_effective_thresholds",
    "build_gate_snapshot",
    "calculate_hours_since_promotion",
    "calculate_success_rate",
    "check_and_demote_patterns",
    "demote_pattern",
    "get_demotion_reason",
    "is_cooldown_active",
    "validate_threshold_overrides",
]
