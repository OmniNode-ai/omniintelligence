# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for the code crawler handler."""

import tempfile
from pathlib import Path

import pytest

from omniintelligence.nodes.node_code_crawler_effect.handlers.handler_crawl_files import (
    crawl_files,
)
from omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_config import (
    ModelCrawlConfig,
    ModelRepoCrawlConfig,
)


@pytest.mark.unit
class TestCrawlFiles:
    def test_crawl_with_filtering(self) -> None:
        """Crawler discovers .py files, ignores .txt, respects exclude."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "main.py").write_text("print('hello')")
            (src_dir / "utils.py").write_text("def helper(): pass")
            (src_dir / "nested").mkdir()
            (src_dir / "nested" / "deep.py").write_text("x = 1")
            (src_dir / "readme.txt").write_text("not a python file")

            # Create __pycache__ (should be excluded)
            cache_dir = src_dir / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "main.cpython-312.pyc").write_text("bytecode")

            config = ModelCrawlConfig(
                repos=[
                    ModelRepoCrawlConfig(
                        name="test_repo",
                        enabled=True,
                        path=tmpdir,
                        include=["src/**/*.py"],
                        exclude=["**/__pycache__/**"],
                    ),
                ]
            )

            events = list(crawl_files(config, crawl_id="test_crawl"))

            # Should find 3 .py files, not the .txt or __pycache__
            assert len(events) == 3
            file_paths = {e.file_path for e in events}
            assert "src/main.py" in file_paths
            assert "src/utils.py" in file_paths
            assert "src/nested/deep.py" in file_paths

            # All events should have correct metadata
            for event in events:
                assert event.crawl_id == "test_crawl"
                assert event.repo_name == "test_repo"
                assert event.file_extension == ".py"
                assert len(event.file_hash) == 64  # SHA256 hex

    def test_disabled_repo_skipped(self) -> None:
        """Disabled repos produce no events."""
        config = ModelCrawlConfig(
            repos=[
                ModelRepoCrawlConfig(
                    name="disabled",
                    enabled=False,
                    path="/nonexistent",
                    include=["**/*.py"],
                ),
            ]
        )
        events = list(crawl_files(config))
        assert len(events) == 0

    def test_repo_filter(self) -> None:
        """repo_filter limits crawl to specific repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text("x = 1")

            config = ModelCrawlConfig(
                repos=[
                    ModelRepoCrawlConfig(
                        name="repo_a",
                        path=tmpdir,
                        include=["*.py"],
                    ),
                    ModelRepoCrawlConfig(
                        name="repo_b",
                        path=tmpdir,
                        include=["*.py"],
                    ),
                ]
            )

            events = list(crawl_files(config, repo_filter="repo_a"))
            assert all(e.repo_name == "repo_a" for e in events)
