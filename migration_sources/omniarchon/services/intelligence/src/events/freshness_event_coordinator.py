"""
Event-Driven Freshness Coordinator

Coordinates automatic freshness analysis triggered by document update events.
Integrates with the omnibase event system and LlamaIndex workflows.
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID, uuid4

# Freshness system imports
from freshness import DocumentFreshnessMonitor, FreshnessDatabase
from freshness.models import FreshnessAnalysisRequest
from src.events.models.document_update_event import (
    DocumentUpdateEvent,
    DocumentUpdateType,
    FreshnessAnalysisRequestedEvent,
    FreshnessAnalysisTrigger,
)

logger = logging.getLogger(__name__)


class FreshnessEventCoordinator:
    """
    Coordinates event-driven freshness analysis and re-ranking.

    This coordinator listens for document update events and automatically
    triggers freshness analysis workflows using LlamaIndex workflows.
    """

    def __init__(
        self,
        freshness_monitor: DocumentFreshnessMonitor,
        freshness_database: FreshnessDatabase,
        batch_timeout_seconds: int = 30,
        max_batch_size: int = 100,
    ):
        """
        Initialize the freshness event coordinator.

        Args:
            freshness_monitor: Document freshness analysis engine
            freshness_database: Database for storing freshness data
            batch_timeout_seconds: Maximum time to wait for batch completion
            max_batch_size: Maximum number of documents in a batch
        """
        self.freshness_monitor = freshness_monitor
        self.freshness_database = freshness_database
        self.batch_timeout_seconds = batch_timeout_seconds
        self.max_batch_size = max_batch_size

        # Batch processing state
        self._pending_updates: Dict[str, DocumentUpdateEvent] = {}
        self._batch_timers: Dict[UUID, asyncio.Task] = {}
        self._processing_lock = asyncio.Lock()

        # Performance tracking
        self._stats = {
            "events_processed": 0,
            "analyses_triggered": 0,
            "batch_analyses": 0,
            "immediate_analyses": 0,
            "errors": 0,
        }
        self._start_time = datetime.now(timezone.utc)

        logger.info("FreshnessEventCoordinator initialized")

    async def handle_document_update_event(self, event: DocumentUpdateEvent) -> None:
        """
        Handle a document update event and trigger freshness analysis.

        Args:
            event: Document update event to process
        """
        try:
            self._stats["events_processed"] += 1

            logger.info(
                f"Processing document update event: {event.event_type} "
                f"for {event.document_path}"
            )

            # Handle different event types
            if event.event_type == DocumentUpdateType.DELETED:
                await self._handle_document_deletion(event)
                return

            if event.requires_immediate_analysis:
                await self._trigger_immediate_analysis(event)
            else:
                await self._add_to_batch(event)

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error processing document update event: {e}", exc_info=True)

    async def _handle_document_deletion(self, event: DocumentUpdateEvent) -> None:
        """Handle document deletion - remove from freshness database"""
        try:
            # Remove from freshness tracking
            await self.freshness_database.remove_document(event.document_path)

            # Trigger analysis of dependent documents
            if event.affected_dependencies:
                analysis_event = FreshnessAnalysisRequestedEvent(
                    trigger=FreshnessAnalysisTrigger.DEPENDENCY_CHANGE,
                    target_paths=event.affected_dependencies,
                    correlation_id=event.event_id,
                    requested_by="freshness_coordinator",
                    priority=3,  # Higher priority for dependency changes
                )
                await self._execute_freshness_analysis(analysis_event)

            logger.info(f"Processed document deletion: {event.document_path}")

        except Exception as e:
            logger.error(f"Error handling document deletion: {e}", exc_info=True)

    async def _trigger_immediate_analysis(self, event: DocumentUpdateEvent) -> None:
        """Trigger immediate freshness analysis for high-priority updates"""
        try:
            self._stats["immediate_analyses"] += 1

            analysis_event = FreshnessAnalysisRequestedEvent(
                trigger=FreshnessAnalysisTrigger.DOCUMENT_UPDATE,
                target_paths=[event.document_path],
                correlation_id=event.event_id,
                requested_by="freshness_coordinator",
                priority=event.priority,
                force_refresh=True,
            )

            await self._execute_freshness_analysis(analysis_event)

            logger.info(f"Triggered immediate analysis for {event.document_path}")

        except Exception as e:
            logger.error(f"Error in immediate analysis: {e}", exc_info=True)

    async def _add_to_batch(self, event: DocumentUpdateEvent) -> None:
        """Add document update to batch processing queue"""
        async with self._processing_lock:
            batch_id = event.batch_id or uuid4()

            # Add to pending updates
            self._pending_updates[event.document_path] = event

            # Set up batch timer if not already running
            if batch_id not in self._batch_timers:
                timer_task = asyncio.create_task(self._batch_timer(batch_id))
                self._batch_timers[batch_id] = timer_task

            # Trigger batch if we hit the size limit
            if len(self._pending_updates) >= self.max_batch_size:
                await self._process_batch(batch_id)

    async def _batch_timer(self, batch_id: UUID) -> None:
        """Timer for batch processing timeout"""
        try:
            await asyncio.sleep(self.batch_timeout_seconds)
            await self._process_batch(batch_id)
        except asyncio.CancelledError:
            pass  # Normal cancellation when batch is processed early
        except Exception as e:
            logger.error(f"Error in batch timer: {e}", exc_info=True)

    async def _process_batch(self, batch_id: UUID) -> None:
        """Process a batch of pending document updates"""
        async with self._processing_lock:
            if not self._pending_updates:
                return

            try:
                self._stats["batch_analyses"] += 1

                # Collect all pending paths
                target_paths = list(self._pending_updates.keys())
                events = list(self._pending_updates.values())

                # Clear pending updates
                self._pending_updates.clear()

                # Cancel timer
                if batch_id in self._batch_timers:
                    self._batch_timers[batch_id].cancel()
                    del self._batch_timers[batch_id]

                # Create batch analysis request
                analysis_event = FreshnessAnalysisRequestedEvent(
                    trigger=FreshnessAnalysisTrigger.DOCUMENT_UPDATE,
                    target_paths=target_paths,
                    correlation_id=batch_id,
                    requested_by="freshness_coordinator_batch",
                    priority=max(e.priority for e in events),
                    max_files=len(target_paths),
                )

                await self._execute_freshness_analysis(analysis_event)

                logger.info(f"Processed batch of {len(target_paths)} document updates")

            except Exception as e:
                logger.error(f"Error processing batch: {e}", exc_info=True)

    async def _execute_freshness_analysis(
        self, analysis_event: FreshnessAnalysisRequestedEvent
    ) -> None:
        """Execute freshness analysis based on the analysis event"""
        try:
            self._stats["analyses_triggered"] += 1

            # Convert event to freshness analysis request
            request = FreshnessAnalysisRequest(
                path=(
                    analysis_event.target_paths[0]
                    if len(analysis_event.target_paths) == 1
                    else "/"
                ),
                recursive=analysis_event.recursive,
                include_patterns=analysis_event.include_patterns,
                exclude_patterns=analysis_event.exclude_patterns,
                max_files=analysis_event.max_files,
                calculate_dependencies=analysis_event.calculate_dependencies,
            )

            # Execute analysis
            start_time = datetime.now(timezone.utc)

            if len(analysis_event.target_paths) == 1:
                # Single document analysis
                result = await self.freshness_monitor.analyze_document(
                    analysis_event.target_paths[0]
                )
                # Store result
                await self.freshness_database.store_document_freshness(result)

            else:
                # Batch analysis - analyze base directory
                base_path = self._find_common_base_path(analysis_event.target_paths)
                result = await self.freshness_monitor.analyze_directory(
                    directory_path=base_path,
                    recursive=request.recursive,
                    include_patterns=request.include_patterns,
                    exclude_patterns=request.exclude_patterns,
                    max_files=request.max_files,
                )

                # Store result
                await self.freshness_database.store_analysis(result)

            # TODO: Implement event publishing when Kafka producer is integrated
            # Completion events and re-ranking events should be published to event bus

            analysis_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"Completed freshness analysis of {len(analysis_event.target_paths)} paths "
                f"in {analysis_time:.2f}s"
            )

        except Exception as e:
            logger.error(f"Error executing freshness analysis: {e}", exc_info=True)
            # TODO: Publish error completion event when Kafka producer is integrated

    # TODO: Implement _trigger_reranking when Kafka producer is integrated
    # This method should:
    # 1. Get freshness scores for updated documents
    # 2. Create and publish DocumentRerankingRequestedEvent
    # 3. Integrate with knowledge graph and search index updates

    def _find_common_base_path(self, paths: List[str]) -> str:
        """Find common base path for a list of file paths"""
        if not paths:
            return "/"

        if len(paths) == 1:
            return str(Path(paths[0]).parent)

        # Find common prefix
        common_parts = []
        path_parts = [Path(p).parts for p in paths]

        for i in range(min(len(parts) for parts in path_parts)):
            part_set = set(parts[i] for parts in path_parts)
            if len(part_set) == 1:
                common_parts.append(list(part_set)[0])
            else:
                break

        return str(Path(*common_parts)) if common_parts else "/"

    async def get_stats(self) -> Dict[str, Any]:
        """Get coordinator performance statistics"""
        async with self._processing_lock:
            return {
                **self._stats,
                "pending_updates": len(self._pending_updates),
                "active_batches": len(self._batch_timers),
                "uptime_seconds": (
                    datetime.now(timezone.utc) - self._start_time
                ).total_seconds(),
            }

    async def shutdown(self) -> None:
        """Graceful shutdown of the coordinator"""
        try:
            # Cancel all batch timers
            for timer_task in self._batch_timers.values():
                timer_task.cancel()

            # Process any remaining batches
            if self._pending_updates:
                await self._process_batch(uuid4())

            logger.info("FreshnessEventCoordinator shutdown complete")

        except Exception as e:
            logger.error(f"Error during coordinator shutdown: {e}", exc_info=True)
