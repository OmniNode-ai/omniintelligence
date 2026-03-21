# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for OnexTreeGenerator and handle_code_crawl.

Covers:
  - OnexTreeGenerator scans a temp directory and returns .py files only
  - Include/exclude patterns are respected
  - Handler emits correct number of ModelCodeFileDiscoveredEvent events
  - Handler skips non-existent repo paths gracefully
  - Event fields are populated correctly

Ticket: OMN-5658
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from omniintelligence.nodes.node_code_crawler_effect.handlers.handler_onextree_generator import (
    OnexTreeGenerator,
    handle_code_crawl,
)
from omniintelligence.nodes.node_code_crawler_effect.models.model_code_file_discovered_event import (
    ModelCodeFileDiscoveredEvent,
)

pytestmark = pytest.mark.unit


# =============================================================================
# OnexTreeGenerator tests
# =============================================================================


@pytest.mark.asyncio
async def test_generator_scans_py_files_only(tmp_path: Path) -> None:
    """OnexTreeGenerator with include pattern returns only .py files."""
    # Create mixed file types
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')")
    (tmp_path / "src" / "config.yaml").write_text("key: value")
    (tmp_path / "src" / "utils.py").write_text("def util(): pass")
    (tmp_path / "README.md").write_text("# README")

    generator = OnexTreeGenerator(
        project_root=tmp_path,
        include_patterns=["src/**/*.py"],
    )

    result = await generator.generate_tree()

    # Collect all file nodes
    files = _collect_files(result.tree)
    file_names = {f.name for f in files}

    assert "app.py" in file_names
    assert "utils.py" in file_names
    assert "config.yaml" not in file_names
    assert "README.md" not in file_names


@pytest.mark.asyncio
async def test_generator_respects_exclude_patterns(tmp_path: Path) -> None:
    """OnexTreeGenerator excludes directories matching exclude patterns."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.pyc").write_bytes(b"\x00")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("# test")

    generator = OnexTreeGenerator(
        project_root=tmp_path,
        exclude_patterns=["__pycache__", "tests"],
    )

    result = await generator.generate_tree()
    files = _collect_files(result.tree)
    file_names = {f.name for f in files}

    assert "main.py" in file_names
    assert "cached.pyc" not in file_names
    assert "test_main.py" not in file_names


@pytest.mark.asyncio
async def test_generator_statistics(tmp_path: Path) -> None:
    """OnexTreeGenerator computes correct file statistics."""
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "b.py").write_text("y = 2")
    (tmp_path / "c.txt").write_text("text")

    generator = OnexTreeGenerator(project_root=tmp_path)
    result = await generator.generate_tree()

    assert result.statistics.total_files == 3
    assert result.statistics.file_type_distribution.get("py") == 2
    assert result.statistics.file_type_distribution.get("txt") == 1
    assert result.statistics.total_size_bytes > 0


@pytest.mark.asyncio
async def test_generator_empty_directory(tmp_path: Path) -> None:
    """OnexTreeGenerator handles empty directories without errors."""
    generator = OnexTreeGenerator(project_root=tmp_path)
    result = await generator.generate_tree()

    assert result.statistics.total_files == 0
    assert result.tree.type == "directory"
    assert result.tree.children == []


@pytest.mark.asyncio
async def test_generator_nested_directories(tmp_path: Path) -> None:
    """OnexTreeGenerator recursively scans nested directories."""
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    (tmp_path / "a" / "b" / "c" / "deep.py").write_text("# deep")

    generator = OnexTreeGenerator(
        project_root=tmp_path,
        include_patterns=["**/*.py"],
    )
    result = await generator.generate_tree()
    files = _collect_files(result.tree)

    assert len(files) == 1
    assert files[0].name == "deep.py"
    assert files[0].path == "a/b/c/deep.py"


# =============================================================================
# handle_code_crawl tests
# =============================================================================


@pytest.mark.asyncio
async def test_handler_emits_correct_event_count(tmp_path: Path) -> None:
    """Handler emits one ModelCodeFileDiscoveredEvent per discovered .py file."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "one.py").write_text("# one")
    (tmp_path / "src" / "two.py").write_text("# two")
    (tmp_path / "src" / "three.py").write_text("# three")
    (tmp_path / "src" / "skip.txt").write_text("skip me")

    repos_config = [
        {
            "name": "test_repo",
            "path": str(tmp_path),
            "include": ["src/**/*.py"],
            "exclude": ["__pycache__"],
        }
    ]

    events = await handle_code_crawl(
        repos_config=repos_config,
        crawl_id="test-crawl-001",
    )

    assert len(events) == 3
    assert all(isinstance(e, ModelCodeFileDiscoveredEvent) for e in events)
    assert all(e.repo_name == "test_repo" for e in events)
    assert all(e.crawl_id == "test-crawl-001" for e in events)


