"""Handler for CODE_ANALYSIS_REQUESTED events.

This handler implements ProtocolMessageHandler for processing code analysis
request events. It receives the event envelope, executes the analysis via
transform handlers, and returns ModelHandlerOutput.for_effect() with
completion or failure events.

ONEX Compliance:
- Implements ProtocolMessageHandler protocol
- Returns ModelHandlerOutput.for_effect() (no direct event publishing)
- Runtime publishes returned events

Architecture:
    1. Receive ModelEventEnvelope with ModelCodeAnalysisRequestPayload
    2. Extract correlation_id and payload from envelope
    3. Execute analysis using existing transform handlers
    4. Build completion/failure event payload
    5. Return ModelHandlerOutput.for_effect(events=(...))
    6. Runtime publishes the events
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from omnibase_core.enums.enum_execution_shape import EnumMessageCategory
from omnibase_core.enums.enum_node_kind import EnumNodeKind
from omnibase_core.models.dispatch.model_handler_output import ModelHandlerOutput
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

from omniintelligence.enums.enum_code_analysis import (
    EnumAnalysisErrorCode,
    EnumAnalysisOperationType,
    EnumCodeAnalysisEventType,
)
from omniintelligence.models.events import (
    ModelCodeAnalysisCompletedPayload,
    ModelCodeAnalysisFailedPayload,
    ModelCodeAnalysisRequestPayload,
)

# Import existing transform handlers
from omniintelligence.nodes.intelligence_adapter.handlers.handler_transform_pattern import (
    transform_pattern_response,
)
from omniintelligence.nodes.intelligence_adapter.handlers.handler_transform_performance import (
    transform_performance_response,
)
from omniintelligence.nodes.intelligence_adapter.handlers.handler_transform_quality import (
    transform_quality_response,
)
from omniintelligence.nodes.intelligence_adapter.handlers.validation import (
    validate_handler_result,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Handler ID for registry and tracing
HANDLER_ID = "handler_code_analysis_requested"


class HandlerCodeAnalysisRequested:
    """Handler for CODE_ANALYSIS_REQUESTED events.

    Implements ProtocolMessageHandler for processing code analysis requests
    from Kafka. The handler extracts the payload, executes analysis using
    transform handlers, and returns ModelHandlerOutput.for_effect() with
    the appropriate completion or failure event.

    The runtime is responsible for:
    - Subscribing to the CODE_ANALYSIS_REQUESTED topic
    - Deserializing events into ModelEventEnvelope
    - Routing to this handler based on payload type
    - Publishing the returned events

    This handler is responsible for:
    - Extracting and validating the request payload
    - Executing the appropriate analysis operation
    - Building completion/failure event payloads
    - Returning properly structured ModelHandlerOutput

    Example:
        >>> handler = HandlerCodeAnalysisRequested()
        >>> envelope = ModelEventEnvelope(
        ...     payload=ModelCodeAnalysisRequestPayload(
        ...         content="def foo(): pass",
        ...         operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT
        ...     )
        ... )
        >>> output = await handler.handle(envelope)
        >>> assert output.node_kind == EnumNodeKind.EFFECT
        >>> assert len(output.events) == 1  # completion or failure event
    """

    @property
    def handler_id(self) -> str:
        """Unique identifier for this handler."""
        return HANDLER_ID

    @property
    def category(self) -> EnumMessageCategory:
        """Message category this handler processes."""
        return EnumMessageCategory.EVENT

    @property
    def message_types(self) -> set[str]:
        """Specific message types this handler accepts."""
        return {"ModelCodeAnalysisRequestPayload", "CodeAnalysisRequested"}

    @property
    def node_kind(self) -> EnumNodeKind:
        """ONEX node kind this handler represents."""
        return EnumNodeKind.EFFECT

    async def handle(
        self,
        envelope: ModelEventEnvelope[Any],
    ) -> ModelHandlerOutput[None]:
        """Handle CODE_ANALYSIS_REQUESTED event.

        Processes the analysis request and returns a ModelHandlerOutput
        containing either a completion or failure event.

        Args:
            envelope: Event envelope containing ModelCodeAnalysisRequestPayload

        Returns:
            ModelHandlerOutput.for_effect() with completion/failure event
        """
        start_time = time.perf_counter()

        # Extract IDs from envelope
        input_envelope_id = envelope.envelope_id
        # correlation_id may be None, generate one if needed
        correlation_id: UUID = envelope.correlation_id or uuid4()

        try:
            # Extract and validate payload
            payload = self._extract_payload(envelope)

            logger.info(
                f"Processing CODE_ANALYSIS_REQUESTED | "
                f"correlation_id={correlation_id} | "
                f"operation_type={payload.operation_type} | "
                f"source_path={payload.source_path}"
            )

            # Execute analysis based on operation type
            result = await self._execute_analysis(payload, correlation_id)

            # Calculate processing time
            processing_time_ms = (time.perf_counter() - start_time) * 1000

            # Build completion event
            completion_payload = self._build_completion_payload(
                payload=payload,
                result=result,
                correlation_id=correlation_id,
                processing_time_ms=processing_time_ms,
            )

            # Create completion event envelope
            completion_event: ModelEventEnvelope[ModelCodeAnalysisCompletedPayload] = ModelEventEnvelope(
                envelope_id=uuid4(),
                event_type=EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED.value,
                correlation_id=correlation_id,
                causation_id=input_envelope_id,
                timestamp=datetime.now(UTC),
                payload=completion_payload,
            )

            logger.info(
                f"CODE_ANALYSIS_COMPLETED | "
                f"correlation_id={correlation_id} | "
                f"quality_score={completion_payload.quality_score} | "
                f"processing_time_ms={processing_time_ms:.2f}"
            )

            return ModelHandlerOutput.for_effect(
                input_envelope_id=input_envelope_id,
                correlation_id=correlation_id,
                handler_id=self.handler_id,
                events=(completion_event,),
                processing_time_ms=processing_time_ms,
            )

        except Exception as e:
            # Calculate processing time even on failure
            processing_time_ms = (time.perf_counter() - start_time) * 1000

            logger.error(
                f"CODE_ANALYSIS_FAILED | "
                f"correlation_id={correlation_id} | "
                f"error={e}",
                exc_info=True,
            )

            # Build failure event
            failure_payload = self._build_failure_payload(
                error=e,
                correlation_id=correlation_id,
                processing_time_ms=processing_time_ms,
            )

            # Create failure event envelope
            failure_event: ModelEventEnvelope[ModelCodeAnalysisFailedPayload] = ModelEventEnvelope(
                envelope_id=uuid4(),
                event_type=EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED.value,
                correlation_id=correlation_id,
                causation_id=input_envelope_id,
                timestamp=datetime.now(UTC),
                payload=failure_payload,
            )

            return ModelHandlerOutput.for_effect(
                input_envelope_id=input_envelope_id,
                correlation_id=correlation_id,
                handler_id=self.handler_id,
                events=(failure_event,),
                processing_time_ms=processing_time_ms,
            )

    def _extract_payload(
        self, envelope: ModelEventEnvelope[Any]
    ) -> ModelCodeAnalysisRequestPayload:
        """Extract and validate payload from envelope.

        Args:
            envelope: Event envelope

        Returns:
            Validated ModelCodeAnalysisRequestPayload

        Raises:
            ValueError: If payload is invalid
        """
        payload = envelope.payload

        # If already a model, return it
        if isinstance(payload, ModelCodeAnalysisRequestPayload):
            return payload

        # If dict, validate and convert
        if isinstance(payload, dict):
            return ModelCodeAnalysisRequestPayload.model_validate(payload)

        raise ValueError(f"Invalid payload type: {type(payload).__name__}")

    async def _execute_analysis(
        self,
        payload: ModelCodeAnalysisRequestPayload,
        correlation_id: UUID,
    ) -> dict[str, Any]:
        """Execute analysis based on operation type.

        Uses the existing transform handlers for response transformation.

        Args:
            payload: Analysis request payload
            correlation_id: Correlation ID for tracing

        Returns:
            Analysis result dictionary
        """
        operation_type = payload.operation_type or EnumAnalysisOperationType.QUALITY_ASSESSMENT

        # Build base result with content analysis
        # In a real implementation, this would call the intelligence service
        # For now, we use the transform handlers with mock data
        base_result: dict[str, Any] = {
            "success": True,
            "correlation_id": str(correlation_id),
            "source_path": payload.source_path,
            "language": payload.language,
        }

        if operation_type == EnumAnalysisOperationType.QUALITY_ASSESSMENT:
            # Transform quality response
            quality_result = transform_quality_response(base_result)
            validated = validate_handler_result(quality_result, "assess_code_quality")
            return dict(validated)

        elif operation_type == EnumAnalysisOperationType.PATTERN_DETECTION:
            # Transform pattern response
            pattern_result = transform_pattern_response(base_result)
            validated = validate_handler_result(pattern_result, "detect_patterns")
            return dict(validated)

        elif operation_type == EnumAnalysisOperationType.PERFORMANCE_ANALYSIS:
            # Transform performance response
            perf_result = transform_performance_response(base_result)
            validated = validate_handler_result(perf_result, "analyze_performance")
            return dict(validated)

        else:
            # Default to quality assessment for unknown types
            quality_result = transform_quality_response(base_result)
            validated = validate_handler_result(quality_result, "assess_code_quality")
            return dict(validated)

    def _build_completion_payload(
        self,
        payload: ModelCodeAnalysisRequestPayload,
        result: dict[str, Any],
        correlation_id: UUID,
        processing_time_ms: float,
    ) -> ModelCodeAnalysisCompletedPayload:
        """Build completion event payload.

        Args:
            payload: Original request payload
            result: Analysis result
            correlation_id: Correlation ID
            processing_time_ms: Processing time

        Returns:
            ModelCodeAnalysisCompletedPayload
        """
        return ModelCodeAnalysisCompletedPayload(
            correlation_id=str(correlation_id),
            result=result,
            source_path=payload.source_path,
            quality_score=float(result.get("quality_score", 0.0)),
            onex_compliance=float(result.get("onex_compliance_score", 0.0)),
            issues_count=int(result.get("issues_count", len(result.get("issues", [])))),
            recommendations_count=int(
                result.get("recommendations_count", len(result.get("recommendations", [])))
            ),
            processing_time_ms=processing_time_ms,
            operation_type=payload.operation_type,
            complexity_score=result.get("complexity_score"),
            maintainability_score=result.get("maintainability_score"),
            results_summary=result.get("summary", {}),
            cache_hit=result.get("cache_hit", False),
        )

    def _build_failure_payload(
        self,
        error: Exception,
        correlation_id: UUID,
        processing_time_ms: float,
    ) -> ModelCodeAnalysisFailedPayload:
        """Build failure event payload.

        Args:
            error: The exception that caused failure
            correlation_id: Correlation ID
            processing_time_ms: Processing time before failure

        Returns:
            ModelCodeAnalysisFailedPayload
        """
        # Determine error code based on exception type
        error_code = self._classify_error(error)

        return ModelCodeAnalysisFailedPayload(
            correlation_id=str(correlation_id),
            error_code=error_code.value,
            error_message=str(error),
            retry_allowed=error_code in {
                EnumAnalysisErrorCode.TIMEOUT,
                EnumAnalysisErrorCode.SERVICE_UNAVAILABLE,
            },
            processing_time_ms=processing_time_ms,
            error_details=repr(error),
            suggested_action=self._get_suggested_action(error_code),
        )

    def _classify_error(self, error: Exception) -> EnumAnalysisErrorCode:
        """Classify exception into error code.

        Args:
            error: The exception

        Returns:
            Appropriate EnumAnalysisErrorCode
        """
        error_type = type(error).__name__

        if "Timeout" in error_type or "timeout" in str(error).lower():
            return EnumAnalysisErrorCode.TIMEOUT
        if "Value" in error_type or "Validation" in error_type:
            return EnumAnalysisErrorCode.INVALID_INPUT
        if "Connection" in error_type or "Unavailable" in error_type:
            return EnumAnalysisErrorCode.SERVICE_UNAVAILABLE
        if "Service" in error_type:
            return EnumAnalysisErrorCode.SERVICE_ERROR

        return EnumAnalysisErrorCode.INTERNAL_ERROR

    def _get_suggested_action(self, error_code: EnumAnalysisErrorCode) -> str:
        """Get suggested action for error code.

        Args:
            error_code: The error code

        Returns:
            Suggested action string
        """
        suggestions = {
            EnumAnalysisErrorCode.TIMEOUT: "Retry the request or increase timeout",
            EnumAnalysisErrorCode.INVALID_INPUT: "Check input format and required fields",
            EnumAnalysisErrorCode.SERVICE_UNAVAILABLE: "Wait and retry, service may be restarting",
            EnumAnalysisErrorCode.SERVICE_ERROR: "Contact support if error persists",
            EnumAnalysisErrorCode.INTERNAL_ERROR: "Contact support with correlation_id",
            EnumAnalysisErrorCode.UNKNOWN: "Contact support with correlation_id",
        }
        return suggestions.get(error_code, "Contact support")


__all__ = ["HandlerCodeAnalysisRequested", "HANDLER_ID"]
