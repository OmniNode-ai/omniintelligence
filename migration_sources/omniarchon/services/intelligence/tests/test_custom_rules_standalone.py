"""
Standalone test for CustomQualityRulesEngine

Tests basic functionality without external dependencies.
Can be run directly: python test_custom_rules_standalone.py

Created: 2025-10-15
"""

import asyncio
import sys
from pathlib import Path

import pytest
from archon_services.quality.custom_rules import (
    CustomQualityRule,
    CustomQualityRulesEngine,
)

# Add parent directory to path for imports


async def test_basic_functionality():
    """Test basic custom rules engine functionality."""
    print("=" * 60)
    print("Testing CustomQualityRulesEngine")
    print("=" * 60)

    engine = CustomQualityRulesEngine()

    # Test 1: Rule registration
    print("\n✅ Test 1: Rule Registration")
    rule1 = CustomQualityRule(
        rule_id="test_rule_1",
        project_id="test_project",
        rule_type="pattern",
        description="Check for class definitions",
        severity="warning",
        checker=lambda code: "class" in code,
        weight=0.5,
        enabled=True,
    )

    await engine.register_rule("test_project", rule1)
    rules = await engine.get_project_rules("test_project")
    assert len(rules) == 1
    print(f"   Registered rule: {rule1.rule_id}")
    print(f"   Total rules: {len(rules)}")

    # Test 2: Rule evaluation - passing
    print("\n✅ Test 2: Rule Evaluation (Passing)")
    code_with_class = """
class MyClass:
    def method(self):
        pass
"""
    result = await engine.evaluate_rules("test_project", code_with_class)
    print(f"   Custom Score: {result['custom_score']:.2f}")
    print(f"   Rules Evaluated: {result['rules_evaluated']}")
    print(f"   Violations: {len(result['violations'])}")
    assert result["custom_score"] == pytest.approx(1.0, abs=1e-6)

    # Test 3: Rule evaluation - failing
    print("\n✅ Test 3: Rule Evaluation (Failing)")
    code_without_class = """
def my_function():
    pass
"""
    result = await engine.evaluate_rules("test_project", code_without_class)
    print(f"   Custom Score: {result['custom_score']:.2f}")
    print(f"   Rules Evaluated: {result['rules_evaluated']}")
    print(f"   Warnings: {len(result['warnings'])}")
    assert result["custom_score"] == pytest.approx(0.0, abs=1e-6)
    assert len(result["warnings"]) == 1

    # Test 4: Pattern checker (via public API)
    print("\n✅ Test 4: Pattern Checker")
    # Create fresh engine for isolated test
    engine = CustomQualityRulesEngine()

    # Register pattern rule for async functions
    import re

    async_pattern_rule = CustomQualityRule(
        rule_id="async_pattern_rule",
        project_id="pattern_test",
        rule_type="pattern",
        description="Check for async function definitions",
        severity="warning",
        checker=lambda code: bool(re.search(r"async\s+def", code)),
        weight=1.0,
        enabled=True,
    )
    await engine.register_rule("pattern_test", async_pattern_rule)

    # Test with async code (should pass)
    result_async = await engine.evaluate_rules(
        "pattern_test", "async def my_async_func():"
    )
    assert result_async["custom_score"] == 1.0
    assert len(result_async["warnings"]) == 0

    # Test with sync code (should fail)
    result_sync = await engine.evaluate_rules("pattern_test", "def my_sync_func():")
    assert result_sync["custom_score"] == 0.0
    assert len(result_sync["warnings"]) == 1
    print("   Pattern checker working correctly")

    # Test 5: Forbid pattern checker (via public API)
    print("\n✅ Test 5: Forbid Pattern Checker")
    # Create fresh engine for isolated test
    engine = CustomQualityRulesEngine()

    # Register forbid pattern rule for 'Any' type
    forbid_any_rule = CustomQualityRule(
        rule_id="forbid_any_rule",
        project_id="forbid_test",
        rule_type="pattern",
        description="Forbid usage of Any type annotation",
        severity="critical",
        checker=lambda code: not bool(re.search(r":\s*Any\b", code)),
        weight=1.0,
        enabled=True,
    )
    await engine.register_rule("forbid_test", forbid_any_rule)

    # Test without Any (should pass)
    result_no_any = await engine.evaluate_rules("forbid_test", "def func(x: int):")
    assert result_no_any["custom_score"] == 1.0
    assert len(result_no_any["violations"]) == 0

    # Test with Any (should fail)
    result_with_any = await engine.evaluate_rules("forbid_test", "def func(x: Any):")
    assert result_with_any["custom_score"] == 0.0
    assert len(result_with_any["violations"]) == 1
    print("   Forbid pattern checker working correctly")

    # Test 6: Complexity checker (via public API)
    print("\n✅ Test 6: Complexity Checker")
    # Create fresh engine for isolated test
    engine = CustomQualityRulesEngine()

    def complexity_checker(max_complexity: int):
        """Create complexity checker closure."""

        def checker(code: str) -> bool:
            try:
                import ast

                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Calculate complexity (decision points + 1)
                        complexity = 1
                        for child in ast.walk(node):
                            if isinstance(child, (ast.If, ast.While, ast.For)):
                                complexity += 1
                            elif isinstance(child, ast.ExceptHandler):
                                complexity += 1
                            elif isinstance(child, ast.BoolOp):
                                complexity += len(child.values) - 1
                        if complexity > max_complexity:
                            return False
                return True
            except SyntaxError:
                return False

        return checker

    complexity_rule = CustomQualityRule(
        rule_id="complexity_rule",
        project_id="complexity_test",
        rule_type="metric",
        description="Check cyclomatic complexity",
        severity="warning",
        checker=complexity_checker(max_complexity=3),
        weight=1.0,
        enabled=True,
    )
    await engine.register_rule("complexity_test", complexity_rule)

    simple_code = """
def simple():
    return True
"""
    complex_code = """
def complex(a, b, c):
    if a > 0:
        if b > 0:
            if c > 0:
                return True
    return False
"""
    # Test simple code (should pass)
    result_simple = await engine.evaluate_rules("complexity_test", simple_code)
    assert result_simple["custom_score"] == 1.0

    # Test complex code (should fail)
    result_complex = await engine.evaluate_rules("complexity_test", complex_code)
    assert result_complex["custom_score"] == 0.0
    print("   Complexity checker working correctly")

    # Test 7: Docstring coverage checker (via public API)
    print("\n✅ Test 7: Docstring Coverage Checker")
    # Create fresh engine for isolated test
    engine = CustomQualityRulesEngine()

    def docstring_checker(min_coverage: float):
        """Create docstring coverage checker closure."""

        def checker(code: str) -> bool:
            try:
                import ast

                tree = ast.parse(code)
                total_functions = 0
                documented_functions = 0

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        total_functions += 1
                        if ast.get_docstring(node):
                            documented_functions += 1

                if total_functions == 0:
                    return True  # No functions to check

                coverage = documented_functions / total_functions
                return coverage >= min_coverage
            except SyntaxError:
                return False

        return checker

    docstring_rule = CustomQualityRule(
        rule_id="docstring_rule",
        project_id="docstring_test",
        rule_type="metric",
        description="Check docstring coverage",
        severity="suggestion",
        checker=docstring_checker(min_coverage=0.7),
        weight=1.0,
        enabled=True,
    )
    await engine.register_rule("docstring_test", docstring_rule)

    code_with_docs = """
def func1():
    '''Docstring.'''
    pass

def func2():
    '''Docstring.'''
    pass
"""
    # Test code with good docstring coverage (should pass)
    result_docs = await engine.evaluate_rules("docstring_test", code_with_docs)
    assert result_docs["custom_score"] == 1.0
    print("   Docstring checker working correctly")
    # Test 8: Weighted scoring
    print("\n✅ Test 8: Weighted Scoring")

    # Create fresh engine for isolated test
    engine = CustomQualityRulesEngine()

    # Add weighted rules
    rule_heavy = CustomQualityRule(
        rule_id="heavy_rule",
        project_id="weighted_test",
        rule_type="pattern",
        description="Heavy weight rule (passes)",
        severity="critical",
        checker=lambda code: True,  # Passes
        weight=0.7,
        enabled=True,
    )

    rule_light = CustomQualityRule(
        rule_id="light_rule",
        project_id="weighted_test",
        rule_type="pattern",
        description="Light weight rule (fails)",
        severity="warning",
        checker=lambda code: False,  # Fails
        weight=0.3,
        enabled=True,
    )

    await engine.register_rule("weighted_test", rule_heavy)
    await engine.register_rule("weighted_test", rule_light)

    result = await engine.evaluate_rules("weighted_test", "test code")
    print(f"   Total Weight: {result['total_weight']:.2f}")
    print(f"   Passed Weight: {result['passed_weight']:.2f}")
    print(f"   Custom Score: {result['custom_score']:.2f}")
    assert result["custom_score"] == pytest.approx(
        0.7, abs=1e-6
    )  # Only heavy rule passed

    # Test 9: Rule enable/disable
    print("\n✅ Test 9: Rule Enable/Disable")

    # Create fresh engine for isolated test
    engine = CustomQualityRulesEngine()
    rule = CustomQualityRule(
        rule_id="toggle_rule",
        project_id="toggle_test",
        rule_type="pattern",
        description="Rule to toggle",
        severity="warning",
        checker=lambda code: False,  # Always fails
        weight=1.0,
        enabled=True,
    )

    await engine.register_rule("toggle_test", rule)

    # Evaluate with enabled rule
    result_enabled = await engine.evaluate_rules("toggle_test", "test")
    print(f"   Enabled - Rules Evaluated: {result_enabled['rules_evaluated']}")
    assert result_enabled["rules_evaluated"] == 1

    # Disable rule
    await engine.disable_rule("toggle_test", "toggle_rule")

    # Evaluate with disabled rule
    result_disabled = await engine.evaluate_rules("toggle_test", "test")
    print(f"   Disabled - Rules Evaluated: {result_disabled['rules_evaluated']}")
    assert result_disabled["rules_evaluated"] == 0

    # Test 10: YAML configuration loading
    print("\n✅ Test 10: YAML Configuration Loading")

    # Check if example config exists
    config_path = (
        Path(__file__).parent.parent.parent.parent
        / "config"
        / "quality_rules"
        / "omniclaude.yaml"
    )

    if config_path.exists():
        # Create fresh engine for isolated test
        engine = CustomQualityRulesEngine()
        await engine.load_project_rules("omniclaude", config_path)

        rules = await engine.get_project_rules("omniclaude")
        print(f"   Loaded {len(rules)} rules from {config_path.name}")

        # Test evaluation with loaded rules
        sample_code = """
from omnibase.protocols import NodeBase

class NodeTestEffect(NodeBase):
    '''Test effect node.'''

    async def execute_effect(self, contract):
        '''Execute effect.'''
        return {"status": "success"}
"""
        result = await engine.evaluate_rules("omniclaude", sample_code)
        print(f"   Custom Score: {result['custom_score']:.2f}")
        print(f"   Violations: {len(result['violations'])}")
        print(f"   Warnings: {len(result['warnings'])}")
    else:
        print(f"   Config file not found: {config_path}")
        print("   Skipping YAML test")

    print("\n" + "=" * 60)
    print("✅ All Tests Passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_basic_functionality())
