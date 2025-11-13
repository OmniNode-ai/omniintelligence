"""Kafka configuration helper for context-aware bootstrap servers.

This module provides context-aware Kafka configuration to handle different
deployment scenarios:
- Docker containers: Use internal DNS (omninode-bridge-redpanda:9092)
- Host scripts: Use localhost with published port (localhost:29092)
- Auto-detect: Determine context automatically
- Network-specific IPs can be set via KAFKA_BOOTSTRAP_SERVERS in .env

Usage:
    from config.kafka_helper import get_kafka_bootstrap_servers

    # Auto-detect context
    servers = get_kafka_bootstrap_servers()

    # Explicit context
    servers = get_kafka_bootstrap_servers(context="host")
"""

import os
from typing import Literal

from config.settings import settings

ContextType = Literal["auto", "docker", "host", "remote"]


def get_kafka_bootstrap_servers(context: ContextType = "auto") -> str:
    """
    Get Kafka bootstrap servers based on deployment context.

    This function returns the appropriate Kafka bootstrap servers string
    based on the deployment context. It respects the KAFKA_BOOTSTRAP_SERVERS
    environment variable if set.

    Args:
        context: Deployment context:
            - 'auto': Auto-detect based on environment (default)
            - 'docker': Running inside Docker container
            - 'host': Running on host machine (development)
            - 'remote': Running on remote Kafka server directly

    Returns:
        Kafka bootstrap servers string

    Examples:
        >>> # Auto-detect (recommended for most cases)
        >>> servers = get_kafka_bootstrap_servers()
        >>>
        >>> # Explicit context for scripts
        >>> servers = get_kafka_bootstrap_servers(context="host")
        >>> print(servers)
        'localhost:29092'
        >>>
        >>> # Docker services
        >>> servers = get_kafka_bootstrap_servers(context="docker")
        >>> print(servers)
        'omninode-bridge-redpanda:9092'
    """
    # Environment variable override takes precedence
    override = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    if override:
        return override

    # Auto-detect context if requested
    if context == "auto":
        context = _detect_context()

    # Return context-specific bootstrap servers
    if context == "docker":
        # Docker services use internal DNS with internal port
        # DNS resolves via /etc/hosts → 192.168.86.200:9092
        return "omninode-bridge-redpanda:9092"
    elif context == "remote":
        # Scripts running ON the remote server itself
        return "localhost:29092"
    else:  # context == "host"
        # Host scripts default to localhost with published port
        # For network-specific IPs (e.g., 192.168.86.200), set KAFKA_BOOTSTRAP_SERVERS in .env
        return "localhost:29092"


def _detect_context() -> Literal["docker", "host"]:
    """
    Auto-detect deployment context.

    Returns:
        'docker' if running in Docker container, 'host' otherwise
    """
    # Check for Docker environment
    # Method 1: Check for .dockerenv file
    if os.path.exists("/.dockerenv"):
        return "docker"

    # Method 2: Check cgroup for docker
    try:
        with open("/proc/1/cgroup", "r") as f:
            cgroup = f.read()
            if "docker" in cgroup or "containerd" in cgroup:
                return "docker"
    except (FileNotFoundError, PermissionError):
        pass

    # Default to host
    return "host"


def get_kafka_consumer_config(
    context: ContextType = "auto", group_id: str = "default-consumer-group", **kwargs
) -> dict:
    """
    Get complete Kafka consumer configuration.

    Args:
        context: Deployment context (see get_kafka_bootstrap_servers)
        group_id: Kafka consumer group ID
        **kwargs: Additional Kafka consumer configuration overrides

    Returns:
        Dictionary of Kafka consumer configuration

    Example:
        >>> config = get_kafka_consumer_config(
        ...     context="host",
        ...     group_id="archon-intelligence-consumer"
        ... )
    """
    config = {
        "bootstrap_servers": get_kafka_bootstrap_servers(context),
        "group_id": group_id,
        "auto_offset_reset": "earliest",
        "enable_auto_commit": True,
        "max_poll_records": 500,
        "session_timeout_ms": 30000,
        "request_timeout_ms": 60000,
    }

    # Override with any provided kwargs
    config.update(kwargs)

    return config


def get_kafka_producer_config(context: ContextType = "auto", **kwargs) -> dict:
    """
    Get complete Kafka producer configuration.

    Args:
        context: Deployment context (see get_kafka_bootstrap_servers)
        **kwargs: Additional Kafka producer configuration overrides

    Returns:
        Dictionary of Kafka producer configuration

    Example:
        >>> config = get_kafka_producer_config(context="host")
    """
    config = {
        "bootstrap_servers": get_kafka_bootstrap_servers(context),
        "acks": "all",
        "retries": 3,
        "max_in_flight_requests_per_connection": 5,
        "compression_type": "snappy",
        "linger_ms": 10,
        "request_timeout_ms": 60000,
    }

    # Override with any provided kwargs
    config.update(kwargs)

    return config


# Backward compatibility: default bootstrap servers for host context
KAFKA_BOOTSTRAP_SERVERS = get_kafka_bootstrap_servers(context="host")

# Common configurations for easy import
# Note: For network-specific IPs, override via KAFKA_BOOTSTRAP_SERVERS in .env
KAFKA_HOST_SERVERS = "localhost:29092"
KAFKA_DOCKER_SERVERS = "omninode-bridge-redpanda:9092"
KAFKA_REMOTE_SERVERS = "localhost:29092"
