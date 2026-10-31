# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""FixRecord creation handler with atomic transaction and orphan prevention.

Ticket: OMN-3556
"""

from __future__ import annotations

import logging
from typing import Any

from omniintelligence.debug_intel.protocols import ProtocolDebugStore
from omniintelligence.nodes.node_debug_fix_record_effect.models.model_fix_record_request import (
    ModelFixRecordRequest,
)

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


class HandlerFixRecord:
    """Create a FixRecord when CI recovers, using an injected debug store."""

    def __init__(self, *, store: ProtocolDebugStore) -> None:
        self._store = store

    async def handle(self, request: ModelFixRecordRequest) -> dict[str, Any] | None:
        """Create a FixRecord when CI recovers after an open TriggerRecord exists.

        Steps:
        1. Find the most recent open TriggerRecord for (repo, branch)
        2. If none found: noop (no active failure streak to resolve)
        3. Insert a FixRecord (with regression_test_added heuristic)
        4. Atomically mark the TriggerRecord resolved via try_mark_trigger_resolved
        5. If the atomic update returns no rows: the race was lost — mark as orphaned

        If try_mark_trigger_resolved returns False (concurrent handler won the race)
        the FixRecord is an orphan; the retrieval query join filters it out.

        Returns:
            The fix record dict on success, None if no open trigger or race lost.
        """
        # Step 1: Find open trigger
        trigger = await self._store.find_open_trigger_record(
            repo=request.repo, branch=request.branch
        )
        if trigger is None:
            logger.info(
                "No open TriggerRecord found for repo=%s branch=%s — noop",
                request.repo,
                request.branch,
            )
            return None

        trigger_id = str(trigger["id"])
        regression_test_added = _detect_regression_test_added(request.changed_files)

        # Step 2: Insert fix record
        fix = await self._store.insert_fix_record(
            trigger_record_id=trigger_id,
            repo=request.repo,
            sha=request.sha,
            pr_number=request.pr_number,
            regression_test_added=regression_test_added,
        )
        fix_id = str(fix["id"])

        # Step 3: Atomically mark trigger resolved
        won_race = await self._store.try_mark_trigger_resolved(
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
                "repo": request.repo,
                "sha": request.sha,
                "regression_test_added": regression_test_added,
            },
        )
        return fix


__all__ = [
    "HandlerFixRecord",
]
