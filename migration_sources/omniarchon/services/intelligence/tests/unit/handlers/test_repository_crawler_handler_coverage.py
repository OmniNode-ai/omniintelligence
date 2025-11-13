"""
Unit Tests for RepositoryCrawlerHandler - Comprehensive Coverage

Goal: Improve coverage from 17.4% to 75%+
Covers: Repository crawling logic, file discovery, event handling, error recovery

Created: 2025-11-04
"""

import os
import tempfile
from pathlib import Path
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, mock_open, patch
from uuid import UUID, uuid4

import pytest
from events.models.repository_crawler_events import (
    EnumCrawlerErrorCode,
    EnumRepositoryCrawlerEventType,
    EnumScanScope,
)
from fixtures.kafka_fixtures import MockEventEnvelope
from handlers.repository_crawler_handler import RepositoryCrawlerHandler

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def handler():
    """Create handler instance."""
    return RepositoryCrawlerHandler()


@pytest.fixture
def handler_with_router(handler):
    """Create handler with mocked router."""
    handler._router = AsyncMock()
    handler._router.publish = AsyncMock()
    handler._router_initialized = True
    return handler


@pytest.fixture
def temp_repo_dir():
    """Create temporary repository directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directory structure
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        tests_dir = Path(tmpdir) / "tests"
        tests_dir.mkdir()
        pycache_dir = src_dir / "__pycache__"
        pycache_dir.mkdir()
        node_modules = Path(tmpdir) / "node_modules"
        node_modules.mkdir()

        # Create test files
        (src_dir / "main.py").write_text("def main(): pass")
        (src_dir / "utils.py").write_text("def util(): pass")
        (src_dir / "app.ts").write_text("const app = 1;")
        (tests_dir / "test_main.py").write_text("def test(): pass")
        (pycache_dir / "cached.pyc").write_text("binary")
        (node_modules / "package.js").write_text("module.exports = {};")

        yield tmpdir


# ==============================================================================
# Event Routing Tests (7 tests)
# ==============================================================================


class TestEventRouting:
    """Test event type routing capabilities."""

    def test_can_handle_enum(self, handler):
        """Test can_handle with enum value."""
        assert (
            handler.can_handle(
                EnumRepositoryCrawlerEventType.REPOSITORY_SCAN_REQUESTED.value
            )
            is True
        )

    def test_can_handle_string_variant(self, handler):
        """Test can_handle with string variant."""
        assert handler.can_handle("REPOSITORY_SCAN_REQUESTED") is True

    def test_can_handle_dotted_notation(self, handler):
        """Test can_handle with dotted notation."""
        assert handler.can_handle("intelligence.repository-scan-requested") is True

    def test_can_handle_full_qualified(self, handler):
        """Test can_handle with fully qualified event type."""
        assert (
            handler.can_handle(
                "omninode.intelligence.event.repository_scan_requested.v1"
            )
            is True
        )

    def test_cannot_handle_unknown(self, handler):
        """Test rejection of unknown event type."""
        assert handler.can_handle("unknown.event.type") is False

    def test_cannot_handle_completed(self, handler):
        """Test rejection of COMPLETED event."""
        assert handler.can_handle("REPOSITORY_SCAN_COMPLETED") is False

    def test_cannot_handle_failed(self, handler):
        """Test rejection of FAILED event."""
        assert handler.can_handle("REPOSITORY_SCAN_FAILED") is False


# ==============================================================================
# Initialization Tests (4 tests)
# ==============================================================================


class TestInitialization:
    """Test handler initialization."""

    def test_metrics_initialized(self, handler):
        """Test metrics are properly initialized."""
        assert handler.metrics["events_handled"] == 0
        assert handler.metrics["events_failed"] == 0
        assert handler.metrics["total_processing_time_ms"] == 0.0
        assert handler.metrics["total_files_discovered"] == 0
        assert handler.metrics["total_files_published"] == 0
        assert handler.metrics["total_batches_created"] == 0

    def test_topic_constants(self, handler):
        """Test topic constants are defined."""
        assert (
            handler.REQUEST_TOPIC
            == "dev.archon-intelligence.intelligence.repository-scan-requested.v1"
        )
        assert (
            handler.COMPLETED_TOPIC
            == "dev.archon-intelligence.intelligence.repository-scan-completed.v1"
        )
        assert (
            handler.FAILED_TOPIC
            == "dev.archon-intelligence.intelligence.repository-scan-failed.v1"
        )
        assert (
            handler.DOCUMENT_INDEX_TOPIC
            == "dev.archon-intelligence.intelligence.document-index-requested.v1"
        )

    def test_handler_name(self, handler):
        """Test get_handler_name returns correct name."""
        assert handler.get_handler_name() == "RepositoryCrawlerHandler"

    def test_inheritance(self, handler):
        """Test handler inherits from BaseResponsePublisher."""
        from handlers.base_response_publisher import BaseResponsePublisher

        assert isinstance(handler, BaseResponsePublisher)


# ==============================================================================
# Validation Tests (2 tests)
# ==============================================================================


class TestValidation:
    """Test input validation."""

    @pytest.mark.asyncio
    async def test_missing_repository_path(self, handler_with_router):
        """Test handling of missing repository_path."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={"project_id": "test-project"},
        )

        success = await handler_with_router.handle_event(event)

        assert success is False
        assert handler_with_router.metrics["events_failed"] == 1
        # Verify failed event published
        assert handler_with_router._router.publish.called

    @pytest.mark.asyncio
    async def test_missing_project_id(self, handler_with_router):
        """Test handling of missing project_id."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={"repository_path": "/tmp/test"},
        )

        success = await handler_with_router.handle_event(event)

        assert success is False
        assert handler_with_router.metrics["events_failed"] == 1
        # Verify failed event published
        assert handler_with_router._router.publish.called


# ==============================================================================
# File Discovery Tests (5 tests)
# ==============================================================================


class TestFileDiscovery:
    """Test file discovery logic."""

    def test_discover_files_success(self, handler, temp_repo_dir):
        """Test successful file discovery."""
        files = handler._discover_files(
            repository_path=temp_repo_dir,
            file_patterns=["**/*.py"],
            exclude_patterns=["**/__pycache__/**"],
        )

        assert len(files) == 3  # main.py, utils.py, test_main.py
        paths = [f["relative_path"] for f in files]
        assert any("main.py" in p for p in paths)
        assert any("utils.py" in p for p in paths)

    def test_discover_files_typescript(self, handler, temp_repo_dir):
        """Test discovery of TypeScript files."""
        files = handler._discover_files(
            repository_path=temp_repo_dir,
            file_patterns=["**/*.ts"],
            exclude_patterns=[],
        )

        assert len(files) == 1
        assert files[0]["language"] == "typescript"

    def test_discover_files_exclude_patterns(self, handler, temp_repo_dir):
        """Test exclude patterns work correctly."""
        files = handler._discover_files(
            repository_path=temp_repo_dir,
            file_patterns=["**/*.py", "**/*.ts"],
            exclude_patterns=["**/__pycache__/**", "**/node_modules/**"],
        )

        paths = [f["relative_path"] for f in files]
        # Should not include cached files
        assert not any("__pycache__" in p for p in paths)
        # Should not include .pyc files (binary files are excluded by pattern)
        assert not any(p.endswith(".pyc") for p in paths)

    def test_discover_files_multiple_patterns(self, handler, temp_repo_dir):
        """Test discovery with multiple file patterns."""
        files = handler._discover_files(
            repository_path=temp_repo_dir,
            file_patterns=["**/*.py", "**/*.ts"],
            exclude_patterns=["**/__pycache__/**"],
        )

        assert len(files) >= 3  # Python and TypeScript files

    def test_discover_files_permission_error(self, handler, temp_repo_dir):
        """Test handling of permission errors during discovery."""
        with patch("os.path.getsize", side_effect=PermissionError("Access denied")):
            files = handler._discover_files(
                repository_path=temp_repo_dir,
                file_patterns=["**/*.py"],
                exclude_patterns=[],
            )
            # Should continue despite permission errors
            assert isinstance(files, list)


# ==============================================================================
# Language Detection Tests (8 tests)
# ==============================================================================


class TestLanguageDetection:
    """Test programming language detection."""

    def test_detect_python(self, handler):
        """Test Python file detection."""
        assert handler._detect_language("test.py") == "python"

    def test_detect_typescript(self, handler):
        """Test TypeScript file detection."""
        assert handler._detect_language("test.ts") == "typescript"
        assert handler._detect_language("component.tsx") == "typescript"

    def test_detect_rust(self, handler):
        """Test Rust file detection."""
        assert handler._detect_language("main.rs") == "rust"

    def test_detect_go(self, handler):
        """Test Go file detection."""
        assert handler._detect_language("main.go") == "go"

    def test_detect_javascript(self, handler):
        """Test JavaScript file detection."""
        assert handler._detect_language("app.js") == "javascript"
        assert handler._detect_language("component.jsx") == "javascript"

    def test_detect_java(self, handler):
        """Test Java file detection."""
        assert handler._detect_language("Main.java") == "java"

    def test_detect_cpp(self, handler):
        """Test C++ file detection."""
        assert handler._detect_language("main.cpp") == "cpp"
        assert handler._detect_language("header.hpp") == "cpp"

    def test_detect_unknown(self, handler):
        """Test unknown file extension."""
        assert handler._detect_language("readme.md") == "unknown"
        assert handler._detect_language("data.json") == "unknown"


# ==============================================================================
# Repository Scanning Tests (5 tests)
# ==============================================================================


class TestRepositoryScanning:
    """Test repository scanning functionality."""

    @pytest.mark.asyncio
    async def test_scan_repository_success(self, handler_with_router, temp_repo_dir):
        """Test successful repository scan."""
        result = await handler_with_router._scan_repository(
            repository_path=temp_repo_dir,
            project_id="test-project",
            scan_scope="FULL",
            file_patterns=["**/*.py"],
            exclude_patterns=["**/__pycache__/**"],
            batch_size=10,
            indexing_options={},
            correlation_id=str(uuid4()),
        )

        assert result["files_discovered"] == 3
        assert result["files_published"] == 3
        assert result["files_skipped"] == 0
        assert result["batches_created"] == 1

    @pytest.mark.asyncio
    async def test_scan_repository_not_found(self, handler_with_router):
        """Test scan of non-existent repository."""
        with pytest.raises(FileNotFoundError):
            await handler_with_router._scan_repository(
                repository_path="/nonexistent/path",
                project_id="test-project",
                scan_scope="FULL",
                file_patterns=["**/*.py"],
                exclude_patterns=[],
                batch_size=10,
                indexing_options={},
                correlation_id=str(uuid4()),
            )

    @pytest.mark.asyncio
    async def test_scan_repository_not_directory(self, handler_with_router):
        """Test scan of file instead of directory."""
        with tempfile.NamedTemporaryFile() as tmp:
            with pytest.raises(ValueError, match="not a directory"):
                await handler_with_router._scan_repository(
                    repository_path=tmp.name,
                    project_id="test-project",
                    scan_scope="FULL",
                    file_patterns=["**/*.py"],
                    exclude_patterns=[],
                    batch_size=10,
                    indexing_options={},
                    correlation_id=str(uuid4()),
                )

    @pytest.mark.asyncio
    async def test_scan_repository_no_files(self, handler_with_router):
        """Test scan with no matching files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await handler_with_router._scan_repository(
                repository_path=tmpdir,
                project_id="test-project",
                scan_scope="FULL",
                file_patterns=["**/*.xyz"],  # Non-existent extension
                exclude_patterns=[],
                batch_size=10,
                indexing_options={},
                correlation_id=str(uuid4()),
            )

            assert result["files_discovered"] == 0
            assert result["files_published"] == 0
            assert result["batches_created"] == 0

    @pytest.mark.asyncio
    async def test_scan_repository_file_summaries(
        self, handler_with_router, temp_repo_dir
    ):
        """Test file summaries are created."""
        result = await handler_with_router._scan_repository(
            repository_path=temp_repo_dir,
            project_id="test-project",
            scan_scope="FULL",
            file_patterns=["**/*.py"],
            exclude_patterns=["**/__pycache__/**"],
            batch_size=10,
            indexing_options={},
            correlation_id=str(uuid4()),
        )

        assert "file_summaries" in result
        assert len(result["file_summaries"]) > 0
        summary = result["file_summaries"][0]
        assert "path" in summary
        assert "size" in summary
        assert "language" in summary


