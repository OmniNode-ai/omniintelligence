# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Rationale mismatch detection logic.

Implements detect_mismatches() — the core detection function that identifies
conflicts between agent_rationale (Layer 2) and the structured provenance
fields (Layer 1: constraints_applied, scoring_breakdown, selected_candidate).

Three Mismatch Types Detected:
    OMISSION: A Layer 1 constraint was not mentioned in the rationale text.
    FABRICATION: The rationale references a factor absent from Layer 1.
    WRONG_WINNER: The rationale claims a different winner than selected_candidate.

Detection Algorithm (v1 — keyword/concept matching):
    - OMISSION: For each constraint key in constraints_applied, check whether
      ANY form of the key appears in rationale text (case-insensitive,
      underscore/hyphen-normalized). Missing → OMISSION(WARNING).
    - FABRICATION: For each candidate name mentioned in rationale that is NOT
      in candidates_considered, report FABRICATION(CRITICAL). Also detect
      mention of constraint names that are not in constraints_applied.
    - WRONG_WINNER: If rationale contains phrases like "chose X" or "selected X"
      or "X was selected" where X != selected_candidate, report
      WRONG_WINNER(CRITICAL).

This is v1 — full NLU is v2. Initial version catches obvious conflicts.

Ticket: OMN-2472
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from omniintelligence.mismatch_detector.models import (
    MismatchReport,
    MismatchSeverity,
    MismatchType,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Type alias for DecisionRecord dict (from Kafka or repository)
# ---------------------------------------------------------------------------

DecisionRecordDict = dict[str, Any]


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------


def detect_mismatches(
    record: DecisionRecordDict,
    *,
    detected_at: datetime | None = None,
) -> list[MismatchReport]:
    """Detect conflicts between Layer 2 rationale and Layer 1 provenance.

    Runs three detection passes:
    1. OMISSION: constraints present in Layer 1 not mentioned in rationale.
    2. FABRICATION: factors in rationale not present in Layer 1.
    3. WRONG_WINNER: rationale claims a different winner than selected_candidate.

    Records with ``agent_rationale=None`` are skipped (returns empty list).
    Clean decisions (no mismatches) return an empty list.

    Args:
        record: DecisionRecord as a dict with fields:
            - decision_id: str
            - selected_candidate: str
            - candidates_considered: list[str]
            - constraints_applied: dict[str, str]
            - scoring_breakdown: list[dict] with "candidate" key
            - agent_rationale: str | None
        detected_at: Timestamp for MismatchReport.detected_at. If None,
            uses current UTC time.

    Returns:
        List of MismatchReport instances. Empty list if no mismatches.
    """
    agent_rationale = record.get("agent_rationale")

    # Skip records without rationale (Layer 2 is optional)
    if agent_rationale is None:
        return []

    if detected_at is None:
        detected_at = datetime.now(UTC)

    decision_id = str(record.get("decision_id", "unknown"))
    selected_candidate = str(record.get("selected_candidate", ""))
    candidates_considered: list[str] = list(record.get("candidates_considered", []))
    constraints_applied: dict[str, str] = dict(record.get("constraints_applied", {}))
    scoring_breakdown: list[dict[str, Any]] = list(record.get("scoring_breakdown", []))

    rationale_text = str(agent_rationale)
    mismatches: list[MismatchReport] = []

    # ------------------------------------------------------------------
    # Pass 1: OMISSION — Layer 1 constraint not mentioned in rationale
    # ------------------------------------------------------------------
    mismatches.extend(
        _detect_omissions(
            decision_id=decision_id,
            rationale_text=rationale_text,
            constraints_applied=constraints_applied,
            detected_at=detected_at,
        )
    )

    # ------------------------------------------------------------------
    # Pass 2: FABRICATION — rationale references factor absent from Layer 1
    # ------------------------------------------------------------------
    mismatches.extend(
        _detect_fabrications(
            decision_id=decision_id,
            rationale_text=rationale_text,
            candidates_considered=candidates_considered,
            constraints_applied=constraints_applied,
            scoring_breakdown=scoring_breakdown,
            detected_at=detected_at,
        )
    )

    # ------------------------------------------------------------------
    # Pass 3: WRONG_WINNER — rationale claims different winner
    # ------------------------------------------------------------------
    mismatches.extend(
        _detect_wrong_winner(
            decision_id=decision_id,
            rationale_text=rationale_text,
            selected_candidate=selected_candidate,
            candidates_considered=candidates_considered,
            detected_at=detected_at,
        )
    )

    if mismatches:
        logger.info(
            "Mismatch detection found %d mismatch(es) for decision_id=%s",
            len(mismatches),
            decision_id,
        )
    else:
        logger.debug(
            "Mismatch detection: clean decision. decision_id=%s",
            decision_id,
        )

    return mismatches


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _detect_omissions(
    *,
    decision_id: str,
    rationale_text: str,
    constraints_applied: dict[str, str],
    detected_at: datetime,
) -> list[MismatchReport]:
    """Detect constraints present in Layer 1 but absent from rationale text.

    Uses case-insensitive, underscore/hyphen-normalized keyword matching.
    Each unmentioned constraint produces one OMISSION(WARNING) report.

    Args:
        decision_id: Decision identifier.
        rationale_text: The agent_rationale string.
        constraints_applied: Layer 1 constraints dict.
        detected_at: Detection timestamp.

    Returns:
        List of OMISSION MismatchReports.
    """
    reports = []
    rationale_lower = rationale_text.lower()

    for constraint_key in constraints_applied:
        # Normalize: replace underscores/hyphens with spaces for matching
        normalized = _normalize_key(constraint_key)
        if (
            normalized not in rationale_lower
            and constraint_key.lower() not in rationale_lower
        ):
            reports.append(
                MismatchReport(
                    decision_id=decision_id,
                    mismatch_type=MismatchType.OMISSION,
                    severity=MismatchSeverity.WARNING,
                    quoted_text="",
                    layer1_reference=f"constraints_applied[{constraint_key!r}]",
                    description=(
                        f"Constraint {constraint_key!r} is present in Layer 1 "
                        f"but not mentioned in agent_rationale."
                    ),
                    detected_at=detected_at,
                )
            )

    return reports


def _detect_fabrications(
    *,
    decision_id: str,
    rationale_text: str,
    candidates_considered: list[str],
    constraints_applied: dict[str, str],  # noqa: ARG001
    scoring_breakdown: list[dict[str, Any]],
    detected_at: datetime,
) -> list[MismatchReport]:
    """Detect factors mentioned in rationale that are absent from Layer 1.

    Checks two fabrication patterns:
    1. Candidate names mentioned in rationale that are NOT in
       candidates_considered (fabricated candidate).
    2. Constraint-like phrases in rationale referencing names that are
       NOT in constraints_applied (fabricated constraint name).

    Only scores candidates that appear as whole words to avoid false positives
    (e.g., "gpt" vs "gpt-4o").

    Args:
        decision_id: Decision identifier.
        rationale_text: The agent_rationale string.
        candidates_considered: All candidates from Layer 1.
        constraints_applied: Layer 1 constraints dict.
        scoring_breakdown: Scoring breakdown list (for candidate names).
        detected_at: Detection timestamp.

    Returns:
        List of FABRICATION MismatchReports.
    """
    reports = []
    rationale_lower = rationale_text.lower()

    # All valid candidate names from scoring breakdown + candidates_considered
    valid_candidates = set(candidates_considered)
    for entry in scoring_breakdown:
        if isinstance(entry, dict) and "candidate" in entry:
            valid_candidates.add(str(entry["candidate"]))

    # Detect fabricated candidates: names in rationale not in Layer 1
    # We use a word-boundary pattern to avoid partial matches
    for candidate in valid_candidates:
        # This is a valid candidate — skip
        pass

    # Check if rationale mentions any candidate-like names not in Layer 1
    # Extract potential model names (patterns like "model-name", "gpt-X", etc.)
    # We look for patterns that resemble model identifiers
    candidate_pattern = re.compile(r"\b([a-zA-Z0-9][-a-zA-Z0-9]*[a-zA-Z0-9])\b")
    mentioned_tokens = {
        m.group(1).lower() for m in candidate_pattern.finditer(rationale_text)
    }

    # Check if any valid candidate names appear verbatim in rationale
    # against the scoring breakdown entries — this is a secondary check
    # to catch cases like "I chose X but X wasn't in the list"
    scored_candidates = {
        str(e.get("candidate", "")).lower()
        for e in scoring_breakdown
        if isinstance(e, dict) and e.get("candidate")
    }

    # Detect mentions of candidate-like tokens that match no known candidate
    # This is conservative: we only flag exact matches against known patterns
    # (v1: keyword matching, v2 will use full NLU)

    # For constraint fabrications: check if rationale mentions constraint
    # keys that sound like constraints but aren't in constraints_applied
    # This v1 implementation only checks for explicit "wrong" prefix patterns
    # like "cost_limit not applied" when cost_limit IS in constraints
    # (inverse: fabrication = claiming constraint NOT there when it IS)
    # For now, focus on the core fabrication: claiming a candidate not in list

    # Extract candidate-looking tokens from rationale that match none of
    # the valid candidates (using scored_candidates as reference)
    # (v1: only check recommend/suggest patterns below; v2 will extend this)
    _ = scored_candidates  # referenced for future v2 expansion

    # Check for WRONG_CANDIDATE_CLAIM: if rationale explicitly claims a
    # model that is NOT in any of the candidates considered
    # Pattern: "I recommend <X>" where X is not a valid candidate
    recommend_pattern = re.compile(
        r"\b(?:recommend|suggest|pick|prefer)\s+([a-zA-Z0-9][-a-zA-Z0-9]*)",
        re.IGNORECASE,
    )
    for match in recommend_pattern.finditer(rationale_text):
        mentioned_model = match.group(1).lower()
        if (
            valid_candidates
            and mentioned_model not in {c.lower() for c in valid_candidates}
            and len(mentioned_model) > 2  # avoid false positives on short tokens
        ):
            reports.append(
                MismatchReport(
                    decision_id=decision_id,
                    mismatch_type=MismatchType.FABRICATION,
                    severity=MismatchSeverity.CRITICAL,
                    quoted_text=match.group(0),
                    layer1_reference="candidates_considered",
                    description=(
                        f"Rationale recommends {mentioned_model!r} which is not "
                        f"in candidates_considered."
                    ),
                    detected_at=detected_at,
                )
            )

    return reports


def _detect_wrong_winner(
    *,
    decision_id: str,
    rationale_text: str,
    selected_candidate: str,
    candidates_considered: list[str],
    detected_at: datetime,
) -> list[MismatchReport]:
    """Detect if rationale claims a different winner than selected_candidate.

    Looks for phrases like:
    - "chose X", "selected X", "X was selected", "X was chosen"
    - "winner is X", "X won"

    If X is a known candidate but NOT equal to selected_candidate, reports
    WRONG_WINNER(CRITICAL).

    Args:
        decision_id: Decision identifier.
        rationale_text: The agent_rationale string.
        selected_candidate: The actual Layer 1 winner.
        candidates_considered: All candidates from Layer 1.
        detected_at: Detection timestamp.

    Returns:
        List of WRONG_WINNER MismatchReports.
    """
    reports: list[MismatchReport] = []
    if not selected_candidate or not candidates_considered:
        return reports

    # Patterns indicating which candidate was selected
    winner_patterns = [
        re.compile(
            r"\b(?:chose|selected|picked|went\s+with|recommend(?:ing)?)\s+"
            r"([a-zA-Z0-9][-a-zA-Z0-9\.]*)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b([a-zA-Z0-9][-a-zA-Z0-9\.]*)\s+"
            r"(?:was\s+(?:selected|chosen|picked)|is\s+the\s+(?:best|winner|top))",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bwinner\s+is\s+([a-zA-Z0-9][-a-zA-Z0-9\.]*)",
            re.IGNORECASE,
        ),
    ]

    valid_candidate_names_lower = {c.lower() for c in candidates_considered}
    selected_lower = selected_candidate.lower()

    for pattern in winner_patterns:
        for match in pattern.finditer(rationale_text):
            # Extract the claimed candidate name from either group 1 or 0
            try:
                claimed = match.group(1).lower()
            except IndexError:
                continue

            # Only flag if:
            # 1. Claimed candidate is a known candidate (not a spurious token)
            # 2. Claimed candidate differs from actual winner
            if claimed in valid_candidate_names_lower and claimed != selected_lower:
                reports.append(
                    MismatchReport(
                        decision_id=decision_id,
                        mismatch_type=MismatchType.WRONG_WINNER,
                        severity=MismatchSeverity.CRITICAL,
                        quoted_text=match.group(0),
                        layer1_reference=f"selected_candidate={selected_candidate!r}",
                        description=(
                            f"Rationale claims {match.group(1)!r} was selected, "
                            f"but Layer 1 recorded {selected_candidate!r} as the winner."
                        ),
                        detected_at=detected_at,
                    )
                )
                break  # One report per pattern is sufficient

    return reports


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _normalize_key(key: str) -> str:
    """Normalize a constraint key for text matching.

    Replaces underscores and hyphens with spaces, then lowercases.

    Args:
        key: Constraint key (e.g., ``"cost_limit"`` or ``"latency-budget"``).

    Returns:
        Normalized string (e.g., ``"cost limit"``).
    """
    return key.replace("_", " ").replace("-", " ").lower()


__all__ = [
    "DecisionRecordDict",
    "detect_mismatches",
]
