"""
Centralized Archon Configuration System

This module provides a single source of truth for all service URLs, ports, and endpoints
used throughout the Archon ecosystem. All services should import from this module
to prevent endpoint mismatches and configuration drift.

Usage:
    from server.config.archon_config import ArchonConfig

    config = ArchonConfig()
    mcp_url = config.mcp_service.base_url
    intelligence_endpoint = config.intelligence_service.extract_endpoint
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ServiceConfig:
    """Configuration for a single service"""

    host: str
    port: int
    base_url: str

    @property
    def health_endpoint(self) -> str:
        return f"{self.base_url}/health"


@dataclass
class MCPServiceConfig(ServiceConfig):
    """MCP Server specific configuration"""

    @property
    def mcp_endpoint(self) -> str:
        return f"{self.base_url}/mcp"

    @property
    def create_document_endpoint(self) -> str:
        return f"{self.mcp_endpoint}/create_document"

    @property
    def rag_query_endpoint(self) -> str:
        return f"{self.mcp_endpoint}/rag_query"


@dataclass
class IntelligenceServiceConfig(ServiceConfig):
    """Intelligence Service specific configuration"""

    @property
    def extract_endpoint(self) -> str:
        return f"{self.base_url}/extract/document"

    @property
    def assess_quality_endpoint(self) -> str:
        return f"{self.base_url}/assess/code"


@dataclass
class SearchServiceConfig(ServiceConfig):
    """Enhanced Search Service specific configuration"""

    @property
    def enhanced_search_endpoint(self) -> str:
        return f"{self.base_url}/search/enhanced"

    @property
    def vector_search_endpoint(self) -> str:
        return f"{self.base_url}/search/vector"


@dataclass
class MainServerConfig(ServiceConfig):
    """Main Archon Server specific configuration"""

    @property
    def api_base(self) -> str:
        return f"{self.base_url}/api"

    @property
    def projects_endpoint(self) -> str:
        return f"{self.api_base}/projects"

    @property
    def tasks_endpoint(self) -> str:
        return f"{self.api_base}/tasks"

    @property
    def rag_endpoint(self) -> str:
        return f"{self.api_base}/rag"


class ArchonConfig:
    """
    Centralized configuration for all Archon services.

    This class loads configuration from environment variables and provides
    typed access to all service endpoints and URLs.
    """

    def __init__(self, env_file_path: Optional[str] = None):
        """
        Initialize configuration from environment variables.

        Args:
            env_file_path: Optional path to .env file. If not provided,
                          will look for .env in the project root.
        """
        if env_file_path:
            self._load_env_file(env_file_path)
        else:
            # Try to find .env file in project root
            project_root = self._find_project_root()
            if project_root:
                env_path = project_root / ".env"
                if env_path.exists():
                    self._load_env_file(str(env_path))

        # Load configuration
        self.host = os.getenv("HOST", "localhost")

        # Initialize service configurations
        self.main_server = self._init_main_server()
        self.mcp_service = self._init_mcp_service()
        self.intelligence_service = self._init_intelligence_service()
        self.search_service = self._init_search_service()
        self.bridge_service = self._init_bridge_service()
        self.agents_service = self._init_agents_service()

        # Database configuration
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

        # Security
        self.service_auth_token = os.getenv("SERVICE_AUTH_TOKEN")

        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.logfire_token = os.getenv("LOGFIRE_TOKEN")

    def _find_project_root(self) -> Optional[Path]:
        """Find the project root directory by looking for .env file"""
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / ".env").exists():
                return parent
            if (parent / "docker-compose.yml").exists():
                return parent
        return None

    def _load_env_file(self, env_path: str):
        """Load environment variables from .env file"""
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()
        except FileNotFoundError:
            pass  # .env file is optional

    def _init_main_server(self) -> MainServerConfig:
        """Initialize main server configuration"""
        port = int(os.getenv("ARCHON_SERVER_PORT", "8181"))
        base_url = os.getenv("ARCHON_SERVER_URL", f"http://{self.host}:{port}")

        return MainServerConfig(host=self.host, port=port, base_url=base_url)

    def _init_mcp_service(self) -> MCPServiceConfig:
        """Initialize MCP service configuration"""
        port = int(os.getenv("ARCHON_MCP_PORT", "8051"))
        base_url = os.getenv("ARCHON_MCP_URL", f"http://{self.host}:{port}")

        return MCPServiceConfig(host=self.host, port=port, base_url=base_url)

    def _init_intelligence_service(self) -> IntelligenceServiceConfig:
        """Initialize intelligence service configuration"""
        port = int(os.getenv("INTELLIGENCE_SERVICE_PORT", "8053"))
        base_url = os.getenv("INTELLIGENCE_SERVICE_URL", f"http://{self.host}:{port}")

        return IntelligenceServiceConfig(host=self.host, port=port, base_url=base_url)

    def _init_search_service(self) -> SearchServiceConfig:
        """Initialize search service configuration"""
        port = int(os.getenv("SEARCH_SERVICE_PORT", "8055"))
        base_url = os.getenv("SEARCH_SERVICE_URL", f"http://{self.host}:{port}")

        return SearchServiceConfig(host=self.host, port=port, base_url=base_url)

    def _init_bridge_service(self) -> ServiceConfig:
        """Initialize bridge service configuration"""
        port = int(os.getenv("BRIDGE_SERVICE_PORT", "8054"))
        base_url = os.getenv("BRIDGE_SERVICE_URL", f"http://{self.host}:{port}")

        return ServiceConfig(host=self.host, port=port, base_url=base_url)

    def _init_agents_service(self) -> ServiceConfig:
        """Initialize agents service configuration"""
        port = int(os.getenv("ARCHON_AGENTS_PORT", "8052"))
        base_url = os.getenv("ARCHON_AGENTS_URL", f"http://{self.host}:{port}")

        return ServiceConfig(host=self.host, port=port, base_url=base_url)

    def get_service_url(self, service_name: str) -> str:
        """
        Get the base URL for a service by name.

        Args:
            service_name: One of 'main', 'mcp', 'intelligence', 'search', 'bridge', 'agents'

        Returns:
            Base URL for the service

        Raises:
            ValueError: If service_name is not recognized
        """
        service_map = {
            "main": self.main_server.base_url,
            "server": self.main_server.base_url,
            "mcp": self.mcp_service.base_url,
            "intelligence": self.intelligence_service.base_url,
            "search": self.search_service.base_url,
            "bridge": self.bridge_service.base_url,
            "agents": self.agents_service.base_url,
        }

        if service_name not in service_map:
            raise ValueError(
                f"Unknown service: {service_name}. Available: {list(service_map.keys())}"
            )

        return service_map[service_name]

    def get_correct_intelligence_endpoint(self, prefer_mcp: bool = True) -> str:
        """
        Get the correct intelligence endpoint based on configuration.

        Args:
            prefer_mcp: If True, prefer MCP endpoint over direct intelligence service

        Returns:
            The appropriate intelligence endpoint URL
        """
        if prefer_mcp:
            return self.mcp_service.mcp_endpoint
        else:
            return self.intelligence_service.extract_endpoint

    def validate_configuration(self) -> dict:
        """
        Validate that all required configuration is present.

        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []

        # Check required environment variables
        required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
        for var in required_vars:
            if not os.getenv(var):
                issues.append(f"Missing required environment variable: {var}")

        # Check service authentication
        if not self.service_auth_token:
            warnings.append("SERVICE_AUTH_TOKEN not set - some services may not work")

        # Check ports for conflicts
        ports = [
            self.main_server.port,
            self.mcp_service.port,
            self.intelligence_service.port,
            self.search_service.port,
            self.bridge_service.port,
            self.agents_service.port,
        ]

        if len(ports) != len(set(ports)):
            issues.append("Port conflicts detected in service configuration")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "services": {
                "main_server": self.main_server.base_url,
                "mcp_service": self.mcp_service.base_url,
                "intelligence_service": self.intelligence_service.base_url,
                "search_service": self.search_service.base_url,
                "bridge_service": self.bridge_service.base_url,
                "agents_service": self.agents_service.base_url,
            },
        }


