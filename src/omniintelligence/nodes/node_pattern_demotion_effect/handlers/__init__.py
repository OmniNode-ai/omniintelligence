# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handlers for pattern_demotion_effect node.

This module exports all handler functions and constants for the pattern
demotion effect node, which demotes validated patterns to deprecated status
based on rolling window failure metrics, cooldown periods, and manual disables.

The demotion logic follows a "don't demote on noise" philosophy, requiring
stronger evidence of failure than promotion requires evidence of success.
This asymmetry prevents patterns from oscillating between states.

See handler_demotion.py for detailed documentation of:
    - Demotion gates and their thresholds
    - Cooldown mechanism to prevent oscillation
    - Manual disable as hard override
    - Kafka optionality and implications
"""

from omniintelligence.nodes.node_pattern_demotion_effect.handlers.handler_demotion import (
    # Constants
    DEFAULT_COOLDOWN_HOURS,
    FAILURE_STREAK_THRESHOLD_MAX,
    FAILURE_STREAK_THRESHOLD_MIN,
    MAX_SUCCESS_RATE_FOR_DEMOTION,
    MIN_FAILURE_STREAK_FOR_DEMOTION,
    MIN_INJECTION_COUNT_FOR_DEMOTION,
    SUCCESS_RATE_THRESHOLD_MAX,
    SUCCESS_RATE_THRESHOLD_MIN,
    # Type definitions
    DemotionPatternRecord,
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
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository

__all__ = [
    # Constants
    "DEFAULT_COOLDOWN_HOURS",
    "FAILURE_STREAK_THRESHOLD_MAX",
    "FAILURE_STREAK_THRESHOLD_MIN",
    "MAX_SUCCESS_RATE_FOR_DEMOTION",
    "MIN_FAILURE_STREAK_FOR_DEMOTION",
    "MIN_INJECTION_COUNT_FOR_DEMOTION",
    "SUCCESS_RATE_THRESHOLD_MAX",
    "SUCCESS_RATE_THRESHOLD_MIN",
    # Type definitions
    "DemotionPatternRecord",
    # Protocols
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    # Pure functions
    "build_effective_thresholds",
    "build_gate_snapshot",
    "calculate_hours_since_promotion",
    "calculate_success_rate",
    # Handler functions
    "check_and_demote_patterns",
    "demote_pattern",
    "get_demotion_reason",
    "is_cooldown_active",
    "validate_threshold_overrides",
]
