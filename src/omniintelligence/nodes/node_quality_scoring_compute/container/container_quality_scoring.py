# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handlers of node_quality_scoring_compute.

The handlers are built here, the one binding site, and the node resolves them
through the functions below instead of constructing them (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    HandlerQualityScoringCompute,
)


def resolve_quality_scoring_compute_handler() -> HandlerQualityScoringCompute:
    """Resolve the HandlerQualityScoringCompute the node delegates to."""
    return HandlerQualityScoringCompute()


__all__ = ["resolve_quality_scoring_compute_handler"]
