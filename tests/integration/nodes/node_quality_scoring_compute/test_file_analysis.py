# SPDX-License-Identifier: Apache-2.0
"""Integration tests for quality scoring compute node with real file analysis.

These tests verify that the quality scoring compute node correctly scores
actual Python files from the codebase, validating that:
1. Real production code receives expected quality scores
2. Source path handling works correctly
3. Known code patterns produce expected dimension scores

Test Organization:
    - TestRealFileAnalysis: Tests scoring actual codebase files
    - TestFilePathHandling: Tests for path handling in input/output
    - TestKnownCodePatterns: Tests verifying expected scores for known patterns
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from omniintelligence.nodes.node_quality_scoring_compute.models import (
    ModelQualityScoringInput,
)
from omniintelligence.nodes.node_quality_scoring_compute.node import (
    NodeQualityScoringCompute,
)

# Import centralized constants from conftest
from .conftest import (
    DOCSTRINGS_MIN_DOC_SCORE,
    DOCUMENTATION_MIN_SCORE,
    FROZEN_MODEL_MIN_PATTERNS_SCORE,
    HIGH_COMPLEXITY_MAX_SCORE,
    PRODUCTION_CODE_MIN_SCORE,
    SRC_BASE,
    TODO_MAX_TEMPORAL_SCORE,
    TYPEDDICT_MIN_PATTERNS_SCORE,
)

# =============================================================================
# Constants
# =============================================================================

# Node source files for testing
NODE_FILE: Final[Path] = (
    SRC_BASE / "omniintelligence" / "nodes" / "quality_scoring_compute" / "node.py"
)
HANDLER_FILE: Final[Path] = (
    SRC_BASE
    / "omniintelligence"
    / "nodes"
    / "quality_scoring_compute"
    / "handlers"
    / "handler_quality_scoring.py"
)
MODEL_INPUT_FILE: Final[Path] = (
    SRC_BASE
    / "omniintelligence"
    / "nodes"
    / "quality_scoring_compute"
    / "models"
    / "model_quality_scoring_input.py"
)


# =============================================================================
# Fixtures
# =============================================================================

# Note: onex_container and quality_scoring_node fixtures are provided by conftest.py


@pytest.fixture
def specific_test_files() -> list[Path]:
    """Return list of specific Python files for targeted batch testing.

    This fixture returns a small set of known files for consistent testing,
    unlike sample_python_files which collects up to 20 files dynamically.

    Returns:
        List of Path objects pointing to specific real Python files.
    """
    files = [NODE_FILE, HANDLER_FILE, MODEL_INPUT_FILE]
    # Filter to only files that exist (in case paths change)
    return [f for f in files if f.exists()]


@pytest.fixture
def code_with_frozen_model() -> str:
    """Sample code with frozen Pydantic model."""
    return '''"""Sample module with frozen Pydantic model."""

from pydantic import BaseModel, Field


class FrozenConfig(BaseModel):
    """A frozen configuration model."""

    name: str = Field(..., description="The configuration name")
    value: int = Field(default=0, description="The configuration value")

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["FrozenConfig"]
'''


@pytest.fixture
def code_with_typeddict() -> str:
    """Sample code using TypedDict."""
    return '''"""Sample module with TypedDict usage."""

from typing import TypedDict, Final


class UserInfo(TypedDict):
    """Typed dictionary for user information."""

    name: str
    email: str
    age: int


DEFAULT_USER: Final[UserInfo] = {"name": "", "email": "", "age": 0}


def process_user(user: UserInfo) -> str:
    """Process user information."""
    return f"{user['name']} <{user['email']}>"


__all__ = ["UserInfo", "process_user"]
'''


@pytest.fixture
def code_with_todo_comments() -> str:
    """Sample code with TODO/FIXME comments."""
    return '''"""Module with technical debt markers."""

# TODO: Refactor this function
def legacy_function(x: int) -> int:
    """A legacy function that needs updating."""
    # FIXME: This is a temporary hack
    result = x * 2
    # XXX: Need to handle edge cases
    return result


# HACK: This should be replaced
MAGIC_VALUE = 42
'''


@pytest.fixture
def code_with_docstrings() -> str:
    """Sample code with comprehensive docstrings."""
    return '''"""Module demonstrating good documentation practices.

