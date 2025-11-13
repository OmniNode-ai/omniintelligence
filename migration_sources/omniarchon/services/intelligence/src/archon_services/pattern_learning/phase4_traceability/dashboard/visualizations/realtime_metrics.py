"""
Phase 4 Dashboard - Real-time Metrics Streaming

Real-time metrics streaming for live dashboard updates.
Supports WebSocket and Server-Sent Events (SSE).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class RealtimeMetric(BaseModel):
    """Real-time metric update."""

    metric_type: str = Field(
        ...,
        description="Type of metric (e.g., 'execution', 'feedback', 'lineage_event')",
    )

    pattern_id: Optional[UUID] = Field(
        default=None, description="Pattern ID if applicable"
    )

    pattern_name: Optional[str] = Field(
        default=None, description="Pattern name for display"
    )

    value: Any = Field(..., description="Metric value")

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Metric timestamp",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metric_type": "execution",
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_name": "api_debug_pattern",
                "value": 1,
                "metadata": {"success": True, "execution_time_ms": 450},
                "timestamp": "2025-10-02T20:30:00Z",
            }
        }
    )


class RealtimeMetricsSummary(BaseModel):
    """Summary of real-time metrics."""

    active_patterns: int = Field(default=0, description="Number of active patterns")

    total_executions_today: int = Field(default=0, description="Total executions today")

    avg_success_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Average success rate"
    )

    recent_feedback_count: int = Field(
        default=0, description="Feedback received in last hour"
    )

    recent_lineage_events: List[str] = Field(
        default_factory=list, description="Recent lineage events"
    )

    top_patterns: List[Dict[str, Any]] = Field(
        default_factory=list, description="Top performing patterns"
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Summary timestamp",
    )


class RealtimeMetricsStreamer:
    """
    Real-time metrics streaming.

    Provides live updates for dashboard through:
    - WebSocket connections
    - Server-Sent Events (SSE)
    - Polling API
    """

    def __init__(
        self,
        update_interval_seconds: int = 5,
        buffer_size: int = 100,
    ):
        """
        Initialize real-time metrics streamer.

        Args:
            update_interval_seconds: Seconds between metric updates
            buffer_size: Size of metric buffer
        """
        self.update_interval = update_interval_seconds
        self.buffer_size = buffer_size
        self.metric_buffer: List[RealtimeMetric] = []
        self.subscribers: List[asyncio.Queue] = []

        logger.info(
            f"Initialized RealtimeMetricsStreamer "
            f"(interval={update_interval_seconds}s, buffer={buffer_size})"
        )

    async def stream_metrics(
        self,
        pattern_id: Optional[UUID] = None,
        metric_types: Optional[List[str]] = None,
    ) -> AsyncGenerator[RealtimeMetric, None]:
        """
        Stream metrics in real-time.

        Args:
            pattern_id: Optional filter by pattern ID
            metric_types: Optional filter by metric types

        Yields:
            Real-time metrics as they occur
        """
        logger.info(f"Starting metric stream (pattern_id={pattern_id})")

        # Create subscriber queue
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.buffer_size)
        self.subscribers.append(queue)

        try:
            while True:
                try:
                    # Wait for metric with timeout
                    metric = await asyncio.wait_for(
                        queue.get(), timeout=self.update_interval
                    )

                    # Apply filters
                    if pattern_id and metric.pattern_id != pattern_id:
                        continue

                    if metric_types and metric.metric_type not in metric_types:
                        continue

                    yield metric

                except asyncio.TimeoutError:
                    # Send heartbeat metric
                    yield RealtimeMetric(
                        metric_type="heartbeat",
                        value={"status": "alive"},
                    )

        finally:
            # Cleanup subscriber
            if queue in self.subscribers:
                self.subscribers.remove(queue)

            logger.info("Metric stream closed")

    async def publish_metric(
        self, metric: RealtimeMetric, correlation_id: Optional[UUID] = None
    ) -> None:
        """
        Publish metric to all subscribers.

        Args:
            metric: Metric to publish
        """
        # Add to buffer
        self.metric_buffer.append(metric)
        if len(self.metric_buffer) > self.buffer_size:
            self.metric_buffer.pop(0)

        # Publish to all subscribers
        for queue in self.subscribers:
            try:
                await asyncio.wait_for(queue.put(metric), timeout=0.1)  # Don't block
            except asyncio.TimeoutError:
                logger.warning("Subscriber queue full, dropping metric")

        logger.debug(f"Published metric: {metric.metric_type}")

    async def get_metrics_summary(self) -> RealtimeMetricsSummary:
        """
        Get summary of recent metrics.

        Returns:
            Metrics summary
        """
        # This would typically query a database or cache
        # For now, return a mock summary
        summary = RealtimeMetricsSummary(
            active_patterns=42,
            total_executions_today=1250,
            avg_success_rate=0.92,
            recent_feedback_count=15,
            recent_lineage_events=[
                "pattern_derived: api_debug_v3 from api_debug_v2",
                "pattern_merged: auth_flow_v1 + auth_flow_v2",
            ],
            top_patterns=[
                {"name": "api_debug_pattern", "executions": 150, "success_rate": 0.95},
                {"name": "auth_flow_pattern", "executions": 120, "success_rate": 0.88},
                {
                    "name": "perf_optimize_pattern",
                    "executions": 95,
                    "success_rate": 0.92,
                },
            ],
        )

        return summary

    async def stream_metrics_sse(
        self,
        pattern_id: Optional[UUID] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream metrics as Server-Sent Events.

        Args:
            pattern_id: Optional filter by pattern ID

        Yields:
            SSE-formatted metric strings
        """
        async for metric in self.stream_metrics(pattern_id=pattern_id):
            # Format as SSE
            sse_data = f"data: {metric.model_dump_json()}\n\n"
            yield sse_data

    def get_recent_metrics(
        self,
        count: int = 20,
        metric_type: Optional[str] = None,
    ) -> List[RealtimeMetric]:
        """
        Get recent metrics from buffer.

        Args:
            count: Number of metrics to return
            metric_type: Optional filter by type

        Returns:
            List of recent metrics
        """
        metrics = self.metric_buffer

        # Filter by type
        if metric_type:
            metrics = [m for m in metrics if m.metric_type == metric_type]

        # Return most recent
        return metrics[-count:]

    async def simulate_metric_stream(
        self,
        duration_seconds: int = 60,
    ) -> AsyncGenerator[RealtimeMetric, None]:
        """
        Simulate metric stream for testing.

        Args:
            duration_seconds: Duration to simulate

        Yields:
            Simulated metrics
        """
        import random

        start_time = datetime.now(timezone.utc)
        pattern_names = ["api_debug", "auth_flow", "perf_optimize", "error_handler"]

        while (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() < duration_seconds:
            # Generate random metric
            metric_type = random.choice(["execution", "feedback", "lineage_event"])

            if metric_type == "execution":
                metric = RealtimeMetric(
                    metric_type="execution",
                    pattern_name=random.choice(pattern_names),
                    value=1,
                    metadata={
                        "success": random.random() > 0.1,
                        "execution_time_ms": random.randint(100, 1000),
                    },
                )
            elif metric_type == "feedback":
                metric = RealtimeMetric(
                    metric_type="feedback",
                    pattern_name=random.choice(pattern_names),
                    value=1,
                    metadata={
                        "sentiment": random.choice(["positive", "neutral", "negative"]),
                        "rating": random.randint(1, 5),
                    },
                )
            else:
                metric = RealtimeMetric(
                    metric_type="lineage_event",
                    pattern_name=random.choice(pattern_names),
                    value=1,
                    metadata={
                        "event_type": random.choice(["derived", "merged", "replaced"]),
                    },
                )

            yield metric

            # Publish to subscribers
            await self.publish_metric(metric)

            # Wait before next metric
            await asyncio.sleep(random.uniform(0.5, 2.0))


# Global instance for application use
_realtime_streamer: Optional[RealtimeMetricsStreamer] = None


def get_realtime_streamer() -> RealtimeMetricsStreamer:
    """
    Get singleton real-time metrics streamer.

    Returns:
        RealtimeMetricsStreamer instance
    """
    global _realtime_streamer

    if _realtime_streamer is None:
        _realtime_streamer = RealtimeMetricsStreamer()

    return _realtime_streamer
