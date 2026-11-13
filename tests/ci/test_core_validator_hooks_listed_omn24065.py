# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-24065: the core validator hooks that pass over this tree are listed, unnarrowed.

omnibase_core merged generic validators that no consumer called. Each id below is
listed in an omnibase_core block of the pre-commit config with no ``files`` or
``exclude`` key, so the hook judges the whole tree and no baseline or
allowlist stands behind it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

CONFIG = Path(__file__).resolve().parents[2] / ".pre-commit-config.yaml"
CORE_REPO = "https://github.com/OmniNode-ai/omnibase_core"
LISTED = (
    "declared-timeout-reaches-call",
    "no-time-bound-truncation",
    "no-id-from-stamp",
    "no-fixed-tmp-atomic-write",
)


def _core_declarations(hook_id: str) -> list[dict[str, object]]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(config, dict)
    found: list[dict[str, object]] = []
    for repo in config["repos"]:
        if not isinstance(repo, dict) or repo.get("repo") != CORE_REPO:
            continue
        for hook in repo.get("hooks", []):
            if isinstance(hook, dict) and hook.get("id") == hook_id:
                found.append(hook)
    return found


@pytest.mark.parametrize("hook_id", LISTED)
def test_hook_is_listed_once_in_an_omnibase_core_block(hook_id: str) -> None:
    assert len(_core_declarations(hook_id)) == 1


@pytest.mark.parametrize("hook_id", LISTED)
def test_hook_judges_the_whole_tree_with_no_narrowing_key(hook_id: str) -> None:
    (hook,) = _core_declarations(hook_id)
    assert not ({"files", "exclude"} & set(hook))
