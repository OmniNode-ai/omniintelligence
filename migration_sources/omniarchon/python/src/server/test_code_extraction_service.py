#!/usr/bin/env python3
"""
Independent test of CodeExtractionService with real document data.

This test verifies that the CodeExtractionService can properly analyze
file information from actual intelligence documents, separate from the
correlation generation system.
"""

import asyncio
import os
import sys

# Add server to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.intelligence_document_reader import create_intelligence_document_reader

from services.client_manager import get_database_client
from services.crawling.code_extraction_service import CodeExtractionService


async def test_code_extraction_independently():
    """Test CodeExtractionService with real document data."""
    print("🔬 INDEPENDENT CODE EXTRACTION SERVICE TEST")
    print("=" * 60)

    # Initialize services
    database_client = get_database_client()
    code_extractor = CodeExtractionService(database_client)
    document_reader = create_intelligence_document_reader(database_client)

    # Get real documents
    print("📄 Fetching real documents...")
    documents = await document_reader.fetch_documents(limit=5)
    print(f"Found {len(documents)} documents")

    # Test with each document
    for i, doc in enumerate(documents[:3]):
        print(f"\n📄 DOCUMENT {i+1}: {doc.repository}")
        print("-" * 40)

        # Extract file information from diff_analysis
        if hasattr(doc, "diff_analysis") and doc.diff_analysis:
            modified_files = (
                doc.diff_analysis.modified_files
                if hasattr(doc.diff_analysis, "modified_files")
                else []
            )
        elif hasattr(doc, "raw_content") and doc.raw_content:
            diff_analysis = doc.raw_content.get("diff_analysis", {})
            modified_files = diff_analysis.get("modified_files", [])
        else:
            modified_files = []

        print(f"📁 Modified files: {len(modified_files)}")
        if modified_files:
            print(f"   Sample files: {modified_files[:3]}")
        else:
            print("   ❌ No modified files found")
            continue

        # Test CodeExtractionService methods
        print("\n🔍 CodeExtractionService Analysis:")

        # Test language detection
        for file_path in modified_files[:5]:
            try:
                language = code_extractor.detect_language_from_extension(file_path)
                print(f"   {file_path} → {language}")

                # Test file type validation
                is_valid = code_extractor.is_valid_source_file(file_path)
                print(f"     Valid source file: {is_valid}")

                # Test concept extraction if it's a valid file
                if is_valid:
                    concepts = code_extractor.extract_file_concepts(
                        file_path, ""
                    )  # Empty content for now
                    print(f"     Concepts: {concepts[:3] if concepts else 'None'}")

            except Exception as e:
                print(f"     Error analyzing {file_path}: {e}")

        # Test technology stack analysis
        try:
            print("\n🛠️ Technology Stack Analysis:")

            # Create a simplified file list for technology detection
            file_data = []
            for file_path in modified_files:
                file_data.append(
                    {
                        "name": file_path,
                        "path": file_path,
                        "extension": (
                            "." + file_path.split(".")[-1] if "." in file_path else ""
                        ),
                        "content": "",  # Would normally have content
                    }
                )

            # Test technology detection patterns
            technologies = set()
            extensions = set()

            for file_info in file_data:
                # Language detection
                if file_info["extension"] in [".py"]:
                    technologies.add("Python")
                elif file_info["extension"] in [".ts", ".tsx"]:
                    technologies.add("TypeScript")
                elif file_info["extension"] in [".js", ".jsx"]:
                    technologies.add("JavaScript")
                elif file_info["extension"] in [".json"]:
                    technologies.add("JSON")

                extensions.add(file_info["extension"])

                # Framework detection from file names
                if "package.json" in file_info["name"]:
                    technologies.add("Node.js")
                elif "pyproject.toml" in file_info["name"]:
                    technologies.add("Python Project")
                elif "docker" in file_info["name"].lower():
                    technologies.add("Docker")

            print(f"   Technologies detected: {list(technologies)}")
            print(f"   Extensions found: {list(extensions)}")

        except Exception as e:
            print(f"   Error in technology analysis: {e}")


async def test_specific_methods():
    """Test specific CodeExtractionService methods."""
    print("\n🧪 SPECIFIC METHOD TESTS")
    print("=" * 60)

    database_client = get_database_client()
    code_extractor = CodeExtractionService(database_client)

    # Test files from our documents
    test_files = [
        "test-fresh-intelligence.py",
        "integration_test_python-integration.py",
        "src/test1.py",
        "src/test2.py",
        "README.md",
        "package.json",
        "pyproject.toml",
    ]

    print("🔍 Language Detection Test:")
    for file_path in test_files:
        try:
            language = code_extractor.detect_language_from_extension(file_path)
            valid = code_extractor.is_valid_source_file(file_path)
            print(f"   {file_path:<35} → {language:<15} (valid: {valid})")
        except Exception as e:
            print(f"   {file_path:<35} → Error: {e}")

    print("\n📊 File Analysis Summary:")
    extensions = {}
    languages = {}

    for file_path in test_files:
        try:
            language = code_extractor.detect_language_from_extension(file_path)
            if language != "Unknown":
                languages[language] = languages.get(language, 0) + 1

            if "." in file_path:
                ext = "." + file_path.split(".")[-1]
                extensions[ext] = extensions.get(ext, 0) + 1
        except Exception as e:
            print(f"   Warning: Failed to analyze {file_path}: {type(e).__name__}: {e}")

    print(f"   Language distribution: {dict(languages)}")
    print(f"   Extension distribution: {dict(extensions)}")


if __name__ == "__main__":

    async def main():
        try:
            await test_code_extraction_independently()
            await test_specific_methods()
            print("\n✅ Independent CodeExtractionService test completed")
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    asyncio.run(main())
