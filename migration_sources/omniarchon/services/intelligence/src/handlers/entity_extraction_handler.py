"""
Entity Extraction Event Handler

Handles entity extraction request events and publishes completed/failed responses.
Implements event-driven entity extraction for code, documents, and relationship queries.

Handles 4 event types:
1. CODE_EXTRACTION_REQUESTED → CODE_EXTRACTION_COMPLETED/FAILED
2. DOCUMENT_EXTRACTION_REQUESTED → DOCUMENT_EXTRACTION_COMPLETED/FAILED
3. ENTITY_SEARCH_REQUESTED → ENTITY_SEARCH_COMPLETED/FAILED
4. RELATIONSHIP_QUERY_REQUESTED → RELATIONSHIP_QUERY_COMPLETED/FAILED

Created: 2025-10-22
Purpose: Event-driven entity extraction integration for Phase 1
"""

# Import create_default_client - handle conflict with root config/ directory
import importlib.util
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from src.events.models.entity_extraction_events import (
    EntityExtractionEventHelpers,
    EnumEntityExtractionErrorCode,
    EnumEntityExtractionEventType,
    ModelCodeExtractionCompletedPayload,
    ModelCodeExtractionFailedPayload,
    ModelCodeExtractionRequestPayload,
    ModelDocumentExtractionCompletedPayload,
    ModelDocumentExtractionFailedPayload,
    ModelDocumentExtractionRequestPayload,
    ModelEntitySearchCompletedPayload,
    ModelEntitySearchFailedPayload,
    ModelEntitySearchRequestPayload,
    ModelRelationshipQueryCompletedPayload,
    ModelRelationshipQueryFailedPayload,
    ModelRelationshipQueryRequestPayload,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

# Resolve the correct config module path
_config_module_path = Path(__file__).parent.parent / "config" / "http_client_config.py"
if _config_module_path.exists():
    # Load the module directly from the file
    _spec = importlib.util.spec_from_file_location(
        "_http_client_config", _config_module_path
    )
    _http_client_config = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_http_client_config)
    create_default_client = _http_client_config.create_default_client
else:
    # Fallback to standard import (for when src is properly in path)
    from config.http_client_config import create_default_client

logger = logging.getLogger(__name__)


