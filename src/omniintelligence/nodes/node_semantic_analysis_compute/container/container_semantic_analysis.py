# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handlers of node_semantic_analysis_compute.

The handlers are built here, the one binding site, and the node resolves them
through the functions below instead of constructing them (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_semantic_analysis_compute.handlers import (
    HandlerSemanticAnalysisCompute,
)


def resolve_semantic_analysis_compute_handler() -> HandlerSemanticAnalysisCompute:
    """Resolve the HandlerSemanticAnalysisCompute the node delegates to."""
    return HandlerSemanticAnalysisCompute()


__all__ = ["resolve_semantic_analysis_compute_handler"]
