# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka topic constants for omniintelligence.

Defines canonical ONEX topic names for events produced and consumed by
the omniintelligence service.

Topic naming convention:
    onex.{kind}.{producer}.{event-name}.v{n}

    kind: evt (observability, broad access) | cmd (commands, restricted)
    producer: omniintelligence

Privacy rule:
    - evt.* topics: preview-safe data only (no rationale, no snapshots)
    - cmd.* topics: full payload (restricted access)

Ticket: OMN-2472
"""


class OmniIntelligenceTopics:
    """Canonical topic name constants for omniintelligence.

    All topics use the ONEX naming convention:
        onex.{kind}.{producer}.{event-name}.v{n}

    Usage:
        >>> from omniintelligence.hooks.topics import OmniIntelligenceTopics
        >>> topic = OmniIntelligenceTopics.DECISION_RECORDED_EVT
    """

    # -----------------------------------------------------------------------
    # DecisionRecord topics (OMN-2465)
    # -----------------------------------------------------------------------

    DECISION_RECORDED_EVT: str = "onex.evt.omniintelligence.decision-recorded.v1"
    """Summary payload (decision_id, type, selected, count, has_rationale).
    Broad access — no sensitive data.
    """

    DECISION_RECORDED_CMD: str = "onex.cmd.omniintelligence.decision-recorded.v1"
    """Full DecisionRecord payload including agent_rationale and snapshot.
    Restricted access — omniintelligence service only.
    """

    # -----------------------------------------------------------------------
    # Rationale mismatch topics (OMN-2472)
    # -----------------------------------------------------------------------

    RATIONALE_MISMATCH_EVT: str = "onex.evt.omniintelligence.rationale-mismatch.v1"
    """Mismatch event payload: decision_id, mismatch_type, severity, timestamp.
    Broad access — no sensitive rationale text in this topic.
    """


__all__ = [
    "OmniIntelligenceTopics",
]
