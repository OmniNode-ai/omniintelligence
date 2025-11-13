"""
Tests for Custom Quality Rules Engine

Test coverage:
- Rule registration and loading
- Pattern, metric, and architectural rule types
- Severity levels and weighted scoring
- YAML configuration parsing
- Rule checker functions
- Error handling and edge cases

Created: 2025-10-15
Purpose: MVP Phase 5B - Quality Intelligence Upgrades
"""

from pathlib import Path

import pytest
from archon_services.quality.custom_rules import (
    CustomQualityRule,
    CustomQualityRulesEngine,
)

# ============================================================================
# Sample Code Fixtures
# ============================================================================


@pytest.fixture
def sample_onex_node_code() -> str:
    """Sample ONEX node code that passes most rules."""
    return """
from omnibase.protocols import NodeBase
from omnibase.models import ModelContractEffect

class NodeExampleEffect(NodeBase):
    '''Example ONEX effect node.'''

    async def execute_effect(self, contract: ModelContractEffect) -> Dict[str, Any]:
        '''Execute effect operation.

        Args:
            contract: Effect contract with operation parameters

        Returns:
            Result dictionary with operation outcome
        '''
        try:
            # Input validation
            if not contract:
                raise ValueError("Contract required")

            # Effect logic
            result = await self._process_effect(contract)

            return {
                "status": "success",
                "result": result
            }
        except Exception as e:
            logger.error(f"Effect execution failed: {e}")
            raise

    async def _process_effect(self, contract: ModelContractEffect) -> Any:
        '''Process effect operation.'''
        return {"processed": True}
"""


@pytest.fixture
def sample_legacy_code() -> str:
    """Sample code with legacy patterns."""
    return """
from typing import Any

class example_class:  # Non-CamelCase
    def process(self, data: Any):  # Any type usage
        result = data.dict()  # Pydantic v1
        return result
"""


@pytest.fixture
def sample_complex_code() -> str:
    """Sample code with high complexity."""
    return """
def complex_function(a, b, c, d, e):
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        return True
    elif a < 0:
        if b < 0:
            if c < 0:
                return False
    else:
        return None
    return False
"""


@pytest.fixture
def sample_yaml_config(tmp_path: Path) -> Path:
    """Create sample YAML configuration file."""
    config_content = """
project_id: test_project
description: Test project configuration

custom_rules:
  - rule_id: "require_node_base"
    description: "Must inherit from NodeBase"
    rule_type: "architectural"
    severity: "critical"
    pattern: "class.*Node.*NodeBase"
    weight: 0.2
    enabled: true

  - rule_id: "forbid_any_types"
    description: "Any types forbidden"
    rule_type: "pattern"
    severity: "critical"
    forbids: ":\\\\s*Any\\\\b"
    weight: 0.15
    enabled: true

  - rule_id: "max_function_complexity"
    description: "Complexity < 10"
    rule_type: "metric"
    severity: "warning"
    max_complexity: 10
    weight: 0.1
    enabled: true

  - rule_id: "min_docstring_coverage"
    description: "70% docstring coverage"
    rule_type: "metric"
    severity: "suggestion"
    min_docstring_coverage: 0.7
    weight: 0.08
    enabled: true
"""
    config_file = tmp_path / "test_rules.yaml"
    config_file.write_text(config_content)
    return config_file


# ============================================================================
# CustomQualityRulesEngine Tests
# ============================================================================


