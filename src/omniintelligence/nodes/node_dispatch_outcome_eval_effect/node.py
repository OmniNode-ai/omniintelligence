# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node Dispatch Outcome Eval Effect.

This node follows the ONEX declarative effect pattern:
    - Contract-driven routing via contract.yaml
    - Lightweight NodeEffect shell
    - Handler implementation wired externally by runtime/container code

OMN-10380 intentionally provides a skeleton only. The handler maps dispatch
worker completion status to PASS/FAIL/ERROR and carries usage fields forward;
quality scoring and database writes are deferred.
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeDispatchOutcomeEvalEffect(NodeEffect):
    """Declarative effect node for dispatch outcome evaluation."""

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeDispatchOutcomeEvalEffect"]
