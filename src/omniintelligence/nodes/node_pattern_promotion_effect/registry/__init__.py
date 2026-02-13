# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Registry module for NodePatternPromotionEffect.

Exports:
    RegistryPatternPromotionEffect: Registry for pattern promotion dependencies.
    RegistryPromotionHandlers: Frozen registry of handler functions.
"""

from omniintelligence.nodes.node_pattern_promotion_effect.registry.registry_pattern_promotion_effect import (
    RegistryPatternPromotionEffect,
    RegistryPromotionHandlers,
)

__all__ = ["RegistryPatternPromotionEffect", "RegistryPromotionHandlers"]
