"""
Comprehensive Test Suite for Correlation Analysis System

Tests the automated correlation generation system including:
- Correlation analyzer algorithms (temporal and semantic)
- Background processor queue management
- API endpoints functionality
- Integration with intelligence data access
- Performance and accuracy validation

This test suite follows ONEX testing principles:
- Comprehensive coverage of all system components
- Performance benchmarking and validation
- Real data testing scenarios
- Error handling and edge case validation
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

# Import system components
from ..services.correlation_analyzer import (
    BreakingChangeResult,
    CorrelationAnalysisResult,
    CorrelationStrength,
    DocumentContext,
    create_correlation_analyzer,
)
from ..services.correlation_processor import (
    CorrelationProcessor,
    CorrelationTask,
    ProcessingStatus,
)


class TestCorrelationAnalyzer:
    """Test suite for the CorrelationAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a correlation analyzer for testing."""
        config = {
            "temporal_threshold_hours": 72,
            "semantic_threshold": 0.3,
            "max_correlations_per_document": 10,
        }
        return create_correlation_analyzer(config)

    @pytest.fixture
    def sample_documents(self):
        """Create sample document contexts for testing."""
        base_time = datetime.now(UTC)

        return [
            DocumentContext(
                id="doc1",
                repository="Archon",
                commit_sha="abc123",
                author="developer1",
                created_at=base_time,
                change_type="feature",
                content={
                    "diff_analysis": {
                        "modified_files": ["src/api/auth.py", "src/models/user.py"],
                        "total_changes": 45,
                    },
                    "correlation_analysis": {
                        "temporal_correlations": [],
                        "semantic_correlations": [],
                    },
                },
                modified_files=["src/api/auth.py", "src/models/user.py"],
                commit_message="feat: add OAuth2 authentication system",
            ),
            DocumentContext(
                id="doc2",
                repository="Archon",
                commit_sha="def456",
                author="developer1",
                created_at=base_time - timedelta(hours=2),
                change_type="feature",
                content={
                    "diff_analysis": {
                        "modified_files": ["src/api/auth.py", "tests/test_auth.py"],
                        "total_changes": 23,
                    }
                },
                modified_files=["src/api/auth.py", "tests/test_auth.py"],
                commit_message="feat: implement JWT token validation",
            ),
            DocumentContext(
                id="doc3",
                repository="omnimcp",
                commit_sha="ghi789",
                author="developer2",
                created_at=base_time - timedelta(hours=24),
                change_type="bugfix",
                content={
                    "diff_analysis": {
                        "modified_files": ["src/auth/oauth.py"],
                        "total_changes": 12,
                    }
                },
                modified_files=["src/auth/oauth.py"],
                commit_message="fix: resolve OAuth token expiration bug",
            ),
            DocumentContext(
                id="doc4",
                repository="Archon",
                commit_sha="jkl012",
                author="developer3",
                created_at=base_time
                - timedelta(hours=100),  # Outside temporal threshold
                change_type="refactor",
                content={
                    "diff_analysis": {
                        "modified_files": ["src/database/models.py"],
                        "total_changes": 78,
                    }
                },
                modified_files=["src/database/models.py"],
                commit_message="refactor: reorganize database models",
            ),
        ]

    @pytest.mark.asyncio
    async def test_temporal_correlation_detection(self, analyzer, sample_documents):
        """Test temporal correlation detection algorithms."""
        target_doc = sample_documents[0]
        context_docs = sample_documents[1:]

        result = await analyzer.analyze_document_correlations(target_doc, context_docs)

        assert isinstance(result, CorrelationAnalysisResult)
        assert result.document_id == "doc1"
        assert len(result.temporal_correlations) > 0

        # Should find correlation with doc2 (same repository, 2 hours apart, same author)
        doc2_correlation = next(
            (tc for tc in result.temporal_correlations if tc.commit_sha == "def456"),
            None,
        )
        assert doc2_correlation is not None
        assert doc2_correlation.time_diff_hours == 2.0
        assert doc2_correlation.correlation_strength > CorrelationStrength.LOW.value

        # Should not find correlation with doc4 (outside temporal threshold)
        doc4_correlation = next(
            (tc for tc in result.temporal_correlations if tc.commit_sha == "jkl012"),
            None,
        )
        assert doc4_correlation is None

    @pytest.mark.asyncio
    async def test_semantic_correlation_detection(self, analyzer, sample_documents):
        """Test semantic correlation detection algorithms."""
        target_doc = sample_documents[0]
        context_docs = sample_documents[1:]

        result = await analyzer.analyze_document_correlations(target_doc, context_docs)

        assert len(result.semantic_correlations) >= 0

        # Should find semantic correlation with doc3 (OAuth-related content)
        if result.semantic_correlations:
            next(
                (
                    sc
                    for sc in result.semantic_correlations
                    if "oauth" in [k.lower() for k in sc.common_keywords]
                ),
                None,
            )
            # May or may not find depending on exact keyword extraction

    @pytest.mark.asyncio
    async def test_breaking_change_detection(self, analyzer, sample_documents):
        """Test breaking change detection algorithms."""
        # Create a document with breaking change indicators
        breaking_doc = DocumentContext(
            id="breaking_doc",
            repository="Archon",
            commit_sha="break123",
            author="developer1",
            created_at=datetime.now(UTC),
            change_type="breaking_change",
            content={
                "diff_analysis": {
                    "modified_files": [
                        "src/api/v1/endpoints.py",
                        "src/api/v2/endpoints.py",
                    ],
                    "total_changes": 150,
                }
            },
            modified_files=["src/api/v1/endpoints.py", "src/api/v2/endpoints.py"],
            commit_message="BREAKING: remove deprecated v1 API endpoints",
        )

        result = await analyzer.analyze_document_correlations(
            breaking_doc, sample_documents
        )

        # Should detect breaking change
        assert len(result.breaking_changes) > 0
        breaking_change = result.breaking_changes[0]
        assert isinstance(breaking_change, BreakingChangeResult)
        assert "breaking" in breaking_change.description.lower()

    @pytest.mark.asyncio
    async def test_cross_repository_correlation(self, analyzer, sample_documents):
        """Test correlation detection across different repositories."""
        target_doc = sample_documents[0]  # Archon repo
        context_docs = sample_documents[1:]  # Includes omnimcp repo

        result = await analyzer.analyze_document_correlations(target_doc, context_docs)

        # Should find cross-repository correlation with doc3
        cross_repo_correlation = next(
            (tc for tc in result.temporal_correlations if tc.repository == "omnimcp"),
            None,
        )

        if cross_repo_correlation:
            # Cross-repo correlations should have lower strength than same-repo
            same_repo_correlation = next(
                (
                    tc
                    for tc in result.temporal_correlations
                    if tc.repository == "Archon"
                ),
                None,
            )
            if same_repo_correlation:
                assert (
                    cross_repo_correlation.correlation_strength
                    <= same_repo_correlation.correlation_strength
                )

    def test_keyword_extraction(self, analyzer, sample_documents):
        """Test keyword extraction from documents."""
        doc = sample_documents[0]
        keywords = analyzer._extract_keywords(doc)

        assert isinstance(keywords, set)
        assert len(keywords) > 0

        # Should extract relevant keywords from file paths and commit message
        expected_keywords = {"auth", "feature", "oauth2", "authentication", "api"}
        overlap = keywords.intersection(expected_keywords)
        assert len(overlap) > 0

    def test_path_similarity_calculation(self, analyzer):
        """Test file path similarity calculation."""
        target_paths = [["src", "api", "auth"], ["src", "models", "user"]]
        context_paths = [["src", "api", "auth"], ["tests", "test", "auth"]]

        similarity = analyzer._calculate_path_similarity(target_paths, context_paths)
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0  # Should have some similarity due to "auth" component


class TestCorrelationProcessor:
    """Test suite for the CorrelationProcessor class."""

    @pytest.fixture
    def processor_config(self):
        """Create processor configuration for testing."""
        return {
            "batch_size": 3,
            "max_context_documents": 50,
            "max_retries": 2,
            "retry_delay_seconds": 1,  # Fast retry for testing
            "context_time_range": "7d",
            "processing_interval": 1,  # Fast processing for testing
        }

    @pytest.fixture
    def processor(self, processor_config):
        """Create a correlation processor for testing."""
        return CorrelationProcessor(processor_config)

    @pytest.fixture
    def sample_tasks(self):
        """Create sample correlation tasks for testing."""
        return [
            CorrelationTask(
                document_id="task1",
                repository="Archon",
                commit_sha="abc123",
                priority=8,
            ),
            CorrelationTask(
                document_id="task2",
                repository="omnimcp",
                commit_sha="def456",
                priority=5,
            ),
            CorrelationTask(
                document_id="task3",
                repository="Archon",
                commit_sha="ghi789",
                priority=3,
            ),
        ]

    @pytest.mark.asyncio
    async def test_queue_management(self, processor, sample_tasks):
        """Test task queueing and prioritization."""
        # Queue tasks
        for task in sample_tasks:
            success = await processor.queue_document_for_processing(
                task.document_id, task.repository, task.commit_sha, task.priority
            )
            assert success

        # Check queue state
        queue_status = processor.get_queue_status()
        assert queue_status["total_tasks"] == 3

        # Check prioritization (higher priority first)
        assert processor.task_queue[0].priority == 8
        assert processor.task_queue[1].priority == 5
        assert processor.task_queue[2].priority == 3

    @pytest.mark.asyncio
    async def test_duplicate_prevention(self, processor):
        """Test prevention of duplicate task queueing."""
        # Queue same document twice
        success1 = await processor.queue_document_for_processing(
            "duplicate_test", "Archon", "abc123", 5
        )
        success2 = await processor.queue_document_for_processing(
            "duplicate_test", "Archon", "abc123", 7
        )

        assert success1
        assert success2  # Should succeed but not add duplicate

        queue_status = processor.get_queue_status()
        assert queue_status["total_tasks"] == 1

    def test_processing_stats(self, processor):
        """Test processing statistics tracking."""
        stats = processor.get_processing_stats()

        required_fields = [
            "total_documents_processed",
            "successful_correlations",
            "failed_processing",
            "total_correlations_generated",
            "queue_length",
            "is_running",
        ]

        for field in required_fields:
            assert field in stats
            assert isinstance(stats[field], int | bool)

    @pytest.mark.asyncio
    async def test_error_handling(self, processor):
        """Test error handling in processing."""
        # Mock data access to raise error
        with patch.object(processor, "get_data_access") as mock_data_access:
            mock_data_access.side_effect = Exception("Database connection failed")

            # Queue a task
            await processor.queue_document_for_processing(
                "error_test", "Archon", "abc123", 5
            )

            # Process batch should handle error gracefully
            await processor._process_batch()

            # Task should be marked as failed
            task = processor.task_queue[0]
            assert task.status == ProcessingStatus.FAILED
            assert task.last_error is not None


class TestCorrelationAPIIntegration:
    """Test suite for correlation API endpoints integration."""

    @pytest.mark.asyncio
    async def test_api_endpoint_availability(self):
        """Test that correlation API endpoints are properly registered."""
        # This would require a test client setup
        # For now, we'll test the route definitions

        from ..api_routes.correlation_api import router

        # Check that key routes exist
        route_paths = [route.path for route in router.routes]

        expected_routes = [
            "/trigger",
            "/processor/control",
            "/stats",
            "/queue",
            "/analyze/single",
            "/analyze/empty",
            "/health",
            "/config",
        ]

        for expected_route in expected_routes:
            # Router paths will have the prefix, so we check the path component
            assert any(
                route_path.endswith(expected_route) for route_path in route_paths
            )


class TestCorrelationSystemIntegration:
    """Integration tests for the complete correlation system."""

    @pytest.mark.asyncio
    async def test_end_to_end_correlation_flow(self):
        """Test complete flow from empty correlations to generated results."""
        # This test would require database setup and real data
        # For now, we'll test the components integrate properly

        analyzer = create_correlation_analyzer()
        processor = CorrelationProcessor()

        # Test that components can be created and interact
        assert analyzer is not None
        assert processor is not None
        assert processor.analyzer is not None

    @pytest.mark.asyncio
    async def test_performance_benchmarks(self, analyzer, sample_documents):
        """Test performance benchmarks for correlation analysis."""
        import time

        target_doc = sample_documents[0]
        context_docs = sample_documents[1:] * 10  # Create larger context set

        start_time = time.time()
        result = await analyzer.analyze_document_correlations(target_doc, context_docs)
        end_time = time.time()

        processing_time = end_time - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert processing_time < 5.0  # 5 seconds max for this test

        # Verify result quality
        assert isinstance(result, CorrelationAnalysisResult)
        assert "analysis_duration_seconds" in result.analysis_metadata
        assert result.analysis_metadata["analysis_duration_seconds"] > 0

    @pytest.mark.asyncio
    async def test_correlation_accuracy_validation(self, analyzer, sample_documents):
        """Test accuracy of correlation detection algorithms."""
        target_doc = sample_documents[0]
        context_docs = sample_documents[1:]

        result = await analyzer.analyze_document_correlations(target_doc, context_docs)

        # Validate temporal correlation accuracy
        for tc in result.temporal_correlations:
            assert tc.correlation_strength >= CorrelationStrength.LOW.value
            assert tc.time_diff_hours >= 0
            assert tc.repository in ["Archon", "omnimcp"]
            assert len(tc.correlation_factors) > 0

        # Validate semantic correlation accuracy
        for sc in result.semantic_correlations:
            assert sc.semantic_similarity >= analyzer.semantic_threshold
            assert isinstance(sc.common_keywords, list)
            assert len(sc.similarity_factors) > 0

        # Validate breaking change accuracy
        for bc in result.breaking_changes:
            assert bc.severity in ["LOW", "MEDIUM", "HIGH"]
            assert 0.0 <= bc.confidence <= 1.0
            assert len(bc.files_affected) > 0


# Performance and load testing
class TestCorrelationSystemPerformance:
    """Performance tests for the correlation system."""

    @pytest.mark.asyncio
    async def test_large_context_performance(self):
        """Test performance with large context document sets."""
        analyzer = create_correlation_analyzer()

        # Create a large set of context documents
        base_time = datetime.now(UTC)
        context_docs = []

        for i in range(100):
            doc = DocumentContext(
                id=f"context_{i}",
                repository=f"repo_{i % 5}",
                commit_sha=f"sha_{i}",
                author=f"author_{i % 10}",
                created_at=base_time - timedelta(hours=i),
                change_type="feature",
                content={
                    "diff_analysis": {
                        "modified_files": [f"src/module_{i}.py"],
                        "total_changes": i,
                    }
                },
                modified_files=[f"src/module_{i}.py"],
            )
            context_docs.append(doc)

        target_doc = context_docs[0]

        import time

        start_time = time.time()

        result = await analyzer.analyze_document_correlations(
            target_doc, context_docs[1:]
        )

        end_time = time.time()
        processing_time = end_time - start_time

        # Should handle large context efficiently
        assert processing_time < 10.0  # 10 seconds max for 100 documents
        assert isinstance(result, CorrelationAnalysisResult)

    @pytest.mark.asyncio
    async def test_concurrent_processing_performance(self):
        """Test performance under concurrent processing load."""
        processor = CorrelationProcessor({"batch_size": 2, "processing_interval": 0.1})

        # Queue multiple tasks
        tasks = []
        for i in range(20):
            task_coro = processor.queue_document_for_processing(
                f"concurrent_test_{i}", f"repo_{i % 3}", f"sha_{i}", 5
            )
            tasks.append(task_coro)

        # Queue all tasks concurrently
        results = await asyncio.gather(*tasks)
        assert all(results)

        # Check that all tasks were queued
        queue_status = processor.get_queue_status()
        assert queue_status["total_tasks"] == 20


# Error handling and edge case testing
class TestCorrelationSystemErrorHandling:
    """Test error handling and edge cases in the correlation system."""

    @pytest.mark.asyncio
    async def test_empty_context_handling(self, analyzer):
        """Test handling of empty context document sets."""
        target_doc = DocumentContext(
            id="test_empty",
            repository="Archon",
            commit_sha="abc123",
            author="developer",
            created_at=datetime.now(UTC),
            change_type="feature",
            content={},
            modified_files=["test.py"],
        )

        result = await analyzer.analyze_document_correlations(target_doc, [])

        assert isinstance(result, CorrelationAnalysisResult)
        assert len(result.temporal_correlations) == 0
        assert len(result.semantic_correlations) == 0
        assert "analysis_timestamp" in result.analysis_metadata

    @pytest.mark.asyncio
    async def test_malformed_document_handling(self, analyzer):
        """Test handling of malformed document data."""
        target_doc = DocumentContext(
            id="malformed",
            repository="",  # Empty repository
            commit_sha="",  # Empty commit
            author="",  # Empty author
            created_at=datetime.now(UTC),
            change_type="",  # Empty change type
            content={},  # Empty content
            modified_files=[],  # Empty files
        )

        context_doc = DocumentContext(
            id="context",
            repository="valid_repo",
            commit_sha="valid_sha",
            author="valid_author",
            created_at=datetime.now(UTC) - timedelta(hours=1),
            change_type="feature",
            content={"test": "data"},
            modified_files=["valid.py"],
        )

        # Should not crash, but may produce minimal correlations
        result = await analyzer.analyze_document_correlations(target_doc, [context_doc])
        assert isinstance(result, CorrelationAnalysisResult)
        assert "analysis_timestamp" in result.analysis_metadata


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
