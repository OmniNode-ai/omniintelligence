# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Policy lifecycle transition logic — table-driven, pure functions.

This module implements the lifecycle state machine transitions:
    CANDIDATE → VALIDATED when N runs with positive signal
    VALIDATED → PROMOTED  when statistical significance threshold met
    PROMOTED  → DEPRECATED when reliability falls below hard floor

Constraints:
    - NO scoring logic — only applies pre-computed reward deltas
    - Table-driven from ModelTransitionThresholds — no hardcoded if/else chains
    - Transitions are evaluated in priority order (degradation before promotion)

The public functions are pure: identical inputs → identical outputs.
All I/O (DB reads/writes, Kafka publishing) is handled by the node.

Ticket: OMN-2557
"""

from __future__ import annotations

import logging

from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_lifecycle_state import (
    EnumPolicyLifecycleState,
)
from omniintelligence.nodes.node_policy_state_reducer.models.model_transition_thresholds import (
    ModelTransitionThresholds,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifecycle state transition table
# ---------------------------------------------------------------------------
# States in priority order for evaluation (degradation always checked first)
_DEGRADATION_STATES = frozenset(
    {EnumPolicyLifecycleState.PROMOTED, EnumPolicyLifecycleState.VALIDATED}
)


def compute_next_lifecycle_state(
    current_state: EnumPolicyLifecycleState,
    reliability_0_1: float,
    run_count: int,
    positive_signal_ratio: float,
    thresholds: ModelTransitionThresholds,
) -> EnumPolicyLifecycleState:
    """Compute the next lifecycle state from current state and metrics.

    Evaluates transitions in priority order:
      1. Degradation: PROMOTED/VALIDATED → DEPRECATED if reliability < floor
      2. Promotion: VALIDATED → PROMOTED if significance threshold met
      3. Validation: CANDIDATE → VALIDATED if N positive runs
      4. No change otherwise

    Args:
        current_state:        The current lifecycle state.
        reliability_0_1:      Current reliability score [0.0, 1.0].
        run_count:            Total number of runs observed.
        positive_signal_ratio: Ratio of positive-signal runs [0.0, 1.0].
        thresholds:           Transition thresholds from ObjectiveSpec.

    Returns:
        The next lifecycle state (may be same as current if no transition).
    """
    # DEPRECATED is a terminal state — no further transitions
    if current_state == EnumPolicyLifecycleState.DEPRECATED:
        return EnumPolicyLifecycleState.DEPRECATED

    # Priority 1: Degradation check (reliability floor breach)
    if current_state in _DEGRADATION_STATES:
        if reliability_0_1 < thresholds.reliability_floor:
            logger.info(
                "Lifecycle degradation: %s → DEPRECATED "
                "(reliability=%.3f < floor=%.3f)",
                current_state.value,
                reliability_0_1,
                thresholds.reliability_floor,
            )
            return EnumPolicyLifecycleState.DEPRECATED

    # Priority 2: VALIDATED → PROMOTED (statistical significance)
    if current_state == EnumPolicyLifecycleState.VALIDATED:
        if (
            run_count >= thresholds.promoted_min_runs
            and reliability_0_1 >= thresholds.promoted_significance_threshold
        ):
            logger.info(
                "Lifecycle promotion: VALIDATED → PROMOTED "
                "(run_count=%d >= %d, reliability=%.3f >= %.3f)",
                run_count,
                thresholds.promoted_min_runs,
                reliability_0_1,
                thresholds.promoted_significance_threshold,
            )
            return EnumPolicyLifecycleState.PROMOTED

    # Priority 3: CANDIDATE → VALIDATED (N positive runs)
    if current_state == EnumPolicyLifecycleState.CANDIDATE:
        if (
            run_count >= thresholds.validated_min_runs
            and positive_signal_ratio >= thresholds.validated_positive_signal_floor
        ):
            logger.info(
                "Lifecycle validation: CANDIDATE → VALIDATED "
                "(run_count=%d >= %d, signal_ratio=%.3f >= %.3f)",
                run_count,
                thresholds.validated_min_runs,
                positive_signal_ratio,
                thresholds.validated_positive_signal_floor,
            )
            return EnumPolicyLifecycleState.VALIDATED

    return current_state


def apply_reward_delta(
    current_reliability: float,
    reward_delta: float,
    run_count: int,
    failure_count: int,
) -> tuple[float, int, int]:
    """Apply a reward delta and update run/failure counts.

    Uses an exponential moving average for reliability updates.
    Positive delta improves reliability; negative delta degrades it.

    Args:
        current_reliability: Current reliability score [0.0, 1.0].
        reward_delta:        Signed delta [-1.0, +1.0].
        run_count:           Current total run count.
        failure_count:       Current total failure count.

    Returns:
        Tuple of (new_reliability, new_run_count, new_failure_count).
    """
    new_run_count = run_count + 1
    new_failure_count = failure_count + (1 if reward_delta < 0 else 0)

    # EMA-style update: weight recent observations more heavily
    alpha = 1.0 / max(new_run_count, 1)  # decaying learning rate
    new_reliability = current_reliability + alpha * (reward_delta - current_reliability)

    # Clamp to [0.0, 1.0]
    new_reliability = max(0.0, min(1.0, new_reliability))

    return new_reliability, new_run_count, new_failure_count


def should_blacklist(
    reliability_0_1: float,
    thresholds: ModelTransitionThresholds,
    already_blacklisted: bool,
) -> bool:
    """Determine whether a tool should be auto-blacklisted.

    Blacklisting fires when reliability falls below the blacklist_floor.
    Already-blacklisted tools are not re-blacklisted (idempotent).

    Args:
        reliability_0_1:      Current reliability score.
        thresholds:           Transition thresholds.
        already_blacklisted:  Whether the tool is already blacklisted.

    Returns:
        True if the tool should be blacklisted in this update.
    """
    if already_blacklisted:
        return False
    return reliability_0_1 < thresholds.blacklist_floor


__all__ = [
    "apply_reward_delta",
    "compute_next_lifecycle_state",
    "should_blacklist",
]
