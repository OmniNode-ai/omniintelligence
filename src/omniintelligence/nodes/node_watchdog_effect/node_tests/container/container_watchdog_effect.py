# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for NodeWatchdogEffect in the node_watchdog_effect tests.

The node is built here, the one binding site, and the tests resolve it through
``resolve_watchdog_effect`` instead of constructing it (OMN-21785).
"""

from __future__ import annotations

from omnibase_core.models.container.model_onex_container import ModelONEXContainer

from omniintelligence.nodes.node_watchdog_effect.node import NodeWatchdogEffect


def resolve_watchdog_effect(container: ModelONEXContainer) -> NodeWatchdogEffect:
    """Resolve the NodeWatchdogEffect bound to ``container``."""
    return NodeWatchdogEffect(container)
