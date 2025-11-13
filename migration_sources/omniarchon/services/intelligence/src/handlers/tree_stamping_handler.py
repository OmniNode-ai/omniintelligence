"""
Tree Stamping Event Handler

Handles tree + stamping integration requests via Kafka events.
Orchestrates TreeStampingBridge operations and publishes responses.

Event Flow:
    1. Consume tree stamping request events
    2. Call TreeStampingBridge orchestrator methods
    3. Publish COMPLETED (success) or FAILED (error) response events

Topics:
    Index Project:
    - Request: dev.archon-intelligence.tree.index-project-requested.v1
    - Completed: dev.archon-intelligence.tree.index-project-completed.v1
    - Failed: dev.archon-intelligence.tree.index-project-failed.v1

    Search Files:
    - Request: dev.archon-intelligence.tree.search-files-requested.v1
    - Completed: dev.archon-intelligence.tree.search-files-completed.v1
    - Failed: dev.archon-intelligence.tree.search-files-failed.v1

    Get Status:
    - Request: dev.archon-intelligence.tree.get-status-requested.v1
    - Completed: dev.archon-intelligence.tree.get-status-completed.v1
    - Failed: dev.archon-intelligence.tree.get-status-failed.v1

Service Integration:
    - TreeStampingBridge: Main orchestrator for file location intelligence pipeline
    - OnexTree (8058): File enumeration
    - MetadataStamping (8057): Intelligence generation
    - Qdrant (6333): Vector indexing
    - Memgraph (7687): Graph indexing
    - Valkey (6379): Caching

Created: 2025-10-24
Purpose: Event-driven project indexing and file location search
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.events.models.tree_stamping_events import (
    EnumIndexingErrorCode,
    EnumIndexingStatus,
    EnumTreeStampingEventType,
    create_get_status_completed,
    create_get_status_failed,
    create_index_project_completed,
    create_index_project_failed,
    create_search_files_completed,
    create_search_files_failed,
)
from src.handlers.base_response_publisher import BaseResponsePublisher
from src.integrations.tree_stamping_bridge import (
    IndexingError,
    IntelligenceGenerationError,
    StampingError,
    TreeDiscoveryError,
    TreeStampingBridge,
)
from src.models.file_location import ProjectIndexStatus

logger = logging.getLogger(__name__)


class TreeStampingHandler(BaseResponsePublisher):
    """
    Handle tree + stamping integration requests via Kafka events.

    Consumes:
    - dev.archon-intelligence.tree.index-project-requested.v1
    - dev.archon-intelligence.tree.search-files-requested.v1
    - dev.archon-intelligence.tree.get-status-requested.v1

    Publishes:
    - dev.archon-intelligence.tree.index-project-completed.v1
    - dev.archon-intelligence.tree.index-project-failed.v1
    - dev.archon-intelligence.tree.search-files-completed.v1
    - dev.archon-intelligence.tree.search-files-failed.v1
    - dev.archon-intelligence.tree.get-status-completed.v1
    - dev.archon-intelligence.tree.get-status-failed.v1

    Performance Targets:
    - Event processing overhead: <100ms (handler logic only)
    - Indexing: <5min for 1000 files (TreeStampingBridge performance)
    - Search (cold): <2s
    - Search (warm): <500ms
    """

    # Topic constants
    INDEX_PROJECT_REQUEST_TOPIC = (
        "dev.archon-intelligence.tree.index-project-requested.v1"
    )
    INDEX_PROJECT_COMPLETED_TOPIC = (
        "dev.archon-intelligence.tree.index-project-completed.v1"
    )
    INDEX_PROJECT_FAILED_TOPIC = "dev.archon-intelligence.tree.index-project-failed.v1"

    SEARCH_FILES_REQUEST_TOPIC = (
        "dev.archon-intelligence.tree.search-files-requested.v1"
    )
    SEARCH_FILES_COMPLETED_TOPIC = (
        "dev.archon-intelligence.tree.search-files-completed.v1"
    )
    SEARCH_FILES_FAILED_TOPIC = "dev.archon-intelligence.tree.search-files-failed.v1"

    GET_STATUS_REQUEST_TOPIC = "dev.archon-intelligence.tree.get-status-requested.v1"
    GET_STATUS_COMPLETED_TOPIC = "dev.archon-intelligence.tree.get-status-completed.v1"
    GET_STATUS_FAILED_TOPIC = "dev.archon-intelligence.tree.get-status-failed.v1"

    def __init__(self, bridge: Optional[TreeStampingBridge] = None):
        """
        Initialize TreeStampingHandler.

        Args:
            bridge: Optional TreeStampingBridge instance (creates new if not provided)
        """
        super().__init__()

        # TreeStampingBridge orchestrator
        self.bridge = bridge or TreeStampingBridge()

        # Metrics
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "index_project_successes": 0,
            "index_project_failures": 0,
            "search_files_successes": 0,
            "search_files_failures": 0,
            "get_status_successes": 0,
            "get_status_failures": 0,
        }

        logger.info("TreeStampingHandler initialized")

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string (may include prefix and version)

        Returns:
            True if event type matches any tree stamping operation
        """
        # Support both full topic names and short event types
        # Full: dev.archon-intelligence.tree.index-project-requested.v1
        # Short: tree.index-project-requested or INDEX_PROJECT_REQUESTED
        event_type_lower = event_type.lower()

        return any(
            [
                # Index Project patterns
                "index-project-requested" in event_type_lower,
                "index_project_requested" in event_type_lower,
                # Search Files patterns
                "search-files-requested" in event_type_lower,
                "search_files_requested" in event_type_lower,
                # Get Status patterns
                "get-status-requested" in event_type_lower,
                "get_status_requested" in event_type_lower,
                "status-requested" in event_type_lower and "tree" in event_type_lower,
            ]
        )

    async def handle_event(self, event: Any) -> bool:
        """
        Handle tree stamping request events.

        Routes to appropriate handler based on event type.

        Args:
            event: Event envelope with request payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        correlation_id = None

        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)
            event_type_str = self._get_event_type(event)
            event_type_lower = event_type_str.lower()

            logger.info(
                f"📥 TreeStampingHandler received event",
                extra={
                    "event_type": event_type_str,
                    "correlation_id": str(correlation_id),
                    "handler": "TreeStampingHandler",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            # Route to appropriate handler
            if (
                "index-project" in event_type_lower
                or "index_project" in event_type_lower
            ):
                return await self._handle_index_project(
                    correlation_id, payload, start_time
                )
            elif (
                "search-files" in event_type_lower or "search_files" in event_type_lower
            ):
                return await self._handle_search_files(
                    correlation_id, payload, start_time
                )
            elif (
                "get-status" in event_type_lower
                or "get_status" in event_type_lower
                or "status" in event_type_lower
            ):
                return await self._handle_get_status(
                    correlation_id, payload, start_time
                )
            else:
                logger.warning(f"Unknown tree stamping event type: {event_type_str}")
                return False

        except Exception as e:
            logger.error(
                f"Tree stamping handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_index_project(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """
        Handle INDEX_PROJECT_REQUESTED event.

        Orchestrates full indexing pipeline via TreeStampingBridge:
        1. Tree discovery (OnexTree)
        2. Intelligence generation (Bridge)
        3. Metadata stamping (Stamping)
        4. Vector indexing (Qdrant)
        5. Graph indexing (Memgraph)
        6. Cache warming (Valkey)

        Args:
            correlation_id: Request correlation ID
            payload: Event payload
            start_time: Handler start time

        Returns:
            True if handled successfully, False otherwise
        """
        try:
            # Extract required fields
            project_path = payload.get("project_path")
            project_name = payload.get("project_name")
            files = payload.get("files")  # Phase 1: Inline content support
            include_tests = payload.get("include_tests", True)
            force_reindex = payload.get("force_reindex", False)

            # Validate required fields
            if not project_path or not project_name:
                logger.error(
                    f"Missing required fields in INDEX_PROJECT_REQUESTED | "
                    f"correlation_id={correlation_id}"
                )
                await self._publish_index_failed(
                    correlation_id=correlation_id,
                    project_name=project_name or "unknown",
                    error_code=EnumIndexingErrorCode.INVALID_INPUT,
                    error_message="Missing required fields: project_path and project_name",
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    retry_recommended=False,
                )
                self.metrics["index_project_failures"] += 1
                return False

            # Validate inline content provided (Phase 0 removed)
            if not files:
                error_msg = (
                    "files parameter is required. Phase 0 (filesystem-based indexing) "
                    "has been removed. Use bulk_ingest_repository.py to send inline content."
                )
                logger.error(f"{error_msg} | correlation_id={correlation_id}")
                await self._publish_index_failed(
                    correlation_id=correlation_id,
                    project_name=project_name,
                    error_code=EnumIndexingErrorCode.INVALID_INPUT,
                    error_message=error_msg,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    retry_recommended=False,
                )
                self.metrics["index_project_failures"] += 1
                return False

            # Log inline content usage
            logger.info(
                f"🚀 Processing INDEX_PROJECT_REQUESTED with {len(files)} files (inline content)",
                extra={
                    "correlation_id": str(correlation_id),
                    "project_name": project_name,
                    "file_count": len(files),
                    "include_tests": include_tests,
                    "force_reindex": force_reindex,
                },
            )

            # Call TreeStampingBridge orchestrator
            result = await self.bridge.index_project(
                project_path=project_path,
                project_name=project_name,
                files=files,  # Pass inline content to bridge
                include_tests=include_tests,
                force_reindex=force_reindex,
            )

            # Calculate total duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Publish response based on result
            if result.success:
                await self._publish_index_completed(
                    correlation_id=correlation_id,
                    project_name=result.project_name,
                    files_discovered=result.files_discovered,
                    files_indexed=result.files_indexed,
                    vector_indexed=result.vector_indexed,
                    graph_indexed=result.graph_indexed,
                    cache_warmed=result.cache_warmed,
                    duration_ms=duration_ms,
                    errors=result.errors,
                    warnings=result.warnings,
                )

                self.metrics["events_handled"] += 1
                self.metrics["index_project_successes"] += 1
                self.metrics["total_processing_time_ms"] += duration_ms

                logger.info(
                    f"✅ INDEX_PROJECT_COMPLETED published successfully",
                    extra={
                        "correlation_id": str(correlation_id),
                        "project_name": project_name,
                        "files_indexed": result.files_indexed,
                        "vector_indexed": result.vector_indexed,
                        "graph_indexed": result.graph_indexed,
                        "cache_warmed": result.cache_warmed,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return True
            else:
                # Indexing failed
                error_message = result.errors[0] if result.errors else "Indexing failed"
                await self._publish_index_failed(
                    correlation_id=correlation_id,
                    project_name=project_name,
                    error_code=EnumIndexingErrorCode.INDEXING_FAILED,
                    error_message=error_message,
                    duration_ms=duration_ms,
                    retry_recommended=True,
                    error_details={
                        "errors": result.errors,
                        "warnings": result.warnings,
                    },
                )

                self.metrics["index_project_failures"] += 1
                logger.warning(
                    f"INDEX_PROJECT_FAILED published | correlation_id={correlation_id} | "
                    f"error={error_message}"
                )
                return False

        except (
            TreeDiscoveryError,
            IntelligenceGenerationError,
            StampingError,
            IndexingError,
        ) as e:
            logger.error(
                f"Index project failed for {payload.get('project_path', 'unknown')}",
                extra={
                    "correlation_id": str(correlation_id),
                    "project_path": payload.get("project_path"),
                    "project_name": payload.get("project_name"),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_index_failed(
                correlation_id=correlation_id,
                project_name=payload.get("project_name", "unknown"),
                error_code=EnumIndexingErrorCode.INTERNAL_ERROR,
                error_message=f"{type(e).__name__}: {str(e)}",
                duration_ms=duration_ms,
                retry_recommended=True,
                error_details={"exception_type": type(e).__name__},
            )

            self.metrics["index_project_failures"] += 1
            return False
        except Exception as e:
            logger.error(
                f"Index project failed (unexpected error)",
                extra={
                    "correlation_id": str(correlation_id),
                    "project_path": payload.get("project_path"),
                    "project_name": payload.get("project_name"),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_index_failed(
                correlation_id=correlation_id,
                project_name=payload.get("project_name", "unknown"),
                error_code=EnumIndexingErrorCode.INTERNAL_ERROR,
                error_message=f"Internal error: {str(e)}",
                duration_ms=duration_ms,
                retry_recommended=True,
                error_details={"exception_type": type(e).__name__},
            )

            self.metrics["index_project_failures"] += 1
            return False

    async def _handle_search_files(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """
        Handle SEARCH_FILES_REQUESTED event.

        Performs semantic file search via TreeStampingBridge:
        1. Check cache (Valkey)
        2. If miss: Query Qdrant (vector similarity)
        3. Filter by quality score
        4. Rank by composite score
        5. Cache result

        Args:
            correlation_id: Request correlation ID
            payload: Event payload
            start_time: Handler start time

        Returns:
            True if handled successfully, False otherwise
        """
        try:
            # Extract required fields
            query = payload.get("query")
            projects = payload.get("projects")
            min_quality_score = payload.get("min_quality_score", 0.0)
            limit = payload.get("limit", 10)

            # Validate required fields
            if not query:
                logger.error(
                    f"Missing required field 'query' in SEARCH_FILES_REQUESTED | "
                    f"correlation_id={correlation_id}"
                )
                await self._publish_search_failed(
                    correlation_id=correlation_id,
                    error_code=EnumIndexingErrorCode.INVALID_INPUT,
                    error_message="Missing required field: query",
                    query_time_ms=(time.perf_counter() - start_time) * 1000,
                    retry_recommended=False,
                )
                self.metrics["search_files_failures"] += 1
                return False

            logger.info(
                f"Processing SEARCH_FILES_REQUESTED | correlation_id={correlation_id} | "
                f"query='{query}' | projects={projects} | min_quality_score={min_quality_score} | "
                f"limit={limit}"
            )

            # Call TreeStampingBridge search
            search_result = await self.bridge.search_files(
                query=query,
                projects=projects,
                min_quality_score=min_quality_score,
                limit=limit,
            )

            # Calculate total duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Publish response
            if search_result.success:
                # Convert FileMatch models to dictionaries
                results_dicts = [
                    result.model_dump() for result in search_result.results
                ]

                await self._publish_search_completed(
                    correlation_id=correlation_id,
                    results=results_dicts,
                    query_time_ms=duration_ms,
                    cache_hit=search_result.cache_hit,
                    total_results=search_result.total_results,
                )

                self.metrics["events_handled"] += 1
                self.metrics["search_files_successes"] += 1
                self.metrics["total_processing_time_ms"] += duration_ms

                logger.info(
                    f"SEARCH_FILES_COMPLETED published | correlation_id={correlation_id} | "
                    f"results_count={len(search_result.results)} | cache_hit={search_result.cache_hit} | "
                    f"duration_ms={duration_ms:.2f}"
                )
                return True
            else:
                # Search failed
                error_message = search_result.error or "Search failed"
                await self._publish_search_failed(
                    correlation_id=correlation_id,
                    error_code=EnumIndexingErrorCode.INTERNAL_ERROR,
                    error_message=error_message,
                    query_time_ms=duration_ms,
                    retry_recommended=True,
                )

                self.metrics["search_files_failures"] += 1
                logger.warning(
                    f"SEARCH_FILES_FAILED published | correlation_id={correlation_id} | "
                    f"error={error_message}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Search files failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_search_failed(
                correlation_id=correlation_id,
                error_code=EnumIndexingErrorCode.INTERNAL_ERROR,
                error_message=f"Internal error: {str(e)}",
                query_time_ms=duration_ms,
                retry_recommended=True,
                error_details={"exception_type": type(e).__name__},
            )

            self.metrics["search_files_failures"] += 1
            return False

    async def _handle_get_status(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """
        Handle GET_STATUS_REQUESTED event.

        Retrieves project indexing status via TreeStampingBridge:
        - Check Valkey cache for status
        - Fallback: Query Qdrant for indexed files

        Args:
            correlation_id: Request correlation ID
            payload: Event payload
            start_time: Handler start time

        Returns:
            True if handled successfully, False otherwise
        """
        try:
            # Extract optional project_name filter
            project_name = payload.get("project_name")

            logger.info(
                f"Processing GET_STATUS_REQUESTED | correlation_id={correlation_id} | "
                f"project_name={project_name}"
            )

            # Call TreeStampingBridge status check
            status_list = await self.bridge.get_indexing_status(
                project_name=project_name
            )

            # Calculate total duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Convert ProjectIndexStatus models to dictionaries
            projects_dicts = []
            for status in status_list:
                status_dict = {
                    "project_name": status.project_name,
                    "indexed": status.indexed,
                    "file_count": status.file_count,
                    "status": status.status.upper(),  # Convert to uppercase for EnumIndexingStatus
                    "last_indexed_at": status.indexed_at,
                }
                projects_dicts.append(status_dict)

            # Publish response
            await self._publish_status_completed(
                correlation_id=correlation_id,
                projects=projects_dicts,
                query_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["get_status_successes"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"GET_STATUS_COMPLETED published | correlation_id={correlation_id} | "
                f"projects_count={len(status_list)} | duration_ms={duration_ms:.2f}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Get status failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_status_failed(
                correlation_id=correlation_id,
                error_code=EnumIndexingErrorCode.INTERNAL_ERROR,
                error_message=f"Internal error: {str(e)}",
                query_time_ms=duration_ms,
                retry_recommended=True,
            )

            self.metrics["get_status_failures"] += 1
            return False

    # ============================================================================
    # Response Publishing Methods
    # ============================================================================

    async def _publish_index_completed(
        self,
        correlation_id: UUID,
        project_name: str,
        files_discovered: int,
        files_indexed: int,
        vector_indexed: int,
        graph_indexed: int,
        cache_warmed: bool,
        duration_ms: float,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
    ) -> None:
        """Publish INDEX_PROJECT_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_index_project_completed(
                project_name=project_name,
                files_discovered=files_discovered,
                files_indexed=files_indexed,
                vector_indexed=vector_indexed,
                graph_indexed=graph_indexed,
                cache_warmed=cache_warmed,
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                errors=errors,
                warnings=warnings,
            )

            await self._router.publish(
                topic=self.INDEX_PROJECT_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.debug(
                f"Published INDEX_PROJECT_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to publish index completed response: {e}", exc_info=True
            )
            raise

    async def _publish_index_failed(
        self,
        correlation_id: UUID,
        project_name: str,
        error_code: EnumIndexingErrorCode,
        error_message: str,
        duration_ms: float,
        retry_recommended: bool = True,
        retry_after_seconds: int = 60,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish INDEX_PROJECT_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_index_project_failed(
                project_name=project_name,
                error_code=error_code,
                error_message=error_message,
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                retry_recommended=retry_recommended,
                retry_after_seconds=retry_after_seconds,
                error_details=error_details,
            )

            await self._router.publish(
                topic=self.INDEX_PROJECT_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.debug(
                f"Published INDEX_PROJECT_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish index failed response: {e}", exc_info=True)
            raise

    async def _publish_search_completed(
        self,
        correlation_id: UUID,
        results: List[Dict[str, Any]],
        query_time_ms: float,
        cache_hit: bool,
        total_results: int,
    ) -> None:
        """Publish SEARCH_FILES_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_search_files_completed(
                results=results,
                query_time_ms=query_time_ms,
                total_results=total_results,
                correlation_id=correlation_id,
                cache_hit=cache_hit,
            )

            await self._router.publish(
                topic=self.SEARCH_FILES_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.debug(
                f"Published SEARCH_FILES_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to publish search completed response: {e}", exc_info=True
            )
            raise

    async def _publish_search_failed(
        self,
        correlation_id: UUID,
        error_code: EnumIndexingErrorCode,
        error_message: str,
        query_time_ms: float,
        retry_recommended: bool = True,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish SEARCH_FILES_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_search_files_failed(
                error_code=error_code,
                error_message=error_message,
                query_time_ms=query_time_ms,
                correlation_id=correlation_id,
                retry_recommended=retry_recommended,
                error_details=error_details,
            )

            await self._router.publish(
                topic=self.SEARCH_FILES_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.debug(
                f"Published SEARCH_FILES_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to publish search failed response: {e}", exc_info=True
            )
            raise

    async def _publish_status_completed(
        self,
        correlation_id: UUID,
        projects: List[Dict[str, Any]],
        query_time_ms: float,
    ) -> None:
        """Publish GET_STATUS_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_get_status_completed(
                projects=projects,
                query_time_ms=query_time_ms,
                correlation_id=correlation_id,
            )

            await self._router.publish(
                topic=self.GET_STATUS_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.debug(
                f"Published GET_STATUS_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to publish status completed response: {e}", exc_info=True
            )
            raise

    async def _publish_status_failed(
        self,
        correlation_id: UUID,
        error_code: EnumIndexingErrorCode,
        error_message: str,
        query_time_ms: float,
        retry_recommended: bool = True,
    ) -> None:
        """Publish GET_STATUS_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_get_status_failed(
                error_code=error_code,
                error_message=error_message,
                query_time_ms=query_time_ms,
                correlation_id=correlation_id,
                retry_recommended=retry_recommended,
            )

            await self._router.publish(
                topic=self.GET_STATUS_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.debug(
                f"Published GET_STATUS_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to publish status failed response: {e}", exc_info=True
            )
            raise

    def _get_event_type(self, event: Any) -> str:
        """Extract event type from event metadata."""
        if isinstance(event, dict):
            # Check metadata first (omnibase_core pattern)
            metadata = event.get("metadata", {})
            if "event_type" in metadata:
                return metadata["event_type"]
            # Fallback to top-level (legacy pattern)
            return event.get("event_type", "")
        else:
            # For object access
            metadata = getattr(event, "metadata", {})
            if isinstance(metadata, dict) and "event_type" in metadata:
                return metadata["event_type"]
            return getattr(event, "event_type", "")

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "TreeStampingHandler"

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

        return {
            **self.metrics,
            "success_rate": success_rate,
            "avg_processing_time_ms": avg_processing_time,
            "handler_name": self.get_handler_name(),
        }

    async def shutdown(self) -> None:
        """Shutdown handler and cleanup resources."""
        await self._shutdown_publisher()
        logger.info("Tree stamping handler shutdown complete")