class TestCustomQualityRulesEngine:
    """Test suite for CustomQualityRulesEngine."""

    @pytest.fixture
    def engine(self) -> CustomQualityRulesEngine:
        """Create engine instance."""
        return CustomQualityRulesEngine()

    # ------------------------------------------------------------------------
    # Initialization Tests
    # ------------------------------------------------------------------------

    def test_engine_initialization(self, engine: CustomQualityRulesEngine):
        """Test engine initializes correctly."""
        assert engine.rules == {}
        assert len(engine.rule_checkers) > 0
        assert "pattern_match" in engine.rule_checkers
        assert "max_function_complexity" in engine.rule_checkers

    # ------------------------------------------------------------------------
    # Rule Registration Tests
    # ------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_register_rule(self, engine: CustomQualityRulesEngine):
        """Test rule registration."""
        rule = CustomQualityRule(
            rule_id="test_rule",
            project_id="test_project",
            rule_type="pattern",
            description="Test rule",
            severity="warning",
            checker=lambda code: True,
            weight=0.1,
            enabled=True,
        )

        await engine.register_rule("test_project", rule)

        assert "test_project" in engine.rules
        assert len(engine.rules["test_project"]) == 1
        assert engine.rules["test_project"][0].rule_id == "test_rule"

    @pytest.mark.asyncio
    async def test_register_multiple_rules(self, engine: CustomQualityRulesEngine):
        """Test registering multiple rules."""
        for i in range(3):
            rule = CustomQualityRule(
                rule_id=f"test_rule_{i}",
                project_id="test_project",
                rule_type="pattern",
                description=f"Test rule {i}",
                severity="warning",
                checker=lambda code: True,
                weight=0.1,
                enabled=True,
            )
            await engine.register_rule("test_project", rule)

        assert len(engine.rules["test_project"]) == 3

    # ------------------------------------------------------------------------
    # Rule Evaluation Tests
    # ------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_evaluate_rules_all_passing(
        self, engine: CustomQualityRulesEngine, sample_onex_node_code: str
    ):
        """Test evaluation with all rules passing."""
        # Register passing rules
        rule1 = CustomQualityRule(
            rule_id="has_class",
            project_id="test",
            rule_type="pattern",
            description="Has class definition",
            severity="critical",
            checker=lambda code: "class" in code,
            weight=0.5,
            enabled=True,
        )

        rule2 = CustomQualityRule(
            rule_id="has_async",
            project_id="test",
            rule_type="pattern",
            description="Has async def",
            severity="warning",
            checker=lambda code: "async def" in code,
            weight=0.3,
            enabled=True,
        )

        await engine.register_rule("test", rule1)
        await engine.register_rule("test", rule2)

        result = await engine.evaluate_rules("test", sample_onex_node_code)

        assert result["custom_score"] == pytest.approx(1.0, abs=1e-9)
        assert result["rules_evaluated"] == 2
        assert len(result["violations"]) == 0
        assert len(result["warnings"]) == 0

    @pytest.mark.asyncio
    async def test_evaluate_rules_with_violations(
        self, engine: CustomQualityRulesEngine, sample_legacy_code: str
    ):
        """Test evaluation with violations."""
        # Register rule that will fail
        rule = CustomQualityRule(
            rule_id="forbid_any",
            project_id="test",
            rule_type="pattern",
            description="No Any types",
            severity="critical",
            checker=lambda code: "Any" not in code,
            weight=0.5,
            enabled=True,
        )

        await engine.register_rule("test", rule)

        result = await engine.evaluate_rules("test", sample_legacy_code)

        assert result["custom_score"] == pytest.approx(
            0.0, abs=1e-9
        )  # Failed critical rule
        assert result["rules_evaluated"] == 1
        assert len(result["violations"]) == 1
        assert result["violations"][0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_evaluate_rules_weighted_scoring(
        self, engine: CustomQualityRulesEngine
    ):
        """Test weighted scoring calculation."""
        # Register rules with different weights
        rule1 = CustomQualityRule(
            rule_id="rule1",
            project_id="test",
            rule_type="pattern",
            description="Rule 1",
            severity="critical",
            checker=lambda code: True,  # Passes
            weight=0.6,
            enabled=True,
        )

        rule2 = CustomQualityRule(
            rule_id="rule2",
            project_id="test",
            rule_type="pattern",
            description="Rule 2",
            severity="warning",
            checker=lambda code: False,  # Fails
            weight=0.4,
            enabled=True,
        )

        await engine.register_rule("test", rule1)
        await engine.register_rule("test", rule2)

        result = await engine.evaluate_rules("test", "test code")

        # Only rule1 passes (0.6 out of 1.0)
        assert result["custom_score"] == pytest.approx(0.6, abs=1e-6)
        assert result["total_weight"] == pytest.approx(1.0, abs=1e-9)
        assert result["passed_weight"] == pytest.approx(0.6, abs=1e-6)

    @pytest.mark.asyncio
    async def test_evaluate_rules_severity_categorization(
        self, engine: CustomQualityRulesEngine
    ):
        """Test severity categorization."""
        # Critical rule (fails)
        rule1 = CustomQualityRule(
            rule_id="critical_rule",
            project_id="test",
            rule_type="pattern",
            description="Critical",
            severity="critical",
            checker=lambda code: False,
            weight=0.3,
            enabled=True,
        )

        # Warning rule (fails)
        rule2 = CustomQualityRule(
            rule_id="warning_rule",
            project_id="test",
            rule_type="pattern",
            description="Warning",
            severity="warning",
            checker=lambda code: False,
            weight=0.2,
            enabled=True,
        )

        # Suggestion rule (fails)
        rule3 = CustomQualityRule(
            rule_id="suggestion_rule",
            project_id="test",
            rule_type="pattern",
            description="Suggestion",
            severity="suggestion",
            checker=lambda code: False,
            weight=0.1,
            enabled=True,
        )

        await engine.register_rule("test", rule1)
        await engine.register_rule("test", rule2)
        await engine.register_rule("test", rule3)

        result = await engine.evaluate_rules("test", "test code")

        assert len(result["violations"]) == 1  # Critical
        assert len(result["warnings"]) == 1  # Warning
        assert len(result["suggestions"]) == 1  # Suggestion

    # ------------------------------------------------------------------------
    # YAML Configuration Tests
    # ------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_load_project_rules_from_yaml(
        self, engine: CustomQualityRulesEngine, sample_yaml_config: Path
    ):
        """Test loading rules from YAML configuration."""
        await engine.load_project_rules("test_project", sample_yaml_config)

        rules = await engine.get_project_rules("test_project")

        assert len(rules) == 4
        rule_ids = [r.rule_id for r in rules]
        assert "require_node_base" in rule_ids
        assert "forbid_any_types" in rule_ids
        assert "max_function_complexity" in rule_ids

    @pytest.mark.asyncio
    async def test_yaml_rule_configuration(
        self,
        engine: CustomQualityRulesEngine,
        sample_yaml_config: Path,
        sample_onex_node_code: str,
    ):
        """Test YAML-configured rules evaluation."""
        await engine.load_project_rules("test_project", sample_yaml_config)

        result = await engine.evaluate_rules("test_project", sample_onex_node_code)

        # Should pass NodeBase and docstring rules
        assert result["custom_score"] > 0.5

    # ------------------------------------------------------------------------
    # Pattern Checker Tests
    # ------------------------------------------------------------------------

    def test_pattern_checker_matches(self, engine: CustomQualityRulesEngine):
        """Test pattern matching checker."""
        checker = engine._create_pattern_checker(r"class\s+\w+")

        assert checker("class MyClass:") is True
        assert checker("def my_function():") is False

    def test_forbid_pattern_checker(self, engine: CustomQualityRulesEngine):
        """Test pattern forbidding checker."""
        checker = engine._create_forbid_pattern_checker(r":\s*Any\b")

        assert checker("def func(x: int):") is True
        assert checker("def func(x: Any):") is False

    # ------------------------------------------------------------------------
    # Complexity Checker Tests
    # ------------------------------------------------------------------------

    def test_complexity_checker(
        self, engine: CustomQualityRulesEngine, sample_complex_code: str
    ):
        """Test complexity checker."""
        checker = engine._create_complexity_checker(max_complexity=5)

        # Simple code passes
        simple_code = "def simple():\n    return True"
        assert checker(simple_code) is True

        # Complex code fails
        assert checker(sample_complex_code) is False

    # ------------------------------------------------------------------------
    # Length Checker Tests
    # ------------------------------------------------------------------------

    def test_length_checker(self, engine: CustomQualityRulesEngine):
        """Test function length checker."""
        checker = engine._create_length_checker(max_length=5)

        # Short function passes
        short_code = """
def short():
    x = 1
    y = 2
    return x + y
"""
        assert checker(short_code) is True

        # Long function fails
        long_code = """
def long():
    line1 = 1
    line2 = 2
    line3 = 3
    line4 = 4
    line5 = 5
    line6 = 6
    return sum
"""
        assert checker(long_code) is False

    # ------------------------------------------------------------------------
    # Docstring Coverage Tests
    # ------------------------------------------------------------------------

    def test_docstring_checker(self, engine: CustomQualityRulesEngine):
        """Test docstring coverage checker."""
        checker = engine._create_docstring_checker(min_coverage=0.7)

        # Good coverage passes
        good_code = """
def func1():
    '''Docstring.'''
    pass

def func2():
    '''Docstring.'''
    pass

def func3():
    pass
"""
        # 2 out of 3 = 66% (fails 70% threshold)
        assert checker(good_code) is False

        # Better coverage passes
        better_code = """
def func1():
    '''Docstring.'''
    pass

def func2():
    '''Docstring.'''
    pass
"""
        # 2 out of 2 = 100% (passes 70% threshold)
        assert checker(better_code) is True

    # ------------------------------------------------------------------------
    # Inheritance Checker Tests
    # ------------------------------------------------------------------------

    def test_inheritance_checker(self, engine: CustomQualityRulesEngine):
        """Test inheritance checker."""
        checker = engine._create_inheritance_checker("NodeBase")

        code_with_base = "class MyNode(NodeBase):\n    pass"
        code_without_base = "class MyClass:\n    pass"

        assert checker(code_with_base) is True
        assert checker(code_without_base) is False

    # ------------------------------------------------------------------------
    # Rule Management Tests
    # ------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_disable_rule(self, engine: CustomQualityRulesEngine):
        """Test rule disabling."""
        rule = CustomQualityRule(
            rule_id="test_rule",
            project_id="test",
            rule_type="pattern",
            description="Test",
            severity="warning",
            checker=lambda code: True,
            weight=0.1,
            enabled=True,
        )

        await engine.register_rule("test", rule)

        # Disable rule
        result = await engine.disable_rule("test", "test_rule")

        assert result is True
        rules = await engine.get_project_rules("test")
        assert rules[0].enabled is False

    @pytest.mark.asyncio
    async def test_enable_rule(self, engine: CustomQualityRulesEngine):
        """Test rule enabling."""
        rule = CustomQualityRule(
            rule_id="test_rule",
            project_id="test",
            rule_type="pattern",
            description="Test",
            severity="warning",
            checker=lambda code: True,
            weight=0.1,
            enabled=False,
        )

        await engine.register_rule("test", rule)

        # Enable rule
        result = await engine.enable_rule("test", "test_rule")

        assert result is True
        rules = await engine.get_project_rules("test")
        assert rules[0].enabled is True

    @pytest.mark.asyncio
    async def test_disabled_rules_not_evaluated(self, engine: CustomQualityRulesEngine):
        """Test that disabled rules are not evaluated."""
        rule = CustomQualityRule(
            rule_id="test_rule",
            project_id="test",
            rule_type="pattern",
            description="Test",
            severity="critical",
            checker=lambda code: False,  # Would fail if evaluated
            weight=0.5,
            enabled=False,
        )

        await engine.register_rule("test", rule)

        result = await engine.evaluate_rules("test", "test code")

        # Rule disabled, so score should be 1.0 (no rules evaluated)
        assert result["custom_score"] == pytest.approx(1.0, abs=1e-9)
        assert result["rules_evaluated"] == 0

    # ------------------------------------------------------------------------
    # Error Handling Tests
    # ------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_evaluate_nonexistent_project(self, engine: CustomQualityRulesEngine):
        """Test evaluation with nonexistent project."""
        result = await engine.evaluate_rules("nonexistent_project", "test code")

        # No rules for project, should return perfect score
        assert result["custom_score"] == pytest.approx(1.0, abs=1e-9)
        assert result["rules_evaluated"] == 0

    @pytest.mark.asyncio
    async def test_load_nonexistent_config(self, engine: CustomQualityRulesEngine):
        """Test loading nonexistent config file."""
        # Should not raise, just log error
        await engine.load_project_rules("test", Path("/nonexistent/path/config.yaml"))

        # No rules loaded
        rules = await engine.get_project_rules("test")
        assert len(rules) == 0

    @pytest.mark.asyncio
    async def test_rule_checker_exception_handling(
        self, engine: CustomQualityRulesEngine
    ):
        """Test handling of checker exceptions."""

        def failing_checker(code: str) -> bool:
            raise ValueError("Checker error")

        rule = CustomQualityRule(
            rule_id="failing_rule",
            project_id="test",
            rule_type="pattern",
            description="Failing rule",
            severity="critical",
            checker=failing_checker,
            weight=0.5,
            enabled=True,
        )

        await engine.register_rule("test", rule)

        # Should not raise, should handle gracefully
        result = await engine.evaluate_rules("test", "test code")

        # Failed checker should not contribute to score
        assert result["custom_score"] == pytest.approx(0.0, abs=1e-9)
        assert result["rules_evaluated"] == 1


