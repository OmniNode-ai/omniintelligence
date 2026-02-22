# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""SQLAlchemy model for decision_records table.

Defines the persistence-layer representation of DecisionRecord events.
The database schema is declared here without a migration (migration freeze per
.migration_freeze). Schema must be created separately via provisioning tools.

Layer Separation:
    - Layer 1 (provenance): decision_id, decision_type, timestamp,
      candidates_considered, constraints_applied, scoring_breakdown,
      tie_breaker, selected_candidate, reproducibility_snapshot
    - Layer 2 (rationale): agent_rationale

The read API returns Layer 1 by default; Layer 2 is returned only when
``include_rationale=True`` is passed to the repository.

Ticket: OMN-2467
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table name constant
# ---------------------------------------------------------------------------

DECISION_RECORDS_TABLE = "decision_records"


# ---------------------------------------------------------------------------
# Enums for external contract surfaces (Kafka payloads / cross-process)
# ---------------------------------------------------------------------------


class DecisionType(str, Enum):
    """Decision classification types used in cross-process Kafka payloads.

    Per coding guidelines: "Use Enum for external contract surfaces and
    cross-process boundaries."
    """

    MODEL_SELECT = "model_select"
    """Selection of an AI model from a candidate set."""

    ROUTING = "routing"
    """Routing decision (e.g., agent selection)."""

    UNKNOWN = "unknown"
    """Unrecognised decision type — preserved for forward compatibility."""


class TieBreaker(str, Enum):
    """Tie-breaking rules applied when candidates score equally.

    Per coding guidelines: "Use Enum for external contract surfaces and
    cross-process boundaries."
    """

    ALPHABETICAL = "alphabetical"
    """Lexicographically first candidate wins."""

    FIRST = "first"
    """First candidate in list order wins."""

    UNKNOWN = "unknown"
    """Unrecognised tie-breaker — preserved for forward compatibility."""


def _parse_decision_type(value: str | None) -> str:
    """Map incoming string to a DecisionType value (forward-compatible)."""
    if value is None:
        return DecisionType.UNKNOWN.value
    try:
        return DecisionType(value).value
    except ValueError:
        return value  # preserve unknown values as-is for forward compatibility


def _parse_tie_breaker(value: str | None) -> str | None:
    """Map incoming string to a TieBreaker value (forward-compatible)."""
    if value is None:
        return None
    try:
        return TieBreaker(value).value
    except ValueError:
        return value  # preserve unknown values as-is for forward compatibility


# ---------------------------------------------------------------------------
# DecisionScore (per-candidate scoring breakdown)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionScoreRow:
    """Per-candidate scoring breakdown stored in the decision record.

    Attributes:
        candidate: Candidate name/identifier.
        score: Aggregate score for the candidate.
        breakdown: Per-metric score breakdown.
    """

    candidate: str
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "candidate": self.candidate,
            "score": self.score,
            "breakdown": self.breakdown,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionScoreRow:
        """Deserialize from dict."""
        return cls(
            candidate=data["candidate"],
            score=float(data["score"]),
            breakdown={str(k): float(v) for k, v in data.get("breakdown", {}).items()},
        )


