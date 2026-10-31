# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for enhanced architectural scoring dimension.

This module tests the architectural scoring dimension:
    - Module exports (__all__)
    - Import organization
    - Handler pattern detection
    - Class organization
    - Inheritance patterns
"""

from __future__ import annotations

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    HandlerQualityScoring,
    ModelScoreCodeQualityRequest,
)


class TestArchitecturalScoring:
    """Tests for enhanced architectural scoring dimension."""

    def test_all_exports_improves_score(self) -> None:
        """Modules with __all__ exports should score better architecturally."""
        with_all = '''
"""Module with proper exports."""

def public_function() -> int:
    """A public function."""
    return 42

__all__ = ["public_function"]
'''
        without_all = '''
"""Module without exports."""

def public_function() -> int:
    """A public function."""
    return 42
'''
        result_with = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=with_all, language="python")
        )
        result_without = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=without_all, language="python")
        )

        # Module with __all__ should score better on architectural dimension
        assert (
            result_with["dimensions"]["architectural"]
            >= result_without["dimensions"]["architectural"]
        )

    def test_imports_inside_functions_penalized(self) -> None:
        """Imports inside functions (circular import risk) should be penalized."""
        clean_imports = '''
"""Clean module with imports at top."""
import os
import sys

def process() -> str:
    return os.getcwd()
'''
        circular_risk = '''
"""Module with import inside function."""

def process() -> str:
    import os  # Import inside function
    return os.getcwd()
'''
        result_clean = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=clean_imports, language="python")
        )
        result_risky = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=circular_risk, language="python")
        )

        # Imports inside functions should lower architectural score
        assert (
            result_clean["dimensions"]["architectural"]
            > result_risky["dimensions"]["architectural"]
        )

    def test_import_grouping_bonus(self) -> None:
        """Properly grouped imports should receive a bonus."""
        grouped_imports = '''
"""Module with grouped imports."""
import os
import sys

from pydantic import BaseModel

from mypackage import utils
'''
        ungrouped_imports = '''
"""Module with interleaved imports."""
import os
from pydantic import BaseModel
import sys
from mypackage import utils
import json
'''
        result_grouped = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=grouped_imports, language="python")
        )
        result_ungrouped = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=ungrouped_imports, language="python")
        )

        # Grouped imports should score better
        assert (
            result_grouped["dimensions"]["architectural"]
            >= result_ungrouped["dimensions"]["architectural"]
        )

    def test_handler_pattern_detection(self) -> None:
        """Handler pattern (private typed functions) should be rewarded."""
        handler_pattern = '''
"""Module following handler pattern."""

def _compute_score(data: dict) -> float:
    """Compute score from data."""
    return 0.5

def _validate_input(value: str) -> bool:
    """Validate input value."""
    return len(value) > 0

def _transform_result(raw: list) -> dict:
    """Transform raw result."""
    return {"items": raw}
'''
        no_handler_pattern = '''
"""Module without handler pattern."""

def compute_score(data):
    return 0.5

def validate_input(value):
    return len(value) > 0
'''
        result_handler = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=handler_pattern, language="python")
        )
        result_no_handler = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=no_handler_pattern, language="python")
        )

        # Handler pattern should score better on architectural dimension
        assert (
            result_handler["dimensions"]["architectural"]
            >= result_no_handler["dimensions"]["architectural"]
        )

    def test_class_organization_matters(self) -> None:
        """Proper class organization (ClassVar at top) should score better."""
        well_organized = '''
"""Well organized class."""
from typing import ClassVar

class Model:
    """Model class."""
    VERSION: ClassVar[str] = "1.0"
    model_config = {"frozen": True}

    def process(self) -> int:
        return 42
'''
        poorly_organized = '''
"""Poorly organized class."""
from typing import ClassVar

class Model:
    """Model class."""
    def process(self) -> int:
        return 42

    VERSION: ClassVar[str] = "1.0"
    model_config = {"frozen": True}
'''
        result_good = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=well_organized, language="python")
        )
        result_bad = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=poorly_organized, language="python")
        )

        # Well organized class should score better
        assert (
            result_good["dimensions"]["architectural"]
            >= result_bad["dimensions"]["architectural"]
        )

    def test_multiple_inheritance_still_penalized(self) -> None:
        """Multiple inheritance should still be penalized (existing check preserved)."""
        single_inheritance = '''
class Child(Parent):
    """Single inheritance."""
    pass
'''
        multiple_inheritance = '''
class Child(Parent1, Parent2, Mixin):
    """Multiple inheritance."""
    pass
'''
        result_single = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=single_inheritance, language="python")
        )
        result_multiple = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(
                content=multiple_inheritance, language="python"
            )
        )

        # Multiple inheritance should lower score
        assert (
            result_single["dimensions"]["architectural"]
            > result_multiple["dimensions"]["architectural"]
        )

    def test_import_after_code_still_penalized(self) -> None:
        """Imports after code should still be penalized (existing check preserved)."""
        imports_at_top = '''
"""Module docstring."""
import os
import sys

x = 1
'''
        imports_after_code = '''
"""Module docstring."""
x = 1

import os
import sys
'''
        result_top = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=imports_at_top, language="python")
        )
        result_after = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=imports_after_code, language="python")
        )

        # Imports at top should score better
        assert (
            result_top["dimensions"]["architectural"]
            > result_after["dimensions"]["architectural"]
        )

    def test_comprehensive_architectural_score(self) -> None:
        """Test comprehensive architectural scoring with all factors."""
        excellent_architecture = '''
"""Module with excellent architecture."""
from __future__ import annotations

import ast
import re
from typing import Final

from pydantic import BaseModel

__all__ = ["process_data", "DataModel"]

MAX_SIZE: Final[int] = 100

class DataModel(BaseModel):
    """Data model with proper structure."""
    name: str
    value: int

    model_config = {"frozen": True}

def process_data(data: DataModel) -> dict:
    """Process the data model."""
    return {"name": data.name}

def _validate_input(value: str) -> bool:
    """Validate input internally."""
    return len(value) > 0

def _transform_output(raw: dict) -> list:
    """Transform output internally."""
    return list(raw.keys())
'''
        poor_architecture = """
