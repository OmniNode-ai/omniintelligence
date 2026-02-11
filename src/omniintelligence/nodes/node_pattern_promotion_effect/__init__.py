# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Promotion Effect node - OMN-1680, OMN-1757.

This node handles automatic promotion of provisional patterns to validated
status based on rolling window success metrics. Supports dry_run mode for
previewing promotions without committing changes.

Key Components:
    - NodePatternPromotionEffect: Pure declarative effect node (thin shell)
    - ModelPromotionCheckRequest: Input request with thresholds and dry_run flag
    - ModelPromotionCheckResult: Aggregated result with promotion outcomes
    - ModelPromotionResult: Individual pattern promotion result
    - ModelGateSnapshot: Gate values at promotion decision time
    - check_and_promote_patterns: Main handler for batch promotion
    - promote_pattern: Single pattern promotion handler
    - meets_promotion_criteria: Pure function for criteria check

Promotion Gates (all must pass):
    1. Injection Count Gate: injection_count_rolling_20 >= 5
    2. Success Rate Gate: success_rate >= 0.6 (60%)
    3. Failure Streak Gate: failure_streak < 3
    4. Disabled Gate: Pattern not in disabled_patterns_current

ONEX Invariant:
    Kafka is OPTIONAL per "Effect nodes must never block on Kafka".
    When producer is unavailable, promotions proceed via direct
    database UPDATE (fallback mode).

Usage (Declarative Pattern):
    from omniintelligence.nodes.node_pattern_promotion_effect import (
        NodePatternPromotionEffect,
        check_and_promote_patterns,
        promote_pattern,
        meets_promotion_criteria,
        ModelPromotionCheckRequest,
    )

    # Create node via container (pure declarative shell)
    from omnibase_core.models.container import ModelONEXContainer
    container = ModelONEXContainer()
    node = NodePatternPromotionEffect(container)

    # Handlers are called directly with their dependencies
    result = await check_and_promote_patterns(
        repository=db_conn,
        producer=kafka_producer,
        dry_run=False,
        correlation_id=correlation_id,
        topic_env_prefix="dev",
    )

    # For event-driven execution, use RuntimeHostProcess
    # which reads handler_routing from contract.yaml

Reference:
    - OMN-1680: Auto-promote logic for patterns
    - OMN-1757: Refactor to declarative pattern
    - OMN-1805: Event-driven lifecycle transitions
"""

# Handler functions
from omniintelligence.nodes.node_pattern_promotion_effect.handlers import (
    MAX_FAILURE_STREAK,
    MIN_INJECTION_COUNT,
    MIN_SUCCESS_RATE,
    build_gate_snapshot,
    calculate_success_rate,
    check_and_promote_patterns,
    meets_promotion_criteria,
    promote_pattern,
)

# Introspection support
from omniintelligence.nodes.node_pattern_promotion_effect.introspection import (
    PatternPromotionErrorCode,
    PatternPromotionIntrospection,
    PatternPromotionMetadataLoader,
    get_introspection_response,
)

# Models
from omniintelligence.nodes.node_pattern_promotion_effect.models import (
    ModelGateSnapshot,
    ModelPatternPromotedEvent,
    ModelPromotionCheckRequest,
    ModelPromotionCheckResult,
    ModelPromotionResult,
)

# Node class (pure declarative shell)
from omniintelligence.nodes.node_pattern_promotion_effect.node import (
    NodePatternPromotionEffect,
)

__all__ = [
    # Constants
    "MAX_FAILURE_STREAK",
    "MIN_INJECTION_COUNT",
    "MIN_SUCCESS_RATE",
    # Models
    "ModelGateSnapshot",
    "ModelPatternPromotedEvent",
    "ModelPromotionCheckRequest",
    "ModelPromotionCheckResult",
    "ModelPromotionResult",
    # Node
    "NodePatternPromotionEffect",
    # Introspection
    "PatternPromotionErrorCode",
    "PatternPromotionIntrospection",
    "PatternPromotionMetadataLoader",
    # Handlers
    "build_gate_snapshot",
    "calculate_success_rate",
    "check_and_promote_patterns",
    "get_introspection_response",
    "meets_promotion_criteria",
    "promote_pattern",
]
