"""
Progress Tracker Utility

Consolidates all Socket.IO progress tracking operations for cleaner service code.
"""

from datetime import datetime
from typing import Any

from server.config.logfire_config import safe_logfire_error, safe_logfire_info


class ProgressTracker:
    """
    Utility class for tracking and broadcasting progress updates via Socket.IO.
    Consolidates all progress-related Socket.IO operations.
    """

    def __init__(self, sio, progress_id: str, operation_type: str = "crawl"):
        """
        Initialize the progress tracker.

        Args:
            sio: Socket.IO instance
            progress_id: Unique progress identifier
            operation_type: Type of operation (crawl, upload, etc.)
        """
        self.sio = sio
        self.progress_id = progress_id
        self.operation_type = operation_type
        self.state = {
            "progressId": progress_id,
            "startTime": datetime.now().isoformat(),
            "status": "initializing",
            "percentage": 0,
            "logs": [],
        }

    async def start(self, initial_data: dict[str, Any] | None = None):
        """
        Start progress tracking with initial data.

        Args:
            initial_data: Optional initial data to include
        """
        self.state["status"] = "starting"
        self.state["startTime"] = datetime.now().isoformat()

        if initial_data:
            self.state.update(initial_data)

        await self._emit_progress()
        safe_logfire_info(
            f"Progress tracking started | progress_id={self.progress_id} | type={self.operation_type}"
        )

    async def update(self, status: str, percentage: int, log: str, **kwargs):
        """
        Update progress with status, percentage, and log message.

        Args:
            status: Current status (analyzing, crawling, processing, etc.)
            percentage: Progress percentage (0-100)
            log: Log message describing current operation
            **kwargs: Additional data to include in update
        """
        self.state.update(
            {
                "status": status,
                "percentage": min(100, max(0, percentage)),  # Ensure 0-100
                "log": log,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Add log entry
        if "logs" not in self.state:
            self.state["logs"] = []
        self.state["logs"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "message": log,
                "status": status,
                "percentage": percentage,
            }
        )

        # Add any additional data
        for key, value in kwargs.items():
            self.state[key] = value

        await self._emit_progress()

    async def complete(self, completion_data: dict[str, Any] | None = None):
        """
        Mark progress as completed with optional completion data.

        Args:
            completion_data: Optional data about the completed operation
        """
        self.state["status"] = "completed"
        self.state["percentage"] = 100
        self.state["endTime"] = datetime.now().isoformat()

        if completion_data:
            self.state.update(completion_data)

        # Calculate duration
        if "startTime" in self.state:
            start = datetime.fromisoformat(self.state["startTime"])
            end = datetime.fromisoformat(self.state["endTime"])
            duration = (end - start).total_seconds()
            self.state["duration"] = duration
            self.state["durationFormatted"] = self._format_duration(duration)

        await self._emit_progress()
        safe_logfire_info(
            f"Progress completed | progress_id={self.progress_id} | type={self.operation_type} | duration={self.state.get('durationFormatted', 'unknown')}"
        )

    async def error(
        self, error_message: str, error_details: dict[str, Any] | None = None
    ):
        """
        Mark progress as failed with error information.

        Args:
            error_message: Error message
            error_details: Optional additional error details
        """
        self.state.update(
            {
                "status": "error",
                "error": error_message,
                "errorTime": datetime.now().isoformat(),
            }
        )

        if error_details:
            self.state["errorDetails"] = error_details

        await self._emit_progress()
        safe_logfire_error(
            f"Progress error | progress_id={self.progress_id} | type={self.operation_type} | error={error_message}"
        )

    async def update_batch_progress(
        self, current_batch: int, total_batches: int, batch_size: int, message: str
    ):
        """
        Update progress for batch operations.

        Args:
            current_batch: Current batch number (1-based)
            total_batches: Total number of batches
            batch_size: Size of each batch
            message: Progress message
        """
        percentage = int((current_batch / total_batches) * 100)
        await self.update(
            status="processing_batch",
            percentage=percentage,
            log=message,
            currentBatch=current_batch,
            totalBatches=total_batches,
            batchSize=batch_size,
        )

    async def update_crawl_stats(
        self, processed_pages: int, total_pages: int, current_url: str | None = None
    ):
        """
        Update crawling statistics.

        Args:
            processed_pages: Number of pages processed
            total_pages: Total pages to process
            current_url: Currently processing URL
        """
        percentage = int((processed_pages / max(total_pages, 1)) * 100)
        log = f"Processing page {processed_pages}/{total_pages}"
        if current_url:
            log += f": {current_url}"

        await self.update(
            status="crawling",
            percentage=percentage,
            log=log,
            processedPages=processed_pages,
            totalPages=total_pages,
            currentUrl=current_url,
        )

    async def update_storage_progress(
        self, chunks_stored: int, total_chunks: int, operation: str = "storing"
    ):
        """
        Update document storage progress.

        Args:
            chunks_stored: Number of chunks stored
            total_chunks: Total chunks to store
            operation: Storage operation description
        """
        percentage = int((chunks_stored / max(total_chunks, 1)) * 100)
        await self.update(
            status="document_storage",
            percentage=percentage,
            log=f"{operation}: {chunks_stored}/{total_chunks} chunks",
            chunksStored=chunks_stored,
            totalChunks=total_chunks,
        )

    async def _emit_progress(self):
        """Emit progress update via Socket.IO."""
        event_name = f"{self.operation_type}_progress"

        # Log detailed progress info for debugging
        safe_logfire_info(
            f"📢 [SOCKETIO] Broadcasting {event_name} to room: {self.progress_id}"
        )
        safe_logfire_info(
            f"📢 [SOCKETIO] Status: {self.state.get('status')} | Percentage: {self.state.get('percentage')}%"
        )

        # Emit to the progress room
        await self.sio.emit(event_name, self.state, room=self.progress_id)

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"

    def get_state(self) -> dict[str, Any]:
        """Get current progress state."""
        return self.state.copy()

    async def join_room(self, sid: str):
        """Add a socket ID to the progress room."""
        await self.sio.enter_room(sid, self.progress_id)
        safe_logfire_info(f"Socket {sid} joined progress room {self.progress_id}")

    async def leave_room(self, sid: str):
        """Remove a socket ID from the progress room."""
        await self.sio.leave_room(sid, self.progress_id)
        safe_logfire_info(f"Socket {sid} left progress room {self.progress_id}")
