"""
Standalone tests for Quality Suggestion Generator

Tests that don't require external dependencies like omnibase_core.

Created: 2025-10-15
Purpose: Validate suggestion generator logic without full dependency stack
"""

import sys
from pathlib import Path

import pytest

# Import directly without going through __init__ to avoid dependency issues
from archon_services.quality.suggestion_generator import QualitySuggestionGenerator

# Add parent directory to path for imports


@pytest.fixture
def generator():
    """Create suggestion generator instance"""
    return QualitySuggestionGenerator()


@pytest.mark.asyncio
class TestSuggestionGeneratorCore:
    """Test core suggestion generator functionality"""

    async def test_generator_initialization(self, generator):
        """Test generator initializes correctly and can generate suggestions"""
        assert generator is not None
        assert hasattr(generator, "violation_patterns")
        assert hasattr(generator, "node_type_requirements")
        # Behavior test: verify generator has patterns loaded
        assert len(generator.violation_patterns) > 0
        # Behavior test: verify all expected node types are supported
        supported_node_types = ["effect", "compute", "reducer", "orchestrator"]
        for node_type in supported_node_types:
            assert node_type in generator.node_type_requirements

    async def test_violation_pattern_detection(self, generator):
        """Test violation pattern detection works"""
        validation_result = {
            "quality_score": 0.6,
            "onex_compliance_score": 0.5,
            "violations": ["Legacy Pydantic v1 .dict() method"],
            "warnings": [],
        }

        code = "data = model.dict()"
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # Should generate at least one suggestion
        assert len(suggestions) > 0

        # Should have proper structure
        for suggestion in suggestions:
            assert "type" in suggestion
            assert "priority" in suggestion
            assert "title" in suggestion
            assert "description" in suggestion
            assert "impact" in suggestion
            assert "effort" in suggestion

    async def test_priority_sorting(self, generator):
        """Test suggestions are properly sorted by priority"""
        validation_result = {
            "quality_score": 0.5,
            "onex_compliance_score": 0.4,
            "violations": [
                "Uses Any types (forbidden in ONEX)",
                "Non-CamelCase Pydantic models",
            ],
            "warnings": ["Code uses outdated patterns"],
        }

        code = """
class user_config(BaseModel):
    data: Any = None
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # Check priorities are descending
        priorities = [s["priority"] for s in suggestions]
        assert priorities == sorted(priorities, reverse=True)

    async def test_deduplication(self, generator):
        """Test duplicate suggestions are removed"""
        validation_result = {
            "quality_score": 0.6,
            "onex_compliance_score": 0.5,
            "violations": [
                "Uses Any types (forbidden in ONEX)",
                "Uses Any types (forbidden in ONEX)",  # Duplicate
            ],
            "warnings": [],
        }

        code = "def process(data: Any) -> Any:\n    pass"
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # Check no duplicate titles
        titles = [s["title"] for s in suggestions]
        assert len(titles) == len(set(titles)), "Found duplicate suggestion titles"

    async def test_node_type_specific_suggestions(self, generator):
        """Test node type specific suggestions are generated

        Behavior test: Each node type should receive relevant suggestions about
        implementing required methods and patterns (e.g., execute_effect, execute_compute).
        We verify suggestions are generated and contain node-type-specific guidance.
        """
        validation_result = {
            "quality_score": 0.9,
            "onex_compliance_score": 0.9,
            "violations": [],
            "warnings": [],
        }

        code = """
class MyNode:
    def __init__(self):
        pass
"""

        # Expected method patterns for each node type (behavior, not implementation)
        expected_patterns = {
            "effect": ["execute_effect", "effect"],
            "compute": ["execute_compute", "compute"],
            "reducer": ["execute_reduction", "reducer", "aggregate"],
            "orchestrator": ["execute_orchestration", "orchestrator", "workflow"],
        }

        # Test for each node type
        for node_type in ["effect", "compute", "reducer", "orchestrator"]:
            suggestions = await generator.generate_suggestions(
                validation_result, code, node_type
            )

            # Behavior test: Should receive suggestions for this node type
            assert len(suggestions) > 0, f"No suggestions generated for {node_type}"

            # Behavior test: Suggestions should contain node-type-specific guidance
            # Check if any suggestion mentions expected patterns for this node type
            all_text = " ".join(
                [
                    s["title"].lower() + " " + s["description"].lower()
                    for s in suggestions
                ]
            )

            has_node_specific_content = any(
                pattern in all_text for pattern in expected_patterns[node_type]
            )
            assert (
                has_node_specific_content
            ), f"Suggestions for {node_type} should contain node-type-specific guidance"

    async def test_quality_improvements_on_low_score(self, generator):
        """Test quality improvement suggestions for low scores"""
        validation_result = {
            "quality_score": 0.6,  # Low score
            "onex_compliance_score": 0.8,
            "violations": [],
            "warnings": [],
        }

        code = """
