#!/usr/bin/env python3
"""
Test correlation generation using real data from the API response.

This test uses the exact data structure we see in the API to reproduce
the issue where correlations show "Unknown"/"mixed" instead of "Python"/"py".
"""

import json
from typing import Any

# Real data from the API response
ARCHON_PYTHON_DOC = {
    "id": "1db561b8-6841-4465-9760-66e1bba06b3d",
    "created_at": "2025-09-05T11:49:00.000Z",
    "repository": "Archon",
    "commit_sha": "test-commit-hash",
    "author": "Test User",
    "change_type": "enhanced_code_changes_with_correlation",
    "intelligence_data": {
        "diff_analysis": {
            "total_changes": 3,
            "added_lines": 0,
            "removed_lines": 0,
            "modified_files": ["src/test1.py", "src/test2.py", "README.md"],
        }
    },
}

OMNIMCP_PYTHON_DOC = {
    "id": "2ec7b3fd-2f52-4255-af02-f25666ace810",
    "created_at": "2025-09-01T18:39:47.16168+00:00",
    "repository": "omnimcp",
    "commit_sha": "236573f",
    "author": "Intelligence System",
    "change_type": "pre_push_intelligence_update",
    "intelligence_data": {
        "diff_analysis": {
            "total_changes": 5,
            "added_lines": 0,
            "removed_lines": 0,
            "modified_files": [
                "examples/client_local_example.py",
                "examples/comprehensive_example.py",
                "examples/consul_example.py",
                "examples/server_example.py",
                "examples/simple_example.py",
            ],
        }
    },
}

# Document with null diff_analysis (causing the issue)
UNKNOWN_DOC = {
    "id": "69527cab-c1ee-4f77-a8ae-73d427cec7ae",
    "created_at": "2025-09-01T12:45:51.264589+00:00",
    "repository": "unknown",
    "commit_sha": "unknown",
    "author": "Claude Analysis",
    "change_type": "spec",
    "intelligence_data": {
        "diff_analysis": None,  # This is the problem!
        "correlation_analysis": {
            "temporal_correlations": [],
            "semantic_correlations": [],
            "breaking_changes": [],
        },
    },
}


class MockDiffAnalysis:
    def __init__(self, modified_files: list[str]):
        self.modified_files = modified_files


class MockDocument:
    """Mock document that matches the correlation generator expectations."""

    def __init__(self, doc_data: dict[str, Any]):
        self.id = doc_data["id"]
        self.repository = doc_data["repository"]
        self.commit_sha = doc_data["commit_sha"]
        self.created_at = doc_data["created_at"]
        self.change_type = doc_data.get("change_type", "unknown")
        self.raw_content = doc_data.get("intelligence_data", {})

        # Create diff_analysis from intelligence_data structure
        intelligence_data = doc_data.get("intelligence_data", {})
        diff_analysis_data = intelligence_data.get("diff_analysis")

        if diff_analysis_data and diff_analysis_data.get("modified_files"):
            self.diff_analysis = MockDiffAnalysis(diff_analysis_data["modified_files"])
        else:
            self.diff_analysis = None  # This is what causes the issue!


def get_file_information_for_correlation(
    doc1: MockDocument, doc2: MockDocument
) -> dict[str, Any]:
    """Recreate the exact logic from correlation_generator.py."""
    print(f"\n🔍 ANALYZING: {doc1.repository} vs {doc2.repository}")

    file_info = {
        "common_files": [],
        "common_extensions": [],
        "common_directories": [],
        "file_overlap_ratio": 0.0,
        "technology_stack": [],
    }

    # Get file sets from both documents - THE CRITICAL PATH
    files1 = set(doc1.diff_analysis.modified_files if doc1.diff_analysis else [])
    files2 = set(doc2.diff_analysis.modified_files if doc2.diff_analysis else [])

    print(f"   📁 {doc1.repository} diff_analysis: {doc1.diff_analysis is not None}")
    print(f"   📁 {doc1.repository} files: {list(files1)}")
    print(f"   📁 {doc2.repository} diff_analysis: {doc2.diff_analysis is not None}")
    print(f"   📁 {doc2.repository} files: {list(files2)}")

    # Collect all file extensions and directories from both documents
    all_files = files1.union(files2)
    print(f"   📂 Combined files: {list(all_files)}")

    if all_files:
        # Extract extensions from all files
        all_exts = set()
        all_dirs = set()

        for file_path in all_files:
            if "." in file_path:
                ext = file_path.split(".")[-1].lower()
                all_exts.add(ext)
            if "/" in file_path:
                dirs = file_path.split("/")[:-1]
                all_dirs.update(dirs)

        # Technology stack inference
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

        print(f"   🏷️ Extensions: {list(all_exts)}")
        print(f"   🛠️ Technology stack: {file_info['technology_stack']}")

    # Calculate overlap only if both documents have files
    if files1 and files2:
        print("   🔗 ENTERING overlap calculation (both docs have files)")

        # Common files (exact matches)
        common_files = files1.intersection(files2)
        file_info["common_files"] = list(common_files)[:5]

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
        file_info["common_directories"] = list(common_dirs)[:3]

        print(
            f"   ✅ Updated to common only - extensions: {file_info['common_extensions']}"
        )

    else:
        print("   ⏭️ SKIPPING overlap calculation:")
        print(f"      - files1 empty: {not files1}")
        print(f"      - files2 empty: {not files2}")

    # Ensure file_information is never completely empty (prevents JSON filtering)
    if not any(
        [
            file_info["common_files"],
            file_info["common_extensions"],
            file_info["common_directories"],
            file_info["technology_stack"],
        ]
    ):
        print("   ⚠️ FALLBACK: Setting Unknown/mixed")
        file_info["technology_stack"] = ["Unknown"]
        file_info["common_extensions"] = ["mixed"]

    return file_info


