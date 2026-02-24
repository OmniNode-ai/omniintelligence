# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Canonical Pydantic v2 event contracts for the Review-Fix Pairing system.

All four canonical event models are defined here and importable from the
single ``omniintelligence.review_pairing.models`` module.

Design decisions:
- All models use ``X | Y`` union syntax (PEP 604) — no ``Optional[T]``.
- All datetime fields are UTC-aware (``datetime`` with ``timezone.utc``).
- All models are frozen (immutable after construction) per repository invariant.
- All fields carry inline docstring-style descriptions via ``Field(description=...)``.
- Models pass ``mypy --strict``.

ONEX Compliance:
    Naming follows ``Model{Domain}{Purpose}`` convention.
    All models inherit from ``pydantic.BaseModel`` with ``frozen=True``.

Reference: OMN-2535
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum, unique
from uuid import UUID

from pydantic import BaseModel, Field


@unique
class FindingSeverity(str, Enum):
    """Severity level of a review finding.

    Values mirror standard static-analysis severity classifications used
    by linters (ruff, flake8, mypy) and SAST tools.
    """

    ERROR = "error"
    """Finding represents a definite bug or hard failure."""

    WARNING = "warning"
    """Finding represents a potential issue or style violation."""

    INFO = "info"
    """Informational finding with no immediate actionability."""

    HINT = "hint"
    """Lowest severity; hints that a refactor might be beneficial."""


@unique
class PairingType(str, Enum):
    """How a fix commit was associated with a finding.

    Used to distinguish high-confidence pairings (same-file, explicit
    autofix) from heuristic pairings (temporal proximity, same PR).
    """

    AUTOFIX = "autofix"
    """Tool generated the fix automatically (highest confidence)."""

    SAME_COMMIT = "same_commit"
    """Fix and finding resolution occurred in the same commit."""

    SAME_PR = "same_pr"
    """Fix commit is part of the same pull request as the finding."""

    TEMPORAL = "temporal"
    """Fix commit occurred within a configurable time window after finding."""

    INFERRED = "inferred"
    """Pairing was inferred via heuristic (lowest confidence)."""


class ReviewFindingObserved(BaseModel, frozen=True):
    """Event emitted when a review finding is captured from any review source.

    Published to ``onex.evt.review-pairing.finding-observed.v1`` whenever a
    linter, CI check, or GitHub Checks run surfaces a new diagnostic finding
    for a pull request.

    Attributes:
        finding_id: Globally unique identifier for this finding instance.
        repo: Repository slug in ``owner/name`` format (e.g. ``OmniNode-ai/omniintelligence``).
        pr_id: Pull request number (integer) within the repository.
        rule_id: Canonical rule identifier from the originating tool
            (e.g. ``ruff:E501``, ``mypy:return-value``, ``eslint:no-unused-vars``).
        severity: Severity level of the finding.
        file_path: Relative path to the file containing the finding.
        line_start: First line number of the finding (1-indexed).
        line_end: Last line number of the finding (1-indexed, inclusive).
            ``None`` for single-line findings.
        tool_name: Name of the tool that generated this finding
            (e.g. ``ruff``, ``mypy``, ``eslint``, ``github-checks``).
        tool_version: Version string of the tool at observation time.
        normalized_message: Tool-agnostic message normalised to remove
            line/column references and version-specific details, suitable
            for clustering across tool versions.
        raw_message: Verbatim message as emitted by the tool.
        commit_sha_observed: Git SHA of the commit at which the finding
            was observed. Used to correlate with fix commits.
        observed_at: UTC datetime when this event was generated.
    """

    finding_id: UUID = Field(
        description="Globally unique identifier for this finding instance.",
    )
    repo: str = Field(
        description="Repository slug in 'owner/name' format.",
        min_length=3,
    )
    pr_id: int = Field(
        description="Pull request number within the repository.",
        gt=0,
    )
    rule_id: str = Field(
        description=(
            "Canonical rule identifier from the originating tool "
            "(e.g. 'ruff:E501', 'mypy:return-value')."
        ),
        min_length=1,
    )
    severity: FindingSeverity = Field(
        description="Severity level of the finding.",
    )
    file_path: str = Field(
        description="Relative path to the file containing the finding.",
        min_length=1,
    )
    line_start: int = Field(
        description="First line number of the finding (1-indexed).",
        gt=0,
    )
    line_end: int | None = Field(
        default=None,
        description=(
            "Last line number of the finding (1-indexed, inclusive). "
            "None for single-line findings."
        ),
    )
    tool_name: str = Field(
        description="Name of the tool that generated this finding.",
        min_length=1,
    )
    tool_version: str = Field(
        description="Version string of the tool at observation time.",
        min_length=1,
    )
    normalized_message: str = Field(
        description=(
            "Tool-agnostic message normalised for clustering; "
            "excludes line/column references and version-specific details."
        ),
        min_length=1,
    )
    raw_message: str = Field(
        description="Verbatim message as emitted by the tool.",
        min_length=1,
    )
    commit_sha_observed: str = Field(
        description="Git SHA of the commit at which the finding was observed.",
        min_length=7,
        max_length=40,
    )
    observed_at: datetime = Field(
        description="UTC datetime when this event was generated.",
    )


