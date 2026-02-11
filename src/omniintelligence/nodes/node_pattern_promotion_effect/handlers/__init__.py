"""Handlers for pattern_promotion_effect.

This module exports handler functions for the pattern promotion effect node,
which promotes patterns from provisional to validated status based on
rolling window metrics.

Handler Pattern:
    Each handler is an async function that:
    - Accepts a repository protocol for database operations
    - Evaluates patterns against promotion thresholds
    - Updates pattern status if criteria are met
    - Publishes promotion events to Kafka
    - Returns typed result models

Promotion Gates (all must pass):
    1. Injection Count Gate: injection_count_rolling_20 >= 5
    2. Success Rate Gate: success_rate >= 0.6 (60%)
    3. Failure Streak Gate: failure_streak < 3
    4. Disabled Gate: Pattern not in disabled_patterns_current

Usage:
    from omniintelligence.nodes.node_pattern_promotion_effect.handlers import (
        ProtocolPatternRepository,
        ProtocolKafkaPublisher,
        check_and_promote_patterns,
        meets_promotion_criteria,
    )

    # Check and promote eligible patterns
    result = await check_and_promote_patterns(
        repository=db_connection,
        producer=kafka_producer,
        dry_run=False,
    )

    # Pure criteria check (no I/O)
    is_eligible = meets_promotion_criteria(pattern_record)

Reference:
    - OMN-1680: Auto-promote logic for patterns
    - OMN-1678: Rolling window metrics (dependency)
    - OMN-1679: Contribution heuristics (dependency)
"""

from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote import (
    AutoPromoteCheckResult,
    AutoPromoteResult,
    handle_auto_promote_check,
    meets_candidate_to_provisional_criteria,
    meets_provisional_to_validated_criteria,
)
from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_promotion import (
    MAX_FAILURE_STREAK,
    MIN_INJECTION_COUNT,
    MIN_SUCCESS_RATE,
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
    build_gate_snapshot,
    calculate_success_rate,
    check_and_promote_patterns,
    meets_promotion_criteria,
    promote_pattern,
)

__all__: list[str] = [
    "AutoPromoteCheckResult",
    "AutoPromoteResult",
    "MAX_FAILURE_STREAK",
    "MIN_INJECTION_COUNT",
    "MIN_SUCCESS_RATE",
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    "build_gate_snapshot",
    "calculate_success_rate",
    "handle_auto_promote_check",
    "check_and_promote_patterns",
    "meets_candidate_to_provisional_criteria",
    "meets_promotion_criteria",
    "meets_provisional_to_validated_criteria",
    "promote_pattern",
]
