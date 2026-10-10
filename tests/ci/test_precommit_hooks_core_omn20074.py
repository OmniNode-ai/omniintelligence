# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-20074: no-hardcoded-topics and no-untracked-todos come from omnibase_core, with every exclude and setting unchanged.

OCC retirement S8: the hooks of these ids used to be pulled from the
change-control repository; omnibase_core exports them under the same ids, so only
``repo:`` and ``rev:`` change.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

CONFIG = Path(__file__).resolve().parents[2] / ".pre-commit-config.yaml"
CORE_REPO = "https://github.com/OmniNode-ai/omnibase_core"
CHANGE_CONTROL_REPO = "https://github.com/OmniNode-ai/onex_change_control"
# Each hook's exclude from the change-control block, byte for byte (None: no exclude).
EXPECTED_EXCLUDE: dict[str, str | None] = {
    "no-hardcoded-topics": "(?x)^(\n  src/omniintelligence/constants\\.py|\n  src/omniintelligence/runtime/dispatch_handlers\\.py|\n  src/omniintelligence/runtime/contracts/runtime_config\\.yaml|\n  src/omniintelligence/nodes/node_bloom_eval_orchestrator/handlers/handler_bloom_eval_effect\\.py|\n  src/omniintelligence/nodes/node_compliance_evaluate_effect/handlers/handler_compliance_evaluate\\.py|\n  src/omniintelligence/nodes/node_crawl_scheduler_effect/handlers/handler_crawl_scheduler\\.py|\n  src/omniintelligence/nodes/node_evidence_collection_effect/handlers/handler_evidence_collection\\.py|\n  src/omniintelligence/nodes/node_gmail_intent_evaluator_effect/handlers/handler_gmail_intent_evaluate\\.py|\n  src/omniintelligence/nodes/node_pattern_compliance_effect/handlers/handler_compute\\.py|\n  src/omniintelligence/nodes/node_watchdog_effect/handlers/handler_watchdog\\.py|\n  src/omniintelligence/model_selector/episode_emitter\\.py|\n  src/omniintelligence/runtime/dispatch_handler_code_analysis\\.py|\n  src/omniintelligence/runtime/contract_topics\\.py\n)$",
    "no-untracked-todos": None,
}
# The keys each hook carried, so a widened or added setting is refused.
EXPECTED_KEYS: dict[str, list[str]] = {
    "no-hardcoded-topics": ["exclude", "id"],
    "no-untracked-todos": ["id", "stages"],
}
# The stages each hook carried (None: no stages key).
EXPECTED_STAGES: dict[str, list[str] | None] = {
    "no-hardcoded-topics": None,
    "no-untracked-todos": ["pre-commit"],
}
# Hook ids the change-control repository still supplies after the move.
REMAINING_CHANGE_CONTROL_HOOKS: set[str] = set()


def _repos() -> list[dict[str, object]]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(config, dict)
    repos = config["repos"]
    assert isinstance(repos, list)
    return [repo for repo in repos if isinstance(repo, dict)]


def _hooks(repo: dict[str, object]) -> list[dict[str, object]]:
    hooks = repo.get("hooks", [])
    assert isinstance(hooks, list)
    return [hook for hook in hooks if isinstance(hook, dict)]


def _declarations(hook_id: str) -> list[tuple[dict[str, object], dict[str, object]]]:
    return [
        (repo, hook)
        for repo in _repos()
        for hook in _hooks(repo)
        if hook.get("id") == hook_id
    ]


@pytest.mark.parametrize("hook_id", sorted(EXPECTED_EXCLUDE))
def test_hook_is_declared_once_in_an_omnibase_core_block_at_a_full_sha(
    hook_id: str,
) -> None:
    found = _declarations(hook_id)
    assert len(found) == 1
    repo, _ = found[0]
    assert repo["repo"] == CORE_REPO
    rev = repo["rev"]
    assert isinstance(rev, str)
    assert re.fullmatch(r"[0-9a-f]{40}", rev)


@pytest.mark.parametrize("hook_id", sorted(EXPECTED_EXCLUDE))
def test_hook_keeps_its_exclude_and_settings(hook_id: str) -> None:
    _, hook = _declarations(hook_id)[0]
    exclude = hook.get("exclude")
    expected = EXPECTED_EXCLUDE[hook_id]
    if expected is None:
        assert exclude is None
    else:
        assert isinstance(exclude, str)
        assert exclude == expected
    assert sorted(hook) == EXPECTED_KEYS[hook_id]
    assert hook.get("stages") == EXPECTED_STAGES[hook_id]


def test_change_control_block_supplies_only_the_hooks_not_yet_ported() -> None:
    supplied = {
        str(hook["id"])
        for repo in _repos()
        if repo["repo"] == CHANGE_CONTROL_REPO
        for hook in _hooks(repo)
    }
    assert supplied == REMAINING_CHANGE_CONTROL_HOOKS
