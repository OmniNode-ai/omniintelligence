"""
PostgresPattern Effect Node - Official omnibase_core template structure
"""
import time
from typing import Dict, Any
from omnibase_core.node import NodeOmniAgentEffect
from omnibase_core.errors import ModelOnexError, CoreErrorCode

from .models import ModelPostgresPatternEffectInput, ModelPostgresPatternEffectOutput, ModelPostgresPatternEffectConfig

class NodePostgresPatternEffect(NodeOmniAgentEffect[
    ModelPostgresPatternEffectInput,
    ModelPostgresPatternEffectOutput,
    ModelPostgresPatternEffectConfig
]):
    """Effect node for postgres_pattern operations."""

    def __init__(self, config: ModelPostgresPatternEffectConfig):
        super().__init__(config)
        self.config = config
        self._request_count = 0
        self._retry_count = 0
        self._total_processing_time_ms = 0.0

    async def process(self, input_data: ModelPostgresPatternEffectInput) -> ModelPostgresPatternEffectOutput:
        """Process postgres_pattern operation with retry logic."""
        start_time = time.time()
        self._request_count += 1
        
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                result = await self._execute_operation(input_data)
                
                processing_time_ms = (time.time() - start_time) * 1000
                self._total_processing_time_ms += processing_time_ms

                return ModelPostgresPatternEffectOutput(
                    correlation_id=input_data.correlation_id,
                    processing_time_ms=processing_time_ms,
                    **result
                )
            except Exception as e:
                last_error = e
                self._retry_count += 1
                if attempt < self.config.max_retries:
                    await time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                    continue
                break
        
        processing_time_ms = (time.time() - start_time) * 1000
        raise ModelOnexError(
            code=CoreErrorCode.OPERATION_FAILED,
            message=f"{node_name} failed after {self.config.max_retries} retries: {str(last_error)}",
            cause=last_error
        )

    async def _execute_operation(self, input_data: ModelPostgresPatternEffectInput) -> Dict[str, Any]:
        """Execute the core operation."""
        # Placeholder implementation
        return {}

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            "request_count": self._request_count,
            "retry_count": self._retry_count,
            "average_processing_time_ms": self._total_processing_time_ms / max(self._request_count, 1),
        }
