# SPDX-License-Identifier: Apache-2.0
"""
OmniIntelligence Runtime Package.

Provides configuration and registry components for the OmniIntelligence runtime host.

This package contains:
    - ModelIntelligenceRuntimeConfig: Application-level runtime configuration
    - IntelligenceNodeRegistry: Node registration and discovery (Phase 6)

Usage:
    from omniintelligence.runtime import (
        ModelIntelligenceRuntimeConfig,
        ModelEventBusConfig,
        ModelHandlerConfig,
        ModelTopicConfig,
    )

    # Load from YAML file
    config = ModelIntelligenceRuntimeConfig.from_yaml("/path/to/config.yaml")

    # Load from environment
    config = ModelIntelligenceRuntimeConfig.from_environment()

Note:
    This package does NOT contain:
    - BaseRuntimeHostProcess (belongs in omnibase_infra)
    - Handler implementations (belong in omnibase_infra)
    - Protocol definitions (belong in omnibase_spi)
"""

from omniintelligence.runtime.model_runtime_config import (
    # Enums (ONEX compliant - Enum prefix)
    EnumHandlerType,
    EnumLogLevel,
    # ONEX-compliant Model* prefixed classes
    ModelEventBusConfig,
    ModelHandlerConfig,
    ModelIntelligenceRuntimeConfig,
    ModelRuntimeProfileConfig,
    ModelTopicConfig,
)

__all__ = [
    "EnumHandlerType",
    "EnumLogLevel",
    "ModelEventBusConfig",
    "ModelHandlerConfig",
    "ModelIntelligenceRuntimeConfig",
    "ModelRuntimeProfileConfig",
    "ModelTopicConfig",
]
