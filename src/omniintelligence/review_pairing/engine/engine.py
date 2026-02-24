# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pairing Engine: Confidence-Scored Finding-to-Fix Join.

The ``PairingEngine`` is the core component of the Review-Fix Pairing system.
It joins ``ReviewFindingObserved`` records with candidate fix commits to produce
confidence-scored ``FindingFixPair`` records.

Architecture:
    - Pure computation: no Kafka or Postgres I/O (those belong in effect nodes)
    - Stateless: all context is passed in via function arguments
    - Idempotent: re-processing the same finding produces at most one pair record
    - Testable: all I/O is abstracted behind injected providers

Primary match key:
    ``(repo, pr_id, file_path, rule_id, normalized_message)``

Pairing types:
    - ``autofix``: tool_autofix=True on the fix
    - ``same_commit``: fix and finding observed at the same commit SHA
    - ``same_pr``: fix commit is in the same PR as the finding
    - ``temporal``: fix commit is within the configured time window
    - ``inferred``: heuristic match (lowest confidence)

Reference: OMN-2551
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from omniintelligence.review_pairing.engine.scorer import (
    ConfidenceScorer,
    ScoringContext,
    has_config_change,
    is_anchored_to_diff,
    is_formatter_batch_commit,
)
from omniintelligence.review_pairing.models import (
    FindingFixPair,
    PairingType,
    ReviewFindingObserved,
    ReviewFixApplied,
)

logger = logging.getLogger(__name__)

# Default temporal proximity window for pairing
DEFAULT_TEMPORAL_WINDOW_HOURS = 72

# Minimum confidence to store a pair (even unpromoted)
STORAGE_THRESHOLD = 0.0


@dataclass
class CandidateFix:
    """A candidate fix commit for evaluation against a finding.

    Attributes:
        fix: The ``ReviewFixApplied`` event for this fix commit.
        disappearance_confirmed: Whether a ``ReviewFindingResolved`` event
            confirmed the finding is gone after this fix.
        all_pr_files: Set of all files modified in the same PR as this fix.
            Used for formatter batch detection and config change detection.
    """

    fix: ReviewFixApplied
    disappearance_confirmed: bool = False
    all_pr_files: set[str] = field(default_factory=set)


@dataclass
class PairingResult:
    """Result of attempting to pair a finding with candidate fixes.

    Attributes:
        finding_id: UUID of the ``ReviewFindingObserved`` that was processed.
        pairs: List of ``FindingFixPair`` records produced (may be empty if no
            candidates met the storage threshold).
        promoted_pairs: Subset of ``pairs`` with ``confidence_score >= 0.75``
            and ``pairing_type != formatter_batch``.
        skipped_reason: If no pairs were produced, the reason why.
    """

    finding_id: UUID
    pairs: list[FindingFixPair]
    promoted_pairs: list[FindingFixPair]
    skipped_reason: str | None = None


