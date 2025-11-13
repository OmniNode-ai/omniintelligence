"""
MCP Document Indexing Pipeline Performance Metrics

This module provides comprehensive metrics collection for the MCP document
indexing pipeline, tracking end-to-end performance across all services.

Pipeline Flow:
MCP → Server → Bridge → Intelligence → Search → Qdrant/Memgraph

Key Metrics:
- End-to-end pipeline latency (target <30 seconds)
- Individual service timing (Bridge <5s, Intelligence <10s, etc.)
- Error rates and failure patterns
- Resource utilization and bottlenecks
- Business metrics and throughput
"""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# Create dedicated registry for pipeline metrics
PIPELINE_REGISTRY = CollectorRegistry()


class PipelineStage(Enum):
    """Pipeline stages for tracking"""

    MCP_CREATION = "mcp_creation"
    BRIDGE_SYNC = "bridge_sync"
    INTELLIGENCE_PROCESSING = "intelligence_processing"
    VECTOR_EMBEDDING = "vector_embedding"
    QDRANT_INDEXING = "qdrant_indexing"
    MEMGRAPH_INDEXING = "memgraph_indexing"
    SEARCH_INDEXING = "search_indexing"
    END_TO_END = "end_to_end"


class PipelineStatus(Enum):
    """Pipeline execution status"""

    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


# Pipeline timing metrics
PIPELINE_DURATION = Histogram(
    "archon_pipeline_duration_seconds",
    "Duration of pipeline stages in seconds",
    ["stage", "document_type", "service"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0),
    registry=PIPELINE_REGISTRY,
)

PIPELINE_COUNT = Counter(
    "archon_pipeline_executions_total",
    "Total number of pipeline executions",
    ["stage", "status", "document_type", "service"],
    registry=PIPELINE_REGISTRY,
)

PIPELINE_ERRORS = Counter(
    "archon_pipeline_errors_total",
    "Total number of pipeline errors",
    ["stage", "error_type", "service"],
    registry=PIPELINE_REGISTRY,
)

