# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for individual dimension scoring.

This module tests the computation of individual quality dimensions:
    - Type coverage and patterns
    - Documentation quality
    - Complexity metrics
    - Maintainability scoring
    - ONEX pattern detection
"""

from __future__ import annotations

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    score_code_quality,
)


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
