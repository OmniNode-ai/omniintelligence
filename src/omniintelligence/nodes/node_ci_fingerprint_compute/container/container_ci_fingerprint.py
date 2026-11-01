# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handlers of node_ci_fingerprint_compute.

The handlers are built here, the one binding site, and the node resolves them
through the functions below instead of constructing them (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_ci_fingerprint_compute.handlers.handler_fingerprint import (
    HandlerCiFingerprint,
)


def resolve_ci_fingerprint_handler() -> HandlerCiFingerprint:
    """Resolve the HandlerCiFingerprint the node delegates to."""
    return HandlerCiFingerprint()


__all__ = ["resolve_ci_fingerprint_handler"]
