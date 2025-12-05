# SPDX-License-Identifier: Apache-2.0
"""
OmniIntelligence Runtime Package.

Provides configuration and registry components for the OmniIntelligence runtime host.

This package contains:
    - IntelligenceRuntimeConfig: Application-level runtime configuration
    - IntelligenceNodeRegistry: Node registration and discovery (Phase 6)

Usage:
    from omniintelligence.runtime import (
        IntelligenceRuntimeConfig,
        EventBusConfig,
        HandlerConfig,
        TopicConfig,
    )

    # Load from YAML file
    config = IntelligenceRuntimeConfig.from_yaml("/path/to/config.yaml")

    # Load from environment
    config = IntelligenceRuntimeConfig.from_environment()

Note:
    This package does NOT contain:
    - BaseRuntimeHostProcess (belongs in omnibase_infra)
    - Handler implementations (belong in omnibase_infra)
    - Protocol definitions (belong in omnibase_spi)
"""

from omniintelligence.runtime.runtime_config import (
    EventBusConfig,
    HandlerConfig,
    IntelligenceRuntimeConfig,
    TopicConfig,
)

__all__ = [
    "EventBusConfig",
    "HandlerConfig",
    "IntelligenceRuntimeConfig",
    "TopicConfig",
]
