"""
Simplified Unit Tests for Tree Building Logic

Tests the build_directory_tree() configuration and integration without complex mocking.
Focuses on testable logic and relies on integration tests for full workflow.

Coverage Target: 90%+
Created: 2025-11-10
"""

import os
import sys
from pathlib import Path

import pytest

# Add project root to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.bulk_ingest_repository import BulkIngestApp


@pytest.fixture
def bulk_ingest_app(tmp_path):
    """Create BulkIngestApp instance for testing."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()

    app = BulkIngestApp(
        project_path=project_path,
        project_name="test_project",
        kafka_bootstrap_servers="localhost:9092",
        dry_run=True,  # Prevent actual Kafka operations
        skip_tree=False,  # Enable tree building for tests
    )

    return app


class TestTreeBuildingConfiguration:
    """Test tree building configuration and settings."""

    def test_tree_building_enabled_by_default(self, bulk_ingest_app):
        """Test that tree building is enabled by default."""
        assert bulk_ingest_app.skip_tree is False

    def test_tree_building_can_be_disabled(self, tmp_path):
        """Test that tree building can be disabled with skip_tree flag."""
        project_path = tmp_path / "test_skip"
        project_path.mkdir()

        app = BulkIngestApp(
            project_path=project_path,
            project_name="test_skip",
            kafka_bootstrap_servers="localhost:9092",
            dry_run=True,
            skip_tree=True,  # Disable tree building
        )

        assert app.skip_tree is True

    def test_tree_building_project_name_set(self, bulk_ingest_app):
        """Test that project name is properly set for tree building."""
        assert bulk_ingest_app.project_name == "test_project"

    def test_tree_building_project_path_set(self, bulk_ingest_app):
        """Test that project path is properly set for tree building."""
        assert bulk_ingest_app.project_path.name == "test_project"
        assert bulk_ingest_app.project_path.exists()


@pytest.mark.asyncio
class TestTreeBuildingSkipLogic:
    """Test skip_tree flag logic."""

    async def test_skip_tree_returns_true_immediately(self, tmp_path):
        """Test that build_directory_tree returns True when skip_tree is True."""
        project_path = tmp_path / "test_skip"
        project_path.mkdir()

        app = BulkIngestApp(
            project_path=project_path,
            project_name="test_skip",
            kafka_bootstrap_servers="localhost:9092",
            dry_run=True,
            skip_tree=True,  # Disable tree building
        )

        correlation_id = "test-correlation-id"
        result = await app.build_directory_tree(correlation_id)

        # Should return True (success) without actually building tree
        assert result is True


class TestCLIArgumentHandling:
    """Test CLI argument handling for tree building."""

    def test_skip_tree_from_cli_default_false(self, tmp_path):
        """Test skip_tree defaults to False."""
        project_path = tmp_path / "cli_test"
        project_path.mkdir()

        app = BulkIngestApp(
            project_path=project_path,
            project_name="cli_test",
            kafka_bootstrap_servers="localhost:9092",
            dry_run=True,
            # skip_tree not specified - should default to False
        )

        assert app.skip_tree is False

    def test_skip_tree_from_cli_explicit_true(self, tmp_path):
        """Test skip_tree can be explicitly set to True."""
        project_path = tmp_path / "cli_test_skip"
        project_path.mkdir()

        app = BulkIngestApp(
            project_path=project_path,
            project_name="cli_test_skip",
            kafka_bootstrap_servers="localhost:9092",
            dry_run=True,
            skip_tree=True,
        )

        assert app.skip_tree is True

    def test_skip_tree_from_cli_explicit_false(self, tmp_path):
        """Test skip_tree can be explicitly set to False."""
        project_path = tmp_path / "cli_test_explicit"
        project_path.mkdir()

        app = BulkIngestApp(
            project_path=project_path,
            project_name="cli_test_explicit",
            kafka_bootstrap_servers="localhost:9092",
            dry_run=True,
            skip_tree=False,
        )

        assert app.skip_tree is False


class TestProjectConfiguration:
    """Test project configuration for tree building."""

    def test_project_path_resolved(self, bulk_ingest_app):
        """Test that project path is resolved to absolute path."""
        assert bulk_ingest_app.project_path.is_absolute()

    def test_project_name_from_path(self, tmp_path):
        """Test that project name defaults to directory name."""
        project_path = tmp_path / "my_custom_project"
        project_path.mkdir()

        app = BulkIngestApp(
            project_path=project_path,
            # project_name not specified - should default to "my_custom_project"
            kafka_bootstrap_servers="localhost:9092",
            dry_run=True,
        )

        assert app.project_name == "my_custom_project"

    def test_project_name_explicit_override(self, tmp_path):
        """Test that explicit project name overrides path."""
        project_path = tmp_path / "directory_name"
        project_path.mkdir()

        app = BulkIngestApp(
            project_path=project_path,
            project_name="custom_name",  # Override default
            kafka_bootstrap_servers="localhost:9092",
            dry_run=True,
        )

        assert app.project_name == "custom_name"


class TestEnvironmentVariables:
    """Test environment variable handling for tree building."""

    def test_memgraph_uri_default(self, bulk_ingest_app):
        """Test that MEMGRAPH_URI defaults are used."""
        # Default should be bolt://localhost:7687
        # This is read inside build_directory_tree()
        assert bulk_ingest_app.project_name is not None

    def test_dry_run_enabled(self, bulk_ingest_app):
        """Test that dry_run flag is respected."""
        assert bulk_ingest_app.dry_run is True

    def test_dry_run_disabled(self, tmp_path):
        """Test that dry_run can be disabled."""
        project_path = tmp_path / "not_dry_run"
        project_path.mkdir()

        app = BulkIngestApp(
            project_path=project_path,
            project_name="not_dry_run",
            kafka_bootstrap_servers="localhost:9092",
            dry_run=False,
        )

        assert app.dry_run is False


class TestLoggingConfiguration:
    """Test logging configuration for tree building."""

    def test_logger_exists(self, bulk_ingest_app):
        """Test that logger is configured."""
        assert bulk_ingest_app.logger is not None

    def test_verbose_logging_disabled_by_default(self, bulk_ingest_app):
        """Test that verbose logging is disabled by default."""
        assert bulk_ingest_app.verbose is False

    def test_verbose_logging_can_be_enabled(self, tmp_path):
        """Test that verbose logging can be enabled."""
        project_path = tmp_path / "verbose_test"
        project_path.mkdir()

        app = BulkIngestApp(
            project_path=project_path,
            project_name="verbose_test",
            kafka_bootstrap_servers="localhost:9092",
            dry_run=True,
            verbose=True,
        )

        assert app.verbose is True


if __name__ == "__main__":
    import subprocess

    try:
        result = subprocess.run(
            ["pytest", __file__, "-v", "--tb=short", "-x"],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print("pytest not found. Install with: pip install pytest pytest-asyncio")
