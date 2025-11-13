"""
Pattern Learning Event Handler

Handles pattern learning operation events and publishes COMPLETED/FAILED responses.
Implements event-driven interface for pattern matching, scoring, and analysis.

Created: 2025-10-22
Purpose: Event-driven pattern learning operations integration
"""

import logging
import os
import time
from typing import Any, Dict, Optional
from uuid import UUID

from src.events.models.pattern_learning_events import (
    EnumPatternLearningErrorCode,
    ModelCacheClearCompletedPayload,
    ModelCacheClearFailedPayload,
    ModelCacheClearRequestPayload,
    ModelCacheStatsCompletedPayload,
    ModelCacheStatsFailedPayload,
    ModelCacheStatsRequestPayload,
    ModelHealthCompletedPayload,
    ModelHealthFailedPayload,
    ModelHealthRequestPayload,
    ModelHybridScoreCompletedPayload,
    ModelHybridScoreFailedPayload,
    ModelHybridScoreRequestPayload,
    ModelMetricsCompletedPayload,
    ModelMetricsFailedPayload,
    ModelMetricsRequestPayload,
    ModelPatternMatchCompletedPayload,
    ModelPatternMatchFailedPayload,
    ModelPatternMatchRequestPayload,
    ModelSemanticAnalyzeCompletedPayload,
    ModelSemanticAnalyzeFailedPayload,
    ModelSemanticAnalyzeRequestPayload,
    PatternLearningEventHelpers,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)

# Intelligence service URL configuration
INTELLIGENCE_SERVICE_URL = os.getenv(
    "INTELLIGENCE_SERVICE_URL", "http://localhost:8053"  # Fallback for local dev only
)


