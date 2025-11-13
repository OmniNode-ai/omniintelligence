"""Quality Trends Event Handler - Event-driven quality trends tracking (7 operations)"""

import logging
import os
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from src.events.models.quality_trends_events import *
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)

# Intelligence Service endpoint
INTELLIGENCE_SERVICE_URL = os.getenv(
    "INTELLIGENCE_SERVICE_URL", "http://localhost:8053"  # Fallback for local dev only
)
HTTP_TIMEOUT = 30.0  # 30 second timeout


class QualityTrendsHandler(BaseResponsePublisher):
    """Handle quality trends request events and publish results."""

    def __init__(self):
        super().__init__()
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "operations_by_type": {},
        }

    def can_handle(self, event_type: str) -> bool:
        try:
            EnumQualityTrendsEventType(event_type)
            return "REQUESTED" in event_type
        except ValueError:
            return any(
                k in event_type.lower()
                for k in [
                    "snapshot",
                    "project_trend",
                    "file_trend",
                    "file_history",
                    "detect_regression",
                    "stats",
                    "clear",
                ]
            )

    async def handle_event(self, event: Any) -> bool:
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
            if (
                "snapshot" in event_type_str.lower()
                and "clear" not in event_type_str.lower()
            ):
                return await self._handle_snapshot(correlation_id, payload, start_time)
            elif (
                "project_trend" in event_type_str.lower()
                or "project-trend" in event_type_str.lower()
            ):
                return await self._handle_project_trend(
                    correlation_id, payload, start_time
                )
            elif (
                "file_trend" in event_type_str.lower()
                or "file-trend" in event_type_str.lower()
            ):
                return await self._handle_file_trend(
                    correlation_id, payload, start_time
                )
            elif (
                "file_history" in event_type_str.lower()
                or "file-history" in event_type_str.lower()
            ):
                return await self._handle_file_history(
                    correlation_id, payload, start_time
                )
            elif (
                "detect_regression" in event_type_str.lower()
                or "detect-regression" in event_type_str.lower()
            ):
                return await self._handle_detect_regression(
                    correlation_id, payload, start_time
                )
            elif "stats" in event_type_str.lower():
                return await self._handle_stats(correlation_id, payload, start_time)
            elif "clear" in event_type_str.lower():
                return await self._handle_clear(correlation_id, payload, start_time)
            else:
                logger.error(f"Unknown quality trends operation: {event_type_str}")
                return False
        except Exception as e:
            logger.error(
                f"Quality trends handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_snapshot(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            req = ModelQualityTrendsSnapshotRequestPayload(**payload)
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{INTELLIGENCE_SERVICE_URL}/api/quality-trends/snapshot",
                    json=payload,
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsSnapshotCompletedPayload(
                **res, processing_time_ms=dur
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "snapshot_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.SNAPSHOT_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("snapshot")
            return True
        except Exception as e:
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsSnapshotFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                file_path=payload.get("file_path", "unknown"),
                error_message=str(e),
                error_code=EnumQualityTrendsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "snapshot_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.SNAPSHOT_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_project_trend(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            req = ModelQualityTrendsProjectTrendRequestPayload(**payload)
            # HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(
                    f"{INTELLIGENCE_SERVICE_URL}/api/quality-trends/project/{req.project_id}/trend",
                    params=(
                        {"time_window_days": req.time_window_days}
                        if hasattr(req, "time_window_days")
                        else {}
                    ),
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsProjectTrendCompletedPayload(
                project_id=res["project_id"],
                trend=res["trend"],
                current_quality=res["current_quality"],
                avg_quality=res["avg_quality"],
                slope=res["slope"],
                snapshots_count=res["snapshots_count"],
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "project_trend_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.PROJECT_TREND_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("project_trend")
            return True
        except Exception as e:
            logger.error(f"Project trend failed | cid={cid} | error={e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsProjectTrendFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                error_message=str(e),
                error_code=EnumQualityTrendsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "project_trend_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.PROJECT_TREND_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_file_trend(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            req = ModelQualityTrendsFileTrendRequestPayload(**payload)
            # HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(
                    f"{INTELLIGENCE_SERVICE_URL}/api/quality-trends/project/{req.project_id}/file/{req.file_path}/trend",
                    params=(
                        {"time_window_days": req.time_window_days}
                        if hasattr(req, "time_window_days")
                        else {}
                    ),
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsFileTrendCompletedPayload(
                project_id=res["project_id"],
                file_path=res["file_path"],
                trend=res["trend"],
                current_quality=res["current_quality"],
                avg_quality=res["avg_quality"],
                slope=res["slope"],
                snapshots_count=res["snapshots_count"],
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "file_trend_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.FILE_TREND_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("file_trend")
            return True
        except Exception as e:
            logger.error(f"File trend failed | cid={cid} | error={e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsFileTrendFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                file_path=payload.get("file_path", "unknown"),
                error_message=str(e),
                error_code=EnumQualityTrendsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "file_trend_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.FILE_TREND_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_file_history(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            req = ModelQualityTrendsFileHistoryRequestPayload(**payload)
            # HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                params = {}
                if hasattr(req, "limit"):
                    params["limit"] = req.limit
                response = await client.get(
                    f"{INTELLIGENCE_SERVICE_URL}/api/quality-trends/project/{req.project_id}/file/{req.file_path}/history",
                    params=params,
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsFileHistoryCompletedPayload(
                project_id=res["project_id"],
                file_path=res["file_path"],
                history=res.get(
                    "history", []
                ),  # API returns "history" and model expects "history"
                snapshots_count=res["snapshots_count"],
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "file_history_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.FILE_HISTORY_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("file_history")
            return True
        except Exception as e:
            logger.error(f"File history failed | cid={cid} | error={e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsFileHistoryFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                file_path=payload.get("file_path", "unknown"),
                error_message=str(e),
                error_code=EnumQualityTrendsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "file_history_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.FILE_HISTORY_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_detect_regression(
        self, cid: str, payload: dict, start_time: float
    ) -> bool:
        try:
            req = ModelQualityTrendsDetectRegressionRequestPayload(**payload)
            # HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                request_data = {
                    "project_id": req.project_id,
                    "current_score": req.current_score,
                    "threshold": req.threshold,
                }
                if hasattr(req, "file_path") and req.file_path:
                    request_data["file_path"] = req.file_path
                response = await client.post(
                    f"{INTELLIGENCE_SERVICE_URL}/api/quality-trends/detect-regression",
                    json=request_data,
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsDetectRegressionCompletedPayload(
                project_id=res["project_id"],
                regression_detected=res.get("regression_detected", False),
                current_score=res["current_score"],
                avg_recent_score=res.get("avg_recent_score", 0.0),
                difference=res.get("difference", 0.0),
                threshold=req.threshold,  # Use threshold from request
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "detect_regression_completed",
                p,
                UUID(cid) if isinstance(cid, str) else cid,
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.DETECT_REGRESSION_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("detect_regression")
            return True
        except Exception as e:
            logger.error(
                f"Detect regression failed | cid={cid} | error={e}", exc_info=True
            )
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsDetectRegressionFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                file_path=payload.get("file_path", ""),
                error_message=str(e),
                error_code=EnumQualityTrendsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "detect_regression_failed",
                p,
                UUID(cid) if isinstance(cid, str) else cid,
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.DETECT_REGRESSION_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_stats(self, cid: str, payload: dict, start_time: float) -> bool:
        try:
            # HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(
                    f"{INTELLIGENCE_SERVICE_URL}/api/quality-trends/stats"
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsStatsCompletedPayload(
                total_snapshots=res["total_snapshots"],
                service_status=res.get("service_status", "active"),
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "stats_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.STATS_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("stats")
            return True
        except Exception as e:
            logger.error(f"Stats failed | cid={cid} | error={e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsStatsFailedPayload(
                error_message=str(e),
                error_code=EnumQualityTrendsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "stats_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.STATS_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_clear(self, cid: str, payload: dict, start_time: float) -> bool:
        try:
            req = ModelQualityTrendsClearRequestPayload(**payload)
            # HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.delete(
                    f"{INTELLIGENCE_SERVICE_URL}/api/quality-trends/project/{req.project_id}/snapshots"
                )
                response.raise_for_status()
                res = response.json()
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsClearCompletedPayload(
                project_id=res["project_id"],
                cleared_snapshots=res.get("cleared_snapshots", 0),
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "clear_completed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.CLEAR_COMPLETED
                ),
                e,
                str(cid),
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += dur
            self._increment_operation_metric("clear")
            return True
        except Exception as e:
            logger.error(f"Clear failed | cid={cid} | error={e}", exc_info=True)
            dur = (time.perf_counter() - start_time) * 1000
            await self._ensure_router_initialized()
            p = ModelQualityTrendsClearFailedPayload(
                project_id=payload.get("project_id", "unknown"),
                error_message=str(e),
                error_code=EnumQualityTrendsErrorCode.INTERNAL_ERROR,
                retry_allowed=True,
                processing_time_ms=dur,
            )
            e = QualityTrendsEventHelpers.create_event_envelope(
                "clear_failed", p, UUID(cid) if isinstance(cid, str) else cid
            )
            await self._router.publish(
                QualityTrendsEventHelpers.get_kafka_topic(
                    EnumQualityTrendsEventType.CLEAR_FAILED
                ),
                e,
                str(cid),
            )
            self.metrics["events_failed"] += 1
            return False

    def _increment_operation_metric(self, op: str) -> None:
        if op not in self.metrics["operations_by_type"]:
            self.metrics["operations_by_type"][op] = 0
        self.metrics["operations_by_type"][op] += 1

    def get_handler_name(self) -> str:
        return "QualityTrendsHandler"

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
