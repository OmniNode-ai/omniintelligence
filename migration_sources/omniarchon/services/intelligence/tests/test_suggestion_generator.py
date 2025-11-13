"""
Tests for Quality Suggestion Generator

Tests the intelligent suggestion generation system for code quality improvements.

Created: 2025-10-15
Purpose: Comprehensive testing of QualitySuggestionGenerator
"""

import pytest
from archon_services.quality.suggestion_generator import (
    QualitySuggestionGenerator,
)


@pytest.fixture
def generator():
    """Create suggestion generator instance"""
    return QualitySuggestionGenerator()


@pytest.mark.asyncio
class TestViolationMapping:
    """Test violation-to-suggestion mapping"""

    async def test_pydantic_v1_dict_violation(self, generator):
        """Test suggestion for .dict() legacy pattern"""
        validation_result = {
            "quality_score": 0.6,
            "onex_compliance_score": 0.5,
            "violations": ["Legacy Pydantic v1 .dict() method (use .model_dump())"],
            "warnings": [],
        }

        code = "data = model.dict()"
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        assert len(suggestions) > 0
        assert any("model_dump" in s["title"].lower() for s in suggestions)
        assert any(s["priority"] >= 8 for s in suggestions)

    async def test_any_type_violation(self, generator):
        """Test suggestion for Any type usage"""
        validation_result = {
            "quality_score": 0.5,
            "onex_compliance_score": 0.4,
            "violations": ["Uses Any types (forbidden in ONEX)"],
            "warnings": [],
        }

        code = "def process(data: Any) -> Any:\n    pass"
        suggestions = await generator.generate_suggestions(
            validation_result, code, "compute"
        )

        assert len(suggestions) > 0
        any_suggestion = next(
            (s for s in suggestions if "any type" in s["title"].lower()), None
        )
        assert any_suggestion is not None
        assert any_suggestion["priority"] == 10
        assert any_suggestion["type"] == "quality"

    async def test_naming_convention_violation(self, generator):
        """Test suggestion for naming convention issues"""
        validation_result = {
            "quality_score": 0.7,
            "onex_compliance_score": 0.6,
            "violations": ["Non-CamelCase Pydantic models (should be Model* prefix)"],
            "warnings": [],
        }

        code = "class user_config(BaseModel):\n    pass"
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        assert len(suggestions) > 0
        naming_suggestion = next(
            (s for s in suggestions if "camelcase" in s["title"].lower()), None
        )
        assert naming_suggestion is not None
        assert "ModelUserConfig" in naming_suggestion["code_example"]

    async def test_registry_injection_violation(self, generator):
        """Test suggestion for direct instantiation"""
        validation_result = {
            "quality_score": 0.6,
            "onex_compliance_score": 0.5,
            "violations": ["Direct instantiation without container"],
            "warnings": [],
        }

        code = "def __init__(self):\n    self.db = Database()"
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        assert len(suggestions) > 0
        injection_suggestion = next(
            (s for s in suggestions if "registry" in s["title"].lower()), None
        )
        assert injection_suggestion is not None
        assert injection_suggestion["priority"] >= 7


