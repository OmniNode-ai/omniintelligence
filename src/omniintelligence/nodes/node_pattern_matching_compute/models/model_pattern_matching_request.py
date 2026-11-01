# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerPatternMatching."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_matching_compute.handlers.protocols import (
    PatternRecord,
)

# Supported operations
PatternOperation = Literal["match", "similarity", "classify", "validate"]


class ModelPatternMatchingRequest(BaseModel):
    """Request for matching code against a pattern library.

    Range validation (``min_confidence``, ``max_results``, empty snippet) is
    intentionally left to the handler so invalid input yields a structured
    error result rather than a raised exception.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    code_snippet: str
    patterns: Sequence[PatternRecord]
    min_confidence: float = 0.5
    max_results: int = 10
    operation: PatternOperation = "match"
    language: str | None = None
    pattern_categories: Sequence[str] | None = None
    correlation_id: str | None = None


__all__ = ["ModelPatternMatchingRequest", "PatternOperation"]
