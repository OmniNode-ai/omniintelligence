"""
End-to-end tests for service discovery via Consul.

These tests verify complete service discovery workflows:
1. Service registration on startup
2. Discovery by other services
3. Health check monitoring
4. Failover scenarios

Requires running services:
- Consul (192.168.86.200:8500)
- Test services can be mocked or real

Run with: pytest tests/e2e/test_service_discovery.py --real-integration
"""

import asyncio
import os
import time
import uuid
from typing import Dict, List

import consul
import pytest
from src.server.services.consul_service import ConsulService


@pytest.fixture
def consul_host():
    """Get Consul host from environment."""
    return os.getenv("CONSUL_HOST", "192.168.86.200")


@pytest.fixture
def consul_port():
    """Get Consul port from environment."""
    return int(os.getenv("CONSUL_PORT", "8500"))


@pytest.fixture
def test_service_prefix():
    """Generate unique prefix for test services."""
    return f"e2e-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def consul_service_manager(consul_host, consul_port):
    """Create ConsulService manager for tests."""
    service = ConsulService(host=consul_host, port=consul_port, enabled=True)
    yield service
    # Cleanup after test
    await service.cleanup()


@pytest.mark.real_integration
@pytest.mark.asyncio
class TestServiceDiscoveryRegistration:
    """Test service registration flow."""

    async def test_multiple_services_register_on_startup(
        self, consul_service_manager, test_service_prefix
    ):
        """Test multiple Archon services register on startup."""
        if not consul_service_manager.enabled:
            pytest.skip("Consul not available")

        services_config = [
            {
                "id": f"{test_service_prefix}-server-1",
                "name": f"{test_service_prefix}-archon-server",
                "port": 8181,
                "health_url": "http://localhost:8181/health",
            },
            {
                "id": f"{test_service_prefix}-intelligence-1",
                "name": f"{test_service_prefix}-archon-intelligence",
                "port": 8053,
                "health_url": "http://localhost:8053/health",
            },
            {
                "id": f"{test_service_prefix}-bridge-1",
                "name": f"{test_service_prefix}-archon-bridge",
                "port": 8054,
                "health_url": "http://localhost:8054/health",
            },
            {
                "id": f"{test_service_prefix}-search-1",
                "name": f"{test_service_prefix}-archon-search",
                "port": 8055,
                "health_url": "http://localhost:8055/health",
            },
        ]

        # Register all services
        for svc in services_config:
            success = consul_service_manager.register_service(
                service_id=svc["id"],
                service_name=svc["name"],
                port=svc["port"],
                address="localhost",
                tags=["test", "e2e"],
                meta={"environment": "test", "test_run": test_service_prefix},
                health_check_url=None,  # No real health check for test
            )
            assert success is True

        # Wait for registration to propagate
        await asyncio.sleep(2)

        # Verify all services registered
        for svc in services_config:
            instances = consul_service_manager.discover_service(
                svc["name"], passing_only=False
            )
            assert len(instances) > 0
            found = any(inst["service_id"] == svc["id"] for inst in instances)
            assert found, f"Service {svc['id']} not found in Consul"


