# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handlers of node_success_criteria_matcher_compute.

The handlers are built here, the one binding site, and the node resolves them
through the functions below instead of constructing them (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers import (
    HandlerSuccessCriteriaCompute,
)


def resolve_success_criteria_compute_handler() -> HandlerSuccessCriteriaCompute:
    """Resolve the HandlerSuccessCriteriaCompute the node delegates to."""
    return HandlerSuccessCriteriaCompute()


__all__ = ["resolve_success_criteria_compute_handler"]
