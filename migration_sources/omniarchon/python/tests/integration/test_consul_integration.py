"""
Integration tests for Consul service discovery.

These tests require a running Consul instance and are marked with @pytest.mark.real_integration.
Run with: pytest tests/integration/test_consul_integration.py --real-integration

Tests cover:
1. Full registration workflow
2. Service discovery across services
3. Health check updates
4. Graceful degradation when Consul unavailable
5. Multi-service coordination
"""

import asyncio
import os
import time
from unittest.mock import patch

import consul
import pytest
from src.server.services.consul_service import ConsulService, get_consul_service


@pytest.fixture
def consul_host():
    """Get Consul host from environment (default: 192.168.86.200)."""
    return os.getenv("CONSUL_HOST", "192.168.86.200")


@pytest.fixture
def consul_port():
    """Get Consul port from environment (default: 8500)."""
    return int(os.getenv("CONSUL_PORT", "8500"))


@pytest.fixture
def consul_service_live(consul_host, consul_port):
    """Create ConsulService connected to real Consul instance."""
    service = ConsulService(host=consul_host, port=consul_port, enabled=True)
    yield service
    # Cleanup: deregister any services registered during test
    asyncio.run(service.cleanup())


@pytest.fixture
def unique_service_id():
    """Generate unique service ID for test isolation."""
    timestamp = int(time.time() * 1000)
    return f"test-service-{timestamp}"


@pytest.mark.real_integration
class TestConsulIntegrationRegistration:
    """Integration tests for service registration."""

    def test_register_and_discover_service(
        self, consul_service_live, unique_service_id
    ):
        """Test full registration and discovery workflow."""
        # Skip if Consul not available
        if not consul_service_live.enabled:
            pytest.skip("Consul not available")

        # Register service
        success = consul_service_live.register_service(
            service_id=unique_service_id,
            service_name="test-archon-service",
            port=9999,
            address="localhost",
            tags=["test", "integration"],
            meta={"test": "true", "purpose": "integration-testing"},
            health_check_url=None,  # No health check for simplicity
        )

        assert success is True
        assert unique_service_id in consul_service_live.registered_services

        # Give Consul time to register
        time.sleep(1)

        # Discover the service
        instances = consul_service_live.discover_service(
            "test-archon-service", passing_only=False  # No health check configured
        )

        assert len(instances) > 0
        found_service = next(
            (svc for svc in instances if svc["service_id"] == unique_service_id), None
        )
        assert found_service is not None
        assert found_service["address"] == "localhost"
        assert found_service["port"] == 9999

    def test_register_with_health_check(self, consul_service_live, unique_service_id):
        """Test service registration with health check."""
        if not consul_service_live.enabled:
            pytest.skip("Consul not available")

        # Register service with health check pointing to a non-existent endpoint
        # (health check will fail, but registration should succeed)
        success = consul_service_live.register_service(
            service_id=unique_service_id,
            service_name="test-health-check-service",
            port=9998,
            health_check_url="http://localhost:9998/health",
            health_check_interval="10s",
            health_check_timeout="5s",
        )

        assert success is True

        # Give Consul time to perform health check
        time.sleep(2)

        # Discover service (should exist even if unhealthy)
        instances = consul_service_live.discover_service(
            "test-health-check-service", passing_only=False
        )

        assert len(instances) > 0
        found_service = next(
            (svc for svc in instances if svc["service_id"] == unique_service_id), None
        )
        assert found_service is not None

    def test_deregister_service(self, consul_service_live, unique_service_id):
        """Test service deregistration."""
        if not consul_service_live.enabled:
            pytest.skip("Consul not available")

        # Register service
        consul_service_live.register_service(
            service_id=unique_service_id,
            service_name="test-deregister-service",
            port=9997,
        )

        time.sleep(1)

        # Verify service exists
        instances = consul_service_live.discover_service(
            "test-deregister-service", passing_only=False
        )
        assert any(svc["service_id"] == unique_service_id for svc in instances)

        # Deregister service
        success = consul_service_live.deregister_service(unique_service_id)
        assert success is True
        assert unique_service_id not in consul_service_live.registered_services

        time.sleep(1)

        # Verify service no longer exists
        instances = consul_service_live.discover_service(
            "test-deregister-service", passing_only=False
        )
        assert not any(svc["service_id"] == unique_service_id for svc in instances)


