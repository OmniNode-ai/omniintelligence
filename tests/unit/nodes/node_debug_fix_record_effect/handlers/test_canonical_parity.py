# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Compare fix-record results and store operations with the pre-flip handler."""

from __future__ import annotations

from types import ModuleType
from unittest.mock import AsyncMock

import pytest

from omniintelligence.nodes.node_debug_fix_record_effect.handlers import (
    handler_fix_record as canonical,
)

# Legacy module captured with git show 688acb01:src/omniintelligence/nodes/node_debug_fix_record_effect/handlers/handler_fix_record.py
# Kept inline so unit-test jobs need no git history in a shallow checkout.
LEGACY_SOURCE = '''# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""FixRecord creation handler with atomic transaction and orphan prevention.

Ticket: OMN-3556
"""

from __future__ import annotations

import logging
from typing import Any

from omniintelligence.debug_intel.protocols import ProtocolDebugStore

logger = logging.getLogger(__name__)


def _detect_regression_test_added(changed_files: list[str]) -> bool:
    """Phase 1 heuristic: true if PR touches tests/ AND modifies a test file.

    Not perfect — does not parse AST. Better than always False.
    Only matches files under the tests/ directory (not filenames that merely
    contain "test" elsewhere in the path).
    """
    return any(
        f.startswith("tests/") and (f.endswith(".py") or "/test_" in f)
        for f in changed_files
    )


async def handle_fix_record(
    repo: str,
    branch: str,
    sha: str,
    pr_number: int | None,
    changed_files: list[str],
    store: ProtocolDebugStore,
) -> dict[str, Any] | None:
    """Create a FixRecord when CI recovers after an open TriggerRecord exists.

    Steps:
    1. Find the most recent open TriggerRecord for (repo, branch)
    2. If none found: noop (no active failure streak to resolve)
    3. Insert a FixRecord (with regression_test_added heuristic)
    4. Atomically mark the TriggerRecord resolved via try_mark_trigger_resolved
    5. If the atomic update returns no rows: the race was lost — mark as orphaned

    Orphaned fix records: if try_mark_trigger_resolved returns False (concurrent
    handler won the race), the FixRecord is an orphan. The retrieval query join
    will filter it out (fix_record_id on trigger_record won't point to this fix).

    Returns:
        The fix record dict on success, None if no open trigger or race lost.
    """
    # Step 1: Find open trigger
    trigger = await store.find_open_trigger_record(repo=repo, branch=branch)
    if trigger is None:
        logger.info(
            "No open TriggerRecord found for repo=%s branch=%s — noop",
            repo,
            branch,
        )
        return None

    trigger_id = str(trigger["id"])
    regression_test_added = _detect_regression_test_added(changed_files)

    # Step 2: Insert fix record
    fix = await store.insert_fix_record(
        trigger_record_id=trigger_id,
        repo=repo,
        sha=sha,
        pr_number=pr_number,
        regression_test_added=regression_test_added,
    )
    fix_id = str(fix["id"])

    # Step 3: Atomically mark trigger resolved
    won_race = await store.try_mark_trigger_resolved(
        trigger_record_id=trigger_id,
        fix_record_id=fix_id,
    )

    if not won_race:
        logger.warning(
            "Race lost for trigger_record_id=%s — fix_record %s is orphaned",
            trigger_id,
            fix_id,
        )
        return {
            "orphaned": True,
            "fix_record_id": fix_id,
            "trigger_record_id": trigger_id,
        }

    logger.info(
        "FixRecord created and TriggerRecord resolved",
        extra={
            "fix_record_id": fix_id,
            "trigger_record_id": trigger_id,
            "repo": repo,
            "sha": sha,
            "regression_test_added": regression_test_added,
        },
    )
    return fix


__all__ = [
    "_detect_regression_test_added",
    "handle_fix_record",
]
'''
CASES = {
    "no_trigger": (False, True, []),
    "resolved_without_tests": (True, True, ["src/fix.py"]),
    "resolved_with_tests": (True, True, ["src/fix.py", "tests/test_fix.py"]),
    "race_lost": (True, False, ["tests/test_fix.py"]),
    "non_test_directory": (True, True, ["testing/helper.py"]),
    "nested_test_file": (True, True, ["tests/data/test_result.json"]),
}


def _legacy_handler() -> ModuleType:
    module = ModuleType("legacy_fix_record")
    exec(compile(LEGACY_SOURCE, "<legacy_fix_record>", "exec"), module.__dict__)
    return module


def _store(*, trigger_exists: bool, wins_race: bool) -> AsyncMock:
    store = AsyncMock()
    store.find_open_trigger_record.return_value = (
        {"id": "trigger-id"} if trigger_exists else None
    )
    store.insert_fix_record.return_value = {"id": "fix-id", "repo": "example/repo"}
    store.try_mark_trigger_resolved.return_value = wins_race
    return store


@pytest.mark.unit
@pytest.mark.parametrize("case", CASES)
async def test_canonical_dispatch_matches_legacy(case: str) -> None:
    """The typed entry preserves results, dependency arguments and call order."""
    handler_type = getattr(canonical, "HandlerFixRecord", None)
    assert handler_type is not None, "typed handler class must exist"
    # Import after the assertion so the overlaid test fails on its assertion on BASE.
    from omniintelligence.nodes.node_debug_fix_record_effect.models.model_fix_record_request import (
        ModelFixRecordRequest,
    )

    trigger_exists, wins_race, changed_files = CASES[case]
    request = ModelFixRecordRequest(
        repo="example/repo",
        branch="dev",
        sha="fix-sha",
        pr_number=None if case == "race_lost" else 42,
        changed_files=changed_files,
    )
    old_store = _store(trigger_exists=trigger_exists, wins_race=wins_race)
    new_store = _store(trigger_exists=trigger_exists, wins_race=wins_race)
    legacy = _legacy_handler()
    expected = await legacy.handle_fix_record(**request.model_dump(), store=old_store)
    actual = await handler_type(new_store).handle(request)

    assert actual == expected
    assert new_store.mock_calls == old_store.mock_calls
    for operation in (
        "find_open_trigger_record",
        "insert_fix_record",
        "try_mark_trigger_resolved",
    ):
        assert (
            getattr(new_store, operation).await_args_list
            == getattr(old_store, operation).await_args_list
        )
