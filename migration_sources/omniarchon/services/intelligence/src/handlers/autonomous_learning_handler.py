"""
Autonomous Learning Event Handler

Handles autonomous learning request events and publishes completed/failed responses.
Implements event-driven interface for pattern ingestion, predictions, and autonomous execution.

Handles 7 event types:
1. PATTERN_INGEST_REQUESTED → PATTERN_INGEST_COMPLETED/FAILED
2. PATTERN_SUCCESS_REQUESTED → PATTERN_SUCCESS_COMPLETED/FAILED
3. AGENT_PREDICT_REQUESTED → AGENT_PREDICT_COMPLETED/FAILED
4. TIME_PREDICT_REQUESTED → TIME_PREDICT_COMPLETED/FAILED
5. SAFETY_SCORE_REQUESTED → SAFETY_SCORE_COMPLETED/FAILED
6. STATS_REQUESTED → STATS_COMPLETED/FAILED
7. HEALTH_REQUESTED → HEALTH_COMPLETED/FAILED

Created: 2025-10-22
Purpose: Event-driven autonomous learning integration for Phase 3
"""

import logging
import os
import time
from typing import Any, Dict
from uuid import UUID

import httpx
from src.events.models.autonomous_learning_events import (
    AutonomousLearningEventHelpers,
    EnumAutonomousErrorCode,
    EnumAutonomousEventType,
    ModelAutonomousAgentPredictCompletedPayload,
    ModelAutonomousAgentPredictFailedPayload,
    ModelAutonomousAgentPredictRequestPayload,
    ModelAutonomousHealthCompletedPayload,
    ModelAutonomousHealthFailedPayload,
    ModelAutonomousPatternsIngestCompletedPayload,
    ModelAutonomousPatternsIngestFailedPayload,
    ModelAutonomousPatternsIngestRequestPayload,
    ModelAutonomousPatternsSuccessCompletedPayload,
    ModelAutonomousPatternsSuccessFailedPayload,
    ModelAutonomousPatternsSuccessRequestPayload,
    ModelAutonomousSafetyScoreCompletedPayload,
    ModelAutonomousSafetyScoreFailedPayload,
    ModelAutonomousSafetyScoreRequestPayload,
    ModelAutonomousStatsCompletedPayload,
    ModelAutonomousStatsFailedPayload,
    ModelAutonomousTimePredictCompletedPayload,
    ModelAutonomousTimePredictFailedPayload,
    ModelAutonomousTimePredictRequestPayload,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class AutonomousLearningHandler(BaseResponsePublisher):
    """Handle autonomous learning request events and publish results."""

    def __init__(self):
        """Initialize Autonomous Learning handler."""
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
        """Check if this handler can process the given event type."""
        try:
            EnumAutonomousEventType(event_type)
            return "REQUESTED" in event_type
        except ValueError:
            return any(
                keyword in event_type.lower()
                for keyword in [
                    "pattern_ingest_requested",
                    "pattern_success_requested",
                    "agent_predict_requested",
                    "time_predict_requested",
                    "safety_score_requested",
                    "stats_requested",
                    "health_requested",
                    "pattern-ingest-requested",
                    "pattern-success-requested",
                    "agent-predict-requested",
                    "time-predict-requested",
                    "safety-score-requested",
                    "stats-requested",
                    "health-requested",
                ]
            )

    async def handle_event(self, event: Any) -> bool:
        """Handle autonomous learning request event."""
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
                "pattern_ingest" in event_type_str.lower()
                or "pattern-ingest" in event_type_str.lower()
            ):
                return await self._handle_pattern_ingest(
                    correlation_id, payload, start_time
                )
            elif (
                "pattern_success" in event_type_str.lower()
                or "pattern-success" in event_type_str.lower()
            ):
                return await self._handle_pattern_success(
                    correlation_id, payload, start_time
                )
            elif (
                "agent_predict" in event_type_str.lower()
                or "agent-predict" in event_type_str.lower()
            ):
                return await self._handle_agent_predict(
                    correlation_id, payload, start_time
                )
            elif (
                "time_predict" in event_type_str.lower()
                or "time-predict" in event_type_str.lower()
            ):
                return await self._handle_time_predict(
                    correlation_id, payload, start_time
                )
            elif (
                "safety_score" in event_type_str.lower()
                or "safety-score" in event_type_str.lower()
            ):
                return await self._handle_safety_score(
                    correlation_id, payload, start_time
                )
            elif (
                "stats" in event_type_str.lower()
                and "health" not in event_type_str.lower()
            ):
                return await self._handle_stats(correlation_id, payload, start_time)
            elif "health" in event_type_str.lower():
                return await self._handle_health(correlation_id, payload, start_time)
            else:
                logger.error(f"Unknown autonomous operation type: {event_type_str}")
                return False

        except Exception as e:
            logger.error(
                f"Autonomous learning handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_pattern_ingest(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle PATTERN_INGEST_REQUESTED event."""
        try:
            request = ModelAutonomousPatternsIngestRequestPayload(**payload)
            logger.info(
                f"Processing PATTERN_INGEST_REQUESTED | correlation_id={correlation_id}"
            )

            # HTTP call: POST /api/autonomous/patterns/ingest
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/autonomous/patterns/ingest",
                    json={
                        "patterns": (
                            request.patterns if hasattr(request, "patterns") else []
                        ),
                        "source": (
                            request.source
                            if hasattr(request, "source")
                            else "event_bus"
                        ),
                    },
                )
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_pattern_ingest_completed(
                correlation_id, result, duration_ms
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("pattern_ingest")
            return True

        except Exception as e:
            logger.error(f"Pattern ingest operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_pattern_ingest_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_pattern_success(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle PATTERN_SUCCESS_REQUESTED event."""
        try:
            request = ModelAutonomousPatternsSuccessRequestPayload(**payload)
            logger.info(
                f"Processing PATTERN_SUCCESS_REQUESTED | correlation_id={correlation_id} | min_success_rate={request.min_success_rate}"
            )

            # POST http://localhost:8053/api/autonomous/patterns/success
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/autonomous/patterns/success",
                    json={
                        "min_success_rate": request.min_success_rate,
                        "limit": request.limit,
                    },
                )
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_pattern_success_completed(
                correlation_id, result, duration_ms
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("pattern_success")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Pattern success HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_pattern_success_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Pattern success operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_pattern_success_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_agent_predict(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle AGENT_PREDICT_REQUESTED event."""
        try:
            request = ModelAutonomousAgentPredictRequestPayload(**payload)
            logger.info(
                f"Processing AGENT_PREDICT_REQUESTED | correlation_id={correlation_id}"
            )

            # POST http://localhost:8053/api/autonomous/predict/agent
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/autonomous/predict/agent",
                    json={
                        "context": request.context,
                        "requirements": request.requirements,
                    },
                )
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_agent_predict_completed(
                correlation_id, result, duration_ms
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("agent_predict")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Agent predict HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_agent_predict_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Agent predict operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_agent_predict_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_time_predict(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle TIME_PREDICT_REQUESTED event."""
        try:
            request = ModelAutonomousTimePredictRequestPayload(**payload)
            logger.info(
                f"Processing TIME_PREDICT_REQUESTED | correlation_id={correlation_id} | agent={request.agent}"
            )

            # POST http://localhost:8053/api/autonomous/predict/time
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/autonomous/predict/time",
                    json={
                        "task_description": request.task_description,
                        "agent": request.agent,
                        "complexity": request.complexity,
                    },
                )
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_time_predict_completed(
                correlation_id, result, duration_ms
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("time_predict")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Time predict HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_time_predict_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Time predict operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_time_predict_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_safety_score(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle SAFETY_SCORE_REQUESTED event."""
        try:
            request = ModelAutonomousSafetyScoreRequestPayload(**payload)
            logger.info(
                f"Processing SAFETY_SCORE_REQUESTED | correlation_id={correlation_id} | task_type={request.task_type}"
            )

            # GET http://localhost:8053/api/autonomous/calculate/safety
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/autonomous/calculate/safety",
                    params={
                        "action": request.task_type,
                        "context": request.context or "",
                    },
                )
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_safety_score_completed(
                correlation_id, result, duration_ms
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("safety_score")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Safety score HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_safety_score_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Safety score operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_safety_score_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_stats(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle STATS_REQUESTED event."""
        try:
            logger.info(f"Processing STATS_REQUESTED | correlation_id={correlation_id}")

            # GET http://localhost:8053/api/autonomous/stats
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/autonomous/stats")
                response.raise_for_status()
                result = response.json()

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_stats_completed(correlation_id, result, duration_ms)

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("stats")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Stats HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_stats_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
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
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_health(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle HEALTH_REQUESTED event."""
        try:
            logger.info(
                f"Processing HEALTH_REQUESTED | correlation_id={correlation_id}"
            )

            # GET http://localhost:8053/api/autonomous/health
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/autonomous/health")
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
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Health operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_health_failed(
                correlation_id,
                str(e),
                EnumAutonomousErrorCode.INTERNAL_ERROR,
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    # Publish methods (completed payloads)
    async def _publish_pattern_ingest_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousPatternsIngestCompletedPayload(
            pattern_id=result["pattern_id"],
            pattern_name=result["pattern_name"],
            is_new_pattern=result["is_new_pattern"],
            success_rate=result["success_rate"],
            total_executions=result["total_executions"],
            confidence_score=result["confidence_score"],
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "pattern_ingest_completed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.PATTERN_INGEST_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published PATTERN_INGEST_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_pattern_ingest_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumAutonomousErrorCode,
        processing_time_ms: float,
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousPatternsIngestFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "pattern_ingest_failed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.PATTERN_INGEST_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published PATTERN_INGEST_FAILED | correlation_id={correlation_id}"
        )

    async def _publish_pattern_success_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousPatternsSuccessCompletedPayload(
            patterns=result["patterns"],
            count=result["count"],
            filters_applied=result["filters_applied"],
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "pattern_success_completed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.PATTERN_SUCCESS_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published PATTERN_SUCCESS_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_pattern_success_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumAutonomousErrorCode,
        processing_time_ms: float,
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousPatternsSuccessFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "pattern_success_failed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.PATTERN_SUCCESS_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published PATTERN_SUCCESS_FAILED | correlation_id={correlation_id}"
        )

    async def _publish_agent_predict_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousAgentPredictCompletedPayload(
            recommended_agent=result["recommended_agent"],
            confidence_score=result["confidence_score"],
            confidence_level=result["confidence_level"],
            reasoning=result["reasoning"],
            alternative_agents=result["alternative_agents"],
            expected_success_rate=result["expected_success_rate"],
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "agent_predict_completed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.AGENT_PREDICT_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published AGENT_PREDICT_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_agent_predict_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumAutonomousErrorCode,
        processing_time_ms: float,
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousAgentPredictFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "agent_predict_failed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.AGENT_PREDICT_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published AGENT_PREDICT_FAILED | correlation_id={correlation_id}"
        )

    async def _publish_time_predict_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousTimePredictCompletedPayload(
            estimated_duration_ms=result["estimated_duration_ms"],
            p25_duration_ms=result["p25_duration_ms"],
            p75_duration_ms=result["p75_duration_ms"],
            p95_duration_ms=result["p95_duration_ms"],
            confidence_score=result["confidence_score"],
            time_breakdown=result["time_breakdown"],
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "time_predict_completed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.TIME_PREDICT_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published TIME_PREDICT_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_time_predict_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumAutonomousErrorCode,
        processing_time_ms: float,
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousTimePredictFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "time_predict_failed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.TIME_PREDICT_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published TIME_PREDICT_FAILED | correlation_id={correlation_id}"
        )

    async def _publish_safety_score_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousSafetyScoreCompletedPayload(
            safety_score=result["safety_score"],
            safety_rating=result["safety_rating"],
            can_execute_autonomously=result["can_execute_autonomously"],
            requires_human_review=result["requires_human_review"],
            risk_factors=result["risk_factors"],
            safety_checks_required=result["safety_checks_required"],
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "safety_score_completed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.SAFETY_SCORE_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published SAFETY_SCORE_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_safety_score_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumAutonomousErrorCode,
        processing_time_ms: float,
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousSafetyScoreFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "safety_score_failed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.SAFETY_SCORE_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published SAFETY_SCORE_FAILED | correlation_id={correlation_id}"
        )

    async def _publish_stats_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousStatsCompletedPayload(
            total_patterns=result["total_patterns"],
            total_agents=result["total_agents"],
            average_success_rate=result["average_success_rate"],
            total_executions=result["total_executions"],
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "stats_completed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.STATS_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(f"Published STATS_COMPLETED | correlation_id={correlation_id}")

    async def _publish_stats_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumAutonomousErrorCode,
        processing_time_ms: float,
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousStatsFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "stats_failed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.STATS_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(f"Published STATS_FAILED | correlation_id={correlation_id}")

    async def _publish_health_completed(
        self, correlation_id: UUID, result: dict, processing_time_ms: float
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousHealthCompletedPayload(
            status=result["status"],
            service=result["service"],
            version=result["version"],
            uptime_seconds=result["uptime_seconds"],
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "health_completed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.HEALTH_COMPLETED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(f"Published HEALTH_COMPLETED | correlation_id={correlation_id}")

    async def _publish_health_failed(
        self,
        correlation_id: UUID,
        error_message: str,
        error_code: EnumAutonomousErrorCode,
        processing_time_ms: float,
    ) -> None:
        await self._ensure_router_initialized()
        payload = ModelAutonomousHealthFailedPayload(
            error_message=error_message,
            error_code=error_code,
            retry_allowed=True,
            processing_time_ms=processing_time_ms,
        )
        event_envelope = AutonomousLearningEventHelpers.create_event_envelope(
            "health_failed",
            payload,
            correlation_id,
        )
        topic = AutonomousLearningEventHelpers.get_kafka_topic(
            EnumAutonomousEventType.HEALTH_FAILED
        )
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(f"Published HEALTH_FAILED | correlation_id={correlation_id}")

    def _increment_operation_metric(self, operation: str) -> None:
        """Increment operation-specific metric."""
        if operation not in self.metrics["operations_by_type"]:
            self.metrics["operations_by_type"][operation] = 0
        self.metrics["operations_by_type"][operation] += 1

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "AutonomousLearningHandler"

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
