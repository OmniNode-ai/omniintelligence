# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for quality_scoring_compute handlers.

This module provides comprehensive unit tests for the score_code_quality
handler function and its supporting dimension scoring logic.

Test Categories:
    - TestScoreCodeQuality: Main function interface tests
    - TestDimensionScoring: Individual dimension computation tests
    - TestRecommendations: Recommendation generation tests
    - TestWeightValidation: Weight configuration validation tests
    - TestEdgeCases: Edge case and boundary condition tests
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.quality_scoring_compute.handlers import (
    ANALYSIS_VERSION,
    DEFAULT_WEIGHTS,
    QualityScoringResult,
    score_code_quality,
)
from omniintelligence.nodes.quality_scoring_compute.handlers.exceptions import (
    QualityScoringValidationError,
)


class TestScoreCodeQuality:
    """Tests for the main score_code_quality function."""

    def test_scores_valid_python_code(self) -> None:
        """Test scoring well-formed Python code returns complete result."""
        code = '''
class ModelExample(BaseModel):
    """A well-documented model."""
    name: str = Field(..., description="Name field")
    value: int = Field(default=0)

    model_config = {"frozen": True, "extra": "forbid"}
'''
        result = score_code_quality(code, "python")

        assert result["success"] is True
        assert 0.0 <= result["quality_score"] <= 1.0
        assert "complexity" in result["dimensions"]
        assert "maintainability" in result["dimensions"]
        assert "documentation" in result["dimensions"]
        assert "temporal_relevance" in result["dimensions"]
        assert "patterns" in result["dimensions"]
        assert "architectural" in result["dimensions"]
        assert result["source_language"] == "python"
        assert result["analysis_version"] == ANALYSIS_VERSION

    def test_high_score_for_onex_compliant_code(self) -> None:
        """ONEX-compliant code should score well on patterns dimension."""
        onex_code = '''
from typing import TypedDict, ClassVar, Final
from pydantic import BaseModel, Field, field_validator

class ResponseProtocol(TypedDict):
    """Protocol for response structure."""
    success: bool
    data: dict[str, str]

class ModelConfig(BaseModel):
    """Frozen ONEX-compliant model."""
    value: str = Field(..., min_length=1)

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: str) -> str:
        """Validate and normalize value."""
        return v.strip()
'''
        result = score_code_quality(onex_code, "python")

        assert result["dimensions"]["patterns"] >= 0.7
        # High quality code should be ONEX compliant with default threshold
        assert result["quality_score"] >= 0.6

    def test_low_score_for_antipatterns(self) -> None:
        """Code with ONEX antipatterns should score lower on patterns."""
        bad_code = '''
def process(data, **kwargs):
    result = {}
    for k, v in data.items():
        result[k] = v
    return result
'''
        result = score_code_quality(bad_code, "python")

        # Untyped functions with mutable defaults and **kwargs
        assert result["dimensions"]["patterns"] < 0.7
        # Anti-patterns should lower patterns score (replaces old type_coverage check)
        assert result["dimensions"]["documentation"] < 0.7

    def test_custom_weights_affect_score(self) -> None:
        """Test that custom weights affect the final score."""
        code = "def hello(): pass"

        # Weight heavily on documentation (which this lacks)
        doc_weights = {
            "complexity": 0.05,
            "maintainability": 0.05,
            "documentation": 0.70,
            "temporal_relevance": 0.05,
            "patterns": 0.05,
            "architectural": 0.10,
        }
        result_doc = score_code_quality(code, "python", weights=doc_weights)

        # Weight heavily on complexity (simple code should score well)
        complexity_weights = {
            "complexity": 0.70,
            "maintainability": 0.05,
            "documentation": 0.05,
            "temporal_relevance": 0.05,
            "patterns": 0.05,
            "architectural": 0.10,
        }
        result_complexity = score_code_quality(code, "python", weights=complexity_weights)

        # Complexity-weighted should be higher than doc-weighted for this simple code
        assert result_complexity["quality_score"] > result_doc["quality_score"]

    def test_onex_threshold_affects_compliance(self) -> None:
        """Test ONEX compliance threshold determination."""
        medium_code = '''
class Example:
    """Example class with basic structure."""
    def __init__(self, value: str) -> None:
        self.value = value
'''
        # Low threshold - should pass
        result_low = score_code_quality(medium_code, "python", onex_threshold=0.3)

        # High threshold - should fail
        result_high = score_code_quality(medium_code, "python", onex_threshold=0.95)

        # Same dimension scores for both
        assert result_low["dimensions"]["patterns"] == result_high["dimensions"]["patterns"]

        # Different compliance results based on threshold
        assert result_low["onex_compliant"] is True or result_low["quality_score"] < 0.3
        assert result_high["onex_compliant"] is False or result_high["quality_score"] >= 0.95

    def test_handles_syntax_error_gracefully(self) -> None:
        """Malformed Python should not crash, returns low baseline scores."""
        bad_syntax = "def broken( class while:"

        result = score_code_quality(bad_syntax, "python")

        assert result["success"] is True  # Does not crash
        assert result["quality_score"] >= 0.0
        assert result["onex_compliant"] is False
        # Syntax error code gets baseline low scores (0.3) for all dimensions
        # that depend on AST parsing
        assert result["quality_score"] <= 0.5

    def test_unsupported_language_baseline_scores(self) -> None:
        """Unsupported languages should return baseline scores."""
        code = 'fn main() { println!("Hello"); }'

        result = score_code_quality(code, "rust")

        assert result["success"] is True
        assert result["source_language"] == "rust"
        assert result["quality_score"] == 0.5  # Baseline
        # All dimensions should be baseline
        for dim_score in result["dimensions"].values():
            assert dim_score == 0.5
        # Should have unsupported language recommendation
        assert any("unsupported" in r.lower() for r in result["recommendations"])

    def test_empty_content_raises_validation_error(self) -> None:
        """Empty or whitespace content should raise QualityScoringValidationError."""
        with pytest.raises(QualityScoringValidationError, match="empty"):
            score_code_quality("", "python")

        with pytest.raises(QualityScoringValidationError, match="empty"):
            score_code_quality("   \n\t  ", "python")

    def test_returns_typed_dict_structure(self) -> None:
        """Result should match QualityScoringResult TypedDict structure."""
        result = score_code_quality("x = 1", "python")

        # Verify all required keys present
        expected_keys = {
            "success",
            "quality_score",
            "dimensions",
            "onex_compliant",
            "recommendations",
            "source_language",
            "analysis_version",
        }
        assert set(result.keys()) == expected_keys

    def test_scores_are_bounded(self) -> None:
        """All scores should be in valid range [0.0, 1.0]."""
        test_cases = [
            "x = 1",
            "def foo(): pass",
            """
class Large:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
""",
        ]

        for code in test_cases:
            result = score_code_quality(code, "python")

            assert 0.0 <= result["quality_score"] <= 1.0
            for dim, score in result["dimensions"].items():
                assert 0.0 <= score <= 1.0, f"Dimension {dim} out of bounds: {score}"