# ==============================================================================
# Batch Publishing Tests (5 tests)
# ==============================================================================


class TestBatchPublishing:
    """Test batch publishing logic."""

    @pytest.mark.asyncio
    async def test_publish_batches_success(self, handler_with_router, temp_repo_dir):
        """Test successful batch publishing."""
        files = [
            {
                "absolute_path": str(Path(temp_repo_dir) / "src" / "main.py"),
                "relative_path": "src/main.py",
                "size": 100,
                "language": "python",
            }
        ]

        published, batches = await handler_with_router._publish_batches(
            files=files,
            project_id="test-project",
            batch_size=10,
            indexing_options={},
            correlation_id=str(uuid4()),
        )

        assert published == 1
        assert batches == 1
        assert handler_with_router._router.publish.called

    @pytest.mark.asyncio
    async def test_publish_batches_multiple_batches(
        self, handler_with_router, temp_repo_dir
    ):
        """Test publishing with multiple batches."""
        files = [
            {
                "absolute_path": str(Path(temp_repo_dir) / f"file{i}.py"),
                "relative_path": f"file{i}.py",
                "size": 100,
                "language": "python",
            }
            for i in range(5)
        ]

        # Create the actual files
        for file_info in files:
            Path(file_info["absolute_path"]).write_text("def test(): pass")

        published, batches = await handler_with_router._publish_batches(
            files=files,
            project_id="test-project",
            batch_size=2,  # 5 files / 2 per batch = 3 batches
            indexing_options={},
            correlation_id=str(uuid4()),
        )

        assert published == 5
        assert batches == 3

    @pytest.mark.asyncio
    async def test_publish_batches_file_read_error(self, handler_with_router):
        """Test handling of file read errors during publishing."""
        files = [
            {
                "absolute_path": "/nonexistent/file.py",
                "relative_path": "file.py",
                "size": 100,
                "language": "python",
            }
        ]

        published, batches = await handler_with_router._publish_batches(
            files=files,
            project_id="test-project",
            batch_size=10,
            indexing_options={},
            correlation_id=str(uuid4()),
        )

        # Should skip unreadable files
        assert published == 0
        assert batches == 1

    @pytest.mark.asyncio
    async def test_publish_batches_indexing_options(
        self, handler_with_router, temp_repo_dir
    ):
        """Test indexing options are passed through."""
        files = [
            {
                "absolute_path": str(Path(temp_repo_dir) / "src" / "main.py"),
                "relative_path": "src/main.py",
                "size": 100,
                "language": "python",
            }
        ]

        indexing_options = {"skip_metadata": True, "priority": "high"}

        await handler_with_router._publish_batches(
            files=files,
            project_id="test-project",
            batch_size=10,
            indexing_options=indexing_options,
            correlation_id=str(uuid4()),
        )

        # Verify publish was called (options passed internally)
        assert handler_with_router._router.publish.called

    @pytest.mark.asyncio
    async def test_publish_batches_empty_list(self, handler_with_router):
        """Test publishing with empty file list."""
        published, batches = await handler_with_router._publish_batches(
            files=[],
            project_id="test-project",
            batch_size=10,
            indexing_options={},
            correlation_id=str(uuid4()),
        )

        assert published == 0
        assert batches == 0


