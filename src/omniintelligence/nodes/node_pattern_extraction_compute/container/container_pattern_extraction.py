# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handlers of node_pattern_extraction_compute.

The handlers are built here, the one binding site, and the node resolves them
through the functions below instead of constructing them (OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_pattern_extraction_compute.handlers import (
    HandlerExtractAllPatterns,
    HandlerPatternExtractionCore,
)


def resolve_extract_all_patterns_handler() -> HandlerExtractAllPatterns:
    """Resolve the HandlerExtractAllPatterns the node delegates to."""
    return HandlerExtractAllPatterns()


def resolve_pattern_extraction_core_handler() -> HandlerPatternExtractionCore:
    """Resolve the HandlerPatternExtractionCore the node delegates to."""
    return HandlerPatternExtractionCore()


__all__ = [
    "resolve_extract_all_patterns_handler",
    "resolve_pattern_extraction_core_handler",
]
