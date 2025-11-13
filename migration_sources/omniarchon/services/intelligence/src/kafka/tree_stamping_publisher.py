"""
Tree Stamping Event Publisher

Publishes tree stamping response events to Kafka event bus.
Uses KafkaEventPublisher for low-level Kafka operations.

Created: 2025-10-24
Purpose: Event-driven tree + stamping integration responses
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# Import Kafka publisher with fallback for missing dependencies
try:
    from events.kafka_publisher import KafkaEventPublisher
except ImportError:
    # Fallback stub when confluent_kafka is not available
    class KafkaEventPublisher:
        """Stub Kafka publisher for testing without confluent_kafka"""

        def __init__(self, config=None):
            self.config = config
            self.is_connected = False

        async def initialize(self):
            pass

        async def publish(self, topic, event, key=None, headers=None, partition=None):
            pass


from src.config.kafka_config import get_kafka_config

logger = logging.getLogger(__name__)


class TreeStampingPublisher:
    """
    Publisher for tree stamping response events.

    Publishes completion/failure events for:
    - INDEX_PROJECT operations
    - SEARCH_FILES operations
    - GET_STATUS operations

    Uses KafkaEventPublisher for actual Kafka publishing with
    delivery guarantees and correlation ID tracking.
    """

    def __init__(self):
        """Initialize tree stamping publisher."""
        self._kafka_publisher = KafkaEventPublisher()
        self._config = get_kafka_config()
        self._topics = self._config.topics

        logger.info("TreeStampingPublisher initialized")

    async def initialize(self) -> None:
        """Initialize publisher (compatibility with async patterns)."""
        await self._kafka_publisher.initialize()
        logger.info("TreeStampingPublisher ready")

    async def publish_index_project_completed(
        self,
        correlation_id: str,
        causation_id: Optional[str],
        project_name: str,
        files_discovered: int,
        files_indexed: int,
        vector_indexed: int,
        graph_indexed: int,
        cache_warmed: bool,
        duration_ms: int,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
    ) -> None:
        """
        Publish index project completed event.

        Args:
            correlation_id: Correlation ID from original request
            causation_id: Event ID that caused this event (original request event_id)
            project_name: Name of indexed project
            files_discovered: Number of files discovered
            files_indexed: Number of files successfully indexed
            vector_indexed: Number of files indexed in vector DB
            graph_indexed: Number of files indexed in knowledge graph
            cache_warmed: Whether cache was warmed
            duration_ms: Operation duration in milliseconds
            errors: Optional list of error messages
            warnings: Optional list of warning messages
        """
        event = self._build_event(
            event_type="dev.archon-intelligence.tree.index-project-completed.v1",
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "project_name": project_name,
                "files_discovered": files_discovered,
                "files_indexed": files_indexed,
                "vector_indexed": vector_indexed,
                "graph_indexed": graph_indexed,
                "cache_warmed": cache_warmed,
                "duration_ms": duration_ms,
                "errors": errors or [],
                "warnings": warnings or [],
            },
        )

        await self._kafka_publisher.publish(
            topic=self._topics.tree_index_project_completed,
            event=event,
            key=correlation_id,
        )

        logger.info(
            f"Published index-project-completed | "
            f"correlation_id={correlation_id} | "
            f"project={project_name} | "
            f"files_indexed={files_indexed}"
        )

    async def publish_index_project_failed(
        self,
        correlation_id: str,
        causation_id: Optional[str],
        project_name: str,
        error_code: str,
        error_message: str,
        duration_ms: int,
        retry_recommended: bool = True,
        retry_after_seconds: int = 60,
    ) -> None:
        """
        Publish index project failed event.

        Args:
            correlation_id: Correlation ID from original request
            causation_id: Event ID that caused this event
            project_name: Name of project that failed indexing
            error_code: Error classification code
            error_message: Human-readable error description
            duration_ms: Operation duration before failure
            retry_recommended: Whether retry is recommended
            retry_after_seconds: Recommended retry delay
        """
        event = self._build_event(
            event_type="dev.archon-intelligence.tree.index-project-failed.v1",
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "project_name": project_name,
                "error_code": error_code,
                "error_message": error_message,
                "duration_ms": duration_ms,
                "retry_recommended": retry_recommended,
                "retry_after_seconds": retry_after_seconds,
            },
        )

        await self._kafka_publisher.publish(
            topic=self._topics.tree_index_project_failed,
            event=event,
            key=correlation_id,
        )

        logger.error(
            f"Published index-project-failed | "
            f"correlation_id={correlation_id} | "
            f"project={project_name} | "
            f"error={error_code}: {error_message}"
        )

    async def publish_search_files_completed(
        self,
        correlation_id: str,
        causation_id: Optional[str],
        query: str,
        results: List[Dict[str, Any]],
        total_results: int,
        duration_ms: int,
    ) -> None:
        """
        Publish search files completed event.

        Args:
            correlation_id: Correlation ID from original request
            causation_id: Event ID that caused this event
            query: Search query text
            results: List of search results
            total_results: Total number of results found
            duration_ms: Search duration in milliseconds
        """
        event = self._build_event(
            event_type="dev.archon-intelligence.tree.search-files-completed.v1",
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "query": query,
                "results": results,
                "total_results": total_results,
                "duration_ms": duration_ms,
            },
        )

        await self._kafka_publisher.publish(
            topic=self._topics.tree_search_files_completed,
            event=event,
            key=correlation_id,
        )

        logger.info(
            f"Published search-files-completed | "
            f"correlation_id={correlation_id} | "
            f"query={query} | "
            f"results={total_results}"
        )

    async def publish_search_files_failed(
        self,
        correlation_id: str,
        causation_id: Optional[str],
        query: str,
        error_code: str,
        error_message: str,
        duration_ms: int,
    ) -> None:
        """
        Publish search files failed event.

        Args:
            correlation_id: Correlation ID from original request
            causation_id: Event ID that caused this event
            query: Search query that failed
            error_code: Error classification code
            error_message: Human-readable error description
            duration_ms: Operation duration before failure
        """
        event = self._build_event(
            event_type="dev.archon-intelligence.tree.search-files-failed.v1",
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "query": query,
                "error_code": error_code,
                "error_message": error_message,
                "duration_ms": duration_ms,
            },
        )

        await self._kafka_publisher.publish(
            topic=self._topics.tree_search_files_failed,
            event=event,
            key=correlation_id,
        )

        logger.error(
            f"Published search-files-failed | "
            f"correlation_id={correlation_id} | "
            f"query={query} | "
            f"error={error_code}: {error_message}"
        )

    async def publish_get_status_completed(
        self,
        correlation_id: str,
        causation_id: Optional[str],
        project_name: str,
        is_indexed: bool,
        last_indexed_at: Optional[str],
        file_count: int,
        index_health: str,
        duration_ms: int,
    ) -> None:
        """
        Publish get status completed event.

        Args:
            correlation_id: Correlation ID from original request
            causation_id: Event ID that caused this event
            project_name: Name of project
            is_indexed: Whether project is indexed
            last_indexed_at: Last indexing timestamp (ISO format)
            file_count: Number of indexed files
            index_health: Health status (healthy/degraded/unhealthy)
            duration_ms: Operation duration in milliseconds
        """
        event = self._build_event(
            event_type="dev.archon-intelligence.tree.get-status-completed.v1",
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "project_name": project_name,
                "is_indexed": is_indexed,
                "last_indexed_at": last_indexed_at,
                "file_count": file_count,
                "index_health": index_health,
                "duration_ms": duration_ms,
            },
        )

        await self._kafka_publisher.publish(
            topic=self._topics.tree_get_status_completed,
            event=event,
            key=correlation_id,
        )

        logger.info(
            f"Published get-status-completed | "
            f"correlation_id={correlation_id} | "
            f"project={project_name} | "
            f"indexed={is_indexed}"
        )

    async def publish_get_status_failed(
        self,
        correlation_id: str,
        causation_id: Optional[str],
        project_name: str,
        error_code: str,
        error_message: str,
        duration_ms: int,
    ) -> None:
        """
        Publish get status failed event.

        Args:
            correlation_id: Correlation ID from original request
            causation_id: Event ID that caused this event
            project_name: Name of project
            error_code: Error classification code
            error_message: Human-readable error description
            duration_ms: Operation duration before failure
        """
        event = self._build_event(
            event_type="dev.archon-intelligence.tree.get-status-failed.v1",
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "project_name": project_name,
                "error_code": error_code,
                "error_message": error_message,
                "duration_ms": duration_ms,
            },
        )

        await self._kafka_publisher.publish(
            topic=self._topics.tree_get_status_failed,
            event=event,
            key=correlation_id,
        )

        logger.error(
            f"Published get-status-failed | "
            f"correlation_id={correlation_id} | "
            f"project={project_name} | "
            f"error={error_code}: {error_message}"
        )

    def _build_event(
        self,
        event_type: str,
        correlation_id: str,
        causation_id: Optional[str],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build event envelope with metadata.

        Args:
            event_type: Event type string
            correlation_id: Correlation ID for tracking
            causation_id: Event ID that caused this event
            payload: Event payload

        Returns:
            Complete event envelope
        """
        event_id = str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        envelope = {
            "event_id": event_id,
            "event_type": event_type,
            "correlation_id": correlation_id,
            "timestamp": timestamp,
            "source": {
                "service": "archon-intelligence",
                "instance_id": "intelligence-service",  # Could be made dynamic
            },
            "payload": payload,
        }

        # Add causation_id if provided (links to triggering event)
        if causation_id:
            envelope["causation_id"] = causation_id

        return envelope

    async def shutdown(self) -> None:
        """Shutdown publisher and flush pending messages."""
        await self._kafka_publisher.shutdown()
        logger.info("TreeStampingPublisher shutdown complete")
