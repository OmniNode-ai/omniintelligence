#!/usr/bin/env python3
"""
Standalone Test for File Information Extraction Logic

This test recreates the get_file_information_for_correlation() logic
without dependencies on the full service infrastructure.
"""

import json
import logging
from typing import Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockDiffAnalysis:
    """Mock DiffAnalysis for testing."""

    def __init__(self, modified_files: list[str]):
        self.modified_files = modified_files


class MockDocument:
    """Mock document for testing correlation logic."""

    def __init__(self, repository: str, modified_files: list[str]):
        self.repository = repository
        self.diff_analysis = (
            MockDiffAnalysis(modified_files) if modified_files else None
        )


def get_file_information_for_correlation(
    doc1: MockDocument, doc2: MockDocument
) -> dict[str, Any]:
    """
    Recreated from correlation_generator.py line 589-686
    Extract specific file information for correlation display.
    """
    file_info = {
        "common_files": [],
        "common_extensions": [],
        "common_directories": [],
        "file_overlap_ratio": 0.0,
        "technology_stack": [],
    }

    # Get file sets from both documents
    files1 = set(doc1.diff_analysis.modified_files if doc1.diff_analysis else [])
    files2 = set(doc2.diff_analysis.modified_files if doc2.diff_analysis else [])

    # Debug logging
    logger.info(f"🗂️ Files in {doc1.repository}: {list(files1)}")
    logger.info(f"🗂️ Files in {doc2.repository}: {list(files2)}")

    # Collect all file extensions and directories from both documents
    all_files = files1.union(files2)

    if all_files:
        # Extract extensions from all files
        all_exts = set()
        all_dirs = set()

        for file_path in all_files:
            # Extract file extensions
            if "." in file_path:
                ext = file_path.split(".")[-1].lower()
                all_exts.add(ext)

            # Extract directories
            if "/" in file_path:
                dirs = file_path.split("/")[:-1]  # Exclude filename
                all_dirs.update(dirs)

        # Technology stack inference from all extensions
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

        for ext in all_exts:
            if ext in ext_tech_map:
                tech_stack.add(ext_tech_map[ext])

        file_info["technology_stack"] = (
            list(tech_stack)[:4] if tech_stack else ["Mixed"]
        )
        file_info["common_extensions"] = list(all_exts)[:5] if all_exts else ["various"]
        file_info["common_directories"] = list(all_dirs)[:3] if all_dirs else ["src"]

    # Calculate overlap only if both documents have files
    if files1 and files2:
        # Common files (exact matches)
        common_files = files1.intersection(files2)
        file_info["common_files"] = list(common_files)[:5]  # Limit to 5

        # File overlap ratio
        total_files = files1.union(files2)
        file_info["file_overlap_ratio"] = (
            len(common_files) / len(total_files) if total_files else 0.0
        )

        # Update with truly common extensions and directories
        exts1 = {f.split(".")[-1].lower() for f in files1 if "." in f}
        exts2 = {f.split(".")[-1].lower() for f in files2 if "." in f}
        common_exts = exts1.intersection(exts2)
        file_info["common_extensions"] = list(common_exts)

        dirs1 = set()
        dirs2 = set()

        for f in files1:
            if "/" in f:
                dirs1.update(f.split("/")[:-1])

        for f in files2:
            if "/" in f:
                dirs2.update(f.split("/")[:-1])

        common_dirs = dirs1.intersection(dirs2)
        file_info["common_directories"] = list(common_dirs)[:3]  # Limit to 3

    # Ensure file_information is never completely empty (prevents JSON filtering)
    if not any(
        [
            file_info["common_files"],
            file_info["common_extensions"],
            file_info["common_directories"],
            file_info["technology_stack"],
        ]
    ):
        file_info["technology_stack"] = ["Unknown"]
        file_info["common_extensions"] = ["mixed"]

    return file_info


