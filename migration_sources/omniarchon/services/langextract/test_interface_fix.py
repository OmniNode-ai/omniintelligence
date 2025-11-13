#!/usr/bin/env python3
"""
Test script to verify interface fixes for langextract service.

This script tests the critical interface fix where semantic_extractor.extract_semantic_patterns
now returns SemanticAnalysisResult instead of List[SemanticPattern].
"""

import asyncio
import sys
from pathlib import Path

# Add the service directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from extractors.semantic_pattern_extractor import SemanticPatternExtractor
from models.extraction_models import SemanticAnalysisResult


async def test_semantic_pattern_interface():
    """Test that semantic pattern extractor returns correct type"""
    print("🔬 Testing Semantic Pattern Extractor Interface...")

    extractor = SemanticPatternExtractor()

    test_content = """
    This is a test document for semantic analysis.

    We are testing the following concepts:
    - Entity extraction capabilities
    - Relationship mapping between different components
    - Semantic pattern recognition
    - Document analysis workflows

    The system should identify patterns like:
    1. Problem-solution relationships
    2. Process steps and procedures
    3. Technical terminology and concepts

    This document contains various entities like:
    - Organizations: Tech Corp, Innovation Labs
    - People: John Smith, Dr. Jane Doe
    - Locations: New York, San Francisco
    - Dates: 2024-01-15, March 2024

    The analysis should extract meaningful relationships and semantic context.
    """

    try:
        # Test the extract_semantic_patterns method
        print("📊 Calling extract_semantic_patterns...")
        result = await extractor.extract_semantic_patterns(
            content=test_content,
            entities=[],
            context={"test_mode": True, "domain": "technical_documentation"},
        )

        # Verify the result type
        print(f"✅ Result type: {type(result)}")
        print(
            f"✅ Is SemanticAnalysisResult: {isinstance(result, SemanticAnalysisResult)}"
        )

        # Verify the result has expected attributes
        print(f"✅ Has semantic_context: {hasattr(result, 'semantic_context')}")
        print(f"✅ Has semantic_patterns: {hasattr(result, 'semantic_patterns')}")

        if hasattr(result, "semantic_context"):
            print(f"✅ semantic_context type: {type(result.semantic_context)}")
            print(f"✅ semantic_context content: {result.semantic_context}")

        if hasattr(result, "semantic_patterns"):
            print(f"✅ semantic_patterns type: {type(result.semantic_patterns)}")
            print(f"✅ semantic_patterns count: {len(result.semantic_patterns)}")

        print(f"✅ Concepts found: {len(result.concepts)}")
        print(f"✅ Themes found: {len(result.themes)}")
        print(f"✅ Primary topics: {result.primary_topics}")

        print("🎉 INTERFACE TEST SUCCESSFUL!")
        return True

    except Exception as e:
        print(f"❌ INTERFACE TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_interface_attribute_access():
    """Test the specific attribute access patterns from app.py"""
    print("\n🔍 Testing Attribute Access Patterns...")

    extractor = SemanticPatternExtractor()

    test_content = "Sample content for testing attribute access patterns."

    try:
        # Call the method
        semantic_results = await extractor.extract_semantic_patterns(
            content=test_content, entities=[], context={"test": "context"}
        )

        # Test the problematic attribute accesses from app.py
        print("📊 Testing semantic_results.semantic_context access...")
        semantic_context = semantic_results.semantic_context
        print(f"✅ semantic_context accessed successfully: {type(semantic_context)}")

        print("📊 Testing semantic_results.semantic_patterns access...")
        semantic_patterns = semantic_results.semantic_patterns
        print(
            f"✅ semantic_patterns accessed successfully: {type(semantic_patterns)}, count: {len(semantic_patterns)}"
        )

        print("🎉 ATTRIBUTE ACCESS TEST SUCCESSFUL!")
        return True

    except AttributeError as e:
        print(f"❌ ATTRIBUTE ACCESS FAILED: {e}")
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        return False


async def main():
    """Run all interface tests"""
    print("🚀 Starting LangExtract Interface Tests...")
    print("=" * 60)

    # Test 1: Basic interface functionality
    test1_passed = await test_semantic_pattern_interface()

    # Test 2: Specific attribute access patterns
    test2_passed = await test_interface_attribute_access()

    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY:")
    print(f"✅ Interface Type Test: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"✅ Attribute Access Test: {'PASSED' if test2_passed else 'FAILED'}")

    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED! Interface fixes are working correctly.")
        print(
            "🔧 The original 'list' object has no attribute 'semantic_context' error should be resolved."
        )
        return True
    else:
        print("❌ SOME TESTS FAILED! Interface issues remain.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
