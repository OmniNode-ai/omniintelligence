# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The dependency-provenance gate is core's validator, not a repository copy (OMN-22011).

omniintelligence carried its own scripts/check_dep_provenance.py (OMN-13873). It forbade
every ``git``/``rev``/``branch``/``tag`` source for omnibase-core and omnibase-spi,
so the cascade's own pin (a ``tag``-only source at the sibling's dev merge tag,
RULING 2026-10-29T01:50:26Z) failed it: the identical defect (omnimemory#720) went red in Dep Provenance
Gate, pre-commit and ONEX Validation. The script is also baselined shrink-only by
the canonical-file-shape ratchet, so the allowance omniclaude and omnibase_infra
carry could not be ported into it. Core's ``check-dep-provenance`` hook (OMN-22011)
admits the registry, a workspace and the sibling's own dev merge tag, and refuses a
revision, a branch, a release tag, a path and a foreign repository. This repository
consumes it through the pre-commit config, so the core revision has one home.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_CORE_REPO = "https://github.com/OmniNode-ai/omnibase_core"
_REV_RE = re.compile(r"dev-\d{14}-[0-9a-f]{12}")


def _core_hook_rev() -> str:
    config = yaml.safe_load((_ROOT / ".pre-commit-config.yaml").read_text())
    revs = [
        repo["rev"]
        for repo in config["repos"]
        if repo["repo"] == _CORE_REPO
        and "check-dep-provenance" in [hook["id"] for hook in repo["hooks"]]
    ]
    assert len(revs) == 1, "check-dep-provenance must come from omnibase_core once"
    return revs[0]


def test_the_repository_carries_no_copy_of_the_gate() -> None:
    assert not (_ROOT / "scripts" / "check_dep_provenance.py").exists()
    baseline = (
        _ROOT / ".onex_ratchets" / "canonical_file_shape_baseline.txt"
    ).read_text()
    assert "check_dep_provenance" not in baseline


def test_no_local_hook_runs_the_deleted_script() -> None:
    config = yaml.safe_load((_ROOT / ".pre-commit-config.yaml").read_text())
    local = [
        hook["id"]
        for repo in config["repos"]
        if repo["repo"] == "local"
        for hook in repo["hooks"]
        if "check_dep_provenance" in hook.get("entry", "")
        or hook["id"] == "check-dep-provenance"
    ]
    assert local == []


def test_the_hook_comes_from_a_core_dev_merge_tag() -> None:
    assert _REV_RE.fullmatch(_core_hook_rev())


def test_the_workflow_runs_the_same_hook_from_the_pre_commit_config() -> None:
    text = (_ROOT / ".github" / "workflows" / "dep-provenance-gate.yml").read_text()
    assert "scripts/check_dep_provenance.py" not in text
    assert "pre-commit run check-dep-provenance" in text
