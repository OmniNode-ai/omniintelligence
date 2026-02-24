"""Canonical Kafka topic registry for the Intent Intelligence Framework.

Defines the 4 Intent Intelligence Kafka topics as a StrEnum. All topic names
follow ONEX canonical format: ``onex.{kind}.{producer}.{event-name}.v{n}``

This module is the single source of truth for Intent Intelligence topic names.
No hardcoded topic strings should appear in producer or consumer code; use
these enum values instead.

Topics:
    INTENT_CLASSIFIED      — Intent class assigned to a session prompt.
    INTENT_DRIFT_DETECTED  — Execution diverged from declared intent.
    INTENT_OUTCOME_LABELED — Intent outcome labeled after completion.
    INTENT_PATTERN_PROMOTED — Intent pattern promoted to learned patterns.

Consumers:
    - omnimemory: consumes INTENT_CLASSIFIED to update graph storage.
    - omniintelligence: publishes and consumes these topics internally.

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

    All 4 topics use ``onex.evt.intent.*`` as the producer namespace
    (producer: ``intent``, kind: ``evt``).

    Values:
        INTENT_CLASSIFIED: Fired when an intent class is assigned to a session
            prompt. Published by the intent classifier; consumed by omnimemory
            for graph storage and by analytics consumers.
        INTENT_DRIFT_DETECTED: Fired when execution diverges from the declared
            intent class. Consumers may trigger alerts or model updates.
        INTENT_OUTCOME_LABELED: Fired when a session outcome is labeled as
            successful or failed. Used to update graph success rates.
        INTENT_PATTERN_PROMOTED: Fired when an intent-derived pattern is
            promoted into the learned-patterns corpus.
    """

    INTENT_CLASSIFIED = "onex.evt.intent.classified.v1"
    """Intent class assigned to a session prompt."""

    INTENT_DRIFT_DETECTED = "onex.evt.intent.drift.detected.v1"
    """Execution diverged from declared intent."""

    INTENT_OUTCOME_LABELED = "onex.evt.intent.outcome.labeled.v1"
    """Intent outcome labeled after completion."""

    INTENT_PATTERN_PROMOTED = "onex.evt.intent.pattern.promoted.v1"
    """Intent pattern promoted to learned patterns."""


__all__ = ["IntentTopic"]
