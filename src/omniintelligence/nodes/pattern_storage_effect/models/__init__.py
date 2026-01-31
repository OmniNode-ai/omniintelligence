# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Models for Pattern Storage Effect node.

This module exports all models used by the NodePatternStorageEffect,
including input, output, and supporting models for pattern storage
and lifecycle state management.

Key Models:
    - ModelPatternStorageInput: Input from pattern-learned.v1 events
    - ModelPatternStoredEvent: Output for pattern-stored.v1 events
    - ModelPatternPromotedEvent: Output for pattern-promoted.v1 events
    - EnumPatternState: Pattern lifecycle states (candidate/provisional/validated)
    - PatternStorageGovernance: Governance constants (MIN_CONFIDENCE = 0.5)

Lineage Key:
    Patterns are uniquely identified by (domain, signature_hash) for
    deduplication and version tracking.

Reference:
    - OMN-1668: Pattern storage effect models
"""

from omniintelligence.nodes.pattern_storage_effect.models.model_pattern_state import (
    EnumPatternState,
    PatternStorageGovernance,
)
from omniintelligence.nodes.pattern_storage_effect.models.model_pattern_storage_input import (
    ModelPatternStorageInput,
    ModelPatternStorageMetadata,
)
from omniintelligence.nodes.pattern_storage_effect.models.model_pattern_storage_output import (
    ModelPatternMetricsSnapshot,
    ModelPatternPromotedEvent,
    ModelPatternStoredEvent,
)

__all__ = [
    "EnumPatternState",
    "ModelPatternMetricsSnapshot",
    "ModelPatternPromotedEvent",
    "ModelPatternStorageInput",
    "ModelPatternStorageMetadata",
    "ModelPatternStoredEvent",
    "PatternStorageGovernance",
]
