# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handlers of node_ci_error_classifier_compute.

The handlers are built here, the one binding site, and the node resolves them
through the functions below instead of constructing them (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_ci_error_classifier_compute.handlers.handler_classifier import (
    HandlerCiErrorClassifier,
)


def resolve_ci_error_classifier_handler() -> HandlerCiErrorClassifier:
    """Resolve the HandlerCiErrorClassifier the node delegates to."""
    return HandlerCiErrorClassifier()


__all__ = ["resolve_ci_error_classifier_handler"]
