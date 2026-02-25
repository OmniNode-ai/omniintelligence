"""Canonical Kafka topic registry for the Intent Intelligence Framework.

Defines the 3 Intent Intelligence Kafka topics as a StrEnum. All topic names
follow ONEX canonical format: ``onex.{kind}.{producer}.{event-name}.v{n}``

This module is the single source of truth for Intent Intelligence topic names.
No hardcoded topic strings should appear in producer or consumer code; use
these enum values instead.

Topics:
    INTENT_DRIFT_DETECTED  — Execution diverged from declared intent.
    INTENT_OUTCOME_LABELED — Intent outcome labeled after completion.
    INTENT_PATTERN_PROMOTED — Intent pattern promoted to learned patterns.

Note:
    The classified-intent topic (``onex.evt.omniintelligence.intent-classified.v1``)
    is produced directly by node_claude_hook_event_effect and lives in constants.py
    as ``TOPIC_SUFFIX_INTENT_CLASSIFIED_V1``. It is not part of this enum.

ONEX Compliance:
    - Topic names are immutable StrEnum values (no hardcoded strings elsewhere).
    - All `emitted_at` fields in envelope models must be injected by callers.
    - No datetime.now() defaults permitted.

Reference: OMN-2487
"""

from __future__ import annotations

from enum import Enum, unique

from omnibase_core.utils.util_str_enum_base import StrValueHelper


@unique
class IntentTopic(StrValueHelper, str, Enum):
    """Canonical Kafka topic names for the Intent Intelligence Framework.

    All topics use ``onex.evt.intent.*`` as the producer namespace
    (producer: ``intent``, kind: ``evt``).

    Values:
        INTENT_DRIFT_DETECTED: Fired when execution diverges from the declared
            intent class. Consumers may trigger alerts or model updates.
        INTENT_OUTCOME_LABELED: Fired when a session outcome is labeled as
            successful or failed. Used to update graph success rates.
        INTENT_PATTERN_PROMOTED: Fired when an intent-derived pattern is
            promoted into the learned-patterns corpus.
    """

    INTENT_DRIFT_DETECTED = "onex.evt.intent.drift.detected.v1"
    """Execution diverged from declared intent."""

    INTENT_OUTCOME_LABELED = "onex.evt.intent.outcome.labeled.v1"
    """Intent outcome labeled after completion."""

    INTENT_PATTERN_PROMOTED = "onex.evt.intent.pattern.promoted.v1"
    """Intent pattern promoted to learned patterns."""


__all__ = ["IntentTopic"]
