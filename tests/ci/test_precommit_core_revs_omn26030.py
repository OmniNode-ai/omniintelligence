# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""OMN-26030: omnibase_core dev-merge hook revs read the newest tag, in step with the CI pin."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
CORE_REPO = "https://github.com/OmniNode-ai/omnibase_core"
NEW_TAG = "dev-20261119101844-59e0293aeaef"
OLD_TAG_PREFIXES = ("dev-20261029", "dev-20261103", "dev-20261111")


def _core_revs() -> list[str]:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text("utf-8"))
    return [str(r["rev"]) for r in config["repos"] if r.get("repo") == CORE_REPO]


def test_no_core_hook_rev_reads_an_old_dev_tag() -> None:
    stale = [rev for rev in _core_revs() if rev.startswith(OLD_TAG_PREFIXES)]
    assert stale == []


def test_dev_tag_revs_read_the_newest_tag() -> None:
    dev_revs = [rev for rev in _core_revs() if rev.startswith("dev-")]
    assert dev_revs
    assert set(dev_revs) == {NEW_TAG}


def test_ci_canonical_file_shape_pin_matches_the_hook_rev() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    assert f"omnibase_core@{NEW_TAG}" in workflow
