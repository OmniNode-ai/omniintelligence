"""
Configuration module for Archon

This module provides configuration management and service discovery
for the Archon microservices architecture.
"""

# New centralized configuration system
from server.config.archon_config import (
    ArchonConfig,
    IntelligenceServiceConfig,
    MainServerConfig,
    MCPServiceConfig,
    SearchServiceConfig,
    ServiceConfig,
    get_archon_config,
    get_intelligence_endpoint,
    get_service_url,
)
from server.config.service_discovery import (
    Environment,
    ServiceDiscovery,
    discovery,
    get_agents_url,
    get_api_url,
    get_mcp_url,
    is_service_healthy,
)

__all__ = [
    # Legacy service discovery
    "ServiceDiscovery",
    "Environment",
    "discovery",
    "get_api_url",
    "get_mcp_url",
    "get_agents_url",
    "is_service_healthy",
    # New centralized configuration system
    "ArchonConfig",
    "ServiceConfig",
    "MCPServiceConfig",
    "IntelligenceServiceConfig",
    "SearchServiceConfig",
    "MainServerConfig",
    "get_archon_config",
    "get_service_url",
    "get_intelligence_endpoint",
]
