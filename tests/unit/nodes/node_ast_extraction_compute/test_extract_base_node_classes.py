# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for AST extraction on NodeCompute base class [OMN-7173].

Reads the real NodeCompute source from omnibase_core and verifies that
extract_entities_from_source produces correct class entities, base class
lists, method lists, and INHERITS relationships.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers import (
    extract_entities_from_source,
)


def _omni_home() -> Path:
    """Locate the omni_home root directory.

    Strategy:
    1. If OMNI_HOME env var is set, use that.
    2. Walk up from this file's directory looking for a directory that
       contains both ``omnibase_core/`` and ``omniintelligence/`` subdirs.
    3. If running from a git worktree, resolve the main working tree via
       ``git rev-parse --git-common-dir`` and walk up from there.

    Raises:
        RuntimeError: If omni_home cannot be found.
    """
    env_val = os.environ.get("OMNI_HOME")
    if env_val:
        p = Path(env_val)
        if p.is_dir():
            return p

    def _has_both_repos(d: Path) -> bool:
        return (d / "omnibase_core").is_dir() and (d / "omniintelligence").is_dir()

    # Strategy 2: walk up from __file__
    current = Path(__file__).resolve()
    for ancestor in current.parents:
        if _has_both_repos(ancestor):
            return ancestor

    # Strategy 3: resolve via git common dir (worktree support)
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(current.parent),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        # common_dir is the .git dir of the main repo; its parent is the repo,
        # and its grandparent may be omni_home.
        git_path = Path(common_dir).resolve()
        for ancestor in git_path.parents:
            if _has_both_repos(ancestor):
                return ancestor
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    msg = (
        "Cannot locate omni_home. Set the OMNI_HOME environment variable "
        "or run tests from within the omni_home tree."
    )
    raise RuntimeError(msg)


def _read_node_compute_source() -> str:
    """Read the NodeCompute source file from omnibase_core."""
    path = (
        _omni_home()
        / "omnibase_core"
        / "src"
        / "omnibase_core"
        / "nodes"
        / "node_compute.py"
    )
    return path.read_text(encoding="utf-8")


@pytest.mark.unit
class TestExtractNodeComputeBaseClass:
    """Verify AST extraction on the real NodeCompute source file."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        source = _read_node_compute_source()
        self.result = extract_entities_from_source(
            source,
            file_path="src/omnibase_core/nodes/node_compute.py",
            source_repo="omnibase_core",
        )
        self.entities_by_name = {e.entity_name: e for e in self.result.entities}

    def test_node_compute_class_entity_found(self) -> None:
        """A class entity named 'NodeCompute' is extracted."""
        assert "NodeCompute" in self.entities_by_name
        entity = self.entities_by_name["NodeCompute"]
        assert entity.entity_type == "class"
        assert entity.source_repo == "omnibase_core"

    def test_node_compute_bases_and_methods(self) -> None:
        """NodeCompute lists correct bases and includes the 'process' method."""
        entity = self.entities_by_name["NodeCompute"]

        # Bases include NodeCoreBase and MixinHandlerRouting
        assert "NodeCoreBase" in entity.bases
        assert "MixinHandlerRouting" in entity.bases

        # Methods include 'process'
        method_names = [m["name"] for m in entity.methods]
        assert "process" in method_names

    def test_inherits_relationships(self) -> None:
        """INHERITS relationships exist from NodeCompute to its base classes."""
        inherits_rels = [
            r
            for r in self.result.relationships
            if r.relationship_type == "inherits"
            and r.source_entity == "omnibase_core.nodes.node_compute.NodeCompute"
        ]
        target_names = {r.target_entity for r in inherits_rels}
        assert "NodeCoreBase" in target_names
        assert "MixinHandlerRouting" in target_names
