"""
Integration Test: Platform Health API
Tests GET /api/intelligence/platform/health endpoint

Tests the platform health endpoint that aggregates health from:
- Database (PostgreSQL)
- Kafka (message broker)
- All Omniarchon services
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestPlatformHealthEndpoint:
    """Integration tests for Platform Health API endpoint."""

    @pytest.mark.asyncio
    async def test_platform_health_success(self):
        """Test successful platform health check with all services healthy."""
        from app import app

        client = TestClient(app)

        # Mock health monitor
        with patch(
            "src.api.platform.service.get_health_monitor"
        ) as mock_get_health_monitor:
            # Create mock health monitor
            mock_monitor = MagicMock()

            # Create mock infrastructure health response
            from archon_services.health_monitor import (
                HealthStatus,
                InfrastructureHealthResponse,
                ServiceHealth,
            )

            mock_infra_health = InfrastructureHealthResponse(
                overall_status=HealthStatus.HEALTHY,
                services=[
                    ServiceHealth(
                        service="postgresql",
                        status=HealthStatus.HEALTHY,
                        response_time_ms=15.5,
                        message="PostgreSQL healthy with 34 tables",
                        details={
                            "database": "omninode_bridge",
                            "table_count": 34,
                            "database_size_mb": 125.7,
                        },
                        last_checked=datetime.now(timezone.utc),
                    ),
                    ServiceHealth(
                        service="kafka",
                        status=HealthStatus.HEALTHY,
                        response_time_ms=8.2,
                        message="Kafka healthy with 2 brokers, 15 topics",
                        details={
                            "broker_count": 2,
                            "topic_count": 15,
                        },
                        last_checked=datetime.now(timezone.utc),
                    ),
                    ServiceHealth(
                        service="qdrant",
                        status=HealthStatus.HEALTHY,
                        response_time_ms=12.3,
                        message="Qdrant healthy with 3 collections",
                        details={
                            "collections_count": 3,
                        },
                        last_checked=datetime.now(timezone.utc),
                    ),
                ],
                total_response_time_ms=45.8,
                healthy_count=3,
                degraded_count=0,
                unhealthy_count=0,
                checked_at=datetime.now(timezone.utc),
            )

            # Configure mock
            mock_monitor.check_all_services = AsyncMock(return_value=mock_infra_health)
            mock_get_health_monitor.return_value = mock_monitor

            # Make request
            response = client.get("/api/intelligence/platform/health")

            # Verify response
            assert response.status_code == 200
            data = response.json()

            # Verify structure
            assert "overall_status" in data
            assert "database" in data
            assert "kafka" in data
            assert "services" in data
            assert "total_response_time_ms" in data
            assert "checked_at" in data
            assert "healthy_count" in data
            assert "degraded_count" in data
            assert "unhealthy_count" in data

            # Verify overall status
            assert data["overall_status"] == "healthy"

            # Verify database health
            assert data["database"]["status"] == "healthy"
            assert data["database"]["latency_ms"] == 15.5
            assert "database" in data["database"]["details"]

            # Verify Kafka health
            assert data["kafka"]["status"] == "healthy"
            assert data["kafka"]["lag"] == 0

            # Verify services list
            assert len(data["services"]) >= 3
            service_names = [s["name"] for s in data["services"]]
            assert "postgresql" in service_names
            assert "kafka" in service_names
            assert "qdrant" in service_names

    @pytest.mark.asyncio
    async def test_platform_health_with_degraded_service(self):
        """Test platform health with degraded service."""
        from app import app

        client = TestClient(app)

        with patch(
            "src.api.platform.service.get_health_monitor"
        ) as mock_get_health_monitor:
            from archon_services.health_monitor import (
                HealthStatus,
                InfrastructureHealthResponse,
                ServiceHealth,
            )

            # Mock with one degraded service
            mock_infra_health = InfrastructureHealthResponse(
                overall_status=HealthStatus.DEGRADED,
                services=[
                    ServiceHealth(
                        service="postgresql",
                        status=HealthStatus.HEALTHY,
                        response_time_ms=15.5,
                        message="PostgreSQL healthy",
                        last_checked=datetime.now(timezone.utc),
                    ),
                    ServiceHealth(
                        service="kafka",
                        status=HealthStatus.DEGRADED,
                        response_time_ms=150.0,
                        message="Kafka slow response",
                        last_checked=datetime.now(timezone.utc),
                    ),
                ],
                total_response_time_ms=165.5,
                healthy_count=1,
                degraded_count=1,
                unhealthy_count=0,
                checked_at=datetime.now(timezone.utc),
            )

            mock_monitor = MagicMock()
            mock_monitor.check_all_services = AsyncMock(return_value=mock_infra_health)
            mock_get_health_monitor.return_value = mock_monitor

            response = client.get("/api/intelligence/platform/health")

            assert response.status_code == 200
            data = response.json()

            # Verify degraded status propagates to overall
            assert data["overall_status"] == "degraded"
            assert data["degraded_count"] >= 1

    @pytest.mark.asyncio
    async def test_platform_health_with_cache(self):
        """Test platform health with caching enabled."""
        from app import app

        client = TestClient(app)

        with patch(
            "src.api.platform.service.get_health_monitor"
        ) as mock_get_health_monitor:
            from archon_services.health_monitor import (
                HealthStatus,
                InfrastructureHealthResponse,
                ServiceHealth,
            )

            mock_infra_health = InfrastructureHealthResponse(
                overall_status=HealthStatus.HEALTHY,
                services=[
                    ServiceHealth(
                        service="postgresql",
                        status=HealthStatus.HEALTHY,
                        response_time_ms=15.5,
                        message="PostgreSQL healthy",
                        last_checked=datetime.now(timezone.utc),
                    ),
                ],
                total_response_time_ms=15.5,
                healthy_count=1,
                degraded_count=0,
                unhealthy_count=0,
                checked_at=datetime.now(timezone.utc),
            )

            mock_monitor = MagicMock()
            mock_monitor.check_all_services = AsyncMock(return_value=mock_infra_health)
            mock_get_health_monitor.return_value = mock_monitor

            # Request with cache enabled
            response = client.get("/api/intelligence/platform/health?use_cache=true")

            assert response.status_code == 200

            # Verify cache parameter was passed
            mock_monitor.check_all_services.assert_called_once_with(use_cache=True)

    @pytest.mark.asyncio
    async def test_platform_health_without_cache(self):
        """Test platform health with caching disabled."""
        from app import app

        client = TestClient(app)

        with patch(
            "src.api.platform.service.get_health_monitor"
        ) as mock_get_health_monitor:
            from archon_services.health_monitor import (
                HealthStatus,
                InfrastructureHealthResponse,
                ServiceHealth,
            )

            mock_infra_health = InfrastructureHealthResponse(
                overall_status=HealthStatus.HEALTHY,
                services=[
                    ServiceHealth(
                        service="postgresql",
                        status=HealthStatus.HEALTHY,
                        response_time_ms=15.5,
                        message="PostgreSQL healthy",
                        last_checked=datetime.now(timezone.utc),
                    ),
                ],
                total_response_time_ms=15.5,
                healthy_count=1,
                degraded_count=0,
                unhealthy_count=0,
                checked_at=datetime.now(timezone.utc),
            )

            mock_monitor = MagicMock()
            mock_monitor.check_all_services = AsyncMock(return_value=mock_infra_health)
            mock_get_health_monitor.return_value = mock_monitor

            # Request with cache disabled
            response = client.get("/api/intelligence/platform/health?use_cache=false")

            assert response.status_code == 200

            # Verify cache parameter was passed
            mock_monitor.check_all_services.assert_called_once_with(use_cache=False)

    @pytest.mark.asyncio
    async def test_platform_health_service_count(self):
        """Test that platform health returns all expected services."""
        from app import app

        client = TestClient(app)

        with patch(
            "src.api.platform.service.get_health_monitor"
        ) as mock_get_health_monitor:
            from archon_services.health_monitor import (
                HealthStatus,
                InfrastructureHealthResponse,
                ServiceHealth,
            )

            mock_infra_health = InfrastructureHealthResponse(
                overall_status=HealthStatus.HEALTHY,
                services=[
                    ServiceHealth(
                        service="postgresql",
                        status=HealthStatus.HEALTHY,
                        response_time_ms=15.5,
                        message="PostgreSQL healthy",
                        last_checked=datetime.now(timezone.utc),
                    ),
                    ServiceHealth(
                        service="kafka",
                        status=HealthStatus.HEALTHY,
                        response_time_ms=8.2,
                        message="Kafka healthy",
                        last_checked=datetime.now(timezone.utc),
                    ),
                    ServiceHealth(
                        service="qdrant",
                        status=HealthStatus.HEALTHY,
                        response_time_ms=12.3,
                        message="Qdrant healthy",
                        last_checked=datetime.now(timezone.utc),
                    ),
                ],
                total_response_time_ms=36.0,
                healthy_count=3,
                degraded_count=0,
                unhealthy_count=0,
                checked_at=datetime.now(timezone.utc),
            )

            mock_monitor = MagicMock()
            mock_monitor.check_all_services = AsyncMock(return_value=mock_infra_health)
            mock_get_health_monitor.return_value = mock_monitor

            response = client.get("/api/intelligence/platform/health")

            assert response.status_code == 200
            data = response.json()

            # Verify we have services including synthetic ones
            assert len(data["services"]) >= 7  # At least 7 Omniarchon services

            # Verify expected Omniarchon services are present
            service_names = [s["name"] for s in data["services"]]
            expected_services = [
                "postgresql",
                "kafka",
                "qdrant",
                "archon-intelligence",
                "archon-server",
            ]

            for service_name in expected_services:
                assert any(
                    service_name in name for name in service_names
                ), f"Expected service {service_name} not found in services list"