@pytest.mark.asyncio
async def test_handler_event_fields_populated(tmp_path: Path) -> None:
    """Handler populates all event fields correctly."""
    content = "print('hello world')"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(content)

    repos_config = [
        {
            "name": "my_repo",
            "path": str(tmp_path),
            "include": ["src/**/*.py"],
            "exclude": [],
        }
    ]

    events = await handle_code_crawl(repos_config=repos_config)

    assert len(events) == 1
    evt = events[0]
    assert evt.repo_name == "my_repo"
    assert evt.file_path == "src/app.py"
    assert evt.file_hash == hashlib.sha256(content.encode()).hexdigest()
    assert evt.file_size_bytes == len(content.encode())
    assert evt.contract_version == "1.0.0"
    assert evt.event_id  # non-empty UUID
    assert evt.crawl_id  # non-empty


@pytest.mark.asyncio
async def test_handler_skips_nonexistent_repo(tmp_path: Path) -> None:
    """Handler skips repos whose path does not exist."""
    repos_config = [
        {
            "name": "missing_repo",
            "path": str(tmp_path / "does_not_exist"),
            "include": ["**/*.py"],
            "exclude": [],
        }
    ]

    events = await handle_code_crawl(repos_config=repos_config)
    assert events == []


@pytest.mark.asyncio
async def test_handler_multiple_repos(tmp_path: Path) -> None:
    """Handler processes multiple repos and tags events with correct repo_name."""
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    (repo_a / "src").mkdir(parents=True)
    (repo_b / "src").mkdir(parents=True)
    (repo_a / "src" / "a.py").write_text("# a")
    (repo_b / "src" / "b1.py").write_text("# b1")
    (repo_b / "src" / "b2.py").write_text("# b2")

    repos_config = [
        {
            "name": "repo_a",
            "path": str(repo_a),
            "include": ["src/**/*.py"],
            "exclude": [],
        },
        {
            "name": "repo_b",
            "path": str(repo_b),
            "include": ["src/**/*.py"],
            "exclude": [],
        },
    ]

    events = await handle_code_crawl(repos_config=repos_config)

    repo_a_events = [e for e in events if e.repo_name == "repo_a"]
    repo_b_events = [e for e in events if e.repo_name == "repo_b"]

    assert len(repo_a_events) == 1
    assert len(repo_b_events) == 2


@pytest.mark.asyncio
async def test_handler_generates_crawl_id_when_not_provided(tmp_path: Path) -> None:
    """Handler generates a crawl_id when none is provided."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "f.py").write_text("# f")

    repos_config = [
        {"name": "r", "path": str(tmp_path), "include": ["src/**/*.py"], "exclude": []},
    ]

    events = await handle_code_crawl(repos_config=repos_config)
    assert len(events) == 1
    assert events[0].crawl_id  # should be a non-empty generated UUID


# =============================================================================
# Helpers
# =============================================================================


def _collect_files(node: OnexTreeNode) -> list[OnexTreeNode]:  # type: ignore[name-defined]  # noqa: F821
    """Recursively collect all file nodes from a tree."""
    from omniintelligence.nodes.node_code_crawler_effect.models.model_onextree import (
        OnexTreeNode,
    )

    files: list[OnexTreeNode] = []
    if node.type == "file":
        files.append(node)
    elif node.children:
        for child in node.children:
            files.extend(_collect_files(child))
    return files
