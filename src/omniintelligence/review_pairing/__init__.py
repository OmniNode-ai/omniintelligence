# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Review-Fix Pairing subsystem for OmniIntelligence.

This package provides the canonical event contracts, Pydantic models, and
Postgres schema migration for the Review-Fix Pairing and Pattern Reinforcement
system (OMN-2353).

Public API:
    models — All four canonical event contracts plus the pairing model.
    topics — Kafka topic registry for review-pairing events.
"""

from omniintelligence.review_pairing.models import (
    FindingFixPair,
    ReviewFindingObserved,
    ReviewFindingResolved,
    ReviewFixApplied,
)

__all__ = [
    "FindingFixPair",
    "ReviewFindingObserved",
    "ReviewFindingResolved",
    "ReviewFixApplied",
]
