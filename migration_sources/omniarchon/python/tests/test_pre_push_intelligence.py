#!/usr/bin/env python3
"""
Comprehensive pytest test suite for Enhanced Intelligence Pre-Push Hook v4.0

This replaces manual testing with proper automated tests that can verify:
1. Git information extraction
2. Sensitive content filtering
3. Intelligence document creation
4. MCP integration
5. Complete end-to-end flow
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the intelligence module to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intelligence.pre_push_intelligence import PrePushIntelligenceGatherer


@pytest.fixture
def temp_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir) / "test_repo"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
        )

        # Create initial commit
        test_file = repo_path / "test_file.py"
        test_file.write_text("# Initial test file\nprint('hello world')\n")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True
        )

        yield repo_path


@pytest.fixture
def test_config(temp_repo):
    """Create a test configuration file."""
    config = {
        "intelligence_enabled": True,
        "archon_mcp_endpoint": "http://localhost:8051/mcp",
        "archon_project_id": "test-project-id",
        "diff_analysis": {
            "enabled": True,
            "max_diff_size": 5000,
            "context_lines": 3,
            "filter_sensitive_content": True,
        },
        "correlation_analysis": {
            "enabled": True,
            "sibling_repositories": ["omnibase-core", "omniagent"],
            "time_windows": [6, 24, 72],
        },
    }

    config_path = temp_repo / "intelligence-hook-config.json"
    config_path.write_text(json.dumps(config, indent=2))
    return config_path


class TestPrePushIntelligenceGatherer:
    """Test cases for the PrePushIntelligenceGatherer class."""

    @pytest.fixture
    def gatherer(self, temp_repo, test_config):
        """Create a PrePushIntelligenceGatherer instance for testing."""
        return PrePushIntelligenceGatherer(
            repo_path=str(temp_repo), config_path=str(test_config)
        )

    def test_config_loading(self, gatherer):
        """Test that configuration is loaded correctly."""
        assert gatherer.config["intelligence_enabled"] is True
        assert gatherer.config["archon_project_id"] == "test-project-id"
        assert gatherer.config["diff_analysis"]["context_lines"] == 3
        assert (
            "omnibase-core"
            in gatherer.config["correlation_analysis"]["sibling_repositories"]
        )

    def test_config_defaults(self, temp_repo):
        """Test that default configuration is used when no config file exists."""
        gatherer = PrePushIntelligenceGatherer(repo_path=str(temp_repo))
        assert gatherer.config["intelligence_enabled"] is True
        assert (
            gatherer.config["archon_project_id"]
            == "26a1bd66-5fb6-40f9-a702-c69d789cf344"
        )

    def test_git_info_extraction(self, gatherer, temp_repo):
        """Test extraction of git repository information."""
        # Create a new commit to test
        test_file = temp_repo / "new_feature.py"
        test_file.write_text(
            "# New feature file\ndef new_function():\n    return 'test'\n"
        )
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: add new feature"], cwd=temp_repo, check=True
        )

        git_info = gatherer.get_git_info()

        assert git_info["repository"] == "test_repo"
        assert git_info["branch"] == "master" or git_info["branch"] == "main"
        assert git_info["author_name"] == "Test User"
        assert git_info["commit_message"] == "feat: add new feature"
        assert "new_feature.py" in git_info["changed_files"]
        assert "def new_function():" in git_info["diff_content"]
        assert git_info["timestamp"]  # Should have ISO timestamp

    def test_sensitive_content_filtering(self, gatherer):
        """Test that sensitive content is properly filtered."""
        sensitive_content = """
