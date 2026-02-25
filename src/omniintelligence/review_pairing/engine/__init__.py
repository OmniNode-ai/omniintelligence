# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pairing Engine for the Review-Fix Pairing subsystem.

Implements the confidence-scored finding-to-fix join logic (OMN-2551).

Public API:
    PairingEngine      — Main engine class
    ConfidenceScorer   — Scoring model for finding-fix pairs
    PairingResult      — Result of a pairing attempt
"""

from omniintelligence.review_pairing.engine.engine import PairingEngine, PairingResult
from omniintelligence.review_pairing.engine.scorer import (
    ConfidenceScorer,
    ScoringContext,
    ScoringResult,
)

__all__ = [
    "ConfidenceScorer",
    "PairingEngine",
    "PairingResult",
    "ScoringContext",
    "ScoringResult",
]
