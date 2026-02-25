# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""NodeObjectiveABFrameworkCompute — A/B objective testing with traffic splitting.

Implements the A/B objective testing framework from OMN-2361 design doc Section 10.

Traffic splitting:
    - Deterministic hash on run_id (same run_id → same variant assignment)
    - All registered variants receive the same EvidenceBundle

Shadow evaluation safety:
    - Only ACTIVE variant results drive policy state
    - SHADOW variant results are stored for analysis only

Divergence detection:
    - Different passed outcomes between active and shadow
    - ScoreVector L2 distance > registry.divergence_threshold

Upgrade signal:
    - Shadow win rate >= (1 - registry.significance_threshold) over N runs
    - Emit ObjectiveUpgradeReadyEvent (promotion requires explicit operator action)

Ticket: OMN-2571
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_objective_ab_framework_compute.handlers.handler_ab_framework import (
    run_ab_evaluation,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_ab_evaluation_input import (
    ModelABEvaluationInput,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_ab_evaluation_output import (
    ModelABEvaluationOutput,
)


class NodeObjectiveABFrameworkCompute(
    NodeCompute[ModelABEvaluationInput, ModelABEvaluationOutput]
):
    """Pure COMPUTE node for A/B objective variant testing.

    Evaluates an EvidenceBundle against all registered objective variants,
    detects divergence, and signals upgrade readiness.

    This node is a thin declarative shell delegating to run_ab_evaluation.
    """

    async def compute(
        self, input_data: ModelABEvaluationInput
    ) -> ModelABEvaluationOutput:
        """Run A/B evaluation against all registered variants."""
        return run_ab_evaluation(input_data)


__all__ = ["NodeObjectiveABFrameworkCompute"]
