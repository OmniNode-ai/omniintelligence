# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
OmniIntelligence Runtime Package.

Provides configuration, registry, and plugin components for the OmniIntelligence
runtime host.

This package contains:
    - ModelIntelligenceRuntimeConfig: Application-level runtime configuration
    - PluginIntelligence: Domain plugin for ONEX kernel initialization
    - IntelligenceNodeRegistry: Node registration and discovery (Phase 6)

Usage:
    from omniintelligence.runtime import (
        ModelIntelligenceRuntimeConfig,
        ModelEventBusConfig,
        ModelHandlerConfig,
        ModelTopicConfig,
        PluginIntelligence,
    )

    # Load from YAML file
    config = ModelIntelligenceRuntimeConfig.from_yaml("/path/to/config.yaml")

    # Load from environment
    config = ModelIntelligenceRuntimeConfig.from_environment()

    # Register plugin with kernel
    from omnibase_infra.runtime.protocol_domain_plugin import RegistryDomainPlugin
    registry = RegistryDomainPlugin()
    registry.register(PluginIntelligence())

Note:
    This package does NOT contain:
    - BaseRuntimeHostProcess (belongs in omnibase_infra)
    - Handler implementations (belong in omnibase_infra)
    - Protocol definitions (belong in omnibase_spi)
"""

from omniintelligence.runtime.enum_handler_type import EnumHandlerType
from omniintelligence.runtime.enum_log_level import EnumLogLevel
from omniintelligence.runtime.model_event_bus_config import ModelEventBusConfig
from omniintelligence.runtime.model_handler_config import ModelHandlerConfig
from omniintelligence.runtime.model_intelligence_runtime_config import (
    ModelIntelligenceRuntimeConfig,
)
from omniintelligence.runtime.model_runtime_profile_config import (
    ModelRuntimeProfileConfig,
)
from omniintelligence.runtime.model_topic_config import ModelTopicConfig
from omniintelligence.runtime.plugin import PluginIntelligence

__all__ = [
    "EnumHandlerType",
    "EnumLogLevel",
    "ModelEventBusConfig",
    "ModelHandlerConfig",
    "ModelIntelligenceRuntimeConfig",
    "ModelRuntimeProfileConfig",
    "ModelTopicConfig",
    "PluginIntelligence",
]
