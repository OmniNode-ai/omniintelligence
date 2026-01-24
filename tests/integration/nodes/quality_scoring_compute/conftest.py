# SPDX-License-Identifier: Apache-2.0
"""Fixtures for quality_scoring_compute integration tests.

This module provides pytest fixtures for testing the NodeQualityScoringCompute
node against real Python files from the codebase. Fixtures include:

- Path constants for project structure navigation
- Real Python file collection from the codebase
- Node instantiation fixtures
- Sample code fixtures for high/low quality testing
- Minimal valid input fixtures

Usage:
    @pytest.mark.integration
    def test_quality_scoring_on_real_files(
        quality_scoring_node: NodeQualityScoringCompute,
        sample_python_files: list[Path],
    ) -> None:
        for file_path in sample_python_files:
            content = file_path.read_text()
            input_data = ModelQualityScoringInput(
                source_path=str(file_path),
                content=content,
            )
            result = await quality_scoring_node.compute(input_data)
            assert result.success
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.nodes.quality_scoring_compute import NodeQualityScoringCompute
from omniintelligence.nodes.quality_scoring_compute.handlers import OnexStrictnessLevel
from omniintelligence.nodes.quality_scoring_compute.models import (
    ModelDimensionWeights,
    ModelQualityScoringInput,
)


# =============================================================================
# Path Configuration
# =============================================================================

# Project root directory (relative to this test file)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent

# Nodes source directory for collecting real Python files
NODES_DIR = PROJECT_ROOT / "src" / "omniintelligence" / "nodes"


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
def quality_scoring_node() -> NodeQualityScoringCompute:
    """Instantiate a NodeQualityScoringCompute node for testing.

    Returns:
        Configured NodeQualityScoringCompute instance
    """
    return NodeQualityScoringCompute()


@pytest.fixture
def high_quality_code() -> str:
    """ONEX-compliant high-quality code sample.

    This sample demonstrates best practices:
    - frozen=True and extra="forbid" on Pydantic models
    - TypedDict for typed dictionaries
    - Protocol for structural typing
    - Proper docstrings and type annotations
    - No TODO/FIXME comments
    - Proper naming conventions

    Returns:
        String containing high-quality Python code
    """
    return '''# SPDX-License-Identifier: Apache-2.0
"""High-quality module following ONEX patterns.

This module demonstrates ONEX-compliant code patterns including
frozen Pydantic models, TypedDict, Protocol, and proper documentation.
"""

from __future__ import annotations

from typing import Protocol, TypedDict

from pydantic import BaseModel, Field


class UserMetadata(TypedDict):
    """Metadata for user records.

    Attributes:
        created_at: ISO 8601 timestamp of user creation
        updated_at: ISO 8601 timestamp of last update
        version: Record version for optimistic locking
    """

    created_at: str
    updated_at: str
    version: int


class UserRepositoryProtocol(Protocol):
    """Protocol defining user repository operations.

    This protocol enables structural typing for user data access,
    allowing different implementations (SQL, NoSQL, in-memory) to
    be used interchangeably.
    """

    async def get_user(self, user_id: str) -> ModelUser | None:
        """Retrieve a user by ID.

        Args:
            user_id: Unique identifier for the user

        Returns:
            User model if found, None otherwise
        """
        ...

    async def save_user(self, user: ModelUser) -> bool:
        """Persist a user record.

        Args:
            user: User model to persist

        Returns:
            True if save succeeded, False otherwise
        """
        ...


class ModelUser(BaseModel):
    """Immutable user model following ONEX patterns.

    This model uses frozen=True for immutability and extra="forbid"
    to prevent undeclared fields, ensuring type safety at runtime.

    Attributes:
        user_id: Unique identifier for the user
        email: User's email address (validated format)
        display_name: Human-readable display name
        is_active: Whether the user account is active
    """

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the user",
    )
    email: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="User's email address",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable display name",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the user account is active",
    )

    model_config = {"frozen": True, "extra": "forbid"}


def calculate_user_score(user: ModelUser, metadata: UserMetadata) -> float:
    """Calculate a user engagement score.

    This pure function computes a score based on user attributes
    and metadata, following functional programming principles.

    Args:
        user: The user model to score
        metadata: Associated metadata for the user

    Returns:
        Engagement score between 0.0 and 1.0
    """
    base_score = 0.5 if user.is_active else 0.1
    version_bonus = min(metadata["version"] * 0.01, 0.3)
    return min(base_score + version_bonus, 1.0)


__all__ = [
    "ModelUser",
    "UserMetadata",
    "UserRepositoryProtocol",
    "calculate_user_score",
]
'''


@pytest.fixture
def low_quality_code() -> str:
    """Code sample with anti-patterns for testing low scores.

    This sample contains common quality issues:
    - dict[str, Any] instead of TypedDict
    - TODO and FIXME comments
    - **kwargs usage
    - Missing docstrings
    - No frozen=True on models
    - Long functions
    - Magic numbers

    Returns:
        String containing low-quality Python code with anti-patterns
    """
    return '''"""Module with quality issues for testing."""

from typing import Any

from pydantic import BaseModel


class User(BaseModel):
    name: str
    data: dict[str, Any]  # Anti-pattern: untyped dictionary


def process_user(user, **kwargs):
    # TODO: fix this later
    # FIXME: this is broken
    x = 42  # magic number
    result = {}
    for i in range(100):
        if i % 2 == 0:
            if i % 3 == 0:
                if i % 5 == 0:
                    result[str(i)] = user.name + str(i)
                else:
                    result[str(i)] = user.name
            else:
                result[str(i)] = str(i)
        else:
            result[str(i)] = None
    return result


def another_bad_function(data: dict[str, Any], config: dict[str, Any]):
    # No docstring
    # Using dict[str, Any] anti-pattern
    if data.get("flag"):
        return config.get("value", 0) * 2
    return None
'''


@pytest.fixture
def minimal_valid_input() -> ModelQualityScoringInput:
    """Create a minimal valid input for quality scoring.

    Returns:
        ModelQualityScoringInput with required fields populated
    """
    return ModelQualityScoringInput(
        source_path="/test/minimal.py",
        content='"""Minimal module."""\n\ndef hello() -> str:\n    """Return greeting."""\n    return "hello"\n',
        language="python",
    )


@pytest.fixture
def strict_preset_input(high_quality_code: str) -> ModelQualityScoringInput:
    """Create input with STRICT preset for production-level testing.

    Args:
        high_quality_code: High-quality code fixture

    Returns:
        ModelQualityScoringInput configured with STRICT preset
    """
    return ModelQualityScoringInput(
        source_path="/test/strict_example.py",
        content=high_quality_code,
        language="python",
        onex_preset=OnexStrictnessLevel.STRICT,
    )


@pytest.fixture
def custom_weights_input(high_quality_code: str) -> ModelQualityScoringInput:
    """Create input with custom dimension weights.

    Configures weights that emphasize documentation and patterns
    over complexity and maintainability.

    Args:
        high_quality_code: High-quality code fixture

    Returns:
        ModelQualityScoringInput with custom dimension weights
    """
    return ModelQualityScoringInput(
        source_path="/test/custom_weights.py",
        content=high_quality_code,
        language="python",
        dimension_weights=ModelDimensionWeights(
            complexity=0.10,
            maintainability=0.10,
            documentation=0.25,
            temporal_relevance=0.15,
            patterns=0.25,
            architectural=0.15,
        ),
        onex_compliance_threshold=0.75,
    )
