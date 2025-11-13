"""
Consul Service Discovery Integration

Provides service registration, health checks, and node lookup via Consul.
"""

import logging
import os
from typing import Any, Optional

import consul

logger = logging.getLogger(__name__)


class ConsulService:
    """
    Consul client wrapper for service registration and discovery.

    Features:
    - Service registration with health checks
    - Service discovery by name
    - Graceful degradation when Consul unavailable
    - Automatic deregistration on shutdown
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        enabled: bool = True,
    ):
        """
        Initialize Consul client.

        Args:
            host: Consul server host (default: env CONSUL_HOST or 192.168.86.200)
            port: Consul server port (default: env CONSUL_PORT or 8500)
            enabled: Enable Consul integration (default: env CONSUL_ENABLED or True)
        """
        self.enabled = os.getenv("CONSUL_ENABLED", str(enabled)).lower() == "true"
        self.host = host or os.getenv("CONSUL_HOST", "192.168.86.200")
        self.port = int(port or os.getenv("CONSUL_PORT", "8500"))

        self.client: Optional[consul.Consul] = None
        self.registered_services: set[str] = set()

        if self.enabled:
            try:
                self.client = consul.Consul(host=self.host, port=self.port)
                logger.info(f"✅ Consul client initialized: {self.host}:{self.port}")
            except Exception as e:
                logger.warning(
                    f"⚠️  Consul client initialization failed: {e}. "
                    f"Service discovery will be disabled."
                )
                self.enabled = False
                self.client = None
        else:
            logger.info("ℹ️  Consul integration disabled (CONSUL_ENABLED=false)")

    def register_service(
        self,
        service_id: str,
        service_name: str,
        port: int,
        address: Optional[str] = None,
        tags: Optional[list[str]] = None,
        meta: Optional[dict[str, str]] = None,
        health_check_url: Optional[str] = None,
        health_check_interval: str = "10s",
        health_check_timeout: str = "5s",
    ) -> bool:
        """
        Register service with Consul.

        Args:
            service_id: Unique service instance ID (e.g., "archon-server-1")
            service_name: Service name (e.g., "archon-server")
            port: Service port
            address: Service address (default: localhost)
            tags: Service tags for filtering (metadata will be converted to tags)
            meta: Service metadata (converted to tags in 'key:value' format)
            health_check_url: HTTP health check endpoint
            health_check_interval: Health check interval (default: 10s)
            health_check_timeout: Health check timeout (default: 5s)

        Returns:
            True if registration successful, False otherwise
        """
        if not self.enabled or not self.client:
            logger.debug(f"Consul disabled - skipping registration for {service_name}")
            return False

        try:
            # Build service registration payload
            service_address = address or "localhost"
            service_tags = tags or []
            service_meta = meta or {}

            # Add default metadata
            service_meta.setdefault("version", os.getenv("SERVICE_VERSION", "1.0.0"))
            service_meta.setdefault(
                "environment", os.getenv("ENVIRONMENT", "development")
            )

            # Convert metadata to tags (python-consul2 1.1.0 doesn't support 'meta' parameter)
            # Format: 'key:value'
            for key, value in service_meta.items():
                service_tags.append(f"{key}:{value}")

            # Build health check configuration
            check = None
            if health_check_url:
                check = consul.Check.http(
                    health_check_url,
                    interval=health_check_interval,
                    timeout=health_check_timeout,
                    deregister="30s",  # Deregister after 30s of failures
                )

            # Register service (note: 'meta' parameter not supported in python-consul2 1.1.0)
            self.client.agent.service.register(
                name=service_name,
                service_id=service_id,
                address=service_address,
                port=port,
                tags=service_tags,
                check=check,
            )

            self.registered_services.add(service_id)
            logger.info(
                f"✅ Registered service '{service_name}' (ID: {service_id}) "
                f"at {service_address}:{port}"
            )

            if health_check_url:
                logger.info(
                    f"   Health check: {health_check_url} "
                    f"(interval: {health_check_interval}, timeout: {health_check_timeout})"
                )

            return True

        except Exception as e:
            logger.error(
                f"❌ Failed to register service '{service_name}': {e}",
                exc_info=True,
            )
            return False

    def deregister_service(self, service_id: str) -> bool:
        """
        Deregister service from Consul.

        Args:
            service_id: Service instance ID to deregister

        Returns:
            True if deregistration successful, False otherwise
        """
        if not self.enabled or not self.client:
            logger.debug(f"Consul disabled - skipping deregistration for {service_id}")
            return False

        try:
            self.client.agent.service.deregister(service_id)
            self.registered_services.discard(service_id)
            logger.info(f"✅ Deregistered service: {service_id}")
            return True

        except Exception as e:
            logger.error(
                f"❌ Failed to deregister service '{service_id}': {e}",
                exc_info=True,
            )
            return False

    def discover_service(
        self,
        service_name: str,
        tag: Optional[str] = None,
        passing_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Discover service instances by name.

        Args:
            service_name: Service name to lookup
            tag: Filter by tag (optional)
            passing_only: Only return healthy instances (default: True)

        Returns:
            List of service instances with address and port
            Format: [{"address": "...", "port": ..., "tags": [...], "meta": {...}}]
        """
        if not self.enabled or not self.client:
            logger.debug(f"Consul disabled - returning empty list for {service_name}")
            return []

        try:
            # Query Consul for service instances
            index, services = self.client.health.service(
                service_name,
                tag=tag,
                passing=passing_only,
            )

            instances = []
            for service in services:
                service_info = service.get("Service", {})
                instances.append(
                    {
                        "service_id": service_info.get("ID"),
                        "address": service_info.get("Address"),
                        "port": service_info.get("Port"),
                        "tags": service_info.get("Tags", []),
                        "meta": service_info.get("Meta", {}),
                    }
                )

            logger.info(
                f"✅ Discovered {len(instances)} instance(s) of '{service_name}' "
                f"(passing_only={passing_only})"
            )

            return instances

        except Exception as e:
            logger.error(
                f"❌ Failed to discover service '{service_name}': {e}",
                exc_info=True,
            )
            return []

    def get_service_url(
        self,
        service_name: str,
        scheme: str = "http",
        tag: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get URL for first healthy service instance.

        Args:
            service_name: Service name to lookup
            scheme: URL scheme (http/https)
            tag: Filter by tag (optional)

        Returns:
            Service URL (e.g., "http://localhost:8053") or None if not found
        """
        instances = self.discover_service(service_name, tag=tag, passing_only=True)

        if not instances:
            logger.warning(f"⚠️  No healthy instances found for '{service_name}'")
            return None

        # Return first healthy instance
        instance = instances[0]
        address = instance["address"]
        port = instance["port"]

        return f"{scheme}://{address}:{port}"

    async def cleanup(self) -> None:
        """
        Cleanup: deregister all registered services.

        Should be called during application shutdown.
        """
        if not self.enabled or not self.client:
            return

        logger.info("🧹 Cleaning up Consul service registrations...")

        for service_id in list(self.registered_services):
            self.deregister_service(service_id)

        logger.info("✅ Consul cleanup complete")


# Singleton instance
_consul_service: Optional[ConsulService] = None


def get_consul_service() -> ConsulService:
    """
    Get or create Consul service singleton.

    Returns:
        ConsulService instance
    """
    global _consul_service

    if _consul_service is None:
        _consul_service = ConsulService()

    return _consul_service