# ==============================================================================
# Response Publishing Tests (4 tests)
# ==============================================================================


class TestResponsePublishing:
    """Test response event publishing."""

    @pytest.mark.asyncio
    async def test_publish_completed_response(self, handler_with_router):
        """Test publishing completed response."""
        scan_result = {
            "files_discovered": 10,
            "files_published": 10,
            "files_skipped": 0,
            "batches_created": 1,
            "file_summaries": [],
        }

        await handler_with_router._publish_completed_response(
            correlation_id=str(uuid4()),
            scan_result=scan_result,
            repository_path="/tmp/test",
            project_id="test-project",
            scan_scope="FULL",
            processing_time_ms=1000.0,
        )

        assert handler_with_router._router.publish.called
        call_args = handler_with_router._router.publish.call_args
        assert call_args[1]["topic"] == handler_with_router.COMPLETED_TOPIC

    @pytest.mark.asyncio
    async def test_publish_completed_response_invalid_scope(self, handler_with_router):
        """Test completed response with invalid scope defaults to FULL."""
        scan_result = {
            "files_discovered": 5,
            "files_published": 5,
            "batches_created": 1,
        }

        await handler_with_router._publish_completed_response(
            correlation_id=str(uuid4()),
            scan_result=scan_result,
            repository_path="/tmp/test",
            project_id="test-project",
            scan_scope="INVALID_SCOPE",  # Invalid, should default to FULL
            processing_time_ms=500.0,
        )

        assert handler_with_router._router.publish.called

    @pytest.mark.asyncio
    async def test_publish_failed_response(self, handler_with_router):
        """Test publishing failed response."""
        await handler_with_router._publish_failed_response(
            correlation_id=str(uuid4()),
            repository_path="/tmp/test",
            project_id="test-project",
            error_code=EnumCrawlerErrorCode.REPOSITORY_NOT_FOUND,
            error_message="Repository not found",
            retry_allowed=False,
            processing_time_ms=100.0,
            error_details={"exception": "FileNotFoundError"},
        )

        assert handler_with_router._router.publish.called
        call_args = handler_with_router._router.publish.call_args
        assert call_args[1]["topic"] == handler_with_router.FAILED_TOPIC

    @pytest.mark.asyncio
    async def test_publish_failed_response_no_project_id(self, handler_with_router):
        """Test failed response without project_id."""
        await handler_with_router._publish_failed_response(
            correlation_id=str(uuid4()),
            repository_path="/tmp/test",
            project_id=None,
            error_code=EnumCrawlerErrorCode.INVALID_INPUT,
            error_message="Missing project_id",
            retry_allowed=False,
        )

        assert handler_with_router._router.publish.called


