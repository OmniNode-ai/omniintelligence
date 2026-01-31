# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Demotion Effect Node - Demote validated patterns to deprecated.

This node implements OMN-1681: Auto-demote logic for patterns that no longer
meet quality thresholds based on rolling window metrics.
"""

from omniintelligence.nodes.node_pattern_demotion_effect.node import (
    NodePatternDemotionEffect,
)

__all__ = ["NodePatternDemotionEffect"]
