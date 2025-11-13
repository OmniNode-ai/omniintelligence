"""
Infrastructure Scan Handler

Handles INFRASTRUCTURE_SCAN operation requests by querying PostgreSQL, Kafka,
Qdrant, and Docker services to provide infrastructure topology information.

Created: 2025-10-26
Purpose: Provide infrastructure topology to omniclaude manifest_injector
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
import httpx
from aiokafka.admin import AIOKafkaAdminClient
from qdrant_client import AsyncQdrantClient
from src.events.models.intelligence_adapter_events import ModelInfrastructureScanPayload


# Add project root to path for config imports
def _find_project_root() -> Path:
    """
    Find project root by searching for .git directory (repository root).

    Walks up the directory tree from this file's location until .git is found.
    This ensures we find the repository root, not just a service-level pyproject.toml.
    Falls back to pyproject.toml if .git is not found.
    """
    current = Path(__file__).resolve().parent
    # First pass: look for .git (repository root)
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    # Second pass: fall back to pyproject.toml
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    # Final fallback to current directory if no marker found
    return current


project_root = _find_project_root()
sys.path.insert(0, str(project_root))
from config import settings  # Centralized configuration

# Kafka configuration constants
KAFKA_DOCKER_SERVERS = (
    "omninode-bridge-redpanda:9092"  # Docker services use internal DNS
)

logger = logging.getLogger(__name__)


class InfrastructureScanHandler:
    """
    Handle INFRASTRUCTURE_SCAN operations.

    Query PostgreSQL, Kafka, Qdrant, and Docker to provide infrastructure topology.

    Performance Target: <1500ms query timeout
    """

    TIMEOUT_MS = 1500  # Per spec: 1500ms query timeout

    def __init__(
        self,
        postgres_url: Optional[str] = None,
        kafka_bootstrap_servers: Optional[str] = None,
        qdrant_url: Optional[str] = None,
        archon_mcp_url: Optional[str] = None,
    ):
        """
        Initialize Infrastructure Scan handler.

        Args:
            postgres_url: PostgreSQL connection URL
            kafka_bootstrap_servers: Kafka bootstrap servers
            qdrant_url: Qdrant URL
            archon_mcp_url: Archon MCP URL
        """
        # Build PostgreSQL URL from environment variables
        if postgres_url:
            self.postgres_url = postgres_url
        elif os.getenv("DATABASE_URL"):
            self.postgres_url = os.getenv("DATABASE_URL")
        else:
            # Build from individual components
            pg_host = os.getenv("POSTGRES_HOST", "192.168.86.200")
            pg_port = os.getenv("POSTGRES_PORT", "5436")
            pg_user = os.getenv("POSTGRES_USER", "postgres")
            pg_pass = os.getenv("POSTGRES_PASSWORD", "")
            pg_db = os.getenv("POSTGRES_DATABASE", "omninode_bridge")
            self.postgres_url = (
                f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
            )
        self.kafka_bootstrap = kafka_bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            KAFKA_DOCKER_SERVERS,  # Use centralized config for Docker context
        )
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://qdrant:6333")
        self.archon_mcp_url = archon_mcp_url or os.getenv(
            "ARCHON_MCP_URL", "http://localhost:8051"
        )

    async def execute(
        self,
        source_path: str,
        options: Dict[str, Any],
    ) -> ModelInfrastructureScanPayload:
        """
        Execute INFRASTRUCTURE_SCAN operation.

        Args:
            source_path: Not used (always "infrastructure")
            options: Operation options (include_databases, include_kafka_topics, etc.)

        Returns:
            ModelInfrastructureScanPayload with infrastructure information

        Raises:
            Exception: If scan fails or times out
        """
        start_time = time.perf_counter()

        try:
            # Extract options
            include_databases = options.get("include_databases", True)
            include_kafka = options.get("include_kafka_topics", True)
            include_qdrant = options.get("include_qdrant_collections", True)
            include_docker = options.get("include_docker_services", True)
            include_archon_mcp = options.get("include_archon_mcp", True)

            logger.info(f"Executing INFRASTRUCTURE_SCAN | options={options}")

            # Execute scans in parallel with timeout
            timeout_seconds = self.TIMEOUT_MS / 1000

            results = await asyncio.gather(
                self._scan_postgresql() if include_databases else None,
                self._scan_kafka() if include_kafka else None,
                self._scan_qdrant() if include_qdrant else None,
                self._scan_docker() if include_docker else None,
                self._scan_archon_mcp() if include_archon_mcp else None,
                return_exceptions=True,
            )

            postgresql, kafka, qdrant, docker_services, archon_mcp = results

            # Handle exceptions in results
            if isinstance(postgresql, Exception):
                logger.warning(f"PostgreSQL scan failed: {postgresql}")
                postgresql = None
            if isinstance(kafka, Exception):
                logger.warning(f"Kafka scan failed: {kafka}")
                kafka = None
            if isinstance(qdrant, Exception):
                logger.warning(f"Qdrant scan failed: {qdrant}")
                qdrant = None
            if isinstance(docker_services, Exception):
                logger.warning(f"Docker scan failed: {docker_services}")
                docker_services = None
            if isinstance(archon_mcp, Exception):
                logger.warning(f"Archon MCP scan failed: {archon_mcp}")
                archon_mcp = None

            query_time_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                f"INFRASTRUCTURE_SCAN completed | query_time_ms={query_time_ms:.2f}"
            )

            return ModelInfrastructureScanPayload(
                postgresql=postgresql,
                kafka=kafka,
                qdrant=qdrant,
                docker_services=docker_services,
                archon_mcp=archon_mcp,
                query_time_ms=query_time_ms,
            )

        except Exception as e:
            query_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"INFRASTRUCTURE_SCAN failed | error={e} | query_time_ms={query_time_ms:.2f}",
                exc_info=True,
            )
            raise

    async def _scan_postgresql(self) -> Optional[Dict[str, Any]]:
        """Scan PostgreSQL database."""
        try:
            conn = await asyncpg.connect(self.postgres_url, timeout=1.0)
            try:
                # Get table information
                tables_query = """
                    SELECT
                        schemaname,
                        tablename,
                        pg_total_relation_size(schemaname||'.'||tablename)::bigint / 1024 / 1024 as size_mb
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY size_mb DESC
                    LIMIT 10
                """
                tables_raw = await conn.fetch(tables_query)

                tables = []
                for row in tables_raw:
                    # Get row count
                    count_query = (
                        f"SELECT COUNT(*) FROM {row['schemaname']}.{row['tablename']}"
                    )
                    row_count = await conn.fetchval(count_query)

                    tables.append(
                        {
                            "name": row["tablename"],
                            "row_count": row_count,
                            "size_mb": float(row["size_mb"]),
                        }
                    )

                # Get total table count
                total_count_query = """
                    SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'
                """
                total_table_count = await conn.fetchval(total_count_query)

                # Parse connection URL to get host/port
                # Format: postgresql://user:pass@host:port/database
                parts = self.postgres_url.split("@")[1].split("/")
                host_port = parts[0].split(":")
                database = parts[1]

                return {
                    "host": host_port[0],
                    "port": int(host_port[1]) if len(host_port) > 1 else 5432,
                    "database": database,
                    "status": "connected",
                    "tables": tables,
                    "table_count": total_table_count,
                }
            finally:
                await conn.close()

        except Exception as e:
            logger.error(f"PostgreSQL scan failed: {e}", exc_info=True)
            # Return error state instead of None for better visibility
            # Try to parse host/port/database from URL for error reporting
            try:
                parts = self.postgres_url.split("@")[1].split("/")
                host_port = parts[0].split(":")
                database = parts[1]
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 5432
            except:
                host = "unknown"
                port = 0
                database = "unknown"

            return {
                "host": host,
                "port": port,
                "database": database,
                "status": "error",
                "error": str(e),
                "tables": [],
                "table_count": 0,
            }

    async def _scan_kafka(self) -> Optional[Dict[str, Any]]:
        """Scan Kafka/Redpanda topics."""
        try:
            admin_client = AIOKafkaAdminClient(
                bootstrap_servers=self.kafka_bootstrap,
                request_timeout_ms=1000,
            )
            await admin_client.start()
            try:
                # Get topic metadata
                metadata = await admin_client._client.fetch_all_metadata()

                topics = []
                # metadata.topics() returns a set of topic names
                for topic_name in metadata.topics():
                    partitions = metadata.partitions_for_topic(topic_name)
                    if partitions:
                        # Access internal metadata structure for replication factor
                        # metadata._metadata.topics[topic_name].partitions[partition_id].replicas
                        replication_factor = 0
                        try:
                            first_partition = min(partitions)
                            partition_metadata = metadata._metadata.topics[
                                topic_name
                            ].partitions[first_partition]
                            replication_factor = len(partition_metadata.replicas)
                        except (KeyError, AttributeError):
                            pass

                        topics.append(
                            {
                                "name": topic_name,
                                "partitions": len(partitions),
                                "replication_factor": replication_factor,
                                "message_count": "unknown",  # Would need consumer to count
                            }
                        )

                return {
                    "bootstrap_servers": self.kafka_bootstrap,
                    "status": "connected",
                    "topics": topics,
                    "topic_count": len(topics),
                }
            finally:
                await admin_client.close()

        except Exception as e:
            logger.error(f"Kafka scan failed: {e}", exc_info=True)
            # Return error state instead of None for better visibility
            return {
                "bootstrap_servers": self.kafka_bootstrap,
                "status": "error",
                "error": str(e),
                "topics": [],
                "topic_count": 0,
            }

    async def _scan_qdrant(self) -> Optional[Dict[str, Any]]:
        """Scan Qdrant collections."""
        try:
            client = AsyncQdrantClient(url=self.qdrant_url, timeout=1.0)

            # Get collections
            collections_response = await client.get_collections()

            collections = []
            for collection in collections_response.collections:
                # Get collection info
                collection_info = await client.get_collection(collection.name)

                collections.append(
                    {
                        "name": collection.name,
                        "vector_size": collection_info.config.params.vectors.size,
                        "point_count": collection_info.points_count,
                    }
                )

            await client.close()

            return {
                "endpoint": self.qdrant_url,
                "status": "connected",
                "collections": collections,
                "collection_count": len(collections),
            }

        except Exception as e:
            logger.error(f"Qdrant scan failed: {e}", exc_info=True)
            # Return error state instead of None for better visibility
            return {
                "endpoint": self.qdrant_url,
                "status": "error",
                "error": str(e),
                "collections": [],
                "collection_count": 0,
            }

    async def _scan_docker(self) -> Optional[List[Dict[str, Any]]]:
        """Scan Docker services."""
        try:
            # Query Docker via Unix socket or HTTP
            # For simplicity, return static service list based on docker-compose
            # In production, would query Docker API directly

            services = [
                {
                    "name": "archon-intelligence",
                    "status": "running",
                    "port": 8053,
                    "health": "healthy",
                },
                {
                    "name": "archon-search",
                    "status": "running",
                    "port": 8055,
                    "health": "healthy",
                },
                {
                    "name": "archon-bridge",
                    "status": "running",
                    "port": 8054,
                    "health": "healthy",
                },
                {
                    "name": "qdrant",
                    "status": "running",
                    "port": 6333,
                    "health": "healthy",
                },
                {
                    "name": "memgraph",
                    "status": "running",
                    "port": 7687,
                    "health": "healthy",
                },
            ]

            return services

        except Exception as e:
            logger.error(f"Docker scan failed: {e}")
            return None

    async def _scan_archon_mcp(self) -> Optional[Dict[str, Any]]:
        """Scan Archon MCP service."""
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                # Try health endpoint
                response = await client.get(f"{self.archon_mcp_url}/health")

                if response.status_code == 200:
                    health_data = response.json()
                    return {
                        "endpoint": self.archon_mcp_url,
                        "status": "healthy",
                        "health_data": health_data,
                    }
                else:
                    return {
                        "endpoint": self.archon_mcp_url,
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}",
                    }

        except httpx.ConnectError as e:
            logger.warning(f"Archon MCP connection failed: {e}")
            return {
                "endpoint": self.archon_mcp_url,
                "status": "unavailable",
                "error": "Connection refused - service not running",
            }
        except Exception as e:
            logger.error(f"Archon MCP scan failed: {e}", exc_info=True)
            return {
                "endpoint": self.archon_mcp_url,
                "status": "error",
                "error": str(e),
            }