def test_scenarios():
    """Test different scenarios to identify the root cause."""

    print("🧪 TEST SCENARIO 1: Archon (Python) vs omnimcp (Python)")
    print("=" * 60)
    archon_doc = MockDocument(ARCHON_PYTHON_DOC)
    omnimcp_doc = MockDocument(OMNIMCP_PYTHON_DOC)

    result1 = get_file_information_for_correlation(archon_doc, omnimcp_doc)
    print(f"✅ Result: {json.dumps(result1, indent=2)}")

    print("\n\n🧪 TEST SCENARIO 2: Archon (Python) vs Unknown (no files)")
    print("=" * 60)
    archon_doc = MockDocument(ARCHON_PYTHON_DOC)
    unknown_doc = MockDocument(UNKNOWN_DOC)

    result2 = get_file_information_for_correlation(archon_doc, unknown_doc)
    print(f"✅ Result: {json.dumps(result2, indent=2)}")

    print("\n\n🧪 TEST SCENARIO 3: Unknown (no files) vs omnimcp (Python)")
    print("=" * 60)
    unknown_doc = MockDocument(UNKNOWN_DOC)
    omnimcp_doc = MockDocument(OMNIMCP_PYTHON_DOC)

    result3 = get_file_information_for_correlation(unknown_doc, omnimcp_doc)
    print(f"✅ Result: {json.dumps(result3, indent=2)}")

    print("\n\n🧪 TEST SCENARIO 4: Unknown vs Unknown (both no files)")
    print("=" * 60)
    unknown_doc1 = MockDocument(UNKNOWN_DOC)
    unknown_doc2 = MockDocument(
        {**UNKNOWN_DOC, "id": "different-id", "repository": "another-unknown"}
    )

    result4 = get_file_information_for_correlation(unknown_doc1, unknown_doc2)
    print(f"✅ Result: {json.dumps(result4, indent=2)}")

    print("\n\n🎯 ANALYSIS")
    print("=" * 60)
    print(f"Scenario 1 (Python + Python): Technology = {result1['technology_stack']}")
    print(f"Scenario 2 (Python + No files): Technology = {result2['technology_stack']}")
    print(f"Scenario 3 (No files + Python): Technology = {result3['technology_stack']}")
    print(
        f"Scenario 4 (No files + No files): Technology = {result4['technology_stack']}"
    )

    print("\n🔍 ROOT CAUSE IDENTIFICATION:")

    if result1["technology_stack"] == ["Python"]:
        print("✅ Python+Python correctly produces Python tech stack")
    else:
        print("❌ Python+Python should produce Python tech stack")

    if result2["technology_stack"] == ["Unknown"]:
        print("⚠️ Python+No files produces Unknown (fallback triggered)")
    elif "Python" in result2["technology_stack"]:
        print("✅ Python+No files still produces Python tech stack")

    if result4["technology_stack"] == ["Unknown"]:
        print("✅ No files+No files correctly produces Unknown (fallback)")

    # This tells us what the correlation system is seeing
    if result1["technology_stack"] != ["Unknown"] and result2["technology_stack"] == [
        "Unknown"
    ]:
        print(
            "\n💡 CONCLUSION: The system is correlating documents with NULL diff_analysis"
        )
        print("   - When both docs have Python files → Works correctly")
        print("   - When one doc has NULL diff_analysis → Fallback to Unknown/mixed")
        print(
            "   - The '1 correlation' you're seeing is likely between two 'unknown' repos"
        )


if __name__ == "__main__":
    test_scenarios()
