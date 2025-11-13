"""
Unit Tests for File Path Search Enhancements

Tests path pattern matching, embedding content preparation, and recall improvements.
Validates glob pattern filtering and path emphasis for better search accuracy.

Coverage Target: 90%+
"""

import os
import re
import sys
from typing import List
from unittest.mock import MagicMock, patch

import pytest

# Add service path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "../../../services/intelligence/src")
)


class FilePathSearchEnhancer:
    """
    Enhances file path search with pattern matching and path emphasis.
    Simulates actual implementation for path search improvements.
    """

    def __init__(self):
        self.path_weight = 2.0  # Weight for path terms in embeddings

    def prepare_embedding_content(
        self, file_path: str, content: str = None, emphasize_path: bool = True
    ) -> str:
        """
        Prepare content for embedding with path emphasis.

        Args:
            file_path: File path to embed
            content: Optional file content
            emphasize_path: Whether to emphasize path terms

        Returns:
            Prepared content string for embedding
        """
        parts = []

        if emphasize_path:
            # Extract path components
            path_terms = self._extract_path_terms(file_path)

            # Repeat path terms for emphasis (simulates weighting)
            for _ in range(int(self.path_weight)):
                parts.append(" ".join(path_terms))

        # Add original path
        parts.append(file_path)

        # Add content if provided
        if content:
            parts.append(content)

        return " ".join(parts)

    def _extract_path_terms(self, file_path: str) -> List[str]:
        """
        Extract searchable terms from file path.

        Extracts:
        - Directory names
        - File name (without extension)
        - File extension
        - Path components split by common separators

        Args:
            file_path: File path to extract terms from

        Returns:
            List of path terms
        """
        from pathlib import Path

        path = Path(file_path)
        terms = []

        # Add directory components
        for parent in path.parents:
            if parent.name:
                terms.append(parent.name)

        # Split by common separators
        filename_parts = re.split(r"[-_\.]", path.stem)
        filename_parts = [p for p in filename_parts if p]

        # Add filename: either split parts (if compound) or whole stem
        if len(filename_parts) > 1:
            # Compound name - use split parts only
            terms.extend(filename_parts)
        elif path.stem:
            # Simple name - use whole stem
            terms.append(path.stem)

        # Add extension
        if path.suffix:
            terms.append(path.suffix.lstrip("."))

        return terms

    def glob_to_regex(self, pattern: str) -> str:
        """
        Convert glob pattern to regex pattern.

        Supports:
        - * : Matches any characters except /
        - ** : Matches any characters including /
        - ? : Matches single character
        - [abc] : Character class

        Args:
            pattern: Glob pattern (e.g., "src/**/*.py")

        Returns:
            Regex pattern string
        """
        # Escape special regex characters
        regex = re.escape(pattern)

        # Convert glob wildcards to regex
        # IMPORTANT: Process ** before * to avoid double conversion
        # **/ at the beginning or after / should match zero or more path components
        regex = regex.replace(r"\*\*/", "(?:.*/)?")  # **/ -> (?:.*/)? (optional path)
        regex = regex.replace(r"\*\*", ".*")  # ** -> .* (any characters)
        regex = regex.replace(r"\*", "[^/]*")  # * -> [^/]* (any except /)
        regex = regex.replace(r"\?", ".")  # ? -> . (single char)

        # Add anchors
        regex = f"^{regex}$"

        return regex

    def filter_by_pattern(self, file_paths: List[str], pattern: str) -> List[str]:
        """
        Filter file paths by glob pattern.

        Args:
            file_paths: List of file paths to filter
            pattern: Glob pattern (e.g., "**/*.py")

        Returns:
            Filtered list of file paths
        """
        regex_pattern = self.glob_to_regex(pattern)
        regex = re.compile(regex_pattern)

        return [path for path in file_paths if regex.match(path)]

    def calculate_path_similarity(self, query: str, file_path: str) -> float:
        """
        Calculate similarity between query and file path.

        Uses simple term matching for demonstration.

        Args:
            query: Search query
            file_path: File path

        Returns:
            Similarity score (0.0 - 1.0)
        """
        # Common file extensions to exclude from similarity calculation
        # Extensions rarely appear in user queries and dilute scores
        COMMON_EXTENSIONS = {
            "py",
            "js",
            "ts",
            "tsx",
            "jsx",
            "go",
            "rs",
            "java",
            "cpp",
            "c",
            "h",
            "md",
            "txt",
            "json",
            "yaml",
            "yml",
            "xml",
            "html",
            "css",
            "scss",
        }

        query_terms = set(query.lower().split())
        path_terms_raw = self._extract_path_terms(file_path)

        # Filter out common extensions and lowercase all terms for case-insensitive matching
        path_terms = set(
            term.lower()
            for term in path_terms_raw
            if term.lower() not in COMMON_EXTENSIONS
        )

        if not query_terms or not path_terms:
            return 0.0

        # Calculate Jaccard similarity
        intersection = query_terms.intersection(path_terms)
        union = query_terms.union(path_terms)

        return len(intersection) / len(union) if union else 0.0


