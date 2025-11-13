"""
Tests for Health Monitor Service

Tests infrastructure health monitoring for:
- Qdrant vector database
- PostgreSQL database
- Kafka message broker
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest
from aiokafka.errors import KafkaConnectionError
from archon_services.health_monitor import (
    HealthMonitor,
    HealthStatus,
    InfrastructureHealthResponse,
    ServiceHealth,
    get_health_monitor,
)
from asyncpg.exceptions import PostgresConnectionError
from qdrant_client.http.exceptions import UnexpectedResponse


@pytest.fixture
def health_monitor():
    """Create a health monitor instance for testing."""
    return HealthMonitor(
        qdrant_host="localhost",
        qdrant_port=6333,
        postgres_host="localhost",
        postgres_port=5436,
        postgres_database="test_db",
        postgres_user="test_user",
        postgres_password="test_password",
        kafka_bootstrap_servers="localhost:9092",
        cache_ttl=30,
    )


@pytest.mark.asyncio
async def test_check_qdrant_health_success(health_monitor):
    """Test successful Qdrant health check."""
    # Mock Qdrant client and collections
    mock_collection = MagicMock()
    mock_collection.name = "test_collection"

    mock_collections_response = MagicMock()
    mock_collections_response.collections = [mock_collection]

    mock_collection_info = MagicMock()
    mock_collection_info.points_count = 100
    mock_collection_info.vectors_count = 100

    mock_qdrant_client = AsyncMock()
    mock_qdrant_client.get_collections.return_value = mock_collections_response
    mock_qdrant_client.get_collection.return_value = mock_collection_info

    health_monitor.qdrant_client = mock_qdrant_client

    # Run health check
    result = await health_monitor.check_qdrant_health()

    # Assertions
    assert result.service == "qdrant"
    assert result.status == HealthStatus.HEALTHY
    assert result.response_time_ms > 0
    assert "healthy" in result.message.lower()
    assert result.details is not None
    assert result.details["collections_count"] == 1
    assert result.details["host"] == "localhost"
    assert result.details["port"] == 6333


@pytest.mark.asyncio
async def test_check_qdrant_health_failure(health_monitor):
    """Test Qdrant health check failure."""
    # Mock Qdrant client with connection failure
    mock_qdrant_client = AsyncMock()
    mock_qdrant_client.get_collections.side_effect = UnexpectedResponse(
        status_code=500,
        reason_phrase="Internal Server Error",
        content=b"Internal Server Error",
        headers=httpx.Headers({"content-type": "text/plain"}),
    )

    health_monitor.qdrant_client = mock_qdrant_client

    # Run health check
    result = await health_monitor.check_qdrant_health()

    # Assertions
    assert result.service == "qdrant"
    assert result.status == HealthStatus.UNHEALTHY
    assert result.response_time_ms > 0
    assert "failed" in result.message.lower()
    assert result.error is not None


@pytest.mark.asyncio
async def test_check_postgres_health_success(health_monitor):
    """Test successful PostgreSQL health check."""
    # Mock asyncpg connection
    mock_conn = AsyncMock()
    mock_conn.fetchval.side_effect = [
        1,  # SELECT 1 test query
        1024 * 1024,  # Database size in bytes
        10,  # Table count
    ]

    with patch("asyncpg.connect", return_value=mock_conn):
        # Run health check
        result = await health_monitor.check_postgres_health()

        # Assertions
        assert result.service == "postgresql"
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms > 0
        assert "healthy" in result.message.lower()
        assert result.details is not None
        assert result.details["table_count"] == 10
        assert result.details["database"] == "test_db"
        assert result.details["database_size_mb"] == 1.0

        # Verify connection was closed
        mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_check_postgres_health_connection_failure(health_monitor):
    """Test PostgreSQL health check connection failure."""
    with patch(
        "asyncpg.connect",
        side_effect=PostgresConnectionError("Connection refused"),
    ):
        # Run health check
        result = await health_monitor.check_postgres_health()

        # Assertions
        assert result.service == "postgresql"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.response_time_ms > 0
        assert "failed" in result.message.lower()
        assert result.error is not None


@pytest.mark.asyncio
async def test_check_kafka_health_success(health_monitor):
    """Test successful Kafka health check."""
    # Mock Kafka producer and cluster metadata
    mock_broker = MagicMock()
    mock_topic = MagicMock()

    mock_metadata = MagicMock()
    mock_metadata.brokers.return_value = [mock_broker, mock_broker]
    mock_metadata.topics.return_value = [mock_topic, mock_topic, mock_topic]

    mock_producer = AsyncMock()
    mock_producer.client.fetch_all_metadata.return_value = mock_metadata

    with patch(
        "archon_services.health_monitor.AIOKafkaProducer", return_value=mock_producer
    ):
        # Run health check
        result = await health_monitor.check_kafka_health()

        # Assertions
        assert result.service == "kafka"
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms > 0
        assert "healthy" in result.message.lower()
        assert result.details is not None
        assert result.details["broker_count"] == 2
        assert result.details["topic_count"] == 3

        # Verify producer was started and stopped
        mock_producer.start.assert_called_once()
        mock_producer.stop.assert_called_once()


@pytest.mark.asyncio
async def test_check_kafka_health_connection_failure(health_monitor):
    """Test Kafka health check connection failure."""
    mock_producer = AsyncMock()
    mock_producer.start.side_effect = KafkaConnectionError(
        "Cannot connect to Kafka broker"
    )

    with patch(
        "archon_services.health_monitor.AIOKafkaProducer", return_value=mock_producer
    ):
        # Run health check
        result = await health_monitor.check_kafka_health()

        # Assertions
        assert result.service == "kafka"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.response_time_ms > 0
        assert "failed" in result.message.lower()
        assert result.error is not None

        # Verify producer stop was called in finally block (even when start fails)
        mock_producer.stop.assert_called_once()


@pytest.mark.asyncio
async def test_check_all_services_all_healthy(health_monitor):
    """Test check_all_services when all services are healthy."""
    # Mock all service checks to return healthy
    with (
        patch.object(
            health_monitor,
            "check_qdrant_health",
            return_value=ServiceHealth(
                service="qdrant",
                status=HealthStatus.HEALTHY,
                response_time_ms=50.0,
                message="Qdrant healthy",
                last_checked=datetime.now(timezone.utc),
            ),
        ),
        patch.object(
            health_monitor,
            "check_postgres_health",
            return_value=ServiceHealth(
                service="postgresql",
                status=HealthStatus.HEALTHY,
                response_time_ms=30.0,
                message="PostgreSQL healthy",
                last_checked=datetime.now(timezone.utc),
            ),
        ),
        patch.object(
            health_monitor,
            "check_kafka_health",
            return_value=ServiceHealth(
                service="kafka",
                status=HealthStatus.HEALTHY,
                response_time_ms=40.0,
                message="Kafka healthy",
                last_checked=datetime.now(timezone.utc),
            ),
        ),
    ):
        # Run health check
        result = await health_monitor.check_all_services(use_cache=False)

        # Assertions
        assert isinstance(result, InfrastructureHealthResponse)
        assert result.overall_status == HealthStatus.HEALTHY
        assert len(result.services) == 3
        assert result.healthy_count == 3
        assert result.degraded_count == 0
        assert result.unhealthy_count == 0
        assert result.total_response_time_ms > 0


@pytest.mark.asyncio
async def test_check_all_services_one_unhealthy(health_monitor):
    """Test check_all_services when one service is unhealthy."""
    # Mock Qdrant as unhealthy, others healthy
    with (
        patch.object(
            health_monitor,
            "check_qdrant_health",
            return_value=ServiceHealth(
                service="qdrant",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=50.0,
                message="Qdrant connection failed",
                error="Connection refused",
                last_checked=datetime.now(timezone.utc),
            ),
        ),
        patch.object(
            health_monitor,
            "check_postgres_health",
            return_value=ServiceHealth(
                service="postgresql",
                status=HealthStatus.HEALTHY,
                response_time_ms=30.0,
                message="PostgreSQL healthy",
                last_checked=datetime.now(timezone.utc),
            ),
        ),
        patch.object(
            health_monitor,
            "check_kafka_health",
            return_value=ServiceHealth(
                service="kafka",
                status=HealthStatus.HEALTHY,
                response_time_ms=40.0,
                message="Kafka healthy",
                last_checked=datetime.now(timezone.utc),
            ),
        ),
    ):
        # Run health check
        result = await health_monitor.check_all_services(use_cache=False)

        # Assertions
        assert result.overall_status == HealthStatus.UNHEALTHY
        assert result.healthy_count == 2
        assert result.degraded_count == 0
        assert result.unhealthy_count == 1


@pytest.mark.asyncio
async def test_check_all_services_one_degraded(health_monitor):
    """Test check_all_services when one service is degraded."""
    # Mock PostgreSQL as degraded, others healthy
    with (
        patch.object(
            health_monitor,
            "check_qdrant_health",
            return_value=ServiceHealth(
                service="qdrant",
                status=HealthStatus.HEALTHY,
                response_time_ms=50.0,
                message="Qdrant healthy",
                last_checked=datetime.now(timezone.utc),
            ),
        ),
        patch.object(
            health_monitor,
            "check_postgres_health",
            return_value=ServiceHealth(
                service="postgresql",
                status=HealthStatus.DEGRADED,
                response_time_ms=500.0,
                message="PostgreSQL slow but working",
                last_checked=datetime.now(timezone.utc),
            ),
        ),
        patch.object(
            health_monitor,
            "check_kafka_health",
            return_value=ServiceHealth(
                service="kafka",
                status=HealthStatus.HEALTHY,
                response_time_ms=40.0,
                message="Kafka healthy",
                last_checked=datetime.now(timezone.utc),
            ),
        ),
    ):
        # Run health check
        result = await health_monitor.check_all_services(use_cache=False)

        # Assertions
        assert result.overall_status == HealthStatus.DEGRADED
        assert result.healthy_count == 2
        assert result.degraded_count == 1
        assert result.unhealthy_count == 0


@pytest.mark.asyncio
async def test_check_all_services_caching(health_monitor):
    """Test that caching works correctly."""
    # Mock all services as healthy
    mock_result = InfrastructureHealthResponse(
        overall_status=HealthStatus.HEALTHY,
        services=[
            ServiceHealth(
                service="qdrant",
                status=HealthStatus.HEALTHY,
                response_time_ms=50.0,
                message="Qdrant healthy",
                last_checked=datetime.now(timezone.utc),
            )
        ],
        total_response_time_ms=50.0,
        healthy_count=1,
        degraded_count=0,
        unhealthy_count=0,
        checked_at=datetime.now(timezone.utc),
    )

    # Create mock return values
    mock_health_result = ServiceHealth(
        service="test",
        status=HealthStatus.HEALTHY,
        response_time_ms=50.0,
        message="Test healthy",
        last_checked=datetime.now(timezone.utc),
    )

    with (
        patch.object(
            health_monitor,
            "check_qdrant_health",
            new_callable=AsyncMock,
            return_value=mock_health_result,
        ) as mock_qdrant,
        patch.object(
            health_monitor,
            "check_postgres_health",
            new_callable=AsyncMock,
            return_value=mock_health_result,
        ) as mock_postgres,
        patch.object(
            health_monitor,
            "check_kafka_health",
            new_callable=AsyncMock,
            return_value=mock_health_result,
        ) as mock_kafka,
    ):
        # First call should run checks
        health_monitor._cached_health = None
        health_monitor._cache_timestamp = None

        result1 = await health_monitor.check_all_services(use_cache=True)

        # Checks should have been called
        assert mock_qdrant.called
        assert mock_postgres.called
        assert mock_kafka.called

        # Reset mocks
        mock_qdrant.reset_mock()
        mock_postgres.reset_mock()
        mock_kafka.reset_mock()

        # Second call within cache TTL should use cache
        result2 = await health_monitor.check_all_services(use_cache=True)

        # Checks should NOT have been called again
        assert not mock_qdrant.called
        assert not mock_postgres.called
        assert not mock_kafka.called


@pytest.mark.asyncio
async def test_health_monitor_from_env():
    """Test creating health monitor from environment variables."""
    with patch.dict(
        "os.environ",
        {
            "QDRANT_HOST": "test-qdrant",
            "QDRANT_PORT": "6334",
            "POSTGRES_HOST": "test-postgres",
            "POSTGRES_PORT": "5437",
            "POSTGRES_DATABASE": "test_db",
            "POSTGRES_USER": "test_user",
            "POSTGRES_PASSWORD": "test_pass",
            "KAFKA_BOOTSTRAP_SERVERS": "test-kafka:9093",
            "HEALTH_CHECK_CACHE_TTL": "60",
        },
    ):
        monitor = HealthMonitor.from_env()

        assert monitor.qdrant_host == "test-qdrant"
        assert monitor.qdrant_port == 6334
        assert monitor.postgres_host == "test-postgres"
        assert monitor.postgres_port == 5437
        assert monitor.postgres_database == "test_db"
        assert monitor.postgres_user == "test_user"
        assert monitor.postgres_password == "test_pass"
        assert monitor.kafka_bootstrap_servers == "test-kafka:9093"
        assert monitor.cache_ttl == 60


@pytest.mark.asyncio
async def test_health_monitor_cleanup(health_monitor):
    """Test cleanup of health monitor resources."""
    # Mock Qdrant client
    mock_qdrant_client = AsyncMock()
    health_monitor.qdrant_client = mock_qdrant_client

    # Run cleanup
    await health_monitor.cleanup()

    # Verify client was closed
    mock_qdrant_client.close.assert_called_once()
    assert health_monitor.qdrant_client is None


@pytest.mark.asyncio
async def test_get_health_monitor_singleton():
    """Test that get_health_monitor returns singleton instance."""
    # Reset global instance
    import archon_services.health_monitor as hm_module

    hm_module._health_monitor = None

    # Get first instance
    monitor1 = get_health_monitor()

    # Get second instance
    monitor2 = get_health_monitor()

    # Should be same instance
    assert monitor1 is monitor2

    # Cleanup
    hm_module._health_monitor = None
