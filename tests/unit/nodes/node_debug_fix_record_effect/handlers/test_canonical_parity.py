# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Compare fix-record results and store operations with the pre-flip handler."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

import pytest

from omniintelligence.nodes.node_debug_fix_record_effect.handlers import (
    handler_fix_record as canonical,
)

BASE_REF = "688acb01"
CASES = {
    "no_trigger": (False, True, []),
    "resolved_without_tests": (True, True, ["src/fix.py"]),
    "resolved_with_tests": (True, True, ["src/fix.py", "tests/test_fix.py"]),
    "race_lost": (True, False, ["tests/test_fix.py"]),
    "non_test_directory": (True, True, ["testing/helper.py"]),
    "nested_test_file": (True, True, ["tests/data/test_result.json"]),
}


def _legacy_handler() -> ModuleType:
    root = Path(__file__).resolve().parents[5]
    relative = (
        "src/omniintelligence/nodes/node_debug_fix_record_effect/"
        "handlers/handler_fix_record.py"
    )
    source = subprocess.run(
        ["git", "show", f"{BASE_REF}:{relative}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    module = ModuleType("legacy_fix_record")
    exec(compile(source, "<legacy_fix_record>", "exec"), module.__dict__)
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
