# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Canonical Kafka topic registry for the Intent Intelligence Framework.

Defines the 3 Intent Intelligence Kafka topics as a StrEnum. All topic names
follow ONEX canonical format: ``onex.{kind}.{producer}.{event-name}.v{n}``

This module is the single source of truth for Intent Intelligence topic names.
No hardcoded topic strings should appear in producer or consumer code; use
these enum values instead.

Topics:
    INTENT_DRIFT_DETECTED  -- Execution diverged from declared intent.
    INTENT_OUTCOME_LABELED -- Intent outcome labeled after completion.
    INTENT_PATTERN_PROMOTED -- Intent pattern promoted to learned patterns.

Note:
    The classified-intent topic (``onex.evt.omniintelligence.intent-classified.v1``)
    is produced directly by node_claude_hook_event_effect and lives in constants.py
    as ``TOPIC_SUFFIX_INTENT_CLASSIFIED_V1``. It is not part of this enum.

ONEX Compliance:
    - Topic names are immutable StrEnum values (no hardcoded strings elsewhere).
    - All `emitted_at` fields in envelope models must be injected by callers.
    - No datetime.now() defaults permitted.

Migration (OMN-3253):
    Previous topic names used ``intent`` as the producer segment instead of
    ``omniintelligence``. The old names are preserved as ``INTENT_TOPIC_ALIASES``
    for one release cycle to allow consumers to migrate.

Reference: OMN-2487
"""

from __future__ import annotations

from enum import Enum, unique

from omnibase_core.utils.util_str_enum_base import StrValueHelper


@unique
class IntentTopic(StrValueHelper, str, Enum):
    """Canonical Kafka topic names for the Intent Intelligence Framework.

    All topics use ``onex.evt.omniintelligence.*`` as the producer namespace
    (producer: ``omniintelligence``, kind: ``evt``).

    Values:
        INTENT_DRIFT_DETECTED: Fired when execution diverges from the declared
            intent class. Consumers may trigger alerts or model updates.
        INTENT_OUTCOME_LABELED: Fired when a session outcome is labeled as
            successful or failed. Used to update graph success rates.
        INTENT_PATTERN_PROMOTED: Fired when an intent-derived pattern is
            promoted into the learned-patterns corpus.
    """

    INTENT_DRIFT_DETECTED = "onex.evt.omniintelligence.intent-drift-detected.v1"
    """Execution diverged from declared intent."""

    INTENT_OUTCOME_LABELED = "onex.evt.omniintelligence.intent-outcome-labeled.v1"
    """Intent outcome labeled after completion."""

    INTENT_PATTERN_PROMOTED = "onex.evt.omniintelligence.intent-pattern-promoted.v1"
    """Intent pattern promoted to learned patterns."""


# OMN-3253: Migration aliases for one release cycle.
# Consumers should subscribe to BOTH old and new topic names during migration,
# then drop the old names in the next release.
INTENT_TOPIC_ALIASES: dict[str, str] = {
    "onex.evt.intent.drift.detected.v1": IntentTopic.INTENT_DRIFT_DETECTED.value,
    "onex.evt.intent.outcome.labeled.v1": IntentTopic.INTENT_OUTCOME_LABELED.value,
    "onex.evt.intent.pattern.promoted.v1": IntentTopic.INTENT_PATTERN_PROMOTED.value,
}
"""Map from deprecated topic name to canonical topic name (OMN-3253)."""


__all__ = ["IntentTopic", "INTENT_TOPIC_ALIASES"]
