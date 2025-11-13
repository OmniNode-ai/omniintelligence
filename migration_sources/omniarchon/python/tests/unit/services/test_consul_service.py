"""
Unit tests for ConsulService - Service discovery and registration.

Tests cover:
1. Service registration with health checks
2. Service deregistration
3. Service discovery by name
4. Graceful degradation when Consul unavailable
5. Health check configuration
6. Metadata and tags handling
7. URL construction for service discovery
"""

import os
from unittest.mock import MagicMock, Mock, patch

import consul
import pytest
from src.server.services.consul_service import ConsulService, get_consul_service


@pytest.fixture
def mock_consul_client():
    """Mock Consul client with agent API."""
    mock_client = MagicMock(spec=consul.Consul)

    # Mock agent service registration API
    mock_client.agent = MagicMock()
    mock_client.agent.service = MagicMock()
    mock_client.agent.service.register = MagicMock()
    mock_client.agent.service.deregister = MagicMock()

    # Mock health service API
    mock_client.health = MagicMock()
    mock_client.health.service = MagicMock(
        return_value=(
            0,
            [],
        )  # (index, services)
    )

    return mock_client


@pytest.fixture
def consul_service_enabled(mock_consul_client):
    """Create ConsulService with Consul enabled and mocked client."""
    with patch("src.server.services.consul_service.consul.Consul") as mock_consul:
        mock_consul.return_value = mock_consul_client
        service = ConsulService(host="localhost", port=8500, enabled=True)
        service.client = mock_consul_client
        return service


@pytest.fixture
def consul_service_disabled():
    """Create ConsulService with Consul disabled."""
    return ConsulService(enabled=False)


class TestConsulServiceInitialization:
    """Test Consul service initialization."""

    def test_initialization_enabled(self, mock_consul_client):
        """Test successful initialization with Consul enabled."""
        with patch("src.server.services.consul_service.consul.Consul") as mock_consul:
            mock_consul.return_value = mock_consul_client

            service = ConsulService(host="192.168.86.200", port=8500, enabled=True)

            assert service.enabled is True
            assert service.host == "192.168.86.200"
            assert service.port == 8500
            assert service.client is not None
            assert len(service.registered_services) == 0

    def test_initialization_disabled(self):
        """Test initialization with Consul disabled."""
        service = ConsulService(enabled=False)

        assert service.enabled is False
        assert service.client is None
        assert len(service.registered_services) == 0

    def test_initialization_with_env_vars(self, mock_consul_client):
        """Test initialization reads from environment variables."""
        with patch("src.server.services.consul_service.consul.Consul") as mock_consul:
            mock_consul.return_value = mock_consul_client

            with patch.dict(
                os.environ,
                {
                    "CONSUL_HOST": "custom-host",
                    "CONSUL_PORT": "9500",
                    "CONSUL_ENABLED": "true",
                },
                clear=False,
            ):
                service = ConsulService()

                assert service.host == "custom-host"
                assert service.port == 9500
                assert service.enabled is True

    def test_initialization_failure_disables_consul(self):
        """Test that Consul initialization failure disables service gracefully."""
        with patch(
            "src.server.services.consul_service.consul.Consul",
            side_effect=Exception("Connection failed"),
        ):
            service = ConsulService(enabled=True)

            assert service.enabled is False
            assert service.client is None


