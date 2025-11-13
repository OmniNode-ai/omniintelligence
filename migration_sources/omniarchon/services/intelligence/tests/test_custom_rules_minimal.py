"""
Minimal test for CustomQualityRulesEngine

Direct import without quality service dependencies.
Run with: python test_custom_rules_minimal.py

Created: 2025-10-15
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

# Load custom_rules module directly without triggering package __init__.py files
# This avoids pulling in heavy dependencies like omnibase_core
_module_path = (
    Path(__file__).parent.parent
    / "src"
    / "archon_services"
    / "quality"
    / "custom_rules.py"
)
_spec = importlib.util.spec_from_file_location("custom_rules", _module_path)
_custom_rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_custom_rules)

CustomQualityRule = _custom_rules.CustomQualityRule
CustomQualityRulesEngine = _custom_rules.CustomQualityRulesEngine


async def run_tests():
    """Run basic functionality tests."""
    print("=" * 70)
    print("CustomQualityRulesEngine - Minimal Functionality Test")
    print("=" * 70)

    tests_passed = 0
    tests_total = 0

    # Test 1: Engine initialization
    tests_total += 1
    print("\n[Test 1] Engine Initialization")
    try:
        engine = CustomQualityRulesEngine()
        assert hasattr(engine, "rules")
        assert hasattr(engine, "rule_checkers")
        print("   ✅ PASS - Engine initialized successfully")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL - {e}")

    # Test 2: Rule registration
    tests_total += 1
    print("\n[Test 2] Rule Registration")
    try:
        rule = CustomQualityRule(
            rule_id="test_pattern",
            project_id="test_proj",
            rule_type="pattern",
            description="Test pattern rule",
            severity="warning",
            checker=lambda code: "class" in code,
            weight=0.5,
            enabled=True,
        )
        await engine.register_rule("test_proj", rule)
        rules = await engine.get_project_rules("test_proj")
        assert len(rules) == 1
        assert rules[0].rule_id == "test_pattern"
        print(f"   ✅ PASS - Registered rule: {rule.rule_id}")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL - {e}")

    # Test 3: Pattern checker creation
    tests_total += 1
    print("\n[Test 3] Pattern Checker")
    try:
        checker = engine._create_pattern_checker(r"async\s+def")
        assert checker("async def func():") is True
        assert checker("def func():") is False
        print("   ✅ PASS - Pattern checker works correctly")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL - {e}")

    # Test 4: Forbid pattern checker
    tests_total += 1
    print("\n[Test 4] Forbid Pattern Checker")
    try:
        checker = engine._create_forbid_pattern_checker(r":\s*Any\b")
        assert checker("def func(x: int):") is True
        assert checker("def func(x: Any):") is False
        print("   ✅ PASS - Forbid pattern checker works correctly")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL - {e}")

    # Test 5: Complexity checker
    tests_total += 1
    print("\n[Test 5] Complexity Checker")
    try:
        checker = engine._create_complexity_checker(max_complexity=3)

        simple = "def simple():\n    return True"
        complex_code = """
def complex(a, b, c):
    if a:
        if b:
            if c:
                return True
    return False
