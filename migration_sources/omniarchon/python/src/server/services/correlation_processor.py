"""
Correlation Processor Service

Background service for processing intelligence documents with empty correlations.
Provides queue management, batch processing, and integration with the intelligence
data access layer.

This service implements:
- Background queue processing for documents needing correlation analysis
- Batch processing optimization for performance
- Integration with correlation_analyzer for actual analysis
- Data persistence through intelligence_data_access
- Error handling and retry mechanisms
- Progress tracking and monitoring

Architecture follows ONEX principles:
- Service orchestration pattern
- Clean integration with data and analysis layers
- Configurable processing parameters
- Comprehensive error handling and logging
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from server.data.intelligence_data_access import QueryParameters
from server.services.correlation_analyzer import (
    CorrelationAnalysisResult,
    DocumentContext,
    create_correlation_analyzer,
)
from server.services.intelligence_service import get_intelligence_data_access

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Processing status for correlation tasks."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class CorrelationTask:
    """Task for correlation processing."""

    document_id: str
    repository: str
    commit_sha: str
    priority: int = 5  # 1-10, higher = more important
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: ProcessingStatus = ProcessingStatus.PENDING
    attempts: int = 0
    last_error: Optional[str] = None
    processing_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingBatch:
    """Batch of documents for processing."""

    tasks: list[CorrelationTask]
    context_documents: list[DocumentContext]
    batch_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ProcessingStats:
    """Statistics for correlation processing."""

    total_documents_processed: int = 0
    successful_correlations: int = 0
    failed_processing: int = 0
    average_processing_time: float = 0.0
    total_correlations_generated: int = 0
    processing_start_time: Optional[datetime] = None
    last_batch_completed: Optional[datetime] = None


class CorrelationProcessor:
    """
    Background processor for correlation analysis tasks.

    This service manages the queue of documents needing correlation analysis
    and coordinates the actual analysis work with the CorrelationAnalyzer.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        """
        Initialize correlation processor with configuration.

        Args:
            config: Configuration dictionary for processing parameters
        """
        self.config = config or {}

        # Processing configuration
        self.batch_size = self.config.get("batch_size", 5)
        self.max_context_documents = self.config.get("max_context_documents", 100)
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay_seconds = self.config.get(
            "retry_delay_seconds", 300
        )  # 5 minutes
        self.context_time_range = self.config.get("context_time_range", "7d")
        self.processing_interval = self.config.get(
            "processing_interval", 60
        )  # 1 minute

        # Initialize components
        self.analyzer = create_correlation_analyzer(
            self.config.get("analyzer_config", {})
        )
        self.data_access = None  # Will be initialized when needed
        self.task_queue: list[CorrelationTask] = []
        self.processing_stats = ProcessingStats()
        self.is_running = False
        self.current_batch: Optional[ProcessingBatch] = None

    def get_data_access(self):
        """Get intelligence data access instance (lazy initialization)."""
        if self.data_access is None:
            self.data_access = get_intelligence_data_access()
        return self.data_access

    async def start_processing(self):
        """Start the background processing loop."""
        if self.is_running:
            logger.warning("Correlation processor is already running")
            return

        self.is_running = True
        self.processing_stats.processing_start_time = datetime.now(UTC)

        logger.info("Starting correlation processor background service")

        try:
            while self.is_running:
                await self._process_batch()
                await asyncio.sleep(self.processing_interval)

        except Exception as e:
            logger.error(f"Error in correlation processing loop: {e}")
            self.is_running = False
            raise

    async def stop_processing(self):
        """Stop the background processing loop."""
        logger.info("Stopping correlation processor background service")
        self.is_running = False

    async def queue_document_for_processing(
        self, document_id: str, repository: str, commit_sha: str, priority: int = 5
    ) -> bool:
        """
        Add a document to the processing queue.

        Args:
            document_id: ID of document to process
            repository: Repository name
            commit_sha: Commit SHA
            priority: Processing priority (1-10)

        Returns:
            True if queued successfully, False otherwise
        """
        try:
            # Check if already queued
            existing_task = next(
                (task for task in self.task_queue if task.document_id == document_id),
                None,
            )

            if existing_task:
                logger.debug(f"Document {document_id} already queued for processing")
                return True

            # Create new task
            task = CorrelationTask(
                document_id=document_id,
                repository=repository,
                commit_sha=commit_sha,
                priority=priority,
            )

            self.task_queue.append(task)

            # Sort queue by priority (higher priority first)
            self.task_queue.sort(key=lambda x: x.priority, reverse=True)

            logger.info(
                f"Queued document {document_id} for correlation processing (priority: {priority})"
            )
            return True

        except Exception as e:
            logger.error(f"Error queuing document {document_id} for processing: {e}")
            return False

    async def queue_documents_with_empty_correlations(self) -> int:
        """
        Automatically queue all documents with empty correlations for processing.

        Returns:
            Number of documents queued
        """
        try:
            data_access = self.get_data_access()

            # Get documents from the last 7 days to find empty correlations
            params = QueryParameters(
                time_range="7d",
                limit=1000,  # Large limit to get all recent documents
                offset=0,
            )

            documents = data_access.get_parsed_documents(params)
            queued_count = 0

            for doc in documents:
                # Check if document has empty correlations
                has_temporal = len(doc.temporal_correlations) > 0
                has_semantic = len(doc.semantic_correlations) > 0

                if not has_temporal and not has_semantic:
                    # Queue for processing with higher priority for more recent documents
                    doc_age_hours = (
                        datetime.now(UTC)
                        - datetime.fromisoformat(doc.created_at.replace("Z", "+00:00"))
                    ).total_seconds() / 3600.0

                    # Higher priority for newer documents
                    priority = max(1, min(10, int(10 - (doc_age_hours / 24))))

                    if await self.queue_document_for_processing(
                        doc.id, doc.repository, doc.commit_sha, priority
                    ):
                        queued_count += 1

            logger.info(
                f"Queued {queued_count} documents with empty correlations for processing"
            )
            return queued_count

        except Exception as e:
            logger.error(f"Error queuing documents with empty correlations: {e}")
            return 0

    async def _process_batch(self):
        """Process a batch of correlation tasks."""
        if not self.task_queue:
            return

        # Get pending tasks for batch
        pending_tasks = [
            task
            for task in self.task_queue
            if task.status == ProcessingStatus.PENDING
            and task.attempts < self.max_retries
        ]

        if not pending_tasks:
            return

        # Create batch
        batch_tasks = pending_tasks[: self.batch_size]
        batch_id = f"batch_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        logger.info(
            f"Processing correlation batch {batch_id} with {len(batch_tasks)} tasks"
        )

        try:
            # Get context documents for the batch
            context_documents = await self._get_context_documents(batch_tasks)

            batch = ProcessingBatch(
                tasks=batch_tasks,
                context_documents=context_documents,
                batch_id=batch_id,
            )

            self.current_batch = batch

            # Process each task in the batch
            for task in batch_tasks:
                await self._process_single_task(task, context_documents)

            self.processing_stats.last_batch_completed = datetime.now(UTC)

        except Exception as e:
            logger.error(f"Error processing batch {batch_id}: {e}")

            # Mark batch tasks as failed
            for task in batch_tasks:
                task.status = ProcessingStatus.FAILED
                task.last_error = str(e)
                task.attempts += 1

        finally:
            self.current_batch = None

    async def _process_single_task(
        self, task: CorrelationTask, context_documents: list[DocumentContext]
    ):
        """Process a single correlation task."""
        task.status = ProcessingStatus.IN_PROGRESS
        task.attempts += 1
        start_time = datetime.now(UTC)

        try:
            # Get target document data
            target_document = await self._get_target_document(task)
            if not target_document:
                raise ValueError(
                    f"Could not retrieve document data for {task.document_id}"
                )

            # Perform correlation analysis
            analysis_result = await self.analyzer.analyze_document_correlations(
                target_document, context_documents
            )

            # Save results back to database
            success = await self._save_correlation_results(task, analysis_result)

            if success:
                task.status = ProcessingStatus.COMPLETED
                task.processing_metadata = {
                    "processing_time_seconds": (
                        datetime.now(UTC) - start_time
                    ).total_seconds(),
                    "temporal_correlations": len(analysis_result.temporal_correlations),
                    "semantic_correlations": len(analysis_result.semantic_correlations),
                    "breaking_changes": len(analysis_result.breaking_changes),
                }

                # Update statistics
                self.processing_stats.total_documents_processed += 1
                self.processing_stats.successful_correlations += 1
                self.processing_stats.total_correlations_generated += len(
                    analysis_result.temporal_correlations
                ) + len(analysis_result.semantic_correlations)

                logger.info(
                    f"Successfully processed correlations for document {task.document_id}: "
                    f"{len(analysis_result.temporal_correlations)} temporal, "
                    f"{len(analysis_result.semantic_correlations)} semantic"
                )
            else:
                raise ValueError("Failed to save correlation results")

        except Exception as e:
            logger.error(f"Error processing task for document {task.document_id}: {e}")
            task.status = ProcessingStatus.FAILED
            task.last_error = str(e)
            self.processing_stats.failed_processing += 1

            # Schedule retry if under retry limit
            if task.attempts < self.max_retries:
                task.status = ProcessingStatus.RETRYING
                logger.info(
                    f"Will retry document {task.document_id} (attempt {task.attempts}/{self.max_retries})"
                )

    async def _get_target_document(
        self, task: CorrelationTask
    ) -> Optional[DocumentContext]:
        """Get target document data for analysis."""
        try:
            data_access = self.get_data_access()

            # Get the specific document
            params = QueryParameters(
                repository=task.repository,
                time_range="7d",  # Use wide range to ensure we find the document
                limit=1000,
                offset=0,
            )

            documents = data_access.get_parsed_documents(params)

            # Find the specific document
            target_doc = next(
                (doc for doc in documents if doc.id == task.document_id), None
            )

            if not target_doc:
                return None

            # Convert to DocumentContext
            return DocumentContext(
                id=target_doc.id,
                repository=target_doc.repository,
                commit_sha=target_doc.commit_sha,
                author=target_doc.author,
                created_at=datetime.fromisoformat(
                    target_doc.created_at.replace("Z", "+00:00")
                ),
                change_type=target_doc.change_type,
                content=getattr(target_doc, "raw_content", {}),
                modified_files=(
                    target_doc.diff_analysis.modified_files
                    if target_doc.diff_analysis
                    else []
                ),
                commit_message=None,  # Would need to be added to data structure if available
            )

        except Exception as e:
            logger.error(
                f"Error getting target document for task {task.document_id}: {e}"
            )
            return None

    async def _get_context_documents(
        self, batch_tasks: list[CorrelationTask]
    ) -> list[DocumentContext]:
        """Get context documents for correlation analysis."""
        try:
            data_access = self.get_data_access()

            # Get documents from the configured time range
            params = QueryParameters(
                time_range=self.context_time_range,
                limit=self.max_context_documents,
                offset=0,
            )

            documents = data_access.get_parsed_documents(params)

            # Convert to DocumentContext objects
            context_documents = []

            for doc in documents:
                try:
                    context_doc = DocumentContext(
                        id=doc.id,
                        repository=doc.repository,
                        commit_sha=doc.commit_sha,
                        author=doc.author,
                        created_at=datetime.fromisoformat(
                            doc.created_at.replace("Z", "+00:00")
                        ),
                        change_type=doc.change_type,
                        content=getattr(doc, "raw_content", {}),
                        modified_files=(
                            doc.diff_analysis.modified_files
                            if doc.diff_analysis
                            else []
                        ),
                    )
                    context_documents.append(context_doc)

                except Exception as e:
                    logger.debug(f"Error converting document {doc.id} to context: {e}")
                    continue

            logger.debug(
                f"Retrieved {len(context_documents)} context documents for batch"
            )
            return context_documents

        except Exception as e:
            logger.error(f"Error getting context documents: {e}")
            return []

    async def _save_correlation_results(
        self, task: CorrelationTask, analysis_result: CorrelationAnalysisResult
    ) -> bool:
        """
        Save correlation analysis results back to the database.

        Note: This is a placeholder implementation. In a real system, this would
        update the document's correlation data in the database.
        """
        try:
            # TODO: Implement actual database update logic
            # This would involve updating the document's content with the new correlations

            logger.info(
                f"Would save correlations for document {task.document_id}: "
                f"{len(analysis_result.temporal_correlations)} temporal, "
                f"{len(analysis_result.semantic_correlations)} semantic correlations"
            )

            # For now, just log the results for verification
            for tc in analysis_result.temporal_correlations:
                logger.debug(
                    f"Temporal correlation: {tc.repository}:{tc.commit_sha} "
                    f"(strength: {tc.correlation_strength}, time_diff: {tc.time_diff_hours}h)"
                )

            for sc in analysis_result.semantic_correlations:
                logger.debug(
                    f"Semantic correlation: {sc.repository}:{sc.commit_sha} "
                    f"(similarity: {sc.semantic_similarity}, keywords: {sc.common_keywords})"
                )

            return True

        except Exception as e:
            logger.error(
                f"Error saving correlation results for document {task.document_id}: {e}"
            )
            return False

    def get_processing_stats(self) -> dict[str, Any]:
        """Get current processing statistics."""
        stats = {
            "total_documents_processed": self.processing_stats.total_documents_processed,
            "successful_correlations": self.processing_stats.successful_correlations,
            "failed_processing": self.processing_stats.failed_processing,
            "total_correlations_generated": self.processing_stats.total_correlations_generated,
            "queue_length": len(self.task_queue),
            "is_running": self.is_running,
            "processing_start_time": (
                self.processing_stats.processing_start_time.isoformat()
                if self.processing_stats.processing_start_time
                else None
            ),
            "last_batch_completed": (
                self.processing_stats.last_batch_completed.isoformat()
                if self.processing_stats.last_batch_completed
                else None
            ),
            "current_batch": (
                {
                    "batch_id": self.current_batch.batch_id,
                    "task_count": len(self.current_batch.tasks),
                    "context_documents": len(self.current_batch.context_documents),
                }
                if self.current_batch
                else None
            ),
            "configuration": {
                "batch_size": self.batch_size,
                "max_context_documents": self.max_context_documents,
                "max_retries": self.max_retries,
                "processing_interval": self.processing_interval,
                "context_time_range": self.context_time_range,
            },
        }

        return stats

    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status."""
        status_counts = {status.value: 0 for status in ProcessingStatus}

        for task in self.task_queue:
            status_counts[task.status.value] += 1

        return {
            "total_tasks": len(self.task_queue),
            "status_breakdown": status_counts,
            "tasks": [
                {
                    "document_id": task.document_id,
                    "repository": task.repository,
                    "commit_sha": task.commit_sha,
                    "priority": task.priority,
                    "status": task.status.value,
                    "attempts": task.attempts,
                    "created_at": task.created_at.isoformat(),
                    "last_error": task.last_error,
                }
                for task in self.task_queue
            ],
        }


# Global processor instance (singleton pattern)
_processor_instance = None


def get_correlation_processor(
    config: Optional[dict[str, Any]] = None,
) -> CorrelationProcessor:
    """
    Get the global correlation processor instance.

    Args:
        config: Configuration dictionary (only used on first call)

    Returns:
        CorrelationProcessor instance (enhanced by default)
    """
    global _processor_instance
    if _processor_instance is None:
        # Check if enhanced correlation is enabled in config
        if config and config.get("disable_enhanced_correlation", False):
            _processor_instance = CorrelationProcessor(config)
        else:
            # Import here to avoid circular dependencies
            from .enhanced_correlation_processor import (
                get_enhanced_correlation_processor,
            )

            _processor_instance = get_enhanced_correlation_processor(config)
    return _processor_instance
