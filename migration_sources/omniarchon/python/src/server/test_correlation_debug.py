#!/usr/bin/env python3
"""
Debug Test for Correlation Generation Logic

This test fetches actual documents from the API and runs the correlation
generation logic directly to identify why correlations aren't being generated
between Archon and omnimcp documents with Python files.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

import httpx

# Add the server to the path so we can import from services
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from services.correlation_generator import AutomatedCorrelationGenerator

# Set up logging to see detailed debug information
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockDiffAnalysis:
    """Mock DiffAnalysis for testing."""

    def __init__(self, modified_files: list[str]):
        self.modified_files = modified_files


class MockDocument:
    """Mock document for testing correlation logic."""

    def __init__(self, doc_data: dict[str, Any]):
        self.id = doc_data.get("id", "unknown")
        self.repository = doc_data.get("repository", "unknown")
        self.commit_sha = doc_data.get("commit_sha", "unknown")
        self.created_at = doc_data.get("created_at", datetime.now(UTC).isoformat())
        self.change_type = doc_data.get("change_type", "unknown")
        self.raw_content = doc_data.get("raw_content", {})

        # Create DiffAnalysis if modified_files are present
        modified_files = doc_data.get("modified_files", [])
        if modified_files:
            self.diff_analysis = MockDiffAnalysis(modified_files)
        else:
            self.diff_analysis = None


async def fetch_documents_from_api() -> list[dict[str, Any]]:
    """Fetch actual documents from the intelligence API."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8053/documents", timeout=30.0)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"❌ Failed to fetch documents from API: {e}")
        return []


def extract_file_paths_from_doc(doc_data: dict[str, Any]) -> list[str]:
    """Extract file paths from document data."""
    # Try different locations where file paths might be stored
    file_paths = []

    # Check for modified_files in raw_content
    raw_content = doc_data.get("raw_content", {})
    if raw_content:
        # Check diff_analysis structure
        if "diff_analysis" in raw_content:
            diff_analysis = raw_content["diff_analysis"]
            if isinstance(diff_analysis, dict) and "modified_files" in diff_analysis:
                file_paths.extend(diff_analysis["modified_files"])

        # Check for direct modified_files
        if "modified_files" in raw_content:
            if isinstance(raw_content["modified_files"], list):
                file_paths.extend(raw_content["modified_files"])

    # Check top-level modified_files
    if "modified_files" in doc_data:
        if isinstance(doc_data["modified_files"], list):
            file_paths.extend(doc_data["modified_files"])

    return file_paths


