"""
Document Processing Event Handler

Handles document processing events:
- PROCESS_DOCUMENT_REQUESTED: Process single document
- BATCH_INDEX_REQUESTED: Batch index multiple documents

Implements event-driven document processing with entity extraction,
embedding generation, and batch operations.

Created: 2025-10-22
Purpose: Phase 4 - Bridge & Utility Events Implementation
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from src.events.models.document_processing_events import (
    EnumDocumentProcessingErrorCode,
    EnumDocumentProcessingEventType,
    create_batch_index_completed,
    create_batch_index_failed,
    create_process_document_completed,
    create_process_document_failed,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class DocumentProcessingHandler(BaseResponsePublisher):
    """
    Handle document processing events and orchestrate document intelligence operations.

    Event Flow:
        1. Consume document processing request events
        2. Call appropriate service HTTP endpoints
        3. Publish COMPLETED (success) or FAILED (error) response

    Topics:
        - Process Document:
            - Request: dev.archon-intelligence.document.process-document-requested.v1
            - Completed: dev.archon-intelligence.document.process-document-completed.v1
            - Failed: dev.archon-intelligence.document.process-document-failed.v1
        - Batch Index:
            - Request: dev.archon-intelligence.document.batch-index-requested.v1
            - Completed: dev.archon-intelligence.document.batch-index-completed.v1
            - Failed: dev.archon-intelligence.document.batch-index-failed.v1

    Service Integration:
        - Intelligence (8053): Document processing and entity extraction
    """

    # Topic constants
    PROCESS_DOCUMENT_REQUEST_TOPIC = (
        "dev.archon-intelligence.document.process-document-requested.v1"
    )
    PROCESS_DOCUMENT_COMPLETED_TOPIC = (
        "dev.archon-intelligence.document.process-document-completed.v1"
    )
    PROCESS_DOCUMENT_FAILED_TOPIC = (
        "dev.archon-intelligence.document.process-document-failed.v1"
    )

    BATCH_INDEX_REQUEST_TOPIC = (
        "dev.archon-intelligence.document.batch-index-requested.v1"
    )
    BATCH_INDEX_COMPLETED_TOPIC = (
        "dev.archon-intelligence.document.batch-index-completed.v1"
    )
    BATCH_INDEX_FAILED_TOPIC = "dev.archon-intelligence.document.batch-index-failed.v1"

    # Service endpoints
    INTELLIGENCE_URL = os.getenv(
        "INTELLIGENCE_SERVICE_URL", "http://localhost:8053"  # Fallback for local dev
    )

    # Timeouts (in seconds)
    PROCESS_DOCUMENT_TIMEOUT = 30.0
    BATCH_INDEX_TIMEOUT = 300.0  # 5 minutes for batch operations

    def __init__(self, intelligence_url: Optional[str] = None):
        """
        Initialize Document Processing handler.

        Args:
            intelligence_url: Optional Intelligence service URL (default: localhost:8053)
        """
        super().__init__()

        # Service URL
        self.intelligence_url = intelligence_url or self.INTELLIGENCE_URL

        # HTTP client
        self.http_client: Optional[httpx.AsyncClient] = None

        # Metrics
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "process_document_successes": 0,
            "process_document_failures": 0,
            "batch_index_successes": 0,
            "batch_index_failures": 0,
            "total_documents_processed": 0,
        }

    async def _ensure_http_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=60.0)

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
            True if event type matches any document processing operation
        """
        return event_type in [
            EnumDocumentProcessingEventType.PROCESS_DOCUMENT_REQUESTED.value,
            "PROCESS_DOCUMENT_REQUESTED",
            "document.process-document-requested",
            EnumDocumentProcessingEventType.BATCH_INDEX_REQUESTED.value,
            "BATCH_INDEX_REQUESTED",
            "document.batch-index-requested",
        ]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle document processing request events.

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

            # Route to appropriate handler
            if (
                "process-document" in event_type_lower
                or "process_document" in event_type_lower
            ):
                return await self._handle_process_document(
                    correlation_id, payload, start_time
                )
            elif "batch-index" in event_type_lower or "batch_index" in event_type_lower:
                return await self._handle_batch_index(
                    correlation_id, payload, start_time
                )
            else:
                logger.warning(
                    f"Unknown document processing event type: {event_type_str}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Document processing handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_process_document(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """Handle PROCESS_DOCUMENT_REQUESTED event."""
        try:
            # Extract required fields
            document_path = payload.get("document_path")
            content = payload.get("content")
            document_type = payload.get("document_type", "auto")
            processing_options = payload.get("processing_options", {})
            extract_entities = payload.get("extract_entities", True)
            generate_embeddings = payload.get("generate_embeddings", True)

            # Validate required fields
            if not document_path:
                logger.error(
                    f"Missing document_path in PROCESS_DOCUMENT_REQUESTED | correlation_id={correlation_id}"
                )
                await self._publish_process_document_failed(
                    correlation_id=correlation_id,
                    document_path="unknown",
                    error_code=EnumDocumentProcessingErrorCode.INVALID_INPUT,
                    error_message="Missing required field: document_path",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["process_document_failures"] += 1
                return False

            logger.info(
                f"Processing PROCESS_DOCUMENT_REQUESTED | correlation_id={correlation_id} | "
                f"document_path={document_path} | document_type={document_type}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            response = await self.http_client.post(
                f"{self.intelligence_url}/process/document",
                json={
                    "document_path": document_path,
                    "content": content,
                    "document_type": document_type,
                    "processing_options": processing_options,
                    "extract_entities": extract_entities,
                    "generate_embeddings": generate_embeddings,
                },
                timeout=self.PROCESS_DOCUMENT_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_process_document_completed(
                correlation_id=correlation_id,
                result=result,
                document_path=document_path,
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["process_document_successes"] += 1
            self.metrics["total_documents_processed"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"PROCESS_DOCUMENT_COMPLETED | correlation_id={correlation_id} | "
                f"entities_extracted={result.get('entities_extracted', 0)} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            await self._publish_process_document_failed(
                correlation_id=correlation_id,
                document_path=payload.get("document_path", "unknown"),
                error_code=EnumDocumentProcessingErrorCode.INTERNAL_ERROR,
                error_message=f"Service error: {e.response.status_code}",
                retry_allowed=True,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                error_details={"status_code": e.response.status_code},
            )
            self.metrics["process_document_failures"] += 1
            return False

        except Exception as e:
            logger.error(f"Process document failed: {e}", exc_info=True)
            await self._publish_process_document_failed(
                correlation_id=correlation_id,
                document_path=payload.get("document_path", "unknown"),
                error_code=EnumDocumentProcessingErrorCode.INTERNAL_ERROR,
                error_message=f"Internal error: {str(e)}",
                retry_allowed=True,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                error_details={"exception_type": type(e).__name__},
            )
            self.metrics["process_document_failures"] += 1
            return False

    async def _handle_batch_index(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """Handle BATCH_INDEX_REQUESTED event."""
        try:
            # Extract required fields
            document_paths = payload.get("document_paths", [])
            batch_options = payload.get("batch_options", {})
            skip_existing = payload.get("skip_existing", True)
            parallel_workers = payload.get("parallel_workers", 4)

            # Validate required fields
            if not document_paths:
                logger.error(
                    f"Missing document_paths in BATCH_INDEX_REQUESTED | correlation_id={correlation_id}"
                )
                await self._publish_batch_index_failed(
                    correlation_id=correlation_id,
                    total_documents=0,
                    error_code=EnumDocumentProcessingErrorCode.INVALID_INPUT,
                    error_message="Missing required field: document_paths",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["batch_index_failures"] += 1
                return False

            if len(document_paths) > 1000:
                logger.error(
                    f"Batch too large: {len(document_paths)} documents | correlation_id={correlation_id}"
                )
                await self._publish_batch_index_failed(
                    correlation_id=correlation_id,
                    total_documents=len(document_paths),
                    error_code=EnumDocumentProcessingErrorCode.BATCH_TOO_LARGE,
                    error_message=f"Batch size {len(document_paths)} exceeds limit of 1000",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["batch_index_failures"] += 1
                return False

            logger.info(
                f"Processing BATCH_INDEX_REQUESTED | correlation_id={correlation_id} | "
                f"document_count={len(document_paths)} | parallel_workers={parallel_workers}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            response = await self.http_client.post(
                f"{self.intelligence_url}/batch-index",
                json={
                    "document_paths": document_paths,
                    "batch_options": batch_options,
                    "skip_existing": skip_existing,
                    "parallel_workers": parallel_workers,
                },
                timeout=self.BATCH_INDEX_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_batch_index_completed(
                correlation_id=correlation_id,
                result=result,
                total_documents=len(document_paths),
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["batch_index_successes"] += 1
            self.metrics["total_documents_processed"] += result.get(
                "documents_indexed", 0
            )
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"BATCH_INDEX_COMPLETED | correlation_id={correlation_id} | "
                f"documents_indexed={result.get('documents_indexed', 0)} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            await self._publish_batch_index_failed(
                correlation_id=correlation_id,
                total_documents=len(payload.get("document_paths", [])),
                error_code=EnumDocumentProcessingErrorCode.INTERNAL_ERROR,
                error_message=f"Service error: {e.response.status_code}",
                retry_allowed=True,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                partial_results={"status_code": e.response.status_code},
            )
            self.metrics["batch_index_failures"] += 1
            return False

        except Exception as e:
            logger.error(f"Batch index failed: {e}", exc_info=True)
            await self._publish_batch_index_failed(
                correlation_id=correlation_id,
                total_documents=len(payload.get("document_paths", [])),
                error_code=EnumDocumentProcessingErrorCode.INTERNAL_ERROR,
                error_message=f"Internal error: {str(e)}",
                retry_allowed=True,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                partial_results={"exception_type": type(e).__name__},
            )
            self.metrics["batch_index_failures"] += 1
            return False

    async def _publish_process_document_completed(
        self,
        correlation_id: UUID,
        result: Dict[str, Any],
        document_path: str,
        processing_time_ms: float,
    ) -> None:
        """Publish PROCESS_DOCUMENT_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_process_document_completed(
                document_path=document_path,
                entities_extracted=result.get("entities_extracted", 0),
                embeddings_generated=result.get("embeddings_generated", 0),
                processing_results=result.get("processing_results", {}),
                processing_time_ms=processing_time_ms,
                correlation_id=correlation_id,
                cache_hit=result.get("cache_hit", False),
            )

            await self._router.publish(
                topic=self.PROCESS_DOCUMENT_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.info(
                f"Published PROCESS_DOCUMENT_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish completed response: {e}", exc_info=True)
            raise

    async def _publish_process_document_failed(
        self,
        correlation_id: UUID,
        document_path: str,
        error_code: EnumDocumentProcessingErrorCode,
        error_message: str,
        retry_allowed: bool,
        processing_time_ms: float,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish PROCESS_DOCUMENT_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_process_document_failed(
                document_path=document_path,
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
                error_details=error_details,
            )

            await self._router.publish(
                topic=self.PROCESS_DOCUMENT_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published PROCESS_DOCUMENT_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish failed response: {e}", exc_info=True)
            raise

    async def _publish_batch_index_completed(
        self,
        correlation_id: UUID,
        result: Dict[str, Any],
        total_documents: int,
        processing_time_ms: float,
    ) -> None:
        """Publish BATCH_INDEX_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_batch_index_completed(
                total_documents=total_documents,
                documents_indexed=result.get("documents_indexed", 0),
                documents_skipped=result.get("documents_skipped", 0),
                documents_failed=result.get("documents_failed", 0),
                batch_results=result.get("batch_results", {}),
                processing_time_ms=processing_time_ms,
                correlation_id=correlation_id,
                failed_documents=result.get("failed_documents", []),
            )

            await self._router.publish(
                topic=self.BATCH_INDEX_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.info(
                f"Published BATCH_INDEX_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish batch index completed: {e}", exc_info=True)
            raise

    async def _publish_batch_index_failed(
        self,
        correlation_id: UUID,
        total_documents: int,
        error_code: EnumDocumentProcessingErrorCode,
        error_message: str,
        retry_allowed: bool,
        processing_time_ms: float,
        partial_results: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish BATCH_INDEX_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_batch_index_failed(
                total_documents=total_documents,
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
                partial_results=partial_results,
            )

            await self._router.publish(
                topic=self.BATCH_INDEX_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published BATCH_INDEX_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish batch index failed: {e}", exc_info=True)
            raise

    def _get_correlation_id(self, event: Any) -> UUID:
        """Extract correlation ID from event."""
        if isinstance(event, dict):
            correlation_id = event.get("correlation_id")
            if correlation_id is None:
                payload = event.get("payload", {})
                correlation_id = payload.get("correlation_id")
        else:
            correlation_id = getattr(event, "correlation_id", None)
            if correlation_id is None:
                payload = getattr(event, "payload", {})
                correlation_id = payload.get("correlation_id")

        if correlation_id is None:
            raise ValueError("Event missing correlation_id")

        # Maintain UUID type throughout - no conversion to string
        if not isinstance(correlation_id, UUID):
            raise TypeError(f"correlation_id must be UUID, got {type(correlation_id)}")

        return correlation_id

    def _get_payload(self, event: Any) -> Dict[str, Any]:
        """Extract payload from event."""
        if isinstance(event, dict):
            payload = event.get("payload", event)
        else:
            payload = getattr(event, "payload", None)
            if payload is None:
                raise ValueError("Event missing payload")

        return payload

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
        return "DocumentProcessingHandler"

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
        await self._close_http_client()
        await self._shutdown_publisher()
        logger.info("Document processing handler shutdown complete")
