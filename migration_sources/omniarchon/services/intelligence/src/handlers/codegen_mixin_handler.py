"""
Codegen Mixin Handler

Handles mixin recommendation requests via Kafka events for autonomous code generation.
Integrates with CodegenPatternService for mixin analysis and recommendations.

Created: 2025-10-14 (MVP Day 2)
Updated: 2025-10-14 - Integrated BaseResponsePublisher for response publishing
Purpose: Event-driven mixin recommendation for omniclaude codegen workflow
"""

import logging
import time
from typing import Any, Dict, Optional

from src.archon_services.pattern_learning import CodegenPatternService
from src.archon_services.performance import PerformanceBaselineService
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class CodegenMixinHandler(BaseResponsePublisher):
    """
    Handle mixin recommendation requests via Kafka events.

    Follows BaseEventHandler pattern from MVP plan.
    """

    def __init__(
        self,
        pattern_service: Optional[CodegenPatternService] = None,
        performance_baseline: Optional[PerformanceBaselineService] = None,
    ):
        """
        Initialize mixin handler.

        Integrates PerformanceBaselineService for performance tracking (Phase 5C).

        Args:
            pattern_service: Optional CodegenPatternService instance
            performance_baseline: Optional PerformanceBaselineService instance for performance tracking
        """
        super().__init__()
        self.pattern_service = pattern_service or CodegenPatternService()
        self.performance_baseline = performance_baseline or PerformanceBaselineService()
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
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
        return event_type in ["codegen.request.mixin", "mixin.recommend"]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle mixin recommendation event.

        Phase 5C: Tracks performance metrics and detects anomalies.

        Args:
            event: Event envelope with payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)

            requirements = payload.get("requirements", [])
            node_type = payload.get("node_type", "effect")

            if not requirements:
                logger.error(
                    f"No requirements in mixin recommendation event {correlation_id}"
                )
                await self._publish_mixin_error_response(
                    correlation_id, "Missing requirements in request"
                )
                self.metrics["events_failed"] += 1
                return False

            # Ensure requirements is a list
            if isinstance(requirements, str):
                requirements = [requirements]

            # Recommend mixins using pattern service
            logger.info(
                f"Mixin recommendation for {correlation_id}: node_type={node_type}, "
                f"requirements_count={len(requirements)}"
            )

            recommendations = await self.pattern_service.recommend_mixins(
                requirements=requirements,
                node_type=node_type,
            )

            # Log result
            logger.info(
                f"Mixin recommendation complete for {correlation_id}: "
                f"found {len(recommendations)} recommendations"
            )

            # Publish response using BaseResponsePublisher
            await self._publish_mixin_response(correlation_id, recommendations)

            # Phase 5C: Record performance and check for anomalies
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._record_performance_metrics(
                operation="codegen_mixin_recommendation",
                duration_ms=duration_ms,
                context={
                    "event_type": self._get_event_type(event),
                    "node_type": node_type,
                },
            )

            self.metrics["events_handled"] += 1
            return True

        except Exception as e:
            logger.error(f"Mixin handler failed: {e}", exc_info=True)
            try:
                correlation_id = self._get_correlation_id(event)
                await self._publish_mixin_error_response(correlation_id, str(e))
            except Exception as publish_error:
                logger.error(f"Failed to publish error response: {publish_error}")

            # Phase 5C: Record performance even on failure
            duration_ms = (time.perf_counter() - start_time) * 1000
            context = {
                "event_type": getattr(event, "event_type", "unknown"),
                "node_type": locals().get("node_type", "unknown"),
                "error": str(e),
            }
            await self._record_performance_metrics(
                operation="codegen_mixin_recommendation",
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
        return "CodegenMixinHandler"

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
            operation: Operation name (e.g., "codegen_mixin_recommendation")
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

    async def _publish_mixin_response(
        self, correlation_id: str, recommendations: list
    ) -> None:
        """
        Publish mixin recommendation response back to omniclaude using HybridEventRouter.

        Args:
            correlation_id: Request correlation ID
            recommendations: List of mixin recommendation dictionaries
        """
        try:
            # Build result payload
            result = {
                "recommendations": recommendations,
                "count": len(recommendations),
                "avg_confidence": (
                    sum(r["confidence"] for r in recommendations) / len(recommendations)
                    if recommendations
                    else 0.0
                ),
            }

            await self._publish_response(
                correlation_id=correlation_id,
                result=result,
                response_type="mixin",
                priority="NORMAL",
            )
        except Exception as e:
            logger.error(
                f"Failed to publish mixin response for {correlation_id}: {e}",
                exc_info=True,
            )

    async def _publish_mixin_error_response(
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
                response_type="mixin",
                error_code="MIXIN_ERROR",
            )
        except Exception as e:
            logger.critical(
                f"Failed to publish mixin error response for {correlation_id}: {e}",
                exc_info=True,
            )
