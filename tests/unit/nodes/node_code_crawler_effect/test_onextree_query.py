# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for OnexTree Query Engine (OMN-5673)."""

from __future__ import annotations

import time

import pytest

from omniintelligence.nodes.node_code_crawler_effect.handlers.handler_onextree_query import (
    FileNode,
    OnexTreeQueryEngine,
)


def _build_file_tree(n: int) -> list[FileNode]:
    """Generate a synthetic file tree with n Python files across directories."""
    nodes: list[FileNode] = []
    dirs_needed = max(1, n // 10)

    # Create directories
    for d in range(dirs_needed):
        nodes.append(
            FileNode(
                path=f"src/pkg{d}",
                name=f"pkg{d}",
                node_type="directory",
            )
        )

    # Create files distributed across directories
    for i in range(n):
        d = i % dirs_needed
        ext = "py" if i % 3 != 2 else "yaml"
        nodes.append(
            FileNode(
                path=f"src/pkg{d}/file_{i}.{ext}",
                name=f"file_{i}.{ext}",
                node_type="file",
                extension=ext,
            )
        )

    return nodes


@pytest.mark.unit
class TestOnexTreeQueryEngine:
    """Tests for query engine lookups and config-driven index selection."""

    def test_exact_path_lookup_performance(self) -> None:
        """Exact path lookup returns in <5ms for 10K file tree."""
        nodes = _build_file_tree(10_000)
        engine = OnexTreeQueryEngine()
        engine.load_file_nodes(nodes)

        # Pick a file that exists: index 100 → dir 100%1000=100, ext: 100%3=1 → py
        target = "src/pkg100/file_100.py"

        start = time.perf_counter()
        result = engine.lookup_path(target)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result is not None
        assert result.path == target
        assert elapsed_ms < 5, f"Lookup took {elapsed_ms:.2f}ms (expected <5ms)"

    def test_extension_lookup(self) -> None:
        """Extension lookup returns all matching files."""
        nodes = _build_file_tree(30)
        engine = OnexTreeQueryEngine()
        engine.load_file_nodes(nodes)

        py_files = engine.find_by_extension("py")
        yaml_files = engine.find_by_extension("yaml")

        assert len(py_files) > 0
        assert all(f.extension == "py" for f in py_files)
        assert len(yaml_files) > 0
        assert all(f.extension == "yaml" for f in yaml_files)

    def test_directory_children(self) -> None:
        """Directory children returns immediate children."""
        nodes = [
            FileNode(path="src", name="src", node_type="directory"),
            FileNode(path="src/a.py", name="a.py", node_type="file", extension="py"),
            FileNode(path="src/b.py", name="b.py", node_type="file", extension="py"),
        ]
        engine = OnexTreeQueryEngine()
        engine.load_file_nodes(nodes)

        children = engine.get_directory_children("src")
        assert len(children) == 2
        assert {c.name for c in children} == {"a.py", "b.py"}

    def test_name_similarity_search(self) -> None:
        """Name similarity finds files by partial name match."""
        nodes = [
            FileNode(
                path="src/handler_crawl.py",
                name="handler_crawl.py",
                node_type="file",
                extension="py",
            ),
            FileNode(
                path="src/handler_extract.py",
                name="handler_extract.py",
                node_type="file",
                extension="py",
            ),
            FileNode(
                path="src/model_entity.py",
                name="model_entity.py",
                node_type="file",
                extension="py",
            ),
        ]
        engine = OnexTreeQueryEngine()
        engine.load_file_nodes(nodes)

        results = engine.find_similar_names("handler")
        assert len(results) == 2
        assert all("handler" in r.name for r in results)

    def test_config_driven_index_selection(self) -> None:
        """Disabled indexes are not built."""
        nodes = _build_file_tree(100)

        # Only enable exact_path index
        engine = OnexTreeQueryEngine(enabled_indexes=["exact_path"])
        engine.load_file_nodes(nodes)

        # exact_path should work
        assert engine.lookup_path("src/pkg0/file_0.py") is not None

        # extension index should be empty (disabled)
        assert engine.find_by_extension("py") == []

        # name index should be empty (disabled)
        assert engine.find_by_name("file_0.py") == []

    def test_from_contract_config(self) -> None:
        """Factory method reads config correctly."""
        config = {
            "enabled": True,
            "indexes": [
                {"type": "exact_path"},
                {"type": "extension"},
            ],
        }
        engine = OnexTreeQueryEngine.from_contract_config(config)
        assert engine._enabled == {"exact_path", "extension"}

    def test_from_contract_config_disabled(self) -> None:
        """Disabled engine has no indexes."""
        config = {"enabled": False}
        engine = OnexTreeQueryEngine.from_contract_config(config)
        assert engine._enabled == set()
