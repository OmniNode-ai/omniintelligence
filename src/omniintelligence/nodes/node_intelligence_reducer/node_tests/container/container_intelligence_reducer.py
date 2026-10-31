# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for NodeIntelligenceReducer in the node_intelligence_reducer tests.

The node is built here, the one binding site, and the tests resolve it through
``resolve_intelligence_reducer`` instead of constructing it (OMN-21785).
"""

from __future__ import annotations

from omnibase_core.models.container.model_onex_container import ModelONEXContainer

from omniintelligence.nodes.node_intelligence_reducer.node import (
    NodeIntelligenceReducer,
)


def resolve_intelligence_reducer(
    container: ModelONEXContainer,
) -> NodeIntelligenceReducer:
    """Resolve the NodeIntelligenceReducer bound to ``container``."""
    return NodeIntelligenceReducer(container=container)
