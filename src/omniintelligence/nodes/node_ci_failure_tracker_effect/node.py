# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CI Failure Tracker Effect Node — declarative shell.

Ticket: OMN-3556
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeCiFailureTrackerEffect(NodeEffect):
    """Declarative effect node for CI failure tracking.

    Consumes ci-failure-detected.v1 events. Increments failure streaks,
    logs CI failure events, and creates TriggerRecords when streak threshold
    is crossed.

    This node is a thin shell following the ONEX declarative pattern.
    All routing and execution logic is driven by contract.yaml.
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeCiFailureTrackerEffect"]
