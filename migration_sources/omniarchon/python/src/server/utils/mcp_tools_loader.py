"""
MCP Tools Configuration Loader

Loads MCP tool definitions from YAML configuration file and adds
dynamic timestamps for discovered_at fields.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from server.config.logfire_config import api_logger


def get_config_path() -> Path:
    """Get the path to the MCP tools configuration file."""
    # Get project root (4 levels up from this file)
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent
    config_path = project_root / "config" / "mcp_tools.yaml"

    return config_path


def load_mcp_tools() -> list[dict[str, Any]]:
    """
    Load MCP tool definitions from YAML configuration.

    Returns:
        List of tool definitions with added discovered_at timestamps

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is malformed
    """
    config_path = get_config_path()

    if not config_path.exists():
        api_logger.error(f"MCP tools config not found: {config_path}")
        raise FileNotFoundError(f"MCP tools configuration not found: {config_path}")

    try:
        # Load YAML configuration
        with open(config_path) as f:
            config = yaml.safe_load(f)

        if not config or "tools" not in config:
            api_logger.error("Invalid MCP tools config: missing 'tools' key")
            raise ValueError("Invalid MCP tools configuration: missing 'tools' key")

        # Convert to list format with dynamic timestamps
        tools = []
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        for tool_key, tool_config in config["tools"].items():
            # Add dynamic discovered_at timestamp
            tool_definition = {
                **tool_config,
                "discovered_at": current_timestamp,
            }
            tools.append(tool_definition)

        api_logger.info(f"Loaded {len(tools)} MCP tools from configuration")
        return tools

    except yaml.YAMLError as e:
        api_logger.error(f"Failed to parse MCP tools config: {e}")
        raise
    except Exception as e:
        api_logger.error(f"Failed to load MCP tools config: {e}")
        raise


def validate_tool_structure(tool: dict[str, Any]) -> bool:
    """
    Validate that a tool definition has the required structure.

    Args:
        tool: Tool definition dictionary

    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        "id",
        "client_id",
        "tool_name",
        "tool_description",
        "tool_schema",
        "discovered_at",
    ]

    # Check all required fields exist
    for field in required_fields:
        if field not in tool:
            api_logger.warning(f"Tool missing required field: {field}")
            return False

    # Validate tool_schema structure
    if "inputSchema" not in tool.get("tool_schema", {}):
        api_logger.warning(f"Tool {tool.get('tool_name')} missing inputSchema")
        return False

    return True


def get_tool_count() -> int:
    """
    Get the number of tools defined in the configuration.

    Returns:
        Number of tools, or 0 if config cannot be loaded
    """
    try:
        tools = load_mcp_tools()
        return len(tools)
    except Exception:
        return 0


class RoutingConfig:
    """Holds routing configuration for an MCP tool."""

    def __init__(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ):
        self.method = method
        self.endpoint = endpoint
        self.params = params or {}
        self.json_body = json_body


def get_tool_routing(tool_name: str, arguments: dict[str, Any]) -> RoutingConfig:
    """
    Get routing configuration for a tool based on YAML config.

    This replaces the brittle if/elif chain by loading routing config
    from the YAML file and building the HTTP request dynamically.

    Args:
        tool_name: Name of the tool to route
        arguments: Arguments passed to the tool

    Returns:
        RoutingConfig: Configuration with method, endpoint, params, and body

    Raises:
        ValueError: If tool not found or routing config missing
        KeyError: If required path parameter missing from arguments
    """
    config_path = get_config_path()

    if not config_path.exists():
        raise FileNotFoundError(f"MCP tools configuration not found: {config_path}")

    try:
        # Load YAML configuration
        with open(config_path) as f:
            config = yaml.safe_load(f)

        if not config or "tools" not in config:
            raise ValueError("Invalid MCP tools configuration: missing 'tools' key")

        # Find the tool configuration
        tool_config = config["tools"].get(tool_name)
        if not tool_config:
            raise ValueError(f"Tool '{tool_name}' not found in configuration")

        # Extract routing configuration
        routing = tool_config.get("routing")
        if not routing:
            raise ValueError(f"Tool '{tool_name}' missing routing configuration")

        http_method = routing["method"]
        endpoint = routing["endpoint"]
        params_location = routing.get("params_location", "query")
        path_params = routing.get("path_params", [])
        exclude_from_body = routing.get("exclude_from_body", [])

        # Build endpoint with path parameters
        for param in path_params:
            if param not in arguments:
                raise KeyError(
                    f"Required path parameter '{param}' missing from arguments"
                )
            endpoint = endpoint.replace(f"{{{param}}}", str(arguments[param]))

        # Build params/body based on params_location
        params = {}
        json_body = None

        if params_location == "query":
            # Query parameters (GET requests)
            params = arguments.copy()
        elif params_location == "body":
            # JSON body (POST/PUT/PATCH requests)
            # Exclude path params from body
            json_body = {
                k: v for k, v in arguments.items() if k not in exclude_from_body
            }
        elif params_location == "path":
            # Path only, no additional params/body needed
            pass

        api_logger.debug(
            f"Routing {tool_name}: {http_method} {endpoint} "
            f"(params: {params}, body: {json_body})"
        )

        return RoutingConfig(
            method=http_method,
            endpoint=endpoint,
            params=params,
            json_body=json_body,
        )

    except yaml.YAMLError as e:
        api_logger.error(f"Failed to parse MCP tools config: {e}")
        raise
    except Exception as e:
        api_logger.error(f"Failed to get tool routing for '{tool_name}': {e}")
        raise
