"""
Distributed Tracing for MCP Document Indexing Pipeline

This module provides comprehensive distributed tracing capabilities for tracking
document flow through the entire indexing pipeline across multiple microservices.

Features:
- OpenTelemetry-compatible tracing
- Cross-service correlation
- Performance correlation analysis
- Error tracking and debugging
- Real-time trace visualization
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

try:
    from opentelemetry import baggage, trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.propagate import extract, inject
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace.status import Status, StatusCode

    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("OpenTelemetry not available - tracing disabled")

logger = logging.getLogger(__name__)


class TraceEventType(Enum):
    """Types of trace events"""

    DOCUMENT_CREATED = "document_created"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    SERVICE_CALL = "service_call"
    ERROR_OCCURRED = "error_occurred"
    PERFORMANCE_THRESHOLD = "performance_threshold"
    QUEUE_PROCESSED = "queue_processed"


@dataclass
class TraceContext:
    """Trace context for pipeline execution"""

    trace_id: str
    span_id: str
    document_id: str
    document_type: str
    correlation_id: str
    service_name: str
    operation_name: str
    started_at: datetime
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "started_at": self.started_at.isoformat()}


class PipelineTracer:
    """
    Distributed tracing system for MCP document indexing pipeline.

    Provides:
    - Cross-service trace correlation
    - Performance analytics
    - Error debugging
    - Real-time monitoring
    """

    def __init__(self, service_name: str, jaeger_endpoint: Optional[str] = None):
        self.service_name = service_name
        self.tracer = None
        self.traces: dict[str, list[dict[str, Any]]] = {}
        self.max_traces = 10000

        if TRACING_AVAILABLE and jaeger_endpoint:
            self._setup_tracing(jaeger_endpoint)
        else:
            logger.info("Using in-memory tracing fallback")

    def _setup_tracing(self, jaeger_endpoint: str):
        """Setup OpenTelemetry tracing with Jaeger"""
        try:
            # Configure tracer provider
            trace.set_tracer_provider(TracerProvider())

            # Configure Jaeger exporter
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_endpoint.split("://")[1].split(":")[0],
                agent_port=int(jaeger_endpoint.split(":")[-1]),
                collector_endpoint=f"{jaeger_endpoint}/api/traces",
            )

            # Add span processor
            span_processor = BatchSpanProcessor(jaeger_exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)

            # Get tracer
            self.tracer = trace.get_tracer(self.service_name)

            logger.info(
                f"Tracing configured for {self.service_name} -> {jaeger_endpoint}"
            )

        except Exception as e:
            logger.error(f"Failed to setup tracing: {e}")
            self.tracer = None

    def start_pipeline_trace(
        self,
        document_id: str,
        document_type: str,
        operation: str = "document_indexing",
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Start a new pipeline trace"""
        correlation_id = str(uuid.uuid4())

        if self.tracer:
            # OpenTelemetry trace
            with self.tracer.start_as_current_span(
                f"pipeline_{operation}",
                attributes={
                    "service.name": self.service_name,
                    "document.id": document_id,
                    "document.type": document_type,
                    "pipeline.correlation_id": correlation_id,
                    "pipeline.operation": operation,
                },
            ) as span:
                span.set_attribute("pipeline.started_at", datetime.now().isoformat())
                if metadata:
                    for key, value in metadata.items():
                        span.set_attribute(f"metadata.{key}", str(value))

        # In-memory fallback trace
        trace_data = {
            "trace_id": correlation_id,
            "document_id": document_id,
            "document_type": document_type,
            "operation": operation,
            "service": self.service_name,
            "started_at": datetime.now().isoformat(),
            "events": [],
            "metadata": metadata or {},
        }

        self.traces[correlation_id] = [trace_data]

        # Cleanup old traces
        if len(self.traces) > self.max_traces:
            old_traces = list(self.traces.keys())[: -self.max_traces]
            for old_trace in old_traces:
                del self.traces[old_trace]

        logger.info(
            f"Started pipeline trace {correlation_id} for document {document_id}"
        )
        return correlation_id

    @asynccontextmanager
    async def trace_stage(
        self,
        correlation_id: str,
        stage_name: str,
        service_name: str,
        operation: str = "process",
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Context manager for tracing a pipeline stage"""
        start_time = time.time()
        stage_span_id = str(uuid.uuid4())

        # Add to trace events
        event_data = {
            "event_type": TraceEventType.STAGE_STARTED.value,
            "stage_name": stage_name,
            "service_name": service_name,
            "operation": operation,
            "span_id": stage_span_id,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        if correlation_id in self.traces:
            self.traces[correlation_id].append(event_data)

        if self.tracer:
            with self.tracer.start_as_current_span(
                f"{stage_name}_{operation}",
                attributes={
                    "service.name": service_name,
                    "stage.name": stage_name,
                    "stage.operation": operation,
                    "pipeline.correlation_id": correlation_id,
                    "span.id": stage_span_id,
                },
            ) as span:
                try:
                    yield TraceContext(
                        trace_id=correlation_id,
                        span_id=stage_span_id,
                        document_id="",  # Would be filled from pipeline context
                        document_type="",
                        correlation_id=correlation_id,
                        service_name=service_name,
                        operation_name=operation,
                        started_at=datetime.now(),
                        metadata=metadata or {},
                    )

                    # Success
                    duration = time.time() - start_time
                    span.set_attribute("stage.duration_seconds", duration)
                    span.set_status(Status(StatusCode.OK))

                    # Add completion event
                    completion_event = {
                        "event_type": TraceEventType.STAGE_COMPLETED.value,
                        "stage_name": stage_name,
                        "service_name": service_name,
                        "span_id": stage_span_id,
                        "duration_seconds": duration,
                        "timestamp": datetime.now().isoformat(),
                        "status": "success",
                    }

                    if correlation_id in self.traces:
                        self.traces[correlation_id].append(completion_event)

                except Exception as e:
                    # Error
                    duration = time.time() - start_time
                    span.set_attribute("stage.duration_seconds", duration)
                    span.set_attribute("error.message", str(e))
                    span.set_status(Status(StatusCode.ERROR, str(e)))

                    # Add error event
                    error_event = {
                        "event_type": TraceEventType.STAGE_FAILED.value,
                        "stage_name": stage_name,
                        "service_name": service_name,
                        "span_id": stage_span_id,
                        "duration_seconds": duration,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "timestamp": datetime.now().isoformat(),
                        "status": "error",
                    }

                    if correlation_id in self.traces:
                        self.traces[correlation_id].append(error_event)

                    raise
        else:
            # Fallback without OpenTelemetry
            try:
                yield TraceContext(
                    trace_id=correlation_id,
                    span_id=stage_span_id,
                    document_id="",
                    document_type="",
                    correlation_id=correlation_id,
                    service_name=service_name,
                    operation_name=operation,
                    started_at=datetime.now(),
                    metadata=metadata or {},
                )

                duration = time.time() - start_time
                completion_event = {
                    "event_type": TraceEventType.STAGE_COMPLETED.value,
                    "stage_name": stage_name,
                    "service_name": service_name,
                    "span_id": stage_span_id,
                    "duration_seconds": duration,
                    "timestamp": datetime.now().isoformat(),
                    "status": "success",
                }

                if correlation_id in self.traces:
                    self.traces[correlation_id].append(completion_event)

            except Exception as e:
                duration = time.time() - start_time
                error_event = {
                    "event_type": TraceEventType.STAGE_FAILED.value,
                    "stage_name": stage_name,
                    "service_name": service_name,
                    "span_id": stage_span_id,
                    "duration_seconds": duration,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "timestamp": datetime.now().isoformat(),
                    "status": "error",
                }

                if correlation_id in self.traces:
                    self.traces[correlation_id].append(error_event)

                raise

    def trace_service_call(
        self,
        correlation_id: str,
        target_service: str,
        operation: str,
        duration: float,
        status_code: int,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Trace a service-to-service call"""
        event_data = {
            "event_type": TraceEventType.SERVICE_CALL.value,
            "target_service": target_service,
            "operation": operation,
            "duration_seconds": duration,
            "status_code": status_code,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        if correlation_id in self.traces:
            self.traces[correlation_id].append(event_data)

        if self.tracer:
            with self.tracer.start_as_current_span(
                f"call_{target_service}_{operation}",
                attributes={
                    "service.name": self.service_name,
                    "target.service": target_service,
                    "call.operation": operation,
                    "call.duration_seconds": duration,
                    "call.status_code": status_code,
                    "pipeline.correlation_id": correlation_id,
                },
            ):
                pass

    def trace_performance_threshold(
        self,
        correlation_id: str,
        threshold_name: str,
        actual_value: float,
        threshold_value: float,
        unit: str = "seconds",
    ):
        """Trace performance threshold violations"""
        event_data = {
            "event_type": TraceEventType.PERFORMANCE_THRESHOLD.value,
            "threshold_name": threshold_name,
            "actual_value": actual_value,
            "threshold_value": threshold_value,
            "unit": unit,
            "exceeded": actual_value > threshold_value,
            "timestamp": datetime.now().isoformat(),
        }

        if correlation_id in self.traces:
            self.traces[correlation_id].append(event_data)

    def get_trace(self, correlation_id: str) -> Optional[list[dict[str, Any]]]:
        """Get trace data for a correlation ID"""
        return self.traces.get(correlation_id)

    def get_active_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get currently active traces"""
        all_traces = list(self.traces.values())

        # Filter to active traces (those without completion events)
        active_traces = []
        for trace_events in all_traces:
            if not trace_events:
                continue

            # Check if trace has completion event
            has_completion = any(
                event.get("event_type")
                in [
                    TraceEventType.STAGE_COMPLETED.value,
                    TraceEventType.STAGE_FAILED.value,
                ]
                for event in trace_events[1:]  # Skip initial trace data
            )

            if not has_completion:
                active_traces.append(trace_events[0])  # Return trace metadata

        return active_traces[-limit:]

    def get_trace_analytics(self, time_window_hours: int = 24) -> dict[str, Any]:
        """Get trace analytics for the specified time window"""
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)

        # Filter traces within time window
        recent_traces = []
        for trace_events in self.traces.values():
            if not trace_events:
                continue

            trace_start = datetime.fromisoformat(trace_events[0]["started_at"])
            if trace_start >= cutoff_time:
                recent_traces.append(trace_events)

        if not recent_traces:
            return {"message": "No traces in time window"}

        # Calculate analytics
        analytics = {
            "time_window_hours": time_window_hours,
            "total_traces": len(recent_traces),
            "trace_summary": self._calculate_trace_summary(recent_traces),
            "service_performance": self._calculate_service_performance(recent_traces),
            "error_analysis": self._calculate_error_analysis(recent_traces),
            "bottleneck_analysis": self._identify_bottlenecks(recent_traces),
            "throughput_analysis": self._calculate_throughput(
                recent_traces, time_window_hours
            ),
        }

        return analytics

    def _calculate_trace_summary(
        self, traces: list[list[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Calculate trace summary statistics"""
        total_duration = 0
        completed_traces = 0
        failed_traces = 0

        for trace_events in traces:
            # Calculate total duration from events
            stage_events = [e for e in trace_events[1:] if e.get("duration_seconds")]
            if stage_events:
                trace_duration = sum(e["duration_seconds"] for e in stage_events)
                total_duration += trace_duration

                # Check if trace completed successfully
                has_error = any(e.get("status") == "error" for e in stage_events)
                if has_error:
                    failed_traces += 1
                else:
                    completed_traces += 1

        success_rate = completed_traces / len(traces) if traces else 0
        avg_duration = total_duration / len(traces) if traces else 0

        return {
            "total_traces": len(traces),
            "completed_traces": completed_traces,
            "failed_traces": failed_traces,
            "success_rate": success_rate,
            "average_duration_seconds": avg_duration,
        }

    def _calculate_service_performance(
        self, traces: list[list[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Calculate performance metrics by service"""
        service_metrics = {}

        for trace_events in traces:
            for event in trace_events[1:]:
                service_name = event.get("service_name")
                if not service_name or not event.get("duration_seconds"):
                    continue

                if service_name not in service_metrics:
                    service_metrics[service_name] = {
                        "total_calls": 0,
                        "total_duration": 0,
                        "error_count": 0,
                        "durations": [],
                    }

                metrics = service_metrics[service_name]
                metrics["total_calls"] += 1
                metrics["total_duration"] += event["duration_seconds"]
                metrics["durations"].append(event["duration_seconds"])

                if event.get("status") == "error":
                    metrics["error_count"] += 1

        # Calculate derived metrics
        for service_name, metrics in service_metrics.items():
            metrics["average_duration"] = (
                metrics["total_duration"] / metrics["total_calls"]
            )
            metrics["error_rate"] = metrics["error_count"] / metrics["total_calls"]

            # Calculate percentiles
            durations = sorted(metrics["durations"])
            if durations:
                metrics["p50"] = durations[len(durations) // 2]
                metrics["p95"] = durations[int(len(durations) * 0.95)]
                metrics["p99"] = durations[int(len(durations) * 0.99)]

            # Remove raw durations to reduce memory
            del metrics["durations"]

        return service_metrics

    def _calculate_error_analysis(
        self, traces: list[list[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Analyze error patterns"""
        error_types = {}
        error_services = {}
        error_stages = {}

        for trace_events in traces:
            for event in trace_events[1:]:
                if event.get("status") == "error":
                    error_type = event.get("error_type", "unknown")
                    service_name = event.get("service_name", "unknown")
                    stage_name = event.get("stage_name", "unknown")

                    error_types[error_type] = error_types.get(error_type, 0) + 1
                    error_services[service_name] = (
                        error_services.get(service_name, 0) + 1
                    )
                    error_stages[stage_name] = error_stages.get(stage_name, 0) + 1

        return {
            "error_types": error_types,
            "error_services": error_services,
            "error_stages": error_stages,
            "total_errors": sum(error_types.values()),
        }

    def _identify_bottlenecks(
        self, traces: list[list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Identify performance bottlenecks"""
        stage_performance = {}

        for trace_events in traces:
            for event in trace_events[1:]:
                stage_name = event.get("stage_name")
                duration = event.get("duration_seconds")

                if not stage_name or not duration:
                    continue

                if stage_name not in stage_performance:
                    stage_performance[stage_name] = []

                stage_performance[stage_name].append(duration)

        # Calculate bottlenecks
        bottlenecks = []
        for stage_name, durations in stage_performance.items():
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)

            if avg_duration > 5.0 or max_duration > 30.0:  # Thresholds
                bottlenecks.append(
                    {
                        "stage": stage_name,
                        "average_duration": avg_duration,
                        "max_duration": max_duration,
                        "sample_count": len(durations),
                        "severity": "high" if avg_duration > 10.0 else "medium",
                    }
                )

        return sorted(bottlenecks, key=lambda x: x["average_duration"], reverse=True)

    def _calculate_throughput(
        self, traces: list[list[dict[str, Any]]], time_window_hours: int
    ) -> dict[str, Any]:
        """Calculate throughput metrics"""
        traces_per_hour = (
            len(traces) / time_window_hours if time_window_hours > 0 else 0
        )

        # Group by document type
        document_types = {}
        for trace_events in traces:
            doc_type = trace_events[0].get("document_type", "unknown")
            document_types[doc_type] = document_types.get(doc_type, 0) + 1

        return {
            "traces_per_hour": traces_per_hour,
            "total_traces": len(traces),
            "document_types": document_types,
        }


# Global tracer instance
pipeline_tracer = PipelineTracer("archon-pipeline")


def get_pipeline_tracer() -> PipelineTracer:
    """Get the global pipeline tracer"""
    return pipeline_tracer


def configure_tracing(service_name: str, jaeger_endpoint: Optional[str] = None):
    """Configure distributed tracing"""
    global pipeline_tracer
    pipeline_tracer = PipelineTracer(service_name, jaeger_endpoint)
    return pipeline_tracer