# ---------------------------------------------------------------------------
# DecisionRecordRow (main persistence model)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionRecordRow:
    """Persistence-layer representation of a DecisionRecord.

    This dataclass represents a row in the ``decision_records`` table.
    It stores both Layer 1 (provenance) and Layer 2 (rationale) fields.

    Note:
        ``agent_rationale`` is Layer 2 and is stored but returned only when
        explicitly requested via ``include_rationale=True``.

    Attributes:
        decision_id: Unique identifier (UUID as string).
        decision_type: Decision classification (e.g., ``"model_select"``).
        timestamp: When the decision was made (UTC).
        candidates_considered: List of candidate names evaluated.
        constraints_applied: Map of constraint name → reason applied.
        scoring_breakdown: Per-candidate scoring details.
        tie_breaker: Tie-breaking rule applied (or None).
        selected_candidate: The winning candidate.
        agent_rationale: Optional Layer 2 rationale text (LLM explanation).
        reproducibility_snapshot: Runtime state snapshot for replay.
        stored_at: When this record was persisted.
    """

    decision_id: str
    decision_type: str
    timestamp: datetime
    candidates_considered: list[str]
    constraints_applied: dict[str, str]
    scoring_breakdown: list[DecisionScoreRow]
    tie_breaker: str | None
    selected_candidate: str
    agent_rationale: str | None
    reproducibility_snapshot: dict[str, str]
    stored_at: datetime

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_layer1_dict(self) -> dict[str, Any]:
        """Return Layer 1 (provenance) fields only.

        Does not include ``agent_rationale`` (Layer 2).
        """
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type,
            "timestamp": self.timestamp.isoformat(),
            "candidates_considered": self.candidates_considered,
            "constraints_applied": self.constraints_applied,
            "scoring_breakdown": [s.to_dict() for s in self.scoring_breakdown],
            "tie_breaker": self.tie_breaker,
            "selected_candidate": self.selected_candidate,
            "reproducibility_snapshot": self.reproducibility_snapshot,
            "stored_at": self.stored_at.isoformat(),
        }

    def to_full_dict(self) -> dict[str, Any]:
        """Return all fields including Layer 2 (agent_rationale)."""
        result = self.to_layer1_dict()
        result["agent_rationale"] = self.agent_rationale
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionRecordRow:
        """Deserialize from a dict (e.g., from DB row or JSON payload).

        Args:
            data: Dictionary with all DecisionRecordRow fields.

        Returns:
            DecisionRecordRow instance.
        """
        return cls(
            decision_id=str(data["decision_id"]),
            decision_type=_parse_decision_type(str(data["decision_type"])),
            timestamp=_parse_datetime(data["timestamp"]),
            candidates_considered=list(data.get("candidates_considered", [])),
            constraints_applied=dict(data.get("constraints_applied", {})),
            scoring_breakdown=[
                DecisionScoreRow.from_dict(s) for s in data.get("scoring_breakdown", [])
            ],
            tie_breaker=_parse_tie_breaker(data.get("tie_breaker")),
            selected_candidate=str(data["selected_candidate"]),
            agent_rationale=data.get("agent_rationale"),
            reproducibility_snapshot=dict(data.get("reproducibility_snapshot", {})),
            stored_at=_parse_datetime(data.get("stored_at", datetime.now(UTC))),
        )

    @classmethod
    def from_event_payload(
        cls,
        payload: dict[str, Any],
        stored_at: datetime,
        *,
        correlation_id: str | None = None,
    ) -> DecisionRecordRow:
        """Create a row from a Kafka event payload.

        Args:
            payload: Deserialized DecisionRecord JSON from Kafka message.
            stored_at: Timestamp when this record was persisted (injected by caller).
            correlation_id: Trace correlation ID for end-to-end tracing.

        Returns:
            DecisionRecordRow ready for storage.

        Raises:
            ValueError: If ``scoring_breakdown`` contains invalid JSON (schema
                corruption — must not be silently swallowed).
        """
        scoring_raw = payload.get("scoring_breakdown", [])
        if isinstance(scoring_raw, str):
            try:
                scoring_raw = json.loads(scoring_raw)
            except json.JSONDecodeError as exc:
                logger.error(
                    "Invalid scoring_breakdown JSON in DecisionRecord payload",
                    extra={"correlation_id": correlation_id},
                )
                msg = f"Invalid scoring_breakdown JSON: {exc}"
                raise ValueError(msg) from exc

        return cls(
            decision_id=str(payload["decision_id"]),
            decision_type=_parse_decision_type(str(payload["decision_type"])),
            timestamp=_parse_datetime(payload["timestamp"]),
            candidates_considered=list(payload.get("candidates_considered", [])),
            constraints_applied=dict(payload.get("constraints_applied", {})),
            scoring_breakdown=[DecisionScoreRow.from_dict(s) for s in scoring_raw],
            tie_breaker=_parse_tie_breaker(payload.get("tie_breaker")),
            selected_candidate=str(payload["selected_candidate"]),
            agent_rationale=payload.get("agent_rationale"),
            reproducibility_snapshot=dict(payload.get("reproducibility_snapshot", {})),
            stored_at=stored_at,
        )


# ---------------------------------------------------------------------------
# Cursor (pagination)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionRecordCursor:
    """Cursor for paginated queries over decision_records.

    Attributes:
        last_decision_id: The decision_id of the last record returned.
        last_stored_at: The stored_at of the last record returned.
    """

    last_decision_id: str
    last_stored_at: datetime


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_datetime(value: Any) -> datetime:
    """Parse datetime from ISO string or datetime object.

    Args:
        value: ISO-8601 string or datetime.

    Returns:
        datetime instance.

    Raises:
        ValueError: If value cannot be parsed as datetime.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    msg = f"Cannot parse datetime from {type(value).__name__}: {value!r}"
    raise ValueError(msg)


__all__ = [
    "DECISION_RECORDS_TABLE",
    "DecisionRecordCursor",
    "DecisionRecordRow",
    "DecisionScoreRow",
    "DecisionType",
    "TieBreaker",
]
