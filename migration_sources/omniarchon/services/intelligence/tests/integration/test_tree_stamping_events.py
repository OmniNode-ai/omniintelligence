"""
Integration Tests for Tree Stamping Event Flow

End-to-end event flow testing:
- Publish request event → Handler processes → Verify response event
- Test all 3 operations (index, search, status)
- Correlation ID preservation
- Error event publishing
- Concurrent event processing

Created: 2025-10-24
Purpose: Stream E - Testing Infrastructure
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

# Import fixtures
from fixtures.kafka_fixtures import (
    MockEventEnvelope,
    MockKafkaConsumer,
    MockKafkaProducer,
    correlation_tracker,
    event_factory,
)

# Import real handler
from handlers.tree_stamping_handler import TreeStampingHandler

# Import models
from models.file_location import (
    FileSearchResult,
    ProjectIndexResult,
    ProjectIndexStatus,
)

# ==============================================================================
# Integration Test Suite
# ==============================================================================


class TestTreeStampingEventFlowIntegration:
    """Integration tests for complete event flow."""

    @pytest.fixture
    async def event_bus(self):
        """Create mock event bus with producer and consumer."""
        producer = MockKafkaProducer()
        consumer = MockKafkaConsumer()
        return {"producer": producer, "consumer": consumer}

    @pytest.fixture
    def mock_bridge(self):
        """Mock TreeStampingBridge for integration testing."""
        bridge = AsyncMock()

        # Default successful responses
        bridge.index_project = AsyncMock(
            return_value=ProjectIndexResult(
                success=True,
                project_name="test-project",
                files_discovered=100,
                files_indexed=98,
                vector_indexed=98,
                graph_indexed=98,
                cache_warmed=True,
                duration_ms=5000,
                errors=[],
                warnings=["2 files skipped"],
            )
        )

        bridge.search_files = AsyncMock(
            return_value=FileSearchResult(
                success=True,
                results=[],
                query_time_ms=100,
                cache_hit=False,
                total_results=0,
            )
        )

        bridge.get_indexing_status = AsyncMock(
            return_value=[
                ProjectIndexStatus(
                    project_name="test-project",
                    indexed=True,
                    file_count=98,
                    status="indexed",  # Lowercase for ProjectIndexStatus model
                )
            ]
        )

        return bridge

    # ==========================================================================
    # Index Project Flow Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_index_project_success_flow(self, event_bus, mock_bridge):
        """Test complete successful index project flow."""
        producer = event_bus["producer"]
        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer  # Use producer as mock router

        # Sample files with inline content
        files = [
            {
                "relative_path": "test/file1.py",
                "content": "def test_function(): pass",
                "size_bytes": 100,
                "language": "python",
            },
            {
                "relative_path": "test/file2.py",
                "content": "def another_test(): return True",
                "size_bytes": 120,
                "language": "python",
            },
        ]

        # Create request event
        correlation_id = str(uuid4())
        request_event = MockEventEnvelope(
            event_type="tree.index-project-requested",
            correlation_id=correlation_id,
            payload={
                "project_path": "/tmp/test-project",
                "project_name": "test-project",
                "files": files,
                "include_tests": True,
                "force_reindex": False,
            },
        )

        # Process event
        success = await handler.handle_event(request_event)

        # Verify handler succeeded
        assert success is True

        # Verify bridge was called with files parameter
        mock_bridge.index_project.assert_called_once_with(
            project_path="/tmp/test-project",
            project_name="test-project",
            files=files,
            include_tests=True,
            force_reindex=False,
        )

        # Verify response event published
        published_events = producer.get_events_for_correlation(correlation_id)
        assert len(published_events) == 1

        response_event = published_events[0]
        assert (
            response_event["topic"]
            == "dev.archon-intelligence.tree.index-project-completed.v1"
        )
        assert response_event["correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_index_project_failure_flow(self, event_bus, mock_bridge):
        """Test complete failed index project flow."""
        producer = event_bus["producer"]

        # Configure bridge to fail
        mock_bridge.index_project.return_value = ProjectIndexResult(
            success=False,
            project_name="test-project",
            files_discovered=0,
            files_indexed=0,
            vector_indexed=0,
            graph_indexed=0,
            cache_warmed=False,
            duration_ms=100,
            errors=["OnexTree service unavailable"],
            warnings=[],
        )

        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer

        # Sample files with inline content
        files = [
            {
                "relative_path": "src/main.py",
                "content": "def main(): print('Hello')",
                "size_bytes": 80,
                "language": "python",
            },
        ]

        # Create request event
        correlation_id = str(uuid4())
        request_event = MockEventEnvelope(
            event_type="tree.index-project-requested",
            correlation_id=correlation_id,
            payload={
                "project_path": "/tmp/test",
                "project_name": "test",
                "files": files,
            },
        )

        # Process event
        success = await handler.handle_event(request_event)

        # Verify handler reported failure
        assert success is False

        # Verify failed event published
        published_events = producer.get_events_for_correlation(correlation_id)
        assert len(published_events) == 1

        response_event = published_events[0]
        assert (
            response_event["topic"]
            == "dev.archon-intelligence.tree.index-project-failed.v1"
        )
        assert response_event["correlation_id"] == correlation_id

    # ==========================================================================
    # Search Files Flow Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_search_files_success_flow(self, event_bus, mock_bridge):
        """Test complete successful search files flow."""
        producer = event_bus["producer"]
        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer

        # Create request event
        correlation_id = str(uuid4())
        request_event = MockEventEnvelope(
            event_type="tree.search-files-requested",
            correlation_id=correlation_id,
            payload={
                "query": "authentication module",
                "projects": ["test-project"],
                "file_types": [".py"],
                "min_quality_score": 0.7,
                "limit": 10,
            },
        )

        # Process event
        success = await handler.handle_event(request_event)

        # Verify success
        assert success is True
        mock_bridge.search_files.assert_called_once()

        # Verify response event
        published_events = producer.get_events_for_correlation(correlation_id)
        assert len(published_events) == 1

        response_event = published_events[0]
        assert (
            response_event["topic"]
            == "dev.archon-intelligence.tree.search-files-completed.v1"
        )

    @pytest.mark.asyncio
    async def test_search_files_failure_flow(self, event_bus, mock_bridge):
        """Test complete failed search files flow."""
        producer = event_bus["producer"]

        # Configure bridge to fail
        mock_bridge.search_files.return_value = FileSearchResult(
            success=False,
            results=[],
            query_time_ms=100,
            cache_hit=False,
            total_results=0,
            error="Qdrant service unavailable",
        )

        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer

        # Create request event
        correlation_id = str(uuid4())
        request_event = MockEventEnvelope(
            event_type="tree.search-files-requested",
            correlation_id=correlation_id,
            payload={"query": "test"},
        )

        # Process event
        success = await handler.handle_event(request_event)

        # Verify failure
        assert success is False

        # Verify failed event published
        published_events = producer.get_events_for_correlation(correlation_id)
        assert len(published_events) == 1

        response_event = published_events[0]
        assert (
            response_event["topic"]
            == "dev.archon-intelligence.tree.search-files-failed.v1"
        )

    # ==========================================================================
    # Get Status Flow Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_status_success_flow(self, event_bus, mock_bridge):
        """Test complete successful get status flow."""
        producer = event_bus["producer"]
        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer

        # Create request event
        correlation_id = str(uuid4())
        request_event = MockEventEnvelope(
            event_type="tree.get-status-requested",
            correlation_id=correlation_id,
            payload={"project_name": "test-project"},
        )

        # Process event
        success = await handler.handle_event(request_event)

        # Verify success
        assert success is True
        mock_bridge.get_indexing_status.assert_called_once_with(
            project_name="test-project"
        )

        # Verify response event
        published_events = producer.get_events_for_correlation(correlation_id)
        assert len(published_events) == 1

        response_event = published_events[0]
        assert (
            response_event["topic"]
            == "dev.archon-intelligence.tree.get-status-completed.v1"
        )

    # ==========================================================================
    # Correlation ID Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_correlation_id_preservation(self, event_bus, mock_bridge):
        """Test correlation ID is preserved through event flow."""
        producer = event_bus["producer"]
        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer

        # Use specific correlation ID (must be valid UUID format)
        correlation_id = str(uuid4())

        # Sample files with inline content
        files = [
            {
                "relative_path": "test/correlation_test.py",
                "content": "# Test for correlation preservation",
                "size_bytes": 40,
                "language": "python",
            },
        ]

        request_event = MockEventEnvelope(
            event_type="tree.index-project-requested",
            correlation_id=correlation_id,
            payload={
                "project_path": "/tmp/test",
                "project_name": "test",
                "files": files,
            },
        )

        # Process event
        await handler.handle_event(request_event)

        # Verify correlation ID preserved in response
        published_events = producer.get_events_for_correlation(correlation_id)
        assert len(published_events) == 1
        assert published_events[0]["correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_multiple_requests_different_correlations(
        self, event_bus, mock_bridge
    ):
        """Test multiple requests with different correlation IDs."""
        producer = event_bus["producer"]
        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer

        correlation_id_1 = str(uuid4())
        correlation_id_2 = str(uuid4())

        # Sample files for both requests
        files_1 = [
            {
                "relative_path": "src/module1.py",
                "content": "# Module 1",
                "size_bytes": 50,
                "language": "python",
            },
        ]

        files_2 = [
            {
                "relative_path": "src/module2.py",
                "content": "# Module 2",
                "size_bytes": 50,
                "language": "python",
            },
        ]

        # Process first request
        request_1 = MockEventEnvelope(
            event_type="tree.index-project-requested",
            correlation_id=correlation_id_1,
            payload={
                "project_path": "/tmp/test1",
                "project_name": "test1",
                "files": files_1,
            },
        )
        await handler.handle_event(request_1)

        # Process second request
        request_2 = MockEventEnvelope(
            event_type="tree.index-project-requested",
            correlation_id=correlation_id_2,
            payload={
                "project_path": "/tmp/test2",
                "project_name": "test2",
                "files": files_2,
            },
        )
        await handler.handle_event(request_2)

        # Verify both correlations tracked separately
        events_1 = producer.get_events_for_correlation(correlation_id_1)
        events_2 = producer.get_events_for_correlation(correlation_id_2)

        assert len(events_1) == 1
        assert len(events_2) == 1
        assert events_1[0]["correlation_id"] == correlation_id_1
        assert events_2[0]["correlation_id"] == correlation_id_2

    # ==========================================================================
    # Concurrent Processing Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_concurrent_event_processing(self, event_bus, mock_bridge):
        """Test handler can process multiple events concurrently."""
        producer = event_bus["producer"]
        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer

        # Create multiple events with files
        num_events = 5
        events = [
            MockEventEnvelope(
                event_type="tree.index-project-requested",
                correlation_id=str(uuid4()),
                payload={
                    "project_path": f"/tmp/test{i}",
                    "project_name": f"test{i}",
                    "files": [
                        {
                            "relative_path": f"src/file{i}.py",
                            "content": f"# Test file {i}",
                            "size_bytes": 50,
                            "language": "python",
                        }
                    ],
                },
            )
            for i in range(num_events)
        ]

        # Process concurrently
        results = await asyncio.gather(*[handler.handle_event(e) for e in events])

        # Verify all succeeded
        assert all(results)
        assert handler.metrics["events_handled"] == num_events

        # Verify all responses published
        assert len(producer.published_events) == num_events

    # ==========================================================================
    # Error Handling Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_bridge_exception_publishes_failure_event(
        self, event_bus, mock_bridge
    ):
        """Test bridge exception results in failure event."""
        producer = event_bus["producer"]

        # Configure bridge to raise exception
        mock_bridge.index_project.side_effect = Exception("Bridge failure")

        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer

        # Sample files with inline content
        files = [
            {
                "relative_path": "src/error_test.py",
                "content": "# This will trigger an error",
                "size_bytes": 60,
                "language": "python",
            },
        ]

        correlation_id = str(uuid4())
        request_event = MockEventEnvelope(
            event_type="tree.index-project-requested",
            correlation_id=correlation_id,
            payload={
                "project_path": "/tmp/test",
                "project_name": "test",
                "files": files,
            },
        )

        # Process event
        success = await handler.handle_event(request_event)

        # Verify failure
        assert success is False

        # Verify failed event published
        published_events = producer.get_events_for_correlation(correlation_id)
        assert len(published_events) == 1
        assert "failed" in published_events[0]["topic"]

    @pytest.mark.asyncio
    async def test_malformed_event_handling(self, event_bus, mock_bridge):
        """Test handler gracefully handles malformed events."""
        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = event_bus["producer"]

        # Malformed event (missing required fields)
        malformed_event = {"some": "data", "event_type": "tree.index-project-requested"}

        # Should not crash
        success = await handler.handle_event(malformed_event)

        # Should report failure
        assert success is False
        assert handler.metrics["events_failed"] == 1

    # ==========================================================================
    # Topic Routing Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_correct_response_topics(self, event_bus, mock_bridge):
        """Test correct response topics are used for each operation."""
        producer = event_bus["producer"]
        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer

        test_cases = [
            {
                "event_type": "tree.index-project-requested",
                "expected_topic": "dev.archon-intelligence.tree.index-project-completed.v1",
                "payload": {
                    "project_path": "/tmp/test",
                    "project_name": "test",
                    "files": [
                        {
                            "relative_path": "test/file.py",
                            "content": "# test content",
                            "size_bytes": 50,
                            "language": "python",
                        }
                    ],
                },
            },
            {
                "event_type": "tree.search-files-requested",
                "expected_topic": "dev.archon-intelligence.tree.search-files-completed.v1",
                "payload": {"query": "test"},
            },
            {
                "event_type": "tree.get-status-requested",
                "expected_topic": "dev.archon-intelligence.tree.get-status-completed.v1",
                "payload": {"project_name": "test"},
            },
        ]

        for test_case in test_cases:
            producer.reset()

            event = MockEventEnvelope(
                event_type=test_case["event_type"],
                correlation_id=str(uuid4()),
                payload=test_case["payload"],
            )

            await handler.handle_event(event)

            assert len(producer.published_events) == 1
            assert producer.published_events[0]["topic"] == test_case["expected_topic"]

    # ==========================================================================
    # Metrics Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_handler_metrics_tracking(self, event_bus, mock_bridge):
        """Test handler tracks metrics correctly during event flow."""
        producer = event_bus["producer"]
        handler = TreeStampingHandler(bridge=mock_bridge)
        handler._router = producer

        # Sample files for success case
        success_files = [
            {
                "relative_path": "src/success.py",
                "content": "def success(): return True",
                "size_bytes": 60,
                "language": "python",
            },
        ]

        # Sample files for failure case
        failure_files = [
            {
                "relative_path": "src/failure.py",
                "content": "def failure(): raise Exception('Error')",
                "size_bytes": 80,
                "language": "python",
            },
        ]

        # Process successful event
        success_event = MockEventEnvelope(
            event_type="tree.index-project-requested",
            payload={
                "project_path": "/tmp/test",
                "project_name": "test",
                "files": success_files,
            },
        )
        await handler.handle_event(success_event)

        assert handler.metrics["events_handled"] == 1
        assert handler.metrics["events_failed"] == 0
        assert handler.metrics["index_project_successes"] == 1

        # Process failed event - handler returns False but doesn't increment events_failed
        # because the error is caught and handled (publishes failed event)
        mock_bridge.index_project.side_effect = Exception("Error")
        fail_event = MockEventEnvelope(
            event_type="tree.index-project-requested",
            payload={
                "project_path": "/tmp/test2",
                "project_name": "test2",
                "files": failure_files,
            },
        )
        await handler.handle_event(fail_event)

        # The handler catches the exception and publishes a failed event
        # events_handled only increments on success, so it stays at 1
        assert handler.metrics["events_handled"] == 1
        assert handler.metrics["index_project_failures"] == 1


# ==============================================================================
# End-to-End Scenario Tests
# ==============================================================================


class TestEndToEndScenarios:
    """End-to-end scenario tests simulating real usage."""

    @pytest.mark.asyncio
    async def test_complete_project_indexing_workflow(self):
        """Test complete workflow: index → verify status → search."""
        # Create mock infrastructure
        producer = MockKafkaProducer()
        bridge = AsyncMock()

        # Configure bridge responses
        bridge.index_project.return_value = ProjectIndexResult(
            success=True,
            project_name="omniarchon",
            files_discovered=1247,
            files_indexed=1245,
            vector_indexed=1245,
            graph_indexed=1245,
            cache_warmed=True,
            duration_ms=285000,
            errors=[],
            warnings=["2 files failed intelligence"],
        )

        bridge.get_indexing_status.return_value = [
            ProjectIndexStatus(
                project_name="omniarchon",
                indexed=True,
                file_count=1245,
                status="indexed",  # Lowercase for ProjectIndexStatus model
            )
        ]

        bridge.search_files.return_value = FileSearchResult(
            success=True,
            results=[],
            query_time_ms=150,
            cache_hit=False,
            total_results=10,
        )

        handler = TreeStampingHandler(bridge=bridge)
        handler._router = producer

        # Sample files from the project
        project_files = [
            {
                "relative_path": "services/intelligence/app.py",
                "content": "from fastapi import FastAPI\napp = FastAPI()",
                "size_bytes": 200,
                "language": "python",
            },
            {
                "relative_path": "services/intelligence/src/api.py",
                "content": "async def health(): return {'status': 'ok'}",
                "size_bytes": 150,
                "language": "python",
            },
            {
                "relative_path": "tests/test_integration.py",
                "content": "import pytest\ndef test_example(): pass",
                "size_bytes": 180,
                "language": "python",
            },
        ]

        # Step 1: Index project
        index_correlation = str(uuid4())
        index_event = MockEventEnvelope(
            event_type="tree.index-project-requested",
            correlation_id=index_correlation,
            payload={
                "project_path": "/Volumes/PRO-G40/Code/omniarchon",
                "project_name": "omniarchon",
                "files": project_files,
            },
        )
        index_success = await handler.handle_event(index_event)
        assert index_success is True

        # Step 2: Check status
        status_correlation = str(uuid4())
        status_event = MockEventEnvelope(
            event_type="tree.get-status-requested",
            correlation_id=status_correlation,
            payload={"project_name": "omniarchon"},
        )
        status_success = await handler.handle_event(status_event)
        assert status_success is True

        # Step 3: Search files
        search_correlation = str(uuid4())
        search_event = MockEventEnvelope(
            event_type="tree.search-files-requested",
            correlation_id=search_correlation,
            payload={
                "query": "kafka event handler",
                "projects": ["omniarchon"],
            },
        )
        search_success = await handler.handle_event(search_event)
        assert search_success is True

        # Verify all operations completed
        assert len(producer.published_events) == 3
        assert handler.metrics["events_handled"] == 3
        assert handler.metrics["events_failed"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
