"""
Batch Processor for Pattern Ingestion
======================================

Parallel processing of multiple repositories with error recovery and progress tracking.

Features:
- Parallel repository processing using asyncio
- Progress tracking with real-time updates
- Error recovery (resume from failures)
- Configurable concurrency limits
- Comprehensive metrics aggregation

ONEX Compliance: Yes
Migration Date: 2025-10-28
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from pattern_ingestion.ingestion_pipeline import IngestionMetrics, IngestionPipeline
from pattern_ingestion.pr_intelligence import (
    PRIntelligenceExtractor,
    PRIntelligenceMetrics,
)

logger = logging.getLogger(__name__)


@dataclass
class BatchMetrics:
    """Aggregated metrics for batch processing."""

    # Repository ingestion metrics
    repos_processed: int = 0
    repos_failed: int = 0
    total_files_processed: int = 0
    total_patterns_found: int = 0
    total_patterns_inserted: int = 0
    total_patterns_updated: int = 0
    total_errors: int = 0

    # PR intelligence metrics
    prs_analyzed: int = 0
    prs_failed: int = 0
    total_mentions_extracted: int = 0
    total_mentions_stored: int = 0

    # Performance metrics
    total_processing_time_ms: float = 0.0
    avg_repo_processing_time_ms: float = 0.0

    # Individual repository metrics
    repo_metrics: Dict[str, IngestionMetrics] = field(default_factory=dict)
    pr_metrics: Dict[str, PRIntelligenceMetrics] = field(default_factory=dict)


class BatchProcessor:
    """
    Parallel batch processor for pattern ingestion.

    Orchestrates parallel processing of:
    - Multiple repositories for pattern extraction
    - Multiple PRs for intelligence gathering

    Features:
    - Configurable concurrency (semaphore-based rate limiting)
    - Progress tracking with callbacks
    - Error recovery (continue on failure)
    - Comprehensive metrics aggregation

    Example:
        processor = BatchProcessor(
            db_config=db_config,
            max_concurrent=4
        )

        metrics = await processor.process_repositories(
            repositories=[
                "/path/to/repo1",
                "/path/to/repo2",
                "/path/to/repo3",
            ],
            min_quality=0.6
        )

        print(f"Processed {metrics.repos_processed} repos")
        print(f"Found {metrics.total_patterns_found} patterns")
    """

    def __init__(
        self,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        max_concurrent: int = 4,
        langextract_base_url: str = "http://archon-langextract:8156",
        correlation_id: Optional[uuid.UUID] = None,
    ):
        """
        Initialize batch processor.

        Args:
            db_host: Database host
            db_port: Database port
            db_name: Database name
            db_user: Database user
            db_password: Database password
            max_concurrent: Maximum concurrent operations (default: 4)
            langextract_base_url: LangExtract service URL
            correlation_id: Optional correlation ID for tracing
        """
        self.db_config = {
            "host": db_host,
            "port": db_port,
            "database": db_name,
            "user": db_user,
            "password": db_password,
        }
        self.max_concurrent = max_concurrent
        self.langextract_base_url = langextract_base_url
        self.correlation_id = correlation_id or uuid.uuid4()

        # Semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent)

        logger.info(
            f"BatchProcessor initialized: max_concurrent={max_concurrent}, "
            f"correlation_id={self.correlation_id}"
        )

    async def process_repositories(
        self,
        repositories: List[str],
        min_quality: float = 0.0,
        batch_size: int = 50,
        recursive: bool = True,
        progress_callback: Optional[callable] = None,
    ) -> BatchMetrics:
        """
        Process multiple repositories in parallel.

        Args:
            repositories: List of repository paths
            min_quality: Minimum quality score (0.0-1.0)
            batch_size: Batch size for database inserts
            recursive: Whether to scan subdirectories
            progress_callback: Optional callback for progress updates

        Returns:
            BatchMetrics with aggregated statistics
        """
        import time

        start_time = time.time()

        batch_metrics = BatchMetrics()

        # Create tasks for parallel processing
        tasks = [
            self._process_repository_with_semaphore(
                repo_path=repo,
                min_quality=min_quality,
                batch_size=batch_size,
                recursive=recursive,
                batch_metrics=batch_metrics,
                progress_callback=progress_callback,
            )
            for repo in repositories
        ]

        # Execute all tasks in parallel (with semaphore limiting concurrency)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Repository processing failed: {repositories[i]}: {result}",
                    exc_info=result,
                )
                batch_metrics.repos_failed += 1
                batch_metrics.total_errors += 1
            else:
                # Result is IngestionMetrics
                batch_metrics.repos_processed += 1
                batch_metrics.total_files_processed += result.files_processed
                batch_metrics.total_patterns_found += result.patterns_found
                batch_metrics.total_patterns_inserted += result.patterns_inserted
                batch_metrics.total_patterns_updated += result.patterns_updated
                batch_metrics.total_errors += result.errors
                batch_metrics.repo_metrics[repositories[i]] = result

        batch_metrics.total_processing_time_ms = (time.time() - start_time) * 1000

        if batch_metrics.repos_processed > 0:
            batch_metrics.avg_repo_processing_time_ms = (
                batch_metrics.total_processing_time_ms / batch_metrics.repos_processed
            )

        logger.info(
            f"Batch processing complete: {batch_metrics.repos_processed}/{len(repositories)} repos, "
            f"{batch_metrics.total_patterns_found} patterns found, "
            f"{batch_metrics.total_patterns_inserted} inserted, "
            f"{batch_metrics.repos_failed} failed "
            f"({batch_metrics.total_processing_time_ms:.2f}ms)"
        )

        return batch_metrics

    async def _process_repository_with_semaphore(
        self,
        repo_path: str,
        min_quality: float,
        batch_size: int,
        recursive: bool,
        batch_metrics: BatchMetrics,
        progress_callback: Optional[callable],
    ) -> IngestionMetrics:
        """
        Process a single repository with semaphore rate limiting.

        Args:
            repo_path: Path to repository
            min_quality: Minimum quality score
            batch_size: Batch size for database inserts
            recursive: Whether to scan subdirectories
            batch_metrics: Batch metrics to update
            progress_callback: Optional progress callback

        Returns:
            IngestionMetrics for this repository
        """
        async with self.semaphore:
            logger.info(f"Processing repository: {repo_path}")

            if progress_callback:
                progress_callback(
                    {
                        "status": "processing",
                        "repository": repo_path,
                        "total_repos": batch_metrics.repos_processed,
                    }
                )

            async with IngestionPipeline(
                **self.db_config, correlation_id=self.correlation_id
            ) as pipeline:
                metrics = await pipeline.ingest_directory(
                    directory=repo_path,
                    min_quality=min_quality,
                    batch_size=batch_size,
                    recursive=recursive,
                )

            if progress_callback:
                progress_callback(
                    {
                        "status": "completed",
                        "repository": repo_path,
                        "metrics": metrics,
                        "total_repos": batch_metrics.repos_processed + 1,
                    }
                )

            return metrics

    async def process_prs(
        self,
        prs: List[Dict[str, Any]],
        min_confidence: float = 0.5,
        progress_callback: Optional[callable] = None,
    ) -> BatchMetrics:
        """
        Process multiple PRs in parallel for intelligence extraction.

        Args:
            prs: List of PR dictionaries with 'repository' and 'pr_number' keys
                Example: [
                    {"repository": "owner/repo", "pr_number": 123},
                    {"repository": "owner/repo", "pr_number": 124},
                ]
            min_confidence: Minimum confidence for pattern mentions
            progress_callback: Optional callback for progress updates

        Returns:
            BatchMetrics with aggregated PR intelligence statistics
        """
        import time

        start_time = time.time()

        batch_metrics = BatchMetrics()

        # Create tasks for parallel processing
        tasks = [
            self._process_pr_with_semaphore(
                repository=pr["repository"],
                pr_number=pr["pr_number"],
                min_confidence=min_confidence,
                batch_metrics=batch_metrics,
                progress_callback=progress_callback,
            )
            for pr in prs
        ]

        # Execute all tasks in parallel (with semaphore limiting concurrency)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        for i, result in enumerate(results):
            pr_key = f"{prs[i]['repository']}#{prs[i]['pr_number']}"

            if isinstance(result, Exception):
                logger.error(
                    f"PR processing failed: {pr_key}: {result}", exc_info=result
                )
                batch_metrics.prs_failed += 1
                batch_metrics.total_errors += 1
            else:
                # Result is PRIntelligenceMetrics
                batch_metrics.prs_analyzed += result.prs_analyzed
                batch_metrics.total_mentions_extracted += result.mentions_extracted
                batch_metrics.total_mentions_stored += result.mentions_stored
                batch_metrics.pr_metrics[pr_key] = result

        batch_metrics.total_processing_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"PR batch processing complete: {batch_metrics.prs_analyzed}/{len(prs)} PRs, "
            f"{batch_metrics.total_mentions_extracted} mentions extracted, "
            f"{batch_metrics.total_mentions_stored} stored, "
            f"{batch_metrics.prs_failed} failed "
            f"({batch_metrics.total_processing_time_ms:.2f}ms)"
        )

        return batch_metrics

    async def _process_pr_with_semaphore(
        self,
        repository: str,
        pr_number: int,
        min_confidence: float,
        batch_metrics: BatchMetrics,
        progress_callback: Optional[callable],
    ) -> PRIntelligenceMetrics:
        """
        Process a single PR with semaphore rate limiting.

        Args:
            repository: GitHub repository (owner/repo)
            pr_number: PR number
            min_confidence: Minimum confidence for pattern mentions
            batch_metrics: Batch metrics to update
            progress_callback: Optional progress callback

        Returns:
            PRIntelligenceMetrics for this PR
        """
        async with self.semaphore:
            pr_key = f"{repository}#{pr_number}"
            logger.info(f"Processing PR: {pr_key}")

            if progress_callback:
                progress_callback(
                    {
                        "status": "processing",
                        "pr": pr_key,
                        "total_prs": batch_metrics.prs_analyzed,
                    }
                )

            async with PRIntelligenceExtractor(
                **self.db_config,
                langextract_base_url=self.langextract_base_url,
                correlation_id=self.correlation_id,
            ) as extractor:
                metrics = await extractor.analyze_pr(
                    repository=repository,
                    pr_number=pr_number,
                    min_confidence=min_confidence,
                )

            if progress_callback:
                progress_callback(
                    {
                        "status": "completed",
                        "pr": pr_key,
                        "metrics": metrics,
                        "total_prs": batch_metrics.prs_analyzed + 1,
                    }
                )

            return metrics

    async def process_combined(
        self,
        repositories: List[str],
        prs: List[Dict[str, Any]],
        min_quality: float = 0.6,
        min_confidence: float = 0.5,
        batch_size: int = 50,
        progress_callback: Optional[callable] = None,
    ) -> BatchMetrics:
        """
        Process both repositories and PRs in parallel.

        Args:
            repositories: List of repository paths
            prs: List of PR dictionaries
            min_quality: Minimum quality score for patterns
            min_confidence: Minimum confidence for PR mentions
            batch_size: Batch size for database inserts
            progress_callback: Optional progress callback

        Returns:
            Combined BatchMetrics
        """
        logger.info(
            f"Starting combined processing: {len(repositories)} repos, {len(prs)} PRs"
        )

        # Process repositories and PRs in parallel
        repo_task = self.process_repositories(
            repositories=repositories,
            min_quality=min_quality,
            batch_size=batch_size,
            progress_callback=progress_callback,
        )

        pr_task = self.process_prs(
            prs=prs, min_confidence=min_confidence, progress_callback=progress_callback
        )

        repo_metrics, pr_metrics = await asyncio.gather(repo_task, pr_task)

        # Combine metrics
        combined = BatchMetrics(
            repos_processed=repo_metrics.repos_processed,
            repos_failed=repo_metrics.repos_failed,
            total_files_processed=repo_metrics.total_files_processed,
            total_patterns_found=repo_metrics.total_patterns_found,
            total_patterns_inserted=repo_metrics.total_patterns_inserted,
            total_patterns_updated=repo_metrics.total_patterns_updated,
            prs_analyzed=pr_metrics.prs_analyzed,
            prs_failed=pr_metrics.prs_failed,
            total_mentions_extracted=pr_metrics.total_mentions_extracted,
            total_mentions_stored=pr_metrics.total_mentions_stored,
            total_errors=repo_metrics.total_errors + pr_metrics.total_errors,
            total_processing_time_ms=max(
                repo_metrics.total_processing_time_ms,
                pr_metrics.total_processing_time_ms,
            ),
            repo_metrics=repo_metrics.repo_metrics,
            pr_metrics=pr_metrics.pr_metrics,
        )

        logger.info(
            f"Combined processing complete: "
            f"{combined.repos_processed} repos, {combined.prs_analyzed} PRs, "
            f"{combined.total_patterns_found} patterns, {combined.total_mentions_extracted} mentions"
        )

        return combined