@pytest.mark.real_integration
class TestConsulIntegrationDiscovery:
    """Integration tests for service discovery."""

    def test_discover_multiple_instances(self, consul_service_live):
        """Test discovering multiple instances of same service."""
        if not consul_service_live.enabled:
            pytest.skip("Consul not available")

        timestamp = int(time.time() * 1000)
        service_ids = [
            f"test-multi-{timestamp}-1",
            f"test-multi-{timestamp}-2",
            f"test-multi-{timestamp}-3",
        ]

        # Register multiple instances
        for i, service_id in enumerate(service_ids):
            consul_service_live.register_service(
                service_id=service_id,
                service_name="test-multi-instance-service",
                port=9900 + i,
                address="localhost",
            )

        time.sleep(1)

        # Discover all instances
        instances = consul_service_live.discover_service(
            "test-multi-instance-service", passing_only=False
        )

        # Filter to only our test instances
        test_instances = [svc for svc in instances if svc["service_id"] in service_ids]
        assert len(test_instances) == 3

        # Verify ports are different
        ports = {svc["port"] for svc in test_instances}
        assert len(ports) == 3

    def test_discover_with_tag_filter(self, consul_service_live, unique_service_id):
        """Test service discovery with tag filtering."""
        if not consul_service_live.enabled:
            pytest.skip("Consul not available")

        # Register service with specific tag
        consul_service_live.register_service(
            service_id=unique_service_id,
            service_name="test-tagged-service",
            port=9996,
            tags=["production", "primary"],
        )

        time.sleep(1)

        # Discover with tag filter
        instances = consul_service_live.discover_service(
            "test-tagged-service", tag="production", passing_only=False
        )

        assert len(instances) > 0
        found_service = next(
            (svc for svc in instances if svc["service_id"] == unique_service_id), None
        )
        assert found_service is not None
        assert "production" in found_service["tags"]

    def test_get_service_url(self, consul_service_live, unique_service_id):
        """Test getting service URL from discovery."""
        if not consul_service_live.enabled:
            pytest.skip("Consul not available")

        # Register service
        consul_service_live.register_service(
            service_id=unique_service_id,
            service_name="test-url-service",
            port=9995,
            address="localhost",
        )

        time.sleep(1)

        # Get service URL
        url = consul_service_live.get_service_url("test-url-service")

        assert url is not None
        assert "localhost" in url
        assert "9995" in url


@pytest.mark.real_integration
class TestConsulIntegrationGracefulDegradation:
    """Integration tests for graceful degradation."""

    def test_service_continues_without_consul(self):
        """Test that application services can start when Consul unavailable."""
        # Create service with invalid Consul host
        service = ConsulService(host="invalid-host", port=8500, enabled=True)

        # Service should disable itself gracefully
        assert service.enabled is False
        assert service.client is None

        # Operations should return False/empty without raising exceptions
        result = service.register_service(
            service_id="test", service_name="test", port=8080
        )
        assert result is False

        instances = service.discover_service("test")
        assert instances == []

    def test_operations_when_disabled(self):
        """Test all operations work when Consul explicitly disabled."""
        service = ConsulService(enabled=False)

        # All operations should fail gracefully
        assert service.register_service("test", "test", 8080) is False
        assert service.deregister_service("test") is False
        assert service.discover_service("test") == []
        assert service.get_service_url("test") is None


