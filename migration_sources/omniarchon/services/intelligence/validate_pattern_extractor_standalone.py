"""
Standalone Pattern Extractor Validation

Validates pattern extraction without requiring full service dependencies.

Created: 2025-10-15 (MVP Phase 5A)
Usage: python validate_pattern_extractor_standalone.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for proper imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import pattern extractor module directly
from services.pattern_learning.phase5_autonomous.pattern_extractor import (
    PatternExtractor,
)


async def main():
    """Run validation tests for PatternExtractor."""

    print("=" * 80)
    print("Pattern Extractor Validation - Phase 5A MVP (Standalone)")
    print("=" * 80)
    print()

    extractor = PatternExtractor()
    validation_result_success = {
        "is_valid": True,
        "quality_score": 0.92,
        "onex_compliance_score": 0.95,
    }

    test_cases = [
        {
            "name": "Base Class Inheritance",
            "code": """
class NodeDatabaseWriterEffect(NodeBase):
    '''Effect node for database writes.'''
    pass
""",
            "expected_category": "architectural",
            "expected_pattern": "base_class_inheritance",
        },
        {
            "name": "Mixin Composition",
            "code": """
class NodeCachedApiEffect(NodeBase, CachingMixin, RetryMixin):
    '''Effect node with mixins.'''
    pass
""",
            "expected_category": "architectural",
            "expected_pattern": "mixin_composition",
        },
        {
            "name": "ONEX Method Implementation",
            "code": """
class NodeExampleEffect(NodeBase):
    async def execute_effect(self, contract):
        return await self._perform(contract)
""",
            "expected_category": "architectural",
            "expected_pattern": "onex_method_implementation",
        },
        {
            "name": "Error Handling",
            "code": """
async def process_data(data):
    try:
        result = await validate(data)
        return result
    except ValueError as e:
        logger.error(f"Error: {e}")
        raise
    finally:
        await cleanup()
""",
            "expected_category": "quality",
            "expected_pattern": "error_handling",
        },
        {
            "name": "Type Annotations",
            "code": """
from typing import Dict, Any

async def compute(data: Dict[str, Any], factor: float) -> Dict[str, Any]:
    return {"result": data["value"] * factor}
""",
            "expected_category": "quality",
            "expected_pattern": "type_annotations",
        },
        {
            "name": "Documentation",
            "code": '''
async def operation(param: str) -> bool:
    """
    Perform operation.

    Args:
        param: Input parameter

    Returns:
        Operation success status
    """
    return True
''',
            "expected_category": "quality",
            "expected_pattern": "documentation",
        },
        {
            "name": "Input Validation",
            "code": """
async def process(user_id: str, data: dict):
    if not user_id or not isinstance(user_id, str):
        raise ValueError("Invalid user_id")
    return await store(user_id, data)
""",
            "expected_category": "security",
            "expected_pattern": "input_validation",
        },
        {
            "name": "Container Usage",
            "code": """
from omnibase.container import Container

class NodeDbEffect(NodeBase):
    def __init__(self, container: Container[DatabaseService]):
        self.db = container.resolve(DatabaseService)
""",
            "expected_category": "onex",
            "expected_pattern": "container_dependency_injection",
        },
        {
            "name": "Structured Logging",
            "code": """
class NodeApiEffect(NodeBase):
    async def execute_effect(self, contract):
        correlation_id = contract.correlation_id
        logger.info("Processing", extra={"correlation_id": correlation_id})
        return await self._call_api(contract)
""",
            "expected_category": "onex",
            "expected_pattern": "structured_logging",
        },
        {
            "name": "ONEX Naming Convention",
            "code": """
class NodeDatabaseWriterEffect(NodeBase):
    pass
""",
            "expected_category": "onex",
            "expected_pattern": "naming_convention",
        },
    ]

    total_tests = len(test_cases)
    successful_tests = 0
    results = []

    print(f"Running {total_tests} validation tests...\n")

    for i, test_case in enumerate(test_cases, 1):
        test_name = test_case["name"]
        print(f"Test {i}/{total_tests}: {test_name}...", end=" ")

        try:
            patterns = await extractor.extract_patterns(
                code=test_case["code"],
                validation_result=validation_result_success,
                node_type="effect",
            )

            # Check if expected patterns were found
            categories_found = {p.pattern_category.value for p in patterns}
            pattern_types_found = {p.pattern_type for p in patterns}

            # Check if expected category and pattern type match
            category_match = test_case["expected_category"] in categories_found
            pattern_match = test_case["expected_pattern"] in pattern_types_found

            if category_match and pattern_match and len(patterns) > 0:
                successful_tests += 1
                print(f"✅ PASS ({len(patterns)} patterns)")
                results.append(
                    {
                        "test": test_name,
                        "status": "PASS",
                        "patterns_found": len(patterns),
                    }
                )
            else:
                print("❌ FAIL")
                print(
                    f"   Expected: {test_case['expected_category']}/{test_case['expected_pattern']}"
                )
                print(
                    f"   Found: categories={categories_found}, patterns={pattern_types_found}"
                )
                results.append(
                    {
                        "test": test_name,
                        "status": "FAIL",
                        "patterns_found": len(patterns),
                    }
                )

        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append({"test": test_name, "status": "ERROR", "error": str(e)})

    # Calculate accuracy
    accuracy = (successful_tests / total_tests) * 100

    print()
    print("=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)
    print(f"Total Tests:        {total_tests}")
    print(f"Passed Tests:       {successful_tests}")
    print(f"Failed Tests:       {total_tests - successful_tests}")
    print(f"Accuracy:           {accuracy:.1f}%")
    print("Target:             80.0%")
    print("=" * 80)

    # Show detailed results for failed tests
    failed_tests = [r for r in results if r["status"] != "PASS"]
    if failed_tests:
        print("\nFailed Tests:")
        for result in failed_tests:
            print(f"  - {result['test']}: {result['status']}")
            if "error" in result:
                print(f"    Error: {result['error']}")

    print()
    if accuracy >= 80.0:
        print(
            f"✅ SUCCESS: Pattern extraction accuracy ({accuracy:.1f}%) meets 80% target!"
        )
        print(
            "\nPhase 5A Deliverable: Autonomous pattern extraction working with 80%+ accuracy"
        )
        return 0
    else:
        print(
            f"❌ FAILURE: Pattern extraction accuracy ({accuracy:.1f}%) below 80% target"
        )
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
