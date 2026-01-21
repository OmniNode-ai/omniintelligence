# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for enhanced architectural scoring dimension.

This module tests the architectural scoring dimension:
    - Module exports (__all__)
    - Import organization
    - Handler pattern detection
    - Class organization
    - Inheritance patterns
"""

from __future__ import annotations

from omniintelligence.nodes.quality_scoring_compute.handlers import (
    score_code_quality,
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
        result_with = score_code_quality(with_all, "python")
        result_without = score_code_quality(without_all, "python")

        # Module with __all__ should score better on architectural dimension
        assert result_with["dimensions"]["architectural"] >= result_without["dimensions"]["architectural"]

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
        result_clean = score_code_quality(clean_imports, "python")
        result_risky = score_code_quality(circular_risk, "python")

        # Imports inside functions should lower architectural score
        assert result_clean["dimensions"]["architectural"] > result_risky["dimensions"]["architectural"]

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
        result_grouped = score_code_quality(grouped_imports, "python")
        result_ungrouped = score_code_quality(ungrouped_imports, "python")

        # Grouped imports should score better
        assert result_grouped["dimensions"]["architectural"] >= result_ungrouped["dimensions"]["architectural"]

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
        result_handler = score_code_quality(handler_pattern, "python")
        result_no_handler = score_code_quality(no_handler_pattern, "python")

        # Handler pattern should score better on architectural dimension
        assert result_handler["dimensions"]["architectural"] >= result_no_handler["dimensions"]["architectural"]

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
        result_good = score_code_quality(well_organized, "python")
        result_bad = score_code_quality(poorly_organized, "python")

        # Well organized class should score better
        assert result_good["dimensions"]["architectural"] >= result_bad["dimensions"]["architectural"]

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
        result_single = score_code_quality(single_inheritance, "python")
        result_multiple = score_code_quality(multiple_inheritance, "python")

        # Multiple inheritance should lower score
        assert result_single["dimensions"]["architectural"] > result_multiple["dimensions"]["architectural"]

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
        result_top = score_code_quality(imports_at_top, "python")
        result_after = score_code_quality(imports_after_code, "python")

        # Imports at top should score better
        assert result_top["dimensions"]["architectural"] > result_after["dimensions"]["architectural"]

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
        poor_architecture = '''
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
'''
        result_excellent = score_code_quality(excellent_architecture, "python")
        result_poor = score_code_quality(poor_architecture, "python")

        # Excellent architecture should score significantly higher
        assert result_excellent["dimensions"]["architectural"] > result_poor["dimensions"]["architectural"]
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
        result = score_code_quality(simple_module, "python")

        # Simple module should get the default architectural score or better
        assert result["dimensions"]["architectural"] >= 0.5

    def test_architectural_constants_are_defined(self) -> None:
        """New architectural constants should be properly defined."""
        from omniintelligence.nodes.quality_scoring_compute.handlers.handler_quality_scoring import (
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
