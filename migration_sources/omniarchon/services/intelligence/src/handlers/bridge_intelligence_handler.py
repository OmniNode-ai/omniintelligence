"""
Bridge Intelligence Event Handler

Handles bridge intelligence events:
- GENERATE_INTELLIGENCE_REQUESTED: Generate OmniNode metadata intelligence
- BRIDGE_HEALTH_REQUESTED: Check bridge service health
- CAPABILITIES_REQUESTED: Retrieve bridge service capabilities

Implements event-driven integration with Bridge service for metadata generation,
health monitoring, and capability discovery.

Created: 2025-10-22
Purpose: Phase 4 - Bridge & Utility Events Implementation
"""

import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from src.events.models.bridge_intelligence_events import (
    EnumBridgeErrorCode,
    EnumBridgeEventType,
    create_capabilities_completed,
    create_capabilities_failed,
    create_generate_intelligence_completed,
    create_generate_intelligence_failed,
    create_health_completed,
    create_health_failed,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class BridgeIntelligenceHandler(BaseResponsePublisher):
    """
    Handle bridge intelligence events and orchestrate Bridge service operations.

    Event Flow:
        1. Consume bridge intelligence request events
        2. Call appropriate Bridge service HTTP endpoint
        3. Publish COMPLETED (success) or FAILED (error) response

    Topics:
        - Generate Intelligence:
            - Request: dev.archon-intelligence.bridge.generate-intelligence-requested.v1
            - Completed: dev.archon-intelligence.bridge.generate-intelligence-completed.v1
            - Failed: dev.archon-intelligence.bridge.generate-intelligence-failed.v1
        - Health Check:
            - Request: dev.archon-intelligence.bridge.bridge-health-requested.v1
            - Completed: dev.archon-intelligence.bridge.bridge-health-completed.v1
            - Failed: dev.archon-intelligence.bridge.bridge-health-failed.v1
        - Capabilities:
            - Request: dev.archon-intelligence.bridge.capabilities-requested.v1
            - Completed: dev.archon-intelligence.bridge.capabilities-completed.v1
            - Failed: dev.archon-intelligence.bridge.capabilities-failed.v1

    Service Integration:
        - Bridge (8054): Metadata generation, health checks, capabilities
    """

    # Topic constants
    GENERATE_INTELLIGENCE_REQUEST_TOPIC = (
        "dev.archon-intelligence.bridge.generate-intelligence-requested.v1"
    )
    GENERATE_INTELLIGENCE_COMPLETED_TOPIC = (
        "dev.archon-intelligence.bridge.generate-intelligence-completed.v1"
    )
    GENERATE_INTELLIGENCE_FAILED_TOPIC = (
        "dev.archon-intelligence.bridge.generate-intelligence-failed.v1"
    )

    HEALTH_REQUEST_TOPIC = "dev.archon-intelligence.bridge.bridge-health-requested.v1"
    HEALTH_COMPLETED_TOPIC = "dev.archon-intelligence.bridge.bridge-health-completed.v1"
    HEALTH_FAILED_TOPIC = "dev.archon-intelligence.bridge.bridge-health-failed.v1"

    CAPABILITIES_REQUEST_TOPIC = (
        "dev.archon-intelligence.bridge.capabilities-requested.v1"
    )
    CAPABILITIES_COMPLETED_TOPIC = (
        "dev.archon-intelligence.bridge.capabilities-completed.v1"
    )
    CAPABILITIES_FAILED_TOPIC = "dev.archon-intelligence.bridge.capabilities-failed.v1"

    # Service endpoints
    BRIDGE_URL = "http://localhost:8054"

    # Timeouts (in seconds)
    GENERATE_INTELLIGENCE_TIMEOUT = 30.0
    HEALTH_TIMEOUT = 5.0
    CAPABILITIES_TIMEOUT = 5.0

    def __init__(self, bridge_url: Optional[str] = None):
        """
        Initialize Bridge Intelligence handler.

        Args:
            bridge_url: Optional Bridge service URL (default: localhost:8054)
        """
        super().__init__()

        # Service URL
        self.bridge_url = bridge_url or self.BRIDGE_URL

        # HTTP client
        self.http_client: Optional[httpx.AsyncClient] = None

        # Metrics
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "generate_intelligence_successes": 0,
            "generate_intelligence_failures": 0,
            "health_check_successes": 0,
            "health_check_failures": 0,
            "capabilities_successes": 0,
            "capabilities_failures": 0,
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
            True if event type matches any bridge intelligence operation
        """
        return event_type in [
            EnumBridgeEventType.GENERATE_INTELLIGENCE_REQUESTED.value,
            "GENERATE_INTELLIGENCE_REQUESTED",
            "bridge.generate-intelligence-requested",
            EnumBridgeEventType.BRIDGE_HEALTH_REQUESTED.value,
            "BRIDGE_HEALTH_REQUESTED",
            "bridge.bridge-health-requested",
            EnumBridgeEventType.CAPABILITIES_REQUESTED.value,
            "CAPABILITIES_REQUESTED",
            "bridge.capabilities-requested",
        ]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle bridge intelligence request events.

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
                "generate-intelligence" in event_type_lower
                or "generate_intelligence" in event_type_lower
            ):
                return await self._handle_generate_intelligence(
                    correlation_id, payload, start_time
                )
            elif "bridge-health" in event_type_lower or "health" in event_type_lower:
                return await self._handle_health_check(
                    correlation_id, payload, start_time
                )
            elif "capabilities" in event_type_lower:
                return await self._handle_capabilities(
                    correlation_id, payload, start_time
                )
            else:
                logger.warning(f"Unknown bridge event type: {event_type_str}")
                return False

        except Exception as e:
            logger.error(
                f"Bridge intelligence handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_generate_intelligence(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """Handle GENERATE_INTELLIGENCE_REQUESTED event."""
        try:
            # Extract required fields
            source_path = payload.get("source_path")
            content = payload.get("content")
            language = payload.get("language")
            metadata_options = payload.get("metadata_options", {})

            # Validate required fields
            if not source_path or not content:
                logger.error(
                    f"Missing required fields in GENERATE_INTELLIGENCE_REQUESTED | correlation_id={correlation_id}"
                )
                await self._publish_generate_intelligence_failed(
                    correlation_id=correlation_id,
                    source_path=source_path or "unknown",
                    error_code=EnumBridgeErrorCode.INVALID_INPUT,
                    error_message="Missing required fields: source_path and content",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["generate_intelligence_failures"] += 1
                return False

            logger.info(
                f"Processing GENERATE_INTELLIGENCE_REQUESTED | correlation_id={correlation_id} | "
                f"source_path={source_path} | language={language} | content_length={len(content)}"
            )

            # Call Bridge service
            await self._ensure_http_client()
            response = await self.http_client.post(
                f"{self.bridge_url}/api/bridge/generate-intelligence",
                json={
                    "source_path": source_path,
                    "content": content,
                    "language": language,
                    "options": metadata_options,
                },
                timeout=self.GENERATE_INTELLIGENCE_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_generate_intelligence_completed(
                correlation_id=correlation_id,
                result=result,
                source_path=source_path,
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["generate_intelligence_successes"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"GENERATE_INTELLIGENCE_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Bridge service HTTP error: {e.response.status_code} | {e.response.text}"
            )
            await self._publish_generate_intelligence_failed(
                correlation_id=correlation_id,
                source_path=payload.get("source_path", "unknown"),
                error_code=EnumBridgeErrorCode.BRIDGE_SERVICE_UNAVAILABLE,
                error_message=f"Bridge service error: {e.response.status_code}",
                retry_allowed=True,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                error_details={
                    "status_code": e.response.status_code,
                    "detail": e.response.text,
                },
            )
            self.metrics["generate_intelligence_failures"] += 1
            return False

        except Exception as e:
            logger.error(f"Generate intelligence failed: {e}", exc_info=True)
            await self._publish_generate_intelligence_failed(
                correlation_id=correlation_id,
                source_path=payload.get("source_path", "unknown"),
                error_code=EnumBridgeErrorCode.INTERNAL_ERROR,
                error_message=f"Internal error: {str(e)}",
                retry_allowed=True,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                error_details={"exception_type": type(e).__name__},
            )
            self.metrics["generate_intelligence_failures"] += 1
            return False

    async def _handle_health_check(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """Handle BRIDGE_HEALTH_REQUESTED event."""
        try:
            include_dependencies = payload.get("include_dependencies", True)
            timeout_ms = payload.get("timeout_ms", 5000)

            logger.info(
                f"Processing BRIDGE_HEALTH_REQUESTED | correlation_id={correlation_id}"
            )

            # Call Bridge service
            await self._ensure_http_client()
            response = await self.http_client.get(
                f"{self.bridge_url}/api/bridge/health",
                params={"include_dependencies": include_dependencies},
                timeout=timeout_ms / 1000.0,
            )
            response.raise_for_status()
            health_data = response.json()

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_health_completed(
                correlation_id=correlation_id,
                health_data=health_data,
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["health_check_successes"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"BRIDGE_HEALTH_COMPLETED | correlation_id={correlation_id} | "
                f"status={health_data.get('status', 'unknown')} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            await self._publish_health_failed(
                correlation_id=correlation_id,
                error_code=EnumBridgeErrorCode.BRIDGE_SERVICE_UNAVAILABLE,
                error_message=f"Health check failed: {str(e)}",
                retry_allowed=True,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.metrics["health_check_failures"] += 1
            return False

    async def _handle_capabilities(
        self, correlation_id: UUID, payload: Dict[str, Any], start_time: float
    ) -> bool:
        """Handle CAPABILITIES_REQUESTED event."""
        try:
            include_versions = payload.get("include_versions", True)
            include_limits = payload.get("include_limits", True)

            logger.info(
                f"Processing CAPABILITIES_REQUESTED | correlation_id={correlation_id}"
            )

            # Call Bridge service
            await self._ensure_http_client()
            response = await self.http_client.get(
                f"{self.bridge_url}/api/bridge/capabilities",
                params={
                    "include_versions": include_versions,
                    "include_limits": include_limits,
                },
                timeout=self.CAPABILITIES_TIMEOUT,
            )
            response.raise_for_status()
            capabilities_data = response.json()

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_capabilities_completed(
                correlation_id=correlation_id,
                capabilities_data=capabilities_data,
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["capabilities_successes"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"CAPABILITIES_COMPLETED | correlation_id={correlation_id} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except Exception as e:
            logger.error(f"Capabilities query failed: {e}", exc_info=True)
            await self._publish_capabilities_failed(
                correlation_id=correlation_id,
                error_code=EnumBridgeErrorCode.BRIDGE_SERVICE_UNAVAILABLE,
                error_message=f"Capabilities query failed: {str(e)}",
                retry_allowed=True,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.metrics["capabilities_failures"] += 1
            return False

    async def _publish_generate_intelligence_completed(
        self,
        correlation_id: UUID,
        result: Dict[str, Any],
        source_path: str,
        processing_time_ms: float,
    ) -> None:
        """Publish GENERATE_INTELLIGENCE_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_generate_intelligence_completed(
                source_path=source_path,
                metadata=result.get("metadata", {}),
                blake3_hash=result.get("blake3_hash", ""),
                intelligence_score=result.get("intelligence_score", 0.0),
                processing_time_ms=processing_time_ms,
                correlation_id=correlation_id,
                cache_hit=result.get("cache_hit", False),
            )

            await self._router.publish(
                topic=self.GENERATE_INTELLIGENCE_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.info(
                f"Published GENERATE_INTELLIGENCE_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish completed response: {e}", exc_info=True)
            raise

    async def _publish_generate_intelligence_failed(
        self,
        correlation_id: UUID,
        source_path: str,
        error_code: EnumBridgeErrorCode,
        error_message: str,
        retry_allowed: bool,
        processing_time_ms: float,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish GENERATE_INTELLIGENCE_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_generate_intelligence_failed(
                source_path=source_path,
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
                error_details=error_details,
            )

            await self._router.publish(
                topic=self.GENERATE_INTELLIGENCE_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published GENERATE_INTELLIGENCE_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish failed response: {e}", exc_info=True)
            raise

    async def _publish_health_completed(
        self,
        correlation_id: UUID,
        health_data: Dict[str, Any],
        processing_time_ms: float,
    ) -> None:
        """Publish BRIDGE_HEALTH_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_health_completed(
                status=health_data.get("status", "unknown"),
                uptime_seconds=health_data.get("uptime_seconds", 0.0),
                version=health_data.get("version", "unknown"),
                processing_time_ms=processing_time_ms,
                correlation_id=correlation_id,
                dependencies=health_data.get("dependencies", {}),
            )

            await self._router.publish(
                topic=self.HEALTH_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.info(
                f"Published BRIDGE_HEALTH_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish health completed: {e}", exc_info=True)
            raise

    async def _publish_health_failed(
        self,
        correlation_id: UUID,
        error_code: EnumBridgeErrorCode,
        error_message: str,
        retry_allowed: bool,
        processing_time_ms: float,
    ) -> None:
        """Publish BRIDGE_HEALTH_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_health_failed(
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
            )

            await self._router.publish(
                topic=self.HEALTH_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published BRIDGE_HEALTH_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish health failed: {e}", exc_info=True)
            raise

    async def _publish_capabilities_completed(
        self,
        correlation_id: UUID,
        capabilities_data: Dict[str, Any],
        processing_time_ms: float,
    ) -> None:
        """Publish CAPABILITIES_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_capabilities_completed(
                capabilities=capabilities_data.get("capabilities", []),
                supported_languages=capabilities_data.get("supported_languages", []),
                metadata_features=capabilities_data.get("metadata_features", []),
                processing_time_ms=processing_time_ms,
                correlation_id=correlation_id,
                version_info=capabilities_data.get("version_info", {}),
                rate_limits=capabilities_data.get("rate_limits", {}),
            )

            await self._router.publish(
                topic=self.CAPABILITIES_COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.info(
                f"Published CAPABILITIES_COMPLETED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to publish capabilities completed: {e}", exc_info=True
            )
            raise

    async def _publish_capabilities_failed(
        self,
        correlation_id: UUID,
        error_code: EnumBridgeErrorCode,
        error_message: str,
        retry_allowed: bool,
        processing_time_ms: float,
    ) -> None:
        """Publish CAPABILITIES_FAILED event."""
        try:
            await self._ensure_router_initialized()

            event_envelope = create_capabilities_failed(
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
            )

            await self._router.publish(
                topic=self.CAPABILITIES_FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published CAPABILITIES_FAILED | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(f"Failed to publish capabilities failed: {e}", exc_info=True)
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

        # Return as UUID object (Pydantic will handle serialization)
        if isinstance(correlation_id, UUID):
            return correlation_id
        elif isinstance(correlation_id, str):
            return UUID(correlation_id)
        else:
            raise ValueError(f"Invalid correlation_id type: {type(correlation_id)}")

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
        return "BridgeIntelligenceHandler"

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
        logger.info("Bridge intelligence handler shutdown complete")
