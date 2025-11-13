"""
Pattern Traceability Event Handler

Handles pattern traceability operation events and publishes COMPLETED/FAILED responses.
Implements event-driven interface for pattern lineage tracking, analytics, and feedback.

Created: 2025-10-22
Purpose: Event-driven pattern traceability operations integration
"""

import logging
import os
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from src.events.models.pattern_traceability_events import (
    EnumTraceabilityErrorCode,
    ModelAnalyticsCompletedPayload,
    ModelAnalyticsComputeCompletedPayload,
    ModelAnalyticsComputeFailedPayload,
    ModelAnalyticsComputeRequestPayload,
    ModelAnalyticsFailedPayload,
    ModelAnalyticsRequestPayload,
    ModelEvolutionCompletedPayload,
    ModelEvolutionFailedPayload,
    ModelEvolutionRequestPayload,
    ModelExecutionLogsCompletedPayload,
    ModelExecutionLogsFailedPayload,
    ModelExecutionLogsRequestPayload,
    ModelExecutionSummaryCompletedPayload,
    ModelExecutionSummaryFailedPayload,
    ModelExecutionSummaryRequestPayload,
    ModelFeedbackAnalyzeCompletedPayload,
    ModelFeedbackAnalyzeFailedPayload,
    ModelFeedbackAnalyzeRequestPayload,
    ModelFeedbackApplyCompletedPayload,
    ModelFeedbackApplyFailedPayload,
    ModelFeedbackApplyRequestPayload,
    ModelHealthCompletedPayload,
    ModelHealthFailedPayload,
    ModelHealthRequestPayload,
    ModelLineageCompletedPayload,
    ModelLineageFailedPayload,
    ModelLineageRequestPayload,
    ModelTrackBatchCompletedPayload,
    ModelTrackBatchFailedPayload,
    ModelTrackBatchRequestPayload,
    ModelTrackCompletedPayload,
    ModelTrackFailedPayload,
    ModelTrackRequestPayload,
    TraceabilityEventHelpers,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class PatternTraceabilityHandler(BaseResponsePublisher):
    """
    Handle pattern traceability operation events and publish results.

    Supported Operations:
        - TRACK: Track single pattern lineage
        - TRACK_BATCH: Track multiple patterns
        - LINEAGE: Get pattern lineage chain
        - EVOLUTION: Get pattern evolution history
        - EXECUTION_LOGS: Get execution logs
        - EXECUTION_SUMMARY: Get execution summary
        - ANALYTICS: Get pattern analytics
        - ANALYTICS_COMPUTE: Compute analytics
        - FEEDBACK_ANALYZE: Analyze feedback
        - FEEDBACK_APPLY: Apply feedback
        - HEALTH: Health check
    """

    def __init__(self):
        """Initialize Pattern Traceability handler."""
        super().__init__()
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "operations_by_type": {},
        }
        # HTTP client for Intelligence Service API
        self.intelligence_base_url = os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://localhost:8053"
        )
        self.http_client = httpx.AsyncClient(
            base_url=self.intelligence_base_url,
            timeout=httpx.Timeout(30.0, connect=10.0, read=30.0, write=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

    def can_handle(self, event_type: str) -> bool:
        """Check if this handler can process the given event type."""
        return any(
            keyword in event_type.lower()
            for keyword in [
                "track_requested",
                "track_batch_requested",
                "lineage_requested",
                "evolution_requested",
                "execution_logs_requested",
                "execution_summary_requested",
                "analytics_requested",
                "analytics_compute_requested",
                "feedback_analyze_requested",
                "feedback_apply_requested",
                "health_requested",
                "traceability",
            ]
        )

    async def handle_event(self, event: Any) -> bool:
        """Handle traceability operation events."""
        start_time = time.perf_counter()
        correlation_id = None

        try:
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)
            # Handle both dict and object events
            if isinstance(event, dict):
                event_type_str = event.get("event_type", "")
            else:
                # First try direct attribute (for test mocks), then metadata (for omnibase_core)
                event_type_str = getattr(event, "event_type", "")
                if not event_type_str:
                    metadata = getattr(event, "metadata", {})
                    if isinstance(metadata, dict):
                        event_type_str = metadata.get("event_type", "")

            # Route to appropriate operation handler
            if "track_batch" in event_type_str.lower():
                return await self._handle_track_batch(
                    correlation_id, payload, start_time
                )
            elif "track" in event_type_str.lower():
                return await self._handle_track(correlation_id, payload, start_time)
            elif "lineage" in event_type_str.lower():
                return await self._handle_lineage(correlation_id, payload, start_time)
            elif "evolution" in event_type_str.lower():
                return await self._handle_evolution(correlation_id, payload, start_time)
            elif "execution_logs" in event_type_str.lower():
                return await self._handle_execution_logs(
                    correlation_id, payload, start_time
                )
            elif "execution_summary" in event_type_str.lower():
                return await self._handle_execution_summary(
                    correlation_id, payload, start_time
                )
            elif "analytics_compute" in event_type_str.lower():
                return await self._handle_analytics_compute(
                    correlation_id, payload, start_time
                )
            elif "analytics" in event_type_str.lower():
                return await self._handle_analytics(correlation_id, payload, start_time)
            elif "feedback_analyze" in event_type_str.lower():
                return await self._handle_feedback_analyze(
                    correlation_id, payload, start_time
                )
            elif "feedback_apply" in event_type_str.lower():
                return await self._handle_feedback_apply(
                    correlation_id, payload, start_time
                )
            elif "health" in event_type_str.lower():
                return await self._handle_health(correlation_id, payload, start_time)
            else:
                logger.error(f"Unknown traceability operation type: {event_type_str}")
                return False

        except Exception as e:
            logger.error(
                f"Traceability handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_track(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle TRACK operation."""
        try:
            request = ModelTrackRequestPayload(**payload)
            logger.info(
                f"Processing TRACK | correlation_id={correlation_id} | pattern_id={request.pattern_id}"
            )

            # HTTP call: POST /api/pattern-traceability/lineage/track
            request_data = {
                "pattern_id": request.pattern_id,
                "source": "event_handler",  # Default source (model doesn't have source field)
                "metadata": request.metadata or {},
            }

            response = await self.http_client.post(
                "/api/pattern-traceability/lineage/track", json=request_data
            )
            response.raise_for_status()
            api_result = response.json()

            result = {
                "pattern_id": request.pattern_id,
                "tracked": api_result.get("tracked", True),
                "lineage_id": api_result.get("lineage_id", ""),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "track",
                correlation_id,
                ModelTrackCompletedPayload(**result, processing_time_ms=duration_ms),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("track")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Track HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "track",
                correlation_id,
                ModelTrackFailedPayload(
                    pattern_id=payload.get("pattern_id", "unknown"),
                    error_message=f"HTTP {e.response.status_code}: {e.response.text}",
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Track operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "track",
                correlation_id,
                ModelTrackFailedPayload(
                    pattern_id=payload.get("pattern_id", "unknown"),
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_track_batch(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle TRACK_BATCH operation."""
        try:
            request = ModelTrackBatchRequestPayload(**payload)
            logger.info(
                f"Processing TRACK_BATCH | correlation_id={correlation_id} | patterns={len(request.patterns)}"
            )

            # HTTP call: POST /api/pattern-traceability/lineage/track/batch
            request_data = {"patterns": request.patterns}

            response = await self.http_client.post(
                "/api/pattern-traceability/lineage/track/batch", json=request_data
            )
            response.raise_for_status()
            api_result = response.json()

            result = {
                "total_patterns": len(request.patterns),
                "tracked_count": api_result.get("tracked_count", 0),
                "failed_count": api_result.get("failed_count", 0),
                "lineage_ids": api_result.get("lineage_ids", []),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "track_batch",
                correlation_id,
                ModelTrackBatchCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("track_batch")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Track batch HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "track_batch",
                correlation_id,
                ModelTrackBatchFailedPayload(
                    total_patterns=len(payload.get("patterns", [])),
                    error_message=f"HTTP {e.response.status_code}: {e.response.text}",
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Track batch operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "track_batch",
                correlation_id,
                ModelTrackBatchFailedPayload(
                    total_patterns=len(payload.get("patterns", [])),
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_lineage(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle LINEAGE operation."""
        try:
            request = ModelLineageRequestPayload(**payload)
            logger.info(
                f"Processing LINEAGE | correlation_id={correlation_id} | pattern_id={request.pattern_id}"
            )

            # HTTP call: GET /api/pattern-traceability/lineage/{pattern_id}
            response = await self.http_client.get(
                f"/api/pattern-traceability/lineage/{request.pattern_id}"
            )
            response.raise_for_status()
            api_result = response.json()

            result = {
                "pattern_id": request.pattern_id,
                "lineage_chain": api_result.get("lineage_chain", []),
                "depth": api_result.get("depth", 0),
                "total_ancestors": api_result.get("total_ancestors", 0),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "lineage",
                correlation_id,
                ModelLineageCompletedPayload(**result, processing_time_ms=duration_ms),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("lineage")
            return True

        except Exception as e:
            logger.error(f"Lineage operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "lineage",
                correlation_id,
                ModelLineageFailedPayload(
                    pattern_id=payload.get("pattern_id", "unknown"),
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.PATTERN_NOT_FOUND,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_evolution(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle EVOLUTION operation."""
        try:
            request = ModelEvolutionRequestPayload(**payload)
            logger.info(
                f"Processing EVOLUTION | correlation_id={correlation_id} | pattern_id={request.pattern_id}"
            )

            # HTTP call: GET /api/pattern-traceability/lineage/{pattern_id}/evolution
            response = await self.http_client.get(
                f"/api/pattern-traceability/lineage/{request.pattern_id}/evolution"
            )
            response.raise_for_status()
            api_result = response.json()

            result = {
                "pattern_id": request.pattern_id,
                "evolution_stages": api_result.get("evolution_stages", []),
                "total_versions": api_result.get("total_versions", 0),
                "time_span_hours": api_result.get("time_span_hours", 0.0),
                "metrics": api_result.get("metrics", {}),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "evolution",
                correlation_id,
                ModelEvolutionCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("evolution")
            return True

        except Exception as e:
            logger.error(f"Evolution operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "evolution",
                correlation_id,
                ModelEvolutionFailedPayload(
                    pattern_id=payload.get("pattern_id", "unknown"),
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_execution_logs(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle EXECUTION_LOGS operation."""
        try:
            request = ModelExecutionLogsRequestPayload(**payload)
            logger.info(f"Processing EXECUTION_LOGS | correlation_id={correlation_id}")

            # HTTP call: GET /api/pattern-traceability/executions/logs
            params = {}
            if hasattr(request, "limit") and request.limit:
                params["limit"] = request.limit
            if hasattr(request, "time_window_hours") and request.time_window_hours:
                params["time_window_hours"] = request.time_window_hours

            response = await self.http_client.get(
                "/api/pattern-traceability/executions/logs", params=params
            )
            response.raise_for_status()
            api_result = response.json()

            result = {
                "logs": api_result.get("logs", []),
                "total_count": api_result.get("total_count", 0),
                "time_window_hours": (
                    request.time_window_hours
                    if hasattr(request, "time_window_hours")
                    else 24
                ),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "execution_logs",
                correlation_id,
                ModelExecutionLogsCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("execution_logs")
            return True

        except Exception as e:
            logger.error(f"Execution logs operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "execution_logs",
                correlation_id,
                ModelExecutionLogsFailedPayload(
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_execution_summary(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle EXECUTION_SUMMARY operation."""
        try:
            request = ModelExecutionSummaryRequestPayload(**payload)
            logger.info(
                f"Processing EXECUTION_SUMMARY | correlation_id={correlation_id}"
            )

            # HTTP call: GET /api/pattern-traceability/executions/summary
            response = await self.http_client.get(
                "/api/pattern-traceability/executions/summary"
            )
            response.raise_for_status()
            api_result = response.json()

            result = {
                "total_executions": api_result.get("total_executions", 0),
                "success_count": api_result.get("success_count", 0),
                "failure_count": api_result.get("failure_count", 0),
                "average_duration_ms": api_result.get("average_duration_ms", 0.0),
                "breakdown": api_result.get("breakdown", {}),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "execution_summary",
                correlation_id,
                ModelExecutionSummaryCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("execution_summary")
            return True

        except Exception as e:
            logger.error(f"Execution summary operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "execution_summary",
                correlation_id,
                ModelExecutionSummaryFailedPayload(
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_analytics(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle ANALYTICS operation."""
        try:
            request = ModelAnalyticsRequestPayload(**payload)
            logger.info(
                f"Processing ANALYTICS | correlation_id={correlation_id} | pattern_id={request.pattern_id}"
            )

            # HTTP call: GET /api/pattern-traceability/analytics/{pattern_id}
            response = await self.http_client.get(
                f"/api/pattern-traceability/analytics/{request.pattern_id}"
            )
            response.raise_for_status()
            api_result = response.json()

            result = {
                "pattern_id": request.pattern_id,
                "analytics": api_result.get("analytics", {}),
                "usage_count": api_result.get("usage_count", 0),
                "success_rate": api_result.get("success_rate", 0.0),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "analytics",
                correlation_id,
                ModelAnalyticsCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("analytics")
            return True

        except Exception as e:
            logger.error(f"Analytics operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "analytics",
                correlation_id,
                ModelAnalyticsFailedPayload(
                    pattern_id=payload.get("pattern_id", "unknown"),
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_analytics_compute(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle ANALYTICS_COMPUTE operation."""
        try:
            request = ModelAnalyticsComputeRequestPayload(**payload)
            logger.info(
                f"Processing ANALYTICS_COMPUTE | correlation_id={correlation_id} | field={request.correlation_field}"
            )

            # HTTP call: POST /api/pattern-traceability/analytics/compute
            request_body = {"correlation_field": request.correlation_field}
            response = await self.http_client.post(
                "/api/pattern-traceability/analytics/compute", json=request_body
            )
            response.raise_for_status()
            api_result = response.json()

            result = {
                "correlation_field": request.correlation_field,
                "results": api_result.get("results", {}),
                "total_records": api_result.get("total_records", 0),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "analytics_compute",
                correlation_id,
                ModelAnalyticsComputeCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("analytics_compute")
            return True

        except Exception as e:
            logger.error(f"Analytics compute operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "analytics_compute",
                correlation_id,
                ModelAnalyticsComputeFailedPayload(
                    correlation_field=payload.get("correlation_field", "unknown"),
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_feedback_analyze(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FEEDBACK_ANALYZE operation."""
        try:
            request = ModelFeedbackAnalyzeRequestPayload(**payload)
            logger.info(
                f"Processing FEEDBACK_ANALYZE | correlation_id={correlation_id} | pattern_id={request.pattern_id}"
            )

            # HTTP call: POST /api/pattern-traceability/feedback/analyze
            request_body = {
                "pattern_id": request.pattern_id,
                "feedback_data": payload.get("feedback_data", {}),
            }
            response = await self.http_client.post(
                "/api/pattern-traceability/feedback/analyze", json=request_body
            )
            response.raise_for_status()
            api_result = response.json()

            result = {
                "pattern_id": request.pattern_id,
                "analysis_results": api_result.get("analysis_results", {}),
                "recommendations": api_result.get("recommendations", []),
                "confidence": api_result.get("confidence", 0.8),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "feedback_analyze",
                correlation_id,
                ModelFeedbackAnalyzeCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("feedback_analyze")
            return True

        except Exception as e:
            logger.error(f"Feedback analyze operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "feedback_analyze",
                correlation_id,
                ModelFeedbackAnalyzeFailedPayload(
                    pattern_id=payload.get("pattern_id", "unknown"),
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_feedback_apply(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle FEEDBACK_APPLY operation."""
        try:
            request = ModelFeedbackApplyRequestPayload(**payload)
            logger.info(
                f"Processing FEEDBACK_APPLY | correlation_id={correlation_id} | pattern_id={request.pattern_id}"
            )

            # HTTP call: POST /api/pattern-traceability/feedback/apply
            request_body = {
                "pattern_id": request.pattern_id,
                "improvements": payload.get("improvements", []),
            }
            response = await self.http_client.post(
                "/api/pattern-traceability/feedback/apply", json=request_body
            )
            response.raise_for_status()
            api_result = response.json()

            result = {
                "pattern_id": request.pattern_id,
                "applied": api_result.get("applied", True),
                "changes": api_result.get("changes", {}),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "feedback_apply",
                correlation_id,
                ModelFeedbackApplyCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("feedback_apply")
            return True

        except Exception as e:
            logger.error(f"Feedback apply operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "feedback_apply",
                correlation_id,
                ModelFeedbackApplyFailedPayload(
                    pattern_id=payload.get("pattern_id", "unknown"),
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_health(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle HEALTH operation."""
        try:
            request = ModelHealthRequestPayload(**payload)
            logger.info(f"Processing HEALTH | correlation_id={correlation_id}")

            # HTTP call: GET /api/pattern-traceability/health
            response = await self.http_client.get("/api/pattern-traceability/health")
            response.raise_for_status()
            api_result = response.json()

            result = {
                "status": api_result.get("status", "healthy"),
                "checks": api_result.get("checks", {}),
                "uptime_seconds": api_result.get("uptime_seconds", 0.0),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "health",
                correlation_id,
                ModelHealthCompletedPayload(**result, processing_time_ms=duration_ms),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("health")
            return True

        except Exception as e:
            logger.error(f"Health operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "health",
                correlation_id,
                ModelHealthFailedPayload(
                    error_message=str(e),
                    error_code=EnumTraceabilityErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    # ========================================================================
    # Publish Helper Methods
    # ========================================================================

    async def _publish_completed(
        self,
        operation: str,
        correlation_id: UUID,
        payload: Any,
        processing_time_ms: float,
    ) -> None:
        """Generic publish completed event."""
        await self._ensure_router_initialized()

        event_type = f"{operation.replace('_', '_')}_completed"
        event_envelope = TraceabilityEventHelpers.create_event_envelope(
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = TraceabilityEventHelpers.get_kafka_topic(event_type)
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published TRACEABILITY_{operation.upper()}_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_failed(
        self,
        operation: str,
        correlation_id: UUID,
        payload: Any,
        processing_time_ms: float,
    ) -> None:
        """Generic publish failed event."""
        await self._ensure_router_initialized()

        event_type = f"{operation.replace('_', '_')}_failed"
        event_envelope = TraceabilityEventHelpers.create_event_envelope(
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = TraceabilityEventHelpers.get_kafka_topic(event_type)
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published TRACEABILITY_{operation.upper()}_FAILED | correlation_id={correlation_id}"
        )

    def _increment_operation_metric(self, operation: str) -> None:
        """Increment operation-specific metric."""
        if operation not in self.metrics["operations_by_type"]:
            self.metrics["operations_by_type"][operation] = 0
        self.metrics["operations_by_type"][operation] += 1

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "PatternTraceabilityHandler"

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