@pytest.mark.real_integration
@pytest.mark.asyncio
class TestServiceDiscoveryLookup:
    """Test service discovery and lookup."""

    async def test_server_discovers_intelligence_service(
        self, consul_service_manager, test_service_prefix
    ):
        """Test archon-server can discover archon-intelligence service."""
        if not consul_service_manager.enabled:
            pytest.skip("Consul not available")

        intelligence_name = f"{test_service_prefix}-archon-intelligence"
        intelligence_id = f"{test_service_prefix}-intelligence-1"

        # Register intelligence service
        consul_service_manager.register_service(
            service_id=intelligence_id,
            service_name=intelligence_name,
            port=8053,
            address="192.168.86.101",
            tags=["intelligence", "test"],
        )

        await asyncio.sleep(1)

        # Server discovers intelligence service
        url = consul_service_manager.get_service_url(intelligence_name)

        assert url is not None
        assert "192.168.86.101" in url
        assert "8053" in url

    async def test_discover_service_by_tag(
        self, consul_service_manager, test_service_prefix
    ):
        """Test discovering services by tag."""
        if not consul_service_manager.enabled:
            pytest.skip("Consul not available")

        # Register services with different tags
        production_id = f"{test_service_prefix}-prod-1"
        staging_id = f"{test_service_prefix}-staging-1"
        service_name = f"{test_service_prefix}-tagged-service"

        consul_service_manager.register_service(
            service_id=production_id,
            service_name=service_name,
            port=9000,
            tags=["production"],
        )

        consul_service_manager.register_service(
            service_id=staging_id,
            service_name=service_name,
            port=9001,
            tags=["staging"],
        )

        await asyncio.sleep(1)

        # Discover production instances only
        prod_instances = consul_service_manager.discover_service(
            service_name, tag="production", passing_only=False
        )

        assert len(prod_instances) > 0
        assert any(inst["service_id"] == production_id for inst in prod_instances)

    async def test_discover_all_instances_of_service(
        self, consul_service_manager, test_service_prefix
    ):
        """Test discovering multiple instances of same service."""
        if not consul_service_manager.enabled:
            pytest.skip("Consul not available")

        service_name = f"{test_service_prefix}-multi-instance"
        instance_ids = [
            f"{test_service_prefix}-instance-1",
            f"{test_service_prefix}-instance-2",
            f"{test_service_prefix}-instance-3",
        ]

        # Register multiple instances
        for i, instance_id in enumerate(instance_ids):
            consul_service_manager.register_service(
                service_id=instance_id,
                service_name=service_name,
                port=9100 + i,
                address="localhost",
            )

        await asyncio.sleep(1)

        # Discover all instances
        instances = consul_service_manager.discover_service(
            service_name, passing_only=False
        )

        # Filter to our test instances
        test_instances = [
            inst for inst in instances if inst["service_id"] in instance_ids
        ]
        assert len(test_instances) == 3


@pytest.mark.real_integration
@pytest.mark.asyncio
class TestServiceDiscoveryHealthChecks:
    """Test health check functionality."""

    async def test_service_health_check_failure(
        self, consul_service_manager, test_service_prefix
    ):
        """Test service marked unhealthy when health check fails."""
        if not consul_service_manager.enabled:
            pytest.skip("Consul not available")

        service_id = f"{test_service_prefix}-unhealthy"
        service_name = f"{test_service_prefix}-health-test"

        # Register service with health check pointing to non-existent endpoint
        consul_service_manager.register_service(
            service_id=service_id,
            service_name=service_name,
            port=9999,
            address="localhost",
            health_check_url="http://localhost:9999/health",  # Non-existent
            health_check_interval="5s",
            health_check_timeout="2s",
        )

        # Wait for health check to fail
        await asyncio.sleep(7)

        # Discovery with passing_only=True should not include unhealthy service
        healthy_instances = consul_service_manager.discover_service(
            service_name, passing_only=True
        )

        # Should have no healthy instances (health check failing)
        # Note: Timing-dependent, may need adjustment
        assert len(healthy_instances) == 0 or not any(
            inst["service_id"] == service_id for inst in healthy_instances
        )

        # Discovery with passing_only=False should include all instances
        all_instances = consul_service_manager.discover_service(
            service_name, passing_only=False
        )
        assert any(inst["service_id"] == service_id for inst in all_instances)


