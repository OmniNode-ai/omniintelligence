"""
Edge case and error handling tests for the Documentation Indexer Agent.
"""

import tempfile
from pathlib import Path

import pytest

from ..agent import DocumentationIndexerRequest, DocumentChunk
from ..dependencies import create_test_dependencies


class TestFileSystemEdgeCases:
    """Test edge cases related to file system operations."""

    @pytest.mark.asyncio
    async def test_empty_directory(self, test_dependencies):
        """Test processing empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            assert result.files_discovered == 0
            assert result.files_processed == 0
            assert result.chunks_created == 0
            assert result.success_rate == 0.0 or result.success_rate == float(
                "nan"
            )  # Handle division by zero

    @pytest.mark.asyncio
    async def test_directory_with_only_excluded_files(self, test_dependencies):
        """Test directory containing only files that should be excluded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create files that should be excluded
            (temp_path / "node_modules").mkdir()
            (temp_path / "node_modules" / "package.json").write_text('{"name": "test"}')

            (temp_path / "__pycache__").mkdir()
            (temp_path / "__pycache__" / "module.pyc").write_bytes(b"compiled")

            (temp_path / ".git").mkdir()
            (temp_path / ".git" / "config").write_text("[core]")

            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should find no files to process
            assert result.files_discovered == 0
            assert result.files_processed == 0

    @pytest.mark.asyncio
    async def test_permission_denied_simulation(self, test_dependencies):
        """Test handling of permission denied scenarios."""
        # Test with non-existent path (simulates permission issues)
        request = DocumentationIndexerRequest(
            target_path="/root/restricted/path/that/does/not/exist"
        )

        class MockContext:
            def __init__(self, deps):
                self.deps = deps

        from ..agent import index_documentation

        ctx = MockContext(test_dependencies)
        result = await index_documentation(ctx, request)

        # Should handle gracefully
        assert result.files_discovered == 0
        assert result.success_rate == 0.0
        assert len(result.error_summary) > 0
        assert result.processing_time_seconds >= 0

    @pytest.mark.asyncio
    async def test_deeply_nested_structure(self, test_dependencies):
        """Test processing deeply nested directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create deeply nested structure
            current_path = temp_path
            for i in range(10):  # Create 10 levels deep
                current_path = current_path / f"level_{i}"
                current_path.mkdir()

            # Add a file at the deepest level
            (current_path / "deep_file.md").write_text(
                """# Deep File
This file is nested very deeply in the directory structure.

## Content
This tests the agent's ability to handle deep nesting.
            """
            )

            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should find and process the deeply nested file
            assert result.files_discovered >= 1
            assert result.files_processed >= 1
            assert result.success_rate > 0


class TestFileContentEdgeCases:
    """Test edge cases related to file content processing."""

    @pytest.mark.asyncio
    async def test_empty_files(self, test_dependencies):
        """Test processing empty files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create empty files of different types
            (temp_path / "empty.md").touch()
            (temp_path / "empty.yaml").touch()
            (temp_path / "empty.txt").touch()

            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should discover empty files but may not process them
            assert result.files_discovered == 3
            # Processing behavior for empty files may vary
            assert result.processing_time_seconds >= 0

    @pytest.mark.asyncio
    async def test_malformed_frontmatter(self, test_dependencies):
        """Test processing files with malformed YAML frontmatter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            malformed_content = """---
