"""
Pattern Analytics Event Handler

Handles pattern analytics request events and publishes completed/failed responses.
Implements event-driven interface for pattern success rates, top patterns, emerging patterns analysis.

Handles 5 event types:
1. SUCCESS_RATES_REQUESTED → SUCCESS_RATES_COMPLETED/FAILED
2. TOP_PATTERNS_REQUESTED → TOP_PATTERNS_COMPLETED/FAILED
3. EMERGING_REQUESTED → EMERGING_COMPLETED/FAILED
4. HISTORY_REQUESTED → HISTORY_COMPLETED/FAILED
5. HEALTH_REQUESTED → HEALTH_COMPLETED/FAILED

Created: 2025-10-22
Purpose: Event-driven pattern analytics integration for Phase 3
"""

import logging
import os
import time
from typing import Any, Dict
from uuid import UUID

import httpx
from src.events.models.pattern_analytics_events import (
    EnumPatternAnalyticsErrorCode,
    EnumPatternAnalyticsEventType,
    ModelPatternAnalyticsEmergingCompletedPayload,
    ModelPatternAnalyticsEmergingFailedPayload,
    ModelPatternAnalyticsEmergingRequestPayload,
    ModelPatternAnalyticsHealthCompletedPayload,
    ModelPatternAnalyticsHealthFailedPayload,
    ModelPatternAnalyticsHistoryCompletedPayload,
    ModelPatternAnalyticsHistoryFailedPayload,
    ModelPatternAnalyticsHistoryRequestPayload,
    ModelPatternAnalyticsSuccessRatesCompletedPayload,
    ModelPatternAnalyticsSuccessRatesFailedPayload,
    ModelPatternAnalyticsSuccessRatesRequestPayload,
    ModelPatternAnalyticsTopPatternsCompletedPayload,
    ModelPatternAnalyticsTopPatternsFailedPayload,
    ModelPatternAnalyticsTopPatternsRequestPayload,
    PatternAnalyticsEventHelpers,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class PatternAnalyticsHandler(BaseResponsePublisher):
    """Handle pattern analytics request events and publish results."""

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv("INTELLIGENCE_SERVICE_URL", "http://localhost:8053")
        self.timeout = 10.0
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "operations_by_type": {},
        }

    def can_handle(self, event_type: str) -> bool:
        try:
            EnumPatternAnalyticsEventType(event_type)
            return "REQUESTED" in event_type
        except ValueError:
            return any(
                k in event_type.lower()
                for k in [
                    "success_rates",
                    "top_patterns",
                    "emerging",
                    "history",
                    "health",
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
                "success_rates" in event_type_str.lower()
                or "success-rates" in event_type_str.lower()
            ):
                return await self._handle_success_rates(
                    correlation_id, payload, start_time
                )
            elif (
                "top_patterns" in event_type_str.lower()
                or "top-patterns" in event_type_str.lower()
            ):
                return await self._handle_top_patterns(
                    correlation_id, payload, start_time
                )
            elif "emerging" in event_type_str.lower():
                return await self._handle_emerging(correlation_id, payload, start_time)
            elif "history" in event_type_str.lower():
                return await self._handle_history(correlation_id, payload, start_time)
            elif "health" in event_type_str.lower():
                return await self._handle_health(correlation_id, payload, start_time)
            else:
                logger.error(f"Unknown pattern analytics operation: {event_type_str}")
                return False
        except Exception as e:
            logger.error(
                f"Pattern analytics handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_success_rates(
        self, correlation_id: str, payload: dict, start_time: float
    ) -> bool:
        try:
            request = ModelPatternAnalyticsSuccessRatesRequestPayload(**payload)
            logger.info(
                f"Processing SUCCESS_RATES_REQUESTED | correlation_id={correlation_id}"
            )

            # GET http://localhost:8053/api/pattern-analytics/success-rates
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/pattern-analytics/success-rates",
                    params=(
                        {"min_success_rate": request.min_success_rate}
                        if request.min_success_rate
                        else {}
                    ),
                )
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_success_rates_completed(
                correlation_id, result, duration_ms
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("success_rates")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Success rates HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_success_rates_failed(
                correlation_id,
                str(e),
                EnumPatternAnalyticsErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Success rates failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_success_rates_failed(
                correlation_id,
                str(e),
                EnumPatternAnalyticsErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_top_patterns(
        self, correlation_id: str, payload: dict, start_time: float
    ) -> bool:
        try:
            request = ModelPatternAnalyticsTopPatternsRequestPayload(**payload)
            logger.info(
                f"Processing TOP_PATTERNS_REQUESTED | correlation_id={correlation_id}"
            )

            # GET http://localhost:8053/api/pattern-analytics/top-patterns
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                params = {}
                if request.limit:
                    params["limit"] = request.limit
                if request.min_score:
                    params["min_score"] = request.min_score
                response = await client.get(
                    f"{self.base_url}/api/pattern-analytics/top-patterns", params=params
                )
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_top_patterns_completed(
                correlation_id, result, duration_ms
            )
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("top_patterns")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Top patterns HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_top_patterns_failed(
                correlation_id,
                str(e),
                EnumPatternAnalyticsErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Top patterns failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_top_patterns_failed(
                correlation_id,
                str(e),
                EnumPatternAnalyticsErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_emerging(
        self, correlation_id: str, payload: dict, start_time: float
    ) -> bool:
        try:
            request = ModelPatternAnalyticsEmergingRequestPayload(**payload)
            logger.info(
                f"Processing EMERGING_REQUESTED | correlation_id={correlation_id}"
            )

            # GET http://localhost:8053/api/pattern-analytics/emerging-patterns
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                params = {}
                if request.time_window_hours:
                    params["time_window_hours"] = request.time_window_hours
                if request.min_occurrences:
                    params["min_occurrences"] = request.min_occurrences
                response = await client.get(
                    f"{self.base_url}/api/pattern-analytics/emerging-patterns",
                    params=params,
                )
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_emerging_completed(correlation_id, result, duration_ms)
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("emerging")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Emerging HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_emerging_failed(
                correlation_id,
                str(e),
                EnumPatternAnalyticsErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Emerging failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_emerging_failed(
                correlation_id,
                str(e),
                EnumPatternAnalyticsErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_history(
        self, correlation_id: str, payload: dict, start_time: float
    ) -> bool:
        try:
            request = ModelPatternAnalyticsHistoryRequestPayload(**payload)
            logger.info(
                f"Processing HISTORY_REQUESTED | correlation_id={correlation_id} | pattern_id={request.pattern_id}"
            )

            # GET http://localhost:8053/api/pattern-analytics/pattern/{pattern_id}/history
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/pattern-analytics/pattern/{request.pattern_id}/history"
                )
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_history_completed(correlation_id, result, duration_ms)
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("history")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"History HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_history_failed(
                correlation_id,
                payload.get("pattern_id", "unknown"),
                str(e),
                EnumPatternAnalyticsErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"History failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_history_failed(
                correlation_id,
                payload.get("pattern_id", "unknown"),
                str(e),
                EnumPatternAnalyticsErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_health(
        self, correlation_id: str, payload: dict, start_time: float
    ) -> bool:
        try:
            logger.info(
                f"Processing HEALTH_REQUESTED | correlation_id={correlation_id}"
            )

            # GET http://localhost:8053/api/pattern-analytics/health
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/pattern-analytics/health"
                )
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_health_completed(correlation_id, result, duration_ms)
            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("health")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Health HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_health_failed(
                correlation_id,
                str(e),
                EnumPatternAnalyticsErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Health failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_health_failed(
                correlation_id,
                str(e),
                EnumPatternAnalyticsErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    # Publish methods
    async def _publish_success_rates_completed(
        self, cid: str, r: dict, t: float
    ) -> None:
        await self._ensure_router_initialized()
        p = ModelPatternAnalyticsSuccessRatesCompletedPayload(
            patterns=r["patterns"], summary=r["summary"], processing_time_ms=t
        )
        e = PatternAnalyticsEventHelpers.create_event_envelope(
            "success_rates_completed", p, UUID(cid) if isinstance(cid, str) else cid
        )
        await self._router.publish(
            PatternAnalyticsEventHelpers.get_kafka_topic(
                EnumPatternAnalyticsEventType.SUCCESS_RATES_COMPLETED
            ),
            e,
            str(cid),
        )

    async def _publish_success_rates_failed(
        self, cid: str, msg: str, code: EnumPatternAnalyticsErrorCode, t: float
    ) -> None:
        await self._ensure_router_initialized()
        p = ModelPatternAnalyticsSuccessRatesFailedPayload(
            error_message=msg, error_code=code, retry_allowed=True, processing_time_ms=t
        )
        e = PatternAnalyticsEventHelpers.create_event_envelope(
            "success_rates_failed", p, UUID(cid) if isinstance(cid, str) else cid
        )
        await self._router.publish(
            PatternAnalyticsEventHelpers.get_kafka_topic(
                EnumPatternAnalyticsEventType.SUCCESS_RATES_FAILED
            ),
            e,
            str(cid),
        )

    async def _publish_top_patterns_completed(
        self, cid: str, r: dict, t: float
    ) -> None:
        await self._ensure_router_initialized()
        p = ModelPatternAnalyticsTopPatternsCompletedPayload(
            top_patterns=r["top_patterns"],
            total_patterns=r["total_patterns"],
            filter_criteria=r["filter_criteria"],
            processing_time_ms=t,
        )
        e = PatternAnalyticsEventHelpers.create_event_envelope(
            "top_patterns_completed", p, UUID(cid) if isinstance(cid, str) else cid
        )
        await self._router.publish(
            PatternAnalyticsEventHelpers.get_kafka_topic(
                EnumPatternAnalyticsEventType.TOP_PATTERNS_COMPLETED
            ),
            e,
            str(cid),
        )

    async def _publish_top_patterns_failed(
        self, cid: str, msg: str, code: EnumPatternAnalyticsErrorCode, t: float
    ) -> None:
        await self._ensure_router_initialized()
        p = ModelPatternAnalyticsTopPatternsFailedPayload(
            error_message=msg, error_code=code, retry_allowed=True, processing_time_ms=t
        )
        e = PatternAnalyticsEventHelpers.create_event_envelope(
            "top_patterns_failed", p, UUID(cid) if isinstance(cid, str) else cid
        )
        await self._router.publish(
            PatternAnalyticsEventHelpers.get_kafka_topic(
                EnumPatternAnalyticsEventType.TOP_PATTERNS_FAILED
            ),
            e,
            str(cid),
        )

    async def _publish_emerging_completed(self, cid: str, r: dict, t: float) -> None:
        await self._ensure_router_initialized()
        p = ModelPatternAnalyticsEmergingCompletedPayload(
            emerging_patterns=r["emerging_patterns"],
            total_emerging=r["total_emerging"],
            time_window_hours=r["time_window_hours"],
            processing_time_ms=t,
        )
        e = PatternAnalyticsEventHelpers.create_event_envelope(
            "emerging_completed", p, UUID(cid) if isinstance(cid, str) else cid
        )
        await self._router.publish(
            PatternAnalyticsEventHelpers.get_kafka_topic(
                EnumPatternAnalyticsEventType.EMERGING_COMPLETED
            ),
            e,
            str(cid),
        )

    async def _publish_emerging_failed(
        self, cid: str, msg: str, code: EnumPatternAnalyticsErrorCode, t: float
    ) -> None:
        await self._ensure_router_initialized()
        p = ModelPatternAnalyticsEmergingFailedPayload(
            error_message=msg, error_code=code, retry_allowed=True, processing_time_ms=t
        )
        e = PatternAnalyticsEventHelpers.create_event_envelope(
            "emerging_failed", p, UUID(cid) if isinstance(cid, str) else cid
        )
        await self._router.publish(
            PatternAnalyticsEventHelpers.get_kafka_topic(
                EnumPatternAnalyticsEventType.EMERGING_FAILED
            ),
            e,
            str(cid),
        )

    async def _publish_history_completed(self, cid: str, r: dict, t: float) -> None:
        await self._ensure_router_initialized()
        p = ModelPatternAnalyticsHistoryCompletedPayload(
            pattern_id=r["pattern_id"],
            pattern_name=r["pattern_name"],
            feedback_history=r["feedback_history"],
            summary=r["summary"],
            processing_time_ms=t,
        )
        e = PatternAnalyticsEventHelpers.create_event_envelope(
            "history_completed", p, UUID(cid) if isinstance(cid, str) else cid
        )
        await self._router.publish(
            PatternAnalyticsEventHelpers.get_kafka_topic(
                EnumPatternAnalyticsEventType.HISTORY_COMPLETED
            ),
            e,
            str(cid),
        )

    async def _publish_history_failed(
        self,
        cid: str,
        pid: str,
        msg: str,
        code: EnumPatternAnalyticsErrorCode,
        t: float,
    ) -> None:
        await self._ensure_router_initialized()
        p = ModelPatternAnalyticsHistoryFailedPayload(
            pattern_id=pid,
            error_message=msg,
            error_code=code,
            retry_allowed=True,
            processing_time_ms=t,
        )
        e = PatternAnalyticsEventHelpers.create_event_envelope(
            "history_failed", p, UUID(cid) if isinstance(cid, str) else cid
        )
        await self._router.publish(
            PatternAnalyticsEventHelpers.get_kafka_topic(
                EnumPatternAnalyticsEventType.HISTORY_FAILED
            ),
            e,
            str(cid),
        )

    async def _publish_health_completed(self, cid: str, r: dict, t: float) -> None:
        await self._ensure_router_initialized()
        p = ModelPatternAnalyticsHealthCompletedPayload(
            status=r["status"],
            service=r["service"],
            endpoints=r["endpoints"],
            processing_time_ms=t,
        )
        e = PatternAnalyticsEventHelpers.create_event_envelope(
            "health_completed", p, UUID(cid) if isinstance(cid, str) else cid
        )
        await self._router.publish(
            PatternAnalyticsEventHelpers.get_kafka_topic(
                EnumPatternAnalyticsEventType.HEALTH_COMPLETED
            ),
            e,
            str(cid),
        )

    async def _publish_health_failed(
        self, cid: str, msg: str, code: EnumPatternAnalyticsErrorCode, t: float
    ) -> None:
        await self._ensure_router_initialized()
        p = ModelPatternAnalyticsHealthFailedPayload(
            error_message=msg, error_code=code, retry_allowed=True, processing_time_ms=t
        )
        e = PatternAnalyticsEventHelpers.create_event_envelope(
            "health_failed", p, UUID(cid) if isinstance(cid, str) else cid
        )
        await self._router.publish(
            PatternAnalyticsEventHelpers.get_kafka_topic(
                EnumPatternAnalyticsEventType.HEALTH_FAILED
            ),
            e,
            str(cid),
        )

    def _increment_operation_metric(self, op: str) -> None:
        if op not in self.metrics["operations_by_type"]:
            self.metrics["operations_by_type"][op] = 0
        self.metrics["operations_by_type"][op] += 1

    def get_handler_name(self) -> str:
        return "PatternAnalyticsHandler"

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
