# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node Compliance Evaluate Effect - Event-driven compliance evaluation receiver.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers
    - Pattern: "Contract-driven, handlers wired externally"

Closes the loop opened by OMN-2256/omniclaude PR #161:
    omniclaude emits onex.cmd.omniintelligence.compliance-evaluate.v1
    -> this node consumes and calls handle_evaluate_compliance()
    -> emits onex.evt.omniintelligence.compliance-evaluated.v1

All handler routing is 100% driven by contract.yaml, not Python code.

Ticket: OMN-2339
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeComplianceEvaluateEffect(NodeEffect):
    """Declarative effect node for event-driven compliance evaluation.

    Consumes compliance-evaluate commands from omniclaude and delegates
    all logic to the handler (which calls handle_evaluate_compliance()
    from node_pattern_compliance_effect). Emits compliance-evaluated
    events with violation results.

    This node is a pure declarative shell following the ONEX pattern.
    All logic is in the handler functions; the contract.yaml declares
    the subscription and publication topics.

    Related:
        OMN-2256: node_pattern_compliance_effect (the leaf node)
        OMN-2339: This node (the event-driven receiver)
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeComplianceEvaluateEffect"]
