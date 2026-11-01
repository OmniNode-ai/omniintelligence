# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handlers of node_pattern_matching_compute.

The handlers are built here, the one binding site, and the node resolves them
through the functions below instead of constructing them (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_pattern_matching_compute.handlers import (
    HandlerPatternMatchingCompute,
)


def resolve_pattern_matching_compute_handler() -> HandlerPatternMatchingCompute:
    """Resolve the HandlerPatternMatchingCompute the node delegates to."""
    return HandlerPatternMatchingCompute()


__all__ = ["resolve_pattern_matching_compute_handler"]
