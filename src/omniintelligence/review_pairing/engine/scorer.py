# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Confidence scoring model for the Review-Fix Pairing Engine.

Implements the weighted confidence model from the design doc:

Score contributions:
    +0.40  rule_id matches exactly (finding rule_id == diff rule_id)
    +0.30  diff removes flagged construct/token (line-overlap or token match)
    +0.20  finding disappears in later CI run (disappearance confirmed)
    +0.10  anchored to exact diff hunk (line_start in hunk line range)

Penalty contributions:
    -0.20  multiple commits touch same region (ambiguity penalty)
    -0.15  finding disappears without file modification
    -0.10  tool config change explains disappearance

The final score is clamped to [0.0, 1.0].
Pairs with score >= 0.75 are promoted; below threshold are stored but not promoted.

Reference: OMN-2551
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Score weights (per design doc)
# ---------------------------------------------------------------------------

SCORE_RULE_ID_MATCH = 0.40
"""rule_id from the diff context matches the finding rule_id exactly."""

SCORE_DIFF_REMOVES_TOKEN = 0.30
"""Diff removes a construct/token that is flagged by the finding's rule."""

SCORE_DISAPPEARANCE_CONFIRMED = 0.20
"""Finding does not reappear in the next CI run after the fix commit."""

SCORE_ANCHORED_TO_HUNK = 0.10
"""The finding's line_start falls within the modified lines of the diff hunk."""

PENALTY_AMBIGUOUS_COMMITS = -0.20
"""Multiple commits touch the same file/line region — ambiguity penalty."""

PENALTY_DISAPPEARS_WITHOUT_MOD = -0.15
"""Finding disappears without any modification to the file it was in."""

PENALTY_CONFIG_CHANGE = -0.10
"""A tool configuration file was modified in the same PR — finding may have
been suppressed by config rather than actually fixed."""

# Promotion threshold
PROMOTION_THRESHOLD = 0.75
"""Minimum confidence score for a pair to be promoted to a pattern candidate."""

