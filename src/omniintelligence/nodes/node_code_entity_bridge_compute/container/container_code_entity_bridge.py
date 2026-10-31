# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for NodeCodeEntityBridgeCompute.

The node is built here, the one binding site, and the code-entity bridge dispatch
handler resolves it through ``resolve_code_entity_bridge`` instead of
constructing it (OMN-21785).
"""

from __future__ import annotations

from omniintelligence.nodes.node_code_entity_bridge_compute.node import (
    NodeCodeEntityBridgeCompute,
)


def resolve_code_entity_bridge() -> NodeCodeEntityBridgeCompute:
    """Resolve the NodeCodeEntityBridgeCompute the dispatch handler runs."""
    return NodeCodeEntityBridgeCompute()
