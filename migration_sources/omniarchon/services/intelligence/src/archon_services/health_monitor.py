"""
Service Health Monitoring for Pattern Dashboard Infrastructure

ONEX v2.0 Compliance: Compute node for health aggregation
Provides real-time health status for dashboard infrastructure services.

Monitors:
- Qdrant vector database (port 6333)
- PostgreSQL database (port 5436)
- Kafka message broker (port 9092)

Features:
- Fast health checks (<100ms target)
- Cached results (30s TTL)
- Detailed error reporting
- Service-specific metrics
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Health Status Models
# =============================================================================


class HealthStatus(str, Enum):
    """Service health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ServiceHealth(BaseModel):
    """Health status for a single service."""

    service: str = Field(..., description="Service name")
    status: HealthStatus = Field(..., description="Health status")
    response_time_ms: float = Field(..., description="Response time in milliseconds")
    message: str = Field(..., description="Status message")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional details"
    )
    last_checked: datetime = Field(..., description="Last check timestamp")
    error: Optional[str] = Field(default=None, description="Error message if unhealthy")


class InfrastructureHealthResponse(BaseModel):
    """Complete infrastructure health response."""

    overall_status: HealthStatus = Field(
        ..., description="Overall infrastructure status"
    )
    services: List[ServiceHealth] = Field(..., description="Individual service health")
    total_response_time_ms: float = Field(..., description="Total health check time")
    healthy_count: int = Field(..., description="Number of healthy services")
    degraded_count: int = Field(..., description="Number of degraded services")
    unhealthy_count: int = Field(..., description="Number of unhealthy services")
    checked_at: datetime = Field(..., description="Health check timestamp")


# =============================================================================
# Health Monitor Service
# =============================================================================


