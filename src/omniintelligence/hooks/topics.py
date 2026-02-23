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


class OmniIntelligenceTopics(StrEnum):
    """Canonical Kafka topic constants for omniintelligence.

    All topics follow the ONEX naming convention:
        onex.{kind}.{producer}.{event-name}.v{n}

    Members:
        DECISION_RECORDED_EVT: Summary payload (decision_id, type, selected,
            count, has_rationale). Broad access — no sensitive data.
        DECISION_RECORDED_CMD: Full DecisionRecord payload including
            agent_rationale and snapshot. Restricted access.
        RATIONALE_MISMATCH_EVT: Mismatch event payload (decision_id,
            mismatch_type, severity, timestamp). Broad access — no rationale
            text in this topic.
    """

    DECISION_RECORDED_EVT = "onex.evt.omniintelligence.decision-recorded.v1"
    DECISION_RECORDED_CMD = "onex.cmd.omniintelligence.decision-recorded.v1"
    RATIONALE_MISMATCH_EVT = "onex.evt.omniintelligence.rationale-mismatch.v1"


__all__ = [
    "OmniIntelligenceTopics",
]
