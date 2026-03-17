# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka topic constants for omniintelligence.

Defines canonical ONEX topic names for events produced and consumed by
the omniintelligence service as a typed StrEnum surface.

Topic naming convention:
    onex.{kind}.{producer}.{event-name}.v{n}

    kind: evt (observability, broad access) | cmd (commands, restricted)
    producer: omniintelligence

Privacy rule:
    - evt.* topics: preview-safe data only (no rationale, no snapshots)
    - cmd.* topics: full payload (restricted access)

Ticket: OMN-2472
"""

from __future__ import annotations

try:
    from enum import StrEnum  # Python 3.11+
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """Backport of StrEnum for Python 3.10."""

        @staticmethod
        def _generate_next_value_(name: str, *_args: object) -> str:
            return name.lower()


from omniintelligence.constants import (
    TOPIC_DECISION_RECORDED_CMD_V1,
    TOPIC_DECISION_RECORDED_EVT_V1,
    TOPIC_RATIONALE_MISMATCH_EVT_V1,
)


class OmniIntelligenceTopics(StrEnum):
    """Canonical Kafka topic constants for omniintelligence.

    All topics follow the ONEX naming convention:
        onex.{kind}.{producer}.{event-name}.v{n}

    String values are imported from ``omniintelligence.constants`` (single
    source of truth for all topic strings).

    Members:
        DECISION_RECORDED_EVT: Summary payload (decision_id, type, selected,
            count, has_rationale). Broad access — no sensitive data.
        DECISION_RECORDED_CMD: Full DecisionRecord payload including
            agent_rationale and snapshot. Restricted access.
        RATIONALE_MISMATCH_EVT: Mismatch event payload (decision_id,
            mismatch_type, severity, timestamp). Broad access — no rationale
            text in this topic.
    """

    DECISION_RECORDED_EVT = TOPIC_DECISION_RECORDED_EVT_V1
    DECISION_RECORDED_CMD = TOPIC_DECISION_RECORDED_CMD_V1
    RATIONALE_MISMATCH_EVT = TOPIC_RATIONALE_MISMATCH_EVT_V1


__all__ = [
    "OmniIntelligenceTopics",
]
