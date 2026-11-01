# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handlers of node_execution_trace_parser_compute.

The handlers are built here, the one binding site, and the node resolves them
through the functions below instead of constructing them (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers import (
    HandlerTraceParsingCompute,
)


def resolve_trace_parsing_compute_handler() -> HandlerTraceParsingCompute:
    """Resolve the HandlerTraceParsingCompute the node delegates to."""
    return HandlerTraceParsingCompute()


__all__ = ["resolve_trace_parsing_compute_handler"]