# Service-specific metrics
SERVICE_LATENCY = Histogram(
    "archon_service_latency_seconds",
    "Service latency for pipeline operations",
    ["service", "operation", "document_type"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=PIPELINE_REGISTRY,
)

SERVICE_HEALTH = Gauge(
    "archon_service_health_score",
    "Service health score (0-1)",
    ["service"],
    registry=PIPELINE_REGISTRY,
)

# Queue and throughput metrics
PIPELINE_QUEUE_SIZE = Gauge(
    "archon_pipeline_queue_size",
    "Number of documents in pipeline queue",
    ["stage", "service"],
    registry=PIPELINE_REGISTRY,
)

DOCUMENTS_PROCESSED = Counter(
    "archon_documents_processed_total",
    "Total number of documents processed",
    ["document_type", "source", "service"],
    registry=PIPELINE_REGISTRY,
)

PROCESSING_RATE = Gauge(
    "archon_processing_rate_per_minute",
    "Documents processed per minute",
    ["service"],
    registry=PIPELINE_REGISTRY,
)

# Resource utilization metrics
SERVICE_RESOURCE_USAGE = Gauge(
    "archon_service_resource_usage",
    "Service resource usage metrics",
    ["service", "resource_type", "unit"],
    registry=PIPELINE_REGISTRY,
)

# Business metrics
SEARCH_INDEX_SIZE = Gauge(
    "archon_search_index_size",
    "Size of search indexes",
    ["index_type", "service"],
    registry=PIPELINE_REGISTRY,
)

VECTOR_COLLECTION_SIZE = Gauge(
    "archon_vector_collection_size",
    "Size of vector collections",
    ["collection_name", "service"],
    registry=PIPELINE_REGISTRY,
)

# SLA compliance metrics
SLA_COMPLIANCE = Gauge(
    "archon_sla_compliance_percentage",
    "SLA compliance percentage for pipeline stages",
    ["stage", "sla_type"],
    registry=PIPELINE_REGISTRY,
)


@dataclass
class PipelineExecution:
    """Tracks a single pipeline execution"""

    execution_id: str
    document_id: str
    document_type: str
    started_at: datetime
    stages: dict[str, dict[str, Any]]
    status: PipelineStatus
    metadata: dict[str, Any]

    def __post_init__(self):
        if not self.stages:
            self.stages = {}
        if not self.metadata:
            self.metadata = {}


class PipelineMetricsCollector:
    """
    Comprehensive metrics collector for MCP document indexing pipeline.

    Features:
    - End-to-end pipeline tracking
    - Service-specific performance monitoring
    - Resource utilization tracking
    - SLA compliance monitoring
    - Real-time alerting integration
    """

    def __init__(self, service_name: str = "archon-pipeline"):
        self.service_name = service_name
        self.active_executions: dict[str, PipelineExecution] = {}
        self.recent_executions: list[PipelineExecution] = []
        self.max_recent_executions = 1000
        self._background_task: Optional[asyncio.Task] = None

        # Performance thresholds (in seconds)
        self.sla_thresholds = {
            PipelineStage.MCP_CREATION: 2.0,
            PipelineStage.BRIDGE_SYNC: 5.0,
            PipelineStage.INTELLIGENCE_PROCESSING: 10.0,
            PipelineStage.VECTOR_EMBEDDING: 3.0,
            PipelineStage.QDRANT_INDEXING: 2.0,
            PipelineStage.MEMGRAPH_INDEXING: 2.0,
            PipelineStage.SEARCH_INDEXING: 2.0,
            PipelineStage.END_TO_END: 30.0,
        }

        # Start background metrics collection
        self._start_background_collection()

    def start_pipeline_execution(
        self,
        document_id: str,
        document_type: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Start tracking a new pipeline execution"""
        execution_id = str(uuid.uuid4())

        execution = PipelineExecution(
            execution_id=execution_id,
            document_id=document_id,
            document_type=document_type,
            started_at=datetime.now(),
            stages={},
            status=PipelineStatus.STARTED,
            metadata=metadata or {},
        )

        self.active_executions[execution_id] = execution

        # Record pipeline start
        PIPELINE_COUNT.labels(
            stage=PipelineStage.END_TO_END.value,
            status=PipelineStatus.STARTED.value,
            document_type=document_type,
            service=self.service_name,
        ).inc()

        logger.info(
            f"Started pipeline execution {execution_id} for document {document_id}"
        )
        return execution_id

    @asynccontextmanager
    async def track_stage(
        self,
        execution_id: str,
        stage: PipelineStage,
        service_name: str,
        operation: str = "process",
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Context manager to track a pipeline stage"""
        if execution_id not in self.active_executions:
            logger.warning(f"Pipeline execution {execution_id} not found")
            yield
            return

        execution = self.active_executions[execution_id]
        start_time = time.time()

        # Record stage start
        stage_data = {
            "started_at": datetime.now(),
            "service": service_name,
            "operation": operation,
            "metadata": metadata or {},
        }
        execution.stages[stage.value] = stage_data

        PIPELINE_COUNT.labels(
            stage=stage.value,
            status=PipelineStatus.IN_PROGRESS.value,
            document_type=execution.document_type,
            service=service_name,
        ).inc()

        try:
            yield execution

            # Success - record metrics
            duration = time.time() - start_time
            stage_data["completed_at"] = datetime.now()
            stage_data["duration_seconds"] = duration
            stage_data["status"] = PipelineStatus.COMPLETED.value

            # Record timing metrics
            PIPELINE_DURATION.labels(
                stage=stage.value,
                document_type=execution.document_type,
                service=service_name,
            ).observe(duration)

            SERVICE_LATENCY.labels(
                service=service_name,
                operation=operation,
                document_type=execution.document_type,
            ).observe(duration)

            PIPELINE_COUNT.labels(
                stage=stage.value,
                status=PipelineStatus.COMPLETED.value,
                document_type=execution.document_type,
                service=service_name,
            ).inc()

            # Check SLA compliance
            threshold = self.sla_thresholds.get(stage, 30.0)
            compliance = 1.0 if duration <= threshold else 0.0
            SLA_COMPLIANCE.labels(stage=stage.value, sla_type="latency").set(compliance)

            logger.debug(
                f"Stage {stage.value} completed in {duration:.3f}s (threshold: {threshold}s)"
            )

        except Exception as e:
            # Error - record error metrics
            duration = time.time() - start_time
            stage_data["completed_at"] = datetime.now()
            stage_data["duration_seconds"] = duration
            stage_data["status"] = PipelineStatus.FAILED.value
            stage_data["error"] = str(e)

            PIPELINE_ERRORS.labels(
                stage=stage.value, error_type=type(e).__name__, service=service_name
            ).inc()

            PIPELINE_COUNT.labels(
                stage=stage.value,
                status=PipelineStatus.FAILED.value,
                document_type=execution.document_type,
                service=service_name,
            ).inc()

            logger.error(f"Stage {stage.value} failed after {duration:.3f}s: {e}")
            raise

    def complete_pipeline_execution(
        self, execution_id: str, status: PipelineStatus = PipelineStatus.COMPLETED
    ):
        """Complete a pipeline execution"""
        if execution_id not in self.active_executions:
            logger.warning(f"Pipeline execution {execution_id} not found")
            return

        execution = self.active_executions[execution_id]
        execution.status = status

        # Calculate total duration
        total_duration = (datetime.now() - execution.started_at).total_seconds()

        # Record end-to-end metrics
        PIPELINE_DURATION.labels(
            stage=PipelineStage.END_TO_END.value,
            document_type=execution.document_type,
            service=self.service_name,
        ).observe(total_duration)

        PIPELINE_COUNT.labels(
            stage=PipelineStage.END_TO_END.value,
            status=status.value,
            document_type=execution.document_type,
            service=self.service_name,
        ).inc()

        # Check end-to-end SLA compliance
        threshold = self.sla_thresholds[PipelineStage.END_TO_END]
        compliance = 1.0 if total_duration <= threshold else 0.0
        SLA_COMPLIANCE.labels(
            stage=PipelineStage.END_TO_END.value, sla_type="latency"
        ).set(compliance)

        # Move to recent executions
        self.recent_executions.append(execution)
        if len(self.recent_executions) > self.max_recent_executions:
            self.recent_executions = self.recent_executions[
                -self.max_recent_executions :
            ]

        # Remove from active executions
        del self.active_executions[execution_id]

        logger.info(
            f"Pipeline execution {execution_id} completed in {total_duration:.3f}s"
        )

    def record_document_processed(self, document_type: str, source: str = "unknown"):
        """Record a processed document"""
        DOCUMENTS_PROCESSED.labels(
            document_type=document_type, source=source, service=self.service_name
        ).inc()

    def update_queue_size(self, stage: PipelineStage, size: int, service: str):
        """Update queue size for a pipeline stage"""
        PIPELINE_QUEUE_SIZE.labels(stage=stage.value, service=service).set(size)

    def update_service_health(self, service: str, health_score: float):
        """Update service health score (0.0 to 1.0)"""
        SERVICE_HEALTH.labels(service=service).set(health_score)

    def update_processing_rate(self, rate_per_minute: float):
        """Update documents processing rate"""
        PROCESSING_RATE.labels(service=self.service_name).set(rate_per_minute)

    def update_resource_usage(
        self, service: str, resource_type: str, value: float, unit: str
    ):
        """Update resource usage metrics"""
        SERVICE_RESOURCE_USAGE.labels(
            service=service, resource_type=resource_type, unit=unit
        ).set(value)

    def update_index_sizes(self, index_metrics: dict[str, Any]):
        """Update search index and vector collection sizes"""
        for index_type, size in index_metrics.get("search_indexes", {}).items():
            SEARCH_INDEX_SIZE.labels(
                index_type=index_type, service="archon-search"
            ).set(size)

        for collection_name, size in index_metrics.get(
            "vector_collections", {}
        ).items():
            VECTOR_COLLECTION_SIZE.labels(
                collection_name=collection_name, service="archon-search"
            ).set(size)

    def get_pipeline_metrics(self) -> dict[str, Any]:
        """Get current pipeline metrics"""
        return {
            "active_executions": len(self.active_executions),
            "recent_executions": len(self.recent_executions),
            "avg_duration_last_10": self._calculate_avg_duration(),
            "success_rate_last_100": self._calculate_success_rate(),
            "sla_compliance": self._calculate_sla_compliance(),
            "bottlenecks": self._identify_bottlenecks(),
        }

    def _calculate_avg_duration(self) -> float:
        """Calculate average duration of last 10 executions"""
        recent = self.recent_executions[-10:]
        if not recent:
            return 0.0

        durations = []
        for execution in recent:
            if execution.status == PipelineStatus.COMPLETED:
                total_duration = sum(
                    stage_data.get("duration_seconds", 0)
                    for stage_data in execution.stages.values()
                )
                durations.append(total_duration)

        return sum(durations) / len(durations) if durations else 0.0

    def _calculate_success_rate(self) -> float:
        """Calculate success rate of last 100 executions"""
        recent = self.recent_executions[-100:]
        if not recent:
            return 1.0

        successful = sum(1 for e in recent if e.status == PipelineStatus.COMPLETED)
        return successful / len(recent)

    def _calculate_sla_compliance(self) -> dict[str, float]:
        """Calculate SLA compliance for each stage"""
        compliance = {}
        recent = self.recent_executions[-100:]

        if not recent:
            return compliance

        for stage in PipelineStage:
            stage_name = stage.value
            threshold = self.sla_thresholds.get(stage, 30.0)

            compliant_count = 0
            total_count = 0

            for execution in recent:
                if stage_name in execution.stages:
                    stage_data = execution.stages[stage_name]
                    duration = stage_data.get("duration_seconds", 0)
                    if duration > 0:
                        total_count += 1
                        if duration <= threshold:
                            compliant_count += 1

            if total_count > 0:
                compliance[stage_name] = compliant_count / total_count

        return compliance

    def _identify_bottlenecks(self) -> list[dict[str, Any]]:
        """Identify performance bottlenecks"""
        bottlenecks = []
        recent = self.recent_executions[-50:]

        if not recent:
            return bottlenecks

        # Analyze average duration by stage
        stage_durations = {}
        for execution in recent:
            for stage_name, stage_data in execution.stages.items():
                duration = stage_data.get("duration_seconds", 0)
                if duration > 0:
                    if stage_name not in stage_durations:
                        stage_durations[stage_name] = []
                    stage_durations[stage_name].append(duration)

        # Identify stages exceeding thresholds
        for stage_name, durations in stage_durations.items():
            avg_duration = sum(durations) / len(durations)
            threshold = self.sla_thresholds.get(PipelineStage(stage_name), 30.0)

            if avg_duration > threshold * 0.8:  # 80% of threshold
                bottlenecks.append(
                    {
                        "stage": stage_name,
                        "avg_duration": avg_duration,
                        "threshold": threshold,
                        "severity": "high" if avg_duration > threshold else "medium",
                        "recommendation": f"Optimize {stage_name} performance",
                    }
                )

        return sorted(bottlenecks, key=lambda x: x["avg_duration"], reverse=True)

    def _start_background_collection(self):
        """Start background metrics collection"""
        # Skip background collection in test environments
        import os

        if os.getenv("PYTEST_CURRENT_TEST"):
            logger.debug("Skipping background metrics collection in test environment")
            return

        try:
            loop = asyncio.get_event_loop()
            self._background_task = loop.create_task(self._collect_background_metrics())
        except Exception as e:
            logger.warning(f"Could not start background metrics collection: {e}")

    async def cleanup(self):
        """Cleanup background tasks and resources"""
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            logger.debug("Background metrics collection task cancelled")

    async def _collect_background_metrics(self):
        """Collect background metrics periodically"""
        while True:
            try:
                # Calculate processing rate
                recent_1min = [
                    e
                    for e in self.recent_executions
                    if (datetime.now() - e.started_at).total_seconds() <= 60
                ]
                self.update_processing_rate(len(recent_1min))

                # Update queue sizes (would need actual queue implementations)
                for stage in PipelineStage:
                    if stage != PipelineStage.END_TO_END:
                        # Placeholder - would get actual queue sizes
                        self.update_queue_size(stage, 0, self.service_name)

                await asyncio.sleep(30)  # Collect every 30 seconds

            except Exception as e:
                logger.error(f"Error in background metrics collection: {e}")
                await asyncio.sleep(60)


# Global pipeline metrics collector
pipeline_metrics = PipelineMetricsCollector()


def get_pipeline_metrics():
    """Get pipeline metrics in Prometheus format"""
    from prometheus_client.exposition import choose_encoder

    encoder, content_type = choose_encoder(None)
    return encoder(PIPELINE_REGISTRY), content_type


def get_pipeline_status() -> dict[str, Any]:
    """Get comprehensive pipeline status"""
    return {
        "timestamp": datetime.now().isoformat(),
        "metrics": pipeline_metrics.get_pipeline_metrics(),
        "active_executions": len(pipeline_metrics.active_executions),
        "service_health": {
            "archon-server": 1.0,  # Would get actual health scores
            "archon-bridge": 1.0,
            "archon-intelligence": 1.0,
            "archon-search": 1.0,
            "qdrant": 1.0,
            "memgraph": 1.0,
        },
    }
