"""
Track 2 Intelligence Hook System Integration for Pattern Learning Engine

Integrates pattern storage operations with PostgreSQL tracing infrastructure
for comprehensive observability and debugging.

Track: Track 3-1.2 - PostgreSQL Storage Layer (Track 2 Integration)
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

# Add hooks to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

try:
    from lib.tracing.models import ExecutionTrace, HookExecution
    from lib.tracing.postgres_client import PostgresTracingClient

    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    logging.warning(
        "Track 2 tracing not available - pattern operations won't be traced"
    )


logger = logging.getLogger(__name__)


class PatternStorageTracer:
    """
    Integration layer between Pattern Learning Engine and Track 2 Intelligence Hooks.

    Provides automatic tracing of all pattern storage operations for:
    - Performance monitoring
    - Quality tracking
    - Error analysis
    - Audit trails
    """

    def __init__(self, postgres_client: Optional["PostgresTracingClient"] = None):
        """
        Initialize pattern storage tracer.

        Args:
            postgres_client: PostgresTracingClient instance (creates new if None)
        """
        self.enabled = TRACING_AVAILABLE
        self.client = postgres_client

        if self.enabled and not self.client:
            self.client = PostgresTracingClient()

        self.logger = logging.getLogger("PatternStorageTracer")

    async def initialize(self) -> bool:
        """
        Initialize PostgreSQL tracing client.

        Returns:
            True if initialized successfully, False otherwise
        """
        if not self.enabled:
            return False

        if self.client:
            return await self.client.initialize()

        return False

    async def trace_pattern_operation(
        self,
        operation: str,
        pattern_id: Optional[UUID],
        correlation_id: UUID,
        success: bool,
        duration_ms: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UUID]:
        """
        Trace pattern storage operation.

        Args:
            operation: Operation type (insert, update, delete, query, etc.)
            pattern_id: Pattern UUID (if applicable)
            correlation_id: Correlation ID for request tracing
            success: Whether operation succeeded
            duration_ms: Operation duration in milliseconds
            metadata: Additional metadata about the operation

        Returns:
            Trace ID if successful, None otherwise
        """
        if not self.enabled or not self.client:
            return None

        try:
            # Create execution trace
            trace_id = await self.client.create_execution_trace(
                correlation_id=correlation_id,
                root_id=correlation_id,
                parent_id=None,
                session_id=uuid4(),  # Could be passed in for session tracking
                source="pattern_learning_engine",
                prompt_text=f"Pattern operation: {operation}",
                context={
                    "operation": operation,
                    "pattern_id": str(pattern_id) if pattern_id else None,
                    "duration_ms": duration_ms,
                    "metadata": metadata or {},
                },
                tags=["pattern_learning", operation],
            )

            if trace_id:
                # Complete trace immediately (synchronous operation)
                await self.client.complete_execution_trace(
                    correlation_id=correlation_id,
                    success=success,
                    error_message=metadata.get("error") if not success else None,
                    error_type="storage_error" if not success else None,
                )

            return trace_id

        except Exception as e:
            self.logger.error(f"Failed to trace pattern operation: {e}", exc_info=True)
            return None

    async def trace_pattern_usage(
        self,
        pattern_id: UUID,
        file_path: Optional[str],
        correlation_id: UUID,
        quality_before: Optional[float],
        quality_after: Optional[float],
        success: bool,
        execution_time_ms: int,
    ) -> Optional[UUID]:
        """
        Trace pattern usage event with quality metrics.

        Args:
            pattern_id: Pattern UUID
            file_path: File where pattern was used
            correlation_id: Correlation ID for tracing
            quality_before: Quality score before pattern application
            quality_after: Quality score after pattern application
            success: Whether pattern application succeeded
            execution_time_ms: Execution duration

        Returns:
            Hook execution ID if successful, None otherwise
        """
        if not self.enabled or not self.client:
            return None

        try:
            # Create execution trace
            trace_id = await self.client.create_execution_trace(
                correlation_id=correlation_id,
                root_id=correlation_id,
                parent_id=None,
                session_id=uuid4(),
                source="pattern_usage",
                prompt_text=f"Pattern usage: {pattern_id}",
                context={
                    "pattern_id": str(pattern_id),
                    "file_path": file_path,
                    "quality_before": quality_before,
                    "quality_after": quality_after,
                    "quality_improvement": (
                        (quality_after - quality_before)
                        if (quality_before and quality_after)
                        else None
                    ),
                },
                tags=["pattern_usage", "quality_tracking"],
            )

            if trace_id:
                # Record hook execution for quality check
                hook_id = await self.client.record_hook_execution(
                    trace_id=trace_id,
                    hook_type="PatternUsage",
                    hook_name="pattern_application",
                    execution_order=1,
                    tool_name="PatternApplicator",
                    file_path=file_path,
                    duration_ms=execution_time_ms,
                    status="completed" if success else "failed",
                    quality_check_performed=(
                        True if (quality_before and quality_after) else False
                    ),
                    quality_results={
                        "quality_before": quality_before,
                        "quality_after": quality_after,
                        "improvement": (
                            (quality_after - quality_before)
                            if (quality_before and quality_after)
                            else None
                        ),
                    },
                    metadata={"pattern_id": str(pattern_id), "success": success},
                )

                # Complete trace
                await self.client.complete_execution_trace(
                    correlation_id=correlation_id, success=success
                )

                return hook_id

        except Exception as e:
            self.logger.error(f"Failed to trace pattern usage: {e}", exc_info=True)
            return None

    async def trace_analytics_computation(
        self,
        period_start: datetime,
        period_end: datetime,
        pattern_id: Optional[UUID],
        correlation_id: UUID,
        result_count: int,
        computation_time_ms: float,
    ) -> Optional[UUID]:
        """
        Trace analytics computation operations.

        Args:
            period_start: Analytics period start
            period_end: Analytics period end
            pattern_id: Pattern UUID (None for global analytics)
            correlation_id: Correlation ID
            result_count: Number of results computed
            computation_time_ms: Computation duration

        Returns:
            Trace ID if successful, None otherwise
        """
        if not self.enabled or not self.client:
            return None

        try:
            trace_id = await self.client.create_execution_trace(
                correlation_id=correlation_id,
                root_id=correlation_id,
                parent_id=None,
                session_id=uuid4(),
                source="pattern_analytics",
                prompt_text=f"Analytics computation for {period_start} to {period_end}",
                context={
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "pattern_id": str(pattern_id) if pattern_id else "global",
                    "result_count": result_count,
                    "computation_time_ms": computation_time_ms,
                },
                tags=["pattern_analytics", "computation"],
            )

            if trace_id:
                await self.client.complete_execution_trace(
                    correlation_id=correlation_id, success=True
                )

            return trace_id

        except Exception as e:
            self.logger.error(
                f"Failed to trace analytics computation: {e}", exc_info=True
            )
            return None


# ============================================================================
# Global Tracer Instance
# ============================================================================

_pattern_tracer: Optional[PatternStorageTracer] = None


async def get_pattern_tracer() -> PatternStorageTracer:
    """
    Get or create global pattern storage tracer.

    Returns:
        PatternStorageTracer instance
    """
    global _pattern_tracer

    if _pattern_tracer is None:
        _pattern_tracer = PatternStorageTracer()
        await _pattern_tracer.initialize()

    return _pattern_tracer


# ============================================================================
# Convenience Functions for Effect Nodes
# ============================================================================


async def trace_operation(
    operation: str,
    pattern_id: Optional[UUID],
    correlation_id: UUID,
    success: bool,
    duration_ms: float,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Convenience function to trace pattern operations from Effect nodes.

    Usage in Effect nodes:
        >>> from track2_integration import trace_operation
        >>> await trace_operation(
        ...     operation="insert",
        ...     pattern_id=pattern_id,
        ...     correlation_id=contract.correlation_id,
        ...     success=result.success,
        ...     duration_ms=duration_ms,
        ...     metadata={"operation_details": "..."}
        ... )
    """
    tracer = await get_pattern_tracer()
    await tracer.trace_pattern_operation(
        operation=operation,
        pattern_id=pattern_id,
        correlation_id=correlation_id,
        success=success,
        duration_ms=duration_ms,
        metadata=metadata,
    )


# ============================================================================
# Example Usage
# ============================================================================


async def example_tracing():
    """Example of pattern storage tracing."""
    tracer = await get_pattern_tracer()

    # Trace a pattern insert operation
    pattern_id = uuid4()
    correlation_id = uuid4()

    trace_id = await tracer.trace_pattern_operation(
        operation="insert",
        pattern_id=pattern_id,
        correlation_id=correlation_id,
        success=True,
        duration_ms=15.3,
        metadata={
            "pattern_name": "ExamplePattern",
            "pattern_type": "code",
            "language": "python",
        },
    )

    print(f"Traced operation: {trace_id}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_tracing())
