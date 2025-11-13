"""
Codegen Analysis Handler

Handles PRD semantic analysis requests via Kafka events for autonomous code generation.
Integrates with CodegenLangExtractService for semantic understanding.

Created: 2025-10-14
Updated: 2025-10-14 - Integrated BaseResponsePublisher for response publishing
Purpose: Event-driven PRD analysis for omniclaude codegen workflow
"""

import logging
import time
from typing import Any, Dict

from src.archon_services.langextract import CodegenLangExtractService
from src.archon_services.performance import PerformanceBaselineService
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class CodegenAnalysisHandler(BaseResponsePublisher):
    """
    Handle PRD semantic analysis requests via Kafka events.

    Follows BaseEventHandler pattern from MVP plan.
    """

    def __init__(
        self,
        langextract_service: CodegenLangExtractService = None,
        performance_baseline: PerformanceBaselineService = None,
    ):
        """
        Initialize analysis handler.

        Uses CodegenLangExtractService to analyze PRD content for semantic
        understanding and code generation hints.
        Integrates PerformanceBaselineService for performance tracking (Phase 5C).

        Args:
            langextract_service: Optional CodegenLangExtractService instance
            performance_baseline: Optional PerformanceBaselineService instance for performance tracking
        """
        super().__init__()
        self.langextract_service = langextract_service
        self.performance_baseline = performance_baseline or PerformanceBaselineService()
        self._service_initialized = False
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "performance_anomalies": 0,
        }

    async def _ensure_service_initialized(self) -> None:
        """Ensure LangExtract service is initialized and connected."""
        if not self._service_initialized:
            if self.langextract_service is None:
                self.langextract_service = CodegenLangExtractService()

            await self.langextract_service.connect()
            self._service_initialized = True
            logger.info("CodegenAnalysisHandler: LangExtract service connected")

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if handler can process this event
        """
        return event_type in ["codegen.request.analyze", "prd.analyze"]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle PRD analysis event.

        Phase 5C: Tracks performance metrics and detects anomalies.

        Args:
            event: Event envelope with payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        try:
            # Ensure service is initialized
            await self._ensure_service_initialized()

            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)

            prd_content = payload.get("prd_content")
            analysis_type = payload.get("analysis_type", "full")
            context = payload.get("context")
            min_confidence = payload.get("min_confidence", 0.7)

            if not prd_content:
                logger.error(f"No prd_content in analysis event {correlation_id}")
                await self._publish_analysis_error_response(
                    correlation_id, "Missing prd_content in request"
                )
                self.metrics["events_failed"] += 1
                return False

            # Analyze PRD using LangExtract service
            logger.info(
                f"Analyzing PRD for {correlation_id}: type={analysis_type}, "
                f"content_length={len(prd_content)}"
            )

            result = await self.langextract_service.analyze_prd_semantics(
                prd_content=prd_content,
                analysis_type=analysis_type,
                context=context,
                min_confidence=min_confidence,
            )

            # Log analysis result
            logger.info(
                f"Analysis complete for {correlation_id}: "
                f"concepts={len(result['concepts'])}, "
                f"entities={len(result['entities'])}, "
                f"confidence={result['confidence']:.2f}"
            )

            # Publish response using BaseResponsePublisher
            await self._publish_analysis_response(correlation_id, result)

            # Phase 5C: Record performance and check for anomalies
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._record_performance_metrics(
                operation="codegen_analysis",
                duration_ms=duration_ms,
                context={
                    "event_type": self._get_event_type(event),
                    "analysis_type": analysis_type,
                },
            )

            self.metrics["events_handled"] += 1
            return True

        except Exception as e:
            logger.error(f"Analysis handler failed: {e}", exc_info=True)
            try:
                correlation_id = self._get_correlation_id(event)
                await self._publish_analysis_error_response(correlation_id, str(e))
            except Exception as publish_error:
                logger.error(f"Failed to publish error response: {publish_error}")

            # Phase 5C: Record performance even on failure
            duration_ms = (time.perf_counter() - start_time) * 1000
            context = {
                "event_type": getattr(event, "event_type", "unknown"),
                "analysis_type": locals().get("analysis_type", "unknown"),
                "error": str(e),
            }
            await self._record_performance_metrics(
                operation="codegen_analysis",
                duration_ms=duration_ms,
                context=context,
            )

            self.metrics["events_failed"] += 1
            return False
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.metrics["total_processing_time_ms"] += elapsed_ms

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "CodegenAnalysisHandler"

    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics."""
        total_events = self.metrics["events_handled"] + self.metrics["events_failed"]
        success_rate = (
            self.metrics["events_handled"] / total_events if total_events > 0 else 1.0
        )
        avg_processing_time = (
            self.metrics["total_processing_time_ms"] / total_events
            if total_events > 0
            else 0.0
        )

        return {
            **self.metrics,
            "success_rate": success_rate,
            "avg_processing_time_ms": avg_processing_time,
            "handler_name": self.get_handler_name(),
        }

    async def _record_performance_metrics(
        self, operation: str, duration_ms: float, context: Dict[str, Any]
    ) -> None:
        """
        Record performance metrics and detect anomalies.

        Phase 5C: Performance Intelligence
        Tracks handler execution time and detects performance anomalies
        using Z-score analysis (threshold: 3.0 std_devs).

        Args:
            operation: Operation name (e.g., "codegen_analysis")
            duration_ms: Operation duration in milliseconds
            context: Context dictionary with event/analysis information
        """
        try:
            # Record measurement
            await self.performance_baseline.record_measurement(
                operation=operation, duration_ms=duration_ms, context=context
            )

            # Check for anomaly
            anomaly = await self.performance_baseline.detect_performance_anomaly(
                operation=operation, current_duration_ms=duration_ms
            )

            if anomaly["anomaly_detected"]:
                logger.warning(
                    f"Performance anomaly detected in {operation}: "
                    f"duration={duration_ms:.2f}ms, "
                    f"baseline_mean={anomaly['baseline_mean']:.2f}ms, "
                    f"z_score={anomaly['z_score']:.2f}, "
                    f"deviation={anomaly['deviation_percentage']:.1f}%"
                )
                self.metrics["performance_anomalies"] += 1

        except Exception as e:
            logger.error(f"Failed to record performance metrics: {e}", exc_info=True)

    async def _publish_analysis_response(
        self, correlation_id: str, result: Dict[str, Any]
    ) -> None:
        """
        Publish analysis response back to omniclaude using HybridEventRouter.

        Args:
            correlation_id: Request correlation ID
            result: Analysis result dictionary
        """
        try:
            await self._publish_response(
                correlation_id=correlation_id,
                result=result,
                response_type="analyze",
                priority="NORMAL",
            )
        except Exception as e:
            logger.error(
                f"Failed to publish analysis response for {correlation_id}: {e}",
                exc_info=True,
            )

    async def _publish_analysis_error_response(
        self, correlation_id: str, error_message: str
    ) -> None:
        """
        Publish error response using BaseResponsePublisher.

        Args:
            correlation_id: Request correlation ID
            error_message: Error description
        """
        try:
            await super()._publish_error_response(
                correlation_id=correlation_id,
                error_message=error_message,
                response_type="analyze",
                error_code="ANALYSIS_ERROR",
            )
        except Exception as e:
            logger.critical(
                f"Failed to publish analysis error response for {correlation_id}: {e}",
                exc_info=True,
            )

    async def cleanup(self) -> None:
        """
        Cleanup handler resources.

        Closes LangExtract service connection and shuts down response publisher.
        """
        # Close LangExtract service
        if self._service_initialized and self.langextract_service:
            await self.langextract_service.close()
            self._service_initialized = False
            logger.info("CodegenAnalysisHandler: LangExtract service disconnected")

        # Shutdown response publisher
        await self._shutdown_publisher()