@pytest.mark.asyncio
class TestQualityImprovements:
    """Test quality improvement suggestions"""

    async def test_missing_error_handling(self, generator):
        """Test suggestion for missing error handling"""
        validation_result = {
            "quality_score": 0.65,
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

        error_handling = next(
            (s for s in suggestions if "error handling" in s["title"].lower()), None
        )
        assert error_handling is not None
        assert "try" in error_handling["code_example"]
        assert "except" in error_handling["code_example"]

    async def test_missing_type_hints(self, generator):
        """Test suggestion for missing type hints"""
        validation_result = {
            "quality_score": 0.7,
            "onex_compliance_score": 0.8,
            "violations": [],
            "warnings": [],
        }

        code = """
def process_data(input_data):
    return {"result": input_data}
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "compute"
        )

        type_hint_suggestion = next(
            (s for s in suggestions if "type hint" in s["title"].lower()), None
        )
        assert type_hint_suggestion is not None
        assert "->" in type_hint_suggestion["code_example"]

    async def test_missing_docstrings(self, generator):
        """Test suggestion for missing documentation"""
        validation_result = {
            "quality_score": 0.72,
            "onex_compliance_score": 0.8,
            "violations": [],
            "warnings": [],
        }

        code = """
class MyNode:
    def process(self, data):
        return data
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        doc_suggestion = next(
            (s for s in suggestions if "docstring" in s["title"].lower()), None
        )
        assert doc_suggestion is not None
        assert '"""' in doc_suggestion["code_example"]

    async def test_missing_logging(self, generator):
        """Test suggestion for missing logging"""
        validation_result = {
            "quality_score": 0.75,
            "onex_compliance_score": 0.8,
            "violations": [],
            "warnings": [],
        }

        code = """
def process_data(input_data):
    result = compute(input_data)
    return result
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        logging_suggestion = next(
            (s for s in suggestions if "logging" in s["title"].lower()), None
        )
        assert logging_suggestion is not None
        assert "logger" in logging_suggestion["code_example"]


@pytest.mark.asyncio
class TestONEXCompliance:
    """Test ONEX compliance suggestions"""

    async def test_missing_registry_injection(self, generator):
        """Test suggestion for missing registry"""
        validation_result = {
            "quality_score": 0.8,
            "onex_compliance_score": 0.65,
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

        registry_suggestion = next(
            (s for s in suggestions if "registry" in s["title"].lower()), None
        )
        assert registry_suggestion is not None
        assert "BaseOnexRegistry" in registry_suggestion["code_example"]

    async def test_missing_onex_error(self, generator):
        """Test suggestion for missing OnexError"""
        validation_result = {
            "quality_score": 0.8,
            "onex_compliance_score": 0.7,
            "violations": [],
            "warnings": [],
        }

        code = """
def process():
    if error:
        raise Exception("Something went wrong")
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        error_suggestion = next(
            (s for s in suggestions if "onexerror" in s["title"].lower()), None
        )
        assert error_suggestion is not None
        assert "OnexError" in error_suggestion["code_example"]
        assert "CoreErrorCode" in error_suggestion["code_example"]

    async def test_missing_structured_logging(self, generator):
        """Test suggestion for ONEX structured logging"""
        validation_result = {
            "quality_score": 0.85,
            "onex_compliance_score": 0.75,
            "violations": [],
            "warnings": [],
        }

        code = """
def process():
    logger.info("Processing started")
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # Should suggest emit_log_event
        log_suggestion = next(
            (s for s in suggestions if "emit_log_event" in s["title"].lower()), None
        )
        assert log_suggestion is not None
        assert "emit_log_event" in log_suggestion["code_example"]


@pytest.mark.asyncio
class TestNodeTypeSpecific:
    """Test node type specific suggestions"""

    async def test_effect_node_requirements(self, generator):
        """Test Effect node specific suggestions"""
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
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # Should suggest execute_effect method
        method_suggestion = next(
            (s for s in suggestions if "execute_effect" in s["title"].lower()), None
        )
        assert method_suggestion is not None
        assert method_suggestion["priority"] >= 8

        # Should suggest NodeEffect base class
        base_suggestion = next(
            (s for s in suggestions if "nodeeffect" in s["title"].lower()), None
        )
        assert base_suggestion is not None

    async def test_compute_node_requirements(self, generator):
        """Test Compute node specific suggestions"""
        validation_result = {
            "quality_score": 0.9,
            "onex_compliance_score": 0.9,
            "violations": [],
            "warnings": [],
        }

        code = """
class MyNode:
    pass
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "compute"
        )

        # Should suggest execute_compute or run_compute
        method_suggestion = next(
            (
                s
                for s in suggestions
                if "execute_compute" in s["title"].lower()
                or "run_compute" in s["title"].lower()
            ),
            None,
        )
        assert method_suggestion is not None

    async def test_orchestrator_mixins(self, generator):
        """Test Orchestrator node mixin suggestions"""
        validation_result = {
            "quality_score": 0.9,
            "onex_compliance_score": 0.9,
            "violations": [],
            "warnings": [],
        }

        code = """
class MyOrchestrator(NodeOrchestrator):
    async def execute_orchestration(self, data):
        return data
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "orchestrator"
        )

        # Should suggest EventBusMixin or WorkflowMixin
        mixin_suggestions = [s for s in suggestions if "mixin" in s["title"].lower()]
        assert len(mixin_suggestions) > 0


@pytest.mark.asyncio
class TestSuggestionFormatting:
    """Test suggestion formatting and prioritization"""

    async def test_priority_sorting(self, generator):
        """Test suggestions are sorted by priority"""
        validation_result = {
            "quality_score": 0.6,
            "onex_compliance_score": 0.5,
            "violations": [
                "Uses Any types (forbidden in ONEX)",
                "Legacy Pydantic v1 .dict() method (use .model_dump())",
            ],
            "warnings": ["Code uses outdated architectural patterns"],
        }

        code = """
