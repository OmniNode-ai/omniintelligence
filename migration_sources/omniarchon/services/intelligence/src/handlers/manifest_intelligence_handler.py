"""
Manifest Intelligence Handler

Handles MANIFEST_INTELLIGENCE_REQUESTED events by orchestrating parallel queries
to 5 backend sources:
1. Patterns (Qdrant)
2. Infrastructure (PostgreSQL, Kafka, Docker)
3. Models (vLLM, OpenAI)
4. Database Schemas (PostgreSQL)
5. Debug Intelligence (PostgreSQL)

Implements graceful degradation with partial results support.

Created: 2025-11-03
Purpose: Unified manifest intelligence gathering for OmniClaude
Performance Target: <1500ms (p50)
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg
import httpx
from qdrant_client import AsyncQdrantClient
from src.handlers.base_response_publisher import BaseResponsePublisher
from src.handlers.operations.infrastructure_scan_handler import (
    InfrastructureScanHandler,
)
from src.handlers.operations.schema_discovery_handler import SchemaDiscoveryHandler

# Centralized configuration
from config import settings

logger = logging.getLogger(__name__)


class ManifestIntelligenceHandler(BaseResponsePublisher):
    """
    Handle MANIFEST_INTELLIGENCE_REQUESTED events.

    Orchestrates parallel queries to 5 backend sources:
    1. Patterns (Qdrant)
    2. Infrastructure (PostgreSQL, Kafka, Docker)
    3. Models (vLLM, OpenAI)
    4. Database Schemas (PostgreSQL)
    5. Debug Intelligence (PostgreSQL)

    Performance Target: <1500ms (p50), supports partial results
    """

    # Topic constants
    MANIFEST_INTELLIGENCE_REQUEST_TOPIC = (
        "dev.archon-intelligence.intelligence.manifest.requested.v1"
    )
    MANIFEST_INTELLIGENCE_COMPLETED_TOPIC = (
        "dev.archon-intelligence.intelligence.manifest.completed.v1"
    )
    MANIFEST_INTELLIGENCE_FAILED_TOPIC = (
        "dev.archon-intelligence.intelligence.manifest.failed.v1"
    )

    # Performance targets
    TIMEOUT_MS = 1500  # 1500ms target
    QUERY_TIMEOUT_S = 1.5  # 1.5 seconds per query

    def __init__(
        self,
        postgres_url: Optional[str] = None,
        qdrant_url: Optional[str] = None,
        embedding_model_url: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        """
        Initialize Manifest Intelligence handler.

        Args:
            postgres_url: PostgreSQL connection URL
            qdrant_url: Qdrant URL
            embedding_model_url: Embedding model API base URL
            openai_api_key: OpenAI API key
        """
        super().__init__()

        # Service URLs from centralized config
        self.postgres_url = postgres_url or os.getenv(
            "DATABASE_URL",
            settings.get_postgres_dsn(async_driver=True),
        )
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://qdrant:6333")
        self.embedding_model_url = embedding_model_url or os.getenv(
            "EMBEDDING_MODEL_URL", "http://192.168.86.201:8002"
        )
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        # Sub-handlers
        self.infrastructure_handler = InfrastructureScanHandler(
            postgres_url=self.postgres_url
        )
        self.schema_handler = SchemaDiscoveryHandler(postgres_url=self.postgres_url)

        # HTTP client
        self.http_client: Optional[httpx.AsyncClient] = None

        # Metrics
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "partial_results_count": 0,
            "full_results_count": 0,
        }

    async def _ensure_http_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=self.QUERY_TIMEOUT_S)

    async def _close_http_client(self) -> None:
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if event type matches manifest intelligence request
        """
        return event_type.lower() in [
            "manifest_intelligence_requested",
            "manifest.intelligence.requested",
            "intelligence.manifest.requested",
        ]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle MANIFEST_INTELLIGENCE_REQUESTED event.

        Args:
            event: Event envelope with request payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        correlation_id: Optional[UUID] = None

        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)
            options = payload.get("options", {})

            logger.info(
                f"Processing MANIFEST_INTELLIGENCE_REQUESTED | correlation_id={correlation_id} | "
                f"options={options}"
            )

            # Execute parallel queries
            result = await self.execute(correlation_id=correlation_id, options=options)

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_manifest_intelligence_completed(
                correlation_id=correlation_id,
                result=result,
                processing_time_ms=duration_ms,
            )

            # Update metrics
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            if result["summary"]["partial_results"]:
                self.metrics["partial_results_count"] += 1
            else:
                self.metrics["full_results_count"] += 1

            logger.info(
                f"MANIFEST_INTELLIGENCE_COMPLETED | correlation_id={correlation_id} | "
                f"sections_succeeded={result['summary']['sections_succeeded']} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Manifest intelligence handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1

            # Publish failure response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_manifest_intelligence_failed(
                correlation_id=correlation_id
                or UUID("00000000-0000-0000-0000-000000000000"),
                error_message=str(e),
                processing_time_ms=duration_ms,
            )

            return False

    async def execute(
        self, correlation_id: UUID, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute manifest intelligence gathering with parallel queries.

        Args:
            correlation_id: Correlation ID for tracking
            options: Query options (e.g., include_patterns, include_schemas)

        Returns:
            Manifest intelligence result with partial results support

        Raises:
            Exception: If all queries fail
        """
        query_start_time = time.perf_counter()

        logger.debug(
            f"Executing parallel manifest intelligence queries | correlation_id={correlation_id}"
        )

        # Launch all queries in parallel with exception handling
        results = await asyncio.gather(
            self._query_patterns(options),
            self._query_infrastructure(options),
            self._query_models(options),
            self._query_database_schemas(options),
            self._query_debug_intelligence(options),
            return_exceptions=True,  # Support partial results
        )

        # Unpack results
        patterns_result = results[0]
        infrastructure_result = results[1]
        models_result = results[2]
        schemas_result = results[3]
        debug_intel_result = results[4]

        # Build response with graceful degradation
        response = {
            "patterns": {},
            "infrastructure": {},
            "models": {},
            "database_schemas": {},
            "debug_intelligence": {},
            "summary": {
                "sections_succeeded": 0,
                "sections_failed": 0,
                "partial_results": False,
                "query_time_ms": 0.0,
            },
            "warnings": [],
        }

        # Process patterns result
        if isinstance(patterns_result, Exception):
            logger.warning(f"Patterns query failed: {patterns_result}")
            response["warnings"].append(
                f"patterns section unavailable - {str(patterns_result)}"
            )
            response["summary"]["sections_failed"] += 1
        else:
            response["patterns"] = patterns_result
            response["summary"]["sections_succeeded"] += 1

        # Process infrastructure result
        if isinstance(infrastructure_result, Exception):
            logger.warning(f"Infrastructure query failed: {infrastructure_result}")
            response["warnings"].append(
                f"infrastructure section unavailable - {str(infrastructure_result)}"
            )
            response["summary"]["sections_failed"] += 1
        else:
            response["infrastructure"] = infrastructure_result
            response["summary"]["sections_succeeded"] += 1

        # Process models result
        if isinstance(models_result, Exception):
            logger.warning(f"Models query failed: {models_result}")
            response["warnings"].append(
                f"models section unavailable - {str(models_result)}"
            )
            response["summary"]["sections_failed"] += 1
        else:
            response["models"] = models_result
            response["summary"]["sections_succeeded"] += 1

        # Process schemas result
        if isinstance(schemas_result, Exception):
            logger.warning(f"Schemas query failed: {schemas_result}")
            response["warnings"].append(
                f"database_schemas section unavailable - {str(schemas_result)}"
            )
            response["summary"]["sections_failed"] += 1
        else:
            response["database_schemas"] = schemas_result
            response["summary"]["sections_succeeded"] += 1

        # Process debug intelligence result
        if isinstance(debug_intel_result, Exception):
            logger.warning(f"Debug intelligence query failed: {debug_intel_result}")
            response["warnings"].append(
                f"debug_intelligence section unavailable - {str(debug_intel_result)}"
            )
            response["summary"]["sections_failed"] += 1
        else:
            response["debug_intelligence"] = debug_intel_result
            response["summary"]["sections_succeeded"] += 1

        # Update summary
        query_time_ms = (time.perf_counter() - query_start_time) * 1000
        response["summary"]["query_time_ms"] = query_time_ms
        response["summary"]["partial_results"] = (
            response["summary"]["sections_failed"] > 0
        )

        # Log summary
        logger.info(
            f"Manifest intelligence query completed | "
            f"succeeded={response['summary']['sections_succeeded']} | "
            f"failed={response['summary']['sections_failed']} | "
            f"partial={response['summary']['partial_results']} | "
            f"query_time_ms={query_time_ms:.2f}"
        )

        return response

    async def _query_patterns(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query Qdrant for code generation patterns.

        Args:
            options: Query options

        Returns:
            Patterns data with metadata

        Raises:
            Exception: If query fails
        """
        try:
            # Check if patterns query is enabled
            if not options.get("include_patterns", True):
                return {"patterns": [], "total_count": 0, "query_time_ms": 0.0}

            query_start = time.perf_counter()

            # Initialize Qdrant client
            client = AsyncQdrantClient(
                url=self.qdrant_url, timeout=self.QUERY_TIMEOUT_S
            )

            # Get collections
            collections_response = await client.get_collections()

            patterns = []
            total_count = 0

            # Query code generation patterns collection
            for collection in collections_response.collections:
                if "pattern" in collection.name.lower():
                    # Get collection info
                    collection_info = await client.get_collection(collection.name)

                    # Get sample points (limit to 100 for performance)
                    scroll_result = await client.scroll(
                        collection_name=collection.name,
                        limit=min(options.get("max_patterns", 100), 100),
                        with_payload=True,
                        with_vectors=False,
                    )

                    points = scroll_result[0] if scroll_result else []

                    for point in points:
                        payload = point.payload or {}
                        patterns.append(
                            {
                                "id": str(point.id),
                                "name": payload.get("name", "Unknown"),
                                "file_path": payload.get("file_path", ""),
                                "description": payload.get("description", ""),
                                "node_types": payload.get("node_types", []),
                                "confidence": payload.get("confidence", 0.0),
                                "use_cases": payload.get("use_cases", []),
                                "metadata": payload.get("metadata", {}),
                            }
                        )

                    total_count += collection_info.points_count

            await client.close()

            query_time_ms = (time.perf_counter() - query_start) * 1000

            logger.debug(
                f"Patterns query completed | patterns_found={len(patterns)} | "
                f"query_time_ms={query_time_ms:.2f}"
            )

            return {
                "patterns": patterns,
                "total_count": total_count,
                "query_time_ms": query_time_ms,
            }

        except Exception as e:
            logger.error(f"Patterns query failed: {e}", exc_info=True)
            raise

    async def _query_infrastructure(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query infrastructure topology using InfrastructureScanHandler.

        Args:
            options: Query options

        Returns:
            Infrastructure data

        Raises:
            Exception: If query fails
        """
        try:
            # Check if infrastructure query is enabled
            if not options.get("include_infrastructure", True):
                return {}

            # Use existing infrastructure scan handler
            result = await self.infrastructure_handler.execute(
                source_path="infrastructure",
                options=options,
            )

            # Build response with proper structure for remote vs local services
            remote_services = {}
            local_services = {}

            # Remote services (running on 192.168.86.200)
            if result.postgresql:
                remote_services["postgresql"] = result.postgresql
            if result.kafka:
                remote_services["kafka"] = result.kafka

            # Local services (running on localhost/Docker)
            if result.qdrant:
                local_services["qdrant"] = result.qdrant
            if result.archon_mcp:
                local_services["archon_mcp"] = result.archon_mcp
            if result.docker_services:
                local_services["docker_services"] = result.docker_services

            return {
                "remote_services": remote_services,
                "local_services": local_services,
                "query_time_ms": result.query_time_ms,
            }

        except Exception as e:
            logger.error(f"Infrastructure query failed: {e}", exc_info=True)
            raise

    async def _query_models(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query available AI models (vLLM, OpenAI).

        Args:
            options: Query options

        Returns:
            Models data

        Raises:
            Exception: If query fails
        """
        try:
            # Check if models query is enabled
            if not options.get("include_models", True):
                return {"ai_models": {}, "query_time_ms": 0.0}

            query_start = time.perf_counter()

            await self._ensure_http_client()

            ai_models = {"providers": []}

            # Query Embedding/LLM models (vLLM with OpenAI-compatible API)
            try:
                vllm_response = await self.http_client.get(
                    f"{self.embedding_model_url}/v1/models",
                    timeout=self.QUERY_TIMEOUT_S,
                )
                if vllm_response.status_code == 200:
                    vllm_data = vllm_response.json()
                    models = [model["id"] for model in vllm_data.get("data", [])]
                    ai_models["providers"].append(
                        {
                            "name": "vLLM",
                            "models": models,
                            "status": "available",
                            "endpoint": self.embedding_model_url,
                        }
                    )
            except Exception as e:
                logger.warning(f"vLLM query failed: {e}")
                ai_models["providers"].append(
                    {
                        "name": "vLLM",
                        "models": [],
                        "status": "unavailable",
                        "error": str(e),
                    }
                )

            # Add OpenAI models (static list)
            if self.openai_api_key:
                ai_models["providers"].append(
                    {
                        "name": "OpenAI",
                        "models": [
                            "gpt-4-turbo-preview",
                            "gpt-4",
                            "gpt-3.5-turbo",
                        ],
                        "status": "available",
                    }
                )
            else:
                ai_models["providers"].append(
                    {
                        "name": "OpenAI",
                        "models": [],
                        "status": "not_configured",
                    }
                )

            query_time_ms = (time.perf_counter() - query_start) * 1000

            logger.debug(
                f"Models query completed | providers={len(ai_models['providers'])} | "
                f"query_time_ms={query_time_ms:.2f}"
            )

            return {"ai_models": ai_models, "query_time_ms": query_time_ms}

        except Exception as e:
            logger.error(f"Models query failed: {e}", exc_info=True)
            raise

    async def _query_database_schemas(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query database schemas using SchemaDiscoveryHandler.

        Args:
            options: Query options

        Returns:
            Database schemas data

        Raises:
            Exception: If query fails
        """
        try:
            # Check if schemas query is enabled
            if not options.get("include_database_schemas", True):
                return {"tables": [], "total_tables": 0, "query_time_ms": 0.0}

            # Use existing schema discovery handler
            result = await self.schema_handler.execute(
                source_path="database_schemas",
                options=options,
            )

            return {
                "tables": result.tables,
                "total_tables": result.total_tables,
                "query_time_ms": result.query_time_ms,
            }

        except Exception as e:
            logger.error(f"Database schemas query failed: {e}", exc_info=True)
            raise

    async def _query_debug_intelligence(
        self, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Query debug intelligence from PostgreSQL pattern data.

        Args:
            options: Query options

        Returns:
            Debug intelligence data

        Raises:
            Exception: If query fails
        """
        try:
            # Check if debug intelligence query is enabled
            if not options.get("include_debug_intelligence", True):
                return {"pattern_executions": [], "query_time_ms": 0.0}

            query_start = time.perf_counter()

            # Connect to PostgreSQL
            conn = await asyncpg.connect(
                self.postgres_url, timeout=self.QUERY_TIMEOUT_S
            )

            try:
                # Query recent pattern executions (if table exists)
                try:
                    executions_query = """
                        SELECT
                            pattern_id,
                            execution_time_ms,
                            success,
                            error_message,
                            created_at
                        FROM pattern_executions
                        ORDER BY created_at DESC
                        LIMIT 100
                    """
                    executions_raw = await conn.fetch(executions_query)

                    pattern_executions = []
                    for row in executions_raw:
                        pattern_executions.append(
                            {
                                "pattern_id": str(row["pattern_id"]),
                                "execution_time_ms": float(row["execution_time_ms"]),
                                "success": bool(row["success"]),
                                "error_message": row["error_message"],
                                "created_at": (
                                    row["created_at"].isoformat()
                                    if row["created_at"]
                                    else None
                                ),
                            }
                        )

                except asyncpg.exceptions.UndefinedTableError:
                    logger.debug("pattern_executions table does not exist")
                    pattern_executions = []

                query_time_ms = (time.perf_counter() - query_start) * 1000

                logger.debug(
                    f"Debug intelligence query completed | executions={len(pattern_executions)} | "
                    f"query_time_ms={query_time_ms:.2f}"
                )

                return {
                    "pattern_executions": pattern_executions,
                    "query_time_ms": query_time_ms,
                }

            finally:
                await conn.close()

        except Exception as e:
            logger.error(f"Debug intelligence query failed: {e}", exc_info=True)
            raise

    async def _publish_manifest_intelligence_completed(
        self,
        correlation_id: UUID,
        result: Dict[str, Any],
        processing_time_ms: float,
    ) -> None:
        """Publish MANIFEST_INTELLIGENCE_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            from datetime import datetime, timezone

            from events.models.model_event import ModelEvent

            event = ModelEvent(
                event_type="CUSTOM",
                topic=self.MANIFEST_INTELLIGENCE_COMPLETED_TOPIC,
                correlation_id=correlation_id,
                timestamp=datetime.now(timezone.utc),
                source_service="archon-intelligence",
                source_version="1.0.0",
                payload_type="ManifestIntelligenceCompleted",
                payload=result,
                priority="NORMAL",
            )

            await self._router.publish(
                topic=self.MANIFEST_INTELLIGENCE_COMPLETED_TOPIC,
                event=event,
                key=str(correlation_id),
            )

            logger.info(
                f"Published MANIFEST_INTELLIGENCE_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish completed response: {e}", exc_info=True)
            raise

    async def _publish_manifest_intelligence_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        processing_time_ms: float,
    ) -> None:
        """Publish MANIFEST_INTELLIGENCE_FAILED event."""
        try:
            await self._ensure_router_initialized()

            from datetime import datetime, timezone

            from events.models.model_event import ModelEvent

            error_payload = {
                "error_message": error_message,
                "error_code": "MANIFEST_INTELLIGENCE_FAILED",
                "processing_time_ms": processing_time_ms,
                "retry_allowed": True,
            }

            event = ModelEvent(
                event_type="CUSTOM",
                topic=self.MANIFEST_INTELLIGENCE_FAILED_TOPIC,
                correlation_id=correlation_id,
                timestamp=datetime.now(timezone.utc),
                source_service="archon-intelligence",
                source_version="1.0.0",
                payload_type="ManifestIntelligenceFailed",
                payload=error_payload,
                priority="HIGH",
            )

            await self._router.publish(
                topic=self.MANIFEST_INTELLIGENCE_FAILED_TOPIC,
                event=event,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published MANIFEST_INTELLIGENCE_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish failed response: {e}", exc_info=True)
            raise

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "ManifestIntelligenceHandler"

    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics."""
        total_events = self.metrics["events_handled"] + self.metrics["events_failed"]
        success_rate = (
            self.metrics["events_handled"] / total_events if total_events > 0 else 1.0
        )
        avg_processing_time = (
            self.metrics["total_processing_time_ms"] / self.metrics["events_handled"]
            if self.metrics["events_handled"] > 0
            else 0.0
        )
        partial_results_rate = (
            self.metrics["partial_results_count"] / self.metrics["events_handled"]
            if self.metrics["events_handled"] > 0
            else 0.0
        )

        return {
            **self.metrics,
            "success_rate": success_rate,
            "avg_processing_time_ms": avg_processing_time,
            "partial_results_rate": partial_results_rate,
            "handler_name": self.get_handler_name(),
        }

    async def shutdown(self) -> None:
        """Shutdown handler and cleanup resources."""
        await self._close_http_client()
        await self._shutdown_publisher()
        logger.info("Manifest intelligence handler shutdown complete")
