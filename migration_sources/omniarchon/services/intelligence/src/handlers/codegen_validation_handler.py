"""
Codegen Validation Handler

Handles code validation requests via Kafka events for autonomous code generation.
Integrates with CodegenQualityService for ONEX compliance scoring.

Created: 2025-10-14
Updated: 2025-10-14 - Integrated ComprehensiveONEXScorer
Updated: 2025-10-14 - Integrated BaseResponsePublisher for response publishing
Updated: 2025-10-15 - Integrated PatternExtractor for autonomous pattern learning (Phase 5A)
Purpose: Event-driven code validation for omniclaude codegen workflow
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union

from src.archon_services.pattern_learning.phase5_autonomous import (
    ExtractedPattern,
    PatternExtractor,
)
from src.archon_services.performance import PerformanceBaselineService
from src.archon_services.quality import CodegenQualityService, ComprehensiveONEXScorer
from src.handlers.base_response_publisher import BaseResponsePublisher, EventProtocol

logger = logging.getLogger(__name__)


class CodegenValidationHandler(BaseResponsePublisher):
    """
    Handle code validation requests via Kafka events.

    Follows BaseEventHandler pattern from MVP plan.
    Integrates PatternExtractor for autonomous pattern learning (Phase 5A).
    """

    def __init__(
        self,
        quality_service: Optional[CodegenQualityService] = None,
        pattern_extractor: Optional[PatternExtractor] = None,
        performance_baseline: Optional[PerformanceBaselineService] = None,
    ):
        """
        Initialize validation handler.

        Now uses ComprehensiveONEXScorer with official omnibase_core validators.
        Integrates PatternExtractor for autonomous pattern discovery.
        Integrates PerformanceBaselineService for performance tracking (Phase 5C).

        Args:
            quality_service: Optional CodegenQualityService instance
            pattern_extractor: Optional PatternExtractor instance for pattern learning
            performance_baseline: Optional PerformanceBaselineService instance for performance tracking
        """
        super().__init__()  # Initialize BaseResponsePublisher mixin
        self.quality_service = quality_service or CodegenQualityService(
            quality_scorer=ComprehensiveONEXScorer()
        )
        self.pattern_extractor = pattern_extractor or PatternExtractor()
        self.performance_baseline = performance_baseline or PerformanceBaselineService()
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "patterns_extracted": 0,
            "pattern_extraction_failures": 0,
            "performance_anomalies": 0,
        }

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if handler can process this event
        """
        return event_type in ["codegen.request.validate", "code.validate"]

    async def handle_event(
        self, event: Union[EventProtocol, Dict[str, Any], Any]
    ) -> bool:
        """
        Handle validation event.

        Phase 5C: Tracks performance metrics and detects anomalies.

        Args:
            event: Event envelope with payload (Protocol, dict, or any object)

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)

            code_content = payload.get("code_content")
            node_type = payload.get("node_type", "effect")
            file_path = payload.get("file_path")
            contracts = payload.get("contracts", [])

            if not code_content:
                logger.error(f"No code_content in validation event {correlation_id}")

                # Record performance for early error path to avoid biasing baseline
                duration_ms = (time.perf_counter() - start_time) * 1000
                await self._record_performance_metrics(
                    operation="codegen_validation",
                    duration_ms=duration_ms,
                    context={
                        "event_type": getattr(event, "event_type", None),
                        "node_type": node_type,
                        "correlation_id": correlation_id,
                        "error": "missing_code_content",
                    },
                )

                await self._publish_validation_error_response(
                    correlation_id, "Missing code_content in request"
                )
                self.metrics["events_failed"] += 1
                return False

            # Validate code using quality service
            logger.info(
                f"Validating code for {correlation_id}: node_type={node_type}, "
                f"code_length={len(code_content)}"
            )

            result = await self.quality_service.validate_generated_code(
                code_content=code_content,
                node_type=node_type,
                file_path=file_path,
                contracts=contracts,
            )

            # Log validation result
            logger.info(
                f"Validation complete for {correlation_id}: "
                f"is_valid={result['is_valid']}, "
                f"quality_score={result['quality_score']:.2f}, "
                f"onex_compliance={result['onex_compliance_score']:.2f}"
            )

            # Phase 5A: Extract patterns from successful validations
            if result.get("is_valid", False):
                try:
                    patterns = await self._extract_and_store_patterns(
                        code_content=code_content,
                        validation_result=result,
                        node_type=node_type,
                        file_path=file_path,
                        correlation_id=correlation_id,
                    )
                    logger.info(
                        f"Extracted {len(patterns)} patterns from successful validation "
                        f"(correlation_id={correlation_id})"
                    )
                    self.metrics["patterns_extracted"] += len(patterns)
                except Exception as pattern_error:
                    logger.warning(
                        f"Pattern extraction failed for {correlation_id}: {pattern_error}",
                        exc_info=True,
                    )
                    self.metrics["pattern_extraction_failures"] += 1
                    # Don't fail the validation if pattern extraction fails

            # Publish response using BaseResponsePublisher
            await self._publish_validation_response(correlation_id, result)

            # Phase 5C: Record performance and check for anomalies
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._record_performance_metrics(
                operation="codegen_validation",
                duration_ms=duration_ms,
                context={
                    "event_type": getattr(event, "event_type", None),
                    "node_type": node_type,
                    "correlation_id": correlation_id,
                },
            )

            self.metrics["events_handled"] += 1
            return True

        except Exception as e:
            logger.error(f"Validation handler failed: {e}", exc_info=True)
            try:
                correlation_id = self._get_correlation_id(event)
                await self._publish_validation_error_response(correlation_id, str(e))
            except Exception as publish_error:
                logger.error(f"Failed to publish error response: {publish_error}")

            # Phase 5C: Record performance even on failure with anomaly detection
            duration_ms = (time.perf_counter() - start_time) * 1000
            # Build context defensively - some variables may not be defined
            context = {"error": str(e), "error_type": type(e).__name__}
            try:
                context["event_type"] = getattr(event, "event_type", None)
                payload = self._get_payload(event)
                context["node_type"] = payload.get("node_type", "unknown")
            except Exception:
                pass  # Use minimal context if extraction fails

            await self._record_performance_metrics(
                operation="codegen_validation", duration_ms=duration_ms, context=context
            )

            self.metrics["events_failed"] += 1
            return False
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.metrics["total_processing_time_ms"] += elapsed_ms

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "CodegenValidationHandler"

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

    async def _extract_and_store_patterns(
        self,
        code_content: str,
        validation_result: Dict[str, Any],
        node_type: str,
        file_path: Optional[str],
        correlation_id: str,
    ) -> List[ExtractedPattern]:
        """
        Extract patterns from successful validation and store for future use.

        Phase 5A: Autonomous pattern learning from validated code.
        Patterns are extracted and tracked in memory (future: PostgreSQL + Qdrant).

        Args:
            code_content: Python source code that passed validation
            validation_result: Validation result with quality scores
            node_type: Type of node (effect, compute, reducer, orchestrator)
            file_path: Optional file path for context
            correlation_id: Request correlation ID for tracking

        Returns:
            List of extracted patterns
        """
        try:
            # Extract patterns using PatternExtractor
            patterns = await self.pattern_extractor.extract_patterns(
                code=code_content,
                validation_result=validation_result,
                node_type=node_type,
                file_path=file_path,
            )

            if patterns:
                logger.debug(
                    f"Pattern extraction summary for {correlation_id}:\n"
                    f"  - Architectural: {sum(1 for p in patterns if p.pattern_category.value == 'architectural')}\n"
                    f"  - Quality: {sum(1 for p in patterns if p.pattern_category.value == 'quality')}\n"
                    f"  - Security: {sum(1 for p in patterns if p.pattern_category.value == 'security')}\n"
                    f"  - ONEX: {sum(1 for p in patterns if p.pattern_category.value == 'onex')}"
                )

                # TODO Phase 5A: Implement persistent storage
                # - Store in PostgreSQL for pattern lineage tracking
                # - Index in Qdrant for semantic pattern search
                # For now, patterns are tracked in-memory by PatternExtractor

            return patterns

        except Exception as e:
            logger.error(
                f"Pattern extraction failed for {correlation_id}: {e}",
                exc_info=True,
            )
            raise

    async def _record_performance_metrics(
        self, operation: str, duration_ms: float, context: Dict[str, Any]
    ) -> None:
        """
        Record performance metrics and detect anomalies.

        Phase 5C: Performance Intelligence
        Tracks handler execution time and detects performance anomalies
        using Z-score analysis (threshold: 3.0 std_devs).

        Args:
            operation: Operation name (e.g., "codegen_validation")
            duration_ms: Operation duration in milliseconds
            context: Context dictionary with event/node information
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

    async def _publish_validation_response(
        self, correlation_id: str, result: Dict[str, Any]
    ) -> None:
        """
        Publish validation response back to omniclaude using HybridEventRouter.

        Args:
            correlation_id: Request correlation ID
            result: Validation result dictionary
        """
        try:
            await self._publish_response(
                correlation_id=correlation_id,
                result=result,
                response_type="validate",
                priority="NORMAL",
            )
        except Exception as e:
            logger.error(
                f"Failed to publish validation response for {correlation_id}: {e}",
                exc_info=True,
            )

    async def _publish_validation_error_response(
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
                response_type="validate",
                error_code="VALIDATION_ERROR",
            )
        except Exception as e:
            logger.critical(
                f"Failed to publish validation error response for {correlation_id}: {e}",
                exc_info=True,
            )
