# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Registry module for Pattern Demotion Effect Node.

Provides the registry factory and service handler registry for wiring
handler dependencies to the NodePatternDemotionEffect node.
"""

from omniintelligence.nodes.node_pattern_demotion_effect.registry.registry_pattern_demotion_effect import (
    RegistryPatternDemotionEffect,
    ServiceHandlerRegistry,
)

__all__ = ["RegistryPatternDemotionEffect", "ServiceHandlerRegistry"]
