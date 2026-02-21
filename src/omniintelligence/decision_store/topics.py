# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka topic constants for DecisionRecord events.

Using ``StrEnum`` makes topic names part of the typed external contract
surface — consistent with omnibase_core's topic enum conventions.

Ticket: OMN-2467
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


class DecisionTopics(StrEnum):
    """Kafka topics consumed and produced by the decision_store module.

    Members:
        DECISION_RECORDED: The ``cmd`` topic on which DecisionRecord events
            are published by the model selector and consumed by the storage
            consumer.
    """

    DECISION_RECORDED = "onex.cmd.omniintelligence.decision-recorded.v1"


__all__ = [
    "DecisionTopics",
]
