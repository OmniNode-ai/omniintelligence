# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Policy lifecycle transition logic — table-driven, pure handlers.

Lifecycle state machine transitions:
    CANDIDATE → VALIDATED when N runs with positive signal
    VALIDATED → PROMOTED  when statistical significance threshold met
    PROMOTED  → DEPRECATED when reliability falls below hard floor

Constraints:
    - NO scoring logic — only applies pre-computed reward deltas
    - Table-driven from ModelTransitionThresholds — no hardcoded if/else chains
    - Transitions are evaluated in priority order (degradation before promotion)

The handlers are pure: identical inputs → identical outputs.
All I/O (DB reads/writes, Kafka publishing) is handled by the node.

Ticket: OMN-2557
"""

from __future__ import annotations

import logging

from omniintelligence.nodes.node_policy_state_reducer.models import (
    ModelApplyRewardDeltaRequest,
    ModelApplyRewardDeltaResponse,
    ModelComputeNextLifecycleStateRequest,
    ModelComputeNextLifecycleStateResponse,
    ModelShouldBlacklistRequest,
    ModelShouldBlacklistResponse,
)
from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_lifecycle_state import (
    EnumPolicyLifecycleState,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifecycle state transition table
# ---------------------------------------------------------------------------
# States in priority order for evaluation (degradation always checked first)
_DEGRADATION_STATES = frozenset(
    {EnumPolicyLifecycleState.PROMOTED, EnumPolicyLifecycleState.VALIDATED}
)


class HandlerComputeNextLifecycleState:
    """Handle compute next lifecycle state requests."""

    def handle(
        self, request: ModelComputeNextLifecycleStateRequest
    ) -> ModelComputeNextLifecycleStateResponse:
        """Compute the next lifecycle state from current state and metrics.

        Evaluates transitions in priority order:
          1. Degradation: PROMOTED/VALIDATED → DEPRECATED if reliability < floor
          2. Promotion: VALIDATED → PROMOTED if significance threshold met
          3. Validation: CANDIDATE → VALIDATED if N positive runs
          4. No change otherwise
        """

        # DEPRECATED is a terminal state — no further transitions
        if request.current_state == EnumPolicyLifecycleState.DEPRECATED:
            return ModelComputeNextLifecycleStateResponse(
                lifecycle_state=EnumPolicyLifecycleState.DEPRECATED
            )

        # Priority 1: Degradation check (reliability floor breach)
        if request.current_state in _DEGRADATION_STATES:
            if request.reliability_0_1 < request.thresholds.reliability_floor:
                logger.info(
                    "Lifecycle degradation: %s → DEPRECATED "
                    "(reliability=%.3f < floor=%.3f)",
                    request.current_state.value,
                    request.reliability_0_1,
                    request.thresholds.reliability_floor,
                )
                return ModelComputeNextLifecycleStateResponse(
                    lifecycle_state=EnumPolicyLifecycleState.DEPRECATED
                )

        # Priority 2: VALIDATED → PROMOTED (statistical significance)
        if request.current_state == EnumPolicyLifecycleState.VALIDATED:
            if (
                request.run_count >= request.thresholds.promoted_min_runs
                and request.reliability_0_1
                >= request.thresholds.promoted_significance_threshold
            ):
                logger.info(
                    "Lifecycle promotion: VALIDATED → PROMOTED "
                    "(run_count=%d >= %d, reliability=%.3f >= %.3f)",
                    request.run_count,
                    request.thresholds.promoted_min_runs,
                    request.reliability_0_1,
                    request.thresholds.promoted_significance_threshold,
                )
                return ModelComputeNextLifecycleStateResponse(
                    lifecycle_state=EnumPolicyLifecycleState.PROMOTED
                )

        # Priority 3: CANDIDATE → VALIDATED (N positive runs)
        if request.current_state == EnumPolicyLifecycleState.CANDIDATE:
            if (
                request.run_count >= request.thresholds.validated_min_runs
                and request.positive_signal_ratio
                >= request.thresholds.validated_positive_signal_floor
            ):
                logger.info(
                    "Lifecycle validation: CANDIDATE → VALIDATED "
                    "(run_count=%d >= %d, signal_ratio=%.3f >= %.3f)",
                    request.run_count,
                    request.thresholds.validated_min_runs,
                    request.positive_signal_ratio,
                    request.thresholds.validated_positive_signal_floor,
                )
                return ModelComputeNextLifecycleStateResponse(
                    lifecycle_state=EnumPolicyLifecycleState.VALIDATED
                )

        return ModelComputeNextLifecycleStateResponse(
            lifecycle_state=request.current_state
        )


class HandlerApplyRewardDelta:
    """Handle apply reward delta requests."""

    def handle(
        self, request: ModelApplyRewardDeltaRequest
    ) -> ModelApplyRewardDeltaResponse:
        """Apply a reward delta and update run/failure counts.

        Uses an exponential moving average for reliability updates.
        Positive delta improves reliability; negative delta degrades it.
        """

        new_run_count = request.run_count + 1
        new_failure_count = request.failure_count + (
            1 if request.reward_delta < 0 else 0
        )

        # EMA-style update: weight recent observations more heavily
        alpha = 1.0 / max(new_run_count, 1)  # decaying learning rate
        new_reliability = request.current_reliability + alpha * (
            request.reward_delta - request.current_reliability
        )

        # Clamp to [0.0, 1.0]
        new_reliability = max(0.0, min(1.0, new_reliability))

        return ModelApplyRewardDeltaResponse(
            new_reliability=new_reliability,
            new_run_count=new_run_count,
            new_failure_count=new_failure_count,
        )


class HandlerShouldBlacklist:
    """Handle should blacklist requests."""

    def handle(
        self, request: ModelShouldBlacklistRequest
    ) -> ModelShouldBlacklistResponse:
        """Determine whether a tool should be auto-blacklisted.

        Blacklisting fires when reliability falls below the blacklist_floor.
        Already-blacklisted tools are not re-blacklisted (idempotent).
        """

        if request.already_blacklisted:
            return ModelShouldBlacklistResponse(should_blacklist=False)
        return ModelShouldBlacklistResponse(
            should_blacklist=request.reliability_0_1
            < request.thresholds.blacklist_floor
        )


__all__ = [
    "HandlerComputeNextLifecycleState",
    "HandlerApplyRewardDelta",
    "HandlerShouldBlacklist",
]