# Global configuration instance
_config_instance: Optional[ArchonConfig] = None


def get_archon_config(reload: bool = False) -> ArchonConfig:
    """
    Get the global Archon configuration instance.

    Args:
        reload: If True, force reload the configuration

    Returns:
        ArchonConfig instance
    """
    global _config_instance

    if _config_instance is None or reload:
        _config_instance = ArchonConfig()

    return _config_instance


def get_service_url(service_name: str) -> str:
    """
    Convenience function to get a service URL.

    Args:
        service_name: Name of the service

    Returns:
        Base URL for the service
    """
    return get_archon_config().get_service_url(service_name)


def get_intelligence_endpoint(prefer_mcp: bool = True) -> str:
    """
    Convenience function to get the correct intelligence endpoint.

    Args:
        prefer_mcp: If True, prefer MCP endpoint over direct intelligence service

    Returns:
        The appropriate intelligence endpoint URL
    """
    return get_archon_config().get_correct_intelligence_endpoint(prefer_mcp)


if __name__ == "__main__":
    # CLI tool for configuration validation and inspection
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Archon Configuration Tool")
    parser.add_argument(
        "--validate", action="store_true", help="Validate configuration"
    )
    parser.add_argument("--show", action="store_true", help="Show all configuration")
    parser.add_argument("--service", help="Get URL for specific service")

    args = parser.parse_args()

    config = get_archon_config()

    if args.validate:
        validation = config.validate_configuration()
        print(json.dumps(validation, indent=2))
        exit(0 if validation["valid"] else 1)

    elif args.show:
        print("Archon Configuration:")
        print(f"  Main Server: {config.main_server.base_url}")
        print(f"  MCP Service: {config.mcp_service.base_url}")
        print(f"  Intelligence Service: {config.intelligence_service.base_url}")
        print(f"  Search Service: {config.search_service.base_url}")
        print(f"  Bridge Service: {config.bridge_service.base_url}")
        print(f"  Agents Service: {config.agents_service.base_url}")

    elif args.service:
        try:
            url = config.get_service_url(args.service)
            print(url)
        except ValueError as e:
            print(f"Error: {e}")
            exit(1)

    else:
        parser.print_help()
