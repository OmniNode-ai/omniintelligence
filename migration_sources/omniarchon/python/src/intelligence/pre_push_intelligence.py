#!/usr/bin/env python3
"""
Enhanced Intelligence Pre-Push Hook v4.0 (Python Implementation)

A robust Python-based pre-push hook system for intelligent code change analysis
with cross-repository correlation and comprehensive testing support.

This replaces the complex 758-line shell script with a maintainable, testable
Python implementation that can be properly tested with pytest.
"""

import argparse
import json
import logging
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional


class PrePushIntelligenceGatherer:
    """Main class for gathering intelligence data from git pre-push events."""

    def __init__(
        self, repo_path: Optional[str] = None, config_path: Optional[str] = None
    ):
        """Initialize the intelligence gatherer.

        Args:
            repo_path: Path to the git repository (defaults to current directory)
            config_path: Path to configuration file (defaults to intelligence-hook-config.json)
        """
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.config_path = (
            Path(config_path)
            if config_path
            else self.repo_path / "intelligence-hook-config.json"
        )
        self.config = self._load_config()
        self.logger = self._setup_logging()

    def _load_config(self) -> dict:
        """Load configuration from intelligence-hook-config.json."""
        default_config = {
            "intelligence_enabled": True,
            "archon_mcp_endpoint": "http://localhost:8051/mcp",
            "archon_project_id": "26a1bd66-5fb6-40f9-a702-c69d789cf344",
            "diff_analysis": {
                "enabled": True,
                "max_diff_size": 50000,
                "context_lines": 3,
                "filter_sensitive_content": True,
            },
            "correlation_analysis": {
                "enabled": True,
                "sibling_repositories": [],
                "time_windows": [6, 24, 72],
            },
        }

        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    user_config = json.load(f)
                    # Merge with defaults
                    default_config.update(user_config)
            except (OSError, json.JSONDecodeError) as e:
                print(f"Warning: Could not load config from {self.config_path}: {e}")

        return default_config

    def _setup_logging(self) -> logging.Logger:
        """Setup logging to .git/intelligence-hook.log."""
        logger = logging.getLogger("intelligence-hook")
        logger.setLevel(logging.INFO)

        log_file = self.repo_path / ".git" / "intelligence-hook.log"
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def get_git_info(self) -> dict:
        """Extract git information for current repository state."""
        try:
            # Get repository name
            repo_name = self.repo_path.name

            # Get current branch
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_path,
                text=True,
            ).strip()

            # Get latest commit info
            commit_info = (
                subprocess.check_output(
                    ["git", "log", "-1", "--pretty=format:%H|%an|%ae|%s"],
                    cwd=self.repo_path,
                    text=True,
                )
                .strip()
                .split("|", 3)
            )

            commit_hash, author_name, author_email, commit_message = commit_info

            # Get changed files
            changed_files = (
                subprocess.check_output(
                    [
                        "git",
                        "diff-tree",
                        "--no-commit-id",
                        "--name-only",
                        "-r",
                        commit_hash,
                    ],
                    cwd=self.repo_path,
                    text=True,
                )
                .strip()
                .split("\n")
            )

            # Get diff with context
            diff_output = subprocess.check_output(
                [
                    "git",
                    "show",
                    f'--unified={self.config["diff_analysis"]["context_lines"]}',
                    commit_hash,
                ],
                cwd=self.repo_path,
                text=True,
            )

            return {
                "repository": repo_name,
                "branch": branch,
                "commit_hash": commit_hash,
                "author_name": author_name,
                "author_email": author_email,
                "commit_message": commit_message,
                "changed_files": [
                    f for f in changed_files if f
                ],  # Remove empty strings
                "diff_content": diff_output,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git command failed: {e}")
            raise

    def filter_sensitive_content(self, content: str) -> tuple[str, bool]:
        """Filter sensitive content from diff data.

        Returns:
            Tuple of (filtered_content, was_filtered)
        """
        if not self.config["diff_analysis"]["filter_sensitive_content"]:
            return content, False

        # Sensitive patterns to filter
        patterns = [
            (r"sk-[A-Za-z0-9]{32,}", "[FILTERED_OPENAI_API_KEY]"),
            (r"ghp_[A-Za-z0-9]{30,}", "[FILTERED_GITHUB_TOKEN]"),
            (r'postgresql://[^\s\'"]+', "postgresql://[FILTERED_DB_CONNECTION]"),
            (
                r"eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*",
                "[FILTERED_JWT_TOKEN]",
            ),
            # Bearer token patterns (e.g., Authorization: Bearer sk-...)
            (
                r'(?i)Authorization:\s*Bearer\s+[^\s\'"]+',
                "Authorization: Bearer [FILTERED_TOKEN]",
            ),
            # API key patterns (handles api_key, api-key, apiKey variations)
            # Excludes already-filtered values and known specific patterns
            (
                r'(?i)api[_-]?key["\s]*[:=]["\s]*(?!\[FILTERED)[^"\s,}]+',
                'api_key="[FILTERED_API_KEY]"',
            ),
            (
                r'(?i)secret["\s]*[:=]["\s]*[^"\s,}]+',
                'secret: "[FILTERED_SECRET]"',
            ),
            (
                r'(?i)secret_?key["\s]*[:=]["\s]*[^"\s,}]+',
                "SECRET_KEY=[FILTERED_SECRET]",
            ),
            (
                r'(?i)password["\s]*[:=]["\s]*[^"\s,}]+',
                'password: "[FILTERED_PASSWORD]"',
            ),
        ]

        import re

        filtered_content = content
        was_filtered = False

        for pattern, replacement in patterns:
            if re.search(pattern, filtered_content):
                filtered_content = re.sub(pattern, replacement, filtered_content)
                was_filtered = True

        return filtered_content, was_filtered

    def analyze_correlations(self, git_info: dict) -> dict:
        """Analyze cross-repository correlations."""
        if not self.config["correlation_analysis"]["enabled"]:
            return {"enabled": False}

        # This is a simplified version - in the full implementation,
        # this would analyze sibling repositories for correlations
        return {
            "enabled": True,
            "correlation_id": f"corr_{datetime.now().strftime('%Y%m%d%H%M')}",
            "temporal_correlations": [],
            "semantic_correlations": [],
            "breaking_changes": [],
            "impact_assessment": {"coordination_required": False, "risk_level": "low"},
        }

    def create_intelligence_document(
        self, git_info: dict, correlation_analysis: dict
    ) -> dict:
        """Create intelligence document structure."""
        # Filter sensitive content
        filtered_diff, was_filtered = self.filter_sensitive_content(
            git_info["diff_content"]
        )

        # Truncate diff if too large
        max_size = self.config["diff_analysis"]["max_diff_size"]
        if len(filtered_diff) > max_size:
            filtered_diff = (
                f"# Diff Summarized (Large)\n\n"
                f"Diff exceeds {max_size} characters.\n\n"
                f"Changed files: {len(git_info['changed_files'])}\n"
                f"Commit: {git_info['commit_hash']}\n"
            )

        document = {
            "title": f"Intelligence: {git_info['repository']} Code Changes with Analysis",
            "document_type": "intelligence",
            "content": {
                "analysis_type": "enhanced_code_changes_with_correlation",
                "metadata": {
                    "timestamp": git_info["timestamp"],
                    "repository": git_info["repository"],
                    "branch": git_info["branch"],
                    "commit": git_info["commit_hash"],
                    "author": git_info["author_name"],
                    "hook_version": "4.0_python",
                },
                "change_summary": {
                    "commit_message": git_info["commit_message"],
                    "files_changed": len(git_info["changed_files"]),
                    "security_status": "filtered" if was_filtered else "clean",
                },
                "cross_repository_correlation": correlation_analysis,
                "security_and_privacy": {
                    "content_filtered": was_filtered,
                    "rag_safe": True,
                    "intelligence_ready": True,
                },
                "code_changes_analysis": {
                    "changed_files": git_info["changed_files"],
                    "diff_content": filtered_diff,
                },
            },
            "tags": ["intelligence", "pre-push", "code-analysis", "v4.0"],
        }

        return document

    def send_to_archon_mcp(self, document: dict) -> bool:
        """Send intelligence document to Archon MCP server using the actual MCP endpoint."""
        try:
            # Use the MCP server endpoint
            mcp_endpoint = "http://localhost:8051/mcp"

            # Prepare MCP create_document request
            mcp_request = {
                "method": "create_document",
                "params": {
                    "project_id": self.config["archon_project_id"],
                    "title": document["title"],
                    "document_type": document["document_type"],
                    "content": document["content"],
                    "tags": document["tags"],
                },
            }

            # Send HTTP request to MCP endpoint
            data = json.dumps(mcp_request).encode("utf-8")
            req = urllib.request.Request(
                mcp_endpoint, data=data, headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    result = json.loads(response.read().decode("utf-8"))
                    if result.get("success", False):
                        self.logger.info(
                            "Successfully sent intelligence document to Archon MCP"
                        )
                        return True
                    else:
                        self.logger.error(
                            f"MCP request failed: {result.get('message', 'Unknown error')}"
                        )
                        return False
                else:
                    self.logger.error(
                        f"MCP request failed with status: {response.status}"
                    )
                    return False

        except Exception as e:
            self.logger.error(f"Failed to send document to Archon MCP: {e}")
            # As fallback, save document locally for manual processing
            self._save_document_locally(document)
            return False

    def _save_document_locally(self, document: dict):
        """Save intelligence document locally as fallback."""
        try:
            import random

            doc_id = f"intelligence-document-{random.randint(100000, 999999)}.json"
            doc_path = self.repo_path / ".git" / doc_id

            with open(doc_path, "w") as f:
                json.dump(document, f, indent=2)

            self.logger.info(f"Saved intelligence document locally: {doc_path}")
        except Exception as e:
            self.logger.error(f"Failed to save document locally: {e}")

    def run_intelligence_gathering(self) -> bool:
        """Main method to run the intelligence gathering process."""
        try:
            if not self.config["intelligence_enabled"]:
                self.logger.info("Intelligence gathering is disabled")
                return True

            self.logger.info("Starting intelligence gathering process")

            # Get git information
            git_info = self.get_git_info()
            self.logger.info(
                f"Processing commit {git_info['commit_hash']} in {git_info['repository']}"
            )

            # Analyze correlations
            correlation_analysis = self.analyze_correlations(git_info)

            # Create intelligence document
            document = self.create_intelligence_document(git_info, correlation_analysis)

            # Send to Archon MCP
            success = self.send_to_archon_mcp(document)

            if success:
                self.logger.info("Intelligence gathering completed successfully")
                return True
            else:
                self.logger.error("Intelligence gathering failed")
                return False

        except Exception as e:
            self.logger.error(f"Intelligence gathering failed with error: {e}")
            return False


def main():
    """Main entry point for the pre-push hook."""
    parser = argparse.ArgumentParser(
        description="Enhanced Intelligence Pre-Push Hook v4.0"
    )
    parser.add_argument(
        "--repo-path", help="Path to repository (default: current directory)"
    )
    parser.add_argument("--config-path", help="Path to config file")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode")

    args = parser.parse_args()

    try:
        gatherer = PrePushIntelligenceGatherer(
            repo_path=args.repo_path, config_path=args.config_path
        )

        success = gatherer.run_intelligence_gathering()

        if not success:
            print(
                "Intelligence gathering failed - check .git/intelligence-hook.log for details"
            )
            sys.exit(1)
        else:
            print("Intelligence gathering completed successfully")

    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