def process(data: Any) -> Any:
    result = model.dict()
    return result
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # Verify sorted by priority (descending)
        priorities = [s["priority"] for s in suggestions]
        assert priorities == sorted(priorities, reverse=True)

    async def test_no_duplicate_suggestions(self, generator):
        """Test deduplication of suggestions"""
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
        assert len(titles) == len(set(titles))

    async def test_high_quality_code_minimal_suggestions(self, generator):
        """Test high quality code generates few suggestions"""
        validation_result = {
            "quality_score": 0.95,
            "onex_compliance_score": 0.95,
            "violations": [],
            "warnings": [],
        }

        code = """
class NodeMyEffect(NodeEffect):
    def __init__(self, registry: BaseOnexRegistry):
        super().__init__(registry)

    async def execute_effect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        '''Process data with effect logic'''
        try:
            result = await self.process(data)
            self.emit_log_event('info', 'Processing complete')
            return result
        except Exception as e:
            raise OnexError(CoreErrorCode.PROCESSING_FAILED) from e
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # High quality code should have minimal suggestions
        # (maybe just optional mixin suggestions)
        assert len(suggestions) <= 5

    async def test_suggestion_has_code_examples(self, generator):
        """Test critical suggestions include code examples"""
        validation_result = {
            "quality_score": 0.5,
            "onex_compliance_score": 0.4,
            "violations": ["Legacy Pydantic v1 .dict() method (use .model_dump())"],
            "warnings": [],
        }

        code = "data = model.dict()"
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # High priority suggestions should have code examples
        high_priority = [s for s in suggestions if s["priority"] >= 8]
        assert len(high_priority) > 0
        assert all(s.get("code_example") is not None for s in high_priority)


@pytest.mark.asyncio
class TestComplexScenarios:
    """Test complex real-world scenarios"""

    async def test_multiple_issues_comprehensive_suggestions(self, generator):
        """Test code with multiple issues gets comprehensive suggestions"""
        validation_result = {
            "quality_score": 0.55,
            "onex_compliance_score": 0.45,
            "violations": [
                "Uses Any types (forbidden in ONEX)",
                "Direct instantiation without container",
            ],
            "warnings": ["Code uses outdated architectural patterns"],
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

        # Should have multiple suggestions covering different issues
        assert len(suggestions) >= 5

        # Should cover different types
        types = {s["type"] for s in suggestions}
        assert len(types) >= 2  # Multiple suggestion types

        # Should have high priority items
        assert any(s["priority"] >= 8 for s in suggestions)

    async def test_legacy_code_modernization_path(self, generator):
        """Test legacy code gets clear modernization suggestions"""
        validation_result = {
            "quality_score": 0.4,
            "onex_compliance_score": 0.3,
            "violations": [
                "Legacy Pydantic v1 .dict() method (use .model_dump())",
                "Legacy @validator decorator (use @field_validator)",
            ],
            "warnings": ["Code uses outdated architectural patterns (pre_nodebase)"],
        }

        code = """
from pydantic import BaseModel, validator

class user_config(BaseModel):
    name: str

    @validator('name')
    def validate_name(cls, v):
        return v

    def to_dict(self):
        return self.dict()
"""
        suggestions = await generator.generate_suggestions(
            validation_result, code, "effect"
        )

        # Should prioritize Pydantic v2 migration
        pydantic_suggestions = [
            s
            for s in suggestions
            if "pydantic" in s["title"].lower() or "validator" in s["title"].lower()
        ]
        assert len(pydantic_suggestions) >= 2

        # Should suggest architectural improvements
        arch_suggestions = [s for s in suggestions if s["type"] == "architectural"]
        assert len(arch_suggestions) > 0
