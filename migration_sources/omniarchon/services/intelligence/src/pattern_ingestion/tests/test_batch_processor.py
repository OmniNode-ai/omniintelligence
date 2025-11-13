"""
Unit Tests for BatchProcessor
===============================

Tests parallel processing, error recovery, and metrics aggregation.

ONEX Compliance: Yes
Migration Date: 2025-10-28
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ..batch_processor import BatchProcessor
from ..ingestion_pipeline import IngestionMetrics
from ..pr_intelligence import PRIntelligenceMetrics


@pytest.fixture
def db_config():
    """Database configuration fixture."""
    return {
        "db_host": "localhost",
        "db_port": 5436,
        "db_name": "test_db",
        "db_user": "test_user",
        "db_password": "test_password",
    }


@pytest.mark.asyncio
async def test_batch_processor_initialization(db_config):
    """Test BatchProcessor initialization."""
    processor = BatchProcessor(**db_config, max_concurrent=4)

    assert processor.db_config["host"] == "localhost"
    assert processor.max_concurrent == 4
    assert processor.correlation_id is not None


@pytest.mark.asyncio
async def test_process_repositories(db_config, tmp_path):
    """Test parallel repository processing."""
    # Create test repositories
    repo1 = tmp_path / "repo1"
    repo2 = tmp_path / "repo2"
    repo1.mkdir()
    repo2.mkdir()

    (repo1 / "file1.py").write_text("def test1(): pass")
    (repo2 / "file2.py").write_text("def test2(): pass")

    processor = BatchProcessor(**db_config, max_concurrent=2)

    # Mock IngestionPipeline
    with patch(
        "pattern_ingestion.batch_processor.IngestionPipeline"
    ) as mock_pipeline_class:
        mock_pipeline = AsyncMock()
        mock_pipeline_class.return_value.__aenter__.return_value = mock_pipeline

        # Mock ingestion metrics
        mock_pipeline.ingest_directory.return_value = IngestionMetrics(
            files_processed=1,
            patterns_found=5,
            patterns_inserted=5,
            patterns_updated=0,
            patterns_skipped=0,
            errors=0,
            processing_time_ms=100.0,
        )

        metrics = await processor.process_repositories(
            repositories=[str(repo1), str(repo2)],
            min_quality=0.6,
            batch_size=50,
        )

    assert metrics.repos_processed == 2
    assert metrics.total_patterns_found == 10  # 5 per repo
    assert metrics.total_patterns_inserted == 10


@pytest.mark.asyncio
async def test_process_repositories_with_failures(db_config, tmp_path):
    """Test repository processing with some failures."""
    repo1 = tmp_path / "repo1"
    repo2 = tmp_path / "repo2"
    repo3 = tmp_path / "repo3"  # Will fail
    repo1.mkdir()
    repo2.mkdir()
    # Don't create repo3 to simulate failure

    processor = BatchProcessor(**db_config, max_concurrent=2)

    with patch(
        "pattern_ingestion.batch_processor.IngestionPipeline"
    ) as mock_pipeline_class:
        mock_pipeline = AsyncMock()
        mock_pipeline_class.return_value.__aenter__.return_value = mock_pipeline

        # Mock success for existing repos, failure for non-existent
        async def mock_ingest(directory, **kwargs):
            if "repo3" in directory:
                raise FileNotFoundError(f"Directory not found: {directory}")
            return IngestionMetrics(
                files_processed=1,
                patterns_found=5,
                patterns_inserted=5,
                patterns_updated=0,
                patterns_skipped=0,
                errors=0,
                processing_time_ms=100.0,
            )

        mock_pipeline.ingest_directory.side_effect = mock_ingest

        metrics = await processor.process_repositories(
            repositories=[str(repo1), str(repo2), str(repo3)],
            min_quality=0.6,
        )

    assert metrics.repos_processed == 2
    assert metrics.repos_failed == 1
    assert metrics.total_errors >= 1


@pytest.mark.asyncio
async def test_process_prs(db_config):
    """Test parallel PR processing."""
    processor = BatchProcessor(**db_config, max_concurrent=2)

    prs = [
        {"repository": "owner/repo", "pr_number": 123},
        {"repository": "owner/repo", "pr_number": 124},
    ]

    with patch(
        "pattern_ingestion.batch_processor.PRIntelligenceExtractor"
    ) as mock_extractor_class:
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value.__aenter__.return_value = mock_extractor

        # Mock PR analysis metrics
        mock_extractor.analyze_pr.return_value = PRIntelligenceMetrics(
            prs_analyzed=1,
            patterns_found=3,
            mentions_extracted=5,
            mentions_stored=5,
            errors=0,
            processing_time_ms=200.0,
        )

        metrics = await processor.process_prs(prs=prs, min_confidence=0.5)

    assert metrics.prs_analyzed == 2
    assert metrics.total_mentions_extracted == 10  # 5 per PR


@pytest.mark.asyncio
async def test_process_combined(db_config, tmp_path):
    """Test combined repository and PR processing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "file.py").write_text("def test(): pass")

    processor = BatchProcessor(**db_config, max_concurrent=2)

    prs = [{"repository": "owner/repo", "pr_number": 123}]

    with (
        patch(
            "pattern_ingestion.batch_processor.IngestionPipeline"
        ) as mock_pipeline_class,
        patch(
            "pattern_ingestion.batch_processor.PRIntelligenceExtractor"
        ) as mock_extractor_class,
    ):

        mock_pipeline = AsyncMock()
        mock_pipeline_class.return_value.__aenter__.return_value = mock_pipeline
        mock_pipeline.ingest_directory.return_value = IngestionMetrics(
            files_processed=1,
            patterns_found=5,
            patterns_inserted=5,
            patterns_updated=0,
            patterns_skipped=0,
            errors=0,
            processing_time_ms=100.0,
        )

        mock_extractor = AsyncMock()
        mock_extractor_class.return_value.__aenter__.return_value = mock_extractor
        mock_extractor.analyze_pr.return_value = PRIntelligenceMetrics(
            prs_analyzed=1,
            patterns_found=3,
            mentions_extracted=5,
            mentions_stored=5,
            errors=0,
            processing_time_ms=200.0,
        )

        metrics = await processor.process_combined(
            repositories=[str(repo)],
            prs=prs,
            min_quality=0.6,
            min_confidence=0.5,
        )

    assert metrics.repos_processed == 1
    assert metrics.prs_analyzed == 1
    assert metrics.total_patterns_found == 5
    assert metrics.total_mentions_extracted == 5


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency(db_config):
    """Test that semaphore correctly limits concurrent operations."""
    processor = BatchProcessor(**db_config, max_concurrent=2)

    # Track concurrent executions
    concurrent_count = 0
    max_concurrent = 0

    async def mock_process(*args, **kwargs):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.1)  # Simulate work
        concurrent_count -= 1
        return IngestionMetrics()

    with patch.object(
        processor, "_process_repository_with_semaphore", side_effect=mock_process
    ):
        await processor.process_repositories(
            repositories=["repo1", "repo2", "repo3", "repo4"],
            min_quality=0.6,
        )

    # Should never exceed max_concurrent
    assert max_concurrent <= 2


@pytest.mark.asyncio
async def test_progress_callback(db_config, tmp_path):
    """Test progress callback functionality."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "file.py").write_text("def test(): pass")

    processor = BatchProcessor(**db_config, max_concurrent=1)

    progress_updates = []

    def progress_callback(update):
        progress_updates.append(update)

    with patch(
        "pattern_ingestion.batch_processor.IngestionPipeline"
    ) as mock_pipeline_class:
        mock_pipeline = AsyncMock()
        mock_pipeline_class.return_value.__aenter__.return_value = mock_pipeline
        mock_pipeline.ingest_directory.return_value = IngestionMetrics(
            files_processed=1,
            patterns_found=5,
            patterns_inserted=5,
            patterns_updated=0,
            patterns_skipped=0,
            errors=0,
            processing_time_ms=100.0,
        )

        await processor.process_repositories(
            repositories=[str(repo)],
            min_quality=0.6,
            progress_callback=progress_callback,
        )

    # Should have processing and completed updates
    assert len(progress_updates) == 2
    assert progress_updates[0]["status"] == "processing"
    assert progress_updates[1]["status"] == "completed"