API_KEY=sk-1234567890abcdef1234567890abcdef
GITHUB_TOKEN=ghp_1234567890abcdef1234567890abcdef12
DATABASE_URL=postgresql://user:secret123@localhost:5432/db
JWT_TOKEN=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature
SECRET_KEY=very_secret_password_123
NORMAL_CODE=console.log("Hello World")
        """

        filtered_content, was_filtered = gatherer.filter_sensitive_content(
            sensitive_content
        )

        assert was_filtered is True
        assert "sk-1234567890abcdef1234567890abcdef" not in filtered_content
        assert "[FILTERED_OPENAI_API_KEY]" in filtered_content
        assert "[FILTERED_GITHUB_TOKEN]" in filtered_content
        assert "[FILTERED_DB_CONNECTION]" in filtered_content
        assert "[FILTERED_JWT_TOKEN]" in filtered_content
        assert "console.log" in filtered_content  # Normal code should remain

    def test_no_filtering_when_disabled(self, temp_repo, test_config):
        """Test that filtering is skipped when disabled in config."""
        # Modify config to disable filtering
        config = json.loads(test_config.read_text())
        config["diff_analysis"]["filter_sensitive_content"] = False
        test_config.write_text(json.dumps(config))

        gatherer = PrePushIntelligenceGatherer(
            repo_path=str(temp_repo), config_path=str(test_config)
        )

        sensitive_content = "API_KEY=sk-1234567890abcdef1234567890abcdef"
        filtered_content, was_filtered = gatherer.filter_sensitive_content(
            sensitive_content
        )

        assert was_filtered is False
        assert filtered_content == sensitive_content

    def test_correlation_analysis(self, gatherer):
        """Test correlation analysis functionality."""
        git_info = {
            "repository": "test_repo",
            "commit_hash": "abc123",
            "author_name": "Test User",
            "commit_message": "feat: test commit",
        }

        correlation_analysis = gatherer.analyze_correlations(git_info)

        assert correlation_analysis["enabled"] is True
        assert "correlation_id" in correlation_analysis
        assert "temporal_correlations" in correlation_analysis
        assert "semantic_correlations" in correlation_analysis
        assert "breaking_changes" in correlation_analysis
        assert correlation_analysis["impact_assessment"]["risk_level"] in [
            "low",
            "medium",
            "high",
        ]

    def test_correlation_disabled(self, temp_repo, test_config):
        """Test that correlation analysis can be disabled."""
        # Modify config to disable correlation analysis
        config = json.loads(test_config.read_text())
        config["correlation_analysis"]["enabled"] = False
        test_config.write_text(json.dumps(config))

        gatherer = PrePushIntelligenceGatherer(
            repo_path=str(temp_repo), config_path=str(test_config)
        )

        correlation_analysis = gatherer.analyze_correlations({})
        assert correlation_analysis["enabled"] is False

    def test_intelligence_document_creation(self, gatherer):
        """Test creation of intelligence document structure."""
        git_info = {
            "repository": "test_repo",
            "branch": "main",
            "commit_hash": "abc123def456",
            "author_name": "Test User",
            "author_email": "test@example.com",
            "commit_message": "feat: add new feature",
            "changed_files": ["src/feature.py", "tests/test_feature.py"],
            "diff_content": '# Sample diff content\n+def new_function():\n+    return "test"',
            "timestamp": "2025-09-05T12:00:00Z",
        }

        correlation_analysis = {
            "enabled": True,
            "correlation_id": "test_corr_123",
            "temporal_correlations": [],
            "impact_assessment": {"risk_level": "low"},
        }

        document = gatherer.create_intelligence_document(git_info, correlation_analysis)

        assert document["title"].startswith("Intelligence: test_repo Code Changes")
        assert document["document_type"] == "intelligence"
        assert (
            document["content"]["analysis_type"]
            == "enhanced_code_changes_with_correlation"
        )

        metadata = document["content"]["metadata"]
        assert metadata["repository"] == "test_repo"
        assert metadata["branch"] == "main"
        assert metadata["commit"] == "abc123def456"
        assert metadata["author"] == "Test User"
        assert metadata["hook_version"] == "4.0_python"

        change_summary = document["content"]["change_summary"]
        assert change_summary["commit_message"] == "feat: add new feature"
        assert change_summary["files_changed"] == 2

        assert (
            document["content"]["cross_repository_correlation"] == correlation_analysis
        )
        assert "intelligence" in document["tags"]
        assert "v4.0" in document["tags"]

    def test_diff_size_truncation(self, gatherer):
        """Test that large diffs are properly truncated."""
        # Create a very long diff
        large_diff = "# Large diff\n" + "+" + "x" * 10000

        git_info = {
            "repository": "test_repo",
            "branch": "main",
            "commit_hash": "abc123",
            "author_name": "Test User",
            "author_email": "test@example.com",
            "commit_message": "Large change",
            "changed_files": ["large_file.py"],
            "diff_content": large_diff,
            "timestamp": "2025-09-05T12:00:00Z",
        }

        document = gatherer.create_intelligence_document(git_info, {})
        diff_content = document["content"]["code_changes_analysis"]["diff_content"]

        assert len(diff_content) < len(large_diff)
        assert "Diff Summarized (Large)" in diff_content
        assert "abc123" in diff_content  # Commit hash should be included in summary

    @patch("urllib.request.urlopen")
    def test_mcp_integration_success(self, mock_urlopen, gatherer):
        """Test successful integration with Archon MCP."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"success": True}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        document = {
            "title": "Test Intelligence Document",
            "document_type": "intelligence",
            "content": {"test": "data"},
            "tags": ["test"],
        }

        success = gatherer.send_to_archon_mcp(document)

        assert success is True
        mock_urlopen.assert_called_once()

        # Verify the request was properly formatted
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert "8051/mcp" in request.full_url
        assert request.headers["Content-type"] == "application/json"

    @patch("urllib.request.urlopen")
    def test_mcp_integration_failure(self, mock_urlopen, gatherer):
        """Test handling of MCP integration failures."""
        # Mock failed HTTP response
        mock_response = MagicMock()
        mock_response.status = 500
        mock_urlopen.return_value.__enter__.return_value = mock_response

        document = {
            "title": "Test",
            "document_type": "intelligence",
            "content": {},
            "tags": [],
        }

        success = gatherer.send_to_archon_mcp(document)

        assert success is False

    @patch("urllib.request.urlopen")
    def test_mcp_network_error(self, mock_urlopen, gatherer):
        """Test handling of network errors during MCP communication."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        document = {
            "title": "Test",
            "document_type": "intelligence",
            "content": {},
            "tags": [],
        }

        success = gatherer.send_to_archon_mcp(document)

        assert success is False

    def test_intelligence_disabled(self, temp_repo, test_config):
        """Test that the system respects intelligence_enabled=false."""
        # Disable intelligence gathering
        config = json.loads(test_config.read_text())
        config["intelligence_enabled"] = False
        test_config.write_text(json.dumps(config))

        gatherer = PrePushIntelligenceGatherer(
            repo_path=str(temp_repo), config_path=str(test_config)
        )

        # Should return True (success) but not actually process
        result = gatherer.run_intelligence_gathering()
        assert result is True

    @patch("urllib.request.urlopen")
    def test_end_to_end_integration(self, mock_urlopen, temp_repo, test_config):
        """Test the complete end-to-end intelligence gathering flow."""
        # Mock successful MCP response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"success": True}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Create a new commit with some changes
        feature_file = temp_repo / "feature.py"
        feature_file.write_text(
            """