class TestConsulServiceRegistration:
    """Test service registration functionality."""

    def test_register_service_basic(self, consul_service_enabled, mock_consul_client):
        """Test basic service registration."""
        result = consul_service_enabled.register_service(
            service_id="archon-server-1",
            service_name="archon-server",
            port=8181,
            address="localhost",
        )

        assert result is True
        assert "archon-server-1" in consul_service_enabled.registered_services

        # Verify registration call
        mock_consul_client.agent.service.register.assert_called_once()
        call_kwargs = mock_consul_client.agent.service.register.call_args[1]
        assert call_kwargs["name"] == "archon-server"
        assert call_kwargs["service_id"] == "archon-server-1"
        assert call_kwargs["address"] == "localhost"
        assert call_kwargs["port"] == 8181

    def test_register_service_with_health_check(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test service registration with health check."""
        result = consul_service_enabled.register_service(
            service_id="archon-server-1",
            service_name="archon-server",
            port=8181,
            health_check_url="http://localhost:8181/health",
            health_check_interval="10s",
            health_check_timeout="5s",
        )

        assert result is True

        # Verify health check configured
        call_kwargs = mock_consul_client.agent.service.register.call_args[1]
        assert call_kwargs["check"] is not None

    def test_register_service_with_tags(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test service registration with tags."""
        result = consul_service_enabled.register_service(
            service_id="archon-server-1",
            service_name="archon-server",
            port=8181,
            tags=["production", "primary"],
        )

        assert result is True

        call_kwargs = mock_consul_client.agent.service.register.call_args[1]
        assert "production" in call_kwargs["tags"]
        assert "primary" in call_kwargs["tags"]

    def test_register_service_with_metadata(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test service registration with metadata converted to tags."""
        result = consul_service_enabled.register_service(
            service_id="archon-server-1",
            service_name="archon-server",
            port=8181,
            meta={"region": "us-west", "tier": "premium"},
        )

        assert result is True

        call_kwargs = mock_consul_client.agent.service.register.call_args[1]
        # Metadata should be converted to 'key:value' tags
        assert any("region:us-west" in tag for tag in call_kwargs["tags"])
        assert any("tier:premium" in tag for tag in call_kwargs["tags"])

    def test_register_service_with_default_metadata(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test service registration adds default metadata."""
        with patch.dict(
            os.environ,
            {"SERVICE_VERSION": "2.0.0", "ENVIRONMENT": "staging"},
            clear=False,
        ):
            result = consul_service_enabled.register_service(
                service_id="archon-server-1",
                service_name="archon-server",
                port=8181,
            )

            assert result is True

            call_kwargs = mock_consul_client.agent.service.register.call_args[1]
            # Default metadata should be added as tags
            assert any("version:2.0.0" in tag for tag in call_kwargs["tags"])
            assert any("environment:staging" in tag for tag in call_kwargs["tags"])

    def test_register_service_when_disabled(self, consul_service_disabled):
        """Test registration returns False when Consul disabled."""
        result = consul_service_disabled.register_service(
            service_id="archon-server-1",
            service_name="archon-server",
            port=8181,
        )

        assert result is False
        assert len(consul_service_disabled.registered_services) == 0

    def test_register_service_failure(self, consul_service_enabled, mock_consul_client):
        """Test service registration failure handling."""
        mock_consul_client.agent.service.register.side_effect = Exception(
            "Registration failed"
        )

        result = consul_service_enabled.register_service(
            service_id="archon-server-1",
            service_name="archon-server",
            port=8181,
        )

        assert result is False
        assert "archon-server-1" not in consul_service_enabled.registered_services


class TestConsulServiceDeregistration:
    """Test service deregistration functionality."""

    def test_deregister_service_success(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test successful service deregistration."""
        # Pre-register a service
        consul_service_enabled.registered_services.add("archon-server-1")

        result = consul_service_enabled.deregister_service("archon-server-1")

        assert result is True
        assert "archon-server-1" not in consul_service_enabled.registered_services

        mock_consul_client.agent.service.deregister.assert_called_once_with(
            "archon-server-1"
        )

    def test_deregister_service_when_disabled(self, consul_service_disabled):
        """Test deregistration returns False when Consul disabled."""
        result = consul_service_disabled.deregister_service("archon-server-1")

        assert result is False

    def test_deregister_service_failure(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test service deregistration failure handling."""
        consul_service_enabled.registered_services.add("archon-server-1")
        mock_consul_client.agent.service.deregister.side_effect = Exception(
            "Deregistration failed"
        )

        result = consul_service_enabled.deregister_service("archon-server-1")

        assert result is False


class TestConsulServiceDiscovery:
    """Test service discovery functionality."""

    def test_discover_service_success(self, consul_service_enabled, mock_consul_client):
        """Test successful service discovery."""
        mock_consul_client.health.service.return_value = (
            0,
            [
                {
                    "Service": {
                        "ID": "archon-intelligence-1",
                        "Address": "localhost",
                        "Port": 8053,
                        "Tags": ["production"],
                        "Meta": {"version": "1.0.0"},
                    }
                }
            ],
        )

        result = consul_service_enabled.discover_service("archon-intelligence")

        assert len(result) == 1
        assert result[0]["service_id"] == "archon-intelligence-1"
        assert result[0]["address"] == "localhost"
        assert result[0]["port"] == 8053
        assert "production" in result[0]["tags"]
        assert result[0]["meta"]["version"] == "1.0.0"

    def test_discover_service_with_tag_filter(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test service discovery with tag filtering."""
        mock_consul_client.health.service.return_value = (0, [])

        result = consul_service_enabled.discover_service(
            "archon-server", tag="production", passing_only=True
        )

        assert result == []

        # Verify tag filter passed to Consul
        mock_consul_client.health.service.assert_called_once_with(
            "archon-server", tag="production", passing=True
        )

    def test_discover_service_when_disabled(self, consul_service_disabled):
        """Test discovery returns empty list when Consul disabled."""
        result = consul_service_disabled.discover_service("archon-server")

        assert result == []

    def test_discover_service_failure(self, consul_service_enabled, mock_consul_client):
        """Test service discovery failure handling."""
        mock_consul_client.health.service.side_effect = Exception("Discovery failed")

        result = consul_service_enabled.discover_service("archon-server")

        assert result == []

    def test_discover_service_multiple_instances(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test discovering multiple service instances."""
        mock_consul_client.health.service.return_value = (
            0,
            [
                {
                    "Service": {
                        "ID": "archon-server-1",
                        "Address": "localhost",
                        "Port": 8181,
                        "Tags": [],
                        "Meta": {},
                    }
                },
                {
                    "Service": {
                        "ID": "archon-server-2",
                        "Address": "192.168.1.100",
                        "Port": 8181,
                        "Tags": [],
                        "Meta": {},
                    }
                },
            ],
        )

        result = consul_service_enabled.discover_service("archon-server")

        assert len(result) == 2
        assert result[0]["service_id"] == "archon-server-1"
        assert result[1]["service_id"] == "archon-server-2"


class TestConsulServiceURL:
    """Test service URL construction."""

    def test_get_service_url_success(self, consul_service_enabled, mock_consul_client):
        """Test getting service URL for healthy instance."""
        mock_consul_client.health.service.return_value = (
            0,
            [
                {
                    "Service": {
                        "ID": "archon-intelligence-1",
                        "Address": "localhost",
                        "Port": 8053,
                        "Tags": [],
                        "Meta": {},
                    }
                }
            ],
        )

        result = consul_service_enabled.get_service_url("archon-intelligence")

        assert result == "http://localhost:8053"

    def test_get_service_url_https(self, consul_service_enabled, mock_consul_client):
        """Test getting service URL with HTTPS scheme."""
        mock_consul_client.health.service.return_value = (
            0,
            [
                {
                    "Service": {
                        "ID": "archon-intelligence-1",
                        "Address": "api.example.com",
                        "Port": 443,
                        "Tags": [],
                        "Meta": {},
                    }
                }
            ],
        )

        result = consul_service_enabled.get_service_url(
            "archon-intelligence", scheme="https"
        )

        assert result == "https://api.example.com:443"

    def test_get_service_url_no_instances(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test get_service_url returns None when no healthy instances."""
        mock_consul_client.health.service.return_value = (0, [])

        result = consul_service_enabled.get_service_url("archon-server")

        assert result is None

    def test_get_service_url_with_tag(self, consul_service_enabled, mock_consul_client):
        """Test getting service URL with tag filter."""
        mock_consul_client.health.service.return_value = (
            0,
            [
                {
                    "Service": {
                        "ID": "archon-server-prod",
                        "Address": "prod.example.com",
                        "Port": 8181,
                        "Tags": ["production"],
                        "Meta": {},
                    }
                }
            ],
        )

        result = consul_service_enabled.get_service_url(
            "archon-server", tag="production"
        )

        assert result == "http://prod.example.com:8181"


class TestConsulServiceCleanup:
    """Test cleanup functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_deregisters_all_services(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test cleanup deregisters all registered services."""
        # Register multiple services
        consul_service_enabled.registered_services.add("archon-server-1")
        consul_service_enabled.registered_services.add("archon-intelligence-1")
        consul_service_enabled.registered_services.add("archon-bridge-1")

        await consul_service_enabled.cleanup()

        # All services should be deregistered
        assert len(consul_service_enabled.registered_services) == 0
        assert mock_consul_client.agent.service.deregister.call_count == 3

    @pytest.mark.asyncio
    async def test_cleanup_when_disabled(self, consul_service_disabled):
        """Test cleanup does nothing when Consul disabled."""
        await consul_service_disabled.cleanup()
        # Should complete without errors

    @pytest.mark.asyncio
    async def test_cleanup_with_deregistration_failures(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test cleanup continues even when deregistration fails."""
        consul_service_enabled.registered_services.add("archon-server-1")
        consul_service_enabled.registered_services.add("archon-intelligence-1")

        # First deregistration fails, second succeeds
        mock_consul_client.agent.service.deregister.side_effect = [
            Exception("Deregistration failed"),
            None,
        ]

        await consul_service_enabled.cleanup()

        # All services attempted deregistration
        assert mock_consul_client.agent.service.deregister.call_count == 2


class TestConsulServiceSingleton:
    """Test global singleton pattern."""

    def test_get_consul_service_creates_singleton(self):
        """Test get_consul_service creates and returns singleton."""
        # Reset singleton
        import src.server.services.consul_service as consul_module

        consul_module._consul_service = None

        service1 = get_consul_service()
        service2 = get_consul_service()

        assert service1 is service2  # Same instance

    def test_singleton_instance_configuration(self):
        """Test singleton instance uses environment configuration."""
        import src.server.services.consul_service as consul_module

        consul_module._consul_service = None

        with patch.dict(
            os.environ,
            {"CONSUL_ENABLED": "false"},
            clear=False,
        ):
            service = get_consul_service()

            assert service.enabled is False


class TestConsulServiceEdgeCases:
    """Test edge cases and error scenarios."""

    def test_register_service_with_none_address(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test registration defaults to localhost when address is None."""
        consul_service_enabled.register_service(
            service_id="test-service",
            service_name="test",
            port=8080,
            address=None,
        )

        call_kwargs = mock_consul_client.agent.service.register.call_args[1]
        assert call_kwargs["address"] == "localhost"

    def test_register_service_with_empty_tags(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test registration with empty tags list."""
        consul_service_enabled.register_service(
            service_id="test-service",
            service_name="test",
            port=8080,
            tags=[],
        )

        call_kwargs = mock_consul_client.agent.service.register.call_args[1]
        # Should still have default metadata tags
        assert len(call_kwargs["tags"]) > 0

    def test_health_check_configuration(self, consul_service_enabled):
        """Test health check is properly configured."""
        with patch("src.server.services.consul_service.consul.Check") as mock_check:
            mock_http_check = MagicMock()
            mock_check.http.return_value = mock_http_check

            consul_service_enabled.register_service(
                service_id="test-service",
                service_name="test",
                port=8080,
                health_check_url="http://localhost:8080/health",
                health_check_interval="15s",
                health_check_timeout="10s",
            )

            # Verify Check.http called with correct parameters
            mock_check.http.assert_called_once_with(
                "http://localhost:8080/health",
                interval="15s",
                timeout="10s",
                deregister="30s",
            )

    def test_deregister_nonexistent_service(
        self, consul_service_enabled, mock_consul_client
    ):
        """Test deregistering a service that wasn't registered."""
        result = consul_service_enabled.deregister_service("nonexistent-service")

        # Should still call deregister (Consul handles nonexistent gracefully)
        assert result is True
        mock_consul_client.agent.service.deregister.assert_called_once_with(
            "nonexistent-service"
        )
