"""
Vectorization Compute Node

Generates embeddings from code and documents using OpenAI and other embedding models.
Implements the official omnibase_core COMPUTE node template structure.
"""

import time
from typing import Dict, Any
from uuid import UUID

from omnibase_core.node import NodeOmniAgentCompute
from omnibase_core.errors import ModelOnexError, CoreErrorCode

from .models import (
    ModelVectorizationComputeInput,
    ModelVectorizationComputeOutput,
    ModelVectorizationComputeConfig,
)
from .config import VectorizationComputeConfig
from .enums import EnumVectorizationOperationType
from .utils import (
    generate_cache_key,
    validate_embeddings,
    truncate_content,
)


class NodeVectorizationCompute(NodeOmniAgentCompute[
    ModelVectorizationComputeInput,
    ModelVectorizationComputeOutput,
    ModelVectorizationComputeConfig
]):
    """
    Compute node for generating embeddings.

    Capabilities:
    - Single content vectorization
    - Batch vectorization
    - Caching for performance
    - Multiple embedding models
    - Health monitoring
    """

    def __init__(self, config: ModelVectorizationComputeConfig):
        """
        Initialize vectorization compute node.

        Args:
            config: Node configuration
        """
        super().__init__(config)
        self.config = VectorizationComputeConfig(config)

        # Performance tracking
        self._request_count = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_processing_time_ms = 0.0

        # Simple in-memory cache (production should use Redis/Valkey)
        self._cache: Dict[str, tuple[list[float], float]] = {}  # key -> (embeddings, timestamp)

    async def process(self, input_data: ModelVectorizationComputeInput) -> ModelVectorizationComputeOutput:
        """
        Generate embeddings for content.

        Args:
            input_data: Vectorization input

        Returns:
            Vectorization output with embeddings

        Raises:
            ModelOnexError: If vectorization fails
        """
        start_time = time.time()
        self._request_count += 1
        cache_hit = False

        try:
            # Validate input
            self._validate_input(input_data)

            # Truncate content if needed
            content = truncate_content(
                input_data.content,
                self.config.config.max_content_length
            )

            # Check cache
            if self.config.should_cache():
                cache_key = generate_cache_key(
                    content,
                    input_data.model_name,
                    input_data.metadata
                )

                cached_result = self._get_from_cache(cache_key)
                if cached_result is not None:
                    cache_hit = True
                    self._cache_hits += 1
                    embeddings = cached_result
                else:
                    self._cache_misses += 1
                    embeddings = await self._execute_vectorization(input_data, content)
                    self._put_in_cache(cache_key, embeddings)
            else:
                embeddings = await self._execute_vectorization(input_data, content)

            # Validate embeddings
            if not validate_embeddings(embeddings):
                raise ModelOnexError(
                    code=CoreErrorCode.VALIDATION_ERROR,
                    message="Generated embeddings are invalid"
                )

            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000
            self._total_processing_time_ms += processing_time_ms

            return ModelVectorizationComputeOutput(
                success=True,
                embeddings=embeddings,
                model_used=input_data.model_name,
                metadata={
                    "content_length": len(content),
                    "original_length": len(input_data.content),
                    **input_data.metadata,
                },
                correlation_id=input_data.correlation_id,
                processing_time_ms=processing_time_ms,
                cache_hit=cache_hit,
            )

        except ModelOnexError:
            raise
        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            raise ModelOnexError(
                code=CoreErrorCode.PROCESSING_ERROR,
                message=f"Vectorization failed: {str(e)}",
                cause=e
            )

    def _validate_input(self, input_data: ModelVectorizationComputeInput) -> None:
        """Validate input data."""
        if not input_data.content or len(input_data.content.strip()) == 0:
            raise ModelOnexError(
                code=CoreErrorCode.VALIDATION_ERROR,
                message="Content cannot be empty"
            )

        if input_data.model_name not in [
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002",
        ]:
            raise ModelOnexError(
                code=CoreErrorCode.VALIDATION_ERROR,
                message=f"Unsupported model: {input_data.model_name}"
            )

    async def _execute_vectorization(
        self,
        input_data: ModelVectorizationComputeInput,
        content: str
    ) -> list[float]:
        """
        Execute actual vectorization.

        In production, this would call OpenAI API or local embedding model.
        For now, returns placeholder embeddings.

        Args:
            input_data: Input data
            content: Content to vectorize

        Returns:
            Generated embeddings
        """
        # Placeholder implementation
        # TODO: Implement actual OpenAI API call or local model inference
        embeddings = [0.0] * 1536
        return embeddings

    def _get_from_cache(self, cache_key: str) -> list[float] | None:
        """Get embeddings from cache if not expired."""
        if cache_key not in self._cache:
            return None

        embeddings, cached_at = self._cache[cache_key]

        # Check if expired
        age_seconds = time.time() - cached_at
        if age_seconds > self.config.config.cache_ttl_seconds:
            del self._cache[cache_key]
            return None

        return embeddings

    def _put_in_cache(self, cache_key: str, embeddings: list[float]) -> None:
        """Put embeddings in cache."""
        self._cache[cache_key] = (embeddings, time.time())

        # Simple cache eviction if too large
        if len(self._cache) > 10000:
            # Remove oldest entries
            sorted_keys = sorted(
                self._cache.keys(),
                key=lambda k: self._cache[k][1]
            )
            for key in sorted_keys[:1000]:
                del self._cache[key]

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics dictionary
        """
        avg_processing_time = (
            self._total_processing_time_ms / self._request_count
            if self._request_count > 0
            else 0.0
        )

        cache_hit_rate = (
            self._cache_hits / (self._cache_hits + self._cache_misses)
            if (self._cache_hits + self._cache_misses) > 0
            else 0.0
        )

        return {
            "request_count": self._request_count,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": cache_hit_rate,
            "average_processing_time_ms": avg_processing_time,
            "total_processing_time_ms": self._total_processing_time_ms,
            "cache_size": len(self._cache),
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.

        Returns:
            Health status dictionary
        """
        metrics = self.get_performance_metrics()

        # Check if performance is acceptable
        avg_time = metrics["average_processing_time_ms"]
        is_healthy = avg_time < 10000  # 10 seconds threshold

        return {
            "status": "healthy" if is_healthy else "degraded",
            "checks": {
                "average_latency": {
                    "status": "pass" if avg_time < 5000 else "warn",
                    "value_ms": avg_time,
                    "threshold_ms": 5000,
                },
                "cache_performance": {
                    "status": "pass",
                    "hit_rate": metrics["cache_hit_rate"],
                    "cache_size": metrics["cache_size"],
                },
            },
            "metrics": metrics,
        }
