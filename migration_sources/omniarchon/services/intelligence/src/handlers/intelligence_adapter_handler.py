"""
Intelligence Adapter Event Handler

Handles CODE_ANALYSIS_REQUESTED events and publishes CODE_ANALYSIS_COMPLETED/FAILED responses.
Implements the Intelligence Adapter Effect Node for event-driven code quality analysis.

Created: 2025-10-21
Purpose: Event-driven intelligence integration for real-time code quality assessment
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from src.archon_services.quality.comprehensive_onex_scorer import (
    ComprehensiveONEXScorer,
)
from src.events.hybrid_event_router import HybridEventRouter
from src.events.models.intelligence_adapter_events import (
    EnumAnalysisErrorCode,
    EnumAnalysisOperationType,
    EnumCodeAnalysisEventType,
    ModelDiscoveryPayload,
    ModelInfrastructureScanPayload,
    ModelPatternExtractionPayload,
    ModelSchemaDiscoveryPayload,
    create_completed_event,
    create_failed_event,
)
from src.handlers.base_response_publisher import BaseResponsePublisher
from src.handlers.operations.infrastructure_scan_handler import (
    InfrastructureScanHandler,
)
from src.handlers.operations.model_discovery_handler import ModelDiscoveryHandler
from src.handlers.operations.pattern_extraction_handler import PatternExtractionHandler
from src.handlers.operations.schema_discovery_handler import SchemaDiscoveryHandler

logger = logging.getLogger(__name__)


class IntelligenceAdapterHandler(BaseResponsePublisher):
    """
    Handle CODE_ANALYSIS_REQUESTED events and publish analysis results.

    This handler implements the Intelligence Adapter Effect Node pattern,
    consuming code analysis requests from the event bus and publishing
    results back.

    Event Flow:
        1. Consume CODE_ANALYSIS_REQUESTED event
        2. Extract code content, language, and operation type
        3. Perform quality analysis using ComprehensiveONEXScorer
        4. Publish CODE_ANALYSIS_COMPLETED (success) or CODE_ANALYSIS_FAILED (error)

    Topics:
        - Request: dev.archon-intelligence.intelligence.code-analysis-requested.v1
        - Completed: dev.archon-intelligence.intelligence.code-analysis-completed.v1
        - Failed: dev.archon-intelligence.intelligence.code-analysis-failed.v1
    """

    # Topic constants
    REQUEST_TOPIC = "dev.archon-intelligence.intelligence.code-analysis-requested.v1"
    COMPLETED_TOPIC = "dev.archon-intelligence.intelligence.code-analysis-completed.v1"
    FAILED_TOPIC = "dev.archon-intelligence.intelligence.code-analysis-failed.v1"

    def __init__(
        self,
        quality_scorer: Optional[ComprehensiveONEXScorer] = None,
    ):
        """
        Initialize Intelligence Adapter handler.

        Args:
            quality_scorer: Optional quality scorer instance (created if not provided)
        """
        super().__init__()
        self.quality_scorer = quality_scorer or ComprehensiveONEXScorer()

        # Initialize operation handlers for manifest_injector operations
        self.pattern_extraction_handler = PatternExtractionHandler()
        self.infrastructure_scan_handler = InfrastructureScanHandler()
        self.model_discovery_handler = ModelDiscoveryHandler()
        self.schema_discovery_handler = SchemaDiscoveryHandler()

        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "analysis_successes": 0,
            "analysis_failures": 0,
            # Operation-specific metrics
            "pattern_extraction_count": 0,
            "infrastructure_scan_count": 0,
            "model_discovery_count": 0,
            "schema_discovery_count": 0,
        }

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if event type is CODE_ANALYSIS_REQUESTED
        """
        return event_type in [
            EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value,
            "CODE_ANALYSIS_REQUESTED",
            "intelligence.code-analysis-requested",
            "omninode.intelligence.event.code_analysis_requested.v1",  # Full event type from Kafka
        ]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle CODE_ANALYSIS_REQUESTED event.

        Extracts code content from the event payload, performs quality analysis,
        and publishes the appropriate response event.

        Args:
            event: Event envelope with CODE_ANALYSIS_REQUESTED payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        correlation_id = None

        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)

            # Extract required fields from payload
            source_path = payload.get("source_path")
            content = payload.get("content")
            language = payload.get("language", "python")
            operation_type = payload.get("operation_type", "QUALITY_ASSESSMENT")
            options = payload.get("options", {})

            # Validate source_path (required for all operations)
            if not source_path:
                logger.error(
                    f"Missing source_path in CODE_ANALYSIS_REQUESTED event {correlation_id}"
                )
                await self._publish_failed_response(
                    correlation_id=correlation_id,
                    source_path="unknown",
                    operation_type=operation_type,
                    error_code=EnumAnalysisErrorCode.INVALID_INPUT,
                    error_message="Missing required field: source_path",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["events_failed"] += 1
                self.metrics["analysis_failures"] += 1
                return False

            logger.info(
                f"Processing CODE_ANALYSIS_REQUESTED | correlation_id={correlation_id} | "
                f"source_path={source_path} | language={language} | "
                f"operation_type={operation_type}"
            )

            # Route to appropriate operation handler
            operation_result = None
            if operation_type == EnumAnalysisOperationType.PATTERN_EXTRACTION.value:
                # Pattern extraction: Query Qdrant for code patterns
                operation_result = await self.pattern_extraction_handler.execute(
                    source_path=source_path,
                    options=options,
                )
                self.metrics["pattern_extraction_count"] += 1

            elif operation_type == EnumAnalysisOperationType.INFRASTRUCTURE_SCAN.value:
                # Infrastructure scan: Query PostgreSQL, Kafka, Qdrant, Docker
                operation_result = await self.infrastructure_scan_handler.execute(
                    source_path=source_path,
                    options=options,
                )
                self.metrics["infrastructure_scan_count"] += 1

            elif operation_type == EnumAnalysisOperationType.MODEL_DISCOVERY.value:
                # Model discovery: Scan file system and query Memgraph
                operation_result = await self.model_discovery_handler.execute(
                    source_path=source_path,
                    options=options,
                )
                self.metrics["model_discovery_count"] += 1

            elif operation_type == EnumAnalysisOperationType.SCHEMA_DISCOVERY.value:
                # Schema discovery: Query PostgreSQL information_schema
                operation_result = await self.schema_discovery_handler.execute(
                    source_path=source_path,
                    options=options,
                )
                self.metrics["schema_discovery_count"] += 1

            else:
                # Legacy quality assessment operations - REQUIRE CONTENT
                if not content:
                    logger.error(
                        f"Missing content for quality assessment operation | correlation_id={correlation_id} | "
                        f"operation_type={operation_type}"
                    )
                    await self._publish_failed_response(
                        correlation_id=correlation_id,
                        source_path=source_path or "unknown",
                        operation_type=operation_type,
                        error_code=EnumAnalysisErrorCode.INVALID_INPUT,
                        error_message=f"Missing required field: content for {operation_type} operation",
                        retry_allowed=False,
                        processing_time_ms=(time.perf_counter() - start_time) * 1000,
                    )
                    self.metrics["events_failed"] += 1
                    self.metrics["analysis_failures"] += 1
                    return False

                # Perform quality analysis
                operation_result = await self._analyze_code_quality(
                    content=content,
                    source_path=source_path,
                    language=language,
                    operation_type=operation_type,
                    options=options,
                )

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_operation_response(
                correlation_id=correlation_id,
                operation_result=operation_result,
                source_path=source_path,
                operation_type=operation_type,
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["analysis_successes"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            # Log completion with operation-specific details
            log_msg = (
                f"CODE_ANALYSIS_COMPLETED published | correlation_id={correlation_id} | "
                f"operation_type={operation_type} | processing_time_ms={duration_ms:.2f}"
            )
            # Add quality score for quality assessment operations
            if (
                isinstance(operation_result, dict)
                and "quality_score" in operation_result
            ):
                log_msg += (
                    f" | quality_score={operation_result.get('quality_score', 0):.2f}"
                )
            logger.info(log_msg)

            return True

        except Exception as e:
            logger.error(
                f"Intelligence adapter handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            # Publish error response
            try:
                if correlation_id:
                    # Extract payload data for error response (may not be available if early failure)
                    payload = self._get_payload(event) if event else {}
                    source_path = payload.get("source_path", "unknown")
                    operation_type = payload.get("operation_type", "QUALITY_ASSESSMENT")

                    duration_ms = (time.perf_counter() - start_time) * 1000
                    await self._publish_failed_response(
                        correlation_id=correlation_id,
                        source_path=source_path,
                        operation_type=operation_type,
                        error_code=EnumAnalysisErrorCode.INTERNAL_ERROR,
                        error_message=f"Analysis failed: {str(e)}",
                        retry_allowed=True,
                        processing_time_ms=duration_ms,
                        error_details={"exception_type": type(e).__name__},
                    )
            except Exception as publish_error:
                logger.error(
                    f"Failed to publish error response | correlation_id={correlation_id} | "
                    f"error={publish_error}",
                    exc_info=True,
                )

            self.metrics["events_failed"] += 1
            self.metrics["analysis_failures"] += 1
            return False

    async def _analyze_code_quality(
        self,
        content: str,
        source_path: str,
        language: str,
        operation_type: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze code quality using ComprehensiveONEXScorer.

        Args:
            content: Code content to analyze
            source_path: Path to the source file
            language: Programming language
            operation_type: Type of analysis operation
            options: Additional analysis options

        Returns:
            Analysis result dictionary with quality scores and metrics
        """
        try:
            # Perform quality assessment (synchronous method)
            # Note: analyze_content expects file_path, not source_path, and has no language param
            assessment = self.quality_scorer.analyze_content(
                content=content,
                file_path=source_path,
            )

            # Extract relevant metrics
            # Note: After quality score refactoring, only core metrics are available
            # Removed fields: issues, recommendations, metrics, legacy_indicators, omnibase_violations
            result = {
                "quality_score": assessment.get("quality_score", 0.0),
                "onex_compliance": assessment.get("onex_compliance_score", 0.0),
                # Optional fields (only include if present in assessment)
            }

            # Add optional fields if they exist
            if "relevance_score" in assessment:
                result["relevance_score"] = assessment["relevance_score"]
            if "architectural_era" in assessment:
                result["architectural_era"] = assessment["architectural_era"]

            return result

        except Exception as e:
            logger.error(f"Quality analysis failed: {e}", exc_info=True)
            raise

    async def _publish_operation_response(
        self,
        correlation_id: UUID,
        operation_result: Any,
        source_path: str,
        operation_type: str,
        processing_time_ms: float,
    ) -> None:
        """
        Publish CODE_ANALYSIS_COMPLETED event with operation-specific payload.

        Args:
            correlation_id: Correlation ID from request
            operation_result: Operation result (payload model or dict)
            source_path: Source file path
            operation_type: Type of operation performed
            processing_time_ms: Processing time in milliseconds
        """
        try:
            await self._ensure_router_initialized()

            # Build event envelope based on operation type
            from omnibase_core.models.events.model_event_envelope import (
                ModelEventEnvelope,
            )

            # Serialize operation result to dict
            if hasattr(operation_result, "model_dump"):
                payload_dict = operation_result.model_dump()
            elif isinstance(operation_result, dict):
                payload_dict = operation_result
            else:
                raise ValueError(
                    f"Unsupported operation result type: {type(operation_result)}"
                )

            envelope = ModelEventEnvelope(
                payload=payload_dict,
                correlation_id=correlation_id,
                source_tool="omninode-intelligence",
                metadata={
                    "event_type": "omninode.intelligence.event.code_analysis_completed.v1",
                    "service": "archon-intelligence",
                    "instance_id": "intelligence-adapter-1",
                    "operation_type": operation_type,
                    "processing_time_ms": processing_time_ms,
                },
            )

            # Publish the event
            await self._router.publish(
                topic=self.COMPLETED_TOPIC,
                event=envelope.model_dump(),
                key=str(correlation_id),
            )

            logger.info(
                f"Published CODE_ANALYSIS_COMPLETED | topic={self.COMPLETED_TOPIC} | "
                f"correlation_id={correlation_id} | operation_type={operation_type} | "
                f"processing_time_ms={processing_time_ms:.2f}"
            )

        except Exception as e:
            logger.error(f"Failed to publish operation response: {e}", exc_info=True)
            raise

    async def _publish_failed_response(
        self,
        correlation_id: UUID,
        source_path: str,
        operation_type: str,
        error_code: EnumAnalysisErrorCode,
        error_message: str,
        retry_allowed: bool = False,
        processing_time_ms: float = 0.0,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish CODE_ANALYSIS_FAILED event.

        Args:
            correlation_id: Correlation ID from request
            source_path: Source file path that failed
            operation_type: Type of analysis operation
            error_code: Error code enum value
            error_message: Human-readable error message
            retry_allowed: Whether the operation can be retried
            processing_time_ms: Time taken before failure
            error_details: Optional error context
        """
        try:
            await self._ensure_router_initialized()

            # Convert operation_type string to enum
            try:
                operation_enum = EnumAnalysisOperationType(operation_type)
            except ValueError:
                operation_enum = EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS

            # Create failed event using helper (returns ONEX-compliant envelope)
            event_envelope = create_failed_event(
                operation_type=operation_enum,
                source_path=source_path,
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
                error_details=error_details or {},
            )

            # Publish the ONEX-compliant envelope directly (no wrapper needed)
            await self._router.publish(
                topic=self.FAILED_TOPIC,
                event=event_envelope,  # Pass envelope dict directly
                key=str(correlation_id),
            )

            logger.warning(
                f"Published CODE_ANALYSIS_FAILED | topic={self.FAILED_TOPIC} | "
                f"correlation_id={correlation_id} | error_code={error_code.value} | "
                f"error_message={error_message}"
            )

        except Exception as e:
            logger.error(f"Failed to publish failed response: {e}", exc_info=True)
            raise

    def _get_correlation_id(self, event: Any) -> str:
        """
        Extract correlation ID from event.

        Args:
            event: Event object or dictionary

        Returns:
            Correlation ID as string
        """
        # Support both dict and object interfaces
        if isinstance(event, dict):
            correlation_id = event.get("correlation_id")
            if correlation_id is None:
                # Try to get from payload
                payload = event.get("payload", {})
                correlation_id = payload.get("correlation_id")
        else:
            correlation_id = getattr(event, "correlation_id", None)
            if correlation_id is None:
                # Try to get from payload
                payload = getattr(event, "payload", {})
                correlation_id = payload.get("correlation_id")

        if correlation_id is None:
            raise ValueError("Event missing correlation_id")

        return str(correlation_id)

    def _get_payload(self, event: Any) -> Dict[str, Any]:
        """
        Extract payload from event.

        Args:
            event: Event object or dictionary

        Returns:
            Payload dictionary
        """
        # Support both dict and object interfaces
        if isinstance(event, dict):
            # For dict events from Kafka, the event itself IS the payload
            # unless there's an explicit "payload" key
            payload = event.get("payload", event)
        else:
            payload = getattr(event, "payload", None)
            if payload is None:
                raise ValueError("Event missing payload")

        return payload

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "IntelligenceAdapterHandler"

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