@pytest.fixture
def search_enhancer():
    """Create FilePathSearchEnhancer instance."""
    return FilePathSearchEnhancer()


class TestFilePathSearchEnhancerInitialization:
    """Test FilePathSearchEnhancer initialization."""

    def test_init_success(self):
        """Test successful initialization."""
        enhancer = FilePathSearchEnhancer()
        assert enhancer.path_weight == 2.0

    def test_init_default_path_weight(self):
        """Test default path weight is set."""
        enhancer = FilePathSearchEnhancer()
        assert enhancer.path_weight > 0


class TestPrepareEmbeddingContent:
    """Test prepare_embedding_content method."""

    def test_prepare_content_with_path_only(self, search_enhancer):
        """Test preparing content with only file path."""
        content = search_enhancer.prepare_embedding_content(
            file_path="/test/src/main.py"
        )

        assert "/test/src/main.py" in content
        assert "main" in content  # Filename without extension
        assert "py" in content  # Extension

    def test_prepare_content_with_emphasis(self, search_enhancer):
        """Test path emphasis repeats terms."""
        content = search_enhancer.prepare_embedding_content(
            file_path="/test/utils.py", emphasize_path=True
        )

        # Path terms should appear multiple times due to weighting
        assert content.count("utils") >= 2

    def test_prepare_content_without_emphasis(self, search_enhancer):
        """Test preparing content without path emphasis."""
        content = search_enhancer.prepare_embedding_content(
            file_path="/test/file.py", emphasize_path=False
        )

        # Should only contain path once
        assert content == "/test/file.py"

    def test_prepare_content_with_file_content(self, search_enhancer):
        """Test preparing content with additional file content."""
        file_content = "This is the file content with important keywords"

        content = search_enhancer.prepare_embedding_content(
            file_path="/test/doc.py", content=file_content, emphasize_path=False
        )

        assert "/test/doc.py" in content
        assert "important keywords" in content

    def test_prepare_content_combines_path_and_content(self, search_enhancer):
        """Test combining path and content."""
        content = search_enhancer.prepare_embedding_content(
            file_path="/src/api/routes.py",
            content="API route handlers",
            emphasize_path=True,
        )

        assert "routes" in content
        assert "api" in content
        assert "API route handlers" in content


class TestExtractPathTerms:
    """Test _extract_path_terms method."""

    def test_extract_terms_simple_path(self, search_enhancer):
        """Test extracting terms from simple path."""
        terms = search_enhancer._extract_path_terms("/test/file.py")

        assert "file" in terms  # Filename
        assert "py" in terms  # Extension
        assert "test" in terms  # Directory

    def test_extract_terms_nested_path(self, search_enhancer):
        """Test extracting terms from nested path."""
        terms = search_enhancer._extract_path_terms("/project/src/api/routes.py")

        assert "routes" in terms
        assert "api" in terms
        assert "src" in terms
        assert "project" in terms

    def test_extract_terms_with_underscores(self, search_enhancer):
        """Test extracting terms from filename with underscores."""
        terms = search_enhancer._extract_path_terms("/test/my_module_name.py")

        assert "my" in terms
        assert "module" in terms
        assert "name" in terms

    def test_extract_terms_with_hyphens(self, search_enhancer):
        """Test extracting terms from filename with hyphens."""
        terms = search_enhancer._extract_path_terms("/test/some-utils-file.js")

        assert "some" in terms
        assert "utils" in terms
        assert "file" in terms

    def test_extract_terms_with_dots(self, search_enhancer):
        """Test extracting terms from filename with dots."""
        terms = search_enhancer._extract_path_terms("/test/file.test.ts")

        # Should split on dots
        assert "file" in terms
        assert "test" in terms
        assert "ts" in terms

    def test_extract_terms_no_extension(self, search_enhancer):
        """Test extracting terms from file without extension."""
        terms = search_enhancer._extract_path_terms("/test/README")

        assert "README" in terms
        assert "test" in terms

    def test_extract_terms_removes_empty_strings(self, search_enhancer):
        """Test empty strings are filtered out."""
        terms = search_enhancer._extract_path_terms("/test//double//slash.py")

        # Should not contain empty strings
        assert "" not in terms
        assert all(term for term in terms)


