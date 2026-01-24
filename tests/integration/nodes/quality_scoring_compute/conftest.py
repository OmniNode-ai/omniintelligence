# SPDX-License-Identifier: Apache-2.0
"""Fixtures for quality_scoring_compute integration tests.

This module provides pytest fixtures for testing the NodeQualityScoringCompute
node against real Python files from the codebase. Fixtures include:

- Path constants for project structure navigation
- Quality threshold constants for test assertions
- Real Python file collection from the codebase
- Node instantiation fixtures
- Code sample fixtures for quality level testing

Usage:
    @pytest.mark.integration
    def test_quality_scoring_on_real_files(
        quality_scoring_node: NodeQualityScoringCompute,
        sample_python_files: list[Path],
    ) -> None:
        for file_path in sample_python_files:
            content = file_path.read_text()
            # Create input and test...
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omniintelligence.nodes.quality_scoring_compute import NodeQualityScoringCompute


# =============================================================================
# Path Configuration
# =============================================================================

# Project root directory (relative to this test file)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent

# Nodes source directory for collecting real Python files
NODES_DIR = PROJECT_ROOT / "src" / "omniintelligence" / "nodes"


# =============================================================================
# Quality Threshold Constants
# =============================================================================

# Thresholds for production code quality assertions
PRODUCTION_CODE_MIN_SCORE: Final[float] = 0.6
DOCUMENTATION_MIN_SCORE: Final[float] = 0.5

# Thresholds for different quality levels
HIGH_QUALITY_MIN_SCORE: Final[float] = 0.6
LOW_QUALITY_MAX_SCORE: Final[float] = 0.7
MODERATE_QUALITY_MIN_SCORE: Final[float] = 0.4
MODERATE_QUALITY_MAX_SCORE: Final[float] = 0.85

# Performance thresholds (in milliseconds)
PROCESSING_TIME_NORMAL_MS: Final[float] = 500.0
PROCESSING_TIME_LARGE_MS: Final[float] = 2000.0


# =============================================================================
# Helper Functions
# =============================================================================


def _collect_python_files(base_dir: Path, limit: int = 20) -> list[Path]:
    """Collect Python files from a directory tree.

    Args:
        base_dir: Base directory to search
        limit: Maximum number of files to collect

    Returns:
        List of Python file paths, limited to avoid test slowdown
    """
    if not base_dir.exists():
        return []

    files: list[Path] = []
    for py_file in base_dir.rglob("*.py"):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file) or "test_" in py_file.name:
            continue
        # Skip empty files
        if py_file.stat().st_size == 0:
            continue
        files.append(py_file)
        if len(files) >= limit:
            break

    return sorted(files)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_python_files() -> list[Path]:
    """Collect real Python files from the codebase for testing.

    Collects Python files from the nodes directory, excluding test files
    and __pycache__ directories. Limited to 20 files to keep tests fast.

    Returns:
        List of Path objects pointing to real Python source files
    """
    return _collect_python_files(NODES_DIR, limit=20)


@pytest.fixture
def onex_container() -> ModelONEXContainer:
    """Create a test ONEX container instance."""
    return ModelONEXContainer()


@pytest.fixture
def quality_scoring_node(onex_container: ModelONEXContainer) -> NodeQualityScoringCompute:
    """Instantiate a NodeQualityScoringCompute node for testing.

    Args:
        onex_container: ONEX container fixture

    Returns:
        Configured NodeQualityScoringCompute instance
    """
    return NodeQualityScoringCompute(container=onex_container)


# =============================================================================
# Code Sample Fixtures
# =============================================================================


@pytest.fixture
def high_quality_onex_code() -> str:
    """ONEX-compliant code sample with proper patterns.

    Returns:
        High quality Python code demonstrating ONEX best practices.
    """
    return '''"""ONEX-compliant model with proper patterns.

This module demonstrates best practices for ONEX node development.
"""

from __future__ import annotations

from typing import ClassVar, Final

from pydantic import BaseModel, Field, field_validator


__all__ = ["UserModel", "create_user"]


class UserModel(BaseModel):
    """User model following ONEX patterns.

    Attributes:
        name: The user's display name.
        email: The user's email address.
        age: The user's age in years.
    """

    name: str = Field(..., min_length=1, description="User display name")
    email: str = Field(..., description="User email address")
    age: int = Field(..., ge=0, le=150, description="User age in years")

    model_config: ClassVar[dict[str, bool | str]] = {
        "frozen": True,
        "extra": "forbid",
    }

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()


def create_user(name: str, email: str, age: int) -> UserModel:
    """Create a new user instance.

    Args:
        name: The user's display name.
        email: The user's email address.
        age: The user's age in years.

    Returns:
        A validated UserModel instance.
    """
    return UserModel(name=name, email=email, age=age)
'''


@pytest.fixture
def low_quality_code() -> str:
    """Code sample with anti-patterns and poor quality.

    Returns:
        Low quality Python code with issues for testing.
    """
    return '''# TODO: Fix this later
# FIXME: Performance issues
# XXX: Deprecated approach

def BADFUNCTION(x, y, z, a, b, c, d, e, f, g, **kwargs):
    result = {}
    data = []
    if x:
        if y:
            if z:
                if a:
                    if b:
                        if c:
                            result["value"] = x + y + z
    for i in range(100):
        for j in range(100):
            for k in range(100):
                data.append(i + j + k)
    return result


class badclass:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
    def method4(self): pass
    def method5(self): pass
    model_config = {}
'''


@pytest.fixture
def moderate_quality_code() -> str:
    """Code sample with moderate quality.

    Returns:
        Average quality Python code for testing middle-range scores.
    """
    return '''"""A module with moderate code quality."""

from typing import Optional


class DataProcessor:
    """Process data with basic functionality."""

    def __init__(self, data: list) -> None:
        self.data = data

    def process(self) -> list:
        """Process the data and return results."""
        result = []
        for item in self.data:
            if item is not None:
                result.append(item * 2)
        return result

    def filter_data(self, threshold: int) -> list:
        """Filter data above threshold."""
        return [x for x in self.data if x and x > threshold]
'''
