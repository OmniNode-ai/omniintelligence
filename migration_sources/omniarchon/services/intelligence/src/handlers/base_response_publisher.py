"""
BaseResponsePublisher Mixin for Intelligence Handlers

Provides response publishing functionality using HybridEventRouter for all
intelligence event handlers. Enables handlers to publish responses back to
omniclaude via Kafka/in-memory events.

Created: 2025-10-14
Purpose: Unified response publishing for intelligence codegen handlers
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol, Union
from uuid import UUID

from src.events.hybrid_event_router import HybridEventRouter
from src.events.models.model_routing_context import ModelRoutingContext
from src.utils.security import sanitize_correlation_id

# Note: omnibase_core removed for container compatibility
# Using standard Python exceptions instead


logger = logging.getLogger(__name__)


class EventProtocol(Protocol):
    """Protocol for event objects handled by intelligence handlers."""

    @property
    def correlation_id(self) -> Union[str, UUID]:
        """Correlation ID for tracking the event."""
        ...

    @property
    def payload(self) -> Dict[str, Any]:
        """Event payload containing request data."""
        ...


class BaseResponsePublisher:
    """
    Mixin class providing response publishing functionality for handlers.

    This mixin can be combined with any handler class to add response
    publishing capabilities using HybridEventRouter.

    Usage:
        class MyHandler(BaseEventHandler, BaseResponsePublisher):
            async def handle_event(self, event):
                result = await self.process_event(event)
                await self._publish_response(
                    correlation_id=event.correlation_id,
                    result=result,
                    response_type="analyze"
                )

    Response Topics:
        - omninode.codegen.response.analyze.v1
        - omninode.codegen.response.validate.v1
        - omninode.codegen.response.pattern.v1
        - omninode.codegen.response.mixin.v1
    """

    def __init__(self, *args, **kwargs):
        """Initialize response publisher with HybridEventRouter."""
        super().__init__(*args, **kwargs)
        self._router: Optional[HybridEventRouter] = None
        self._router_initialized = False

    async def _ensure_router_initialized(self) -> None:
        """
        Ensure HybridEventRouter is initialized.

        Raises:
            RuntimeError: If router initialization fails
        """
        if not self._router_initialized:
            try:
                if not self._router:
                    self._router = HybridEventRouter()
                await self._router.initialize()
                self._router_initialized = True
                logger.debug("HybridEventRouter initialized for response publishing")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to initialize HybridEventRouter: {str(e)}"
                ) from e

    async def _publish_response(
        self,
        correlation_id: UUID,
        result: Dict[str, Any],
        response_type: str,
        priority: str = "NORMAL",
    ) -> None:
        """
        Publish response event using HybridEventRouter.

        Args:
            correlation_id: Correlation ID from the original request
            result: Response payload (validation result, analysis result, etc.)
            response_type: Type of response (analyze, validate, pattern, mixin)
            priority: Event priority level (CRITICAL, HIGH, NORMAL, LOW)

        Raises:
            RuntimeError: If publishing fails
        """
        try:
            # Ensure router is initialized
            await self._ensure_router_initialized()

            # Construct response topic
            response_topic = f"omninode.codegen.response.{response_type}.v1"

            # Build event payload
            from src.events.models.model_event import ModelEvent

            event = ModelEvent(
                event_type="CUSTOM",  # EnumProtocolEventType.CUSTOM value
                topic=response_topic,
                correlation_id=correlation_id,
                timestamp=datetime.now(timezone.utc),
                source_service="archon-intelligence",
                source_version="1.0.0",
                payload_type=f"Codegen{response_type.capitalize()}Response",
                payload=result,
                priority=priority,
            )

            # Create routing context - responses should be persisted and cross-service
            context = ModelRoutingContext(
                requires_persistence=True,
                is_cross_service=True,
                is_test_environment=False,
                is_local_tool=False,
                priority_level=priority,
                service_name="archon-intelligence",
            )

            # Publish the event
            await self._router.publish(
                topic=response_topic,
                event=event,
                key=str(correlation_id),
                context=context,
            )

            logger.info(
                f"Published response to {response_topic}: "
                f"correlation_id={correlation_id}, "
                f"response_type={response_type}"
            )
            logger.debug(f"Response payload: {result}")

        except Exception as e:
            # Log error but don't raise - publishing failures shouldn't break handler
            logger.error(
                f"Failed to publish response: correlation_id={correlation_id}, "
                f"response_type={response_type}, error={str(e)}",
                exc_info=True,
            )
            # Optionally re-raise as RuntimeError for critical failures
            if "initialize" in str(e).lower():
                raise RuntimeError(
                    f"Critical error publishing response: {str(e)}"
                ) from e

    async def _publish_error_response(
        self,
        correlation_id: UUID,
        error_message: str,
        response_type: str,
        error_code: Optional[str] = None,
    ) -> None:
        """
        Publish error response event.

        Args:
            correlation_id: Correlation ID from the original request
            error_message: Error description
            response_type: Type of response (analyze, validate, pattern, mixin)
            error_code: Optional error code for classification

        Raises:
            RuntimeError: If publishing fails critically
        """
        error_payload = {
            "quality_score": 0.0,
            "onex_compliance_score": 0.0,
            "violations": [f"Handler error: {error_message}"],
            "warnings": [],
            "suggestions": [],
            "is_valid": False,
            "architectural_era": "unknown",
            "details": {
                "error": error_message,
                "error_code": error_code or "HANDLER_ERROR",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        try:
            await self._publish_response(
                correlation_id=correlation_id,
                result=error_payload,
                response_type=response_type,
                priority="HIGH",  # Errors are high priority
            )
            logger.error(
                f"Published error response: correlation_id={correlation_id}, "
                f"error={error_message}"
            )
        except Exception as e:
            logger.critical(
                f"Failed to publish error response: correlation_id={correlation_id}, "
                f"original_error={error_message}, publish_error={str(e)}",
                exc_info=True,
            )

    async def _shutdown_publisher(self) -> None:
        """
        Shutdown the response publisher and clean up resources.

        Should be called during handler cleanup/shutdown.
        """
        if self._router and self._router_initialized:
            try:
                await self._router.shutdown()
                logger.info("Response publisher shutdown complete")
            except Exception as e:
                logger.error(f"Error shutting down response publisher: {e}")
            finally:
                self._router_initialized = False

    def _get_correlation_id(
        self, event: Union[EventProtocol, Dict[str, Any], Any]
    ) -> str:
        """
        Extract and sanitize correlation ID from event.

        Handles different event formats (object with correlation_id attribute,
        dict with correlation_id key, or unknown). Sanitizes the correlation ID
        to prevent log injection attacks.

        Args:
            event: Event object (Protocol), dict, or any object with correlation_id

        Returns:
            Sanitized correlation ID string or "unknown" if not found/invalid

        Security:
            All correlation IDs are sanitized to prevent:
            - Log injection attacks (newlines, control characters)
            - ANSI escape code injection
            - Buffer overflow attempts (length validation)
        """
        # Extract raw correlation ID
        raw_correlation_id = None
        if hasattr(event, "correlation_id"):
            raw_correlation_id = event.correlation_id
        elif isinstance(event, dict):
            raw_correlation_id = event.get("correlation_id")

        # Sanitize before returning
        return sanitize_correlation_id(raw_correlation_id, allow_unknown=True)

    def _get_payload(
        self, event: Union[EventProtocol, Dict[str, Any], Any]
    ) -> Dict[str, Any]:
        """
        Extract payload from event.

        Handles different event formats (object with payload attribute,
        dict with payload key, or empty dict).

        Args:
            event: Event object (Protocol), dict, or any object with payload

        Returns:
            Payload dictionary
        """
        # Handle different event formats
        if hasattr(event, "payload"):
            return event.payload if isinstance(event.payload, dict) else {}
        elif isinstance(event, dict):
            return event.get("payload", {})
        else:
            return {}

    def _get_event_type(
        self, event: Union[EventProtocol, Dict[str, Any], Any]
    ) -> Optional[str]:
        """
        Extract event_type from event.

        Handles different event formats (object with event_type attribute,
        dict with event_type key, or None).

        Args:
            event: Event object (Protocol), dict, or any object with event_type

        Returns:
            Event type string or None if not found
        """
        # Handle different event formats
        if hasattr(event, "event_type"):
            return event.event_type
        elif isinstance(event, dict):
            return event.get("event_type")
        else:
            return None