class PatternLearningHandler(BaseResponsePublisher):
    """
    Handle pattern learning operation events and publish results.

    Supported Operations:
        - PATTERN_MATCH: Match patterns against query
        - HYBRID_SCORE: Calculate hybrid scoring
        - SEMANTIC_ANALYZE: Semantic analysis
        - METRICS: Get pattern learning metrics
        - CACHE_STATS: Get cache statistics
        - CACHE_CLEAR: Clear pattern cache
        - HEALTH: Health check
    """

    def __init__(self):
        """Initialize Pattern Learning handler."""
        super().__init__()
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "operations_by_type": {},
        }

    def can_handle(self, event_type: str) -> bool:
        """Check if this handler can process the given event type."""
        return any(
            keyword in event_type.lower()
            for keyword in [
                "pattern_match_requested",
                "hybrid_score_requested",
                "semantic_analyze_requested",
                "metrics_requested",
                "cache_stats_requested",
                "cache_clear_requested",
                "health_requested",
                "pattern-learning",
            ]
        )

    async def handle_event(self, event: Any) -> bool:
        """Handle pattern learning operation events."""
        start_time = time.perf_counter()
        correlation_id: Optional[UUID] = None

        try:
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)
            # Extract event_type from metadata (omnibase_core pattern)
            if isinstance(event, dict):
                metadata = event.get("metadata", {})
                event_type_str = metadata.get("event_type", event.get("event_type", ""))
            else:
                metadata = getattr(event, "metadata", {})
                event_type_str = (
                    metadata.get("event_type", "")
                    if isinstance(metadata, dict)
                    else getattr(event, "event_type", "")
                )

            # Route to appropriate operation handler
            if "pattern_match" in event_type_str.lower():
                return await self._handle_pattern_match(
                    correlation_id, payload, start_time
                )
            elif "hybrid_score" in event_type_str.lower():
                return await self._handle_hybrid_score(
                    correlation_id, payload, start_time
                )
            elif "semantic_analyze" in event_type_str.lower():
                return await self._handle_semantic_analyze(
                    correlation_id, payload, start_time
                )
            elif "metrics" in event_type_str.lower():
                return await self._handle_metrics(correlation_id, payload, start_time)
            elif "cache_stats" in event_type_str.lower():
                return await self._handle_cache_stats(
                    correlation_id, payload, start_time
                )
            elif "cache_clear" in event_type_str.lower():
                return await self._handle_cache_clear(
                    correlation_id, payload, start_time
                )
            elif "health" in event_type_str.lower():
                return await self._handle_health(correlation_id, payload, start_time)
            else:
                logger.error(
                    f"Unknown pattern learning operation type: {event_type_str}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Pattern learning handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_pattern_match(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle PATTERN_MATCH operation."""
        import httpx

        try:
            request = ModelPatternMatchRequestPayload(**payload)
            logger.info(
                f"Processing PATTERN_MATCH | correlation_id={correlation_id} | query={request.query_pattern[:50]}"
            )

            # Make HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=30.0) as client:
                request_data = {
                    "code_snippet": request.query_pattern,
                    "context": request.context or {},
                }

                response = await client.post(
                    f"{INTELLIGENCE_SERVICE_URL}/api/pattern-learning/pattern/match",
                    json=request_data,
                )
                response.raise_for_status()
                data = response.json()

            result = {
                "query_pattern": request.query_pattern,
                "matches": data.get("matches", []),
                "match_count": data.get("match_count", len(data.get("matches", []))),
                "highest_similarity": data.get("highest_similarity", 0.0),
                "cache_hit": data.get("cache_hit", False),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "pattern_match",
                correlation_id,
                ModelPatternMatchCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("pattern_match")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Pattern match HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "pattern_match",
                correlation_id,
                ModelPatternMatchFailedPayload(
                    query_pattern=payload.get("query_pattern", "unknown"),
                    error_message=f"HTTP {e.response.status_code}: {e.response.text}",
                    error_code=EnumPatternLearningErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Pattern match operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "pattern_match",
                correlation_id,
                ModelPatternMatchFailedPayload(
                    query_pattern=payload.get("query_pattern", "unknown"),
                    error_message=str(e),
                    error_code=EnumPatternLearningErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_hybrid_score(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle HYBRID_SCORE operation."""
        import httpx

        try:
            request = ModelHybridScoreRequestPayload(**payload)
            logger.info(
                f"Processing HYBRID_SCORE | correlation_id={correlation_id} | pattern_id={request.pattern_id}"
            )

            # Make HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=30.0) as client:
                request_data = {
                    "pattern_id": request.pattern_id,
                    "query": request.query,  # Changed from code_snippet to query (matches model)
                }

                response = await client.post(
                    f"{INTELLIGENCE_SERVICE_URL}/api/pattern-learning/hybrid/score",
                    json=request_data,
                )
                response.raise_for_status()
                data = response.json()

            result = {
                "pattern_id": request.pattern_id,
                "hybrid_score": data.get("hybrid_score", 0.0),
                "semantic_score": data.get("semantic_score", 0.0),
                "keyword_score": data.get("keyword_score", 0.0),
                "structural_score": data.get("structural_score", 0.0),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "hybrid_score",
                correlation_id,
                ModelHybridScoreCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("hybrid_score")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Hybrid score HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "hybrid_score",
                correlation_id,
                ModelHybridScoreFailedPayload(
                    pattern_id=payload.get("pattern_id", "unknown"),
                    error_message=f"HTTP {e.response.status_code}: {e.response.text}",
                    error_code=EnumPatternLearningErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Hybrid score operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "hybrid_score",
                correlation_id,
                ModelHybridScoreFailedPayload(
                    pattern_id=payload.get("pattern_id", "unknown"),
                    error_message=str(e),
                    error_code=EnumPatternLearningErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_semantic_analyze(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle SEMANTIC_ANALYZE operation."""
        import httpx

        try:
            request = ModelSemanticAnalyzeRequestPayload(**payload)
            logger.info(
                f"Processing SEMANTIC_ANALYZE | correlation_id={correlation_id} | text_length={len(request.text)}"
            )

            # Make HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=30.0) as client:
                request_data = {
                    "code": request.text,
                    "language": "python",  # Default language (model doesn't have language field)
                }

                response = await client.post(
                    f"{INTELLIGENCE_SERVICE_URL}/api/pattern-learning/semantic/analyze",
                    json=request_data,
                )
                response.raise_for_status()
                data = response.json()

            result = {
                "text": request.text,
                "semantic_features": data.get("semantic_features", {}),
                "embeddings": data.get("embeddings"),
                "confidence": data.get("confidence", 0.0),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "semantic_analyze",
                correlation_id,
                ModelSemanticAnalyzeCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("semantic_analyze")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Semantic analyze HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "semantic_analyze",
                correlation_id,
                ModelSemanticAnalyzeFailedPayload(
                    text_preview=payload.get("text", "")[:100],
                    error_message=f"HTTP {e.response.status_code}: {e.response.text}",
                    error_code=EnumPatternLearningErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Semantic analyze operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "semantic_analyze",
                correlation_id,
                ModelSemanticAnalyzeFailedPayload(
                    text_preview=payload.get("text", "")[:100],
                    error_message=str(e),
                    error_code=EnumPatternLearningErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_metrics(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle METRICS operation."""
        import httpx

        try:
            request = ModelMetricsRequestPayload(**payload)
            logger.info(f"Processing METRICS | correlation_id={correlation_id}")

            # Make HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{INTELLIGENCE_SERVICE_URL}/api/pattern-learning/metrics"
                )
                response.raise_for_status()
                data = response.json()

            result = {
                "total_patterns": data.get("total_patterns", 0),
                "total_matches": data.get("total_matches", 0),
                "average_similarity": data.get("average_similarity", 0.0),
                "cache_hit_rate": data.get("cache_hit_rate", 0.0),
                "breakdown": data.get("breakdown", {}),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "metrics",
                correlation_id,
                ModelMetricsCompletedPayload(**result, processing_time_ms=duration_ms),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("metrics")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Metrics HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "metrics",
                correlation_id,
                ModelMetricsFailedPayload(
                    error_message=f"HTTP {e.response.status_code}: {e.response.text}",
                    error_code=EnumPatternLearningErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Metrics operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "metrics",
                correlation_id,
                ModelMetricsFailedPayload(
                    error_message=str(e),
                    error_code=EnumPatternLearningErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_cache_stats(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle CACHE_STATS operation."""
        import httpx

        try:
            request = ModelCacheStatsRequestPayload(**payload)
            logger.info(f"Processing CACHE_STATS | correlation_id={correlation_id}")

            # Make HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{INTELLIGENCE_SERVICE_URL}/api/pattern-learning/cache/stats"
                )
                response.raise_for_status()
                data = response.json()

            result = {
                "total_entries": data.get("total_entries", 0),
                "cache_size_bytes": data.get("cache_size_bytes", 0),
                "hit_rate": data.get("hit_rate", 0.0),
                "miss_rate": data.get("miss_rate", 0.0),
                "eviction_count": data.get("eviction_count", 0),
                "entries": data.get("entries"),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "cache_stats",
                correlation_id,
                ModelCacheStatsCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("cache_stats")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Cache stats HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "cache_stats",
                correlation_id,
                ModelCacheStatsFailedPayload(
                    error_message=f"HTTP {e.response.status_code}: {e.response.text}",
                    error_code=EnumPatternLearningErrorCode.CACHE_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Cache stats operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "cache_stats",
                correlation_id,
                ModelCacheStatsFailedPayload(
                    error_message=str(e),
                    error_code=EnumPatternLearningErrorCode.CACHE_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_cache_clear(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle CACHE_CLEAR operation."""
        import httpx

        try:
            request = ModelCacheClearRequestPayload(**payload)
            logger.info(
                f"Processing CACHE_CLEAR | correlation_id={correlation_id} | pattern={request.pattern}"
            )

            # Make HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{INTELLIGENCE_SERVICE_URL}/api/pattern-learning/cache/clear"
                )
                response.raise_for_status()
                data = response.json()

            result = {
                "cleared_count": data.get("cleared_count", 0),
                "pattern": request.pattern,
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "cache_clear",
                correlation_id,
                ModelCacheClearCompletedPayload(
                    **result, processing_time_ms=duration_ms
                ),
                duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self._increment_operation_metric("cache_clear")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Cache clear HTTP error: {e.response.status_code} - {e.response.text}",
                exc_info=True,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "cache_clear",
                correlation_id,
                ModelCacheClearFailedPayload(
                    error_message=f"HTTP {e.response.status_code}: {e.response.text}",
                    error_code=EnumPatternLearningErrorCode.CACHE_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Cache clear operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "cache_clear",
                correlation_id,
                ModelCacheClearFailedPayload(
                    error_message=str(e),
                    error_code=EnumPatternLearningErrorCode.CACHE_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_health(
        self, correlation_id: UUID, payload: dict, start_time: float
    ) -> bool:
        """Handle HEALTH operation."""
        import httpx

        try:
            request = ModelHealthRequestPayload(**payload)
            logger.info(f"Processing HEALTH | correlation_id={correlation_id}")

            # Make HTTP call to intelligence service
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{INTELLIGENCE_SERVICE_URL}/api/pattern-learning/health"
                )
                response.raise_for_status()
                data = response.json()

            result = {
                "status": data.get("status", "unknown"),
                "checks": data.get("checks", {}),
                "uptime_seconds": data.get("uptime_seconds", 0.0),
            }

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed(
                "health",
                correlation_id,
                ModelHealthCompletedPayload(**result, processing_time_ms=duration_ms),
                duration_ms,
            )

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
            await self._publish_failed(
                "health",
                correlation_id,
                ModelHealthFailedPayload(
                    error_message=f"HTTP {e.response.status_code}: {e.response.text}",
                    error_code=EnumPatternLearningErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Health operation failed: {e}", exc_info=True)
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_failed(
                "health",
                correlation_id,
                ModelHealthFailedPayload(
                    error_message=str(e),
                    error_code=EnumPatternLearningErrorCode.INTERNAL_ERROR,
                    retry_allowed=True,
                    processing_time_ms=duration_ms,
                ),
                duration_ms,
            )
            self.metrics["events_failed"] += 1
            return False

    # ========================================================================
    # Publish Helper Methods
    # ========================================================================

    async def _publish_completed(
        self,
        operation: str,
        correlation_id: UUID,
        payload: Any,
        processing_time_ms: float,
    ) -> None:
        """Generic publish completed event."""
        await self._ensure_router_initialized()

        event_type = f"{operation.replace('_', '_')}_completed"
        event_envelope = PatternLearningEventHelpers.create_event_envelope(
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PatternLearningEventHelpers.get_kafka_topic(event_type)
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.info(
            f"Published PATTERN_LEARNING_{operation.upper()}_COMPLETED | correlation_id={correlation_id}"
        )

    async def _publish_failed(
        self,
        operation: str,
        correlation_id: UUID,
        payload: Any,
        processing_time_ms: float,
    ) -> None:
        """Generic publish failed event."""
        await self._ensure_router_initialized()

        event_type = f"{operation.replace('_', '_')}_failed"
        event_envelope = PatternLearningEventHelpers.create_event_envelope(
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
        )

        topic = PatternLearningEventHelpers.get_kafka_topic(event_type)
        await self._router.publish(
            topic=topic, event=event_envelope, key=str(correlation_id)
        )
        logger.warning(
            f"Published PATTERN_LEARNING_{operation.upper()}_FAILED | correlation_id={correlation_id}"
        )

    def _increment_operation_metric(self, operation: str) -> None:
        """Increment operation-specific metric."""
        if operation not in self.metrics["operations_by_type"]:
            self.metrics["operations_by_type"][operation] = 0
        self.metrics["operations_by_type"][operation] += 1

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "PatternLearningHandler"

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