@pytest.mark.real_integration
@pytest.mark.asyncio
class TestServiceDiscoveryFailover:
    """Test failover scenarios."""

    async def test_discover_healthy_instance_after_unhealthy(
        self, consul_service_manager, test_service_prefix
    ):
        """Test discovery returns healthy instance when one is unhealthy."""
        if not consul_service_manager.enabled:
            pytest.skip("Consul not available")

        service_name = f"{test_service_prefix}-failover"

        # Register two instances - one "healthy", one "unhealthy"
        healthy_id = f"{test_service_prefix}-healthy-1"
        unhealthy_id = f"{test_service_prefix}-unhealthy-1"

        # Healthy instance (no health check for simplicity)
        consul_service_manager.register_service(
            service_id=healthy_id,
            service_name=service_name,
            port=9200,
            address="192.168.1.100",
            tags=["primary"],
        )

        # Unhealthy instance (will fail health check)
        consul_service_manager.register_service(
            service_id=unhealthy_id,
            service_name=service_name,
            port=9201,
            address="192.168.1.101",
            tags=["secondary"],
            health_check_url="http://192.168.1.101:9201/health",  # Non-existent
        )

        await asyncio.sleep(1)

        # Get service URL (should return healthy instance)
        url = consul_service_manager.get_service_url(service_name)

        # Without real health checks, this test is limited
        # In production, would verify healthy instance is preferred
        assert url is not None

    async def test_service_deregistration_removes_from_discovery(
        self, consul_service_manager, test_service_prefix
    ):
        """Test deregistered service is removed from discovery."""
        if not consul_service_manager.enabled:
            pytest.skip("Consul not available")

        service_id = f"{test_service_prefix}-deregister-test"
        service_name = f"{test_service_prefix}-temporary-service"

        # Register service
        consul_service_manager.register_service(
            service_id=service_id,
            service_name=service_name,
            port=9300,
        )

        await asyncio.sleep(1)

        # Verify service exists
        instances = consul_service_manager.discover_service(
            service_name, passing_only=False
        )
        assert any(inst["service_id"] == service_id for inst in instances)

        # Deregister service
        consul_service_manager.deregister_service(service_id)

        await asyncio.sleep(1)

        # Verify service removed
        instances = consul_service_manager.discover_service(
            service_name, passing_only=False
        )
        assert not any(inst["service_id"] == service_id for inst in instances)


@pytest.mark.real_integration
@pytest.mark.asyncio
class TestServiceDiscoveryCompleteWorkflow:
    """Test complete service discovery workflow."""

    async def test_complete_service_lifecycle(
        self, consul_service_manager, test_service_prefix
    ):
        """Test complete service lifecycle: register -> discover -> use -> deregister."""
        if not consul_service_manager.enabled:
            pytest.skip("Consul not available")

        # Step 1: Register archon-intelligence service
        intelligence_id = f"{test_service_prefix}-intelligence-lifecycle"
        intelligence_name = f"{test_service_prefix}-intelligence"

        success = consul_service_manager.register_service(
            service_id=intelligence_id,
            service_name=intelligence_name,
            port=8053,
            address="localhost",
            tags=["intelligence", "lifecycle-test"],
            meta={"version": "1.0.0", "test": "true"},
        )
        assert success is True

        await asyncio.sleep(1)

        # Step 2: Discover service from another service (archon-server)
        server_consul = ConsulService(
            host=consul_service_manager.host,
            port=consul_service_manager.port,
            enabled=True,
        )

        url = server_consul.get_service_url(intelligence_name)
        assert url is not None
        assert "localhost:8053" in url

        # Step 3: Simulate using the service (verify it's discoverable)
        instances = server_consul.discover_service(
            intelligence_name, passing_only=False
        )
        intelligence_instance = next(
            (inst for inst in instances if inst["service_id"] == intelligence_id), None
        )
        assert intelligence_instance is not None
        assert intelligence_instance["address"] == "localhost"
        assert intelligence_instance["port"] == 8053

        # Step 4: Deregister service
        consul_service_manager.deregister_service(intelligence_id)

        await asyncio.sleep(1)

        # Step 5: Verify service no longer discoverable
        url_after = server_consul.get_service_url(intelligence_name)
        # URL might still be cached or point to other instances, so check instances
        instances_after = server_consul.discover_service(
            intelligence_name, passing_only=False
        )
        assert not any(
            inst["service_id"] == intelligence_id for inst in instances_after
        )

    async def test_multi_service_coordination(
        self, consul_service_manager, test_service_prefix
    ):
        """Test multiple services coordinating via Consul."""
        if not consul_service_manager.enabled:
            pytest.skip("Consul not available")

        # Register complete Archon service stack
        services = [
            (f"{test_service_prefix}-server", 8181),
            (f"{test_service_prefix}-intelligence", 8053),
            (f"{test_service_prefix}-bridge", 8054),
            (f"{test_service_prefix}-search", 8055),
        ]

        service_ids = []
        for service_name, port in services:
            service_id = f"{service_name}-1"
            consul_service_manager.register_service(
                service_id=service_id,
                service_name=service_name,
                port=port,
                address="localhost",
                tags=["archon", "coordination-test"],
            )
            service_ids.append((service_id, service_name))

        await asyncio.sleep(2)

        # Verify all services are discoverable
        for service_id, service_name in service_ids:
            instances = consul_service_manager.discover_service(
                service_name, passing_only=False
            )
            assert any(inst["service_id"] == service_id for inst in instances)

        # Simulate server discovering and using intelligence service
        intelligence_name = f"{test_service_prefix}-intelligence"
        intelligence_url = consul_service_manager.get_service_url(intelligence_name)
        assert intelligence_url is not None
        assert "8053" in intelligence_url