# ============================================================================
# Integration Tests
# ============================================================================


class TestCustomRulesIntegration:
    """Integration tests for custom rules with real configurations."""

    @pytest.mark.asyncio
    async def test_omniclaude_rules_with_compliant_code(
        self, sample_onex_node_code: str
    ):
        """Test omniclaude rules with ONEX-compliant code."""
        engine = CustomQualityRulesEngine()

        # Load omniclaude rules
        config_path = Path(
            "/Volumes/PRO-G40/Code/omniarchon/config/quality_rules/omniclaude.yaml"
        )

        if config_path.exists():
            await engine.load_project_rules("omniclaude", config_path)

            result = await engine.evaluate_rules("omniclaude", sample_onex_node_code)

            # Should pass most rules
            assert result["custom_score"] > 0.6
            print(f"Custom Score: {result['custom_score']:.2f}")
            print(f"Violations: {len(result['violations'])}")
            print(f"Warnings: {len(result['warnings'])}")

    @pytest.mark.asyncio
    async def test_omniclaude_rules_with_legacy_code(self, sample_legacy_code: str):
        """Test omniclaude rules with legacy code."""
        engine = CustomQualityRulesEngine()

        config_path = Path(
            "/Volumes/PRO-G40/Code/omniarchon/config/quality_rules/omniclaude.yaml"
        )

        if config_path.exists():
            await engine.load_project_rules("omniclaude", config_path)

            result = await engine.evaluate_rules("omniclaude", sample_legacy_code)

            # Should have violations
            assert result["custom_score"] < 0.5
            assert len(result["violations"]) > 0

            print(f"Custom Score: {result['custom_score']:.2f}")
            for violation in result["violations"]:
                print(f"  - {violation['description']}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
