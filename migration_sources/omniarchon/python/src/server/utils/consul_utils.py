"""
Consul Service Discovery Utilities

Convenience functions for Consul-based node lookup and service discovery.
"""

import logging
from typing import Optional

from server.services.consul_service import get_consul_service

logger = logging.getLogger(__name__)


def get_service_url(
    service_name: str,
    scheme: str = "http",
    tag: Optional[str] = None,
    fallback_url: Optional[str] = None,
) -> str:
    """
    Get service URL via Consul with fallback.

    Args:
        service_name: Service name to lookup (e.g., "archon-intelligence")
        scheme: URL scheme (http/https)
        tag: Filter by tag (optional)
        fallback_url: Fallback URL if Consul unavailable or service not found

    Returns:
        Service URL (e.g., "http://localhost:8053")

    Example:
        >>> get_service_url(
        ...     "archon-intelligence",
        ...     fallback_url="http://localhost:8053"
        ... )
        "http://localhost:8053"
    """
    consul_service = get_consul_service()

    # Try Consul lookup
    url = consul_service.get_service_url(service_name, scheme=scheme, tag=tag)

    if url:
        logger.debug(f"✅ Resolved '{service_name}' via Consul: {url}")
        return url

    # Fallback to provided URL
    if fallback_url:
        logger.debug(
            f"⚠️  Consul unavailable - using fallback URL for '{service_name}': {fallback_url}"
        )
        return fallback_url

    # No fallback provided
    raise ValueError(
        f"Service '{service_name}' not found in Consul and no fallback URL provided"
    )


def list_service_instances(
    service_name: str,
    tag: Optional[str] = None,
    passing_only: bool = True,
) -> list[dict]:
    """
    List all instances of a service.

    Args:
        service_name: Service name to lookup
        tag: Filter by tag (optional)
        passing_only: Only return healthy instances (default: True)

    Returns:
        List of service instances with address, port, tags, and metadata

    Example:
        >>> instances = list_service_instances("archon-intelligence")
        >>> for instance in instances:
        ...     print(f"{instance['address']}:{instance['port']}")
        localhost:8053
    """
    consul_service = get_consul_service()
    return consul_service.discover_service(
        service_name,
        tag=tag,
        passing_only=passing_only,
    )


def get_all_archon_services() -> dict[str, list[dict]]:
    """
    Get all Archon services registered in Consul.

    Returns:
        Dictionary mapping service names to their instances

    Example:
        >>> services = get_all_archon_services()
        >>> for service_name, instances in services.items():
        ...     print(f"{service_name}: {len(instances)} instance(s)")
        archon-server: 1 instance(s)
        archon-intelligence: 1 instance(s)
        archon-bridge: 1 instance(s)
        archon-search: 1 instance(s)
    """
    archon_service_names = [
        "archon-server",
        "archon-intelligence",
        "archon-bridge",
        "archon-search",
        "archon-agents",
        "archon-mcp",
    ]

    services = {}
    for service_name in archon_service_names:
        instances = list_service_instances(service_name, passing_only=False)
        if instances:
            services[service_name] = instances

    return services


def is_service_healthy(service_name: str) -> bool:
    """
    Check if service has at least one healthy instance.

    Args:
        service_name: Service name to check

    Returns:
        True if service has healthy instances, False otherwise

    Example:
        >>> if is_service_healthy("archon-intelligence"):
        ...     print("Intelligence service is healthy")
        Intelligence service is healthy
    """
    instances = list_service_instances(service_name, passing_only=True)
    return len(instances) > 0


def get_service_metadata(service_name: str) -> Optional[dict]:
    """
    Get metadata for first healthy service instance.

    Args:
        service_name: Service name to lookup

    Returns:
        Service metadata dict or None if not found

    Example:
        >>> metadata = get_service_metadata("archon-intelligence")
        >>> print(metadata.get("capabilities"))
        quality,performance,freshness,pattern-learning
    """
    instances = list_service_instances(service_name, passing_only=True)

    if not instances:
        return None

    return instances[0].get("meta", {})
