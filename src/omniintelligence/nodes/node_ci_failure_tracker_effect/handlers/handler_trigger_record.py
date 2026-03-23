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
from omniintelligence.protocols import ProtocolKafkaPublisher

logger = logging.getLogger(__name__)


async def handle_trigger_record(
    repo: str,
    branch: str,
    sha: str,
    failure_fingerprint: str,
    error_classification: str,
    store: ProtocolDebugStore,
    streak_threshold: int,
    *,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    correlation_id: str = "unknown",
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

    # OMN-6123: Fire-and-forget CI debug escalation event for omnidash
    await _emit_ci_debug_escalation(
        kafka_producer=kafka_producer,
        correlation_id=correlation_id,
        repo=repo,
        branch=branch,
        failure_type=error_classification,
        consecutive_failures=streak_count,
    )

    return trigger


async def _emit_ci_debug_escalation(
    *,
    kafka_producer: ProtocolKafkaPublisher | None,
    correlation_id: str,
    repo: str,
    branch: str,
    failure_type: str,
    consecutive_failures: int,
) -> None:
    """Fire-and-forget emission of CI debug escalation event.

    Silently logs and returns on any failure -- never blocks the caller.
    """
    if kafka_producer is None:
        return
    try:
        from datetime import UTC, datetime
        from uuid import uuid4

        from omniintelligence.constants import TOPIC_CI_DEBUG_ESCALATION_V1
        from omniintelligence.models.events.model_ci_debug_escalation_event import (
            ModelCiDebugEscalationEvent,
        )

        event = ModelCiDebugEscalationEvent(
            escalation_id=str(uuid4()),
            correlation_id=correlation_id,
            repo=repo,
            branch=branch,
            ci_run_url="",
            failure_type=failure_type or "unknown",
            consecutive_failures=consecutive_failures,
            escalated_at=datetime.now(UTC),
        )
        await kafka_producer.publish(
            topic=TOPIC_CI_DEBUG_ESCALATION_V1,
            key=f"{repo}/{branch}",
            value=event.model_dump(mode="json"),
        )
    except Exception:
        logger.warning(
            "Failed to emit CI debug escalation event (non-blocking)",
            exc_info=True,
        )


__all__ = ["handle_trigger_record"]