def debug_step_by_step(doc1: MockDocument, doc2: MockDocument):
    """Debug the file information generation process step by step."""
    print("\n🔍 STEP-BY-STEP DEBUGGING")
    print("=" * 60)

    # Step 1: Initial file sets
    files1 = set(doc1.diff_analysis.modified_files if doc1.diff_analysis else [])
    files2 = set(doc2.diff_analysis.modified_files if doc2.diff_analysis else [])

    print("📁 STEP 1: Initial file sets")
    print(f"   - {doc1.repository}: {list(files1)}")
    print(f"   - {doc2.repository}: {list(files2)}")
    print(f"   - files1 count: {len(files1)}")
    print(f"   - files2 count: {len(files2)}")

    # Step 2: Combined files
    all_files = files1.union(files2)
    print("\n📂 STEP 2: Combined file analysis")
    print(f"   - All files: {list(all_files)}")
    print(f"   - Total unique files: {len(all_files)}")

    # Step 3: Extract extensions and directories
    all_exts = set()
    all_dirs = set()

    print("\n🏷️ STEP 3: Extension and directory extraction")
    for file_path in all_files:
        print(f"   Processing: {file_path}")

        # Extract extensions
        if "." in file_path:
            ext = file_path.split(".")[-1].lower()
            all_exts.add(ext)
            print(f"     -> Extension: {ext}")

        # Extract directories
        if "/" in file_path:
            dirs = file_path.split("/")[:-1]
            all_dirs.update(dirs)
            print(f"     -> Directories: {dirs}")

    print(f"   - All extensions found: {list(all_exts)}")
    print(f"   - All directories found: {list(all_dirs)}")

    # Step 4: Technology mapping
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

    print("\n🛠️ STEP 4: Technology mapping")
    for ext in all_exts:
        if ext in ext_tech_map:
            tech = ext_tech_map[ext]
            tech_stack.add(tech)
            print(f"   - '{ext}' -> '{tech}' ✅")
        else:
            print(f"   - '{ext}' -> NO MAPPING ❌")

    print(f"   - Final tech stack: {list(tech_stack)}")

    # Step 5: Initial file_info construction
    print("\n📋 STEP 5: Initial file_info construction")
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
        print(f"   - Technology stack: {file_info['technology_stack']}")
        print(f"   - Common extensions: {file_info['common_extensions']}")
        print(f"   - Common directories: {file_info['common_directories']}")

    # Step 6: Overlap calculation (the critical path)
    print("\n🔗 STEP 6: Overlap calculation")
    print(f"   - files1 non-empty: {bool(files1)}")
    print(f"   - files2 non-empty: {bool(files2)}")
    print(f"   - Both have files: {bool(files1 and files2)}")

    if files1 and files2:
        print("   - ENTERING overlap calculation...")

        # Common files
        common_files = files1.intersection(files2)
        file_info["common_files"] = list(common_files)[:5]
        print(f"     - Common files: {list(common_files)}")

        # File overlap ratio
        total_files = files1.union(files2)
        file_info["file_overlap_ratio"] = (
            len(common_files) / len(total_files) if total_files else 0.0
        )
        print(f"     - Overlap ratio: {file_info['file_overlap_ratio']}")

        # Update with truly common extensions
        exts1 = {f.split(".")[-1].lower() for f in files1 if "." in f}
        exts2 = {f.split(".")[-1].lower() for f in files2 if "." in f}
        common_exts = exts1.intersection(exts2)
        file_info["common_extensions"] = list(common_exts)

        print(f"     - {doc1.repository} extensions: {list(exts1)}")
        print(f"     - {doc2.repository} extensions: {list(exts2)}")
        print(f"     - Common extensions: {list(common_exts)}")

        # Update common directories
        dirs1 = set()
        dirs2 = set()

        for f in files1:
            if "/" in f:
                dirs1.update(f.split("/")[:-1])

        for f in files2:
            if "/" in f:
                dirs2.update(f.split("/")[:-1])

        common_dirs = dirs1.intersection(dirs2)
        file_info["common_directories"] = list(common_dirs)[:3]

        print(f"     - {doc1.repository} directories: {list(dirs1)}")
        print(f"     - {doc2.repository} directories: {list(dirs2)}")
        print(f"     - Common directories: {list(common_dirs)}")
    else:
        print("   - SKIPPING overlap calculation (one or both documents have no files)")

    # Step 7: Final fallback check
    print("\n⚠️ STEP 7: Final fallback check")
    before_fallback = dict(file_info)

    if not any(
        [
            file_info["common_files"],
            file_info["common_extensions"],
            file_info["common_directories"],
            file_info["technology_stack"],
        ]
    ):
        print("   - FALLBACK TRIGGERED: Setting Unknown/mixed")
        file_info["technology_stack"] = ["Unknown"]
        file_info["common_extensions"] = ["mixed"]
    else:
        print("   - Fallback NOT triggered: Meaningful data found")

    print(f"   - Before fallback: {before_fallback}")
    print(f"   - After fallback: {file_info}")

    return file_info


def test_with_sample_data():
    """Test with sample data that mimics the actual documents."""

    # Test Case 1: Two documents with Python files (should produce Python tech stack)
    print("🧪 TEST CASE 1: Archon vs omnimcp with Python files")

    archon_files = [
        "src/server/api_routes/intelligence_api.py",
        "src/server/main.py",
        "src/server/services/correlation_generator.py",
        "README.md",
    ]

    omnimcp_files = [
        "examples/client_local_example.py",
        "examples/comprehensive_example.py",
        "src/omnimcp/tools.py",
        "pyproject.toml",
    ]

    archon_doc = MockDocument("Archon", archon_files)
    omnimcp_doc = MockDocument("omnimcp", omnimcp_files)

    # Debug step by step
    file_info = debug_step_by_step(archon_doc, omnimcp_doc)

    print("\n✅ FINAL RESULT:")
    print(json.dumps(file_info, indent=2))

    # Verify expectations
    print("\n🎯 VERIFICATION:")
    print(
        f"   - Technology stack contains Python: {'Python' in file_info['technology_stack']}"
    )
    print(
        f"   - Common extensions contain 'py': {'py' in file_info['common_extensions']}"
    )
    print(
        f"   - NOT Unknown/mixed: {file_info['technology_stack'] != ['Unknown'] and file_info['common_extensions'] != ['mixed']}"
    )


def test_empty_documents():
    """Test with documents that have no files (should trigger fallback)."""
    print("\n\n🧪 TEST CASE 2: Empty documents (should trigger fallback)")

    empty_doc1 = MockDocument("repo1", [])
    empty_doc2 = MockDocument("repo2", [])

    file_info = debug_step_by_step(empty_doc1, empty_doc2)

    print("\n✅ FINAL RESULT:")
    print(json.dumps(file_info, indent=2))

    print("\n🎯 VERIFICATION:")
    print(
        f"   - Should be Unknown/mixed: {file_info['technology_stack'] == ['Unknown'] and file_info['common_extensions'] == ['mixed']}"
    )


if __name__ == "__main__":
    print("🚀 STANDALONE CORRELATION FILE INFORMATION TEST")
    print("=" * 80)

    test_with_sample_data()
    test_empty_documents()
