"""
Repository Crawler Event Handler

Handles REPOSITORY_SCAN_REQUESTED events and publishes REPOSITORY_SCAN_COMPLETED/FAILED responses.
Implements file discovery, pattern matching, and batch publishing to document-indexing-requested topic.

Event Flow:
    1. Consume REPOSITORY_SCAN_REQUESTED event
    2. Discover files in repository matching patterns
    3. Filter files by exclude patterns
    4. Publish batches of DOCUMENT_INDEX_REQUESTED events
    5. Publish REPOSITORY_SCAN_COMPLETED (success) or REPOSITORY_SCAN_FAILED (error)

Topics:
    - Request: dev.archon-intelligence.intelligence.repository-scan-requested.v1
    - Completed: dev.archon-intelligence.intelligence.repository-scan-completed.v1
    - Failed: dev.archon-intelligence.intelligence.repository-scan-failed.v1
    - Document Index: dev.archon-intelligence.intelligence.document-index-requested.v1

Created: 2025-10-22
Purpose: Event-driven repository crawling and batch document indexing
"""

import logging
import os
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from src.events.hybrid_event_router import HybridEventRouter
from src.events.models.repository_crawler_events import (
    EnumCrawlerErrorCode,
    EnumRepositoryCrawlerEventType,
    EnumScanScope,
    create_completed_event,
    create_failed_event,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class RepositoryCrawlerHandler(BaseResponsePublisher):
    """
    Handle REPOSITORY_SCAN_REQUESTED events and publish scan results.

    This handler implements the Repository Crawler pattern, consuming
    repository scan requests from the event bus and publishing results
    along with batch DOCUMENT_INDEX_REQUESTED events.

    Event Flow:
        1. Consume REPOSITORY_SCAN_REQUESTED event
        2. Discover files in repository
        3. Filter by patterns
        4. Batch publish DOCUMENT_INDEX_REQUESTED events
        5. Publish REPOSITORY_SCAN_COMPLETED or REPOSITORY_SCAN_FAILED

    Topics:
        - Request: dev.archon-intelligence.intelligence.repository-scan-requested.v1
        - Completed: dev.archon-intelligence.intelligence.repository-scan-completed.v1
        - Failed: dev.archon-intelligence.intelligence.repository-scan-failed.v1
        - Document Index: dev.archon-intelligence.intelligence.document-index-requested.v1
    """

    # Topic constants
    REQUEST_TOPIC = "dev.archon-intelligence.intelligence.repository-scan-requested.v1"
    COMPLETED_TOPIC = (
        "dev.archon-intelligence.intelligence.repository-scan-completed.v1"
    )
    FAILED_TOPIC = "dev.archon-intelligence.intelligence.repository-scan-failed.v1"
    DOCUMENT_INDEX_TOPIC = (
        "dev.archon-intelligence.intelligence.document-index-requested.v1"
    )

    def __init__(self):
        """Initialize Repository Crawler handler."""
        super().__init__()
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "total_files_discovered": 0,
            "total_files_published": 0,
            "total_batches_created": 0,
        }

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if event type is REPOSITORY_SCAN_REQUESTED
        """
        return event_type in [
            EnumRepositoryCrawlerEventType.REPOSITORY_SCAN_REQUESTED.value,
            "REPOSITORY_SCAN_REQUESTED",
            "intelligence.repository-scan-requested",
            "omninode.intelligence.event.repository_scan_requested.v1",  # Full event type from Kafka
        ]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle REPOSITORY_SCAN_REQUESTED event.

        Discovers files in repository, filters by patterns, and publishes
        batch DOCUMENT_INDEX_REQUESTED events.

        Args:
            event: Event envelope with REPOSITORY_SCAN_REQUESTED payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        correlation_id = None

        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)

            # Extract required fields from payload
            repository_path = payload.get("repository_path")
            project_id = payload.get("project_id")
            scan_scope = payload.get("scan_scope", "FULL")
            file_patterns = payload.get(
                "file_patterns", ["**/*.py", "**/*.ts", "**/*.rs", "**/*.go"]
            )
            exclude_patterns = payload.get(
                "exclude_patterns",
                ["**/__pycache__/**", "**/node_modules/**", "**/.git/**"],
            )
            batch_size = payload.get("batch_size", 50)
            indexing_options = payload.get("indexing_options", {})

            # Validate required fields
            if not repository_path:
                logger.error(
                    f"Missing repository_path in REPOSITORY_SCAN_REQUESTED event {correlation_id}"
                )
                await self._publish_failed_response(
                    correlation_id=correlation_id,
                    repository_path="unknown",
                    project_id=project_id,
                    error_code=EnumCrawlerErrorCode.INVALID_INPUT,
                    error_message="Missing required field: repository_path",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["events_failed"] += 1
                return False

            if not project_id:
                logger.error(
                    f"Missing project_id in REPOSITORY_SCAN_REQUESTED event {correlation_id}"
                )
                await self._publish_failed_response(
                    correlation_id=correlation_id,
                    repository_path=repository_path,
                    project_id=None,
                    error_code=EnumCrawlerErrorCode.INVALID_INPUT,
                    error_message="Missing required field: project_id",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["events_failed"] += 1
                return False

            logger.info(
                f"Processing REPOSITORY_SCAN_REQUESTED | correlation_id={correlation_id} | "
                f"repository_path={repository_path} | project_id={project_id} | "
                f"scan_scope={scan_scope} | batch_size={batch_size}"
            )

            # Perform repository scan
            scan_result = await self._scan_repository(
                repository_path=repository_path,
                project_id=project_id,
                scan_scope=scan_scope,
                file_patterns=file_patterns,
                exclude_patterns=exclude_patterns,
                batch_size=batch_size,
                indexing_options=indexing_options,
                correlation_id=correlation_id,
            )

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed_response(
                correlation_id=correlation_id,
                scan_result=scan_result,
                repository_path=repository_path,
                project_id=project_id,
                scan_scope=scan_scope,
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self.metrics["total_files_discovered"] += scan_result["files_discovered"]
            self.metrics["total_files_published"] += scan_result["files_published"]
            self.metrics["total_batches_created"] += scan_result["batches_created"]

            logger.info(
                f"REPOSITORY_SCAN_COMPLETED published | correlation_id={correlation_id} | "
                f"files_discovered={scan_result['files_discovered']} | "
                f"files_published={scan_result['files_published']} | "
                f"processing_time_ms={duration_ms:.2f}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Repository crawler handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            # Publish error response
            try:
                if correlation_id:
                    # Extract payload data for error response (may not be available if early failure)
                    payload = self._get_payload(event) if event else {}
                    repository_path = payload.get("repository_path", "unknown")
                    project_id = payload.get("project_id")

                    duration_ms = (time.perf_counter() - start_time) * 1000
                    await self._publish_failed_response(
                        correlation_id=correlation_id,
                        repository_path=repository_path,
                        project_id=project_id,
                        error_code=EnumCrawlerErrorCode.INTERNAL_ERROR,
                        error_message=f"Repository scan failed: {str(e)}",
                        retry_allowed=True,
                        processing_time_ms=duration_ms,
                        error_details={"exception_type": type(e).__name__},
                    )
            except Exception as publish_error:
                logger.error(
                    f"Failed to publish error response | correlation_id={correlation_id} | "
                    f"error={publish_error}",
                    exc_info=True,
                )

            self.metrics["events_failed"] += 1
            return False

    async def _scan_repository(
        self,
        repository_path: str,
        project_id: str,
        scan_scope: str,
        file_patterns: list[str],
        exclude_patterns: list[str],
        batch_size: int,
        indexing_options: Dict[str, Any],
        correlation_id: UUID,
    ) -> Dict[str, Any]:
        """
        Scan repository and discover files matching patterns.

        Args:
            repository_path: Path to repository
            project_id: Project identifier
            scan_scope: Scope of scan (FULL, INCREMENTAL, SELECTIVE)
            file_patterns: Glob patterns for files to include
            exclude_patterns: Glob patterns for files to exclude
            batch_size: Number of files per batch
            indexing_options: Options to pass to document indexing
            correlation_id: Correlation ID for tracking

        Returns:
            Scan result dictionary with statistics

        Raises:
            FileNotFoundError: If repository path does not exist
            PermissionError: If insufficient permissions
            ValueError: If patterns are invalid
        """
        # Verify repository exists
        if not os.path.exists(repository_path):
            raise FileNotFoundError(f"Repository not found at path: {repository_path}")

        if not os.path.isdir(repository_path):
            raise ValueError(f"Repository path is not a directory: {repository_path}")

        logger.info(f"Discovering files in repository: {repository_path}")

        # Discover files
        discovered_files = self._discover_files(
            repository_path=repository_path,
            file_patterns=file_patterns,
            exclude_patterns=exclude_patterns,
        )

        logger.info(f"Discovered {len(discovered_files)} files matching patterns")

        # Check if any files found
        if len(discovered_files) == 0:
            logger.warning(
                f"No files found matching patterns in repository: {repository_path}"
            )
            return {
                "files_discovered": 0,
                "files_published": 0,
                "files_skipped": 0,
                "batches_created": 0,
                "file_summaries": [],
            }

        # Publish batches
        files_published, batches_created = await self._publish_batches(
            files=discovered_files,
            project_id=project_id,
            batch_size=batch_size,
            indexing_options=indexing_options,
            correlation_id=correlation_id,
        )

        # Create file summaries (limit to first 100 for performance)
        file_summaries = [
            {
                "path": file_info["relative_path"],
                "size": file_info["size"],
                "language": file_info["language"],
            }
            for file_info in discovered_files[:100]
        ]

        return {
            "files_discovered": len(discovered_files),
            "files_published": files_published,
            "files_skipped": len(discovered_files) - files_published,
            "batches_created": batches_created,
            "file_summaries": file_summaries,
        }

    def _discover_files(
        self,
        repository_path: str,
        file_patterns: list[str],
        exclude_patterns: list[str],
    ) -> list[Dict[str, Any]]:
        """
        Discover all matching files in repository.

        Args:
            repository_path: Path to repository
            file_patterns: Glob patterns for files to include
            exclude_patterns: Glob patterns for files to exclude

        Returns:
            List of file information dictionaries
        """
        discovered_files = []

        for root, dirs, files in os.walk(repository_path):
            # Filter directories (in-place modification to prevent descent)
            dirs[:] = [
                d
                for d in dirs
                if not any(
                    fnmatch(os.path.join(root, d), pattern)
                    for pattern in exclude_patterns
                )
            ]

            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, repository_path)

                # Check if matches include patterns
                if not any(
                    fnmatch(relative_path, pattern) for pattern in file_patterns
                ):
                    continue

                # Check if excluded
                if any(fnmatch(relative_path, pattern) for pattern in exclude_patterns):
                    continue

                try:
                    file_size = os.path.getsize(file_path)
                    language = self._detect_language(file_path)

                    discovered_files.append(
                        {
                            "absolute_path": file_path,
                            "relative_path": relative_path,
                            "size": file_size,
                            "language": language,
                        }
                    )
                except (OSError, PermissionError) as e:
                    logger.warning(f"Failed to access file {file_path}: {e}")
                    continue

        return discovered_files

    def _detect_language(self, file_path: str) -> str:
        """
        Detect programming language from file extension.

        Args:
            file_path: Path to file

        Returns:
            Programming language string
        """
        ext_mapping = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".js": "javascript",
            ".jsx": "javascript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
        }
        ext = Path(file_path).suffix.lower()
        return ext_mapping.get(ext, "unknown")

    async def _publish_batches(
        self,
        files: list[Dict[str, Any]],
        project_id: str,
        batch_size: int,
        indexing_options: Dict[str, Any],
        correlation_id: UUID,
    ) -> tuple[int, int]:
        """
        Publish files in batches as DOCUMENT_INDEX_REQUESTED events.

        Args:
            files: List of file information dictionaries
            project_id: Project identifier
            batch_size: Number of files per batch
            indexing_options: Options to pass to document indexing
            correlation_id: Correlation ID for tracking

        Returns:
            Tuple of (files_published_count, batches_created_count)
        """
        await self._ensure_router_initialized()

        published_count = 0
        batches_created = 0

        for i in range(0, len(files), batch_size):
            batch = files[i : i + batch_size]
            batch_num = i // batch_size + 1

            for file_info in batch:
                try:
                    # Read file content
                    with open(
                        file_info["absolute_path"],
                        "r",
                        encoding="utf-8",
                        errors="ignore",
                    ) as f:
                        content = f.read()

                    # Create DOCUMENT_INDEX_REQUESTED event
                    # Import here to avoid circular dependency
                    from events.models.document_indexing_events import (
                        create_request_event as create_doc_index_event,
                    )

                    event_envelope = create_doc_index_event(
                        source_path=file_info["relative_path"],
                        content=content,
                        language=file_info["language"],
                        project_id=project_id,
                        indexing_options=indexing_options,
                        correlation_id=correlation_id,
                    )

                    # Publish to document-index-requested topic
                    await self._router.publish(
                        topic=self.DOCUMENT_INDEX_TOPIC,
                        event=event_envelope,
                        key=str(correlation_id),
                    )

                    published_count += 1

                except Exception as e:
                    logger.warning(
                        f"Failed to publish document index request for {file_info['relative_path']}: {e}"
                    )
                    continue

            batches_created += 1
            logger.info(
                f"Published batch {batch_num}/{(len(files) + batch_size - 1) // batch_size}: "
                f"{len(batch)} files"
            )

        return published_count, batches_created

    async def _publish_completed_response(
        self,
        correlation_id: UUID,
        scan_result: Dict[str, Any],
        repository_path: str,
        project_id: str,
        scan_scope: str,
        processing_time_ms: float,
    ) -> None:
        """
        Publish REPOSITORY_SCAN_COMPLETED event.

        Args:
            correlation_id: Correlation ID from request
            scan_result: Scan result dictionary
            repository_path: Repository path scanned
            project_id: Project identifier
            scan_scope: Scope of scan performed
            processing_time_ms: Processing time in milliseconds
        """
        try:
            await self._ensure_router_initialized()

            # Convert scan_scope string to enum
            try:
                scope_enum = EnumScanScope(scan_scope)
            except ValueError:
                scope_enum = EnumScanScope.FULL

            # Create completed event using helper (returns ONEX-compliant envelope)
            event_envelope = create_completed_event(
                repository_path=repository_path,
                project_id=project_id,
                scan_scope=scope_enum,
                files_discovered=scan_result["files_discovered"],
                files_published=scan_result["files_published"],
                batches_created=scan_result["batches_created"],
                processing_time_ms=processing_time_ms,
                correlation_id=correlation_id,
                files_skipped=scan_result.get("files_skipped", 0),
                file_summaries=scan_result.get("file_summaries", []),
            )

            # Publish the ONEX-compliant envelope directly
            await self._router.publish(
                topic=self.COMPLETED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.info(
                f"Published REPOSITORY_SCAN_COMPLETED | topic={self.COMPLETED_TOPIC} | "
                f"correlation_id={correlation_id} | files_discovered={scan_result['files_discovered']}"
            )

        except Exception as e:
            logger.error(f"Failed to publish completed response: {e}", exc_info=True)
            raise

    async def _publish_failed_response(
        self,
        correlation_id: UUID,
        repository_path: str,
        project_id: Optional[str],
        error_code: EnumCrawlerErrorCode,
        error_message: str,
        retry_allowed: bool = False,
        processing_time_ms: float = 0.0,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish REPOSITORY_SCAN_FAILED event.

        Args:
            correlation_id: Correlation ID from request
            repository_path: Repository path that failed
            project_id: Optional project identifier
            error_code: Error code enum value
            error_message: Human-readable error message
            retry_allowed: Whether the operation can be retried
            processing_time_ms: Time taken before failure
            error_details: Optional error context
        """
        try:
            await self._ensure_router_initialized()

            # Create failed event using helper (returns ONEX-compliant envelope)
            event_envelope = create_failed_event(
                repository_path=repository_path,
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                project_id=project_id,
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
                error_details=error_details or {},
            )

            # Publish the ONEX-compliant envelope directly
            await self._router.publish(
                topic=self.FAILED_TOPIC,
                event=event_envelope,
                key=str(correlation_id),
            )

            logger.warning(
                f"Published REPOSITORY_SCAN_FAILED | topic={self.FAILED_TOPIC} | "
                f"correlation_id={correlation_id} | error_code={error_code.value} | "
                f"error_message={error_message}"
            )

        except Exception as e:
            logger.error(f"Failed to publish failed response: {e}", exc_info=True)
            raise

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "RepositoryCrawlerHandler"

    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics."""
        total_events = self.metrics["events_handled"] + self.metrics["events_failed"]
        success_rate = (
            self.metrics["events_handled"] / total_events if total_events > 0 else 1.0
        )
        avg_processing_time = (
            self.metrics["total_processing_time_ms"] / self.metrics["events_handled"]
            if self.metrics["events_handled"] > 0
            else 0.0
        )

        return {
            **self.metrics,
            "success_rate": success_rate,
            "avg_processing_time_ms": avg_processing_time,
            "handler_name": self.get_handler_name(),
        }