def process_data(input_data):
    result = risky_operation(input_data)
    return result
"""

        suggestions = await generator.generate_suggestions(
            validation_result, code, "compute"
        )

        # Should suggest error handling
        has_error_handling = any("error" in s["title"].lower() for s in suggestions)
        assert has_error_handling, "Missing error handling suggestion"

        # Should suggest type hints
        has_type_hints = any(
            "type" in s["title"].lower() or "hint" in s["title"].lower()
            for s in suggestions
        )
        assert has_type_hints, "Missing type hints suggestion"

    async def test_onex_compliance_improvements(self, generator):
        """Test ONEX compliance suggestions for low compliance"""
        validation_result = {
            "quality_score": 0.8,
            "onex_compliance_score": 0.6,  # Low compliance
            "violations": [],
            "warnings": [],
        }

        code = """
class MyNode:
    def __init__(self):
        self.service = MyService()
"""

        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # Should suggest registry injection
        has_registry = any("registry" in s["title"].lower() for s in suggestions)
        assert has_registry, "Missing registry injection suggestion"

    async def test_high_quality_minimal_suggestions(self, generator):
        """Test high quality code gets fewer suggestions than low quality code

        Behavior test: High-quality, compliant code should receive significantly fewer
        suggestions than low-quality code with violations. This verifies the generator
        properly recognizes code quality without coupling to exact suggestion counts.
        """
        # High quality code
        high_quality_validation = {
            "quality_score": 0.95,
            "onex_compliance_score": 0.95,
            "violations": [],
            "warnings": [],
        }

        high_quality_code = """
class NodeMyEffect(NodeEffect):
    def __init__(self, registry: BaseOnexRegistry):
        super().__init__(registry)
        self.service = registry.get(MyService)

    async def execute_effect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        '''Process data with effect logic'''
        try:
            result = await self.process(data)
            self.emit_log_event('info', 'Processing complete')
            return result
        except Exception as e:
            raise OnexError(CoreErrorCode.PROCESSING_FAILED) from e
"""

        high_quality_suggestions = await generator.generate_suggestions(
            high_quality_validation, high_quality_code, "effect"
        )

        # Low quality code for comparison
        low_quality_validation = {
            "quality_score": 0.5,
            "onex_compliance_score": 0.4,
            "violations": [
                "Uses Any types (forbidden in ONEX)",
                "Direct instantiation without container",
                "Legacy Pydantic v1 .dict() method",
            ],
            "warnings": ["Code uses outdated patterns"],
        }

        low_quality_code = """
class my_node:
    def __init__(self):
        self.db = Database()

    def process(data: Any):
        result = model.dict()
        return result
"""

        low_quality_suggestions = await generator.generate_suggestions(
            low_quality_validation, low_quality_code, "effect"
        )

        # Behavior test: High quality code should have significantly fewer suggestions
        assert len(high_quality_suggestions) < len(low_quality_suggestions), (
            f"High quality code ({len(high_quality_suggestions)} suggestions) should have "
            f"fewer suggestions than low quality code ({len(low_quality_suggestions)} suggestions)"
        )

        # Behavior test: High quality code should have mostly low-priority suggestions
        high_priority_count = sum(
            1 for s in high_quality_suggestions if s["priority"] >= 8
        )
        assert (
            high_priority_count == 0
        ), f"High quality code should not have high-priority suggestions, found {high_priority_count}"

    async def test_code_example_presence(self, generator):
        """Test high priority suggestions include code examples"""
        validation_result = {
            "quality_score": 0.5,
            "onex_compliance_score": 0.4,
            "violations": ["Legacy Pydantic v1 .dict() method"],
            "warnings": [],
        }

        code = "data = model.dict()"
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # High priority suggestions should have examples
        high_priority = [s for s in suggestions if s["priority"] >= 8]
        assert len(high_priority) > 0

        for suggestion in high_priority:
            assert (
                suggestion.get("code_example") is not None
            ), f"High priority suggestion '{suggestion['title']}' missing code example"

    async def test_multiple_violation_types(self, generator):
        """Test handling multiple violation types"""
        validation_result = {
            "quality_score": 0.5,
            "onex_compliance_score": 0.4,
            "violations": [
                "Uses Any types (forbidden in ONEX)",
                "Direct instantiation without container",
                "Legacy Pydantic v1 .dict() method",
            ],
            "warnings": ["Code uses outdated patterns"],
        }

        code = """
class my_node:
    def __init__(self):
        self.db = Database()

    def process(data: Any):
        result = model.dict()
        return result
"""

        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # Should have multiple suggestions
        assert len(suggestions) >= 3

        # Should cover different types
        types = {s["type"] for s in suggestions}
        assert len(types) >= 2, "Should have multiple suggestion types"


if __name__ == "__main__":
    # Allow running standalone
    pytest.main([__file__, "-v"])