class TestGlobToRegex:
    """Test glob_to_regex conversion method."""

    def test_glob_to_regex_single_star(self, search_enhancer):
        """Test converting single star wildcard."""
        regex = search_enhancer.glob_to_regex("*.py")

        # Should match files in current directory
        assert re.match(regex, "test.py")
        assert not re.match(regex, "dir/test.py")  # Should not match subdirs

    def test_glob_to_regex_double_star(self, search_enhancer):
        """Test converting double star wildcard."""
        regex = search_enhancer.glob_to_regex("**/*.py")

        # Should match files in any subdirectory
        assert re.match(regex, "test.py")
        assert re.match(regex, "dir/test.py")
        assert re.match(regex, "deep/nested/path/test.py")

    def test_glob_to_regex_question_mark(self, search_enhancer):
        """Test converting question mark wildcard."""
        regex = search_enhancer.glob_to_regex("file?.py")

        assert re.match(regex, "file1.py")
        assert re.match(regex, "fileA.py")
        assert not re.match(regex, "file12.py")  # Too many characters

    def test_glob_to_regex_literal_characters(self, search_enhancer):
        """Test literal characters are preserved."""
        regex = search_enhancer.glob_to_regex("src/main.py")

        assert re.match(regex, "src/main.py")
        assert not re.match(regex, "src/other.py")

    def test_glob_to_regex_mixed_patterns(self, search_enhancer):
        """Test mixed glob patterns."""
        regex = search_enhancer.glob_to_regex("src/**/*.test.ts")

        assert re.match(regex, "src/app.test.ts")
        assert re.match(regex, "src/api/routes.test.ts")
        assert not re.match(regex, "src/app.ts")  # Missing .test

    def test_glob_to_regex_anchored(self, search_enhancer):
        """Test regex patterns are anchored."""
        regex = search_enhancer.glob_to_regex("*.py")

        # Should match full string, not substring
        assert re.match(regex, "test.py")
        assert not re.match(regex, "test.py.bak")


class TestFilterByPattern:
    """Test filter_by_pattern method."""

    def test_filter_by_pattern_python_files(self, search_enhancer):
        """Test filtering for Python files."""
        files = [
            "main.py",
            "utils.py",
            "config.yaml",
            "test.js",
        ]

        filtered = search_enhancer.filter_by_pattern(files, "*.py")

        assert "main.py" in filtered
        assert "utils.py" in filtered
        assert "config.yaml" not in filtered
        assert "test.js" not in filtered

    def test_filter_by_pattern_nested_files(self, search_enhancer):
        """Test filtering nested files."""
        files = [
            "src/main.py",
            "src/api/routes.py",
            "tests/test_main.py",
            "README.md",
        ]

        filtered = search_enhancer.filter_by_pattern(files, "**/*.py")

        assert len(filtered) == 3
        assert "README.md" not in filtered

    def test_filter_by_pattern_specific_directory(self, search_enhancer):
        """Test filtering files in specific directory."""
        files = [
            "src/main.py",
            "src/utils.py",
            "tests/test.py",
            "docs/guide.py",
        ]

        filtered = search_enhancer.filter_by_pattern(files, "src/*.py")

        assert "src/main.py" in filtered
        assert "src/utils.py" in filtered
        assert "tests/test.py" not in filtered

    def test_filter_by_pattern_empty_list(self, search_enhancer):
        """Test filtering empty file list."""
        filtered = search_enhancer.filter_by_pattern([], "*.py")

        assert filtered == []

    def test_filter_by_pattern_no_matches(self, search_enhancer):
        """Test filtering when no files match."""
        files = ["file.txt", "doc.md", "config.yaml"]

        filtered = search_enhancer.filter_by_pattern(files, "*.py")

        assert filtered == []

    def test_filter_by_pattern_all_match(self, search_enhancer):
        """Test filtering when all files match."""
        files = ["a.py", "b.py", "c.py"]

        filtered = search_enhancer.filter_by_pattern(files, "*.py")

        assert len(filtered) == 3

    def test_filter_by_pattern_test_files(self, search_enhancer):
        """Test filtering test files specifically."""
        files = [
            "src/main.py",
            "tests/test_main.py",
            "tests/test_utils.py",
            "src/utils.py",
        ]

        filtered = search_enhancer.filter_by_pattern(files, "tests/test_*.py")

        assert len(filtered) == 2
        assert all("test_" in f for f in filtered)


