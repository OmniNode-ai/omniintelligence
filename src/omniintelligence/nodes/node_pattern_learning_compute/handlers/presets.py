"""Default configuration presets for pattern learning.

This module provides default values and constants for pattern learning operations.
These are INPUTS (configurable defaults), not canonical constants.

IMPORTANT:
    Weights and thresholds defined here are reasonable defaults that can be
    overridden by callers. They are NOT authoritative policy - policy decisions
    belong in higher-level orchestration nodes.

Signature Versioning:
    Pattern signatures are versioned to enable migration and comparison across
    algorithm changes. The version is stored alongside each signature.

Usage:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
        SIGNATURE_VERSION,
        DEFAULT_SIMILARITY_WEIGHTS,
    )

    # Use defaults or override
    weights = DEFAULT_SIMILARITY_WEIGHTS  # Use as-is
    weights = {**DEFAULT_SIMILARITY_WEIGHTS, "keyword": 0.35}  # Override one
"""

from __future__ import annotations

from typing import Final

from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    SimilarityWeightsDict,
)

# =============================================================================
# Signature Versioning
# =============================================================================

SIGNATURE_VERSION: Final[str] = "v1.0.0"
"""Version identifier for pattern signatures.

Signature versions enable:
- Migration path when algorithm changes
- Comparison of signatures across versions
- Debugging "why did this pattern change?" questions

Bump this version when signature computation changes.
"""

SIGNATURE_NORMALIZATION: Final[str] = "lowercase_sort_dedupe"
"""Normalization method applied to signature inputs.

Current normalization:
- lowercase: Convert all identifiers to lowercase
- sort: Sort identifiers alphabetically
- dedupe: Remove duplicate identifiers

This ensures deterministic signatures regardless of declaration order.
"""

# =============================================================================
# Similarity Weights
# =============================================================================

DEFAULT_SIMILARITY_WEIGHTS: Final[SimilarityWeightsDict] = {
    "keyword": 0.30,
    "pattern": 0.25,
    "structural": 0.20,
    "label": 0.15,
    "context": 0.10,
}
"""Default weights for 5-component similarity calculation.

These are INPUTS (reasonable defaults), NOT canonical policy.
Callers can override any or all weights.

Weight rationale:
- keyword (0.30): Identifiers are strong indicators of similar code
- pattern (0.25): ONEX pattern markers are highly discriminative
- structural (0.20): Code shape provides moderate signal
- label (0.15): Training labels provide supervised signal
- context (0.10): Domain/framework provides weak contextual signal

Weights sum to 1.0.
"""

# =============================================================================
# Clustering Thresholds
# =============================================================================

DEFAULT_CLUSTERING_THRESHOLD: Final[float] = 0.70
"""Default similarity threshold for clustering.

Patterns with similarity >= this threshold are grouped together.
This is a reasonable starting point; actual threshold may be tuned
based on dataset characteristics.
"""

DEFAULT_DEDUPLICATION_THRESHOLD: Final[float] = 0.85
"""Default similarity threshold for deduplication.

Clusters with similarity >= this threshold are considered duplicates
and merged. Higher threshold = more conservative (fewer merges).

POLICY NOTE: Prefer false negatives (keep separate) over false positives
(merge incorrectly). You can merge later; you can't un-merge.
"""

NEAR_THRESHOLD_MARGIN: Final[float] = 0.05
"""Margin around threshold for near-threshold warnings.

When similarity is within this margin of the threshold, a warning
is emitted for human review.
"""

# =============================================================================
# Promotion Thresholds
# =============================================================================

DEFAULT_PROMOTION_THRESHOLD: Final[float] = 0.70
"""Default confidence threshold for promoting patterns.

Patterns with confidence >= this threshold are classified as "learned"
(ready for use). Below this threshold, patterns are "candidates"
(need more evidence).

This threshold is a starting point. Actual promotion decisions may
involve additional criteria beyond raw confidence.
"""

DEFAULT_MIN_FREQUENCY: Final[int] = 5
"""Default minimum frequency for full confidence contribution.

Clusters with fewer than this many members receive partial
frequency_factor contribution. At or above this count,
frequency_factor = 1.0.
"""

# =============================================================================
# ONEX Pattern Detection
# =============================================================================

ONEX_BASE_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "NodeCompute",
        "NodeEffect",
        "NodeReducer",
        "NodeOrchestrator",
        "BaseModel",
    }
)
"""Known ONEX base classes for pattern detection.

Used during feature extraction to identify ONEX pattern indicators
through inheritance analysis.
"""

ONEX_PATTERN_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "frozen",
        "extra",
        "forbid",
        "model_config",
        "Field",
        "TypedDict",
        "Protocol",
        "Final",
        "ClassVar",
    }
)
"""Keywords that indicate ONEX pattern usage.

These identifiers, when present in code, suggest adherence to
ONEX coding conventions.
"""

__all__ = [
    "DEFAULT_CLUSTERING_THRESHOLD",
    "DEFAULT_DEDUPLICATION_THRESHOLD",
    "DEFAULT_MIN_FREQUENCY",
    "DEFAULT_PROMOTION_THRESHOLD",
    "DEFAULT_SIMILARITY_WEIGHTS",
    "NEAR_THRESHOLD_MARGIN",
    "ONEX_BASE_CLASSES",
    "ONEX_PATTERN_KEYWORDS",
    "SIGNATURE_NORMALIZATION",
    "SIGNATURE_VERSION",
]
