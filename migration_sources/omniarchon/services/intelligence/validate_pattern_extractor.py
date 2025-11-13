"""
Pattern Extractor Validation Script

Quick validation script to demonstrate pattern extraction functionality
without requiring full test framework setup.

Created: 2025-10-15 (MVP Phase 5A)
Usage: python validate_pattern_extractor.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.pattern_learning.phase5_autonomous import (
    PatternCategory,
    PatternExtractor,
)


async def main():
    """Run validation tests for PatternExtractor."""

    print("=" * 80)
    print("Pattern Extractor Validation - Phase 5A MVP")
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
            "expected_categories": {PatternCategory.ARCHITECTURAL},
            "expected_patterns": ["base_class_inheritance"],
        },
        {
            "name": "Mixin Composition",
            "code": """
class NodeCachedApiEffect(NodeBase, CachingMixin, RetryMixin):
    '''Effect node with mixins.'''
    pass
""",
            "expected_categories": {PatternCategory.ARCHITECTURAL},
            "expected_patterns": ["mixin_composition"],
        },
        {
            "name": "ONEX Method Implementation",
            "code": """
class NodeExampleEffect(NodeBase):
    async def execute_effect(self, contract):
        return await self._perform(contract)
""",
            "expected_categories": {PatternCategory.ARCHITECTURAL},
            "expected_patterns": ["onex_method_implementation"],
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
            "expected_categories": {PatternCategory.QUALITY},
            "expected_patterns": ["error_handling"],
        },
        {
            "name": "Type Annotations",
            "code": """
from typing import Dict, Any

async def compute(data: Dict[str, Any], factor: float) -> Dict[str, Any]:
    return {"result": data["value"] * factor}
""",
            "expected_categories": {PatternCategory.QUALITY},
            "expected_patterns": ["type_annotations"],
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
            "expected_categories": {PatternCategory.QUALITY},
            "expected_patterns": ["documentation"],
        },
        {
            "name": "Input Validation",
            "code": """
async def process(user_id: str, data: dict):
    if not user_id or not isinstance(user_id, str):
        raise ValueError("Invalid user_id")
    return await store(user_id, data)
""",
            "expected_categories": {PatternCategory.SECURITY},
            "expected_patterns": ["input_validation"],
        },
        {
            "name": "Container Usage",
            "code": """
from omnibase.container import Container

class NodeDbEffect(NodeBase):
    def __init__(self, container: Container[DatabaseService]):
        self.db = container.resolve(DatabaseService)
""",
            "expected_categories": {PatternCategory.ONEX},
            "expected_patterns": ["container_dependency_injection"],
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
            "expected_categories": {PatternCategory.ONEX},
            "expected_patterns": ["structured_logging"],
        },
        {
            "name": "ONEX Naming Convention",
            "code": """
class NodeDatabaseWriterEffect(NodeBase):
    pass
""",
            "expected_categories": {PatternCategory.ONEX},
            "expected_patterns": ["naming_convention"],
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
            categories_found = {p.pattern_category for p in patterns}
            pattern_types_found = {p.pattern_type for p in patterns}

            # Check if at least one expected category and pattern type match
            category_match = any(
                cat in categories_found for cat in test_case["expected_categories"]
            )
            pattern_match = any(
                pt in pattern_types_found for pt in test_case["expected_patterns"]
            )

            if category_match and pattern_match and len(patterns) > 0:
                successful_tests += 1
                print(f"✅ PASS ({len(patterns)} patterns extracted)")
                results.append(
                    {
                        "test": test_name,
                        "status": "PASS",
                        "patterns_found": len(patterns),
                        "categories": [c.value for c in categories_found],
                    }
                )
            else:
                print("❌ FAIL (Expected patterns not found)")
                results.append(
                    {
                        "test": test_name,
                        "status": "FAIL",
                        "patterns_found": len(patterns),
                        "categories": [c.value for c in categories_found],
                        "expected": test_case["expected_patterns"],
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

    if accuracy >= 80.0:
        print(
            f"\n✅ SUCCESS: Pattern extraction accuracy ({accuracy:.1f}%) meets 80% target!"
        )
        return 0
    else:
        print(
            f"\n❌ FAILURE: Pattern extraction accuracy ({accuracy:.1f}%) below 80% target"
        )
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