"""
        assert checker(simple) is True
        assert checker(complex_code) is False
        print("   ✅ PASS - Complexity checker works correctly")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL - {e}")

    # Test 6: Rule evaluation (passing)
    tests_total += 1
    print("\n[Test 6] Rule Evaluation (Passing)")
    try:
        # Create fresh engine with one rule
        engine2 = CustomQualityRulesEngine()
        rule = CustomQualityRule(
            rule_id="has_class",
            project_id="eval_test",
            rule_type="pattern",
            description="Check for class",
            severity="critical",
            checker=lambda code: "class" in code,
            weight=1.0,
            enabled=True,
        )
        await engine2.register_rule("eval_test", rule)

        result = await engine2.evaluate_rules("eval_test", "class MyClass:\n    pass")

        assert result["custom_score"] == 1.0
        assert result["rules_evaluated"] == 1
        assert len(result["violations"]) == 0
        print(f"   ✅ PASS - Score: {result['custom_score']:.2f}")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL - {e}")

    # Test 7: Rule evaluation (failing)
    tests_total += 1
    print("\n[Test 7] Rule Evaluation (Failing)")
    try:
        result = await engine2.evaluate_rules("eval_test", "def my_func():\n    pass")

        assert result["custom_score"] == 0.0
        assert len(result["violations"]) == 1
        print(
            f"   ✅ PASS - Score: {result['custom_score']:.2f}, Violations: {len(result['violations'])}"
        )
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL - {e}")

    # Test 8: Weighted scoring
    tests_total += 1
    print("\n[Test 8] Weighted Scoring")
    try:
        engine3 = CustomQualityRulesEngine()

        # Rule 1: Weight 0.7, passes
        rule1 = CustomQualityRule(
            rule_id="heavy_pass",
            project_id="weighted",
            rule_type="pattern",
            description="Heavy rule (passes)",
            severity="critical",
            checker=lambda code: True,
            weight=0.7,
            enabled=True,
        )

        # Rule 2: Weight 0.3, fails
        rule2 = CustomQualityRule(
            rule_id="light_fail",
            project_id="weighted",
            rule_type="pattern",
            description="Light rule (fails)",
            severity="warning",
            checker=lambda code: False,
            weight=0.3,
            enabled=True,
        )

        await engine3.register_rule("weighted", rule1)
        await engine3.register_rule("weighted", rule2)

        result = await engine3.evaluate_rules("weighted", "test")

        assert result["custom_score"] == 0.7
        assert result["total_weight"] == 1.0
        assert result["passed_weight"] == 0.7
        print(f"   ✅ PASS - Score: {result['custom_score']:.2f} (expected 0.70)")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL - {e}")

    # Test 9: Severity categorization
    tests_total += 1
    print("\n[Test 9] Severity Categorization")
    try:
        engine4 = CustomQualityRulesEngine()

        # Critical severity
        rule_critical = CustomQualityRule(
            rule_id="critical",
            project_id="severity",
            rule_type="pattern",
            description="Critical rule",
            severity="critical",
            checker=lambda code: False,
            weight=0.3,
            enabled=True,
        )

        # Warning severity
        rule_warning = CustomQualityRule(
            rule_id="warning",
            project_id="severity",
            rule_type="pattern",
            description="Warning rule",
            severity="warning",
            checker=lambda code: False,
            weight=0.2,
            enabled=True,
        )

        # Suggestion severity
        rule_suggestion = CustomQualityRule(
            rule_id="suggestion",
            project_id="severity",
            rule_type="pattern",
            description="Suggestion rule",
            severity="suggestion",
            checker=lambda code: False,
            weight=0.1,
            enabled=True,
        )

        await engine4.register_rule("severity", rule_critical)
        await engine4.register_rule("severity", rule_warning)
        await engine4.register_rule("severity", rule_suggestion)

        result = await engine4.evaluate_rules("severity", "test")

        assert len(result["violations"]) == 1
        assert len(result["warnings"]) == 1
        assert len(result["suggestions"]) == 1
        print(
            f"   ✅ PASS - Violations: {len(result['violations'])}, Warnings: {len(result['warnings'])}, Suggestions: {len(result['suggestions'])}"
        )
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL - {e}")

    # Test 10: YAML loading (if config exists)
    tests_total += 1
    print("\n[Test 10] YAML Configuration Loading")
    try:
        config_path = (
            Path(__file__).parent.parent.parent.parent
            / "config"
            / "quality_rules"
            / "omniclaude.yaml"
        )

        if config_path.exists():
            engine5 = CustomQualityRulesEngine()
            await engine5.load_project_rules("omniclaude", config_path)

            rules = await engine5.get_project_rules("omniclaude")
            print(f"   ✅ PASS - Loaded {len(rules)} rules from {config_path.name}")
            tests_passed += 1
        else:
            print(f"   ⚠️  SKIP - Config not found: {config_path}")
            tests_total -= 1
    except Exception as e:
        print(f"   ❌ FAIL - {e}")

    # Summary
    print("\n" + "=" * 70)
    print(f"Test Results: {tests_passed}/{tests_total} passed")
    if tests_passed == tests_total:
        print("✅ ALL TESTS PASSED!")
    else:
        print(f"❌ {tests_total - tests_passed} test(s) failed")
    print("=" * 70)

    return tests_passed == tests_total


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
