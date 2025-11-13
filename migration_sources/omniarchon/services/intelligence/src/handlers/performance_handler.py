"""
Performance Optimization Event Handler

Handles performance optimization request events and publishes completed/failed responses.
Implements event-driven interface for performance baseline, optimization, and trend analysis.

Handles 5 event types:
1. BASELINE_REQUESTED → BASELINE_COMPLETED/FAILED
2. OPPORTUNITIES_REQUESTED → OPPORTUNITIES_COMPLETED/FAILED
3. OPTIMIZE_REQUESTED → OPTIMIZE_COMPLETED/FAILED
4. REPORT_REQUESTED → REPORT_COMPLETED/FAILED
5. TRENDS_REQUESTED → TRENDS_COMPLETED/FAILED

Created: 2025-10-22
Purpose: Event-driven performance optimization integration for Phase 1
"""

import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from src.events.models.performance_events import (
    EnumPerformanceErrorCode,
    EnumPerformanceEventType,
    ModelBaselineCompletedPayload,
    ModelBaselineFailedPayload,
    ModelBaselineRequestPayload,
    ModelOpportunitiesCompletedPayload,
    ModelOpportunitiesFailedPayload,
    ModelOpportunitiesRequestPayload,
    ModelOptimizeCompletedPayload,
    ModelOptimizeFailedPayload,
    ModelOptimizeRequestPayload,
    ModelReportCompletedPayload,
    ModelReportFailedPayload,
    ModelReportRequestPayload,
    ModelTrendsCompletedPayload,
    ModelTrendsFailedPayload,
    ModelTrendsRequestPayload,
    PerformanceEventHelpers,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class PerformanceHandler(BaseResponsePublisher):
    """
    Handle performance optimization request events and publish results.

    Event Flow:
        1. Consume PERFORMANCE_{OPERATION}_REQUESTED event
        2. Extract payload and perform operation
        3. Publish _COMPLETED (success) or _FAILED (error)

    Topics:
        Baseline:
        - Request: dev.archon-intelligence.performance.baseline-requested.v1
        - Completed: dev.archon-intelligence.performance.baseline-completed.v1
        - Failed: dev.archon-intelligence.performance.baseline-failed.v1

        Opportunities:
        - Request: dev.archon-intelligence.performance.opportunities-requested.v1
        - Completed: dev.archon-intelligence.performance.opportunities-completed.v1
        - Failed: dev.archon-intelligence.performance.opportunities-failed.v1

        Optimize:
        - Request: dev.archon-intelligence.performance.optimize-requested.v1
        - Completed: dev.archon-intelligence.performance.optimize-completed.v1
        - Failed: dev.archon-intelligence.performance.optimize-failed.v1

        Report:
        - Request: dev.archon-intelligence.performance.report-requested.v1
        - Completed: dev.archon-intelligence.performance.report-completed.v1
        - Failed: dev.archon-intelligence.performance.report-failed.v1

        Trends:
        - Request: dev.archon-intelligence.performance.trends-requested.v1
        - Completed: dev.archon-intelligence.performance.trends-completed.v1
        - Failed: dev.archon-intelligence.performance.trends-failed.v1
    """

    # Service endpoints
    INTELLIGENCE_SERVICE_URL = "http://localhost:8053"

    def __init__(self, intelligence_url: Optional[str] = None):
        """Initialize Performance handler.

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
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if event type is a performance request
        """
        try:
            EnumPerformanceEventType(event_type)
            return "REQUESTED" in event_type
        except ValueError:
            return any(
                keyword in event_type.lower()
                for keyword in [
                    "baseline_requested",
                    "opportunities_requested",
                    "optimize_requested",
                    "report_requested",
                    "trends_requested",
                    "baseline-requested",
                    "opportunities-requested",
                    "optimize-requested",
                    "report-requested",
                    "trends-requested",
                ]
            )

    async def handle_event(self, event: Any) -> bool:
        """
        Handle performance optimization request event.

        Routes to appropriate handler based on event type.

        Args:
            event: Event envelope with performance payload

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
            if "baseline" in event_type_str.lower():
                return await self._handle_baseline(correlation_id, payload, start_time)
            elif "opportunities" in event_type_str.lower():
                return await self._handle_opportunities(
                    correlation_id, payload, start_time
                )
            elif "optimize" in event_type_str.lower():
                return await self._handle_optimize(correlation_id, payload, start_time)
            elif "report" in event_type_str.lower():
                return await self._handle_report(correlation_id, payload, start_time)
            elif "trends" in event_type_str.lower():
                return await self._handle_trends(correlation_id, payload, start_time)
            else:
                logger.error(f"Unknown performance operation type: {event_type_str}")
                return False

        except Exception as e:
            logger.error(
                f"Performance handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_baseline(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle BASELINE_REQUESTED event."""
        try:
            request = ModelBaselineRequestPayload(**payload)
            logger.info(
                f"Processing BASELINE_REQUESTED | correlation_id={correlation_id} | "
                f"operation_name={request.operation_name}"
            )

            # Ensure HTTP client is initialized
            await self._ensure_http_client()

            # Make HTTP request to intelligence service
            url = f"{self.intelligence_url}/performance/baseline"
            request_payload = {
                "operation_name": request.operation_name,
                "metrics": request.metrics if hasattr(request, "metrics") else {},
                "code_content": (
                    request.code_content if hasattr(request, "code_content") else None
                ),
            }

            response = await self.http_client.post(url, json=request_payload)
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_baseline_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("baseline")
            return True

        except Exception as e:
            logger.error(f"Baseline operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_baseline_failed(
                correlation_id,
                payload.get("operation_name", "unknown"),
                str(e),
                EnumPerformanceErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_opportunities(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle OPPORTUNITIES_REQUESTED event."""
        try:
            request = ModelOpportunitiesRequestPayload(**payload)
            logger.info(
                f"Processing OPPORTUNITIES_REQUESTED | correlation_id={correlation_id} | "
                f"operation_name={request.operation_name}"
            )

            # Ensure HTTP client is initialized
            await self._ensure_http_client()

            # Make HTTP request to intelligence service
            url = f"{self.intelligence_url}/performance/opportunities/{request.operation_name}"

            response = await self.http_client.get(url)
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_opportunities_completed(
                correlation_id, result, duration_ms
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("opportunities")
            return True

        except Exception as e:
            logger.error(f"Opportunities operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_opportunities_failed(
                correlation_id,
                payload.get("operation_name", "unknown"),
                str(e),
                EnumPerformanceErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_optimize(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle OPTIMIZE_REQUESTED event."""
        try:
            request = ModelOptimizeRequestPayload(**payload)
            logger.info(
                f"Processing OPTIMIZE_REQUESTED | correlation_id={correlation_id} | "
                f"operation_name={request.operation_name} | category={request.category}"
            )

            # Ensure HTTP client is initialized
            await self._ensure_http_client()

            # Make HTTP request to intelligence service
            url = f"{self.intelligence_url}/performance/optimize"
            request_payload = {
                "operation_name": request.operation_name,
                "category": (
                    request.category if hasattr(request, "category") else "general"
                ),
                "test_duration_minutes": (
                    request.test_duration_minutes
                    if hasattr(request, "test_duration_minutes")
                    else 5
                ),
            }

            response = await self.http_client.post(url, json=request_payload)
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_optimize_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("optimize")
            return True

        except Exception as e:
            logger.error(f"Optimize operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_optimize_failed(
                correlation_id,
                payload.get("operation_name", "unknown"),
                payload.get("category", "unknown"),
                str(e),
                EnumPerformanceErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_report(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle REPORT_REQUESTED event."""
        try:
            request = ModelReportRequestPayload(**payload)
            logger.info(
                f"Processing REPORT_REQUESTED | correlation_id={correlation_id} | "
                f"time_window_hours={request.time_window_hours}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            params = {}
            if request.time_window_hours:
                params["time_window_hours"] = request.time_window_hours
            if request.operation_name:
                params["operation"] = request.operation_name

            response = await self.http_client.get(
                f"{self.intelligence_url}/performance/report",
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_report_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("report")

            logger.info(
                f"REPORT_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_report_failed(
                correlation_id,
                f"Service error: {e.response.status_code}",
                EnumPerformanceErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Report operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_report_failed(
                correlation_id,
                str(e),
                EnumPerformanceErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_trends(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle TRENDS_REQUESTED event."""
        try:
            request = ModelTrendsRequestPayload(**payload)
            logger.info(
                f"Processing TRENDS_REQUESTED | correlation_id={correlation_id} | "
                f"time_window_hours={request.time_window_hours}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            params = {}
            if request.time_window_hours:
                params["timeframe"] = request.time_window_hours
            if request.operation_name:
                params["operation"] = request.operation_name

            response = await self.http_client.get(
                f"{self.intelligence_url}/performance/trends",
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_trends_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("trends")

            logger.info(
                f"TRENDS_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_trends_failed(
                correlation_id,
                f"Service error: {e.response.status_code}",
                EnumPerformanceErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(f"Trends operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_trends_failed(
                correlation_id,
                str(e),
                EnumPerformanceErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    # ========================================================================
    # Publish Helper Methods
    # ========================================================================

    async def _publish_baseline_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish BASELINE_COMPLETED event."""
        await self._ensure_router_initialized()

        payload = ModelBaselineCompletedPayload(
            operation_name=result["operation_name"],
            average_response_time_ms=result["average_response_time_ms"],
            p50_ms=result["p50_ms"],
            p95_ms=result["p95_ms"],
            p99_ms=result["p99_ms"],
            std_dev_ms=result.get("std_dev_ms"),
            sample_size=result["sample_size"],
            quality_score=result.get("quality_score"),
            complexity_score=result.get("complexity_score"),
            source=result["source"],
            processing_time_ms=processing_time_ms,
            cache_hit=False,
        )

        event_envelope = PerformanceEventHelpers.create_event_envelope(
            event_type="baseline_completed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PerformanceEventHelpers.get_kafka_topic(
            EnumPerformanceEventType.BASELINE_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(f"Published BASELINE_COMPLETED | correlation_id={correlation_id}")

    async def _publish_baseline_failed(
        self,
        correlation_id: UUID,
        operation_name: str,
        error_message: str,
        error_code: EnumPerformanceErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish BASELINE_FAILED event."""
        await self._ensure_router_initialized()

        payload = ModelBaselineFailedPayload(
            operation_name=operation_name,
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
            error_details={},
        )

        event_envelope = PerformanceEventHelpers.create_event_envelope(
            event_type="baseline_failed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PerformanceEventHelpers.get_kafka_topic(
            EnumPerformanceEventType.BASELINE_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(f"Published BASELINE_FAILED | correlation_id={correlation_id}")

    async def _publish_opportunities_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish OPPORTUNITIES_COMPLETED event."""
        await self._ensure_router_initialized()

        payload = ModelOpportunitiesCompletedPayload(
            operation_name=result["operation_name"],
            opportunities_count=result["opportunities_count"],
            total_potential_improvement_percent=result[
                "total_potential_improvement_percent"
            ],
            categories=result["categories"],
            processing_time_ms=processing_time_ms,
            cache_hit=False,
        )

        event_envelope = PerformanceEventHelpers.create_event_envelope(
            event_type="opportunities_completed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PerformanceEventHelpers.get_kafka_topic(
            EnumPerformanceEventType.OPPORTUNITIES_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published OPPORTUNITIES_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_opportunities_failed(
        self,
        correlation_id: UUID,
        operation_name: str,
        error_message: str,
        error_code: EnumPerformanceErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish OPPORTUNITIES_FAILED event."""
        await self._ensure_router_initialized()

        payload = ModelOpportunitiesFailedPayload(
            operation_name=operation_name,
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
            error_details={},
        )

        event_envelope = PerformanceEventHelpers.create_event_envelope(
            event_type="opportunities_failed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PerformanceEventHelpers.get_kafka_topic(
            EnumPerformanceEventType.OPPORTUNITIES_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published OPPORTUNITIES_FAILED | correlation_id={correlation_id}"
        )

    async def _publish_optimize_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish OPTIMIZE_COMPLETED event."""
        await self._ensure_router_initialized()

        payload = ModelOptimizeCompletedPayload(
            operation_name=result["operation_name"],
            category=result["category"],
            improvement_percent=result["improvement_percent"],
            baseline_ms=result["baseline_ms"],
            optimized_ms=result["optimized_ms"],
            test_duration_minutes=result["test_duration_minutes"],
            processing_time_ms=processing_time_ms,
            success=result["success"],
        )

        event_envelope = PerformanceEventHelpers.create_event_envelope(
            event_type="optimize_completed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PerformanceEventHelpers.get_kafka_topic(
            EnumPerformanceEventType.OPTIMIZE_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(f"Published OPTIMIZE_COMPLETED | correlation_id={correlation_id}")

    async def _publish_optimize_failed(
        self,
        correlation_id: UUID,
        operation_name: str,
        category: str,
        error_message: str,
        error_code: EnumPerformanceErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish OPTIMIZE_FAILED event."""
        await self._ensure_router_initialized()

        payload = ModelOptimizeFailedPayload(
            operation_name=operation_name,
            category=category,
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
            error_details={},
        )

        event_envelope = PerformanceEventHelpers.create_event_envelope(
            event_type="optimize_failed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PerformanceEventHelpers.get_kafka_topic(
            EnumPerformanceEventType.OPTIMIZE_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(f"Published OPTIMIZE_FAILED | correlation_id={correlation_id}")

    async def _publish_report_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish REPORT_COMPLETED event."""
        await self._ensure_router_initialized()

        payload = ModelReportCompletedPayload(
            operations_count=result["operations_count"],
            total_measurements=result["total_measurements"],
            time_window_hours=result["time_window_hours"],
            report_summary=result["report_summary"],
            processing_time_ms=processing_time_ms,
            cache_hit=False,
        )

        event_envelope = PerformanceEventHelpers.create_event_envelope(
            event_type="report_completed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PerformanceEventHelpers.get_kafka_topic(
            EnumPerformanceEventType.REPORT_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(f"Published REPORT_COMPLETED | correlation_id={correlation_id}")

    async def _publish_report_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumPerformanceErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish REPORT_FAILED event."""
        await self._ensure_router_initialized()

        payload = ModelReportFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
            error_details={},
        )

        event_envelope = PerformanceEventHelpers.create_event_envelope(
            event_type="report_failed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PerformanceEventHelpers.get_kafka_topic(
            EnumPerformanceEventType.REPORT_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(f"Published REPORT_FAILED | correlation_id={correlation_id}")

    async def _publish_trends_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        """Publish TRENDS_COMPLETED event."""
        await self._ensure_router_initialized()

        payload = ModelTrendsCompletedPayload(
            operations_count=result["operations_count"],
            trends_count=result["trends_count"],
            time_window_hours=result["time_window_hours"],
            trends_summary=result["trends_summary"],
            processing_time_ms=processing_time_ms,
            cache_hit=False,
        )

        event_envelope = PerformanceEventHelpers.create_event_envelope(
            event_type="trends_completed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PerformanceEventHelpers.get_kafka_topic(
            EnumPerformanceEventType.TRENDS_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(f"Published TRENDS_COMPLETED | correlation_id={correlation_id}")

    async def _publish_trends_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumPerformanceErrorCode,
        processing_time_ms: float,
    ) -> None:
        """Publish TRENDS_FAILED event."""
        await self._ensure_router_initialized()

        payload = ModelTrendsFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
            error_details={},
        )

        event_envelope = PerformanceEventHelpers.create_event_envelope(
            event_type="trends_failed",
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PerformanceEventHelpers.get_kafka_topic(
            EnumPerformanceEventType.TRENDS_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(f"Published TRENDS_FAILED | correlation_id={correlation_id}")

    def _increment_operation_metric(self, operation: str) -> None:
        """Increment operation-specific metric."""
        if operation not in self.metrics["operations_by_type"]:
            self.metrics["operations_by_type"][operation] = 0
        self.metrics["operations_by_type"][operation] += 1

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "PerformanceHandler"

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
