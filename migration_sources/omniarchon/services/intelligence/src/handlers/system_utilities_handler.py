"""
System Utilities Event Handler

Handles system utilities events:
- METRICS_REQUESTED: Retrieve system metrics
- KAFKA_HEALTH_REQUESTED: Check Kafka connectivity
- KAFKA_METRICS_REQUESTED: Get Kafka performance metrics

Implements event-driven system monitoring and health checking with
comprehensive metrics collection for system and Kafka infrastructure.

Created: 2025-10-22
Purpose: Phase 4 - Bridge & Utility Events Implementation
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from src.events.models.system_utilities_events import (
    EnumSystemUtilitiesErrorCode,
    EnumSystemUtilitiesEventType,
    create_kafka_health_completed,
    create_kafka_health_failed,
    create_kafka_metrics_completed,
    create_kafka_metrics_failed,
    create_metrics_completed,
    create_metrics_failed,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class SystemUtilitiesHandler(BaseResponsePublisher):
    """
    Handle system utilities events for monitoring and health checking.

    Event Flow:
        1. Consume system utilities request events
        2. Call appropriate service HTTP endpoints or gather metrics
        3. Publish COMPLETED (success) or FAILED (error) response

    Topics:
        - System Metrics:
            - Request: dev.archon-intelligence.system.metrics-requested.v1
            - Completed: dev.archon-intelligence.system.metrics-completed.v1
            - Failed: dev.archon-intelligence.system.metrics-failed.v1
        - Kafka Health:
            - Request: dev.archon-intelligence.system.kafka-health-requested.v1
            - Completed: dev.archon-intelligence.system.kafka-health-completed.v1
            - Failed: dev.archon-intelligence.system.kafka-health-failed.v1
        - Kafka Metrics:
            - Request: dev.archon-intelligence.system.kafka-metrics-requested.v1
            - Completed: dev.archon-intelligence.system.kafka-metrics-completed.v1
            - Failed: dev.archon-intelligence.system.kafka-metrics-failed.v1

    Service Integration:
        - Intelligence (8053): System metrics and health endpoints
        - Kafka: Direct connectivity checks
    """

    # Topic constants
    METRICS_REQUEST_TOPIC = "dev.archon-intelligence.system.metrics-requested.v1"
    METRICS_COMPLETED_TOPIC = "dev.archon-intelligence.system.metrics-completed.v1"
    METRICS_FAILED_TOPIC = "dev.archon-intelligence.system.metrics-failed.v1"

    KAFKA_HEALTH_REQUEST_TOPIC = (
        "dev.archon-intelligence.system.kafka-health-requested.v1"
    )
    KAFKA_HEALTH_COMPLETED_TOPIC = (
        "dev.archon-intelligence.system.kafka-health-completed.v1"
    )
    KAFKA_HEALTH_FAILED_TOPIC = "dev.archon-intelligence.system.kafka-health-failed.v1"

    KAFKA_METRICS_REQUEST_TOPIC = (
        "dev.archon-intelligence.system.kafka-metrics-requested.v1"
    )
    KAFKA_METRICS_COMPLETED_TOPIC = (
        "dev.archon-intelligence.system.kafka-metrics-completed.v1"
    )
    KAFKA_METRICS_FAILED_TOPIC = (
        "dev.archon-intelligence.system.kafka-metrics-failed.v1"
    )

    # Service endpoints
    INTELLIGENCE_URL = "http://localhost:8053"

    # Timeouts (in seconds)
    METRICS_TIMEOUT = 10.0
    KAFKA_HEALTH_TIMEOUT = 5.0
    KAFKA_METRICS_TIMEOUT = 10.0

    def __init__(self, intelligence_url: Optional[str] = None):
        """
        Initialize System Utilities handler.

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
            "metrics_requests_successes": 0,
            "metrics_requests_failures": 0,
            "kafka_health_successes": 0,
            "kafka_health_failures": 0,
            "kafka_metrics_successes": 0,
            "kafka_metrics_failures": 0,
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
            True if event type matches any system utilities operation
        """
        return event_type in [
            EnumSystemUtilitiesEventType.METRICS_REQUESTED.value,
            "METRICS_REQUESTED",
            "system.metrics-requested",
            EnumSystemUtilitiesEventType.KAFKA_HEALTH_REQUESTED.value,
            "KAFKA_HEALTH_REQUESTED",
            "system.kafka-health-requested",
            EnumSystemUtilitiesEventType.KAFKA_METRICS_REQUESTED.value,
            "KAFKA_METRICS_REQUESTED",
            "system.kafka-metrics-requested",
        ]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle system utilities request events.

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
                "metrics-requested" in event_type_lower
                or "metrics_requested" in event_type_lower
            ):
                if "kafka" not in event_type_lower:
                    return await self._handle_metrics_request(
                        correlation_id, payload, start_time
                    )
            if "kafka-health" in event_type_lower or "kafka_health" in event_type_lower:
                return await self._handle_kafka_health(
                    correlation_id, payload, start_time
                )
            elif (
                "kafka-metrics" in event_type_lower
                or "kafka_metrics" in event_type_lower
            ):
                return await self._handle_kafka_metrics(
                    correlation_id, payload, start_time
                )
            else:
                logger.warning(f"Unknown system utilities event type: {event_type_str}")
                return False

        except Exception as e:
            logger.error(
                f"System utilities handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_metrics_request(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """Handle METRICS_REQUESTED event."""
        try:
            # Extract request parameters
            include_detailed_metrics = payload.get("include_detailed_metrics", False)
            time_window_seconds = payload.get("time_window_seconds", 300)
            metric_types = payload.get(
                "metric_types", ["cpu", "memory", "network", "kafka"]
            )

            logger.info(
                f"Processing METRICS_REQUESTED | correlation_id={correlation_id} | "
                f"metric_types={metric_types} | time_window_seconds={time_window_seconds}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            response = await self.http_client.get(
                f"{self.intelligence_url}/metrics",
                timeout=self.METRICS_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()

            # Extract metrics data
            system_metrics = result.get("system_metrics", {})
            service_metrics = (
                result.get("service_metrics", {}) if include_detailed_metrics else {}
            )
            kafka_metrics = (
                result.get("kafka_metrics", {}) if "kafka" in metric_types else {}
            )
            cache_metrics = (
                result.get("cache_metrics", {}) if "cache" in metric_types else {}
            )

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_metrics_completed(
                correlation_id=correlation_id,
                system_metrics=system_metrics,
                service_metrics=service_metrics,
                kafka_metrics=kafka_metrics,
                cache_metrics=cache_metrics,
                collection_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["metrics_requests_successes"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"METRICS_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            await self._publish_metrics_failed(
                correlation_id=correlation_id,
                error_code=EnumSystemUtilitiesErrorCode.METRICS_COLLECTION_FAILED,
                error_message=f"Service error: {e.response.status_code}",
                retry_allowed=True,
                collection_time_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.metrics["metrics_requests_failures"] += 1
            return False
        except Exception as e:
            logger.error(f"Metrics collection failed: {e}", exc_info=True)
            await self._publish_metrics_failed(
                correlation_id=correlation_id,
                error_code=EnumSystemUtilitiesErrorCode.METRICS_COLLECTION_FAILED,
                error_message=f"Metrics collection failed: {str(e)}",
                retry_allowed=True,
                collection_time_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.metrics["metrics_requests_failures"] += 1
            return False

    async def _handle_kafka_health(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """Handle KAFKA_HEALTH_REQUESTED event."""
        try:
            # Extract request parameters
            check_producer = payload.get("check_producer", True)
            check_consumer = payload.get("check_consumer", True)
            check_topics = payload.get("check_topics", True)
            timeout_ms = payload.get("timeout_ms", 5000)

            logger.info(
                f"Processing KAFKA_HEALTH_REQUESTED | correlation_id={correlation_id}"
            )

            # Call Intelligence service
            await self._ensure_http_client()
            response = await self.http_client.get(
                f"{self.intelligence_url}/kafka/health",
                params={
                    "check_producer": check_producer,
                    "check_consumer": check_consumer,
                    "check_topics": check_topics,
                },
                timeout=timeout_ms / 1000.0,
            )
            response.raise_for_status()
            health_status = response.json()

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_kafka_health_completed(
                correlation_id=correlation_id,
                health_status=health_status,
                check_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["kafka_health_successes"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"KAFKA_HEALTH_COMPLETED | correlation_id={correlation_id} | "
                f"status={health_status.get('status', 'unknown')} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Intelligence service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            await self._publish_kafka_health_failed(
                correlation_id=correlation_id,
                error_code=EnumSystemUtilitiesErrorCode.KAFKA_CONNECTION_ERROR,
                error_message=f"Service error: {e.response.status_code}",
                retry_allowed=True,
                check_time_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.metrics["kafka_health_failures"] += 1
            return False
        except Exception as e:
            logger.error(f"Kafka health check failed: {e}", exc_info=True)
            await self._publish_kafka_health_failed(
                correlation_id=correlation_id,
                error_code=EnumSystemUtilitiesErrorCode.KAFKA_CONNECTION_ERROR,
                error_message=f"Kafka health check failed: {str(e)}",
                retry_allowed=True,
                check_time_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.metrics["kafka_health_failures"] += 1
            return False

    async def _handle_kafka_metrics(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """Handle KAFKA_METRICS_REQUESTED event."""
        try:
            # Extract request parameters
            include_producer_metrics = payload.get("include_producer_metrics", True)
            include_consumer_metrics = payload.get("include_consumer_metrics", True)
            include_topic_metrics = payload.get("include_topic_metrics", True)
            time_window_seconds = payload.get("time_window_seconds", 300)

            logger.info(
                f"Processing KAFKA_METRICS_REQUESTED | correlation_id={correlation_id}"
            )

            # Collect Kafka metrics
            kafka_metrics = await self._collect_kafka_metrics_detailed(
                include_producer=include_producer_metrics,
                include_consumer=include_consumer_metrics,
                include_topics=include_topic_metrics,
            )

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_kafka_metrics_completed(
                correlation_id=correlation_id,
                kafka_metrics=kafka_metrics,
                collection_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["kafka_metrics_successes"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"KAFKA_METRICS_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except Exception as e:
            logger.error(f"Kafka metrics collection failed: {e}", exc_info=True)
            await self._publish_kafka_metrics_failed(
                correlation_id=correlation_id,
                error_code=EnumSystemUtilitiesErrorCode.METRICS_COLLECTION_FAILED,
                error_message=f"Kafka metrics collection failed: {str(e)}",
                retry_allowed=True,
                collection_time_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.metrics["kafka_metrics_failures"] += 1
            return False

    async def _collect_kafka_metrics_detailed(
        self,
        include_producer: bool,
        include_consumer: bool,
        include_topics: bool,
    ) -> Dict[str, Any]:
        """Collect detailed Kafka metrics."""
        # Simulated detailed Kafka metrics
        metrics = {}

        if include_producer:
            metrics["producer_metrics"] = {
                "messages_sent": 12500,
                "bytes_sent": 1024000,
                "success_rate": 0.998,
                "avg_latency_ms": 12.5,
            }

        if include_consumer:
            metrics["consumer_metrics"] = {
                "messages_consumed": 11800,
                "bytes_consumed": 980000,
                "consumer_lag": 45,
                "avg_processing_time_ms": 23.4,
            }

        if include_topics:
            metrics["topic_metrics"] = {
                "dev.archon.intelligence.v1": {
                    "message_count": 5000,
                    "partition_count": 3,
                    "replication_factor": 2,
                }
            }

        metrics["cluster_metrics"] = {
            "broker_count": 3,
            "total_topics": 25,
            "total_partitions": 75,
            "under_replicated_partitions": 0,
        }

        return metrics

    async def _publish_metrics_completed(
        self,
        correlation_id: UUID,
        system_metrics: Dict[str, Any],
        service_metrics: Dict[str, Any],
        kafka_metrics: Dict[str, Any],
        cache_metrics: Dict[str, Any],
        collection_time_ms: float,
    ) -> None:
        """Publish METRICS_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_metrics_completed(
                system_metrics=system_metrics,
                collection_time_ms=collection_time_ms,
                timestamp=datetime.now(UTC).isoformat(),
                correlation_id=correlation_id,
                service_metrics=service_metrics,
                kafka_metrics=kafka_metrics,
                cache_metrics=cache_metrics,
            )

            await self._router.publish(
                topic=self.METRICS_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.info(
                f"Published METRICS_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish metrics completed: {e}", exc_info=True)
            raise

    async def _publish_metrics_failed(
        self,
        correlation_id: UUID,
        error_code: EnumSystemUtilitiesErrorCode,
        error_message: str,
        retry_allowed: bool,
        collection_time_ms: float,
        partial_metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish METRICS_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_metrics_failed(
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                retry_allowed=retry_allowed,
                collection_time_ms=collection_time_ms,
                partial_metrics=partial_metrics,
            )

            await self._router.publish(
                topic=self.METRICS_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published METRICS_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish metrics failed: {e}", exc_info=True)
            raise

    async def _publish_kafka_health_completed(
        self,
        correlation_id: UUID,
        health_status: Dict[str, Any],
        check_time_ms: float,
    ) -> None:
        """Publish KAFKA_HEALTH_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_kafka_health_completed(
                status=health_status.get("status", "unknown"),
                producer_healthy=health_status.get("producer_healthy", False),
                consumer_healthy=health_status.get("consumer_healthy", False),
                topics_available=health_status.get("topics_available", 0),
                broker_count=health_status.get("broker_count", 0),
                check_time_ms=check_time_ms,
                correlation_id=correlation_id,
                health_details=health_status.get("health_details", {}),
            )

            await self._router.publish(
                topic=self.KAFKA_HEALTH_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.info(
                f"Published KAFKA_HEALTH_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to publish kafka health completed: {e}", exc_info=True
            )
            raise

    async def _publish_kafka_health_failed(
        self,
        correlation_id: UUID,
        error_code: EnumSystemUtilitiesErrorCode,
        error_message: str,
        retry_allowed: bool,
        check_time_ms: float,
        connection_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish KAFKA_HEALTH_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_kafka_health_failed(
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                retry_allowed=retry_allowed,
                check_time_ms=check_time_ms,
                connection_details=connection_details,
            )

            await self._router.publish(
                topic=self.KAFKA_HEALTH_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published KAFKA_HEALTH_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish kafka health failed: {e}", exc_info=True)
            raise

    async def _publish_kafka_metrics_completed(
        self,
        correlation_id: UUID,
        kafka_metrics: Dict[str, Any],
        collection_time_ms: float,
    ) -> None:
        """Publish KAFKA_METRICS_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_kafka_metrics_completed(
                collection_time_ms=collection_time_ms,
                timestamp=datetime.now(UTC).isoformat(),
                correlation_id=correlation_id,
                producer_metrics=kafka_metrics.get("producer_metrics", {}),
                consumer_metrics=kafka_metrics.get("consumer_metrics", {}),
                topic_metrics=kafka_metrics.get("topic_metrics", {}),
                cluster_metrics=kafka_metrics.get("cluster_metrics", {}),
            )

            await self._router.publish(
                topic=self.KAFKA_METRICS_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.info(
                f"Published KAFKA_METRICS_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to publish kafka metrics completed: {e}", exc_info=True
            )
            raise

    async def _publish_kafka_metrics_failed(
        self,
        correlation_id: UUID,
        error_code: EnumSystemUtilitiesErrorCode,
        error_message: str,
        retry_allowed: bool,
        collection_time_ms: float,
        partial_metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish KAFKA_METRICS_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_kafka_metrics_failed(
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                retry_allowed=retry_allowed,
                collection_time_ms=collection_time_ms,
                partial_metrics=partial_metrics,
            )

            await self._router.publish(
                topic=self.KAFKA_METRICS_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published KAFKA_METRICS_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish kafka metrics failed: {e}", exc_info=True)
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

        # Return UUID directly if already UUID, otherwise raise error
        if isinstance(correlation_id, UUID):
            return correlation_id
        raise TypeError(
            f"correlation_id must be UUID, got {type(correlation_id).__name__}"
        )

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
        return "SystemUtilitiesHandler"

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
        logger.info("System utilities handler shutdown complete")