def debug_file_information_generation(
    doc1: MockDocument, doc2: MockDocument, generator: AutomatedCorrelationGenerator
) -> dict[str, Any]:
    """Debug the file information generation process step by step."""
    print("\n🔍 DEBUGGING FILE INFORMATION GENERATION")
    print("=" * 60)

    # Step 1: Check diff_analysis objects
    print(f"📁 Document 1 ({doc1.repository}):")
    print(f"   - diff_analysis: {doc1.diff_analysis is not None}")
    if doc1.diff_analysis:
        print(f"   - modified_files: {doc1.diff_analysis.modified_files}")

    print(f"📁 Document 2 ({doc2.repository}):")
    print(f"   - diff_analysis: {doc2.diff_analysis is not None}")
    if doc2.diff_analysis:
        print(f"   - modified_files: {doc2.diff_analysis.modified_files}")

    # Step 2: Get file sets
    files1 = set(doc1.diff_analysis.modified_files if doc1.diff_analysis else [])
    files2 = set(doc2.diff_analysis.modified_files if doc2.diff_analysis else [])

    print("\n📊 FILE ANALYSIS:")
    print(f"   - Files in {doc1.repository}: {list(files1)}")
    print(f"   - Files in {doc2.repository}: {list(files2)}")
    print(f"   - Files1 count: {len(files1)}")
    print(f"   - Files2 count: {len(files2)}")

    # Step 3: Combine all files
    all_files = files1.union(files2)
    print(f"   - All combined files: {list(all_files)}")
    print(f"   - All files count: {len(all_files)}")

    # Step 4: Extract extensions and directories
    all_exts = set()
    all_dirs = set()

    for file_path in all_files:
        print(f"   - Processing file: {file_path}")

        # Extract file extensions
        if "." in file_path:
            ext = file_path.split(".")[-1].lower()
            all_exts.add(ext)
            print(f"     -> Extension: {ext}")

        # Extract directories
        if "/" in file_path:
            dirs = file_path.split("/")[:-1]  # Exclude filename
            all_dirs.update(dirs)
            print(f"     -> Directories: {dirs}")

    print("\n🏷️ EXTRACTED METADATA:")
    print(f"   - All extensions: {list(all_exts)}")
    print(f"   - All directories: {list(all_dirs)}")

    # Step 5: Technology stack mapping
    tech_stack = set()
    ext_tech_map = {
        "py": "Python",
        "ts": "TypeScript",
        "tsx": "React/TypeScript",
        "js": "JavaScript",
        "jsx": "React/JavaScript",
        "rs": "Rust",
        "toml": "Configuration",
        "json": "Configuration",
        "yaml": "Configuration",
        "yml": "Configuration",
        "md": "Documentation",
    }

    print("\n🛠️ TECHNOLOGY MAPPING:")
    for ext in all_exts:
        if ext in ext_tech_map:
            tech = ext_tech_map[ext]
            tech_stack.add(tech)
            print(f"   - Extension '{ext}' -> Technology '{tech}'")
        else:
            print(f"   - Extension '{ext}' -> NO MAPPING")

    print(f"   - Final technology stack: {list(tech_stack)}")

    # Step 6: Build file_info
    file_info = {
        "common_files": [],
        "common_extensions": [],
        "common_directories": [],
        "file_overlap_ratio": 0.0,
        "technology_stack": [],
    }

    if all_files:
        file_info["technology_stack"] = (
            list(tech_stack)[:4] if tech_stack else ["Mixed"]
        )
        file_info["common_extensions"] = list(all_exts)[:5] if all_exts else ["various"]
        file_info["common_directories"] = list(all_dirs)[:3] if all_dirs else ["src"]

        print("\n📋 INITIAL FILE_INFO:")
        print(f"   - technology_stack: {file_info['technology_stack']}")
        print(f"   - common_extensions: {file_info['common_extensions']}")
        print(f"   - common_directories: {file_info['common_directories']}")

    # Step 7: Calculate overlap (this should only happen if both have files)
    if files1 and files2:
        print("\n🔗 OVERLAP CALCULATION:")
        print(f"   - Doc1 has files: {bool(files1)} ({len(files1)} files)")
        print(f"   - Doc2 has files: {bool(files2)} ({len(files2)} files)")

        # Common files (exact matches)
        common_files = files1.intersection(files2)
        file_info["common_files"] = list(common_files)[:5]

        # File overlap ratio
        total_files = files1.union(files2)
        file_info["file_overlap_ratio"] = (
            len(common_files) / len(total_files) if total_files else 0.0
        )

        print(f"   - Common files: {list(common_files)}")
        print(f"   - Total unique files: {len(total_files)}")
        print(f"   - Overlap ratio: {file_info['file_overlap_ratio']}")

        # Update with truly common extensions
        exts1 = {f.split(".")[-1].lower() for f in files1 if "." in f}
        exts2 = {f.split(".")[-1].lower() for f in files2 if "." in f}
        common_exts = exts1.intersection(exts2)
        file_info["common_extensions"] = list(common_exts)

        print(f"   - Doc1 extensions: {list(exts1)}")
        print(f"   - Doc2 extensions: {list(exts2)}")
        print(f"   - Common extensions: {list(common_exts)}")
    else:
        print("\n⚠️ OVERLAP SKIPPED:")
        print("   - One or both documents have no files")
        print(f"   - files1 empty: {not files1}")
        print(f"   - files2 empty: {not files2}")

    # Step 8: Final fallback check
    if not any(
        [
            file_info["common_files"],
            file_info["common_extensions"],
            file_info["common_directories"],
            file_info["technology_stack"],
        ]
    ):
        print("\n❌ FALLBACK TRIGGERED:")
        print("   - No meaningful file information found")
        print(
            "   - Setting defaults: technology_stack=['Unknown'], common_extensions=['mixed']"
        )
        file_info["technology_stack"] = ["Unknown"]
        file_info["common_extensions"] = ["mixed"]

    print("\n✅ FINAL FILE_INFO:")
    print(f"   {json.dumps(file_info, indent=2)}")

    return file_info


