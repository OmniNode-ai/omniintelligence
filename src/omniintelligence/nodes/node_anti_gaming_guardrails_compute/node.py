# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""NodeAntiGamingGuardrailsCompute — structural defenses against metric gaming.

This node implements four anti-gaming guardrails from OMN-2361 design doc
(Section 4 and Section 11):

  1. Goodhart's Law Detection — correlated metric pair divergence
  2. Reward Hacking Detection — score improves, acceptance does not
  3. Distributional Shift Detection — evidence distribution drift
  4. Diversity Constraint — minimum distinct evidence source types (VETO)

It is a COMPUTE node: pure, deterministic, zero I/O.
Alert events are published by the companion NodeAntiGamingAlerterEffect.

Ticket: OMN-2563
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_anti_gaming_guardrails_compute.handlers.handler_guardrails import (
    run_all_guardrails,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_input import (
    ModelGuardrailInput,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_output import (
    ModelGuardrailOutput,
)


class NodeAntiGamingGuardrailsCompute(
    NodeCompute[ModelGuardrailInput, ModelGuardrailOutput]
):
    """Pure COMPUTE node for anti-gaming guardrail evaluation.

    Runs four structural checks:
      1. Goodhart's Law: correlated metric pair divergence
      2. Reward hacking: score improves without human acceptance improvement
      3. Distributional shift: evidence distribution drift from baseline
      4. Diversity constraint: minimum distinct evidence source types (VETO)

    Guards 1–3 emit non-blocking alerts.
    Guard 4 is a VETO: output.should_veto=True means reject the evaluation.

    This node is a thin declarative shell delegating to run_all_guardrails.
    """

    async def compute(
        self, input_data: ModelGuardrailInput
    ) -> ModelGuardrailOutput:
        """Run all anti-gaming guardrail checks."""
        return run_all_guardrails(input_data)


__all__ = ["NodeAntiGamingGuardrailsCompute"]
