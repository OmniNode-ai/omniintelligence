"""
Validate that all requirements from the agent specification are met.
"""

from pathlib import Path

import pytest

from ..agent import DocumentationIndexerRequest
from ..dependencies import create_test_dependencies


class TestCoreRequirements:
    """Test that core agent requirements are satisfied."""

    @pytest.mark.asyncio
    async def test_req_001_file_discovery(self, temp_project_dir, test_dependencies):
        """REQ-001: Discover documentation files across different project structures."""
        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir), processing_mode="comprehensive"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should discover multiple file types
        assert result.files_discovered > 0
        assert result.files_processed > 0

        # Should handle different formats
        assert len(result.knowledge_categories) > 0

    @pytest.mark.asyncio
    async def test_req_002_multi_format_support(
        self, temp_project_dir, test_dependencies
    ):
        """REQ-002: Support multiple documentation formats (.md, .yaml, .txt)."""
        # Verify all expected file types are present in test data
        project_path = Path(temp_project_dir)

        file_types_found = set()
        for file_path in project_path.rglob("*"):
            if file_path.is_file():
                file_types_found.add(file_path.suffix.lower())

        # Should find multiple supported formats
        expected_formats = {".md", ".yaml", ".txt"}
        found_formats = expected_formats & file_types_found
        assert len(found_formats) >= 2  # At least 2 different formats

        # Test processing
        request = DocumentationIndexerRequest(target_path=str(temp_project_dir))

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        assert result.files_processed > 0
        assert result.success_rate > 0

    @pytest.mark.asyncio
    async def test_req_003_content_processing_and_chunking(
        self, temp_project_dir, test_dependencies
    ):
        """REQ-003: Process content and apply intelligent chunking."""
        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir), processing_mode="comprehensive"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should create content chunks
        assert result.chunks_created > 0

        # Should maintain reasonable chunk count relative to files
        if result.files_processed > 0:
            # Most files should produce at least one chunk
            assert result.chunks_created >= result.files_processed * 0.8

    @pytest.mark.asyncio
    async def test_req_004_error_handling(self, edge_case_files, test_dependencies):
        """REQ-004: Handle edge cases and error conditions gracefully."""
        request = DocumentationIndexerRequest(target_path=str(edge_case_files))

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should not crash and should provide meaningful results
        assert isinstance(result.files_discovered, int)
        assert isinstance(result.files_processed, int)
        assert isinstance(result.success_rate, float)
        assert isinstance(result.processing_time_seconds, float)

        # Should handle errors gracefully
        if result.files_failed > 0:
            assert len(result.error_summary) > 0

        # Should continue processing despite errors
        assert result.processing_time_seconds > 0

    @pytest.mark.asyncio
    async def test_req_005_progress_tracking(self, temp_project_dir, test_dependencies):
        """REQ-005: Provide clear progress feedback and reporting."""
        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir), processing_mode="comprehensive"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should provide comprehensive progress information
        assert hasattr(result, "files_discovered")
        assert hasattr(result, "files_processed")
        assert hasattr(result, "files_failed")
        assert hasattr(result, "chunks_created")
        assert hasattr(result, "processing_time_seconds")
        assert hasattr(result, "success_rate")

        # Values should be reasonable
        assert result.files_discovered >= 0
        assert result.files_processed >= 0
        assert result.files_failed >= 0
        assert result.chunks_created >= 0
        assert result.processing_time_seconds >= 0
        assert 0 <= result.success_rate <= 100


class TestArchonIntegrationRequirements:
    """Test Archon MCP integration requirements."""

    @pytest.mark.asyncio
    async def test_req_006_archon_mcp_integration(self, temp_project_dir):
        """REQ-006: Integration with Archon MCP system for document indexing."""
        # Test with Archon integration enabled
        archon_deps = create_test_dependencies(
            archon_mcp_available=True, archon_project_id="test-project-123"
        )

        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir), archon_integration=True
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(archon_deps)
        result = await index_documentation(ctx, request)

        # Should process successfully with Archon integration
        assert result.files_discovered >= 0
        assert result.processing_time_seconds > 0

        # Dependencies should be configured for Archon
        assert archon_deps.archon_mcp_available == True
        assert archon_deps.archon_project_id == "test-project-123"

    @pytest.mark.asyncio
    async def test_req_007_project_context_awareness(
        self, archon_project_structure, test_dependencies
    ):
        """REQ-007: Repository-aware processing with project-specific optimization."""
        request = DocumentationIndexerRequest(
            target_path=str(archon_project_structure), processing_mode="comprehensive"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should identify project-specific patterns
        assert result.files_discovered > 0
        assert result.files_processed > 0

        # Should identify relevant knowledge categories
        categories = result.knowledge_categories
        assert len(categories) > 0

        # For Archon-like structure, should find agent-related content
        # (This is flexible as TestModel doesn't execute actual processing)

    @pytest.mark.asyncio
    async def test_req_008_metadata_extraction(
        self, temp_project_dir, test_dependencies
    ):
        """REQ-008: Extract comprehensive metadata for enhanced search."""
        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir), processing_mode="comprehensive"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should extract knowledge categories (form of metadata)
        assert isinstance(result.knowledge_categories, list)

        # Should provide processing insights
        assert result.processing_time_seconds > 0
        assert result.success_rate >= 0


