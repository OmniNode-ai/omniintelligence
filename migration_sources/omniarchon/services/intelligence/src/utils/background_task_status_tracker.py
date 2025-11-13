"""
Background Task Status Tracker

Tracks the status of background tasks for error propagation and status monitoring.
Uses in-memory cache (Valkey/Redis) for distributed tracking across service instances.

Created: 2025-11-12
Purpose: Enable error propagation from background tasks to API consumers
"""

import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Background task status states."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class BackgroundTaskState(BaseModel):
    """Model for background task state tracking."""

    document_id: str = Field(..., description="Document identifier")
    correlation_id: Optional[str] = Field(
        None, description="Correlation ID for tracing"
    )
    status: TaskStatus = Field(..., description="Current task status")
    started_at: datetime = Field(..., description="Task start timestamp")
    completed_at: Optional[datetime] = Field(
        None, description="Task completion timestamp"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")
    error_details: Optional[Dict[str, Any]] = Field(
        None, description="Detailed error information"
    )
    pipeline_steps: Dict[str, str] = Field(
        default_factory=dict, description="Status of each pipeline step"
    )
    entities_extracted: Optional[int] = Field(
        None, description="Number of entities extracted"
    )
    vector_indexed: Optional[bool] = Field(
        None, description="Whether vector indexing succeeded"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class BackgroundTaskStatusTracker:
    """
    Track background task status using Valkey/Redis cache.

    Features:
    - In-memory cache for fast status lookup
    - TTL-based expiration (24 hours default)
    - Correlation ID tracking for end-to-end tracing
    - Pipeline step tracking for detailed progress
    - Error capture with full context

    Usage:
        tracker = BackgroundTaskStatusTracker(cache_client)

        # Start tracking
        await tracker.start_task("doc-123", correlation_id="abc-456")

        # Update pipeline steps
        await tracker.update_step("doc-123", "embedding_generation", "success")

        # Record success
        await tracker.complete_task("doc-123", entities_extracted=42, vector_indexed=True)

        # Record failure
        await tracker.fail_task("doc-123", error="Vectorization failed", details={...})

        # Query status
        status = await tracker.get_status("doc-123")
    """

    def __init__(self, cache_client: Optional[Any] = None, ttl_seconds: int = 86400):
        """
        Initialize status tracker.

        Args:
            cache_client: Valkey/Redis client for distributed tracking (optional, uses local cache if None)
            ttl_seconds: Time-to-live for status entries (default 24 hours)
        """
        self.cache_client = cache_client
        self.ttl_seconds = ttl_seconds
        self.local_cache: Dict[str, BackgroundTaskState] = {}

    def _get_cache_key(self, document_id: str) -> str:
        """Generate cache key for document ID."""
        return f"bg_task_status:{document_id}"

    async def start_task(
        self, document_id: str, correlation_id: Optional[str] = None
    ) -> None:
        """
        Mark task as started.

        Args:
            document_id: Document identifier
            correlation_id: Optional correlation ID for tracing
        """
        state = BackgroundTaskState(
            document_id=document_id,
            correlation_id=correlation_id,
            status=TaskStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        await self._save_state(document_id, state)

        logger.info(
            f"📊 [TASK TRACKING] Task started | document_id={document_id} | "
            f"correlation_id={correlation_id}",
            extra={
                "document_id": document_id,
                "correlation_id": correlation_id,
                "task_status": TaskStatus.RUNNING.value,
            },
        )

    async def update_step(
        self, document_id: str, step_name: str, step_status: str
    ) -> None:
        """
        Update pipeline step status.

        Args:
            document_id: Document identifier
            step_name: Pipeline step name (e.g., "embedding_generation", "qdrant_indexing")
            step_status: Step status (e.g., "success", "failed", "skipped")
        """
        state = await self.get_status(document_id)
        if state:
            state.pipeline_steps[step_name] = step_status
            await self._save_state(document_id, state)

            logger.debug(
                f"📊 [TASK TRACKING] Step updated | document_id={document_id} | "
                f"step={step_name} | status={step_status}"
            )

    async def complete_task(
        self,
        document_id: str,
        entities_extracted: Optional[int] = None,
        vector_indexed: Optional[bool] = None,
    ) -> None:
        """
        Mark task as successfully completed.

        Args:
            document_id: Document identifier
            entities_extracted: Number of entities extracted
            vector_indexed: Whether vector indexing succeeded
        """
        state = await self.get_status(document_id)
        if not state:
            logger.warning(
                f"⚠️ [TASK TRACKING] Cannot complete task - not found | document_id={document_id}"
            )
            return

        state.status = TaskStatus.SUCCESS
        state.completed_at = datetime.now(timezone.utc)
        state.entities_extracted = entities_extracted
        state.vector_indexed = vector_indexed

        await self._save_state(document_id, state)

        duration_ms = (
            (state.completed_at - state.started_at).total_seconds() * 1000
            if state.completed_at
            else 0
        )

        logger.info(
            f"✅ [TASK TRACKING] Task completed | document_id={document_id} | "
            f"duration_ms={duration_ms:.2f} | entities={entities_extracted} | "
            f"vector_indexed={vector_indexed}",
            extra={
                "document_id": document_id,
                "correlation_id": state.correlation_id,
                "task_status": TaskStatus.SUCCESS.value,
                "duration_ms": duration_ms,
                "entities_extracted": entities_extracted,
                "vector_indexed": vector_indexed,
            },
        )

    async def fail_task(
        self,
        document_id: str,
        error: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark task as failed.

        Args:
            document_id: Document identifier
            error: Error message
            details: Optional detailed error information
        """
        state = await self.get_status(document_id)
        if not state:
            # Create new state if doesn't exist
            state = BackgroundTaskState(
                document_id=document_id,
                status=TaskStatus.FAILED,
                started_at=datetime.now(timezone.utc),
            )

        state.status = TaskStatus.FAILED
        state.completed_at = datetime.now(timezone.utc)
        state.error_message = error
        state.error_details = details or {}

        await self._save_state(document_id, state)

        duration_ms = (
            (state.completed_at - state.started_at).total_seconds() * 1000
            if state.completed_at
            else 0
        )

        logger.error(
            f"❌ [TASK TRACKING] Task failed | document_id={document_id} | "
            f"duration_ms={duration_ms:.2f} | error={error}",
            extra={
                "document_id": document_id,
                "correlation_id": state.correlation_id,
                "task_status": TaskStatus.FAILED.value,
                "duration_ms": duration_ms,
                "error": error,
                "error_details": details,
            },
        )

    async def get_status(self, document_id: str) -> Optional[BackgroundTaskState]:
        """
        Get current task status.

        Args:
            document_id: Document identifier

        Returns:
            BackgroundTaskState if found, None otherwise
        """
        # Try cache first
        if self.cache_client:
            try:
                cache_key = self._get_cache_key(document_id)
                cached_data = await self.cache_client.get(cache_key)
                if cached_data:
                    return BackgroundTaskState.model_validate_json(cached_data)
            except Exception as e:
                logger.warning(
                    f"Cache lookup failed for {document_id}: {e}, falling back to local cache"
                )

        # Fallback to local cache
        return self.local_cache.get(document_id)

    async def _save_state(self, document_id: str, state: BackgroundTaskState) -> None:
        """
        Save state to cache and local cache.

        Args:
            document_id: Document identifier
            state: Task state to save
        """
        # Always save to local cache
        self.local_cache[document_id] = state

        # Try to save to distributed cache
        if self.cache_client:
            try:
                cache_key = self._get_cache_key(document_id)
                await self.cache_client.setex(
                    cache_key, self.ttl_seconds, state.model_dump_json()
                )
            except Exception as e:
                logger.warning(f"Failed to save to cache for {document_id}: {e}")

    async def cleanup_old_tasks(self, age_seconds: int = 86400) -> int:
        """
        Cleanup old tasks from local cache.

        Args:
            age_seconds: Remove tasks older than this (default 24 hours)

        Returns:
            Number of tasks removed
        """
        cutoff_time = time.time() - age_seconds
        removed = 0

        for document_id, state in list(self.local_cache.items()):
            if state.started_at.timestamp() < cutoff_time:
                del self.local_cache[document_id]
                removed += 1

        if removed > 0:
            logger.info(
                f"🧹 [TASK TRACKING] Cleaned up {removed} old tasks from local cache"
            )

        return removed


# Global instance (initialized by app startup)
_global_tracker: Optional[BackgroundTaskStatusTracker] = None


def get_global_tracker() -> Optional[BackgroundTaskStatusTracker]:
    """Get global background task status tracker instance."""
    return _global_tracker


def set_global_tracker(tracker: BackgroundTaskStatusTracker) -> None:
    """Set global background task status tracker instance."""
    global _global_tracker
    _global_tracker = tracker
    logger.info("✅ Global background task status tracker initialized")