class ReviewFixApplied(BaseModel, frozen=True):
    """Event emitted when a fix commit is applied for a known finding.

    Published to ``onex.evt.review-pairing.fix-applied.v1`` when a developer
    (or an automated tool) pushes a commit that is believed to address a
    previously observed finding.

    Attributes:
        fix_id: Globally unique identifier for this fix event.
        finding_id: Foreign key reference to the ``ReviewFindingObserved``
            event that this fix addresses.
        fix_commit_sha: Git SHA of the commit applying the fix.
        file_path: Relative path to the file modified by the fix.
        diff_hunks: Ordered list of unified-diff hunk strings for the fix.
            Each hunk is a string in standard ``@@ ... @@`` format.
        touched_line_range: Two-element list ``[start, end]`` representing
            the inclusive line range touched by the fix. Used for
            overlap detection against the original finding location.
        tool_autofix: ``True`` if the fix was generated by an automated
            tool (e.g. ``ruff --fix``, ``eslint --fix``); ``False`` if
            authored manually.
        applied_at: UTC datetime when the fix commit was observed.
    """

    fix_id: UUID = Field(
        description="Globally unique identifier for this fix event.",
    )
    finding_id: UUID = Field(
        description="Reference to the ReviewFindingObserved this fix addresses.",
    )
    fix_commit_sha: str = Field(
        description="Git SHA of the commit applying the fix.",
        min_length=7,
        max_length=40,
    )
    file_path: str = Field(
        description="Relative path to the file modified by the fix.",
        min_length=1,
    )
    diff_hunks: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered list of unified-diff hunk strings for the fix. "
            "Each hunk is in standard '@@ ... @@' format."
        ),
    )
    touched_line_range: tuple[int, int] = Field(
        description=(
            "Inclusive line range [start, end] touched by the fix. "
            "Used for overlap detection against the original finding location."
        ),
    )
    tool_autofix: bool = Field(
        description=(
            "True if the fix was generated by an automated tool "
            "(e.g. 'ruff --fix'); False if manually authored."
        ),
    )
    applied_at: datetime = Field(
        description="UTC datetime when the fix commit was observed.",
    )


class ReviewFindingResolved(BaseModel, frozen=True):
    """Event emitted when a finding disappearance is confirmed post-fix.

    Published to ``onex.evt.review-pairing.finding-resolved.v1`` by the
    Finding Disappearance Verifier node after a post-fix CI run confirms
    that a previously observed finding no longer appears.

    Attributes:
        resolution_id: Globally unique identifier for this resolution event.
        finding_id: Reference to the ``ReviewFindingObserved`` that was resolved.
        fix_commit_sha: Git SHA of the fix commit that caused the resolution.
        verified_at_commit_sha: Git SHA of the commit at which disappearance
            was confirmed (may differ from ``fix_commit_sha`` if additional
            commits were pushed before verification ran).
        ci_run_id: Identifier of the CI run that confirmed the resolution.
            Format is tool-specific (e.g. GitHub Actions run ID).
        resolved_at: UTC datetime when resolution was confirmed.
    """

    resolution_id: UUID = Field(
        description="Globally unique identifier for this resolution event.",
    )
    finding_id: UUID = Field(
        description="Reference to the ReviewFindingObserved that was resolved.",
    )
    fix_commit_sha: str = Field(
        description="Git SHA of the fix commit that caused the resolution.",
        min_length=7,
        max_length=40,
    )
    verified_at_commit_sha: str = Field(
        description=(
            "Git SHA at which disappearance was confirmed. "
            "May differ from fix_commit_sha if additional commits were pushed."
        ),
        min_length=7,
        max_length=40,
    )
    ci_run_id: str = Field(
        description=(
            "CI run identifier that confirmed the resolution. "
            "Format is tool-specific (e.g. GitHub Actions run ID as string)."
        ),
        min_length=1,
    )
    resolved_at: datetime = Field(
        description="UTC datetime when resolution was confirmed.",
    )


class FindingFixPair(BaseModel, frozen=True):
    """Confidence-scored pairing of a review finding and its fix.

    Produced by the Pairing Engine after joining ``ReviewFindingObserved``
    and ``ReviewFixApplied`` events. The ``confidence_score`` reflects how
    certain the engine is that the fix actually addresses the finding.

    Published to ``onex.evt.review-pairing.pair-created.v1``.

    Attributes:
        pair_id: Globally unique identifier for this pairing record.
        finding_id: Reference to the ``ReviewFindingObserved`` event.
        fix_commit_sha: Git SHA of the commit that applies the fix.
        diff_hunks: Copy of diff hunks from the associated ``ReviewFixApplied``
            event, preserved here for downstream pattern extraction.
        confidence_score: Float in ``[0.0, 1.0]`` representing how confident
            the pairing engine is that this fix addresses the finding.
            Scores below 0.5 are considered low-confidence and excluded from
            pattern promotion.
        disappearance_confirmed: ``True`` if a ``ReviewFindingResolved`` event
            has been received for this pairing; ``False`` otherwise.
        pairing_type: How the fix was associated with the finding.
        created_at: UTC datetime when this pairing was created.
    """

    pair_id: UUID = Field(
        description="Globally unique identifier for this pairing record.",
    )
    finding_id: UUID = Field(
        description="Reference to the ReviewFindingObserved event.",
    )
    fix_commit_sha: str = Field(
        description="Git SHA of the commit that applies the fix.",
        min_length=7,
        max_length=40,
    )
    diff_hunks: list[str] = Field(
        default_factory=list,
        description=(
            "Copy of diff hunks from the associated ReviewFixApplied event, "
            "preserved for downstream pattern extraction."
        ),
    )
    confidence_score: float = Field(
        description=(
            "Confidence in [0.0, 1.0] that this fix addresses the finding. "
            "Scores below 0.5 are excluded from pattern promotion."
        ),
        ge=0.0,
        le=1.0,
    )
    disappearance_confirmed: bool = Field(
        description=(
            "True if a ReviewFindingResolved event has been received "
            "for this pairing; False otherwise."
        ),
    )
    pairing_type: PairingType = Field(
        description="How the fix was associated with the finding.",
    )
    created_at: datetime = Field(
        description="UTC datetime when this pairing was created.",
    )
