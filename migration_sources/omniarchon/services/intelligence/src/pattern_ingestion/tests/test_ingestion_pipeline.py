"""
Unit Tests for IngestionPipeline
==================================

Tests pattern extraction, quality scoring, and database storage.

ONEX Compliance: Yes
Migration Date: 2025-10-28
"""

import asyncio
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ..ingestion_pipeline import IngestionPipeline


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


@pytest.fixture
def sample_python_file(tmp_path):
    """Create a sample Python file for testing."""
    file_path = tmp_path / "sample.py"
    file_path.write_text(
        '''
"""Sample module for testing."""

def add_numbers(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

class Calculator:
    """Simple calculator class."""

    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b
'''
    )
    return str(file_path)


@pytest.mark.asyncio
async def test_ingestion_pipeline_initialization(db_config):
    """Test IngestionPipeline initialization."""
    pipeline = IngestionPipeline(**db_config)

    assert pipeline.db_config["host"] == "localhost"
    assert pipeline.db_config["port"] == 5436
    assert pipeline.correlation_id is not None
    assert pipeline.pool is None  # Not connected yet


@pytest.mark.asyncio
async def test_extract_patterns_from_file(db_config, sample_python_file):
    """Test pattern extraction from a single file."""
    pipeline = IngestionPipeline(**db_config)

    # Mock scorer to avoid radon dependency
    with patch.object(pipeline.scorer, "calculate_overall_quality") as mock_scorer:
        mock_scorer.return_value = {
            "quality_score": 0.8,
            "components": {
                "complexity": 0.9,
                "documentation": 0.8,
                "test_coverage": 0.7,
                "reusability": 0.6,
                "maintainability": 0.8,
            },
        }

        patterns = await pipeline._extract_patterns_from_file(
            sample_python_file, min_quality=0.5
        )

    assert len(patterns) > 0
    assert all("pattern_id" in p for p in patterns)
    assert all("pattern_name" in p for p in patterns)
    assert all("overall_quality" in p for p in patterns)
    assert all(p["overall_quality"] >= 0.5 for p in patterns)


@pytest.mark.asyncio
async def test_generate_pattern_id():
    """Test pattern ID generation."""
    pipeline = IngestionPipeline(
        db_host="localhost",
        db_port=5436,
        db_name="test",
        db_user="test",
        db_password="test",
    )

    pattern = {
        "file_path": "/path/to/file.py",
        "pattern_name": "add_numbers",
        "pattern_type": "function",
    }

    pattern_id = pipeline._generate_pattern_id(pattern)

    assert isinstance(pattern_id, str)
    assert len(pattern_id) <= 255
    assert "add_numbers" in pattern_id
    assert "function" in pattern_id


@pytest.mark.asyncio
async def test_ingest_directory_with_mock_db(db_config, tmp_path):
    """Test directory ingestion with mocked database."""
    # Create test files
    (tmp_path / "file1.py").write_text("def func1(): pass")
    (tmp_path / "file2.py").write_text("def func2(): pass")

    pipeline = IngestionPipeline(**db_config)

    # Mock database pool
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.fetchrow.return_value = None  # No existing patterns
    mock_conn.execute.return_value = None  # Insert success

    pipeline.pool = mock_pool

    # Mock pattern extraction
    with patch.object(pipeline, "_extract_patterns_from_file") as mock_extract:
        mock_extract.return_value = [
            {
                "pattern_id": "test_pattern",
                "pattern_name": "test",
                "pattern_type": "function",
                "pattern_version": "1.0.0",
                "lineage_id": uuid.uuid4(),
                "generation": 1,
                "source_system": "test",
                "correlation_id": uuid.uuid4(),
                "file_path": str(tmp_path / "file1.py"),
                "language": "python",
                "pattern_data": {},
                "metadata": {},
                "complexity_score": 0.8,
                "documentation_score": 0.7,
                "test_coverage_score": 0.6,
                "reusability_score": 0.5,
                "maintainability_score": 0.7,
                "overall_quality": 0.7,
                "usage_count": 1,
            }
        ]

        metrics = await pipeline.ingest_directory(
            directory=str(tmp_path), min_quality=0.5, batch_size=10
        )

    assert metrics.files_processed == 2
    assert metrics.patterns_found == 2
    assert mock_extract.call_count == 2


@pytest.mark.asyncio
async def test_insert_pattern_batch_new_patterns(db_config):
    """Test inserting new patterns."""
    pipeline = IngestionPipeline(**db_config)

    # Mock database pool
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.fetchrow.return_value = None  # No existing patterns
    mock_conn.execute.return_value = None  # Insert success

    pipeline.pool = mock_pool

    patterns = [
        {
            "pattern_id": "test_pattern_1",
            "pattern_name": "test1",
            "pattern_type": "function",
            "pattern_version": "1.0.0",
            "lineage_id": uuid.uuid4(),
            "generation": 1,
            "source_system": "test",
            "correlation_id": uuid.uuid4(),
            "file_path": "/test/file.py",
            "language": "python",
            "pattern_data": {},
            "metadata": {},
            "complexity_score": 0.8,
            "documentation_score": 0.7,
            "test_coverage_score": 0.6,
            "reusability_score": 0.5,
            "maintainability_score": 0.7,
            "overall_quality": 0.7,
            "usage_count": 1,
        }
    ]

    result = await pipeline._insert_pattern_batch(patterns)

    assert result["inserted"] == 1
    assert result["updated"] == 0
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_insert_pattern_batch_existing_patterns(db_config):
    """Test updating existing patterns."""
    pipeline = IngestionPipeline(**db_config)

    # Mock database pool
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Return existing pattern
    mock_conn.fetchrow.return_value = {"id": uuid.uuid4(), "pattern_version": "1.0.0"}
    mock_conn.execute.return_value = None  # Update success

    pipeline.pool = mock_pool

    patterns = [
        {
            "pattern_id": "test_pattern_1",
            "pattern_name": "test1",
            "pattern_type": "function",
            "pattern_version": "1.0.0",
            "lineage_id": uuid.uuid4(),
            "generation": 1,
            "source_system": "test",
            "correlation_id": uuid.uuid4(),
            "file_path": "/test/file.py",
            "language": "python",
            "pattern_data": {},
            "metadata": {},
            "complexity_score": 0.8,
            "documentation_score": 0.7,
            "test_coverage_score": 0.6,
            "reusability_score": 0.5,
            "maintainability_score": 0.7,
            "overall_quality": 0.7,
            "usage_count": 1,
        }
    ]

    result = await pipeline._insert_pattern_batch(patterns)

    assert result["inserted"] == 0
    assert result["updated"] == 1
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_context_manager(db_config):
    """Test async context manager."""
    with patch("asyncpg.create_pool") as mock_create_pool:
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        async with IngestionPipeline(**db_config) as pipeline:
            assert pipeline.pool is not None

        # Verify pool was closed
        mock_pool.close.assert_called_once()