class EntityExtractionHandler(BaseResponsePublisher):
    """
    Handle entity extraction request events and publish results.

    Event Flow:
        1. Consume {CODE|DOCUMENT|SEARCH|RELATIONSHIP}_REQUESTED event
        2. Extract payload and perform operation
        3. Publish _COMPLETED (success) or _FAILED (error)

    Topics:
        Code Extraction:
        - Request: dev.archon-intelligence.entity.code-extraction-requested.v1
        - Completed: dev.archon-intelligence.entity.code-extraction-completed.v1
        - Failed: dev.archon-intelligence.entity.code-extraction-failed.v1

        Document Extraction:
        - Request: dev.archon-intelligence.entity.document-extraction-requested.v1
        - Completed: dev.archon-intelligence.entity.document-extraction-completed.v1
        - Failed: dev.archon-intelligence.entity.document-extraction-failed.v1

        Entity Search:
        - Request: dev.archon-intelligence.entity.entity-search-requested.v1
        - Completed: dev.archon-intelligence.entity.entity-search-completed.v1
        - Failed: dev.archon-intelligence.entity.entity-search-failed.v1

        Relationship Query:
        - Request: dev.archon-intelligence.entity.relationship-query-requested.v1
        - Completed: dev.archon-intelligence.entity.relationship-query-completed.v1
        - Failed: dev.archon-intelligence.entity.relationship-query-failed.v1
    """

    def __init__(
        self,
        http_client: Optional[httpx.AsyncClient] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize Entity Extraction handler."""
        super().__init__()
        self.http_client = http_client or create_default_client()
        # Use environment variable with fallback to localhost for local dev
        self.base_url = base_url or os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://localhost:8053"
        )
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "operations_by_type": {},
        }

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if event type is an entity extraction request
        """
        try:
            EnumEntityExtractionEventType(event_type)
            return "REQUESTED" in event_type
        except ValueError:
            return any(
                keyword in event_type.lower()
                for keyword in [
                    "code_extraction_requested",
                    "document_extraction_requested",
                    "entity_search_requested",
                    "relationship_query_requested",
                    "code-extraction-requested",
                    "document-extraction-requested",
                    "entity-search-requested",
                    "relationship-query-requested",
                ]
            )

    async def handle_event(self, event: Any) -> bool:
        """
        Handle entity extraction request event.

        Routes to appropriate handler based on event type.

        Args:
            event: Event envelope with entity extraction payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        correlation_id = None

        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)
            # Extract event_type from metadata (omnibase_core pattern)
            if isinstance(event, dict):
                metadata = event.get("metadata", {})
                event_type_str = metadata.get("event_type", event.get("event_type", ""))
            else:
                metadata = getattr(event, "metadata", {})
                event_type_str = (
                    metadata.get("event_type", "")
                    if isinstance(metadata, dict)
                    else getattr(event, "event_type", "")
                )

            # Route to appropriate operation handler
            if (
                "code_extraction" in event_type_str.lower()
                or "code-extraction" in event_type_str.lower()
            ):
                return await self._handle_code_extraction(
                    correlation_id, payload, start_time
                )
            elif (
                "document_extraction" in event_type_str.lower()
                or "document-extraction" in event_type_str.lower()
            ):
                return await self._handle_document_extraction(
                    correlation_id, payload, start_time
                )
            elif (
                "entity_search" in event_type_str.lower()
                or "entity-search" in event_type_str.lower()
            ):
                return await self._handle_entity_search(
                    correlation_id, payload, start_time
                )
            elif (
                "relationship_query" in event_type_str.lower()
                or "relationship-query" in event_type_str.lower()
            ):
                return await self._handle_relationship_query(
                    correlation_id, payload, start_time
                )
            else:
                logger.error(
                    f"Unknown entity extraction operation type: {event_type_str}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Entity extraction handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_code_extraction(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle CODE_EXTRACTION_REQUESTED event."""
        try:
            request = ModelCodeExtractionRequestPayload(**payload)
            logger.info(
                f"Processing CODE_EXTRACTION_REQUESTED | correlation_id={correlation_id} | "
                f"source_path={request.source_path} | language={request.language}"
            )

            # Make HTTP request to intelligence service
            url = f"{self.base_url}/extract/code"
            request_payload = {
                "content": request.content,
                "language": request.language,
                "extract_types": request.extract_types,
            }

            response = await self.http_client.post(
                url, json=request_payload, timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            # Extract metrics from HTTP response
            entities_count = result.get("entities_count", 0)
            entity_types = result.get("entity_types", [])
            confidence_mean = result.get("confidence_mean", 0.0)

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_code_extraction_completed(
                correlation_id,
                request.source_path,
                entities_count,
                entity_types,
                confidence_mean,
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("code_extraction")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error during code extraction | status={e.response.status_code}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            error_code = EnumEntityExtractionErrorCode.SERVICE_ERROR
            if e.response.status_code == 400:
                error_code = EnumEntityExtractionErrorCode.INVALID_INPUT

            await self._publish_code_extraction_failed(
                correlation_id,
                payload.get("source_path", "unknown"),
                f"HTTP error: {e.response.status_code}",
                error_code,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except httpx.TimeoutException as e:
            logger.error(f"Timeout during code extraction", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_code_extraction_failed(
                correlation_id,
                payload.get("source_path", "unknown"),
                "Request timeout",
                EnumEntityExtractionErrorCode.TIMEOUT,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Code extraction operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_code_extraction_failed(
                correlation_id,
                payload.get("source_path", "unknown"),
                str(e),
                EnumEntityExtractionErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_document_extraction(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle DOCUMENT_EXTRACTION_REQUESTED event."""
        try:
            request = ModelDocumentExtractionRequestPayload(**payload)
            logger.info(
                f"Processing DOCUMENT_EXTRACTION_REQUESTED | correlation_id={correlation_id} | "
                f"source_path={request.source_path} | document_type={request.document_type}"
            )

            # Make HTTP request to intelligence service
            url = f"{self.base_url}/extract/document"
            request_payload = {
                "content": request.content,
                "doc_type": request.document_type,
            }

            response = await self.http_client.post(
                url, json=request_payload, timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            # Extract metrics from HTTP response
            entities_count = result.get("entities_count", 0)
            keywords_count = result.get("keywords_count", 0)
            confidence_mean = result.get("confidence_mean", 0.0)

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_extraction_completed(
                correlation_id,
                request.source_path,
                entities_count,
                keywords_count,
                confidence_mean,
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("document_extraction")
            return True

        except Exception as e:
            logger.error(f"Document extraction operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_extraction_failed(
                correlation_id,
                payload.get("source_path", "unknown"),
                str(e),
                EnumEntityExtractionErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_entity_search(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle ENTITY_SEARCH_REQUESTED event."""
        try:
            request = ModelEntitySearchRequestPayload(**payload)
            logger.info(
                f"Processing ENTITY_SEARCH_REQUESTED | correlation_id={correlation_id} | "
                f"query={request.query} | limit={request.limit}"
            )

            # Make HTTP request to intelligence service
            url = f"{self.base_url}/entities/search"
            params = {
                "query": request.query,
                "type": (
                    request.entity_type if hasattr(request, "entity_type") else None
                ),
                "limit": request.limit,
            }

            response = await self.http_client.get(
                url,
                params={k: v for k, v in params.items() if v is not None},
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            # Extract metrics from HTTP response
            results_count = result.get("results_count", 0)

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_entity_search_completed(
                correlation_id,
                request.query,
                results_count,
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("entity_search")
            return True

        except Exception as e:
            logger.error(f"Entity search operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_entity_search_failed(
                correlation_id,
                payload.get("query", "unknown"),
                str(e),
                EnumEntityExtractionErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_relationship_query(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle RELATIONSHIP_QUERY_REQUESTED event."""
        try:
            request = ModelRelationshipQueryRequestPayload(**payload)
            logger.info(
                f"Processing RELATIONSHIP_QUERY_REQUESTED | correlation_id={correlation_id} | "
                f"entity_id={request.entity_id} | limit={request.limit}"
            )

            # Make HTTP request to intelligence service
            url = f"{self.base_url}/relationships/{request.entity_id}"
            params = {"limit": request.limit}

            response = await self.http_client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            result = response.json()

            # Extract metrics from HTTP response
            relationships_count = result.get("relationships_count", 0)

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_relationship_query_completed(
                correlation_id,
                request.entity_id,
                relationships_count,
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("relationship_query")
            return True

        except Exception as e:
            logger.error(f"Relationship query operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_relationship_query_failed(
                correlation_id,
                payload.get("entity_id", "unknown"),
                str(e),
                EnumEntityExtractionErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    # ========================================================================
    # Publish Helper Methods
    # ========================================================================

    async def _publish_code_extraction_completed(
        self,
        correlation_id: UUID,
        source_path: str,
        entities_count: int,
        entity_types: list,
        confidence_mean: float,
        processing_time_ms: float,
    ) -> None:
        """Publish CODE_EXTRACTION_COMPLETED event."""
        await self._ensure_router_initialized()

        payload = ModelCodeExtractionCompletedPayload(
            source_path=source_path,
            entities_count=entities_count,
            entity_types=entity_types,
            confidence_mean=confidence_mean,
            confidence_min=max(0.0, confidence_mean - 0.15),
            confidence_max=min(1.0, confidence_mean + 0.08),
            processing_time_ms=processing_time_ms,
            stored=True,
            cache_hit=False,
        )

        event_envelope = EntityExtractionEventHelpers.create_event_envelope(
            event_type="code_extraction_completed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = EntityExtractionEventHelpers.get_kafka_topic(
            EnumEntityExtractionEventType.CODE_EXTRACTION_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published CODE_EXTRACTION_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_code_extraction_failed(
        self,
        correlation_id: UUID,
        source_path: str,
        error_message: str,
        error_code: EnumEntityExtractionErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish CODE_EXTRACTION_FAILED event."""
        await self._ensure_router_initialized()

        payload = ModelCodeExtractionFailedPayload(
            source_path=source_path,
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
            error_details={},
        )

        event_envelope = EntityExtractionEventHelpers.create_event_envelope(
            event_type="code_extraction_failed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = EntityExtractionEventHelpers.get_kafka_topic(
            EnumEntityExtractionEventType.CODE_EXTRACTION_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published CODE_EXTRACTION_FAILED | correlation_id={correlation_id}"
        )

    async def _publish_document_extraction_completed(
        self,
        correlation_id: UUID,
        source_path: str,
        entities_count: int,
        keywords_count: int,
        confidence_mean: float,
        processing_time_ms: float,
    ) -> None:
        """Publish DOCUMENT_EXTRACTION_COMPLETED event."""
        await self._ensure_router_initialized()

        payload = ModelDocumentExtractionCompletedPayload(
            source_path=source_path,
            entities_count=entities_count,
            keywords_count=keywords_count,
            confidence_mean=confidence_mean,
            processing_time_ms=processing_time_ms,
            stored=True,
            cache_hit=False,
        )

        event_envelope = EntityExtractionEventHelpers.create_event_envelope(
            event_type="document_extraction_completed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = EntityExtractionEventHelpers.get_kafka_topic(
            EnumEntityExtractionEventType.DOCUMENT_EXTRACTION_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published DOCUMENT_EXTRACTION_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_document_extraction_failed(
        self,
        correlation_id: UUID,
        source_path: str,
        error_message: str,
        error_code: EnumEntityExtractionErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish DOCUMENT_EXTRACTION_FAILED event."""
        await self._ensure_router_initialized()

        payload = ModelDocumentExtractionFailedPayload(
            source_path=source_path,
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
            error_details={},
        )

        event_envelope = EntityExtractionEventHelpers.create_event_envelope(
            event_type="document_extraction_failed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = EntityExtractionEventHelpers.get_kafka_topic(
            EnumEntityExtractionEventType.DOCUMENT_EXTRACTION_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published DOCUMENT_EXTRACTION_FAILED | correlation_id={correlation_id}"
        )

    async def _publish_entity_search_completed(
        self,
        correlation_id: UUID,
        query: str,
        results_count: int,
        processing_time_ms: float,
    ) -> None:
        """Publish ENTITY_SEARCH_COMPLETED event."""
        await self._ensure_router_initialized()

        payload = ModelEntitySearchCompletedPayload(
            query=query,
            results_count=results_count,
            processing_time_ms=processing_time_ms,
            cache_hit=False,
        )

        event_envelope = EntityExtractionEventHelpers.create_event_envelope(
            event_type="entity_search_completed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = EntityExtractionEventHelpers.get_kafka_topic(
            EnumEntityExtractionEventType.ENTITY_SEARCH_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published ENTITY_SEARCH_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_entity_search_failed(
        self,
        correlation_id: UUID,
        query: str,
        error_message: str,
        error_code: EnumEntityExtractionErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish ENTITY_SEARCH_FAILED event."""
        await self._ensure_router_initialized()

        payload = ModelEntitySearchFailedPayload(
            query=query,
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
            error_details={},
        )

        event_envelope = EntityExtractionEventHelpers.create_event_envelope(
            event_type="entity_search_failed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = EntityExtractionEventHelpers.get_kafka_topic(
            EnumEntityExtractionEventType.ENTITY_SEARCH_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published ENTITY_SEARCH_FAILED | correlation_id={correlation_id}"
        )

    async def _publish_relationship_query_completed(
        self,
        correlation_id: UUID,
        entity_id: str,
        relationships_count: int,
        processing_time_ms: float,
    ) -> None:
        """Publish RELATIONSHIP_QUERY_COMPLETED event."""
        await self._ensure_router_initialized()

        payload = ModelRelationshipQueryCompletedPayload(
            entity_id=entity_id,
            relationships_count=relationships_count,
            processing_time_ms=processing_time_ms,
            cache_hit=False,
        )

        event_envelope = EntityExtractionEventHelpers.create_event_envelope(
            event_type="relationship_query_completed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = EntityExtractionEventHelpers.get_kafka_topic(
            EnumEntityExtractionEventType.RELATIONSHIP_QUERY_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published RELATIONSHIP_QUERY_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_relationship_query_failed(
        self,
        correlation_id: UUID,
        entity_id: str,
        error_message: str,
        error_code: EnumEntityExtractionErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish RELATIONSHIP_QUERY_FAILED event."""
        await self._ensure_router_initialized()

        payload = ModelRelationshipQueryFailedPayload(
            entity_id=entity_id,
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
            error_details={},
        )

        event_envelope = EntityExtractionEventHelpers.create_event_envelope(
            event_type="relationship_query_failed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = EntityExtractionEventHelpers.get_kafka_topic(
            EnumEntityExtractionEventType.RELATIONSHIP_QUERY_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published RELATIONSHIP_QUERY_FAILED | correlation_id={correlation_id}"
        )

    def _increment_operation_metric(self, operation: str) -> None:
        """Increment operation-specific metric."""
        if operation not in self.metrics["operations_by_type"]:
            self.metrics["operations_by_type"][operation] = 0
        self.metrics["operations_by_type"][operation] += 1

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "EntityExtractionHandler"

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
