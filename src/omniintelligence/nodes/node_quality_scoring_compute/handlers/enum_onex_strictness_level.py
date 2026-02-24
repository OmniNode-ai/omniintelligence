# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ONEX strictness level enum.

This module provides the OnexStrictnessLevel enum for quality scoring
configuration. The enum is separated following ONEX naming conventions
for enum files (enum_*.py).

Strictness Levels:
    - STRICT: Production-ready code with high quality bar. Emphasizes documentation
      and pattern adherence. Use for production deployments and code reviews.
    - STANDARD: Default balanced requirements suitable for most use cases.
      Provides good coverage across all dimensions without being overly strict.
    - LENIENT: Development/prototyping mode with lower quality bar. More forgiving
      on documentation and pattern requirements. Use for rapid prototyping,
      exploratory code, or legacy code assessment.

Usage:
    from omniintelligence.nodes.node_quality_scoring_compute.handlers.enum_onex_strictness_level import (
        OnexStrictnessLevel,
    )

    level = OnexStrictnessLevel.STRICT

Example:
    >>> from omniintelligence.nodes.node_quality_scoring_compute.handlers.enum_onex_strictness_level import (
    ...     OnexStrictnessLevel,
    ... )
    >>> OnexStrictnessLevel.STRICT.value
    'strict'
    >>> list(OnexStrictnessLevel)
    [<OnexStrictnessLevel.STRICT: 'strict'>, <OnexStrictnessLevel.STANDARD: 'standard'>, <OnexStrictnessLevel.LENIENT: 'lenient'>]
"""

from __future__ import annotations

from enum import Enum


class OnexStrictnessLevel(str, Enum):
    """ONEX compliance strictness levels.

    Each level represents a different quality bar for code assessment:

    Attributes:
        STRICT: Production-ready quality bar (threshold 0.8).
            Higher weights on documentation (0.20) and patterns (0.20).
            Use for production code, PR reviews, and release candidates.

        STANDARD: Default balanced requirements (threshold 0.7).
            Equal distribution across dimensions (0.15-0.20 each).
            Use for regular development and CI/CD quality gates.

        LENIENT: Development/prototyping mode (threshold 0.5).
            Higher tolerance for complexity (0.25), lower requirements
            for documentation (0.10) and patterns (0.10).
            Use for rapid prototyping, exploration, or legacy assessment.
    """

    STRICT = "strict"
    STANDARD = "standard"
    LENIENT = "lenient"


__all__ = ["OnexStrictnessLevel"]