title: Test Document
description: [unclosed array
invalid: yaml: content
---

# Document Content
This document has malformed frontmatter but valid content.
            """

            (temp_path / "malformed.md").write_text(malformed_content)

            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should handle malformed frontmatter gracefully
            assert result.files_discovered == 1
            # Should attempt to process despite malformed frontmatter
            assert result.processing_time_seconds > 0

    @pytest.mark.asyncio
    async def test_mixed_encoding_files(self, test_dependencies):
        """Test processing files with different encodings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # UTF-8 file
            (temp_path / "utf8.md").write_text(
                "# UTF-8 Document\nContent with émojis 🚀", encoding="utf-8"
            )

            # Latin-1 file
            (temp_path / "latin1.md").write_bytes(
                "# Latin-1 Document\nContent with açénts".encode("latin-1")
            )

            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should handle different encodings
            assert result.files_discovered == 2
            # Should process at least one file successfully
            assert result.files_processed >= 1

    @pytest.mark.asyncio
    async def test_extremely_long_lines(self, test_dependencies):
        """Test processing files with extremely long lines."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file with very long line
            long_line = "This is an extremely long line. " * 1000  # ~33,000 characters
            content = f"# Long Line Document\n\n{long_line}\n\n## End"

            (temp_path / "long_lines.md").write_text(content)

            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should handle long lines without issues
            assert result.files_discovered == 1
            assert result.processing_time_seconds >= 0

    @pytest.mark.asyncio
    async def test_binary_files_mixed_with_text(self, test_dependencies):
        """Test handling binary files mixed with text files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Text file
            (temp_path / "text.md").write_text(
                "# Text Document\nThis is a valid markdown file."
            )

            # Binary file (PNG signature)
            (temp_path / "image.png").write_bytes(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            )

            # Binary file with text extension
            (temp_path / "fake.txt").write_bytes(b"\x00\x01\x02\x03\xff\xfe")

            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should find text files and skip/handle binary appropriately
            assert (
                result.files_discovered >= 1
            )  # Should find at least the .md and .txt files
            assert result.processing_time_seconds >= 0


class TestChunkingEdgeCases:
    """Test edge cases in content chunking."""

    def test_chunk_size_validation(self):
        """Test chunk size configuration validation."""
        # Valid configuration
        deps = create_test_dependencies(
            chunk_size_target=1000, min_chunk_size=100, max_chunk_size=5000
        )
        assert deps.chunk_size_target == 1000

        # Invalid configuration should raise error
        with pytest.raises(ValueError):
            create_test_dependencies(
                chunk_size_target=50, min_chunk_size=100  # Less than min_chunk_size
            )

        with pytest.raises(ValueError):
            create_test_dependencies(
                chunk_size_target=6000,  # Greater than max_chunk_size
                max_chunk_size=5000,
            )

    @pytest.mark.asyncio
    async def test_single_very_long_document(self, test_dependencies):
        """Test chunking of single very long document."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create very long document
            sections = []
            for i in range(20):
                section = f"""
## Section {i}

This is section {i} of the document. It contains substantial content that should be processed and chunked appropriately. The content here is meaningful and should result in proper semantic boundaries for chunking.

### Subsection {i}.1

More detailed content in subsection {i}.1 with additional information and examples.

### Subsection {i}.2

Even more content in subsection {i}.2 to ensure we have enough text for proper chunking behavior.
                """
                sections.append(section)

            long_content = "# Very Long Document\n\n" + "\n".join(sections)
            (temp_path / "long_document.md").write_text(long_content)

            request = DocumentationIndexerRequest(
                target_path=temp_dir, processing_mode="comprehensive"
            )

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should create multiple chunks from long document
            assert result.files_discovered == 1
            assert result.chunks_created > 1  # Should create multiple chunks

    @pytest.mark.asyncio
    async def test_document_with_no_structure(self, test_dependencies):
        """Test chunking document with no headers or clear structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create document with no headers, just paragraphs
            paragraphs = []
            for i in range(10):
                paragraph = f"This is paragraph {i} of the document. It contains regular text without any structural markers like headers. The content flows as plain text paragraphs that need to be chunked based on paragraph boundaries rather than structural elements."
                paragraphs.append(paragraph)

            unstructured_content = "\n\n".join(paragraphs)
            (temp_path / "unstructured.txt").write_text(unstructured_content)

            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should handle unstructured content
            assert result.files_discovered == 1
            assert result.processing_time_seconds >= 0


class TestQualityValidationEdgeCases:
    """Test edge cases in quality validation."""

    @pytest.mark.asyncio
    async def test_validate_chunks_with_extreme_sizes(self, test_dependencies):
        """Test quality validation with chunks of extreme sizes."""
        from ..agent import validate_indexing_quality

        chunks = [
            # Very small chunk
            DocumentChunk(
                chunk_id="tiny",
                file_path="tiny.md",
                file_type="markdown",
                title="Tiny",
                chunk_index=0,
                content="Hi",
                size=2,
                metadata={},
                cross_references=[],
                semantic_tags=[],
            ),
            # Very large chunk
            DocumentChunk(
                chunk_id="huge",
                file_path="huge.md",
                file_type="markdown",
                title="Huge",
                chunk_index=0,
                content="X" * 10000,  # 10,000 characters
                size=10000,
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

        # Should handle extreme sizes and penalize appropriately
        assert (
            result["quality_score"] < 100
        )  # Should be penalized for poor size distribution
        assert result["size_distribution"]["small"] == 1
        assert result["size_distribution"]["oversized"] == 1

    @pytest.mark.asyncio
    async def test_validate_chunks_with_missing_metadata(self, test_dependencies):
        """Test quality validation with chunks missing various metadata."""
        from ..agent import validate_indexing_quality

        chunks = [
            # Complete chunk
            DocumentChunk(
                chunk_id="complete",
                file_path="complete.md",
                file_type="markdown",
                title="Complete",
                chunk_index=0,
                content="Complete chunk with all metadata",
                size=34,
                metadata={"complete": True},
                cross_references=["other.md"],
                semantic_tags=["complete", "metadata"],
            ),
            # Incomplete chunk
            DocumentChunk(
                chunk_id="incomplete",
                file_path="incomplete.md",
                file_type="markdown",
                title="Incomplete",
                chunk_index=0,
                content="Chunk missing metadata",
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

        # Should calculate appropriate coverage percentages
        assert (
            result["metadata_completeness"]["metadata_percentage"] == 50
        )  # 1 out of 2
        assert result["cross_reference_coverage"] == 50  # 1 out of 2
        assert result["semantic_tag_coverage"] == 50  # 1 out of 2


class TestConcurrencyAndResourceManagement:
    """Test edge cases related to resource management."""

    @pytest.mark.asyncio
    async def test_large_number_of_small_files(self, test_dependencies):
        """Test processing large number of small files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create many small files
            for i in range(100):
                content = f"# File {i}\nThis is file number {i}.\n## Content\nMinimal content here."
                (temp_path / f"file_{i:03d}.md").write_text(content)

            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should handle many files efficiently
            assert result.files_discovered == 100
            assert result.processing_time_seconds > 0
            # Performance should be reasonable
            if result.files_processed > 0:
                processing_rate = (
                    result.files_processed / result.processing_time_seconds
                )
                assert processing_rate > 1  # Should process more than 1 file per second

    @pytest.mark.asyncio
    async def test_file_size_limits(self, test_dependencies):
        """Test file size limit enforcement."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file within size limit
            normal_content = "# Normal File\n" + "Content line.\n" * 100
            (temp_path / "normal.md").write_text(normal_content)

            # Create file that exceeds size limit (1MB for test deps)
            large_content = "# Large File\n" + "X" * (2 * 1024 * 1024)  # 2MB
            (temp_path / "large.md").write_text(large_content)

            request = DocumentationIndexerRequest(target_path=temp_dir)

            class MockContext:
                def __init__(self, deps):
                    self.deps = deps

            from ..agent import index_documentation

            ctx = MockContext(test_dependencies)
            result = await index_documentation(ctx, request)

            # Should find both files but may skip large one
            assert result.files_discovered >= 1  # At least the normal file
            # Large file might be excluded due to size limit
            assert result.processing_time_seconds >= 0
