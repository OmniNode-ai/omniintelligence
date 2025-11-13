"""
Codegen Pattern Handler

Handles pattern matching requests via Kafka events for autonomous code generation.
Integrates with CodegenPatternService for finding similar ONEX nodes.

Created: 2025-10-14 (MVP Day 2)
Updated: 2025-10-14 - Integrated BaseResponsePublisher for response publishing
Updated: 2025-10-15 - Integrated PatternFeedbackService for confidence scoring
Purpose: Event-driven pattern matching for omniclaude codegen workflow
"""

import logging
import time
from typing import Any, Dict, List, Optional

from src.archon_services.pattern_learning import CodegenPatternService
from src.archon_services.pattern_learning.pattern_feedback import PatternFeedbackService
from src.archon_services.performance import PerformanceBaselineService
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class CodegenPatternHandler(BaseResponsePublisher):
    """
    Handle pattern matching requests via Kafka events.

    Follows BaseEventHandler pattern from MVP plan.
    Integrates feedback loop for confidence-based pattern recommendations.
    """

    def __init__(
        self,
        pattern_service: Optional[CodegenPatternService] = None,
        feedback_service: Optional[PatternFeedbackService] = None,
        performance_baseline: Optional[PerformanceBaselineService] = None,
    ):
        """
        Initialize pattern handler.

        Integrates PerformanceBaselineService for performance tracking (Phase 5C).

        Args:
            pattern_service: Optional CodegenPatternService instance
            feedback_service: Optional PatternFeedbackService instance for confidence scoring
            performance_baseline: Optional PerformanceBaselineService instance for performance tracking
        """
        super().__init__()  # Initialize BaseResponsePublisher
        self.pattern_service = pattern_service or CodegenPatternService()
        self.feedback_service = feedback_service or PatternFeedbackService()
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
        return event_type in ["codegen.request.pattern", "pattern.match"]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle pattern matching event.

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

            node_description = payload.get("node_description")
            node_type = payload.get("node_type", "effect")
            limit = payload.get("limit", 5)
            score_threshold = payload.get("score_threshold", 0.7)

            if not node_description:
                logger.error(
                    f"No node_description in pattern matching event {correlation_id}"
                )
                await self._publish_error_response(
                    correlation_id, "Missing node_description in request"
                )
                self.metrics["events_failed"] += 1
                return False

            # Find similar nodes using pattern service
            logger.info(
                f"Pattern matching for {correlation_id}: node_type={node_type}, "
                f"description='{node_description[:50]}...'"
            )

            similar_nodes = await self.pattern_service.find_similar_nodes(
                node_description=node_description,
                node_type=node_type,
                limit=limit,
                score_threshold=score_threshold,
            )

            # Enrich patterns with feedback confidence scores
            await self._enrich_with_feedback_confidence(similar_nodes)

            # Sort by feedback confidence (highest first)
            similar_nodes.sort(
                key=lambda x: x.get("feedback_confidence", 0.0), reverse=True
            )

            # Log result with confidence info
            if similar_nodes:
                avg_confidence = sum(
                    n.get("feedback_confidence", 0.0) for n in similar_nodes
                ) / len(similar_nodes)
                logger.info(
                    f"Pattern matching complete for {correlation_id}: "
                    f"found {len(similar_nodes)} similar nodes "
                    f"(avg feedback confidence: {avg_confidence:.2%})"
                )
            else:
                logger.info(
                    f"Pattern matching complete for {correlation_id}: "
                    f"found 0 similar nodes"
                )

            # Publish response
            await self._publish_pattern_response(correlation_id, similar_nodes)

            # Phase 5C: Record performance and check for anomalies
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._record_performance_metrics(
                operation="codegen_pattern_matching",
                duration_ms=duration_ms,
                context={
                    "event_type": self._get_event_type(event),
                    "node_type": node_type,
                },
            )

            self.metrics["events_handled"] += 1
            return True

        except Exception as e:
            logger.error(f"Pattern handler failed: {e}", exc_info=True)
            try:
                correlation_id = self._get_correlation_id(event)
                await self._publish_error_response(correlation_id, str(e))
            except Exception as publish_error:
                logger.error(f"Failed to publish error response: {publish_error}")

            # Phase 5C: Record performance even on failure
            duration_ms = (time.perf_counter() - start_time) * 1000
            event_type = getattr(event, "event_type", None)
            if event_type is None and isinstance(event, dict):
                event_type = event.get("event_type")
            await self._record_performance_metrics(
                operation="codegen_pattern_matching",
                duration_ms=duration_ms,
                context={"error": str(e), "event_type": event_type or "unknown"},
            )

            self.metrics["events_failed"] += 1
            return False
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.metrics["total_processing_time_ms"] += elapsed_ms

    async def _enrich_with_feedback_confidence(
        self, similar_nodes: List[Dict[str, Any]]
    ) -> None:
        """
        Enrich pattern results with feedback confidence scores.

        Adds 'feedback_confidence' field to each node based on historical
        success rates and sample sizes from the feedback service.

        Args:
            similar_nodes: List of similar node dictionaries (modified in-place)
        """
        try:
            for node in similar_nodes:
                node_id = node.get("node_id")
                if not node_id:
                    node["feedback_confidence"] = 0.5  # Default for unknown patterns
                    continue

                # Get confidence from feedback service
                confidence = await self.feedback_service.get_pattern_confidence(node_id)
                node["feedback_confidence"] = round(confidence, 4)

                # Add pattern stats if available
                stats = self.feedback_service.get_pattern_stats(node_id)
                if stats:
                    node["feedback_stats"] = {
                        "success_rate": round(stats["success_rate"], 4),
                        "sample_size": stats["total_samples"],
                        "avg_quality_score": round(stats["avg_quality_score"], 4),
                    }

        except Exception as e:
            logger.error(
                f"Failed to enrich with feedback confidence: {e}", exc_info=True
            )
            # Don't fail the request, just log the error

    async def _record_performance_metrics(
        self, operation: str, duration_ms: float, context: Dict[str, Any]
    ) -> None:
        """
        Record performance metrics and detect anomalies.

        Phase 5C: Performance Intelligence
        Tracks handler execution time and detects performance anomalies
        using Z-score analysis (threshold: 3.0 std_devs).

        Args:
            operation: Operation name (e.g., "codegen_pattern_matching")
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

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "CodegenPatternHandler"

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

    async def _publish_pattern_response(
        self, correlation_id: str, similar_nodes: list
    ) -> None:
        """
        Publish pattern matching response back to omniclaude using HybridEventRouter.

        Args:
            correlation_id: Request correlation ID
            similar_nodes: List of similar node dictionaries
        """
        # Transform similar_nodes list into proper result format
        result = {
            "similar_nodes": similar_nodes,
            "count": len(similar_nodes),
            "avg_similarity": (
                sum(n.get("similarity_score", 0.0) for n in similar_nodes)
                / len(similar_nodes)
                if similar_nodes
                else 0.0
            ),
        }

        try:
            await super()._publish_response(
                correlation_id=correlation_id,
                result=result,
                response_type="pattern",
                priority="NORMAL",
            )
        except Exception as e:
            logger.error(
                f"Failed to publish pattern response for {correlation_id}: {e}",
                exc_info=True,
            )

    async def _publish_error_response(
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
                response_type="pattern",
                error_code="PATTERN_MATCHING_ERROR",
            )
        except Exception as e:
            logger.critical(
                f"Failed to publish pattern error response for {correlation_id}: {e}",
                exc_info=True,
            )