class HealthMonitor:
    """
    Infrastructure health monitoring service.

    Provides health status checks for Pattern Dashboard infrastructure:
    - Qdrant vector database
    - PostgreSQL database
    - Kafka message broker

    Performance target: <100ms for complete health check
    Cache TTL: 30 seconds
    """

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        postgres_host: str = "omninode-bridge-postgres",
        postgres_port: int = 5436,
        postgres_database: str = "omninode_bridge",
        postgres_user: str = "postgres",
        postgres_password: Optional[str] = None,
        kafka_bootstrap_servers: str = "omninode-bridge-redpanda:9092",
        cache_ttl: int = 30,
    ):
        """
        Initialize health monitor.

        Args:
            qdrant_host: Qdrant host (default: localhost)
            qdrant_port: Qdrant port (default: 6333)
            postgres_host: PostgreSQL host
            postgres_port: PostgreSQL port
            postgres_database: PostgreSQL database name
            postgres_user: PostgreSQL user
            postgres_password: PostgreSQL password
            kafka_bootstrap_servers: Kafka bootstrap servers
            cache_ttl: Cache TTL in seconds (default: 30)
        """
        # Qdrant config
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.qdrant_client: Optional[AsyncQdrantClient] = None

        # PostgreSQL config
        self.postgres_host = postgres_host
        self.postgres_port = postgres_port
        self.postgres_database = postgres_database
        self.postgres_user = postgres_user
        self.postgres_password = postgres_password or os.getenv(
            "POSTGRES_PASSWORD", "omninode-bridge-postgres-dev-2024"
        )

        # Kafka config
        self.kafka_bootstrap_servers = kafka_bootstrap_servers

        # Cache config
        self.cache_ttl = cache_ttl
        self._cached_health: Optional[InfrastructureHealthResponse] = None
        self._cache_timestamp: Optional[float] = None

        logger.info(
            f"Health monitor initialized | qdrant={qdrant_host}:{qdrant_port} "
            f"postgres={postgres_host}:{postgres_port} kafka={kafka_bootstrap_servers}"
        )

    @classmethod
    def from_env(cls) -> "HealthMonitor":
        """
        Create health monitor from environment variables.

        Environment Variables:
            QDRANT_HOST: Qdrant host (default: localhost)
            QDRANT_PORT: Qdrant port (default: 6333)
            POSTGRES_HOST: PostgreSQL host (default: omninode-bridge-postgres)
            POSTGRES_PORT: PostgreSQL port (default: 5436)
            POSTGRES_DATABASE: PostgreSQL database (default: omninode_bridge)
            POSTGRES_USER: PostgreSQL user (default: postgres)
            POSTGRES_PASSWORD: PostgreSQL password
            KAFKA_BOOTSTRAP_SERVERS: Kafka servers (default: omninode-bridge-redpanda:9092)
            HEALTH_CHECK_CACHE_TTL: Cache TTL in seconds (default: 30)

        Returns:
            Health monitor instance
        """
        return cls(
            qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
            postgres_host=os.getenv("POSTGRES_HOST", "omninode-bridge-postgres"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5436")),
            postgres_database=os.getenv("POSTGRES_DATABASE", "omninode_bridge"),
            postgres_user=os.getenv("POSTGRES_USER", "postgres"),
            postgres_password=os.getenv("POSTGRES_PASSWORD"),
            kafka_bootstrap_servers=os.getenv(
                "KAFKA_BOOTSTRAP_SERVERS", "omninode-bridge-redpanda:9092"
            ),
            cache_ttl=int(os.getenv("HEALTH_CHECK_CACHE_TTL", "30")),
        )

    def _is_cache_valid(self) -> bool:
        """Check if cached health data is still valid."""
        if self._cached_health is None or self._cache_timestamp is None:
            return False

        age = time.time() - self._cache_timestamp
        return age < self.cache_ttl

    async def check_qdrant_health(self) -> ServiceHealth:
        """
        Check Qdrant vector database health.

        Returns:
            ServiceHealth for Qdrant
        """
        start_time = time.time()
        service_name = "qdrant"

        try:
            # Create client if not exists
            if self.qdrant_client is None:
                self.qdrant_client = AsyncQdrantClient(
                    host=self.qdrant_host,
                    port=self.qdrant_port,
                    timeout=2.0,
                )

            # Get collections
            collections = await self.qdrant_client.get_collections()

            response_time = (time.time() - start_time) * 1000

            # Get collection details
            collection_details = []
            for collection in collections.collections:
                try:
                    info = await self.qdrant_client.get_collection(collection.name)
                    collection_details.append(
                        {
                            "name": collection.name,
                            "points_count": info.points_count,
                            "vectors_count": info.vectors_count,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to get details for collection {collection.name}: {e}"
                    )

            return ServiceHealth(
                service=service_name,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                message=f"Qdrant healthy with {len(collections.collections)} collections",
                details={
                    "collections_count": len(collections.collections),
                    "collections": collection_details,
                    "host": self.qdrant_host,
                    "port": self.qdrant_port,
                },
                last_checked=datetime.now(timezone.utc),
            )

        except UnexpectedResponse as e:
            response_time = (time.time() - start_time) * 1000
            return ServiceHealth(
                service=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message="Qdrant connection failed",
                error=str(e),
                last_checked=datetime.now(timezone.utc),
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Qdrant health check failed: {e}", exc_info=True)
            return ServiceHealth(
                service=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message="Qdrant health check failed",
                error=str(e),
                last_checked=datetime.now(timezone.utc),
            )

    async def check_postgres_health(self) -> ServiceHealth:
        """
        Check PostgreSQL database health.

        Returns:
            ServiceHealth for PostgreSQL
        """
        start_time = time.time()
        service_name = "postgresql"

        try:
            # Create connection
            conn = await asyncpg.connect(
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_database,
                user=self.postgres_user,
                password=self.postgres_password,
                timeout=2.0,
            )

            try:
                # Test query
                result = await conn.fetchval("SELECT 1")

                # Get database stats
                db_size = await conn.fetchval(
                    "SELECT pg_database_size($1)", self.postgres_database
                )

                # Get table count
                table_count = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """
                )

                response_time = (time.time() - start_time) * 1000

                return ServiceHealth(
                    service=service_name,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    message=f"PostgreSQL healthy with {table_count} tables",
                    details={
                        "database": self.postgres_database,
                        "table_count": table_count,
                        "database_size_bytes": db_size,
                        "database_size_mb": (
                            round(db_size / (1024 * 1024), 2) if db_size else 0
                        ),
                        "host": self.postgres_host,
                        "port": self.postgres_port,
                    },
                    last_checked=datetime.now(timezone.utc),
                )

            finally:
                await conn.close()

        except asyncpg.PostgresConnectionError as e:
            response_time = (time.time() - start_time) * 1000
            return ServiceHealth(
                service=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message="PostgreSQL connection failed",
                error=str(e),
                last_checked=datetime.now(timezone.utc),
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"PostgreSQL health check failed: {e}", exc_info=True)
            return ServiceHealth(
                service=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message="PostgreSQL health check failed",
                error=str(e),
                last_checked=datetime.now(timezone.utc),
            )

    async def check_kafka_health(self) -> ServiceHealth:
        """
        Check Kafka message broker health.

        Returns:
            ServiceHealth for Kafka
        """
        start_time = time.time()
        service_name = "kafka"

        try:
            # Create producer to test connection
            producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                request_timeout_ms=2000,
            )

            try:
                await producer.start()

                # Get cluster metadata
                cluster_metadata = await producer.client.fetch_all_metadata()

                response_time = (time.time() - start_time) * 1000

                # Extract broker and topic info
                broker_count = len(cluster_metadata.brokers())
                topic_count = len(cluster_metadata.topics())

                return ServiceHealth(
                    service=service_name,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    message=f"Kafka healthy with {broker_count} brokers, {topic_count} topics",
                    details={
                        "bootstrap_servers": self.kafka_bootstrap_servers,
                        "broker_count": broker_count,
                        "topic_count": topic_count,
                    },
                    last_checked=datetime.now(timezone.utc),
                )

            finally:
                await producer.stop()

        except KafkaConnectionError as e:
            response_time = (time.time() - start_time) * 1000
            return ServiceHealth(
                service=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message="Kafka connection failed",
                error=str(e),
                last_checked=datetime.now(timezone.utc),
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Kafka health check failed: {e}", exc_info=True)
            return ServiceHealth(
                service=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                message="Kafka health check failed",
                error=str(e),
                last_checked=datetime.now(timezone.utc),
            )

    async def check_all_services(
        self, use_cache: bool = True
    ) -> InfrastructureHealthResponse:
        """
        Check health of all infrastructure services.

        Args:
            use_cache: Use cached results if available (default: True)

        Returns:
            Complete infrastructure health response
        """
        # Check cache
        if use_cache and self._is_cache_valid():
            logger.debug("Returning cached health check results")
            return self._cached_health  # type: ignore

        logger.info("Running fresh health checks for all services")
        overall_start = time.time()

        # Run all checks in parallel
        qdrant_task = asyncio.create_task(self.check_qdrant_health())
        postgres_task = asyncio.create_task(self.check_postgres_health())
        kafka_task = asyncio.create_task(self.check_kafka_health())

        # Wait for all checks to complete
        services = await asyncio.gather(qdrant_task, postgres_task, kafka_task)

        total_response_time = (time.time() - overall_start) * 1000

        # Calculate overall status
        healthy_count = sum(1 for s in services if s.status == HealthStatus.HEALTHY)
        degraded_count = sum(1 for s in services if s.status == HealthStatus.DEGRADED)
        unhealthy_count = sum(1 for s in services if s.status == HealthStatus.UNHEALTHY)

        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        # Create response
        response = InfrastructureHealthResponse(
            overall_status=overall_status,
            services=services,
            total_response_time_ms=total_response_time,
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            unhealthy_count=unhealthy_count,
            checked_at=datetime.now(timezone.utc),
        )

        # Update cache
        self._cached_health = response
        self._cache_timestamp = time.time()

        logger.info(
            f"Health check complete | overall={overall_status.value} | "
            f"healthy={healthy_count} degraded={degraded_count} unhealthy={unhealthy_count} | "
            f"total_time={total_response_time:.2f}ms"
        )

        return response

    async def cleanup(self):
        """Cleanup resources."""
        if self.qdrant_client:
            await self.qdrant_client.close()
            self.qdrant_client = None


# =============================================================================
# Global Health Monitor Instance
# =============================================================================

_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """
    Get the global health monitor instance.

    Returns:
        Global health monitor instance
    """
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor.from_env()
    return _health_monitor


async def cleanup_health_monitor():
    """Cleanup global health monitor instance."""
    global _health_monitor
    if _health_monitor:
        await _health_monitor.cleanup()
        _health_monitor = None
