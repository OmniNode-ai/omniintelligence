# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for AST extraction on all four ONEX base node classes [OMN-7174].

Uses ``extract_entities_from_source`` against the real source files in
omnibase_core to verify that each base node class is correctly extracted
with its distinguishing mixin in the ``bases`` list.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers import (
    extract_entities_from_source,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FOUR_NODE_BASE_CLASSES = {
    "NodeCompute",
    "NodeEffect",
    "NodeOrchestrator",
    "NodeReducer",
}

# ---------------------------------------------------------------------------
# Helper: locate omni_home
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Parametrized test data for all four ONEX base node classes
# ---------------------------------------------------------------------------

_BASE_NODE_SPECS = [
    pytest.param(
        {
            "class_name": "NodeCompute",
            "file": "node_compute.py",
            "distinguishing_mixin": "MixinHandlerRouting",
        },
        id="NodeCompute",
    ),
    pytest.param(
        {
            "class_name": "NodeEffect",
            "file": "node_effect.py",
            "distinguishing_mixin": "MixinEffectExecution",
        },
        id="NodeEffect",
    ),
    pytest.param(
        {
            "class_name": "NodeOrchestrator",
            "file": "node_orchestrator.py",
            "distinguishing_mixin": "MixinWorkflowExecution",
        },
        id="NodeOrchestrator",
    ),
    pytest.param(
        {
            "class_name": "NodeReducer",
            "file": "node_reducer.py",
            "distinguishing_mixin": "MixinFSMExecution",
        },
        id="NodeReducer",
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize("spec", _BASE_NODE_SPECS)
def test_base_node_class_extraction(spec: dict[str, str]) -> None:
    """Verify AST extraction finds the base node class with its distinguishing mixin."""
    class_name = spec["class_name"]
    file_name = spec["file"]
    distinguishing_mixin = spec["distinguishing_mixin"]

    source_path = (
        _omni_home() / "omnibase_core" / "src" / "omnibase_core" / "nodes" / file_name
    )
    source_code = source_path.read_text(encoding="utf-8")
    relative_path = f"src/omnibase_core/nodes/{file_name}"

    result = extract_entities_from_source(
        source_code,
        file_path=relative_path,
        source_repo="omnibase_core",
    )

    # Build lookup by entity_name
    entities_by_name = {e.entity_name: e for e in result.entities}

    # Assert the class entity is found
    assert class_name in entities_by_name, (
        f"Expected entity '{class_name}' not found. "
        f"Available entities: {sorted(entities_by_name.keys())}"
    )

    entity = entities_by_name[class_name]
    assert entity.entity_type == "class"
    assert entity.source_repo == "omnibase_core"

    # Assert the distinguishing mixin is in the bases list
    assert distinguishing_mixin in entity.bases, (
        f"Expected '{distinguishing_mixin}' in bases for {class_name}. "
        f"Actual bases: {entity.bases}"
    )

    # Assert NodeCoreBase is also present (shared by all four)
    assert "NodeCoreBase" in entity.bases, (
        f"Expected 'NodeCoreBase' in bases for {class_name}. "
        f"Actual bases: {entity.bases}"
    )


# ---------------------------------------------------------------------------
# Role detection test [OMN-7175]
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_detect_compute_node_role() -> None:
    """extract_entities_from_source detects NodeCompute role on a real file."""
    target = (
        _omni_home()
        / "omniintelligence"
        / "src"
        / "omniintelligence"
        / "nodes"
        / "node_quality_scoring_compute"
        / "node.py"
    )
    assert target.exists(), f"Target file not found: {target}"

    source_code = target.read_text(encoding="utf-8")
    result = extract_entities_from_source(
        source_code,
        file_path="src/omniintelligence/nodes/node_quality_scoring_compute/node.py",
        source_repo="omniintelligence",
    )

    # Find the entity by exact name — never by index/position
    entity = None
    for e in result.entities:
        if e.entity_name == "NodeQualityScoringCompute":
            entity = e
            break

    assert entity is not None, (
        "Entity 'NodeQualityScoringCompute' not found in extraction result. "
        f"Found entities: {[e.entity_name for e in result.entities]}"
    )

    # Strip generic params from each base and detect role
    detected_role: str | None = None
    for base in entity.bases:
        stripped = base.split("[")[0]
        if stripped in FOUR_NODE_BASE_CLASSES:
            detected_role = stripped
            break

    assert detected_role == "NodeCompute", (
        f"Expected role 'NodeCompute' but detected '{detected_role}'. "
        f"Raw bases: {entity.bases}"
    )