# Formatter batch threshold
FORMATTER_BATCH_FILE_FRACTION = 0.80
"""If more than this fraction of a PR's files are touched by a single commit,
the commit is flagged as a formatter batch and excluded from per-rule extraction."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoringContext:
    """All signals available to the confidence scorer for one (finding, commit) pair.

    Attributes:
        rule_id_matched: Whether the finding's rule_id was found in the diff context.
        diff_removes_token: Whether the diff removes a token/construct flagged
            by the finding's rule.
        disappearance_confirmed: Whether a ``ReviewFindingResolved`` event was
            received for this finding after the candidate fix commit.
        anchored_to_hunk: Whether the finding's ``line_start`` falls within the
            modified lines of any hunk in the diff.
        ambiguous_commits: Whether more than one commit touches the same
            file + line region as the finding (ambiguity penalty trigger).
        disappears_without_mod: Whether the finding disappeared without any
            modification to the file it was reported in.
        config_change_detected: Whether a tool config file (e.g., ``pyproject.toml``,
            ``.eslintrc``, ``mypy.ini``) was modified in the same PR.
        candidate_commit_count: Total number of candidate commits evaluated for
            this finding. Used to detect formatter batches (>1 indicates ambiguity
            if they all touch the same region).
        is_formatter_batch: Whether the fix commit was flagged as a formatter batch
            (touches >80% of PR files). Formatter batch commits are excluded from
            per-rule transform extraction.
    """

    rule_id_matched: bool = False
    """rule_id from the diff context matches the finding rule_id exactly."""

    diff_removes_token: bool = False
    """Diff removes the flagged construct/token."""

    disappearance_confirmed: bool = False
    """Finding confirmed absent in the next CI run after the fix commit."""

    anchored_to_hunk: bool = False
    """Finding line_start falls within the modified hunk range."""

    ambiguous_commits: bool = False
    """Multiple commits touch the same file/line region."""

    disappears_without_mod: bool = False
    """Finding disappeared without file modification."""

    config_change_detected: bool = False
    """A tool config file was modified in the same PR."""

    candidate_commit_count: int = 1
    """Total candidate commits evaluated for this finding."""

    is_formatter_batch: bool = False
    """Commit touches >80% of PR files (formatter batch)."""


@dataclass
class ScoringResult:
    """Result of the confidence scoring model for one (finding, commit) pair.

    Attributes:
        raw_score: Unclamped score before clamping to [0.0, 1.0].
        confidence_score: Final clamped score in [0.0, 1.0].
        promoted: Whether the score meets the promotion threshold (>= 0.75).
        score_breakdown: Dict mapping signal name to contribution amount.
        is_formatter_batch: Whether the commit is a formatter batch.
    """

    raw_score: float
    confidence_score: float
    promoted: bool
    score_breakdown: dict[str, float] = field(default_factory=dict)
    is_formatter_batch: bool = False


class ConfidenceScorer:
    """Weighted confidence scorer for finding-fix pairs.

    Applies the scoring model from the design doc to produce a confidence
    score in [0.0, 1.0] for a (finding, commit) candidate pair.

    The scorer is stateless — all context is passed via ``ScoringContext``.
    """

    def score(self, ctx: ScoringContext) -> ScoringResult:
        """Compute a confidence score for the given scoring context.

        Args:
            ctx: All available signals for this (finding, commit) pair.

        Returns:
            ``ScoringResult`` with the final confidence score and breakdown.
        """
        breakdown: dict[str, float] = {}
        raw = 0.0

        # Positive signals
        if ctx.rule_id_matched:
            breakdown["rule_id_match"] = SCORE_RULE_ID_MATCH
            raw += SCORE_RULE_ID_MATCH

        if ctx.diff_removes_token:
            breakdown["diff_removes_token"] = SCORE_DIFF_REMOVES_TOKEN
            raw += SCORE_DIFF_REMOVES_TOKEN

        if ctx.disappearance_confirmed:
            breakdown["disappearance_confirmed"] = SCORE_DISAPPEARANCE_CONFIRMED
            raw += SCORE_DISAPPEARANCE_CONFIRMED

        if ctx.anchored_to_hunk:
            breakdown["anchored_to_hunk"] = SCORE_ANCHORED_TO_HUNK
            raw += SCORE_ANCHORED_TO_HUNK

        # Penalties
        if ctx.ambiguous_commits:
            breakdown["ambiguous_commits"] = PENALTY_AMBIGUOUS_COMMITS
            raw += PENALTY_AMBIGUOUS_COMMITS

        if ctx.disappears_without_mod:
            breakdown["disappears_without_mod"] = PENALTY_DISAPPEARS_WITHOUT_MOD
            raw += PENALTY_DISAPPEARS_WITHOUT_MOD

        if ctx.config_change_detected:
            breakdown["config_change_detected"] = PENALTY_CONFIG_CHANGE
            raw += PENALTY_CONFIG_CHANGE

        # Formatter batch: still score, but flag for exclusion from pattern extraction
        is_formatter_batch = ctx.is_formatter_batch

        # Clamp to [0.0, 1.0]
        confidence = max(0.0, min(1.0, raw))
        promoted = confidence >= PROMOTION_THRESHOLD and not is_formatter_batch

        logger.debug(
            "ConfidenceScorer: raw=%.3f clamped=%.3f promoted=%s breakdown=%s formatter_batch=%s",
            raw,
            confidence,
            promoted,
            breakdown,
            is_formatter_batch,
        )

        return ScoringResult(
            raw_score=raw,
            confidence_score=confidence,
            promoted=promoted,
            score_breakdown=breakdown,
            is_formatter_batch=is_formatter_batch,
        )


# ---------------------------------------------------------------------------
# Hunk intersection helpers
# ---------------------------------------------------------------------------


def parse_hunk_line_range(hunk: str) -> tuple[int, int] | None:
    """Parse the line range from a unified diff hunk header.

    Extracts the *new file* line range from ``@@ -a,b +c,d @@`` format.

    Args:
        hunk: A unified diff hunk string starting with ``@@``.

    Returns:
        Tuple ``(start, end)`` of the new-file line range, or ``None`` if
        the hunk header cannot be parsed.
    """
    match = re.search(
        r"\+(\d+)(?:,(\d+))?", hunk.split("@@")[1] if "@@" in hunk else ""
    )
    if not match:
        return None
    start = int(match.group(1))
    count = int(match.group(2)) if match.group(2) is not None else 1
    end = start + max(0, count - 1)
    return (start, end)


def line_in_hunk(line: int, hunk: str) -> bool:
    """Check if a line number falls within the range of a diff hunk.

    Args:
        line: Line number to check (1-indexed).
        hunk: Unified diff hunk string.

    Returns:
        ``True`` if ``line`` is within the hunk's new-file line range.
    """
    result = parse_hunk_line_range(hunk)
    if result is None:
        return False
    start, end = result
    return start <= line <= end


def is_anchored_to_diff(line_start: int, diff_hunks: list[str]) -> bool:
    """Check if a finding's line is anchored to any hunk in a diff.

    Args:
        line_start: Finding's start line (1-indexed).
        diff_hunks: List of unified diff hunk strings.

    Returns:
        ``True`` if ``line_start`` falls within any hunk's new-file range.
    """
    return any(line_in_hunk(line_start, hunk) for hunk in diff_hunks)


# ---------------------------------------------------------------------------
# Formatter batch detection
# ---------------------------------------------------------------------------


def is_formatter_batch_commit(
    files_touched_by_commit: set[str],
    total_pr_files: set[str],
) -> bool:
    """Detect if a commit is a formatter/mass-reformat batch.

    A commit is classified as a formatter batch if it touches more than
    ``FORMATTER_BATCH_FILE_FRACTION`` (80%) of the PR's files.

    Args:
        files_touched_by_commit: Set of file paths modified by the commit.
        total_pr_files: Set of all file paths modified across the entire PR.

    Returns:
        ``True`` if the commit is a formatter batch.
    """
    if not total_pr_files:
        return False
    fraction = len(files_touched_by_commit & total_pr_files) / len(total_pr_files)
    return fraction > FORMATTER_BATCH_FILE_FRACTION


# ---------------------------------------------------------------------------
# Tool config file detection
# ---------------------------------------------------------------------------

_CONFIG_FILE_PATTERNS = [
    re.compile(r"pyproject\.toml$"),
    re.compile(r"setup\.cfg$"),
    re.compile(r"\.eslintrc(\.(js|json|yml|yaml))?$"),
    re.compile(r"\.eslintignore$"),
    re.compile(r"mypy\.ini$"),
    re.compile(r"\.mypy\.ini$"),
    re.compile(r"ruff\.toml$"),
    re.compile(r"\.ruff\.toml$"),
    re.compile(r"tslint\.json$"),
    re.compile(r"tsconfig.*\.json$"),
    re.compile(r"\.flake8$"),
]


def has_config_change(files_in_pr: set[str]) -> bool:
    """Detect if any tool configuration file was modified in the PR.

    Args:
        files_in_pr: Set of file paths modified in the PR (basenames or relative paths).

    Returns:
        ``True`` if any file matches a known tool config pattern.
    """
    return any(
        any(pattern.search(f) for pattern in _CONFIG_FILE_PATTERNS) for f in files_in_pr
    )
