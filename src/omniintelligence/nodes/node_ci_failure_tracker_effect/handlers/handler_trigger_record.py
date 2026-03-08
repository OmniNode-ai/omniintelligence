# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""TriggerRecord creation handler.

SHA semantics (Phase 1):
    observed_bad_sha = sha when streak threshold was crossed.
    This is NOT the first bad commit; it is the first commit OBSERVED
    after threshold crossing. Phase 2 will add bisect-based
    suspected_first_bad_sha separately.

Streak semantics:
    streak_count_at_trigger is read from failure_streaks.streak_count.
    NEVER derive this by counting ci_failure_events rows.

Ticket: OMN-3556
"""

from __future__ import annotations

import logging
from typing import Any

from omniintelligence.debug_intel.protocols import ProtocolDebugStore

logger = logging.getLogger(__name__)


async def handle_trigger_record(
    repo: str,
    branch: str,
    sha: str,
    failure_fingerprint: str,
    error_classification: str,
    store: ProtocolDebugStore,
    streak_threshold: int,
) -> dict[str, Any] | None:
    """Create a TriggerRecord if streak threshold is met.

    Reads streak_count from failure_streaks (source of truth).
    Stores observed_bad_sha — the SHA present when threshold was crossed.
    Copies streak_count into ci_failure_events.streak_snapshot for history.

    Returns the new trigger record dict, or None if threshold not yet met.
    """
    # Read streak from source of truth (failure_streaks), not row count
    streak_row = await store.get_streak(repo=repo, branch=branch)
    streak_count = int(streak_row["streak_count"]) if streak_row else 0

    # Insert ci_failure_event with streak_snapshot copied from failure_streaks
    await store.insert_ci_failure_event(
        repo=repo,
        branch=branch,
        sha=sha,
        failure_fingerprint=failure_fingerprint,
        error_classification=error_classification,
        # streak_snapshot: historical copy from failure_streaks at this moment
        streak_snapshot=streak_count,
    )

    if streak_count < streak_threshold:
        return None

    # Create TriggerRecord with observed_bad_sha (NOT first_bad_sha)
    trigger = await store.insert_trigger_record(
        repo=repo,
        branch=branch,
        failure_fingerprint=failure_fingerprint,
        error_classification=error_classification,
        # observed_bad_sha: first SHA seen after threshold was crossed.
        # Phase 1 label. Rename to first_bad_sha only after bisect is available.
        observed_bad_sha=sha,
        streak_count_at_trigger=streak_count,
    )
    logger.info(
        "TriggerRecord created",
        extra={
            "trigger_record_id": trigger.get("id"),
            "repo": repo,
            "branch": branch,
            "streak_count": streak_count,
            "observed_bad_sha": sha,
        },
    )
    return trigger


__all__ = ["handle_trigger_record"]
