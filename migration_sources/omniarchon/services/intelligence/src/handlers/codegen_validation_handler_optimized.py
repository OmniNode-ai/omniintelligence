"""
Codegen Validation Handler - Optimized Version (MVP Phase 4 - Workflow 7)

Performance optimizations applied:
1. Concurrency semaphore to prevent system overload
2. LRU caching for repeated code validations
3. Connection pooling awareness
4. Improved error handling

Optimizations target:
- Eliminate 0% success rate at 100 concurrent requests
- Reduce p95 latency from 2006ms → <500ms
- Increase throughput by 2-3x for cached requests
- Maintain 100% success rate under load

Created: 2025-10-15
Purpose: Performance-optimized event-driven code validation
"""

import asyncio
import logging
import time
from collections import OrderedDict
from hashlib import blake2b
from typing import Any, Dict, Optional

from src.archon_services.quality import CodegenQualityService, ComprehensiveONEXScorer
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class CodegenValidationHandlerOptimized(BaseResponsePublisher):
    """
    Optimized validation handler with concurrency control and caching.

    Performance Features:
    - Semaphore-based concurrency limiting (prevents overload)
    - LRU cache for repeated validations (reduces latency)
    - Connection pool aware (prevents pool exhaustion)
    - Graceful degradation under high load
    """

    # Class-level cache for validation results (shared across instances)
    _validation_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    _cache_hits = 0
    _cache_misses = 0

    def __init__(
        self,
        quality_service: Optional[CodegenQualityService] = None,
        max_concurrent: int = 50,  # Limit concurrent operations
        cache_size: int = 1000,  # Cache up to 1000 validation results
    ):
        """
        Initialize optimized validation handler.

        Args:
            quality_service: Optional CodegenQualityService instance
            max_concurrent: Maximum concurrent validation operations (default: 50)
            cache_size: Maximum cache entries (default: 1000)
        """
        super().__init__()
        self.quality_service = quality_service or CodegenQualityService(
            quality_scorer=ComprehensiveONEXScorer()
        )

        # Concurrency control: Limit simultaneous operations
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent

        # Cache configuration
        self.cache_size = cache_size

        # Metrics
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
            "concurrent_operations_peak": 0,
            "semaphore_wait_time_ms": 0.0,
        }

        logger.info(
            f"Initialized optimized validation handler: "
            f"max_concurrent={max_concurrent}, cache_size={cache_size}"
        )

    def can_handle(self, event_type: str) -> bool:
        """Check if this handler can process the given event type."""
        return event_type in ["codegen.request.validate", "code.validate"]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle validation event with concurrency control and caching.

        Performance optimizations:
        1. Semaphore prevents overload
        2. Cache lookup before expensive validation
        3. Async I/O throughout
        """
        start = time.perf_counter()
        semaphore_wait_start = start

        try:
            # Acquire semaphore (blocks if too many concurrent operations)
            async with self.semaphore:
                semaphore_wait_time = (
                    time.perf_counter() - semaphore_wait_start
                ) * 1000
                self.metrics["semaphore_wait_time_ms"] += semaphore_wait_time

                # Track peak concurrent operations
                current_concurrent = self.max_concurrent - self.semaphore._value
                if current_concurrent > self.metrics["concurrent_operations_peak"]:
                    self.metrics["concurrent_operations_peak"] = current_concurrent

                # Extract event data
                correlation_id = self._get_correlation_id(event)
                payload = self._get_payload(event)

                code_content = payload.get("code_content")
                node_type = payload.get("node_type", "effect")
                file_path = payload.get("file_path")
                contracts = payload.get("contracts", [])

                if not code_content:
                    logger.error(
                        f"No code_content in validation event {correlation_id}"
                    )
                    await self._publish_validation_error_response(
                        correlation_id, "Missing code_content in request"
                    )
                    self.metrics["events_failed"] += 1
                    return False

                # Check cache first (optimization)
                cache_key = self._compute_cache_key(
                    code_content, node_type, file_path, contracts
                )
                cached_result = self._get_cached_result(cache_key)

                if cached_result:
                    # Cache hit!
                    self.metrics["cache_hits"] += 1
                    logger.debug(
                        f"Cache HIT for {correlation_id}: "
                        f"cache_key={cache_key[:16]}..., "
                        f"saved validation time"
                    )
                    result = cached_result
                else:
                    # Cache miss - perform validation
                    self.metrics["cache_misses"] += 1
                    logger.debug(
                        f"Cache MISS for {correlation_id}: "
                        f"cache_key={cache_key[:16]}..."
                    )

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

                    # Store in cache
                    self._cache_result(cache_key, result)

                # Log validation result
                logger.info(
                    f"Validation complete for {correlation_id}: "
                    f"is_valid={result['is_valid']}, "
                    f"quality_score={result['quality_score']:.2f}, "
                    f"onex_compliance={result['onex_compliance_score']:.2f}, "
                    f"cache_hit={cached_result is not None}"
                )

                # Publish response
                await self._publish_validation_response(correlation_id, result)

                self.metrics["events_handled"] += 1
                return True

        except Exception as e:
            logger.error(f"Validation handler failed: {e}", exc_info=True)
            try:
                correlation_id = self._get_correlation_id(event)
                await self._publish_validation_error_response(correlation_id, str(e))
            except Exception as publish_error:
                logger.error(f"Failed to publish error response: {publish_error}")
            self.metrics["events_failed"] += 1
            return False
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.metrics["total_processing_time_ms"] += elapsed_ms

    def _compute_cache_key(
        self,
        code_content: str,
        node_type: str,
        file_path: Optional[str] = None,
        contracts: Optional[list] = None,
    ) -> str:
        """
        Compute cache key for validation result.

        Uses BLAKE2b hash for fast, collision-resistant hashing.

        Args:
            code_content: Code to hash
            node_type: ONEX node type
            file_path: Optional file path (affects validation context)
            contracts: Optional contracts list (affects validation rules)

        Returns:
            Cache key (hex digest)
        """
        import json

        # Hash contracts separately for deterministic ordering
        contracts_digest = blake2b(
            json.dumps(contracts or [], sort_keys=True).encode("utf-8"),
            digest_size=16,
        ).hexdigest()

        # Combine all parameters for cache key
        cache_input = (
            f"{node_type}:{file_path or ''}:{contracts_digest}:{code_content}".encode(
                "utf-8"
            )
        )
        return blake2b(cache_input, digest_size=32).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached validation result if available.

        Args:
            cache_key: Cache key

        Returns:
            Cached result or None if not found
        """
        result = self.__class__._validation_cache.get(cache_key)
        if result is not None:
            # Mark as recently used by moving to end
            self.__class__._validation_cache.move_to_end(cache_key, last=True)
        return result

    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """
        Cache validation result with LRU eviction.

        Args:
            cache_key: Cache key
            result: Validation result to cache
        """
        cache = self.__class__._validation_cache

        # If key already exists, update and move to end
        if cache_key in cache:
            cache[cache_key] = result
            cache.move_to_end(cache_key, last=True)
            return

        # If cache is full, evict least recently used entry
        if len(cache) >= self.cache_size:
            evicted_key, _ = cache.popitem(last=False)  # Evict LRU (first item)
            logger.debug(f"Cache evicted LRU entry: {evicted_key[:16]}...")

        # Add new entry
        cache[cache_key] = result

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "CodegenValidationHandlerOptimized"

    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics including optimization stats."""
        total_events = self.metrics["events_handled"] + self.metrics["events_failed"]
        success_rate = (
            self.metrics["events_handled"] / total_events if total_events > 0 else 1.0
        )
        avg_processing_time = (
            self.metrics["total_processing_time_ms"] / total_events
            if total_events > 0
            else 0.0
        )

        total_cache_ops = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        cache_hit_rate = (
            self.metrics["cache_hits"] / total_cache_ops if total_cache_ops > 0 else 0.0
        )

        avg_semaphore_wait = (
            self.metrics["semaphore_wait_time_ms"] / total_events
            if total_events > 0
            else 0.0
        )

        return {
            **self.metrics,
            "success_rate": success_rate,
            "avg_processing_time_ms": avg_processing_time,
            "cache_hit_rate": cache_hit_rate,
            "cache_size": len(self.__class__._validation_cache),
            "max_cache_size": self.cache_size,
            "avg_semaphore_wait_ms": avg_semaphore_wait,
            "handler_name": self.get_handler_name(),
        }

    async def _publish_validation_response(
        self, correlation_id: str, result: Dict[str, Any]
    ) -> None:
        """Publish validation response back to omniclaude."""
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
        """Publish error response."""
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

    def clear_cache(self) -> int:
        """
        Clear validation cache (useful for testing/maintenance).

        Returns:
            Number of entries cleared
        """
        count = len(self.__class__._validation_cache)
        self.__class__._validation_cache.clear()
        logger.info(f"Cleared validation cache: {count} entries removed")
        return count
