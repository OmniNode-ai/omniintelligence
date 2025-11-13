#!/usr/bin/env python3
"""
Quick verification script for language mapping functionality.
Tests the _map_extension_to_language function and _enhance_document_metadata.
"""

from datetime import datetime, timezone


def _map_extension_to_language(file_extension: str) -> str:
    """
    Map file extension to language identifier.
    (Copied from app.py for testing)
    """
    extension_map = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "jsx": "javascript",
        "go": "go",
        "java": "java",
        "rs": "rust",
        "cpp": "cpp",
        "cc": "cpp",
        "cxx": "cpp",
        "c": "c",
        "h": "c",
        "hpp": "cpp",
        "rb": "ruby",
        "php": "php",
        "swift": "swift",
        "kt": "kotlin",
        "scala": "scala",
        "cs": "csharp",
        "vb": "vb",
        "sql": "sql",
        "sh": "shell",
        "bash": "shell",
        "zsh": "shell",
        "yaml": "yaml",
        "yml": "yaml",
        "json": "json",
        "xml": "xml",
        "html": "html",
        "css": "css",
        "scss": "scss",
        "sass": "sass",
        "md": "markdown",
        "rst": "restructuredtext",
        "txt": "text",
    }
    clean_ext = file_extension.lstrip(".").lower()
    return extension_map.get(clean_ext, clean_ext)


def _enhance_document_metadata(
    base_metadata: dict,
    document_id: str,
    title: str,
    source: str,
    project_id=None,
    document_type=None,
    source_domain=None,
    quality_scoring_enabled=None,
    timestamp_field: str = "created_at",
) -> dict:
    """
    Enhance document metadata with common fields.
    (Copied from app.py for testing)
    """
    enhanced = {
        **base_metadata,
        "document_id": document_id,
        "title": title,
        "source": source,
        timestamp_field: datetime.now(timezone.utc).isoformat(),
    }

    # Add optional fields only if provided
    if project_id is not None:
        enhanced["project_id"] = project_id
    if document_type is not None:
        enhanced["document_type"] = document_type
    if source_domain is not None:
        enhanced["source_domain"] = source_domain
    if quality_scoring_enabled is not None:
        enhanced["quality_scoring_enabled"] = quality_scoring_enabled

    # Add language field based on file_extension if present and language not already set
    if "file_extension" in enhanced and "language" not in enhanced:
        enhanced["language"] = _map_extension_to_language(enhanced["file_extension"])

    return enhanced


def test_language_mapping():
    """Test the language mapping function"""
    print("Testing _map_extension_to_language...")
    test_cases = [
        (".py", "python"),
        ("py", "python"),
        (".js", "javascript"),
        ("ts", "typescript"),
        (".go", "go"),
        (".rs", "rust"),
        (".java", "java"),
        (".md", "markdown"),
        (".unknown", "unknown"),
    ]

    all_passed = True
    for extension, expected in test_cases:
        result = _map_extension_to_language(extension)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {extension:15} -> {result:15} (expected: {expected})")
        if result != expected:
            all_passed = False

    return all_passed


def test_metadata_enhancement():
    """Test the metadata enhancement with language field"""
    print("\nTesting _enhance_document_metadata with language field...")

    test_cases = [
        {
            "name": "Python file",
            "base_metadata": {"file_extension": ".py", "custom": "field"},
            "expected_language": "python",
        },
        {
            "name": "JavaScript file",
            "base_metadata": {"file_extension": ".js"},
            "expected_language": "javascript",
        },
        {
            "name": "No file_extension",
            "base_metadata": {"custom": "field"},
            "expected_language": None,
        },
        {
            "name": "Language already set",
            "base_metadata": {"file_extension": ".py", "language": "custom-python"},
            "expected_language": "custom-python",
        },
    ]

    all_passed = True
    for test_case in test_cases:
        enhanced = _enhance_document_metadata(
            base_metadata=test_case["base_metadata"],
            document_id="doc_123",
            title="Test Document",
            source="test",
        )

        actual_language = enhanced.get("language")
        expected_language = test_case["expected_language"]

        if expected_language is None:
            passed = "language" not in enhanced
        else:
            passed = actual_language == expected_language

        status = "✅" if passed else "❌"
        print(
            f"  {status} {test_case['name']:30} -> language={actual_language} (expected: {expected_language})"
        )

        if not passed:
            all_passed = False

    return all_passed


def main():
    """Run all tests"""
    print("=" * 70)
    print("Language Mapping Verification")
    print("=" * 70)

    test1_passed = test_language_mapping()
    test2_passed = test_metadata_enhancement()

    print("\n" + "=" * 70)
    if test1_passed and test2_passed:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())