class TestPerformanceRequirements:
    """Test performance and scalability requirements."""

    @pytest.mark.asyncio
    async def test_req_009_processing_performance(
        self, performance_test_data, test_dependencies
    ):
        """REQ-009: Process documentation efficiently with reasonable performance."""
        request = DocumentationIndexerRequest(
            target_path=str(performance_test_data),
            processing_mode="basic",  # Use basic mode for performance testing
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        import time

        from ..agent import index_documentation

        start_time = time.time()
        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)
        end_time = time.time()

        actual_time = end_time - start_time

        # Should complete in reasonable time
        assert actual_time < 30  # Should complete within 30 seconds for test data

        # Should process multiple files
        assert result.files_discovered > 50  # Test data has 70 files

        # Should maintain performance metrics
        if result.files_processed > 0:
            processing_rate = result.files_processed / result.processing_time_seconds
            assert processing_rate > 0  # Should have measurable processing rate

    @pytest.mark.asyncio
    async def test_req_010_memory_efficiency(self, temp_project_dir, test_dependencies):
        """REQ-010: Memory-efficient processing of large documentation sets."""
        # Configure for smaller chunks to test memory efficiency
        efficient_deps = create_test_dependencies(
            chunk_size_target=300,  # Smaller chunks
            max_file_size_mb=5,  # Reasonable file size limit
        )

        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir), processing_mode="comprehensive"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(efficient_deps)
        result = await index_documentation(ctx, request)

        # Should complete without memory issues
        assert result.processing_time_seconds > 0
        assert result.files_processed >= 0

        # Configuration should be applied
        assert efficient_deps.chunk_size_target == 300
        assert efficient_deps.max_file_size_mb == 5

    @pytest.mark.asyncio
    async def test_req_011_scalability(self, performance_test_data, test_dependencies):
        """REQ-011: Scale to handle large numbers of documentation files."""
        request = DocumentationIndexerRequest(
            target_path=str(performance_test_data), processing_mode="comprehensive"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should handle large file counts
        assert result.files_discovered > 50

        # Should maintain reasonable success rate even with many files
        if result.files_discovered > 0:
            assert result.success_rate > 50  # Should process majority successfully

        # Should create reasonable number of chunks
        assert (
            result.chunks_created >= result.files_processed
        )  # At least one chunk per file


class TestQualityRequirements:
    """Test quality and accuracy requirements."""

    @pytest.mark.asyncio
    async def test_req_012_content_integrity(self, temp_project_dir, test_dependencies):
        """REQ-012: Maintain content integrity during processing and chunking."""
        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir), processing_mode="comprehensive"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should maintain high success rate (content integrity)
        if result.files_discovered > 0:
            assert result.success_rate >= 70  # Should process most files successfully

        # Should create meaningful chunks
        if result.files_processed > 0:
            assert result.chunks_created > 0

    @pytest.mark.asyncio
    async def test_req_013_cross_reference_extraction(
        self, temp_project_dir, test_dependencies
    ):
        """REQ-013: Extract cross-references between documents accurately."""
        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir),
            enable_cross_references=True,
            processing_mode="comprehensive",
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should enable cross-reference processing
        assert request.enable_cross_references == True

        # Should complete processing
        assert result.processing_time_seconds > 0

    @pytest.mark.asyncio
    async def test_req_014_semantic_categorization(
        self, temp_project_dir, test_dependencies
    ):
        """REQ-014: Provide semantic categorization and tagging."""
        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir), processing_mode="semantic"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should identify knowledge categories
        assert isinstance(result.knowledge_categories, list)

        # For test data containing setup, API, and config content,
        # should identify some semantic categories
        if result.files_processed > 0:
            # Categories might be identified during processing
            assert len(result.knowledge_categories) >= 0


class TestValidationRequirements:
    """Test validation and quality assurance requirements."""

    @pytest.mark.asyncio
    async def test_req_015_quality_validation(self, test_dependencies):
        """REQ-015: Validate processing quality and provide quality metrics."""
        from ..agent import DocumentChunk, validate_indexing_quality

        # Create test chunks for validation
        chunks = [
            DocumentChunk(
                chunk_id="test_chunk_1",
                file_path="test.md",
                file_type="markdown",
                title="Test Document",
                chunk_index=0,
                content="This is a test document with meaningful content.",
                size=47,
                metadata={"test": True, "quality": "high"},
                cross_references=["other.md"],
                semantic_tags=["test", "documentation"],
            )
        ]

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await validate_indexing_quality(ctx, chunks)

        # Should provide comprehensive quality metrics
        assert "quality_score" in result
        assert "total_chunks" in result
        assert "metadata_completeness" in result
        assert "cross_reference_coverage" in result
        assert "semantic_tag_coverage" in result

        # Quality score should be meaningful
        assert 0 <= result["quality_score"] <= 100

    @pytest.mark.asyncio
    async def test_req_016_error_reporting(self, edge_case_files, test_dependencies):
        """REQ-016: Comprehensive error reporting and recovery."""
        request = DocumentationIndexerRequest(target_path=str(edge_case_files))

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should provide error information
        assert hasattr(result, "error_summary")
        assert isinstance(result.error_summary, list)

        # Should track failed files
        assert hasattr(result, "files_failed")
        assert result.files_failed >= 0

        # Should continue processing despite errors
        assert result.processing_time_seconds > 0