class TestDimensionScoring:
    """Tests for individual dimension scoring."""

    def test_typed_functions_improve_patterns_score(self) -> None:
        """Functions with type hints align better with ONEX patterns."""
        typed = '''
def process(data: dict[str, int]) -> list[str]:
    """Process data dictionary."""
    return list(data.keys())
'''
        untyped = '''
def process(data, **kwargs):
    result = []
    return result
'''
        result_typed = score_code_quality(typed, "python")
        result_untyped = score_code_quality(untyped, "python")

        # Typed code with docstrings should score better on patterns than code with antipatterns
        assert (
            result_typed["dimensions"]["patterns"]
            >= result_untyped["dimensions"]["patterns"]
        )

    def test_documentation_quality_varies_with_docstrings(self) -> None:
        """Documentation quality should vary based on docstring presence."""
        fully_documented = '''
def process(data: dict[str, int], limit: int) -> list[str]:
    """Process data with limit.

    Args:
        data: Input dictionary.
        limit: Maximum items to return.

    Returns:
        List of keys from data.
    """
    return list(data.keys())[:limit]
'''
        partial_documented = '''
def process(data: dict[str, int], limit: int) -> list[str]:
    """Process data."""
    return list(data.keys())[:limit]
'''
        undocumented = '''
def process(data, limit):
    return list(data.keys())[:limit]
'''
        result_full = score_code_quality(fully_documented, "python")
        result_partial = score_code_quality(partial_documented, "python")
        result_none = score_code_quality(undocumented, "python")

        assert result_full["dimensions"]["documentation"] >= result_partial["dimensions"]["documentation"]
        assert result_partial["dimensions"]["documentation"] >= result_none["dimensions"]["documentation"]

    def test_documentation_detects_docstrings(self) -> None:
        """Code with docstrings should score higher on documentation."""
        documented = '''
def process(data: dict) -> list:
    """Process the input data.

    Args:
        data: Input dictionary to process.

    Returns:
        List of processed items.
    """
    return list(data.keys())
'''
        undocumented = '''
def process(data: dict) -> list:
    return list(data.keys())
'''
        result_doc = score_code_quality(documented, "python")
        result_undoc = score_code_quality(undocumented, "python")

        assert result_doc["dimensions"]["documentation"] > result_undoc["dimensions"]["documentation"]

    def test_documentation_class_and_module_docstrings(self) -> None:
        """Class and module docstrings should improve documentation score."""
        with_docstrings = '''
"""Module docstring for processing."""

class Processor:
    """A processor class for data operations."""

    def process(self, data: dict) -> list:
        """Process the data."""
        return list(data.keys())
'''
        without_docstrings = '''
class Processor:
    def process(self, data: dict) -> list:
        return list(data.keys())
'''
        result_with = score_code_quality(with_docstrings, "python")
        result_without = score_code_quality(without_docstrings, "python")

        assert result_with["dimensions"]["documentation"] > result_without["dimensions"]["documentation"]

    def test_complexity_rewards_simple_code(self) -> None:
        """Simple code should score better on complexity dimension."""
        simple = '''
def add(a: int, b: int) -> int:
    return a + b
'''
        complex_code = '''
def process(data):
    result = 0
    for item in data:
        if item > 0:
            if item < 100:
                for i in range(item):
                    if i % 2 == 0:
                        result += i
                    elif i % 3 == 0:
                        result -= i
                    else:
                        result *= 2
    return result
'''
        result_simple = score_code_quality(simple, "python")
        result_complex = score_code_quality(complex_code, "python")

        assert result_simple["dimensions"]["complexity"] > result_complex["dimensions"]["complexity"]

    def test_complexity_with_try_except(self) -> None:
        """Try-except blocks should add to complexity score."""
        without_try = '''
def simple(x: int) -> int:
    return x * 2
'''
        with_try = '''
def complex(x: int) -> int:
    try:
        result = x * 2
    except TypeError:
        result = 0
    except ValueError:
        result = -1
    return result
'''
        result_simple = score_code_quality(without_try, "python")
        result_with_try = score_code_quality(with_try, "python")

        # More exception handlers = higher complexity = lower complexity score
        assert result_simple["dimensions"]["complexity"] >= result_with_try["dimensions"]["complexity"]

    def test_maintainability_naming_conventions(self) -> None:
        """Proper naming conventions should improve maintainability score."""
        good_naming = '''
class UserAccount:
    """User account model."""

    def get_balance(self) -> float:
        """Get account balance."""
        return 0.0

    def _validate_amount(self, amount: float) -> bool:
        """Validate amount internally."""
        return amount > 0
'''
        bad_naming = '''
class user_account:
    def GetBalance(self):
        return 0.0

    def ValidateAmount(self, Amount):
        return Amount > 0
'''
        result_good = score_code_quality(good_naming, "python")
        result_bad = score_code_quality(bad_naming, "python")

        assert (
            result_good["dimensions"]["maintainability"]
            > result_bad["dimensions"]["maintainability"]
        )

    def test_patterns_detects_onex_patterns(self) -> None:
        """ONEX patterns should improve patterns dimension score."""
        with_patterns = '''
from typing import TypedDict, ClassVar, Final, Protocol
from pydantic import BaseModel, Field

class MyProtocol(Protocol):
    """Protocol for type checking."""
    def method(self) -> str: ...

class Config(TypedDict):
    """Configuration TypedDict."""
    name: str
    value: int

class Model(BaseModel):
    """Pydantic model with frozen config."""
    data: str = Field(..., min_length=1)
    VERSION: ClassVar[str] = "1.0.0"
    MAX_SIZE: Final[int] = 100

    model_config = {"frozen": True, "extra": "forbid"}
'''
        without_patterns = '''
class Model:
    def __init__(self):
        self.data = {}

def process(data, **kwargs):
    return dict(data)
'''
        result_with = score_code_quality(with_patterns, "python")
        result_without = score_code_quality(without_patterns, "python")

        assert result_with["dimensions"]["patterns"] > result_without["dimensions"]["patterns"]

    def test_patterns_penalizes_antipatterns(self) -> None:
        """ONEX anti-patterns should lower the patterns dimension score."""
        clean_code = '''
def process(data: dict[str, str]) -> list[str]:
    return list(data.values())
'''
        with_antipatterns = '''
from typing import Any

def process(data: dict[str, Any], **kwargs) -> list:
    result = []
    defaults = {}
    return result
'''
        result_clean = score_code_quality(clean_code, "python")
        result_antipatterns = score_code_quality(with_antipatterns, "python")

        assert result_clean["dimensions"]["patterns"] > result_antipatterns["dimensions"]["patterns"]


