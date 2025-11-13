"""
Correlation API Routes

Provides endpoints for managing the automated correlation analysis system.
Allows triggering correlation generation, monitoring processing status,
and managing the background correlation processor.

This module provides:
- Manual correlation generation triggers
- Background processing management
- Processing status and statistics
- Queue management and monitoring
- Configuration management

Architecture follows ONEX principles:
- Clear API design with proper HTTP status codes
- Comprehensive error handling and logging
- Integration with correlation processor service
- Performance monitoring and observability
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from server.services.correlation_analyzer import create_correlation_analyzer
from server.services.correlation_processor import get_correlation_processor

logger = logging.getLogger(__name__)

# Create router with prefix
router = APIRouter(prefix="/api/correlations", tags=["correlations"])


# Pydantic models for API requests and responses
class CorrelationTriggerRequest(BaseModel):
    """Request model for triggering correlation analysis."""

    document_id: Optional[str] = None
    repository: Optional[str] = None
    priority: int = 5
    force_reprocess: bool = False


class ProcessorControlRequest(BaseModel):
    """Request model for controlling the background processor."""

    action: str  # "start", "stop", "restart"
    config: Optional[dict[str, Any]] = None


class CorrelationAnalysisResponse(BaseModel):
    """Response model for correlation analysis results."""

    success: bool
    message: str
    document_id: Optional[str] = None
    correlations_generated: Optional[int] = None
    processing_time_seconds: Optional[float] = None
    error: Optional[str] = None


class ProcessingStatsResponse(BaseModel):
    """Response model for processing statistics."""

    success: bool
    stats: dict[str, Any]
    timestamp: str


class QueueStatusResponse(BaseModel):
    """Response model for queue status."""

    success: bool
    queue_status: dict[str, Any]
    timestamp: str


@router.post("/trigger", response_model=CorrelationAnalysisResponse)
async def trigger_correlation_analysis(
    request: CorrelationTriggerRequest, background_tasks: BackgroundTasks
):
    """
    Trigger correlation analysis for specific documents or all empty correlations.

    This endpoint can:
    - Trigger analysis for a specific document
    - Queue all documents with empty correlations for processing
    - Force reprocessing of documents that already have correlations
    """
    try:
        processor = get_correlation_processor()

        if request.document_id:
            # Trigger analysis for specific document
            # TODO: Get repository and commit_sha from document ID
            success = await processor.queue_document_for_processing(
                request.document_id,
                request.repository or "unknown",
                "unknown",  # commit_sha would need to be retrieved
                request.priority,
            )

            if success:
                return CorrelationAnalysisResponse(
                    success=True,
                    message=f"Document {request.document_id} queued for correlation analysis",
                    document_id=request.document_id,
                )
            else:
                raise HTTPException(
                    status_code=400, detail="Failed to queue document for processing"
                )

        else:
            # Queue all documents with empty correlations
            background_tasks.add_task(processor.queue_documents_with_empty_correlations)

            return CorrelationAnalysisResponse(
                success=True,
                message="Background task started to queue documents with empty correlations",
            )

    except Exception as e:
        logger.error(f"Error triggering correlation analysis: {e}")
        return CorrelationAnalysisResponse(
            success=False,
            message="Failed to trigger correlation analysis",
            error=str(e),
        )


@router.post("/processor/control")
async def control_processor(request: ProcessorControlRequest):
    """
    Control the background correlation processor.

    Actions:
    - start: Start the background processing loop
    - stop: Stop the background processing loop
    - restart: Stop and restart the processor
    """
    try:
        processor = get_correlation_processor()

        if request.action == "start":
            if not processor.is_running:
                # Start processor in background
                import asyncio

                asyncio.create_task(processor.start_processing())

                return {
                    "success": True,
                    "message": "Background correlation processor started",
                }
            else:
                return {
                    "success": True,
                    "message": "Background correlation processor is already running",
                }

        elif request.action == "stop":
            await processor.stop_processing()
            return {
                "success": True,
                "message": "Background correlation processor stopped",
            }

        elif request.action == "restart":
            await processor.stop_processing()

            # Wait a moment for clean shutdown
            import asyncio

            await asyncio.sleep(1)

            # Start again
            asyncio.create_task(processor.start_processing())

            return {
                "success": True,
                "message": "Background correlation processor restarted",
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {request.action}. Must be 'start', 'stop', or 'restart'",
            )

    except Exception as e:
        logger.error(f"Error controlling correlation processor: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to control processor: {e!s}"
        )


@router.get("/stats", response_model=ProcessingStatsResponse)
async def get_processing_stats():
    """
    Get current processing statistics and performance metrics.

    Returns information about:
    - Total documents processed
    - Success/failure rates
    - Processing performance
    - Current queue status
    """
    try:
        processor = get_correlation_processor()
        stats = processor.get_processing_stats()

        return ProcessingStatsResponse(
            success=True, stats=stats, timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error getting processing stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get processing stats: {e!s}"
        )


@router.get("/queue", response_model=QueueStatusResponse)
async def get_queue_status():
    """
    Get current queue status and task details.

    Returns information about:
    - Total tasks in queue
    - Task status breakdown
    - Individual task details
    - Queue health metrics
    """
    try:
        processor = get_correlation_processor()
        queue_status = processor.get_queue_status()

        return QueueStatusResponse(
            success=True,
            queue_status=queue_status,
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get queue status: {e!s}"
        )


@router.post("/analyze/single")
async def analyze_single_document(
    document_id: str,
    priority: int = Query(5, ge=1, le=10, description="Processing priority (1-10)"),
):
    """
    Queue a single document for immediate correlation analysis.

    This is a convenience endpoint for analyzing specific documents
    without needing to construct a full trigger request.
    """
    try:
        processor = get_correlation_processor()

        # TODO: Need to retrieve repository and commit_sha from document_id
        # For now, using placeholder values
        success = await processor.queue_document_for_processing(
            document_id, "unknown", "unknown", priority  # repository  # commit_sha
        )

        if success:
            return {
                "success": True,
                "message": f"Document {document_id} queued for correlation analysis",
                "document_id": document_id,
                "priority": priority,
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to queue document")

    except Exception as e:
        logger.error(f"Error analyzing single document {document_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze document: {e!s}"
        )


@router.post("/analyze/empty")
async def analyze_empty_correlations(background_tasks: BackgroundTasks):
    """
    Queue all documents with empty correlations for analysis.

    This endpoint scans for all intelligence documents that have
    empty temporal and semantic correlations and queues them
    for background processing.
    """
    try:
        processor = get_correlation_processor()

        # Run the queuing in background to avoid timeout
        background_tasks.add_task(processor.queue_documents_with_empty_correlations)

        return {
            "success": True,
            "message": "Started background task to queue documents with empty correlations",
            "note": "Check /api/correlations/stats for progress updates",
        }

    except Exception as e:
        logger.error(f"Error analyzing empty correlations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {e!s}")


@router.get("/health")
async def get_correlation_system_health():
    """
    Get health status of the correlation analysis system.

    Returns comprehensive health information including:
    - Processor status
    - Queue health
    - Recent processing performance
    - System configuration
    """
    try:
        processor = get_correlation_processor()
        stats = processor.get_processing_stats()
        queue_status = processor.get_queue_status()

        # Calculate health indicators
        is_healthy = True
        health_issues = []

        # Check if processor is running when it should be
        if not processor.is_running and queue_status["total_tasks"] > 0:
            is_healthy = False
            health_issues.append("Processor not running but tasks in queue")

        # Check for excessive failures
        if stats["failed_processing"] > stats["successful_correlations"] * 0.5:
            is_healthy = False
            health_issues.append("High failure rate in processing")

        # Check for stuck tasks
        stuck_tasks = len(
            [
                task
                for task in queue_status["tasks"]
                if task["status"] == "in_progress"
                and (
                    datetime.utcnow() - datetime.fromisoformat(task["created_at"])
                ).total_seconds()
                > 3600
            ]
        )

        if stuck_tasks > 0:
            is_healthy = False
            health_issues.append(f"{stuck_tasks} tasks stuck in processing")

        health_status = {
            "healthy": is_healthy,
            "status": "healthy" if is_healthy else "degraded",
            "issues": health_issues,
            "processor_running": processor.is_running,
            "queue_length": queue_status["total_tasks"],
            "recent_success_rate": (
                stats["successful_correlations"]
                / max(1, stats["total_documents_processed"])
                if stats["total_documents_processed"] > 0
                else 0
            ),
            "system_info": {
                "total_processed": stats["total_documents_processed"],
                "total_correlations_generated": stats["total_correlations_generated"],
                "uptime_since": stats.get("processing_start_time"),
                "last_activity": stats.get("last_batch_completed"),
            },
        }

        return {
            "success": True,
            "health": health_status,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error checking correlation system health: {e}")
        return {
            "success": False,
            "health": {
                "healthy": False,
                "status": "error",
                "issues": [f"Health check failed: {e!s}"],
            },
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.get("/config")
async def get_correlation_config():
    """
    Get current correlation system configuration.

    Returns the current configuration parameters for the
    correlation analyzer and processor.
    """
    try:
        processor = get_correlation_processor()
        analyzer = create_correlation_analyzer()

        config = {
            "processor_config": {
                "batch_size": processor.batch_size,
                "max_context_documents": processor.max_context_documents,
                "max_retries": processor.max_retries,
                "retry_delay_seconds": processor.retry_delay_seconds,
                "context_time_range": processor.context_time_range,
                "processing_interval": processor.processing_interval,
            },
            "analyzer_config": {
                "temporal_threshold_hours": analyzer.temporal_threshold_hours,
                "semantic_threshold": analyzer.semantic_threshold,
                "max_correlations_per_document": analyzer.max_correlations_per_document,
                "keyword_weight": analyzer.keyword_weight,
                "file_path_weight": analyzer.file_path_weight,
                "author_weight": analyzer.author_weight,
                "commit_message_weight": analyzer.commit_message_weight,
            },
        }

        return {
            "success": True,
            "config": config,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting correlation config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {e!s}")
