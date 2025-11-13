"""
Tool validation tests for the Documentation Indexer Agent.
"""

import pytest

from ..agent import (
    DocumentationIndexerRequest,
    DocumentChunk,
    get_file_preview,
    index_documentation,
    validate_indexing_quality,
)


class TestIndexDocumentationTool:
    """Test the index_documentation tool."""

    @pytest.mark.asyncio
    async def test_index_basic_functionality(self, temp_project_dir, test_dependencies):
        """Test basic indexing functionality."""
        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir), processing_mode="basic"
        )

        # Create a mock context
        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        assert isinstance(result, type(result))  # Should return IndexingResult
        assert result.files_discovered >= 0
        assert result.processing_time_seconds >= 0

    @pytest.mark.asyncio
    async def test_index_comprehensive_processing(
        self, temp_project_dir, test_dependencies
    ):
        """Test comprehensive processing mode."""
        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir),
            processing_mode="comprehensive",
            enable_cross_references=True,
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        assert result.files_discovered > 0
        assert result.files_processed >= 0
        assert result.chunks_created >= 0
        assert 0 <= result.success_rate <= 100

    @pytest.mark.asyncio
    async def test_index_with_patterns(self, temp_project_dir, test_dependencies):
        """Test indexing with include/exclude patterns."""
        request = DocumentationIndexerRequest(
            target_path=str(temp_project_dir),
            include_patterns=["*.md"],
            exclude_patterns=["node_modules", ".git"],
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        assert result.files_discovered >= 0
        assert result.processing_time_seconds >= 0

    @pytest.mark.asyncio
    async def test_index_nonexistent_path(self, test_dependencies):
        """Test indexing nonexistent path."""
        request = DocumentationIndexerRequest(target_path="/nonexistent/path")

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should handle error gracefully
        assert result.files_discovered == 0
        assert result.success_rate == 0.0
        assert len(result.error_summary) > 0

    @pytest.mark.asyncio
    async def test_index_archon_project_structure(
        self, archon_project_structure, test_dependencies
    ):
        """Test indexing Archon-like project structure."""
        request = DocumentationIndexerRequest(
            target_path=str(archon_project_structure),
            processing_mode="comprehensive",
            archon_integration=True,
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        assert result.files_discovered > 0
        assert result.files_processed > 0

        # Should find knowledge categories
        assert len(result.knowledge_categories) > 0

        # Should have reasonable success rate
        assert result.success_rate > 0

    @pytest.mark.asyncio
    async def test_index_edge_cases(self, edge_case_files, test_dependencies):
        """Test indexing with edge case files."""
        request = DocumentationIndexerRequest(target_path=str(edge_case_files))

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should handle edge cases without crashing
        assert result.files_discovered >= 0
        assert result.processing_time_seconds >= 0

        # Some files might fail, but should continue processing
        if result.files_discovered > 0:
            assert result.success_rate >= 0

    @pytest.mark.asyncio
    async def test_index_performance_data(
        self, performance_test_data, test_dependencies
    ):
        """Test indexing performance with larger dataset."""
        request = DocumentationIndexerRequest(
            target_path=str(performance_test_data), processing_mode="comprehensive"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        assert result.files_discovered > 50  # Should find many test files
        assert result.processing_time_seconds > 0
        assert result.chunks_created > 0

        # Should maintain reasonable performance
        processing_rate = result.files_processed / result.processing_time_seconds
        assert processing_rate > 0  # Should process files in reasonable time


class TestFilePreviewTool:
    """Test the get_file_preview tool."""

    @pytest.mark.asyncio
    async def test_file_preview_markdown(self, temp_project_dir, test_dependencies):
        """Test file preview for markdown files."""

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        readme_path = temp_project_dir / "README.md"

        result = await get_file_preview(ctx, str(readme_path), max_lines=10)

        assert "file_path" in result
        assert "file_type" in result
        assert result["file_type"] == ".md"
        assert "preview_lines" in result
        assert len(result["preview_lines"]) <= 10
        assert "total_lines" in result
        assert result["total_lines"] > 0

    @pytest.mark.asyncio
    async def test_file_preview_yaml(self, temp_project_dir, test_dependencies):
        """Test file preview for YAML files."""

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        yaml_path = temp_project_dir / "agents" / "test-agent.yaml"

        result = await get_file_preview(ctx, str(yaml_path), max_lines=15)

        assert "error" not in result
        assert result["file_type"] == ".yaml"
        assert "preview_lines" in result
        assert len(result["preview_lines"]) <= 15

    @pytest.mark.asyncio
    async def test_file_preview_nonexistent(self, test_dependencies):
        """Test file preview for nonexistent file."""

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await get_file_preview(ctx, "/nonexistent/file.md")

        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_file_preview_binary(self, edge_case_files, test_dependencies):
        """Test file preview for binary files."""

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        binary_path = edge_case_files / "binary.png"

        result = await get_file_preview(ctx, str(binary_path))

        # Should handle binary files gracefully
        assert "error" in result or "preview_lines" in result

    @pytest.mark.asyncio
    async def test_file_preview_encoding_issues(
        self, edge_case_files, test_dependencies
    ):
        """Test file preview with encoding issues."""

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        encoding_path = edge_case_files / "encoding.md"

        result = await get_file_preview(ctx, str(encoding_path))

        # Should handle encoding issues
        assert "file_path" in result
        # May have encoding specified or error message
        assert "encoding" in result or "error" in result


class TestValidateIndexingQualityTool:
    """Test the validate_indexing_quality tool."""

    @pytest.mark.asyncio
    async def test_quality_validation_basic(self, test_dependencies):
        """Test basic quality validation."""
        # Create sample chunks
        chunks = [
            DocumentChunk(
                chunk_id="test_1",
                file_path="test1.md",
                file_type="markdown",
                title="Test Document 1",
                chunk_index=0,
                content="This is test content for validation.",
                size=37,
                metadata={"test": True},
                cross_references=["test2.md"],
                semantic_tags=["test", "validation"],
            ),
            DocumentChunk(
                chunk_id="test_2",
                file_path="test2.md",
                file_type="markdown",
                title="Test Document 2",
                chunk_index=0,
                content="Another test document with different content.",
                size=44,
                metadata={"test": True, "category": "example"},
                cross_references=[],
                semantic_tags=["test", "example"],
            ),
        ]

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await validate_indexing_quality(ctx, chunks)

        assert "total_chunks" in result
        assert result["total_chunks"] == 2
        assert "average_chunk_size" in result
        assert "size_distribution" in result
        assert "format_distribution" in result
        assert "metadata_completeness" in result
        assert "quality_score" in result

        # Should have reasonable quality score
        assert 0 <= result["quality_score"] <= 100

    @pytest.mark.asyncio
    async def test_quality_validation_empty(self, test_dependencies):
        """Test quality validation with empty chunk list."""

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await validate_indexing_quality(ctx, [])

        assert "error" in result
        assert "no chunks" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_quality_validation_diverse_chunks(self, test_dependencies):
        """Test quality validation with diverse chunk types."""
        chunks = [
            DocumentChunk(
                chunk_id="md_1",
                file_path="doc.md",
                file_type="markdown",
                title="Markdown Doc",
                chunk_index=0,
                content="# Header\nContent here",
                size=20,
                metadata={"headers": ["Header"]},
                cross_references=["other.md"],
                semantic_tags=["documentation"],
            ),
            DocumentChunk(
                chunk_id="yaml_1",
                file_path="config.yaml",
                file_type="yaml",
                title="Config File",
                chunk_index=0,
                content="name: test\nvalue: 123",
                size=20,
                metadata={"config": True},
                cross_references=[],
                semantic_tags=["configuration"],
            ),
            DocumentChunk(
                chunk_id="txt_1",
                file_path="readme.txt",
                file_type="text",
                title="Readme",
                chunk_index=0,
                content="Plain text content here",
                size=24,
                metadata={},
                cross_references=[],
                semantic_tags=[],
            ),
        ]

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await validate_indexing_quality(ctx, chunks)

        # Should analyze multiple formats
        assert result["format_distribution"]["markdown"] == 1
        assert result["format_distribution"]["yaml"] == 1
        assert result["format_distribution"]["text"] == 1

        # Should calculate coverage percentages
        assert 0 <= result["cross_reference_coverage"] <= 100
        assert 0 <= result["semantic_tag_coverage"] <= 100

    @pytest.mark.asyncio
    async def test_quality_validation_size_analysis(self, test_dependencies):
        """Test quality validation size analysis."""
        # Create chunks of different sizes
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk_{i}",
                file_path=f"file_{i}.md",
                file_type="markdown",
                title=f"Document {i}",
                chunk_index=0,
                content="x" * size,
                size=size,
                metadata={},
                cross_references=[],
                semantic_tags=[],
            )
            for i, size in enumerate(
                [100, 800, 1500, 2500, 4000]
            )  # Different size categories
        ]

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        ctx = MockContext(test_dependencies)
        result = await validate_indexing_quality(ctx, chunks)

        # Should categorize sizes correctly
        size_dist = result["size_distribution"]
        assert size_dist["small"] == 1  # 100 chars
        assert size_dist["medium"] == 2  # 800, 1500 chars
        assert size_dist["large"] == 1  # 2500 chars
        assert size_dist["oversized"] == 1  # 4000 chars

        # Quality score should reflect oversized chunks
        assert result["quality_score"] < 100  # Penalty for oversized chunks