class TestRecommendations:
    """Tests for recommendation generation."""

    def test_generates_recommendations_for_low_scores(self) -> None:
        """Low dimension scores should generate relevant recommendations."""
        # Code lacking documentation
        no_docs = "def f(x): return x * 2"

        result = score_code_quality(no_docs, "python")

        assert len(result["recommendations"]) > 0

    def test_recommendations_are_strings(self) -> None:
        """All recommendations should be strings."""
        code = "x = 1"
        result = score_code_quality(code, "python")

        assert all(isinstance(r, str) for r in result["recommendations"])

    def test_recommendations_include_dimension_tags(self) -> None:
        """Recommendations should include dimension tags in brackets."""
        code = "def f(x): return x"  # Missing types, docs, patterns
        result = score_code_quality(code, "python")

        # Should have recommendations with dimension tags
        for rec in result["recommendations"]:
            # Each recommendation should start with [dimension_name]
            assert rec.startswith("[") and "]" in rec

    def test_syntax_error_produces_low_scores(self) -> None:
        """Syntax errors should produce low baseline scores due to AST parse failures."""
        bad_code = "def broken(:"
        result = score_code_quality(bad_code, "python")

        # Syntax error code gets baseline low scores for dimensions using AST
        # Each dimension that fails to parse returns 0.3
        assert result["success"] is True
        assert result["quality_score"] <= 0.5
        # Should have recommendations due to low scores
        assert len(result["recommendations"]) > 0

    def test_unsupported_language_recommendation(self) -> None:
        """Unsupported languages should produce unsupported_language recommendation."""
        result = score_code_quality("let x = 5;", "javascript")

        assert any("[unsupported_language]" in r for r in result["recommendations"])

    def test_high_quality_code_fewer_recommendations(self) -> None:
        """High quality code should have fewer recommendations."""
        high_quality = '''
"""Module for data processing."""
from typing import TypedDict, Final
from pydantic import BaseModel, Field

CONSTANT: Final[int] = 100

class DataInput(TypedDict):
    """Input data structure."""
    value: int
    name: str

class DataProcessor(BaseModel):
    """Processes data following ONEX patterns."""
    multiplier: int = Field(default=1, ge=1)

    model_config = {"frozen": True, "extra": "forbid"}

    def process(self, data: DataInput) -> int:
        """Process the input data.

        Args:
            data: Input data to process.

        Returns:
            Processed integer result.
        """
        return data["value"] * self.multiplier
'''
        low_quality = "def f(x, **kwargs): return x"

        result_high = score_code_quality(high_quality, "python")
        result_low = score_code_quality(low_quality, "python")

        assert len(result_high["recommendations"]) <= len(result_low["recommendations"])