async def test_correlation_generation_with_real_data():
    """Test correlation generation using real documents from the API."""
    print("🚀 CORRELATION GENERATION DEBUG TEST")
    print("=" * 60)

    # Fetch real documents from API
    print("📡 Fetching documents from Intelligence API...")
    documents = await fetch_documents_from_api()

    if not documents:
        print("❌ No documents found from API")
        return

    print(f"✅ Found {len(documents)} documents")

    # Find Archon and omnimcp documents
    archon_docs = []
    omnimcp_docs = []

    for doc in documents:
        repo = doc.get("repository", "").lower()
        file_paths = extract_file_paths_from_doc(doc)

        # Check if document has Python files
        has_python = any(path.endswith(".py") for path in file_paths)

        if "archon" in repo and has_python:
            archon_docs.append((doc, file_paths))
        elif "omnimcp" in repo and has_python:
            omnimcp_docs.append((doc, file_paths))

    print("\n📊 PYTHON DOCUMENT ANALYSIS:")
    print(f"   - Archon docs with Python files: {len(archon_docs)}")
    print(f"   - omnimcp docs with Python files: {len(omnimcp_docs)}")

    if not archon_docs or not omnimcp_docs:
        print("❌ Need at least one Archon and one omnimcp document with Python files")
        return

    # Take the first document from each
    archon_doc_data, archon_files = archon_docs[0]
    omnimcp_doc_data, omnimcp_files = omnimcp_docs[0]

    print("\n🎯 SELECTED TEST DOCUMENTS:")
    print(
        f"   - Archon: {archon_doc_data.get('repository')} with files: {archon_files[:3]}..."
    )
    print(
        f"   - omnimcp: {omnimcp_doc_data.get('repository')} with files: {omnimcp_files[:3]}..."
    )

    # Create mock documents with file information
    archon_doc_data["modified_files"] = archon_files
    omnimcp_doc_data["modified_files"] = omnimcp_files

    archon_doc = MockDocument(archon_doc_data)
    omnimcp_doc = MockDocument(omnimcp_doc_data)

    # Create correlation generator
    generator = AutomatedCorrelationGenerator()

    # Test the specific file information extraction method
    print("\n🔍 TESTING get_file_information_for_correlation()...")
    debug_file_information_generation(archon_doc, omnimcp_doc, generator)

    # Test semantic correlation analysis
    print("\n🧠 TESTING analyze_semantic_correlation()...")
    semantic_correlation = generator.analyze_semantic_correlation(
        archon_doc, omnimcp_doc
    )

    print("📊 SEMANTIC CORRELATION RESULT:")
    if semantic_correlation:
        print("   ✅ Semantic correlation found!")
        print(f"   - Repository: {semantic_correlation.repository}")
        print(f"   - Similarity: {semantic_correlation.semantic_similarity}")
        print(f"   - Common keywords: {semantic_correlation.common_keywords}")
        print(f"   - File information: {semantic_correlation.file_information}")
    else:
        print("   ❌ No semantic correlation found")

        # Let's debug why
        content_similarity = generator.analyze_content_similarity(
            archon_doc, omnimcp_doc
        )
        quality_correlation = generator.analyze_quality_pattern_correlation(
            archon_doc, omnimcp_doc
        )

        semantic_similarity = (content_similarity * 0.7) + (quality_correlation * 0.3)
        threshold = generator.semantic_threshold * 0.7

        print("   🔍 Debug information:")
        print(f"     - Content similarity: {content_similarity}")
        print(f"     - Quality correlation: {quality_correlation}")
        print(f"     - Combined semantic similarity: {semantic_similarity}")
        print(f"     - Threshold (adjusted): {threshold}")
        print(f"     - Would pass threshold: {semantic_similarity >= threshold}")

    # Test temporal correlation analysis
    print("\n⏰ TESTING analyze_temporal_correlation()...")
    try:
        archon_time = datetime.fromisoformat(
            archon_doc.created_at.replace("Z", "+00:00")
        )
        omnimcp_time = datetime.fromisoformat(
            omnimcp_doc.created_at.replace("Z", "+00:00")
        )

        temporal_correlation = generator.analyze_temporal_correlation(
            archon_doc, archon_time, omnimcp_doc, omnimcp_time
        )

        print("📊 TEMPORAL CORRELATION RESULT:")
        if temporal_correlation:
            print("   ✅ Temporal correlation found!")
            print(f"   - Repository: {temporal_correlation.repository}")
            print(f"   - Time diff: {temporal_correlation.time_diff_hours} hours")
            print(f"   - Strength: {temporal_correlation.correlation_strength}")
        else:
            time_diff = abs((archon_time - omnimcp_time).total_seconds() / 3600)
            print("   ❌ No temporal correlation found")
            print(f"   - Time difference: {time_diff} hours")
            print(f"   - Max window: {max(generator.temporal_windows)} hours")
            print(f"   - Within window: {time_diff <= max(generator.temporal_windows)}")
    except Exception as e:
        print(f"   ❌ Error in temporal analysis: {e}")


if __name__ == "__main__":
    asyncio.run(test_correlation_generation_with_real_data())