def public_func():
    import os
    result = {}
    return result

class Multi(Base1, Base2, Base3):
    def method(self):
        import json
        return json.dumps({})

x = 1
import sys
"""
        result_excellent = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(
                content=excellent_architecture, language="python"
            )
        )
        result_poor = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=poor_architecture, language="python")
        )

        # Excellent architecture should score significantly higher
        assert (
            result_excellent["dimensions"]["architectural"]
            > result_poor["dimensions"]["architectural"]
        )
        # The gap should be substantial given all the architectural issues in poor code
        assert (
            result_excellent["dimensions"]["architectural"]
            - result_poor["dimensions"]["architectural"]
        ) >= 0.2

    def test_simple_module_default_score(self) -> None:
        """Simple modules without classes should get reasonable default score."""
        simple_module = '''
"""Simple module."""
x = 1
y = 2
'''
        result = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=simple_module, language="python")
        )

        # Simple module should get the default architectural score or better
        assert result["dimensions"]["architectural"] >= 0.5

    def test_architectural_constants_are_defined(self) -> None:
        """New architectural constants should be properly defined."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            CLASS_ORGANIZATION_PENALTY,
            HANDLER_PATTERN_BONUS,
            IMPORT_GROUPING_BONUS,
            IMPORTS_INSIDE_FUNCTION_PENALTY,
            MISSING_ALL_EXPORTS_PENALTY,
        )

        # Verify constants exist and have reasonable values
        assert 0.0 < MISSING_ALL_EXPORTS_PENALTY < 1.0
        assert 0.0 < IMPORTS_INSIDE_FUNCTION_PENALTY < 1.0
        assert 0.0 < IMPORT_GROUPING_BONUS < 1.0
        assert 0.0 < HANDLER_PATTERN_BONUS < 1.0
        assert 0.0 < CLASS_ORGANIZATION_PENALTY < 1.0