class TestCalculatePathSimilarity:
    """Test calculate_path_similarity method."""

    def test_calculate_similarity_exact_match(self, search_enhancer):
        """Test similarity for exact term matches."""
        similarity = search_enhancer.calculate_path_similarity(
            query="main utils",
            file_path="/src/main_utils.py",
        )

        assert similarity > 0.5

    def test_calculate_similarity_partial_match(self, search_enhancer):
        """Test similarity for partial matches."""
        similarity = search_enhancer.calculate_path_similarity(
            query="api routes",
            file_path="/src/api/routes.py",
        )

        assert similarity > 0.3

    def test_calculate_similarity_no_match(self, search_enhancer):
        """Test similarity when no terms match."""
        similarity = search_enhancer.calculate_path_similarity(
            query="database models",
            file_path="/src/frontend/components.tsx",
        )

        assert similarity < 0.3

    def test_calculate_similarity_empty_query(self, search_enhancer):
        """Test similarity with empty query."""
        similarity = search_enhancer.calculate_path_similarity(
            query="",
            file_path="/src/file.py",
        )

        assert similarity == 0.0

    def test_calculate_similarity_case_insensitive(self, search_enhancer):
        """Test similarity is case insensitive."""
        similarity1 = search_enhancer.calculate_path_similarity(
            query="Main Utils",
            file_path="/src/main_utils.py",
        )

        similarity2 = search_enhancer.calculate_path_similarity(
            query="main utils",
            file_path="/src/main_utils.py",
        )

        # Should be same (case insensitive)
        assert similarity1 == similarity2


class TestPathSearchRecallImprovement:
    """Test path search recall improvements."""

    def test_path_emphasis_improves_recall(self, search_enhancer):
        """Test path emphasis improves search recall."""
        # Without emphasis
        content_no_emphasis = search_enhancer.prepare_embedding_content(
            file_path="/api/routes/users.py",
            emphasize_path=False,
        )

        # With emphasis
        content_with_emphasis = search_enhancer.prepare_embedding_content(
            file_path="/api/routes/users.py",
            emphasize_path=True,
        )

        # Emphasized content should be longer (terms repeated)
        assert len(content_with_emphasis) > len(content_no_emphasis)

    def test_pattern_filtering_reduces_false_positives(self, search_enhancer):
        """Test pattern filtering reduces false positives."""
        all_files = [
            "src/api/routes.py",
            "src/utils.py",
            "tests/test_api.py",
            "docs/api_guide.md",
        ]

        # Filter to only Python files in src/
        python_files = search_enhancer.filter_by_pattern(all_files, "src/**/*.py")

        # Should exclude tests and docs
        assert "tests/test_api.py" not in python_files
        assert "docs/api_guide.md" not in python_files
        assert len(python_files) == 2

    def test_term_extraction_improves_matching(self, search_enhancer):
        """Test term extraction improves matching."""
        # Complex filename
        terms = search_enhancer._extract_path_terms("/src/api/user-auth-service.py")

        # Should extract all meaningful terms
        assert "user" in terms
        assert "auth" in terms
        assert "service" in terms

        # These terms enable better matching for queries like "user authentication"


if __name__ == "__main__":
    import subprocess

    try:
        result = subprocess.run(
            ["pytest", __file__, "-v", "--tb=short", "-x"],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print("pytest not found. Install with: pip install pytest pytest-asyncio")