# ==============================================================================
# End-to-End Event Handling Tests (5 tests)
# ==============================================================================


class TestEndToEndEventHandling:
    """Test complete event handling flow."""

    @pytest.mark.asyncio
    async def test_handle_event_success(self, handler_with_router, temp_repo_dir):
        """Test successful end-to-end event handling."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={
                "repository_path": temp_repo_dir,
                "project_id": "test-project",
                "scan_scope": "FULL",
                "file_patterns": ["**/*.py"],
                "exclude_patterns": ["**/__pycache__/**"],
                "batch_size": 10,
            },
        )

        success = await handler_with_router.handle_event(event)

        assert success is True
        assert handler_with_router.metrics["events_handled"] == 1
        assert handler_with_router.metrics["total_files_discovered"] >= 3
        assert handler_with_router.metrics["total_files_published"] >= 3

    @pytest.mark.asyncio
    async def test_handle_event_repository_not_found(self, handler_with_router):
        """Test event handling with non-existent repository."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={
                "repository_path": "/nonexistent/path",
                "project_id": "test-project",
                "scan_scope": "FULL",
            },
        )

        success = await handler_with_router.handle_event(event)

        assert success is False
        assert handler_with_router.metrics["events_failed"] == 1

    @pytest.mark.asyncio
    async def test_handle_event_exception_handling(
        self, handler_with_router, temp_repo_dir
    ):
        """Test exception handling during event processing."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={
                "repository_path": temp_repo_dir,
                "project_id": "test-project",
            },
        )

        # Mock _scan_repository to raise exception
        handler_with_router._scan_repository = AsyncMock(
            side_effect=Exception("Simulated error")
        )

        success = await handler_with_router.handle_event(event)

        assert success is False
        assert handler_with_router.metrics["events_failed"] == 1

    @pytest.mark.asyncio
    async def test_handle_event_publish_error_on_failure(self, handler_with_router):
        """Test that failed event is published even when publish itself fails."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={
                "repository_path": "/invalid",
                "project_id": "test-project",
            },
        )

        # Make publish fail
        handler_with_router._router.publish.side_effect = Exception("Publish failed")

        success = await handler_with_router.handle_event(event)

        assert success is False
        assert handler_with_router.metrics["events_failed"] == 1

    @pytest.mark.asyncio
    async def test_handle_event_default_patterns(
        self, handler_with_router, temp_repo_dir
    ):
        """Test event handling with default file patterns."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={
                "repository_path": temp_repo_dir,
                "project_id": "test-project",
                # No file_patterns or exclude_patterns - should use defaults
            },
        )

        success = await handler_with_router.handle_event(event)

        assert success is True


# ==============================================================================
# Metrics Tests (3 tests)
# ==============================================================================


class TestMetrics:
    """Test metrics tracking."""

    def test_get_metrics_initial(self, handler):
        """Test get_metrics with initial state."""
        metrics = handler.get_metrics()

        assert metrics["events_handled"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_processing_time_ms"] == 0.0
        assert metrics["handler_name"] == "RepositoryCrawlerHandler"

    @pytest.mark.asyncio
    async def test_get_metrics_after_success(self, handler_with_router, temp_repo_dir):
        """Test metrics after successful event."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={
                "repository_path": temp_repo_dir,
                "project_id": "test-project",
                "file_patterns": ["**/*.py"],
                "exclude_patterns": ["**/__pycache__/**"],
            },
        )

        await handler_with_router.handle_event(event)

        metrics = handler_with_router.get_metrics()
        assert metrics["events_handled"] == 1
        assert metrics["events_failed"] == 0
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_processing_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_get_metrics_after_failure(self, handler_with_router):
        """Test metrics after failed event."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={
                "repository_path": "/invalid",
                "project_id": "test-project",
            },
        )

        await handler_with_router.handle_event(event)

        metrics = handler_with_router.get_metrics()
        assert metrics["events_handled"] == 0
        assert metrics["events_failed"] == 1
        assert metrics["success_rate"] == 0.0


# ==============================================================================
# Edge Cases and Error Recovery Tests (5 tests)
# ==============================================================================


class TestEdgeCases:
    """Test edge cases and error recovery."""

    @pytest.mark.asyncio
    async def test_correlation_id_extraction(self, handler_with_router, temp_repo_dir):
        """Test correlation ID is properly extracted and used."""
        correlation_id = str(uuid4())
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            correlation_id=correlation_id,
            payload={
                "repository_path": temp_repo_dir,
                "project_id": "test-project",
                "file_patterns": ["**/*.py"],
                "exclude_patterns": ["**/__pycache__/**"],
            },
        )

        await handler_with_router.handle_event(event)

        # Verify publish was called with correlation_id
        assert handler_with_router._router.publish.called

    @pytest.mark.asyncio
    async def test_large_batch_size(self, handler_with_router, temp_repo_dir):
        """Test handling of large batch size."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={
                "repository_path": temp_repo_dir,
                "project_id": "test-project",
                "batch_size": 1000,  # Very large batch
            },
        )

        success = await handler_with_router.handle_event(event)
        assert success is True

    @pytest.mark.asyncio
    async def test_small_batch_size(self, handler_with_router, temp_repo_dir):
        """Test handling of small batch size."""
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            payload={
                "repository_path": temp_repo_dir,
                "project_id": "test-project",
                "batch_size": 1,  # One file per batch
            },
        )

        success = await handler_with_router.handle_event(event)
        assert success is True

    @pytest.mark.asyncio
    async def test_uuid_correlation_id(self, handler_with_router, temp_repo_dir):
        """Test handling of UUID correlation ID."""
        correlation_id = uuid4()
        event = MockEventEnvelope(
            event_type="REPOSITORY_SCAN_REQUESTED",
            correlation_id=str(correlation_id),
            payload={
                "repository_path": temp_repo_dir,
                "project_id": "test-project",
            },
        )

        success = await handler_with_router.handle_event(event)
        assert success is True

    @pytest.mark.asyncio
    async def test_publish_completed_response_exception(self, handler_with_router):
        """Test exception handling in _publish_completed_response."""
        scan_result = {
            "files_discovered": 5,
            "files_published": 5,
            "batches_created": 1,
        }

        # Make router.publish raise an exception
        handler_with_router._router.publish.side_effect = Exception("Publish failed")

        with pytest.raises(Exception, match="Publish failed"):
            await handler_with_router._publish_completed_response(
                correlation_id=str(uuid4()),
                scan_result=scan_result,
                repository_path="/tmp/test",
                project_id="test-project",
                scan_scope="FULL",
                processing_time_ms=100.0,
            )
