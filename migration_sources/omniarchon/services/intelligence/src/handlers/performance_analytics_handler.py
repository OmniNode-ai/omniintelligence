"""Performance Analytics Event Handler - Event-driven performance analytics tracking (6 operations)"""

import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from src.events.models.performance_analytics_events import *
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class PerformanceAnalyticsHandler(BaseResponsePublisher):
    """Handle performance analytics request events and publish results."""

    # Service endpoint
    INTELLIGENCE_URL = "http://localhost:8053"

    # Timeouts (in seconds)
    TRENDS_TIMEOUT = 10.0
    HEALTH_TIMEOUT = 5.0

    def __init__(self, intelligence_url: Optional[str] = None):
        super().__init__()
        self.intelligence_url = intelligence_url or self.INTELLIGENCE_URL
        self.http_client: Optional[httpx.AsyncClient] = None
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
        try:
            EnumPerformanceAnalyticsEventType(event_type)
            return "REQUESTED" in event_type
        except ValueError:
            return any(
                k in event_type.lower()
                for k in [
                    "baselines",
                    "metrics",
                    "optimization_opportunities",
                    "anomaly_check",
                    "trends",
                    "health",
                ]
            )

    async def handle_event(self, event: Any) -> bool:
        start_time = time.perf_counter()
        correlation_id = None
        try:
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)
            event_type_str = self._get_event_type(event)
            event_type_lower = event_type_str.lower()

            if "baselines" in event_type_lower:
                return await self._handle_baselines(correlation_id, payload, start_time)
            elif "metrics" in event_type_lower and "anomaly" not in event_type_lower:
                return await self._handle_metrics(correlation_id, payload, start_time)
            elif (
                "optimization_opportunities" in event_type_lower
                or "optimization-opportunities" in event_type_lower
            ):
                return await self._handle_opportunities(
                    correlation_id, payload, start_time
                )
            elif (
                "anomaly_check" in event_type_lower
                or "anomaly-check" in event_type_lower
            ):
                return await self._handle_anomaly_check(
                    correlation_id, payload, start_time
                )
            elif "trends" in event_type_lower:
                return await self._handle_trends(correlation_id, payload, start_time)
            elif "health" in event_type_lower:
                return await self._handle_health(correlation_id, payload, start_time)
            else:
                logger.error(
                    f"Unknown performance analytics operation: {event_type_str}"
                )
                return False
        except Exception as e:
            logger.error(
                f"Performance analytics handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_baselines(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            logger.info(f"Processing BASELINES_REQUESTED | cid={cid}")
            # HTTP call to intelligence service
            await self._ensure_http_client()
            response = await self.http_client.get(
                f"{self.intelligence_url}/api/performance-analytics/baselines"
            )
            response.raise_for_status()
            result = response.json()

            res = {
                "baselines": result.get("baselines", {}),
                "total_operations": result.get("total_operations", 0),
                "total_measurements": result.get("total_measurements", 0),
            }
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsBaselinesCompletedPayload(
                **res, processing_time_ms=dur
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "baselines_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.BASELINES_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("baselines")
            return True
        except Exception as e:
            logger.error(f"Baselines failed | cid={cid} | error={e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsBaselinesFailedPayload(
                error_message=str(e),
                error_code=EnumPerfAnalyticsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "baselines_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.BASELINES_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_metrics(self, cid: str, payload: dict, start_time: float) -> bool:
        try:
            req = ModelPerfAnalyticsMetricsRequestPayload(**payload)
            # HTTP call to intelligence service
            await self._ensure_http_client()
            response = await self.http_client.get(
                f"{self.intelligence_url}/api/performance-analytics/operations/{req.operation}/metrics"
            )
            response.raise_for_status()
            result = response.json()

            res = {
                "operation": result.get("operation", req.operation),
                "baseline": result.get("baseline", {}),
                "recent_measurements": result.get("recent_measurements", []),
                "trend": result.get("trend", "stable"),
                "anomaly_count_24h": result.get("anomaly_count_24h", 0),
            }
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsMetricsCompletedPayload(**res, processing_time_ms=dur)
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "metrics_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.METRICS_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("metrics")
            return True
        except Exception as e:
            logger.error(f"Metrics failed | cid={cid} | error={e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsMetricsFailedPayload(
                operation=payload.get("operation_name", "unknown"),
                error_message=str(e),
                error_code=EnumPerfAnalyticsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "metrics_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.METRICS_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_opportunities(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            logger.info(f"Processing OPPORTUNITIES_REQUESTED | cid={cid}")
            # HTTP call to intelligence service
            await self._ensure_http_client()
            response = await self.http_client.get(
                f"{self.intelligence_url}/api/performance-analytics/optimization-opportunities"
            )
            response.raise_for_status()
            result = response.json()

            res = {
                "opportunities": result.get("opportunities", []),
                "total_opportunities": result.get("total_opportunities", 0),
                "avg_roi": result.get("avg_roi", 0.0),
                "total_potential_improvement": result.get(
                    "total_potential_improvement", 0.0
                ),
            }
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsOpportunitiesCompletedPayload(
                **res, processing_time_ms=dur
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "opportunities_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.OPPORTUNITIES_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("opportunities")
            return True
        except Exception as e:
            logger.error(f"Opportunities failed | cid={cid} | error={e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsOpportunitiesFailedPayload(
                error_message=str(e),
                error_code=EnumPerfAnalyticsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "opportunities_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.OPPORTUNITIES_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_anomaly_check(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            req = ModelPerfAnalyticsAnomalyCheckRequestPayload(**payload)
            # HTTP call to intelligence service
            await self._ensure_http_client()
            response = await self.http_client.post(
                f"{self.intelligence_url}/api/performance-analytics/operations/{req.operation}/anomaly-check",
                json={"duration_ms": req.duration_ms},
            )
            response.raise_for_status()
            result = response.json()

            res = {
                "operation": req.operation,
                "anomaly_detected": result.get("anomaly_detected", False),
                "z_score": result.get("z_score", 0.0),
                "current_duration_ms": req.duration_ms,
                "baseline_mean": result.get("baseline_mean", 0.0),
                "baseline_p95": result.get("baseline_p95", 0.0),
                "deviation_percentage": result.get("deviation_percentage", 0.0),
                "severity": result.get("severity", "normal"),
            }
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsAnomalyCheckCompletedPayload(
                **res, processing_time_ms=dur
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "anomaly_check_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.ANOMALY_CHECK_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("anomaly_check")
            return True
        except Exception as e:
            logger.error(f"Anomaly check failed | cid={cid} | error={e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsAnomalyCheckFailedPayload(
                operation=payload.get(
                    "operation", payload.get("operation_name", "unknown")
                ),
                error_message=str(e),
                error_code=EnumPerfAnalyticsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "anomaly_check_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.ANOMALY_CHECK_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_trends(self, cid: str, payload: dict, start_time: float) -> bool:
        try:
            logger.info(f"Processing TRENDS_REQUESTED | cid={cid}")

            # Call Intelligence service
            await self._ensure_http_client()
            response = await self.http_client.get(
                f"{self.intelligence_url}/api/performance-analytics/trends",
                timeout=self.TRENDS_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()

            # Extract response data
            res = {
                "time_window": result.get("time_window", "24h"),
                "operations": result.get("operations", {}),
                "overall_health": result.get("overall_health", "unknown"),
            }

            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsTrendsCompletedPayload(**res, processing_time_ms=dur)
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "trends_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                topic=PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.TRENDS_COMPLETED
                ),
                event=e,
                key=str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("trends")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsTrendsFailedPayload(
                error_message=f"Service error: {e.response.status_code}",
                error_code=EnumPerfAnalyticsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "trends_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                topic=PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.TRENDS_FAILED
                ),
                event=e,
                key=str(cid),
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Trends analysis failed: {e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsTrendsFailedPayload(
                error_message=str(e),
                error_code=EnumPerfAnalyticsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "trends_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                topic=PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.TRENDS_FAILED
                ),
                event=e,
                key=str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_health(self, cid: str, payload: dict, start_time: float) -> bool:
        try:
            logger.info(f"Processing HEALTH_REQUESTED | cid={cid}")

            # Call Intelligence service
            await self._ensure_http_client()
            response = await self.http_client.get(
                f"{self.intelligence_url}/api/performance-analytics/health",
                timeout=self.HEALTH_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()

            # Extract response data
            res = {
                "status": result.get("status", "unknown"),
                "baseline_service": result.get("baseline_service", "unknown"),
                "optimization_analyzer": result.get("optimization_analyzer", "unknown"),
                "total_operations_tracked": result.get("total_operations_tracked", 0),
                "total_measurements": result.get("total_measurements", 0),
                "uptime_seconds": result.get("uptime_seconds", 0),
            }

            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsHealthCompletedPayload(**res, processing_time_ms=dur)
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "health_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                topic=PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.HEALTH_COMPLETED
                ),
                event=e,
                key=str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("health")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsHealthFailedPayload(
                error_message=f"Service error: {e.response.status_code}",
                error_code=EnumPerfAnalyticsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "health_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                topic=PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.HEALTH_FAILED
                ),
                event=e,
                key=str(cid),
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelPerfAnalyticsHealthFailedPayload(
                error_message=str(e),
                error_code=EnumPerfAnalyticsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = PerformanceAnalyticsEventHelpers.create_event_envelope(
                "health_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                topic=PerformanceAnalyticsEventHelpers.get_kafka_topic(
                    EnumPerformanceAnalyticsEventType.HEALTH_FAILED
                ),
                event=e,
                key=str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    def _increment_operation_metric(self, op: str) -> None:
        if op not in self.metrics["operations_by_type"]:
            self.metrics["operations_by_type"][op] = 0
        self.metrics["operations_by_type"][op] += 1

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
        return "PerformanceAnalyticsHandler"

    def get_metrics(self) -> Dict[str, Any]:
        total = self.metrics["events_handled"] + self.metrics["events_failed"]
        return {
            **self.metrics,
            "success_rate": (
                self.metrics["events_handled"] / total if total > 0 else 1.0
            ),
            "avg_processing_time_ms": (
                self.metrics["total_processing_time_ms"]
                / self.metrics["events_handled"]
                if self.metrics["events_handled"] > 0
                else 0.0
            ),
            "handler_name": self.get_handler_name(),
        }

    async def shutdown(self) -> None:
        """Shutdown handler and cleanup resources."""
        await self._close_http_client()
        await self._shutdown_publisher()
        logger.info("Performance analytics handler shutdown complete")