class TestWeightValidation:
    """Tests for weight configuration validation."""

    def test_default_weights_sum_to_one(self) -> None:
        """DEFAULT_WEIGHTS should sum to 1.0."""
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_invalid_weight_keys_raise_error(self) -> None:
        """Weights with invalid keys should raise QualityScoringValidationError."""
        invalid_weights = {
            "complexity": 0.5,
            "maintainability": 0.5,
            # Missing: documentation, temporal_relevance, patterns, architectural
        }
        with pytest.raises(QualityScoringValidationError, match="[Mm]issing"):
            score_code_quality("x = 1", "python", weights=invalid_weights)

    def test_extra_weight_keys_raise_error(self) -> None:
        """Weights with extra keys should raise QualityScoringValidationError."""
        extra_weights = {
            "complexity": 0.15,
            "maintainability": 0.15,
            "documentation": 0.15,
            "temporal_relevance": 0.15,
            "patterns": 0.15,
            "architectural": 0.15,
            "extra_dimension": 0.10,  # Not a valid dimension
        }
        with pytest.raises(QualityScoringValidationError, match="[Ee]xtra"):
            score_code_quality("x = 1", "python", weights=extra_weights)

    def test_weights_not_summing_to_one_raise_error(self) -> None:
        """Weights not summing to 1.0 should raise QualityScoringValidationError."""
        bad_weights = {
            "complexity": 0.5,
            "maintainability": 0.5,
            "documentation": 0.5,
            "temporal_relevance": 0.5,
            "patterns": 0.5,
            "architectural": 0.5,  # Sum = 3.0
        }
        with pytest.raises(QualityScoringValidationError, match="sum"):
            score_code_quality("x = 1", "python", weights=bad_weights)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_character_code(self) -> None:
        """Single character valid Python should be scored."""
        result = score_code_quality("1", "python")
        assert result["success"] is True

    def test_only_comments(self) -> None:
        """Code with only comments should be scored."""
        code = """
# This is a comment
# Another comment
"""
        result = score_code_quality(code, "python")
        assert result["success"] is True

    def test_unicode_content(self) -> None:
        """Unicode content should be handled correctly."""
        code = '''
def greet(name: str) -> str:
    """Return greeting message."""
    return f"Hello, {name}!"
'''
        result = score_code_quality(code, "python")
        assert result["success"] is True

    def test_very_long_function(self) -> None:
        """Very long functions should get lower maintainability score."""
        # Generate a function with many lines
        long_func = "def long_func():\n" + "    x = 1\n" * 100 + "    return x"
        short_func = "def short_func():\n    return 1"

        result_long = score_code_quality(long_func, "python")
        result_short = score_code_quality(short_func, "python")

        assert (
            result_short["dimensions"]["maintainability"]
            > result_long["dimensions"]["maintainability"]
        )

    def test_deeply_nested_code(self) -> None:
        """Deeply nested code should score lower on complexity."""
        nested = '''
def deep():
    if True:
        for i in range(10):
            while True:
                if i > 5:
                    for j in range(5):
                        if j > 2:
                            return j
                break
'''
        flat = '''
def flat():
    return 42
'''
        result_nested = score_code_quality(nested, "python")
        result_flat = score_code_quality(flat, "python")

        assert result_flat["dimensions"]["complexity"] > result_nested["dimensions"]["complexity"]

    def test_async_functions(self) -> None:
        """Async functions should be scored correctly."""
        async_code = '''
async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    return {}
'''
        result = score_code_quality(async_code, "python")

        assert result["success"] is True
        # Async function should have reasonable complexity (simple code scores well)
        assert result["dimensions"]["complexity"] >= 0.8

    def test_class_methods(self) -> None:
        """Class methods should score well on maintainability."""
        code = '''
class Example:
    """Example class."""

    def instance_method(self, value: int) -> int:
        """Instance method."""
        return value * 2

    @classmethod
    def class_method(cls, value: int) -> int:
        """Class method."""
        return value * 3
'''
        result = score_code_quality(code, "python")

        # Well-named class with proper method conventions should score high on maintainability
        assert result["dimensions"]["maintainability"] >= 0.8

    def test_language_case_insensitive(self) -> None:
        """Language parameter should be case insensitive."""
        code = "x = 1"

        result_lower = score_code_quality(code, "python")
        result_upper = score_code_quality(code, "PYTHON")
        result_mixed = score_code_quality(code, "Python")

        assert result_lower["quality_score"] == result_upper["quality_score"]
        assert result_lower["quality_score"] == result_mixed["quality_score"]

    def test_py_alias_for_python(self) -> None:
        """'py' should be accepted as alias for 'python'."""
        code = "x = 1"

        result_py = score_code_quality(code, "py")
        result_python = score_code_quality(code, "python")

        # Both should be analyzed as Python, not unsupported
        assert result_py["source_language"] == "py"
        assert result_python["source_language"] == "python"
        # Should get same analysis (not baseline unsupported scores)
        assert "[unsupported_language]" not in str(result_py["recommendations"])
        assert "[unsupported_language]" not in str(result_python["recommendations"])

    def test_no_functions_high_temporal_relevance(self) -> None:
        """Code with no staleness indicators should get high temporal_relevance score."""
        code = '''
CONSTANT = 42
data = {"key": "value"}
'''
        result = score_code_quality(code, "python")

        # No TODO/FIXME/deprecated markers means high temporal relevance (1.0)
        assert result["dimensions"]["temporal_relevance"] == 1.0

    def test_multiple_classes(self) -> None:
        """Multiple classes should all be evaluated."""
        code = '''
class GoodClass:
    """Good naming."""
    pass

class another_class:
    pass

class AnotherGoodClass:
    """Another good class."""
    pass
'''
        result = score_code_quality(code, "python")

        # Mix of good and bad naming should result in moderate score
        assert 0.5 <= result["dimensions"]["maintainability"] <= 0.9

    def test_list_comprehensions_count_as_complexity(self) -> None:
        """List comprehensions should add to complexity score."""
        without_comprehension = '''
def simple(items: list) -> list:
    return items
'''
        with_comprehension = '''
def complex_comprehension(items: list) -> list:
    return [x for x in items if x > 0 for y in x if y != 0]
'''
        result_simple = score_code_quality(without_comprehension, "python")
        result_complex = score_code_quality(with_comprehension, "python")

        # Comprehensions add complexity
        assert result_simple["dimensions"]["complexity"] >= result_complex["dimensions"]["complexity"]
