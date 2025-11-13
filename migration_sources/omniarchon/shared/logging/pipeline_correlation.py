"""
Pipeline Correlation System for Archon Services

Unified correlation tracking system for document processing pipeline
across Bridge → Intelligence → Qdrant → Search services.
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class PipelineCorrelation:
    """
    Manages correlation IDs and tracking data across the entire document processing pipeline.

    Enables end-to-end traceability from initial document creation through
    entity extraction, vectorization, and search indexing.
    """

    def __init__(self):
        self.active_pipelines: Dict[str, Dict[str, Any]] = {}

    def generate_pipeline_id(self, document_id: str, project_id: str) -> str:
        """Generate a unique pipeline correlation ID."""
        timestamp = int(time.time())
        short_uuid = uuid.uuid4().hex[:8]
        return f"pipeline_{document_id}_{project_id}_{short_uuid}_{timestamp}"

    def start_pipeline(
        self,
        document_id: str,
        project_id: str,
        initiating_service: str,
        initial_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a new pipeline correlation tracking."""
        pipeline_id = self.generate_pipeline_id(document_id, project_id)

        self.active_pipelines[pipeline_id] = {
            "pipeline_id": pipeline_id,
            "document_id": document_id,
            "project_id": project_id,
            "initiating_service": initiating_service,
            "start_time": datetime.now(timezone.utc),
            "stages": [],
            "metadata": initial_metadata or {},
            "status": "active",
        }

        return pipeline_id

    def add_stage(
        self,
        pipeline_id: str,
        service: str,
        stage: str,
        request_id: str,
        correlation_id: str,
        stage_metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add a stage to the pipeline tracking."""
        if pipeline_id not in self.active_pipelines:
            # If pipeline doesn't exist, create a minimal one
            self.active_pipelines[pipeline_id] = {
                "pipeline_id": pipeline_id,
                "document_id": "unknown",
                "project_id": "unknown",
                "initiating_service": service,
                "start_time": datetime.now(timezone.utc),
                "stages": [],
                "metadata": {},
                "status": "active",
            }

        stage_data = {
            "service": service,
            "stage": stage,
            "request_id": request_id,
            "correlation_id": correlation_id,
            "timestamp": datetime.now(timezone.utc),
            "metadata": stage_metadata or {},
        }

        self.active_pipelines[pipeline_id]["stages"].append(stage_data)

    def complete_pipeline(self, pipeline_id: str, final_status: str = "completed"):
        """Mark a pipeline as completed."""
        if pipeline_id in self.active_pipelines:
            self.active_pipelines[pipeline_id]["status"] = final_status
            self.active_pipelines[pipeline_id]["end_time"] = datetime.now(timezone.utc)

    def get_pipeline_status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a pipeline."""
        return self.active_pipelines.get(pipeline_id)

    def get_document_pipelines(self, document_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all pipelines for a specific document."""
        return {
            pid: data
            for pid, data in self.active_pipelines.items()
            if data.get("document_id") == document_id
        }

    def cleanup_completed_pipelines(self, hours_old: int = 24):
        """Clean up old completed pipelines to prevent memory bloat."""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (hours_old * 3600)

        pipelines_to_remove = []
        for pipeline_id, data in self.active_pipelines.items():
            if (
                data.get("status") in ["completed", "failed"]
                and data.get("end_time")
                and data["end_time"].timestamp() < cutoff_time
            ):
                pipelines_to_remove.append(pipeline_id)

        for pipeline_id in pipelines_to_remove:
            del self.active_pipelines[pipeline_id]

        return len(pipelines_to_remove)

    def get_pipeline_summary(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of the pipeline for logging purposes."""
        if pipeline_id not in self.active_pipelines:
            return None

        data = self.active_pipelines[pipeline_id]

        duration_seconds = None
        if data.get("end_time"):
            duration_seconds = (data["end_time"] - data["start_time"]).total_seconds()
        elif data.get("start_time"):
            duration_seconds = (
                datetime.now(timezone.utc) - data["start_time"]
            ).total_seconds()

        return {
            "pipeline_id": pipeline_id,
            "document_id": data.get("document_id"),
            "project_id": data.get("project_id"),
            "status": data.get("status"),
            "stages_count": len(data.get("stages", [])),
            "duration_seconds": duration_seconds,
            "services_involved": list(
                set(stage["service"] for stage in data.get("stages", []))
            ),
            "current_stage": data.get("stages", [])[-1] if data.get("stages") else None,
        }


class CorrelationHeaders:
    """
    HTTP headers for correlation tracking across services.
    """

    PIPELINE_ID = "X-Archon-Pipeline-ID"
    REQUEST_ID = "X-Archon-Request-ID"
    CORRELATION_ID = "X-Archon-Correlation-ID"
    SERVICE_NAME = "X-Archon-Service"
    STAGE_NAME = "X-Archon-Stage"

    @classmethod
    def create_headers(
        cls,
        pipeline_id: str,
        request_id: str,
        correlation_id: str,
        service_name: str,
        stage_name: str,
    ) -> Dict[str, str]:
        """Create correlation headers for HTTP requests."""
        return {
            cls.PIPELINE_ID: pipeline_id,
            cls.REQUEST_ID: request_id,
            cls.CORRELATION_ID: correlation_id,
            cls.SERVICE_NAME: service_name,
            cls.STAGE_NAME: stage_name,
        }

    @classmethod
    def extract_headers(cls, headers: Dict[str, str]) -> Dict[str, Optional[str]]:
        """Extract correlation data from HTTP headers."""
        return {
            "pipeline_id": headers.get(cls.PIPELINE_ID),
            "request_id": headers.get(cls.REQUEST_ID),
            "correlation_id": headers.get(cls.CORRELATION_ID),
            "service_name": headers.get(cls.SERVICE_NAME),
            "stage_name": headers.get(cls.STAGE_NAME),
        }


# Global pipeline correlation instance
global_pipeline_correlation = PipelineCorrelation()


def get_pipeline_correlation() -> PipelineCorrelation:
    """Get the global pipeline correlation instance."""
    return global_pipeline_correlation


def create_pipeline_headers(
    document_id: str,
    project_id: str,
    service_name: str,
    stage_name: str,
    request_id: str,
    correlation_id: str,
) -> Dict[str, str]:
    """
    Create correlation headers for a new pipeline stage.

    Convenience function that starts a pipeline if needed and creates appropriate headers.
    """
    pipeline_correlation = get_pipeline_correlation()

    # Check if there's already an active pipeline for this document
    existing_pipelines = pipeline_correlation.get_document_pipelines(document_id)
    active_pipelines = [
        p for p in existing_pipelines.values() if p.get("status") == "active"
    ]

    if active_pipelines:
        # Use existing pipeline
        pipeline_id = active_pipelines[0]["pipeline_id"]
    else:
        # Start new pipeline
        pipeline_id = pipeline_correlation.start_pipeline(
            document_id=document_id,
            project_id=project_id,
            initiating_service=service_name,
        )

    # Add this stage to the pipeline
    pipeline_correlation.add_stage(
        pipeline_id=pipeline_id,
        service=service_name,
        stage=stage_name,
        request_id=request_id,
        correlation_id=correlation_id,
    )

    return CorrelationHeaders.create_headers(
        pipeline_id=pipeline_id,
        request_id=request_id,
        correlation_id=correlation_id,
        service_name=service_name,
        stage_name=stage_name,
    )


# Export key components
__all__ = [
    "PipelineCorrelation",
    "CorrelationHeaders",
    "global_pipeline_correlation",
    "get_pipeline_correlation",
    "create_pipeline_headers",
]
