# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Data models for rationale mismatch detection.

Defines MismatchType, MismatchSeverity, and MismatchReport — the core
data structures for representing detected conflicts between Layer 2 rationale
and Layer 1 provenance in DecisionRecords.

Ticket: OMN-2472
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MismatchType(str, Enum):
    """Classification of the detected mismatch.

    Values:
        OMISSION: A constraint in Layer 1 was not mentioned in the rationale.
        FABRICATION: The rationale references a factor not present in Layer 1.
        WRONG_WINNER: The rationale claims a different winner than
            ``selected_candidate``.
    """

    OMISSION = "omission"
    FABRICATION = "fabrication"
    WRONG_WINNER = "wrong_winner"


class MismatchSeverity(str, Enum):
    """Severity of the detected mismatch.

    Values:
        WARNING: Informational — rationale omitted a constraint or factor.
            Not a direct contradiction.
        CRITICAL: Contradiction — rationale makes a false claim about the
            decision (fabricated factor, wrong winner).
    """

    WARNING = "warning"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# MismatchReport
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MismatchReport:
    """Report of a single detected mismatch between Layer 2 and Layer 1.

    Each report describes one conflict detected in a DecisionRecord.
    Multiple reports may be returned for a single record.

    Attributes:
        decision_id: ID of the DecisionRecord containing the mismatch.
        mismatch_type: Classification of the mismatch.
        severity: Severity level (WARNING or CRITICAL).
        quoted_text: The specific text from agent_rationale that triggered
            this mismatch (or empty string if N/A).
        layer1_reference: The specific Layer 1 field or value that conflicts
            with the rationale.
        description: Human-readable explanation of the mismatch.
        detected_at: When this mismatch was detected (injected by caller).
    """

    decision_id: str
    mismatch_type: MismatchType
    severity: MismatchSeverity
    quoted_text: str
    layer1_reference: str
    description: str
    detected_at: datetime

    def to_event_dict(self) -> dict[str, object]:
        """Serialize to a Kafka event payload dict.

        Returns a privacy-safe dict suitable for the
        ``onex.evt.omniintelligence.rationale-mismatch.v1`` topic.
        Excludes ``quoted_text`` and ``description`` to avoid leaking
        rationale content to broad-access topics.
        """
        return {
            "decision_id": self.decision_id,
            "mismatch_type": self.mismatch_type.value,
            "severity": self.severity.value,
            "layer1_reference": self.layer1_reference,
            "detected_at": self.detected_at.isoformat(),
        }

    def to_full_dict(self) -> dict[str, object]:
        """Serialize to a full dict including quoted_text for storage."""
        return {
            **self.to_event_dict(),
            "quoted_text": self.quoted_text,
            "description": self.description,
        }


__all__ = [
    "MismatchReport",
    "MismatchSeverity",
    "MismatchType",
]
