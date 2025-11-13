"""
Background Task Manager

Manages async background task execution with progress tracking.
Uses pure async patterns for task execution.
"""

import asyncio
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from server.config.logfire_config import get_logger

logger = get_logger(__name__)


class BackgroundTaskManager:
    """Manages async background task execution with progress tracking"""

    def __init__(
        self, max_concurrent_tasks: int = 10, metadata_retention_hours: int = 1
    ):
        self.active_tasks: dict[str, asyncio.Task] = {}
        self.task_metadata: dict[str, dict[str, Any]] = {}
        self.max_concurrent_tasks = max_concurrent_tasks
        self.metadata_retention_hours = metadata_retention_hours
        self._task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._cleanup_task: asyncio.Task | None = None
        logger.info(
            f"BackgroundTaskManager initialized with max {max_concurrent_tasks} concurrent tasks, {metadata_retention_hours}h metadata retention"
        )

    def set_main_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the main event loop for the task manager"""
        logger.info(
            "BackgroundTaskManager uses pure async - main loop setting not required"
        )

    async def submit_task(
        self,
        async_task_func: Callable,
        task_args: tuple,
        task_id: str | None = None,
        progress_callback: Callable | None = None,
    ) -> str:
        """Submit an async task for background execution"""
        task_id = task_id or str(uuid.uuid4())

        # Store metadata
        self.task_metadata[task_id] = {
            "created_at": datetime.utcnow(),
            "status": "running",
            "progress": 0,
        }

        logger.info(f"Submitting async task {task_id} for background execution")

        # Start periodic cleanup if not already running
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

        # Create and start the async task with semaphore to limit concurrency
        async_task = asyncio.create_task(
            self._run_async_with_progress(
                async_task_func, task_args, task_id, progress_callback
            )
        )

        self.active_tasks[task_id] = async_task
        return task_id

    async def _run_async_with_progress(
        self,
        async_task_func: Callable,
        task_args: tuple,
        task_id: str,
        progress_callback: Callable | None = None,
    ) -> Any:
        """Wrapper to run async task with progress tracking and concurrency control"""
        async with self._task_semaphore:  # Limit concurrent tasks
            try:
                logger.info(f"Starting execution of async task {task_id}")

                # Update metadata to running state
                self.task_metadata[task_id].update({"status": "running", "progress": 0})

                # Execute the async task function
                result = await async_task_func(*task_args)

                # Update metadata to completed state
                self.task_metadata[task_id].update(
                    {
                        "status": "complete",
                        "progress": 100,
                        "result": result,
                    }
                )

                # Send completion update via progress callback if provided
                if progress_callback:
                    try:
                        await progress_callback(
                            task_id,
                            {"status": "complete", "percentage": 100, "result": result},
                        )
                    except Exception as callback_error:
                        logger.error(
                            f"Progress callback error for completed task {task_id}: {callback_error}"
                        )

                logger.info(f"Async task {task_id} completed successfully")
                return result

            except Exception as e:
                logger.error(f"Async task {task_id} failed with error: {e}")

                # Update metadata to error state
                self.task_metadata[task_id].update(
                    {
                        "status": "error",
                        "progress": -1,
                        "error": str(e),
                    }
                )

                # Send error update via progress callback if provided
                if progress_callback:
                    try:
                        await progress_callback(
                            task_id,
                            {"status": "error", "percentage": -1, "error": str(e)},
                        )
                    except Exception as callback_error:
                        logger.error(
                            f"Progress callback error for failed task {task_id}: {callback_error}"
                        )

                raise
            finally:
                # Remove from active tasks
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Get current status of a task"""
        metadata = self.task_metadata.get(task_id, {})

        if task_id not in self.active_tasks:
            # Task not active - check if we have metadata from completed task
            if metadata:
                return metadata
            else:
                return {"error": "Task not found"}

        task = self.active_tasks[task_id]

        if task.done():
            try:
                result = task.result()
                metadata["result"] = result
            except Exception as e:
                metadata["error"] = str(e)

        return metadata

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running async task"""
        if task_id in self.active_tasks:
            logger.info(f"Cancelling async task {task_id}")
            task = self.active_tasks[task_id]
            task.cancel()

            # Update metadata
            if task_id in self.task_metadata:
                self.task_metadata[task_id]["status"] = "cancelled"

            # Remove from active tasks
            del self.active_tasks[task_id]
            return True
        return False

    async def _periodic_cleanup(self):
        """Periodically clean up old task metadata to prevent memory leaks"""
        while True:
            try:
                await asyncio.sleep(300)  # Run cleanup every 5 minutes

                current_time = datetime.utcnow()
                retention_cutoff = current_time - timedelta(
                    hours=self.metadata_retention_hours
                )

                # Find and remove old completed/error/cancelled task metadata
                tasks_to_remove = []
                for task_id, metadata in self.task_metadata.items():
                    # Only clean up completed/error/cancelled tasks
                    if metadata.get("status") in ["complete", "error", "cancelled"]:
                        created_at = metadata.get("created_at")
                        if created_at and created_at < retention_cutoff:
                            tasks_to_remove.append(task_id)

                # Remove old metadata
                for task_id in tasks_to_remove:
                    del self.task_metadata[task_id]
                    logger.debug(f"Cleaned up metadata for old task {task_id}")

                if tasks_to_remove:
                    logger.info(
                        f"Cleaned up metadata for {len(tasks_to_remove)} old tasks"
                    )

            except asyncio.CancelledError:
                logger.info("Periodic cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a bit before retrying on error

    async def cleanup(self):
        """Cleanup resources and cancel remaining tasks"""
        logger.info("Shutting down BackgroundTaskManager")

        # Cancel the periodic cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel all active tasks
        for task_id, task in list(self.active_tasks.items()):
            logger.info(f"Cancelling active task {task_id} during cleanup")
            task.cancel()

            # Update metadata
            if task_id in self.task_metadata:
                self.task_metadata[task_id]["status"] = "cancelled"

        # Wait for all tasks to complete or be cancelled
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)

        # Clear collections
        self.active_tasks.clear()
        self.task_metadata.clear()

        logger.info("BackgroundTaskManager shutdown complete")


# Global instance
_task_manager: BackgroundTaskManager | None = None


def get_task_manager() -> BackgroundTaskManager:
    """Get or create the global task manager instance"""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager()
    return _task_manager


async def cleanup_task_manager():
    """Cleanup the global task manager instance"""
    global _task_manager
    if _task_manager:
        await _task_manager.cleanup()
        _task_manager = None
