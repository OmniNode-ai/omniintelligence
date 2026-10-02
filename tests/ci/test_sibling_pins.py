# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Fail-closed gate: a workflow may read a sibling repo only at a pinned version (OMN-20001).

A workflow here that reads another OmniNode-ai repo at a moving ref (`@main`,
`@dev`, no `ref:`, `ref: dev`, a bare `git clone`) turns a merge in that sibling
into a red check on this repo. The rule: each repo checks only itself; a
comparison against a sibling uses the version this repo has pinned (a 40-hex
commit sha or a release tag), and a new sibling version is integration-tested
by this repo before it moves its pin.

Asserted statically over every `.github/workflows/*.yml`:

* a job-level or step-level `uses: OmniNode-ai/<sibling>/...@<ref>` has a
  sha or release-tag `<ref>`;
* an `actions/checkout` step with `repository: OmniNode-ai/<sibling>` has a
  sha or release-tag `ref:`;
* a `run:` step that `git clone`s an OmniNode-ai sibling is refused (clone the
  pinned sha with `git fetch <url> <sha>` instead).

`test_detector_flags_moving_refs` is the positive control: the detector must
flag a synthetic workflow carrying each known-bad shape, so a zero over the real
workflows cannot be a blind detector.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
SELF_REPO = "omniintelligence"
_SIBLING_USES = re.compile(r"^OmniNode-ai/(?P<repo>[\w.-]+)/[^@\s]+@(?P<ref>\S+)$")
_PINNED = re.compile(r"^(?:[0-9a-f]{40}|v\d+\.\d+\.\d+)$")
_CLONE = re.compile(r"git\s+clone\b[^\n]*github\.com/OmniNode-ai/(?P<repo>[\w-]+)")


def _steps(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        step
        for job in (doc.get("jobs") or {}).values()
        for step in (job.get("steps") or [])
    ]


def moving_sibling_reads(doc: dict[str, Any]) -> list[str]:
    """Return a description of every sibling read in ``doc`` not at a pinned version."""
    bad: list[str] = []
    nodes = list((doc.get("jobs") or {}).values()) + _steps(doc)
    for node in nodes:
        uses = node.get("uses")
        if isinstance(uses, str):
            m = _SIBLING_USES.match(uses)
            if m and m["repo"] != SELF_REPO and not _PINNED.match(m["ref"]):
                bad.append(f"uses: {uses}")
            if uses.startswith("actions/checkout@"):
                with_ = node.get("with") or {}
                repo = str(with_.get("repository", ""))
                if (
                    repo.startswith("OmniNode-ai/")
                    and repo != f"OmniNode-ai/{SELF_REPO}"
                ):
                    ref = str(with_.get("ref", ""))
                    if not _PINNED.match(ref):
                        bad.append(f"checkout {repo} ref={ref or '<default branch>'}")
    for step in _steps(doc):
        m = _CLONE.search(str(step.get("run", "")))
        if m and m["repo"] != SELF_REPO:
            bad.append(f"git clone of {m['repo']}")
    return bad


def test_no_workflow_reads_a_sibling_at_a_moving_ref() -> None:
    found = {
        path.name: bad
        for path in sorted(WORKFLOWS.glob("*.yml"))
        if (bad := moving_sibling_reads(yaml.safe_load(path.read_text()) or {}))
    }
    assert not found, f"sibling reads not pinned to a sha or release tag: {found}"


def test_detector_flags_moving_refs() -> None:
    sha = "a" * 40
    doc = yaml.safe_load(
        f"""
jobs:
  reusable_main:
    uses: OmniNode-ai/omnibase_core/.github/workflows/x.yml@main
  reusable_dev:
    uses: OmniNode-ai/omniclaude/.github/workflows/x.yml@dev
  reusable_pinned:
    uses: OmniNode-ai/omniclaude/.github/workflows/x.yml@{sha}
  steps:
    runs-on: ubuntu-latest
    steps:
      - uses: OmniNode-ai/onex_change_control/.github/actions/y@main
      - uses: actions/checkout@v7
        with: {{repository: OmniNode-ai/omnibase_core}}
      - uses: actions/checkout@v7
        with: {{repository: OmniNode-ai/omnibase_core, ref: dev}}
      - uses: actions/checkout@v7
        with: {{repository: OmniNode-ai/omnimarket, ref: {sha}}}
      - run: git clone --depth=1 https://github.com/OmniNode-ai/omnibase_core.git x
"""
    )
    assert moving_sibling_reads(doc) == [
        "uses: OmniNode-ai/omnibase_core/.github/workflows/x.yml@main",
        "uses: OmniNode-ai/omniclaude/.github/workflows/x.yml@dev",
        "uses: OmniNode-ai/onex_change_control/.github/actions/y@main",
        "checkout OmniNode-ai/omnibase_core ref=<default branch>",
        "checkout OmniNode-ai/omnibase_core ref=dev",
        "git clone of omnibase_core",
    ]
