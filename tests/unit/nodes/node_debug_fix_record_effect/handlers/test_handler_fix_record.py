# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for fix record creation handler.

Ticket: OMN-3556
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_debug_fix_record_effect.handlers.handler_fix_record import (
    _detect_regression_test_added,
    handle_fix_record,
)


@pytest.mark.unit
async def test_fix_record_atomic_transaction() -> None:
    """INSERT fix_record + UPDATE trigger_record must both be called."""
    store = AsyncMock()
    store.find_open_trigger_record.return_value = {
        "id": str(uuid4()),
        "repo": "r",
        "branch": "b",
    }
    store.try_mark_trigger_resolved.return_value = True  # won the race
    store.insert_fix_record.return_value = {"id": str(uuid4())}

    await handle_fix_record(
        repo="r",
        branch="b",
        sha="fix-sha",
        pr_number=42,
        changed_files=["src/foo.py"],
        store=store,
    )

    # Both must be called: insert fix, then mark resolved
    store.insert_fix_record.assert_called_once()
    store.try_mark_trigger_resolved.assert_called_once()


@pytest.mark.unit
async def test_race_lost_fix_record_not_returned() -> None:
    """If try_mark_trigger_resolved returns False, result is orphaned."""
    store = AsyncMock()
    store.find_open_trigger_record.return_value = {"id": str(uuid4())}
    store.try_mark_trigger_resolved.return_value = False  # race lost
    fix_id = str(uuid4())
    store.insert_fix_record.return_value = {"id": fix_id}

    result = await handle_fix_record(
        repo="r",
        branch="b",
        sha="fix-sha",
        pr_number=None,
        changed_files=[],
        store=store,
    )

    # Race-lost result must be marked as orphaned (not returned as success)
    assert result is None or result.get("orphaned") is True


@pytest.mark.unit
async def test_no_open_trigger_record_is_noop() -> None:
    """If no unresolved TriggerRecord exists for repo+branch, do nothing."""
    store = AsyncMock()
    store.find_open_trigger_record.return_value = None

    result = await handle_fix_record(
        repo="r", branch="b", sha="sha", pr_number=None, changed_files=[], store=store
    )

    store.insert_fix_record.assert_not_called()
    assert result is None


@pytest.mark.unit
def test_regression_test_added_true_when_tests_modified() -> None:
    """Heuristic: true if PR touches tests/ AND adds/modifies a test file."""
    changed = ["tests/unit/test_foo.py", "src/foo.py"]
    assert _detect_regression_test_added(changed) is True


@pytest.mark.unit
def test_regression_test_added_false_when_no_test_files() -> None:
    """No test files in changed_files means False."""
    changed = ["src/foo.py", "docs/README.md"]
    assert _detect_regression_test_added(changed) is False


@pytest.mark.unit
def test_regression_test_added_false_when_tests_dir_not_touched() -> None:
    """File with 'test' in name but not under tests/ is not counted."""
    changed = ["src/tests_helper.py"]  # filename contains "test" but not under tests/
    assert _detect_regression_test_added(changed) is False