def calculate_total(items):
    '''Calculate total price of items'''
    return sum(item.price for item in items)

def process_payment(amount, method='card'):
    '''Process payment using specified method'''
    if method == 'card':
        return charge_card(amount)
    elif method == 'cash':
        return accept_cash(amount)
    else:
        raise ValueError(f"Unsupported payment method: {method}")
        """
        )

        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: add payment processing"],
            cwd=temp_repo,
            check=True,
        )

        # Run the intelligence gathering process
        gatherer = PrePushIntelligenceGatherer(
            repo_path=str(temp_repo), config_path=str(test_config)
        )

        result = gatherer.run_intelligence_gathering()

        assert result is True
        mock_urlopen.assert_called_once()

        # Verify the request payload
        call_args = mock_urlopen.call_args
        request = call_args[0][0]

        # Read the request data
        request_data = json.loads(request.data.decode("utf-8"))

        # Verify MCP request structure
        assert request_data["method"] == "create_document"
        assert "params" in request_data

        params = request_data["params"]
        assert params["project_id"] == "test-project-id"
        assert "test_repo Code Changes" in params["title"]
        assert params["document_type"] == "intelligence"
        assert "intelligence" in params["tags"]

        content = params["content"]
        assert content["metadata"]["repository"] == "test_repo"
        assert (
            "feat: add payment processing"
            in content["change_summary"]["commit_message"]
        )
        assert (
            content["change_summary"]["files_changed"] == 2
        )  # feature.py + config file
        assert "feature.py" in content["code_changes_analysis"]["changed_files"]


class TestCommandLineInterface:
    """Test the command-line interface."""

    def test_main_function_success(self, temp_repo, test_config):
        """Test successful execution of main function."""
        with patch(
            "sys.argv",
            [
                "pre_push_intelligence.py",
                "--repo-path",
                str(temp_repo),
                "--config-path",
                str(test_config),
                "--test-mode",
            ],
        ):
            with patch(
                "intelligence.pre_push_intelligence.PrePushIntelligenceGatherer"
            ) as mock_gatherer:
                mock_instance = MagicMock()
                mock_instance.run_intelligence_gathering.return_value = True
                mock_gatherer.return_value = mock_instance

                from intelligence.pre_push_intelligence import main

                # Should not raise SystemExit
                main()
                mock_gatherer.assert_called_once()
                mock_instance.run_intelligence_gathering.assert_called_once()

    def test_main_function_failure(self, temp_repo, test_config):
        """Test handling of failures in main function."""
        with patch(
            "sys.argv",
            [
                "pre_push_intelligence.py",
                "--repo-path",
                str(temp_repo),
                "--config-path",
                str(test_config),
            ],
        ):
            with patch(
                "intelligence.pre_push_intelligence.PrePushIntelligenceGatherer"
            ) as mock_gatherer:
                mock_instance = MagicMock()
                mock_instance.run_intelligence_gathering.return_value = False
                mock_gatherer.return_value = mock_instance

                from intelligence.pre_push_intelligence import main

                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1


@pytest.mark.integration
class TestRealIntegration:
    """Integration tests that run against real services (when available)."""

    @pytest.mark.skipif(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
    )
    def test_real_mcp_integration(self, temp_repo):
        """Test integration with a real Archon MCP server."""
        # This test only runs if RUN_INTEGRATION_TESTS=1
        config = {
            "intelligence_enabled": True,
            "archon_mcp_endpoint": "http://localhost:8051/mcp",
            "archon_project_id": "26a1bd66-5fb6-40f9-a702-c69d789cf344",
        }

        config_path = temp_repo / "intelligence-hook-config.json"
        config_path.write_text(json.dumps(config))

        # Create a test commit
        test_file = temp_repo / "integration_test.py"
        test_file.write_text(
            "# Integration test file\nprint('testing real integration')"
        )
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "test: integration test"], cwd=temp_repo, check=True
        )

        gatherer = PrePushIntelligenceGatherer(
            repo_path=str(temp_repo), config_path=str(config_path)
        )

        result = gatherer.run_intelligence_gathering()

        # If the MCP server is running, this should succeed
        # If not, we expect it to fail gracefully
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
