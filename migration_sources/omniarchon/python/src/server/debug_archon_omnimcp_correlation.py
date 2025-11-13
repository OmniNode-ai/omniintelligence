#!/usr/bin/env python3
"""
Debug why Archon ↔ omnimcp documents aren't correlating.

This test uses the actual document data and traces through the
semantic correlation logic to see where it fails.
"""

from typing import Any

# Real documents from the API
ARCHON_DOC = {
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

OMNIMCP_DOC = {
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


class MockDiffAnalysis:
    def __init__(self, modified_files: list[str]):
        self.modified_files = modified_files


class MockDocument:
    def __init__(self, doc_data: dict[str, Any]):
        self.id = doc_data["id"]
        self.repository = doc_data["repository"]
        self.commit_sha = doc_data["commit_sha"]
        self.created_at = doc_data["created_at"]
        self.change_type = doc_data.get("change_type", "unknown")
        self.raw_content = doc_data.get("intelligence_data", {})

        # Create diff_analysis
        intelligence_data = doc_data.get("intelligence_data", {})
        diff_analysis_data = intelligence_data.get("diff_analysis")

        if diff_analysis_data and diff_analysis_data.get("modified_files"):
            self.diff_analysis = MockDiffAnalysis(diff_analysis_data["modified_files"])
        else:
            self.diff_analysis = None


def extract_document_content_for_analysis(doc) -> str:
    """Extract meaningful content from document for analysis."""
    content_parts = []

    # Add repository name
    if doc.repository:
        content_parts.append(doc.repository.lower())

    # Add any available content from raw_content
    if hasattr(doc, "raw_content") and doc.raw_content:
        # Extract from various content sections
        for section in [
            "initialization_summary",
            "recommendations",
            "quality_baseline",
        ]:
            if section in doc.raw_content:
                section_content = str(doc.raw_content[section])
                content_parts.append(section_content.lower())

    return " ".join(content_parts)


def analyze_content_similarity(doc1, doc2) -> float:
    """Analyze content-based similarity between documents."""
    # Extract content from documents for analysis
    content1 = extract_document_content_for_analysis(doc1)
    content2 = extract_document_content_for_analysis(doc2)

    print(f"   📄 Content 1 ({doc1.repository}): '{content1}'")
    print(f"   📄 Content 2 ({doc2.repository}): '{content2}'")

    if not content1 or not content2:
        print("   ⚠️ Missing content - returning 0.1")
        return 0.1  # Low similarity if no content

    # Calculate text-based similarity using shared keywords and concepts
    keywords1 = set(content1.lower().split())
    keywords2 = set(content2.lower().split())

    print(f"   🔤 Keywords 1: {keywords1}")
    print(f"   🔤 Keywords 2: {keywords2}")

    if keywords1 and keywords2:
        intersection = len(keywords1.intersection(keywords2))
        union = len(keywords1.union(keywords2))
        similarity = intersection / union if union > 0 else 0.0
        boosted_similarity = min(
            similarity * 2.0, 0.8
        )  # Boost similarity but cap at 80%

        print(f"   🔍 Intersection: {intersection}, Union: {union}")
        print(f"   📊 Raw similarity: {similarity}")
        print(f"   📈 Boosted similarity: {boosted_similarity}")

        return boosted_similarity

    print("   ⚠️ Empty keywords - returning 0.2")
    return 0.2  # Default low similarity


def extract_quality_indicators(doc) -> list[str]:
    """Extract quality indicators from document."""
    indicators = []

    # Repository type indicators
    if doc.repository:
        repo_lower = doc.repository.lower()
        if "agent" in repo_lower:
            indicators.append("agent_system")
        if "omni" in repo_lower:
            indicators.append("omni_ecosystem")
        if "archon" in repo_lower:
            indicators.append("archon_platform")

    # Content quality indicators
    content = extract_document_content_for_analysis(doc)
    if content:
        if "intelligence" in content:
            indicators.append("intelligence_enhanced")
        if "quality" in content:
            indicators.append("quality_focused")
        if "performance" in content:
            indicators.append("performance_optimized")

    return indicators


def analyze_quality_pattern_correlation(doc1, doc2) -> float:
    """Analyze correlation based on quality patterns and insights."""
    # Extract quality indicators from document content
    quality1 = extract_quality_indicators(doc1)
    quality2 = extract_quality_indicators(doc2)

    print(f"   🏷️ Quality indicators 1 ({doc1.repository}): {quality1}")
    print(f"   🏷️ Quality indicators 2 ({doc2.repository}): {quality2}")

    # Calculate correlation based on shared quality patterns
    shared_patterns = set(quality1).intersection(set(quality2))
    total_patterns = set(quality1).union(set(quality2))

    if total_patterns:
        correlation = len(shared_patterns) / len(total_patterns)
        capped_correlation = min(correlation, 0.6)  # Cap quality correlation at 60%

        print(f"   🔗 Shared patterns: {shared_patterns}")
        print(
            f"   📊 Quality correlation: {correlation} (capped: {capped_correlation})"
        )

        return capped_correlation

    print("   ⚠️ No quality patterns - returning 0.1")
    return 0.1  # Default low correlation


def debug_semantic_correlation_analysis(doc1, doc2):
    """Debug the semantic correlation analysis step by step."""
    print(f"\n🧠 SEMANTIC CORRELATION ANALYSIS: {doc1.repository} vs {doc2.repository}")
    print("=" * 70)

    # Step 1: Content similarity
    print("📝 STEP 1: Content Similarity Analysis")
    content_similarity = analyze_content_similarity(doc1, doc2)
    print(f"   ✅ Content similarity: {content_similarity}")

    # Step 2: Quality pattern correlation
    print("\n🏷️ STEP 2: Quality Pattern Correlation")
    quality_correlation = analyze_quality_pattern_correlation(doc1, doc2)
    print(f"   ✅ Quality correlation: {quality_correlation}")

    # Step 3: Calculate comprehensive semantic similarity
    print("\n🧮 STEP 3: Combined Semantic Similarity")
    # 70% content similarity, 30% quality pattern correlation
    semantic_similarity = (content_similarity * 0.7) + (quality_correlation * 0.3)
    print(f"   📊 Raw semantic similarity: {semantic_similarity}")
    print(
        f"   📈 Formula: ({content_similarity} * 0.7) + ({quality_correlation} * 0.3)"
    )

    # Step 4: Apply variance (like in original code)
    import random

    random.seed(42)  # Fixed seed for reproducible results
    variance = random.uniform(0.9, 1.0)  # Smaller variance for semantic analysis
    semantic_similarity = semantic_similarity * variance
    print(f"   🎲 Variance factor: {variance}")
    print(f"   🎯 Final semantic similarity: {semantic_similarity}")

    # Step 5: Check threshold
    base_threshold = 0.3  # From correlation_generator.py line 60
    adjusted_threshold = base_threshold * 0.7  # From line 442

    print("\n🎚️ STEP 4: Threshold Check")
    print(f"   📊 Base semantic threshold: {base_threshold}")
    print(f"   📉 Adjusted threshold (70%): {adjusted_threshold}")
    print(f"   🎯 Final similarity: {semantic_similarity}")
    print(
        f"   {'✅ PASSES' if semantic_similarity >= adjusted_threshold else '❌ FAILS'} threshold check"
    )

    return {
        "content_similarity": content_similarity,
        "quality_correlation": quality_correlation,
        "semantic_similarity": semantic_similarity,
        "threshold": adjusted_threshold,
        "passes_threshold": semantic_similarity >= adjusted_threshold,
    }


def main():
    """Main test function."""
    print("🔍 ARCHON ↔ OMNIMCP CORRELATION DEBUG")
    print("=" * 80)

    # Create mock documents
    archon_doc = MockDocument(ARCHON_DOC)
    omnimcp_doc = MockDocument(OMNIMCP_DOC)

    print("📄 Documents:")
    print(
        f"   - {archon_doc.repository}: {len(archon_doc.diff_analysis.modified_files)} files"
    )
    print(
        f"   - {omnimcp_doc.repository}: {len(omnimcp_doc.diff_analysis.modified_files)} files"
    )

    # Test both directions
    print("\n🔄 DIRECTION 1: Archon → omnimcp")
    result1 = debug_semantic_correlation_analysis(archon_doc, omnimcp_doc)

    print("\n🔄 DIRECTION 2: omnimcp → Archon")
    result2 = debug_semantic_correlation_analysis(omnimcp_doc, archon_doc)

    print("\n🎯 FINAL ANALYSIS")
    print("=" * 80)
    print(
        f"Direction 1 (Archon → omnimcp): {'✅ CORRELATION' if result1['passes_threshold'] else '❌ NO CORRELATION'}"
    )
    print(
        f"Direction 2 (omnimcp → Archon): {'✅ CORRELATION' if result2['passes_threshold'] else '❌ NO CORRELATION'}"
    )

    if not result1["passes_threshold"] and not result2["passes_threshold"]:
        print("\n🔍 WHY NO CORRELATIONS?")
        print(
            f"   - Content similarity too low: {max(result1['content_similarity'], result2['content_similarity'])}"
        )
        print(
            f"   - Quality correlation too low: {max(result1['quality_correlation'], result2['quality_correlation'])}"
        )
        print(f"   - Threshold too high: {result1['threshold']}")

        print("\n💡 POSSIBLE SOLUTIONS:")
        print(
            f"   1. Lower semantic threshold from {result1['threshold']:.3f} to ~0.15"
        )
        print("   2. Improve content extraction to include file information")
        print("   3. Add more quality indicators for repository relationships")
        print("   4. Boost similarity for related repositories (archon/omni)")


if __name__ == "__main__":
    main()
