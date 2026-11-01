# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handlers of node_pattern_assembler_orchestrator.

The handlers are built here, the one binding site, and the node resolves them
through the functions below instead of constructing them (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers import (
    HandlerPatternAssemblyOrchestrate,
)


def resolve_pattern_assembly_orchestrate_handler() -> HandlerPatternAssemblyOrchestrate:
    """Resolve the HandlerPatternAssemblyOrchestrate the node delegates to."""
    return HandlerPatternAssemblyOrchestrate()


__all__ = ["resolve_pattern_assembly_orchestrate_handler"]
