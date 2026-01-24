# SPDX-License-Identifier: Apache-2.0
"""Fixtures for quality_scoring_compute integration tests.

This module provides pytest fixtures for testing the NodeQualityScoringCompute
node against real Python files from the codebase. Fixtures include:

- Path constants for project structure navigation
- Real Python file collection from the codebase
- Node instantiation fixtures

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
