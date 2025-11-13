#!/usr/bin/env python3
"""
Test Intelligence Fixtures

Simple test script to verify intelligence fixtures work correctly and display
sample data for debugging purposes.
"""

import sys
from pathlib import Path

# Add the server directory to Python path so we can import fixtures
server_dir = Path(__file__).parent
sys.path.insert(0, str(server_dir))

from fixtures.intelligence_fixtures import (
    ASCIIDashboard,
    IntelligenceDebugUtils,
    IntelligenceFixtures,
)


def test_fixtures():
    """Test all fixture components."""
    print("🧪 TESTING INTELLIGENCE FIXTURES")
    print("=" * 80)

    # Test mock documents
    print("\n1️⃣  MOCK DOCUMENTS")
    print("─" * 40)

    mock_docs = IntelligenceFixtures.get_mock_documents()
    print(f"✅ Generated {len(mock_docs)} mock documents")

    for doc in mock_docs:
        print(f"   📄 {doc.repository} ({doc.id})")
        print(f"      Files: {len(doc.modified_files)} modified")
        print(f"      Tech: {doc.content[:50]}...")

    # Test correlations
    print("\n2️⃣  CORRELATION DATA")
    print("─" * 40)

    correlations = IntelligenceFixtures.get_realistic_correlations()
    print("✅ Generated correlation data:")
    print(f"   📈 Temporal correlations: {len(correlations['temporal_correlations'])}")
    print(f"   🔗 Semantic correlations: {len(correlations['semantic_correlations'])}")
    print(f"   💥 Breaking changes: {len(correlations['breaking_changes'])}")

    # Test dashboard rendering
    print("\n3️⃣  ASCII DASHBOARD")
    print("─" * 40)

    dashboard = ASCIIDashboard.render_correlation_summary(correlations)
    print(dashboard)

    # Test data quality validation
    print("\n4️⃣  DATA QUALITY VALIDATION")
    print("─" * 40)

    print("🔍 Validating semantic correlations...")
    for i, corr in enumerate(correlations["semantic_correlations"]):
        file_info = corr.get("file_information", {})
        issues = IntelligenceDebugUtils.validate_file_information(file_info)

        repo = corr.get("repository", "unknown")
        if issues:
            print(f"   ⚠️  {repo}: {len(issues)} issues")
            for issue in issues[:2]:  # Show first 2 issues
                print(f"      - {issue}")
        else:
            print(f"   ✅ {repo}: No validation issues")

    # Test intelligence response
    print("\n5️⃣  FULL INTELLIGENCE RESPONSE")
    print("─" * 40)

    intelligence_response = IntelligenceFixtures.get_intelligence_response()
    print("✅ Generated full intelligence response:")
    print(f"   📊 Success: {intelligence_response['success']}")
    print(f"   📄 Total documents: {intelligence_response['total_documents']}")
    print(f"   🔍 Documents in response: {len(intelligence_response['documents'])}")

    # Show sample document structure
    if intelligence_response["documents"]:
        doc = intelligence_response["documents"][0]
        print("\n📄 Sample Document Structure:")
        print(f"   ID: {doc['id']}")
        print(f"   Repository: {doc['repository']}")
        print(f"   Change Type: {doc['change_type']}")

        intel_data = doc.get("intelligence_data", {})
        if intel_data:
            diff_analysis = intel_data.get("diff_analysis", {})
            corr_analysis = intel_data.get("correlation_analysis", {})
            print(
                f"   📊 Diff Analysis: {diff_analysis.get('total_changes', 0)} changes"
            )
            print(
                f"   🔗 Correlations: {len(corr_analysis.get('semantic_correlations', []))} semantic"
            )

    print("\n✅ All fixture tests completed successfully!")
    print("💡 Use debug_intelligence.py for live API testing")


if __name__ == "__main__":
    test_fixtures()