@pytest.mark.real_integration
class TestConsulIntegrationCleanup:
    """Integration tests for cleanup functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_deregisters_all(self, consul_service_live):
        """Test cleanup deregisters all services."""
        if not consul_service_live.enabled:
            pytest.skip("Consul not available")

        timestamp = int(time.time() * 1000)
        service_ids = [
            f"test-cleanup-{timestamp}-1",
            f"test-cleanup-{timestamp}-2",
        ]

        # Register multiple services
        for service_id in service_ids:
            consul_service_live.register_service(
                service_id=service_id,
                service_name="test-cleanup-service",
                port=9990,
            )

        time.sleep(1)

        # Verify services registered
        instances = consul_service_live.discover_service(
            "test-cleanup-service", passing_only=False
        )
        assert any(svc["service_id"] in service_ids for svc in instances)

        # Cleanup
        await consul_service_live.cleanup()

        time.sleep(1)

        # Verify all services deregistered
        instances = consul_service_live.discover_service(
            "test-cleanup-service", passing_only=False
        )
        assert not any(svc["service_id"] in service_ids for svc in instances)


@pytest.mark.real_integration
class TestConsulIntegrationMultiService:
    """Integration tests for multi-service coordination."""

    def test_multiple_services_register_simultaneously(self, consul_service_live):
        """Test multiple services can register at the same time."""
        if not consul_service_live.enabled:
            pytest.skip("Consul not available")

        timestamp = int(time.time() * 1000)
        services = [
            {
                "id": f"test-server-{timestamp}",
                "name": "test-archon-server",
                "port": 8181,
            },
            {
                "id": f"test-intelligence-{timestamp}",
                "name": "test-archon-intelligence",
                "port": 8053,
            },
            {
                "id": f"test-bridge-{timestamp}",
                "name": "test-archon-bridge",
                "port": 8054,
            },
        ]

        # Register all services
        for svc in services:
            success = consul_service_live.register_service(
                service_id=svc["id"],
                service_name=svc["name"],
                port=svc["port"],
            )
            assert success is True

        time.sleep(1)

        # Verify all services discoverable
        for svc in services:
            instances = consul_service_live.discover_service(
                svc["name"], passing_only=False
            )
            assert any(inst["service_id"] == svc["id"] for inst in instances)

    def test_service_discovery_across_services(self, consul_service_live):
        """Test one service can discover another service."""
        if not consul_service_live.enabled:
            pytest.skip("Consul not available")

        timestamp = int(time.time() * 1000)

        # Register "intelligence" service
        intelligence_id = f"test-intelligence-{timestamp}"
        consul_service_live.register_service(
            service_id=intelligence_id,
            service_name="test-intelligence",
            port=8053,
            address="192.168.86.101",
        )

        time.sleep(1)

        # Create second ConsulService instance (simulating different service)
        server_consul = ConsulService(
            host=consul_service_live.host,
            port=consul_service_live.port,
            enabled=True,
        )

        # "Server" discovers "intelligence" service
        url = server_consul.get_service_url("test-intelligence")

        assert url is not None
        assert "192.168.86.101:8053" in url


@pytest.mark.real_integration
class TestConsulIntegrationMetadata:
    """Integration tests for metadata handling."""

    def test_metadata_conversion_to_tags(self, consul_service_live, unique_service_id):
        """Test metadata is properly converted to tags."""
        if not consul_service_live.enabled:
            pytest.skip("Consul not available")

        # Register with metadata
        consul_service_live.register_service(
            service_id=unique_service_id,
            service_name="test-metadata-service",
            port=9994,
            meta={
                "region": "us-west",
                "tier": "premium",
                "version": "2.0.0",
            },
        )

        time.sleep(1)

        # Discover and verify metadata in tags
        instances = consul_service_live.discover_service(
            "test-metadata-service", passing_only=False
        )

        found_service = next(
            (svc for svc in instances if svc["service_id"] == unique_service_id), None
        )
        assert found_service is not None

        # Metadata should be in tags as 'key:value'
        tags = found_service["tags"]
        assert any("region:us-west" in tag for tag in tags)
        assert any("tier:premium" in tag for tag in tags)
        assert any("version:2.0.0" in tag for tag in tags)


# Mock-based integration tests (no real Consul required)


class TestConsulIntegrationMocked:
    """Integration tests using mocks (no real Consul required)."""

    def test_application_startup_with_consul(self):
        """Test application can start with Consul registration."""
        # This simulates application startup sequence
        with patch("src.server.services.consul_service.consul.Consul") as mock_consul:
            mock_client = mock_consul.return_value
            mock_client.agent = type(
                "Agent",
                (),
                {
                    "service": type(
                        "Service", (), {"register": lambda *args, **kwargs: None}
                    )()
                },
            )()

            # Initialize Consul service
            consul_svc = ConsulService(enabled=True)

            # Register application services
            services = [
                ("archon-server-1", "archon-server", 8181),
                ("archon-intelligence-1", "archon-intelligence", 8053),
                ("archon-bridge-1", "archon-bridge", 8054),
                ("archon-search-1", "archon-search", 8055),
            ]

            for service_id, service_name, port in services:
                result = consul_svc.register_service(
                    service_id=service_id,
                    service_name=service_name,
                    port=port,
                    health_check_url=f"http://localhost:{port}/health",
                )
                assert result is True

            assert len(consul_svc.registered_services) == 4

    def test_application_startup_without_consul(self):
        """Test application can start when Consul unavailable."""
        # Simulate Consul connection failure
        with patch(
            "src.server.services.consul_service.consul.Consul",
            side_effect=Exception("Connection failed"),
        ):
            # Application should start successfully
            consul_svc = ConsulService(enabled=True)

            # Consul should be disabled
            assert consul_svc.enabled is False

            # Application continues with registration calls failing gracefully
            result = consul_svc.register_service(
                service_id="archon-server-1",
                service_name="archon-server",
                port=8181,
            )

            assert result is False
            # No exception raised - application continues