This module provides examples of well-documented functions
following Google-style docstrings.
"""

from typing import Final


# Module-level constant
DEFAULT_MULTIPLIER: Final[int] = 2


def multiply(a: int, b: int) -> int:
    """Multiply two integers.

    Args:
        a: First integer operand.
        b: Second integer operand.

    Returns:
        The product of a and b.

    Example:
        >>> multiply(3, 4)
        12
    """
    return a * b


class Calculator:
    """A simple calculator class.

    This class provides basic arithmetic operations.

    Attributes:
        precision: Number of decimal places for results.
    """

    def __init__(self, precision: int = 2) -> None:
        """Initialize the calculator.

        Args:
            precision: Number of decimal places for results.
        """
        self.precision = precision

    def add(self, a: float, b: float) -> float:
        """Add two numbers.

        Args:
            a: First number.
            b: Second number.

        Returns:
            The sum rounded to the configured precision.
        """
        return round(a + b, self.precision)


__all__ = ["multiply", "Calculator", "DEFAULT_MULTIPLIER"]
'''


@pytest.fixture
def code_with_high_complexity() -> str:
    """Sample code with high cyclomatic complexity."""
    return '''"""Module with complex nested control flow."""


def complex_function(x: int, y: int, z: int) -> str:
    """A function with high cyclomatic complexity."""
    result = ""
    if x > 0:
        if y > 0:
            if z > 0:
                for i in range(x):
                    if i % 2 == 0:
                        if i > y:
                            result += "a"
                        else:
                            result += "b"
                    else:
                        try:
                            if z > i:
                                result += "c"
                            elif z < i:
                                result += "d"
                            else:
                                result += "e"
                        except ValueError:
                            result += "error"
            else:
                result = "z_not_positive"
        else:
            result = "y_not_positive"
    else:
        result = "x_not_positive"
    return result
'''


# =============================================================================
# Test Classes
# =============================================================================


@pytest.mark.integration
class TestRealFileAnalysis:
    """Integration tests scoring actual codebase files."""

    async def test_score_node_implementation_file(
        self, quality_scoring_node: NodeQualityScoringCompute
    ) -> None:
        """Score the quality_scoring_compute node.py file itself.

        The node implementation file should score well as it is production code
        following ONEX patterns.
        """
        if not NODE_FILE.exists():
            pytest.skip(f"Node file not found: {NODE_FILE}")

        content = NODE_FILE.read_text()
        input_data = ModelQualityScoringInput(
            source_path=str(NODE_FILE),
            content=content,
            language="python",
            project_name="omniintelligence",
        )

        result = await quality_scoring_node.compute(input_data)

        # Production code should succeed and score reasonably well
        assert result.success is True
        assert result.quality_score >= PRODUCTION_CODE_MIN_SCORE, (
            f"Node implementation scored {result.quality_score:.2f}, "
            f"expected >= {PRODUCTION_CODE_MIN_SCORE}"
        )

        # Verify dimensions exist and are within valid range
        assert result.dimensions is not None
        for dimension_name, score in result.dimensions.items():
            assert 0.0 <= score <= 1.0, (
                f"Dimension {dimension_name} score {score} out of range"
            )

        # Metadata should be populated
        assert result.metadata is not None
        assert result.metadata.status == "completed"
        assert result.metadata.source_language == "python"

    async def test_score_handler_file(
        self, quality_scoring_node: NodeQualityScoringCompute
    ) -> None:
        """Score the handler_quality_scoring.py file.

        The handler file contains pure functions with type hints and should
        score well on patterns and maintainability.
        """
        if not HANDLER_FILE.exists():
            pytest.skip(f"Handler file not found: {HANDLER_FILE}")

        content = HANDLER_FILE.read_text()
        input_data = ModelQualityScoringInput(
            source_path=str(HANDLER_FILE),
            content=content,
            language="python",
            project_name="omniintelligence",
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        assert result.quality_score >= PRODUCTION_CODE_MIN_SCORE, (
            f"Handler file scored {result.quality_score:.2f}, "
            f"expected >= {PRODUCTION_CODE_MIN_SCORE}"
        )

        # Handler files should have good documentation
        assert result.dimensions is not None
        assert result.dimensions["documentation"] >= DOCUMENTATION_MIN_SCORE, (
            f"Handler documentation score {result.dimensions['documentation']:.2f} "
            f"is below expected minimum {DOCUMENTATION_MIN_SCORE}"
        )

    async def test_score_model_file(
        self, quality_scoring_node: NodeQualityScoringCompute
    ) -> None:
        """Score a Pydantic model file.

        Model files should score well on patterns due to frozen models
        and type annotations.
        """
        if not MODEL_INPUT_FILE.exists():
            pytest.skip(f"Model file not found: {MODEL_INPUT_FILE}")

        content = MODEL_INPUT_FILE.read_text()
        input_data = ModelQualityScoringInput(
            source_path=str(MODEL_INPUT_FILE),
            content=content,
            language="python",
            project_name="omniintelligence",
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        assert result.quality_score >= PRODUCTION_CODE_MIN_SCORE

        # Model files with frozen=True should have good patterns score
        assert result.dimensions is not None
        # Pydantic models with frozen=True should score at least moderately on patterns
        assert result.dimensions["patterns"] >= TYPEDDICT_MIN_PATTERNS_SCORE, (
            f"Model patterns score {result.dimensions['patterns']:.2f} "
            f"lower than expected minimum {TYPEDDICT_MIN_PATTERNS_SCORE}"
        )

    async def test_batch_score_multiple_files(
        self,
        quality_scoring_node: NodeQualityScoringCompute,
        sample_python_files: list[Path],
    ) -> None:
        """Score multiple real files and verify consistency.

        All files should return valid outputs with consistent structure.
        """
        if not sample_python_files:
            pytest.skip("No sample Python files found")

        results = []
        for file_path in sample_python_files:
            content = file_path.read_text()
            input_data = ModelQualityScoringInput(
                source_path=str(file_path),
                content=content,
                language="python",
            )
            result = await quality_scoring_node.compute(input_data)
            results.append((file_path.name, result))

        # Verify all files scored successfully
        for filename, result in results:
            assert result.success is True, f"File {filename} failed scoring"
            assert 0.0 <= result.quality_score <= 1.0, (
                f"File {filename} score {result.quality_score} out of range"
            )
            assert result.dimensions is not None, f"File {filename} missing dimensions"
            assert result.metadata is not None, f"File {filename} missing metadata"

        # Verify consistent dimension structure across all results
        expected_dimensions = {
            "complexity",
            "maintainability",
            "documentation",
            "temporal_relevance",
            "patterns",
            "architectural",
        }
        for filename, result in results:
            actual_dimensions = set(result.dimensions.keys())
            assert actual_dimensions == expected_dimensions, (
                f"File {filename} has unexpected dimensions: {actual_dimensions}"
            )


@pytest.mark.integration
class TestFilePathHandling:
    """Tests for file path handling in scoring."""

    async def test_source_path_preserved_in_output(
        self, quality_scoring_node: NodeQualityScoringCompute
    ) -> None:
        """Verify source_path from input is accessible via input data.

        The source_path should be passed through the input model correctly.
        """
        test_path = "/test/example/sample.py"
        content = '''"""Test module."""

def hello() -> str:
    """Return greeting."""
    return "hello"


__all__ = ["hello"]
'''

        input_data = ModelQualityScoringInput(
            source_path=test_path,
            content=content,
            language="python",
        )

        # Verify source_path is set correctly in input
        assert input_data.source_path == test_path

        result = await quality_scoring_node.compute(input_data)

        # Result should succeed regardless of path
        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.status == "completed"

    async def test_relative_path_handling(
        self, quality_scoring_node: NodeQualityScoringCompute
    ) -> None:
        """Test scoring works with relative file paths."""
        relative_path = "src/module/file.py"
        content = '''"""Module with relative path."""

def example() -> int:
    """Return example value."""
    return 42
'''

        input_data = ModelQualityScoringInput(
            source_path=relative_path,
            content=content,
            language="python",
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        assert result.quality_score >= 0.0

    async def test_absolute_path_handling(
        self, quality_scoring_node: NodeQualityScoringCompute
    ) -> None:
        """Test scoring works with absolute file paths."""
        absolute_path = "/usr/local/lib/python/site-packages/module.py"
        content = '''"""Module with absolute path."""

from typing import Final

CONSTANT: Final[str] = "value"


def get_constant() -> str:
    """Return the constant value."""
    return CONSTANT


__all__ = ["CONSTANT", "get_constant"]
'''

        input_data = ModelQualityScoringInput(
            source_path=absolute_path,
            content=content,
            language="python",
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        assert result.quality_score >= 0.0
        assert result.metadata is not None


@pytest.mark.integration
class TestKnownCodePatterns:
    """Tests verifying expected scores for known code patterns."""

    async def test_frozen_pydantic_model_scores_well(
        self,
        quality_scoring_node: NodeQualityScoringCompute,
        code_with_frozen_model: str,
    ) -> None:
        """Test that frozen Pydantic models get high patterns score.

        Code with frozen=True, extra='forbid', and Field() should score
        well on the patterns dimension.
        """
        input_data = ModelQualityScoringInput(
            source_path="test/frozen_model.py",
            content=code_with_frozen_model,
            language="python",
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        assert result.dimensions is not None

        # Frozen models should score well on patterns
        patterns_score = result.dimensions["patterns"]
        assert patterns_score >= FROZEN_MODEL_MIN_PATTERNS_SCORE, (
            f"Frozen Pydantic model patterns score {patterns_score:.2f} "
            f"is below expected {FROZEN_MODEL_MIN_PATTERNS_SCORE}"
        )

    async def test_typeddict_usage_scores_well(
        self,
        quality_scoring_node: NodeQualityScoringCompute,
        code_with_typeddict: str,
    ) -> None:
        """Test that TypedDict usage increases patterns score.

        TypedDict is a positive ONEX pattern and should contribute
        to a higher patterns score.
        """
        input_data = ModelQualityScoringInput(
            source_path="test/typeddict_module.py",
            content=code_with_typeddict,
            language="python",
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        assert result.dimensions is not None

        # TypedDict usage should result in decent patterns score
        patterns_score = result.dimensions["patterns"]
        assert patterns_score >= TYPEDDICT_MIN_PATTERNS_SCORE, (
            f"TypedDict usage patterns score {patterns_score:.2f} "
            f"is below expected {TYPEDDICT_MIN_PATTERNS_SCORE}"
        )

    async def test_todo_comments_lower_temporal_score(
        self,
        quality_scoring_node: NodeQualityScoringCompute,
        code_with_todo_comments: str,
    ) -> None:
        """Test that TODO/FIXME comments lower temporal_relevance.

        Code with technical debt markers (TODO, FIXME, XXX, HACK)
        should have reduced temporal_relevance score.
        """
        input_data = ModelQualityScoringInput(
            source_path="test/legacy_module.py",
            content=code_with_todo_comments,
            language="python",
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        assert result.dimensions is not None

        # Multiple TODO/FIXME/XXX/HACK comments should reduce temporal score
        temporal_score = result.dimensions["temporal_relevance"]
        # 4 staleness indicators * 0.1 penalty each = 0.4 penalty
        # Expected: 1.0 - 0.4 = 0.6 or lower
        assert temporal_score <= TODO_MAX_TEMPORAL_SCORE, (
            f"Temporal relevance score {temporal_score:.2f} is too high "
            f"for code with multiple TODO/FIXME comments (max: {TODO_MAX_TEMPORAL_SCORE})"
        )

    async def test_docstrings_improve_documentation_score(
        self,
        quality_scoring_node: NodeQualityScoringCompute,
        code_with_docstrings: str,
    ) -> None:
        """Test that docstrings improve documentation dimension.

        Well-documented code with comprehensive docstrings should
        score highly on the documentation dimension.
        """
        input_data = ModelQualityScoringInput(
            source_path="test/documented_module.py",
            content=code_with_docstrings,
            language="python",
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        assert result.dimensions is not None

        # Good docstrings should result in high documentation score
        doc_score = result.dimensions["documentation"]
        assert doc_score >= DOCSTRINGS_MIN_DOC_SCORE, (
            f"Documentation score {doc_score:.2f} is below expected "
            f"{DOCSTRINGS_MIN_DOC_SCORE} for well-documented code"
        )

    async def test_complex_functions_lower_complexity_score(
        self,
        quality_scoring_node: NodeQualityScoringCompute,
        code_with_high_complexity: str,
    ) -> None:
        """Test that deeply nested code lowers complexity score.

        Code with high cyclomatic complexity (deeply nested if/for/try)
        should have a lower complexity score.
        """
        input_data = ModelQualityScoringInput(
            source_path="test/complex_module.py",
            content=code_with_high_complexity,
            language="python",
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        assert result.dimensions is not None

        # High complexity should result in lower complexity score
        complexity_score = result.dimensions["complexity"]
        assert complexity_score <= HIGH_COMPLEXITY_MAX_SCORE, (
            f"Complexity score {complexity_score:.2f} is too high "
            f"for deeply nested code (max: {HIGH_COMPLEXITY_MAX_SCORE})"
        )

    async def test_good_code_is_onex_compliant(
        self,
        quality_scoring_node: NodeQualityScoringCompute,
        code_with_frozen_model: str,
    ) -> None:
        """Test that well-structured code is marked ONEX compliant.

        Code following ONEX patterns (frozen models, proper documentation,
        type hints) should be marked as ONEX compliant.
        """
        input_data = ModelQualityScoringInput(
            source_path="test/compliant_module.py",
            content=code_with_frozen_model,
            language="python",
            onex_compliance_threshold=0.6,  # Use lower threshold for test
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        # With a 0.6 threshold, well-structured code should be compliant
        if result.quality_score >= 0.6:
            assert result.onex_compliant is True, (
                f"Code with score {result.quality_score:.2f} should be ONEX compliant "
                "with threshold 0.6"
            )

    async def test_anti_patterns_generate_recommendations(
        self, quality_scoring_node: NodeQualityScoringCompute
    ) -> None:
        """Test that code with issues generates improvement recommendations."""
        # Code with intentional issues
        poor_code = """def x(y):
    z = []
    for a in y:
        if a > 0:
            if a > 10:
                for b in range(a):
                    z.append(b)
    return z
"""

        input_data = ModelQualityScoringInput(
            source_path="test/poor_code.py",
            content=poor_code,
            language="python",
        )

        result = await quality_scoring_node.compute(input_data)

        assert result.success is True
        # Poor code should generate recommendations
        assert len(result.recommendations) > 0, (
            "Code with issues should generate recommendations"
        )
