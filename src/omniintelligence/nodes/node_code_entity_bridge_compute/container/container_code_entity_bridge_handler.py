# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handlers of node_code_entity_bridge_compute.

The handlers are built here, the one binding site, and the node resolves them
through the functions below instead of constructing them (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_code_entity_bridge_compute.handlers import (
    HandlerCodeEntityBridge,
)


def resolve_code_entity_bridge_handler() -> HandlerCodeEntityBridge:
    """Resolve the HandlerCodeEntityBridge the node delegates to."""
    return HandlerCodeEntityBridge()


__all__ = ["resolve_code_entity_bridge_handler"]
