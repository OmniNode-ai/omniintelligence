# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for omnidash TypeScript extraction in crawler (OMN-5680)."""

from __future__ import annotations

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
class TestOmnidashCrawl:
    """Tests for omnidash TypeScript crawling."""

    def test_crawler_discovers_ts_files(self) -> None:
        """Crawler with omnidash enabled emits events for .ts files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server_dir = Path(tmpdir) / "server"
            server_dir.mkdir()
            (server_dir / "app.ts").write_text("export class App {}")
            (server_dir / "utils.js").write_text("function helper() {}")
            (server_dir / "types.d.ts").write_text("declare type Foo = string;")

            # node_modules should be excluded
            nm_dir = Path(tmpdir) / "node_modules"
            nm_dir.mkdir()
            (nm_dir / "lib.ts").write_text("export const x = 1;")

            config = ModelCrawlConfig(
                repos=[
                    ModelRepoCrawlConfig(
                        name="omnidash",
                        enabled=True,
                        path=tmpdir,
                        include=["server/**/*.ts", "server/**/*.js"],
                        exclude=["node_modules/**", "dist/**", "*.d.ts"],
                    ),
                ]
            )

            events = list(crawl_files(config, crawl_id="test_crawl"))

            file_paths = {e.file_path for e in events}
            # Should find .ts and .js, not .d.ts or node_modules
            assert "server/app.ts" in file_paths
            assert "server/utils.js" in file_paths
            # .d.ts excluded
            assert "server/types.d.ts" not in file_paths
            # node_modules excluded
            assert "node_modules/lib.ts" not in file_paths

            for event in events:
                assert event.repo_name == "omnidash"
                assert event.crawl_id == "test_crawl"
