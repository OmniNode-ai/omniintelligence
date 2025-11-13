"""
Freshness Event Handler

Handles freshness operation events and publishes COMPLETED/FAILED responses.
Implements event-driven interface for document freshness tracking and analysis.

Created: 2025-10-22
Purpose: Event-driven freshness operations integration
"""

import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import quote
from uuid import UUID

import httpx
from src.events.models.freshness_events import (
    EnumFreshnessErrorCode,
    EnumFreshnessEventType,
    FreshnessEventHelpers,
    ModelFreshnessAnalysesCompletedPayload,
    ModelFreshnessAnalysesFailedPayload,
    ModelFreshnessAnalysesRequestPayload,
    ModelFreshnessAnalyzeCompletedPayload,
    ModelFreshnessAnalyzeFailedPayload,
    ModelFreshnessAnalyzeRequestPayload,
    ModelFreshnessCleanupCompletedPayload,
    ModelFreshnessCleanupFailedPayload,
    ModelFreshnessCleanupRequestPayload,
    ModelFreshnessDocumentCompletedPayload,
    ModelFreshnessDocumentFailedPayload,
    ModelFreshnessDocumentRequestPayload,
    ModelFreshnessDocumentUpdateCompletedPayload,
    ModelFreshnessDocumentUpdateFailedPayload,
    ModelFreshnessDocumentUpdateRequestPayload,
    ModelFreshnessEventStatsCompletedPayload,
    ModelFreshnessEventStatsFailedPayload,
    ModelFreshnessEventStatsRequestPayload,
    ModelFreshnessRefreshCompletedPayload,
    ModelFreshnessRefreshFailedPayload,
    ModelFreshnessRefreshRequestPayload,
    ModelFreshnessStaleCompletedPayload,
    ModelFreshnessStaleFailedPayload,
    ModelFreshnessStaleRequestPayload,
    ModelFreshnessStatsCompletedPayload,
    ModelFreshnessStatsFailedPayload,
    ModelFreshnessStatsRequestPayload,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class FreshnessHandler(BaseResponsePublisher):
    """
    Handle freshness operation events and publish results.

    This handler implements the Freshness Effect Node pattern,
    consuming freshness requests from the event bus and publishing
    results back.

    Event Flow:
        1. Consume FRESHNESS_{OPERATION}_REQUESTED event
        2. Extract parameters and operation type
        3. Execute freshness operation
        4. Publish FRESHNESS_{OPERATION}_COMPLETED (success) or FAILED (error)

    Supported Operations:
        - ANALYZE: Analyze document freshness
        - STALE: Get stale documents
        - REFRESH: Refresh documents
        - STATS: Get freshness statistics
        - DOCUMENT: Get single document freshness
        - CLEANUP: Cleanup old freshness data
        - DOCUMENT_UPDATE: Update document freshness
        - EVENT_STATS: Get event statistics
        - ANALYSES: Get freshness analyses
    """

    # Service endpoints
    INTELLIGENCE_SERVICE_URL = os.getenv(
        "INTELLIGENCE_SERVICE_URL",
        "http://localhost:8053",  # Fallback for local dev only
    )

    def __init__(self, intelligence_url: Optional[str] = None):
        """Initialize Freshness handler.

        Args:
            intelligence_url: Optional Intelligence service URL (default: localhost:8053)
        """
        super().__init__()

        # Service URL
        self.intelligence_url = intelligence_url or self.INTELLIGENCE_SERVICE_URL

        # HTTP client
        self.http_client: Optional[httpx.AsyncClient] = None

        # Metrics
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "operations_by_type": {},
        }

    async def _ensure_http_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=30.0)

    async def _close_http_client(self) -> None:
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    def can_handle(self, event_type: str) -> bool:
        """Check if this handler can process the given event type."""
        return any(
            keyword in event_type.lower()
            for keyword in [
                "freshness_analyze_requested",
                "freshness_stale_requested",
                "freshness_refresh_requested",
                "freshness_stats_requested",
                "freshness_document_requested",
                "freshness_cleanup_requested",
                "freshness_document_update_requested",
                "freshness_event_stats_requested",
                "freshness_analyses_requested",
                "freshness.analyze",
                "freshness.stale",
                "freshness.refresh",
                "freshness.stats",
                "freshness.document",
                "freshness.cleanup",
                "freshness.event-stats",
                "freshness.analyses",
            ]
        )

    async def handle_event(self, event: Any) -> bool:
        """
        Handle freshness operation events.

        Routes to appropriate operation handler based on event type.

        Args:
            event: Event envelope with freshness operation payload

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
                "analyze" in event_type_str.lower()
                and "analyses" not in event_type_str.lower()
            ):
                return await self._handle_analyze(correlation_id, payload, start_time)
            elif "stale" in event_type_str.lower():
                return await self._handle_stale(correlation_id, payload, start_time)
            elif "refresh" in event_type_str.lower():
                return await self._handle_refresh(correlation_id, payload, start_time)
            elif (
                "stats" in event_type_str.lower()
                and "event" not in event_type_str.lower()
            ):
                return await self._handle_stats(correlation_id, payload, start_time)
            elif "document_update" in event_type_str.lower():
                return await self._handle_document_update(
                    correlation_id, payload, start_time
                )
            elif (
                "document" in event_type_str.lower()
                and "update" not in event_type_str.lower()
            ):
                return await self._handle_document(correlation_id, payload, start_time)
            elif "cleanup" in event_type_str.lower():
                return await self._handle_cleanup(correlation_id, payload, start_time)
            elif (
                "event" in event_type_str.lower() and "stats" in event_type_str.lower()
            ):
                return await self._handle_event_stats(
                    correlation_id, payload, start_time
                )
            elif "analyses" in event_type_str.lower():
                return await self._handle_analyses(correlation_id, payload, start_time)
            else:
                logger.error(f"Unknown freshness operation type: {event_type_str}")
                return False

        except Exception as e:
            logger.error(
                f"Freshness handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_analyze(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FRESHNESS_ANALYZE operation."""
        try:
            request = ModelFreshnessAnalyzeRequestPayload(**payload)
            logger.info(
                f"Processing FRESHNESS_ANALYZE | correlation_id={correlation_id} | documents={len(request.document_paths)}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            json_payload = {"document_paths": request.document_paths}
            if request.project_id:
                json_payload["project_id"] = request.project_id

            response = await self.http_client.post(
                f"{self.intelligence_url}/freshness/analyze",
                json=json_payload,
                timeout=15.0,
            )
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_analyze_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("analyze")

            logger.info(
                f"FRESHNESS_ANALYZE_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_analyze_failed(
                correlation_id,
                f"Service error: {e.response.status_code}",
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Analyze operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_analyze_failed(
                correlation_id,
                str(e),
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_stale(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FRESHNESS_STALE operation."""
        try:
            request = ModelFreshnessStaleRequestPayload(**payload)
            logger.info(
                f"Processing FRESHNESS_STALE | correlation_id={correlation_id} | threshold_days={request.threshold_days}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            params = {}
            if request.threshold_days is not None:
                params["threshold_days"] = request.threshold_days

            response = await self.http_client.get(
                f"{self.intelligence_url}/freshness/stale",
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_stale_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("stale")

            logger.info(
                f"FRESHNESS_STALE_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_stale_failed(
                correlation_id,
                f"Service error: {e.response.status_code}",
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Stale operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_stale_failed(
                correlation_id,
                str(e),
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_refresh(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FRESHNESS_REFRESH operation."""
        try:
            request = ModelFreshnessRefreshRequestPayload(**payload)
            logger.info(
                f"Processing FRESHNESS_REFRESH | correlation_id={correlation_id} | documents={len(request.document_paths)}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            response = await self.http_client.post(
                f"{self.intelligence_url}/freshness/refresh",
                json={"document_paths": request.document_paths},
                timeout=20.0,
            )
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_refresh_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("refresh")

            logger.info(
                f"FRESHNESS_REFRESH_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_refresh_failed(
                correlation_id,
                f"Service error: {e.response.status_code}",
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Refresh operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_refresh_failed(
                correlation_id,
                str(e),
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_stats(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FRESHNESS_STATS operation."""
        try:
            request = ModelFreshnessStatsRequestPayload(**payload)
            logger.info(f"Processing FRESHNESS_STATS | correlation_id={correlation_id}")

            # Call Intelligence service
            await self._ensure_http_client()
            response = await self.http_client.get(
                f"{self.intelligence_url}/freshness/stats",
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_stats_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("stats")

            logger.info(
                f"FRESHNESS_STATS_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_stats_failed(
                correlation_id,
                f"Service error: {e.response.status_code}",
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Stats operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_stats_failed(
                correlation_id,
                str(e),
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_document(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FRESHNESS_DOCUMENT operation."""
        try:
            request = ModelFreshnessDocumentRequestPayload(**payload)
            logger.info(
                f"Processing FRESHNESS_DOCUMENT | correlation_id={correlation_id} | path={request.document_path}"
            )

            # Call Intelligence service - URL encode the document path
            await self._ensure_http_client()
            encoded_path = quote(request.document_path, safe="")
            response = await self.http_client.get(
                f"{self.intelligence_url}/freshness/document/{encoded_path}",
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("document")

            logger.info(
                f"FRESHNESS_DOCUMENT_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_failed(
                correlation_id,
                payload.get("document_path", "unknown"),
                f"Service error: {e.response.status_code}",
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Document operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_failed(
                correlation_id,
                payload.get("document_path", "unknown"),
                str(e),
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_cleanup(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FRESHNESS_CLEANUP operation."""
        try:
            request = ModelFreshnessCleanupRequestPayload(**payload)
            logger.info(
                f"Processing FRESHNESS_CLEANUP | correlation_id={correlation_id} | older_than_days={request.older_than_days}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            params = {}
            if request.older_than_days is not None:
                params["older_than_days"] = request.older_than_days
            if request.dry_run is not None:
                params["dry_run"] = str(request.dry_run).lower()

            response = await self.http_client.delete(
                f"{self.intelligence_url}/freshness/cleanup",
                params=params,
                timeout=15.0,
            )
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_cleanup_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("cleanup")

            logger.info(
                f"FRESHNESS_CLEANUP_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_cleanup_failed(
                correlation_id,
                f"Service error: {e.response.status_code}",
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Cleanup operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_cleanup_failed(
                correlation_id,
                str(e),
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_document_update(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FRESHNESS_DOCUMENT_UPDATE operation."""
        try:
            request = ModelFreshnessDocumentUpdateRequestPayload(**payload)
            logger.info(
                f"Processing FRESHNESS_DOCUMENT_UPDATE | correlation_id={correlation_id} | path={request.document_path}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            response = await self.http_client.post(
                f"{self.intelligence_url}/freshness/events/document-update",
                json={
                    "document_path": request.document_path,
                    "event_type": request.event_type,
                    "metadata": request.metadata or {},
                },
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_update_completed(
                correlation_id, result, duration_ms
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("document_update")

            logger.info(
                f"FRESHNESS_DOCUMENT_UPDATE_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_update_failed(
                correlation_id,
                payload.get("document_path", "unknown"),
                payload.get("event_type", "unknown"),
                f"Service error: {e.response.status_code}",
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Document update operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_update_failed(
                correlation_id,
                payload.get("document_path", "unknown"),
                payload.get("event_type", "unknown"),
                str(e),
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_event_stats(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FRESHNESS_EVENT_STATS operation."""
        try:
            request = ModelFreshnessEventStatsRequestPayload(**payload)
            logger.info(
                f"Processing FRESHNESS_EVENT_STATS | correlation_id={correlation_id}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            params = {}
            if request.time_window_hours is not None:
                params["time_window_hours"] = request.time_window_hours

            response = await self.http_client.get(
                f"{self.intelligence_url}/freshness/events/stats",
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_event_stats_completed(
                correlation_id, result, duration_ms
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("event_stats")

            logger.info(
                f"FRESHNESS_EVENT_STATS_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_event_stats_failed(
                correlation_id,
                f"Service error: {e.response.status_code}",
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Event stats operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_event_stats_failed(
                correlation_id,
                str(e),
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_analyses(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FRESHNESS_ANALYSES operation."""
        import httpx

        try:
            request = ModelFreshnessAnalysesRequestPayload(**payload)
            logger.info(
                f"Processing FRESHNESS_ANALYSES | correlation_id={correlation_id} | limit={request.limit}"
            )

            # Make HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {}
                if request.limit:
                    params["limit"] = request.limit

                response = await client.get(
                    f"{self.intelligence_url}/freshness/analyses", params=params
                )
                response.raise_for_status()
                data = response.json()

            result = {
                "analyses": data.get("analyses", []),
                "total_count": data.get("total_count", len(data.get("analyses", []))),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_analyses_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("analyses")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Analyses HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_analyses_failed(
                correlation_id,
                f"HTTP {e.response.status_code}: {e.response.text}",
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Analyses operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_analyses_failed(
                correlation_id,
                str(e),
                EnumFreshnessErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    # ========================================================================
    # Publish Helper Methods
    # ========================================================================

    async def _publish_analyze_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish FRESHNESS_ANALYZE_COMPLETED event."""
        await self._ensure_router_initialized()

        payload = ModelFreshnessAnalyzeCompletedPayload(
            analyzed_count=result["analyzed_count"],
            stale_count=result["stale_count"],
            fresh_count=result["fresh_count"],
            results=result["results"],
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            event_type="freshness_analyze_completed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = FreshnessEventHelpers.get_kafka_topic("freshness_analyze_completed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published FRESHNESS_ANALYZE_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_analyze_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumFreshnessErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish FRESHNESS_ANALYZE_FAILED event."""
        await self._ensure_router_initialized()

        payload = ModelFreshnessAnalyzeFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
            error_details={},
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            event_type="freshness_analyze_failed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = FreshnessEventHelpers.get_kafka_topic("freshness_analyze_failed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published FRESHNESS_ANALYZE_FAILED | correlation_id={correlation_id}"
        )

    # NOTE: Similar publish methods for other operations would follow the same pattern
    # For brevity, implementing complete set for all 9 operations would be repetitive
    # Additional publish methods: stale, refresh, stats, document, cleanup, document_update, event_stats, analyses

    async def _publish_stale_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish FRESHNESS_STALE_COMPLETED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessStaleCompletedPayload(
            stale_documents=result["stale_documents"],
            total_count=result["total_count"],
            threshold_days=result["threshold_days"],
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_stale_completed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_stale_completed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_stale_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumFreshnessErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish FRESHNESS_STALE_FAILED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessStaleFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_stale_failed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_stale_failed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_refresh_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish FRESHNESS_REFRESH_COMPLETED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessRefreshCompletedPayload(
            refreshed_count=result["refreshed_count"],
            failed_count=result["failed_count"],
            skipped_count=result["skipped_count"],
            results=result["results"],
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_refresh_completed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_refresh_completed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_refresh_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumFreshnessErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish FRESHNESS_REFRESH_FAILED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessRefreshFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_refresh_failed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_refresh_failed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_stats_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish FRESHNESS_STATS_COMPLETED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessStatsCompletedPayload(
            total_documents=result["total_documents"],
            stale_documents=result["stale_documents"],
            fresh_documents=result["fresh_documents"],
            average_age_days=result["average_age_days"],
            breakdown=result["breakdown"],
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_stats_completed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_stats_completed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_stats_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumFreshnessErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish FRESHNESS_STATS_FAILED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessStatsFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_stats_failed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_stats_failed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_document_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish FRESHNESS_DOCUMENT_COMPLETED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessDocumentCompletedPayload(
            document_path=result["document_path"],
            is_stale=result["is_stale"],
            age_days=result["age_days"],
            last_modified=result["last_modified"],
            freshness_score=result["freshness_score"],
            history=result.get("history"),
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_document_completed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_document_completed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_document_failed(
        self,
        correlation_id: UUID,
        document_path: str,
        error_message: str,
        error_code: EnumFreshnessErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish FRESHNESS_DOCUMENT_FAILED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessDocumentFailedPayload(
            document_path=document_path,
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_document_failed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_document_failed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_cleanup_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish FRESHNESS_CLEANUP_COMPLETED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessCleanupCompletedPayload(
            deleted_count=result["deleted_count"],
            skipped_count=result["skipped_count"],
            dry_run=result["dry_run"],
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_cleanup_completed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_cleanup_completed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_cleanup_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumFreshnessErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish FRESHNESS_CLEANUP_FAILED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessCleanupFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_cleanup_failed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_cleanup_failed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_document_update_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish FRESHNESS_DOCUMENT_UPDATE_COMPLETED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessDocumentUpdateCompletedPayload(
            document_path=result["document_path"],
            event_type=result["event_type"],
            updated=result["updated"],
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_document_update_completed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic(
            "freshness_document_update_completed"
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_document_update_failed(
        self,
        correlation_id: UUID,
        document_path: str,
        event_type: str,
        error_message: str,
        error_code: EnumFreshnessErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish FRESHNESS_DOCUMENT_UPDATE_FAILED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessDocumentUpdateFailedPayload(
            document_path=document_path,
            event_type=event_type,
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_document_update_failed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic(
            "freshness_document_update_failed"
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_event_stats_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish FRESHNESS_EVENT_STATS_COMPLETED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessEventStatsCompletedPayload(
            total_events=result["total_events"],
            events_by_type=result["events_by_type"],
            time_window_hours=result["time_window_hours"],
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_event_stats_completed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_event_stats_completed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_event_stats_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumFreshnessErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish FRESHNESS_EVENT_STATS_FAILED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessEventStatsFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_event_stats_failed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_event_stats_failed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_analyses_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish FRESHNESS_ANALYSES_COMPLETED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessAnalysesCompletedPayload(
            analyses=result["analyses"],
            total_count=result["total_count"],
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_analyses_completed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_analyses_completed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    async def _publish_analyses_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumFreshnessErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish FRESHNESS_ANALYSES_FAILED event."""
        await self._ensure_router_initialized()
        payload = ModelFreshnessAnalysesFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )

        event_envelope = FreshnessEventHelpers.create_event_envelope(
            "freshness_analyses_failed",
            payload,
            correlation_id,
        )
        topic = FreshnessEventHelpers.get_kafka_topic("freshness_analyses_failed")
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )

    def _increment_operation_metric(self, operation: str) -> None:
        """Increment operation-specific metric."""
        if operation not in self.metrics["operations_by_type"]:
            self.metrics["operations_by_type"][operation] = 0
        self.metrics["operations_by_type"][operation] += 1

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "FreshnessHandler"

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
