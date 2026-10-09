# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pin the public-repo hygiene wiring that makes five classes block (OMN-20783).

The gate itself lives in omniclaude and needs a private vocabulary, so it cannot
run here. These tests pin the three repository-owned halves of the mechanism:
the config that names the classes and the scope, the CI caller that runs the
gate at a revision that supports that scope, and the pre-commit hook that runs
the same revision over staged added lines. They also pin the CI pre-commit job,
which runs every hook over the tree and so must hand this hook its vocabulary.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.validation.validate_clean_root import ALLOWED_ROOT_DIRECTORIES

REPO_ROOT = Path(__file__).resolve().parents[3]
HYGIENE_CONFIG = REPO_ROOT / ".public-repo-hygiene.yaml"
HYGIENE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "public-repo-hygiene.yml"
PRECOMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

OMNICLAUDE_REPO_URL = "https://github.com/OmniNode-ai/omniclaude"
REUSABLE_PREFIX = (
    "OmniNode-ai/omniclaude/.github/workflows/public-repo-hygiene-reusable.yml@"
)
HOOK_ID = "public-repo-hygiene"

ENFORCED_CLASSES = frozenset(
    {
        "private-repo-name",
        "internal-kb-prose",
        "lab-config",
        "person-name",
        "private-network",
    }
)

# omniclaude revisions that predate the added-lines scope (OMN-19835, 9a58ef705).
# A caller pinned to one of these ignores `enforce_scope`. Spelled here, not read
# from a sibling clone, so the check runs on every runner.
PRE_ADDED_LINES_PINS = frozenset({"6ccd525e2b6390869d18f8e00d1b36294aa5550a"})

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

pytestmark = pytest.mark.unit


def _load(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path} did not parse to a mapping"
    return loaded


def _caller_pin() -> str:
    jobs = _load(HYGIENE_WORKFLOW)["jobs"]
    uses = str(jobs["public-repo-hygiene"]["uses"])
    assert uses.startswith(REUSABLE_PREFIX), uses
    return uses.removeprefix(REUSABLE_PREFIX)


def _hook_repo() -> dict[str, Any]:
    matches = [
        repository
        for repository in _load(PRECOMMIT_CONFIG)["repos"]
        if repository.get("repo") == OMNICLAUDE_REPO_URL
        and any(hook["id"] == HOOK_ID for hook in repository.get("hooks", []))
    ]
    assert len(matches) == 1, (
        f"expected one omniclaude repo entry carrying {HOOK_ID}, found {len(matches)}"
    )
    return matches[0]


def test_config_enforces_the_five_classes_on_added_lines() -> None:
    config = _load(HYGIENE_CONFIG)
    assert config.get("enforce_scope") == "added-lines"
    assert set(config.get("enforce_classes", [])) == ENFORCED_CLASSES
    assert len(config["enforce_classes"]) == len(ENFORCED_CLASSES)


def test_config_carries_no_allowlist_for_the_residue() -> None:
    config = _load(HYGIENE_CONFIG)
    assert set(config) <= {
        "mode",
        "suppression_registry",
        "enforce_scope",
        "enforce_classes",
        "allowed_top_level",
    }


def test_caller_pin_supports_the_added_lines_scope() -> None:
    pin = _caller_pin()
    assert SHA_RE.match(pin), f"pin must be a lowercase 40-hex commit, got {pin!r}"
    assert pin not in PRE_ADDED_LINES_PINS


def test_caller_keeps_the_job_id_and_inherits_secrets() -> None:
    job = _load(HYGIENE_WORKFLOW)["jobs"]["public-repo-hygiene"]
    assert job.get("secrets") == "inherit"


def test_hook_runs_the_gate_at_the_callers_revision() -> None:
    repository = _hook_repo()
    assert repository["rev"] == _caller_pin()


def test_hook_is_not_narrowed_or_weakened() -> None:
    hook = next(h for h in _hook_repo()["hooks"] if h["id"] == HOOK_ID)
    assert hook.get("args", []) == []
    assert "files" not in hook
    assert "exclude" not in hook
    assert hook.get("always_run", True) is True
    assert "pre-commit" in hook.get("stages", ["pre-commit"])


def _pre_commit_job_steps() -> list[dict[str, Any]]:
    return list(_load(CI_WORKFLOW)["jobs"]["pre-commit"]["steps"])


def test_ci_pre_commit_job_gives_the_hook_its_vocabulary() -> None:
    steps = _pre_commit_job_steps()
    run_index = next(
        i
        for i, s in enumerate(steps)
        if "pre-commit run --all-files" in str(s.get("run", ""))
    )
    before = steps[:run_index]
    exported = "\n".join(str(s.get("run", "")) for s in before)
    assert "OMNI_HYGIENE_VOCAB_PATH" in exported
    fetched = [
        s
        for s in before
        if str(s.get("uses", "")).startswith("actions/checkout")
        and "vocabulary" in str(s.get("with", {}).get("path", ""))
    ]
    assert len(fetched) == 2, "main and lab vocabulary checkouts both precede the run"
    assert any(
        str(s.get("uses", "")).startswith("actions/create-github-app-token")
        for s in before
    )


def test_ci_pre_commit_job_has_no_skip() -> None:
    job = _load(CI_WORKFLOW)["jobs"]["pre-commit"]
    text = yaml.safe_dump(job)
    assert "SKIP" not in text


def test_ci_vocabulary_checkouts_stay_out_of_the_repository_root() -> None:
    """The clean-root hook rejects an unlisted root directory, so the checkout
    paths must sit under a directory it already allows."""
    paths = [
        str(step["with"]["path"])
        for step in _pre_commit_job_steps()
        if str(step.get("uses", "")).startswith("actions/checkout")
        and "vocabulary" in str(step.get("with", {}).get("path", ""))
    ]
    assert len(paths) == 2
    for path in paths:
        root = path.split("/", 1)[0]
        assert "/" in path and root in ALLOWED_ROOT_DIRECTORIES, path