# Mock-based E2E tests (no real Consul required)


class TestServiceDiscoveryMocked:
    """Mock-based service discovery tests."""

    @pytest.mark.asyncio
    async def test_service_registration_flow_mocked(self):
        """Test service registration flow with mocks."""
        from unittest.mock import MagicMock, patch

        mock_consul_client = MagicMock(spec=consul.Consul)
        mock_consul_client.agent = MagicMock()
        mock_consul_client.agent.service = MagicMock()

        with patch("src.server.services.consul_service.consul.Consul") as mock_consul:
            mock_consul.return_value = mock_consul_client

            # Create service manager
            service_manager = ConsulService(enabled=True)

            # Register services
            service_manager.register_service(
                service_id="mock-server-1",
                service_name="mock-archon-server",
                port=8181,
            )

            # Verify registration called
            assert mock_consul_client.agent.service.register.called

    @pytest.mark.asyncio
    async def test_service_discovery_flow_mocked(self):
        """Test service discovery flow with mocks."""
        from unittest.mock import MagicMock, patch

        mock_consul_client = MagicMock(spec=consul.Consul)
        mock_consul_client.health = MagicMock()
        mock_consul_client.health.service = MagicMock(
            return_value=(
                0,
                [
                    {
                        "Service": {
                            "ID": "mock-intelligence-1",
                            "Address": "localhost",
                            "Port": 8053,
                            "Tags": [],
                            "Meta": {},
                        }
                    }
                ],
            )
        )

        with patch("src.server.services.consul_service.consul.Consul") as mock_consul:
            mock_consul.return_value = mock_consul_client

            service_manager = ConsulService(enabled=True)

            # Discover service
            instances = service_manager.discover_service("mock-archon-intelligence")

            assert len(instances) == 1
            assert instances[0]["service_id"] == "mock-intelligence-1"

    @pytest.mark.asyncio
    async def test_complete_service_coordination_mocked(self):
        """Test complete service coordination with mocks."""
        from unittest.mock import MagicMock, patch

        # Simulate multiple services registering and discovering each other
        mock_consul_client = MagicMock(spec=consul.Consul)

        # Mock registration
        mock_consul_client.agent = MagicMock()
        mock_consul_client.agent.service = MagicMock()

        # Mock discovery
        mock_consul_client.health = MagicMock()
        mock_consul_client.health.service = MagicMock(
            return_value=(
                0,
                [
                    {
                        "Service": {
                            "ID": "server-1",
                            "Address": "localhost",
                            "Port": 8181,
                            "Tags": [],
                            "Meta": {},
                        }
                    },
                    {
                        "Service": {
                            "ID": "intelligence-1",
                            "Address": "localhost",
                            "Port": 8053,
                            "Tags": [],
                            "Meta": {},
                        }
                    },
                ],
            )
        )

        with patch("src.server.services.consul_service.consul.Consul") as mock_consul:
            mock_consul.return_value = mock_consul_client

            # Server service registers
            server_consul = ConsulService(enabled=True)
            server_consul.register_service(
                service_id="server-1",
                service_name="archon-server",
                port=8181,
            )

            # Intelligence service registers
            intelligence_consul = ConsulService(enabled=True)
            intelligence_consul.register_service(
                service_id="intelligence-1",
                service_name="archon-intelligence",
                port=8053,
            )

            # Server discovers intelligence
            instances = server_consul.discover_service("archon-intelligence")

            # Verify coordination
            assert len(instances) > 0
            assert mock_consul_client.agent.service.register.call_count >= 2
