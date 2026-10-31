# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka topic registry for the Review-Fix Pairing subsystem.

All topic names follow the ONEX canonical format::

    onex.{kind}.{producer}.{event-name}.v{n}

where:
    kind     — ``evt`` for domain events, ``cmd`` for commands
    producer — ``review-pairing`` for this subsystem
    event-name — kebab-case event name
    n        — integer version

Each value is read from ``review_pairing/contract.yaml``, the source of truth for topic names.

Topics:
    FINDING_OBSERVED  — A review finding was captured from any review source.
    FIX_APPLIED       — A fix commit was applied for a known finding.
    FINDING_RESOLVED  — A finding disappearance was confirmed post-fix.
    PAIR_CREATED      — A confidence-scored finding-fix pair was created.

Reference: OMN-2535
"""

from __future__ import annotations

from enum import StrEnum, unique

from omniintelligence.models.topics import ModelContractTopicReader

_evt = ModelContractTopicReader(nodes_package="omniintelligence").event


@unique
class ReviewPairingTopic(StrEnum):
    """Canonical Kafka topic names for the Review-Fix Pairing subsystem.

    All topics use ``onex.evt.review-pairing.*`` as the producer namespace.

    Values:
        FINDING_OBSERVED: Fired when a review finding is captured from any
            review source (linter, CI, GitHub Checks). Published by the Review
            Signal Adapters; consumed by the Pairing Engine.
        FIX_APPLIED: Fired when a fix commit is applied for a known finding.
            Published by the Review Signal Adapters; consumed by the Pairing Engine.
        FINDING_RESOLVED: Fired when a finding disappearance is confirmed by
            a post-fix CI run. Published by the Finding Disappearance Verifier;
            consumed by the Pairing Engine and Pattern Candidate Reducer.
        PAIR_CREATED: Fired when a confidence-scored finding-fix pair is created.
            Published by the Pairing Engine; consumed by the Pattern Candidate
            Reducer and metrics collectors.
    """

    FINDING_OBSERVED = _evt("review_pairing", "finding-observed")
    """A review finding was captured from any review source."""

    FIX_APPLIED = _evt("review_pairing", "fix-applied")
    """A fix commit was applied for a known finding."""

    FINDING_RESOLVED = _evt("review_pairing", "finding-resolved")
    """A finding disappearance was confirmed post-fix."""

    PAIR_CREATED = _evt("review_pairing", "pair-created")
    """A confidence-scored finding-fix pair was created."""

    CALIBRATION_RUN_COMPLETED = _evt("review_pairing", "calibration-run-completed")
    """A calibration run completed with metrics for a challenger model."""