class PairingEngine:
    """Core pairing engine: joins findings with fix commits.

    The engine is stateless. All I/O (Postgres, Kafka, GitHub API) is handled
    by the caller (effect nodes). The engine only performs pure computation.

    Usage::

        engine = PairingEngine()
        result = engine.pair(
            finding=finding_observed_event,
            candidates=[candidate_fix_1, candidate_fix_2],
        )
        for pair in result.promoted_pairs:
            # persist pair to Postgres, emit Kafka event
            ...

    Args:
        scorer: Optional custom ``ConfidenceScorer``. Defaults to the standard
            weighted model from the design doc.
        temporal_window_hours: Time window (hours) within which a fix commit
            must occur after a finding to be considered a candidate.
            Fixes outside this window are excluded.
    """

    def __init__(
        self,
        scorer: ConfidenceScorer | None = None,
        temporal_window_hours: int = DEFAULT_TEMPORAL_WINDOW_HOURS,
    ) -> None:
        self._scorer = scorer or ConfidenceScorer()
        self._temporal_window = timedelta(hours=temporal_window_hours)

    def pair(
        self,
        finding: ReviewFindingObserved,
        candidates: list[CandidateFix],
    ) -> PairingResult:
        """Pair a finding with its best candidate fix commit.

        For each candidate, the scorer evaluates all signals and produces a
        confidence score. The best-scoring candidate above the storage threshold
        is persisted. Only candidates above the promotion threshold (0.75) are
        marked as promoted.

        The engine is idempotent: if called twice with the same finding and
        candidates, it produces the same set of pairs (same UUIDs are not
        guaranteed, but the semantic content is identical).

        Args:
            finding: The ``ReviewFindingObserved`` event to pair.
            candidates: List of ``CandidateFix`` candidates to evaluate.

        Returns:
            ``PairingResult`` with all produced pairs.
        """
        if not candidates:
            logger.debug(
                "PairingEngine: no candidates for finding %s", finding.finding_id
            )
            return PairingResult(
                finding_id=finding.finding_id,
                pairs=[],
                promoted_pairs=[],
                skipped_reason="no_candidates",
            )

        # Filter to temporal window
        eligible = [
            c for c in candidates if self._within_temporal_window(finding, c.fix)
        ]
        if not eligible:
            logger.debug(
                "PairingEngine: all %d candidates outside temporal window for finding %s",
                len(candidates),
                finding.finding_id,
            )
            return PairingResult(
                finding_id=finding.finding_id,
                pairs=[],
                promoted_pairs=[],
                skipped_reason="all_candidates_outside_temporal_window",
            )

        # Check for ambiguity: multiple candidates touch the same file+line region
        ambiguous = self._is_ambiguous(finding, eligible)

        # Score each candidate
        scored: list[tuple[float, CandidateFix, ScoringContext]] = []
        for candidate in eligible:
            ctx = self._build_context(
                finding=finding,
                candidate=candidate,
                all_candidates=eligible,
                ambiguous=ambiguous,
            )
            result = self._scorer.score(ctx)
            if result.confidence_score >= STORAGE_THRESHOLD:
                scored.append((result.confidence_score, candidate, ctx))

        if not scored:
            logger.debug(
                "PairingEngine: no candidates met storage threshold for finding %s",
                finding.finding_id,
            )
            return PairingResult(
                finding_id=finding.finding_id,
                pairs=[],
                promoted_pairs=[],
                skipped_reason="below_storage_threshold",
            )

        # Sort by confidence descending, pick best
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_candidate, best_ctx = scored[0]

        pair = self._build_pair(
            finding=finding,
            candidate=best_candidate,
            confidence_score=best_score,
            ctx=best_ctx,
        )

        pairs = [pair]
        promoted = [
            p
            for p in pairs
            if p.confidence_score >= 0.75 and not best_ctx.is_formatter_batch
        ]

        logger.info(
            "PairingEngine: finding=%s paired with commit=%s score=%.3f promoted=%s",
            finding.finding_id,
            best_candidate.fix.fix_commit_sha,
            best_score,
            len(promoted) > 0,
        )

        return PairingResult(
            finding_id=finding.finding_id,
            pairs=pairs,
            promoted_pairs=promoted,
        )

    def _within_temporal_window(
        self,
        finding: ReviewFindingObserved,
        fix: ReviewFixApplied,
    ) -> bool:
        """Check if a fix commit is within the temporal window after the finding."""
        # Fix must occur after the finding was observed
        if fix.applied_at <= finding.observed_at:
            return False
        delta = fix.applied_at - finding.observed_at
        return delta <= self._temporal_window

    def _is_ambiguous(
        self,
        finding: ReviewFindingObserved,
        candidates: list[CandidateFix],
    ) -> bool:
        """Check if multiple candidates touch the same file+line region.

        Returns ``True`` if more than one candidate modifies the finding's
        file_path and intersects its line range.
        """
        touching = [
            c
            for c in candidates
            if c.fix.file_path == finding.file_path
            and self._line_ranges_overlap(
                finding.line_start,
                finding.line_end or finding.line_start,
                c.fix.touched_line_range[0],
                c.fix.touched_line_range[1],
            )
        ]
        return len(touching) > 1

    @staticmethod
    def _line_ranges_overlap(
        a_start: int,
        a_end: int,
        b_start: int,
        b_end: int,
    ) -> bool:
        """Check if two line ranges overlap (inclusive)."""
        return a_start <= b_end and b_start <= a_end

    def _build_context(
        self,
        finding: ReviewFindingObserved,
        candidate: CandidateFix,
        all_candidates: list[CandidateFix],
        ambiguous: bool,
    ) -> ScoringContext:
        """Build a ``ScoringContext`` for one (finding, candidate) pair."""
        fix = candidate.fix

        rule_id_matched = self._rule_id_matches(finding, fix)
        diff_removes_token = self._diff_removes_token(finding, fix)
        anchored = is_anchored_to_diff(finding.line_start, fix.diff_hunks)
        config_change = has_config_change(candidate.all_pr_files)
        disappears_without_mod = (
            candidate.disappearance_confirmed and fix.file_path != finding.file_path
        )
        formatter_batch = is_formatter_batch_commit(
            {fix.file_path},
            candidate.all_pr_files,
        )

        return ScoringContext(
            rule_id_matched=rule_id_matched,
            diff_removes_token=diff_removes_token,
            disappearance_confirmed=candidate.disappearance_confirmed,
            anchored_to_hunk=anchored,
            ambiguous_commits=ambiguous,
            disappears_without_mod=disappears_without_mod,
            config_change_detected=config_change,
            candidate_commit_count=len(all_candidates),
            is_formatter_batch=formatter_batch,
        )

    @staticmethod
    def _rule_id_matches(finding: ReviewFindingObserved, fix: ReviewFixApplied) -> bool:
        """Check if the finding's rule_id appears in the diff hunks.

        Looks for the bare rule code (e.g., ``E501``) or the full rule_id
        (e.g., ``ruff:E501``) in the diff hunk text.
        """
        # Extract the bare rule code from "tool:code" format
        rule_code = (
            finding.rule_id.split(":")[-1]
            if ":" in finding.rule_id
            else finding.rule_id
        )
        search_targets = {finding.rule_id, rule_code}

        return any(
            any(target in hunk for target in search_targets) for hunk in fix.diff_hunks
        )

    @staticmethod
    def _diff_removes_token(
        finding: ReviewFindingObserved, fix: ReviewFixApplied
    ) -> bool:
        """Check if the diff removes a line that overlaps with the finding's location.

        A simplified heuristic: looks for removed lines (``-`` prefix) in hunks
        that cover the finding's line_start.
        """
        finding_line = finding.line_start
        for hunk in fix.diff_hunks:
            lines = hunk.splitlines()
            if not lines:
                continue
            # Track current line number in the original file
            current_orig_line = None
            for line_text in lines:
                if line_text.startswith("@@"):
                    # Parse original file start: @@ -a,b +c,d @@
                    m = re.search(r"-(\d+)", line_text)
                    if m:
                        current_orig_line = int(m.group(1))
                    continue
                if current_orig_line is None:
                    continue
                if line_text.startswith("-"):
                    if current_orig_line == finding_line:
                        return True
                    current_orig_line += 1
                elif line_text.startswith("+"):
                    pass  # Added lines don't count toward original line numbers
                else:
                    current_orig_line += 1
        return False

    def _determine_pairing_type(
        self,
        finding: ReviewFindingObserved,
        candidate: CandidateFix,
        ctx: ScoringContext,
    ) -> PairingType:
        """Determine the pairing type for a (finding, candidate) pair."""
        fix = candidate.fix

        if fix.tool_autofix:
            return PairingType.AUTOFIX

        if fix.fix_commit_sha == finding.commit_sha_observed:
            return PairingType.SAME_COMMIT

        # same_pr: fix commit is in the same PR (we don't have explicit PR info here,
        # so we use temporal proximity as a proxy)
        delta = fix.applied_at - finding.observed_at
        if delta.total_seconds() < 3600:  # within 1 hour = likely same PR session
            return PairingType.SAME_PR

        if delta <= self._temporal_window:
            return PairingType.TEMPORAL

        return PairingType.INFERRED

    def _build_pair(
        self,
        finding: ReviewFindingObserved,
        candidate: CandidateFix,
        confidence_score: float,
        ctx: ScoringContext,
    ) -> FindingFixPair:
        """Build a ``FindingFixPair`` from a scored (finding, candidate) pair."""
        pairing_type = self._determine_pairing_type(finding, candidate, ctx)

        return FindingFixPair(
            pair_id=uuid4(),
            finding_id=finding.finding_id,
            fix_commit_sha=candidate.fix.fix_commit_sha,
            diff_hunks=list(candidate.fix.diff_hunks),
            confidence_score=round(confidence_score, 4),
            disappearance_confirmed=candidate.disappearance_confirmed,
            pairing_type=pairing_type,
            created_at=datetime.now(tz=UTC),
        )
