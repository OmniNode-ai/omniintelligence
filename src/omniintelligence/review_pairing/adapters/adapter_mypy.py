# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""mypy text output adapter for the Review Signal Adapters.

Parses mypy text output (default format) and converts each diagnostic
into a ``ReviewFindingObserved`` event.

mypy output format::

    src/foo/bar.py:10: error: Incompatible return value type [return-value]
    src/foo/bar.py:20: note: Revealed type is 'builtins.int'
    Found 1 error in 1 file (checked 3 source files)

Only ``error`` and ``warning`` severity lines are ingested; ``note`` lines
are skipped as they are annotations on errors, not standalone findings.

Confidence tier: ``deterministic`` (rule_id = ``mypy:{error_code}``, exact location)

Usage::

    from omniintelligence.review_pairing.adapters.adapter_mypy import parse_raw

    findings = parse_raw(mypy_output_text, repo="OmniNode-ai/omniintelligence",
                         pr_id=42, commit_sha="abc1234")

Reference: OMN-2542
"""

from __future__ import annotations

import logging
import re
from uuid import uuid4

from omniintelligence.review_pairing.adapters.base import (
    DETERMINISTIC,
    normalize_message,
    utcnow,
)
from omniintelligence.review_pairing.models import (
    FindingSeverity,
    ReviewFindingObserved,
)

logger = logging.getLogger(__name__)

_TOOL_NAME = "mypy"
_UNKNOWN_VERSION = "unknown"

# Regex matching mypy diagnostic lines:
#   file.py:LINE: SEVERITY: MESSAGE [error-code]
#   file.py:LINE:COL: SEVERITY: MESSAGE [error-code]
# The error code in brackets is optional.
_LINE_RE = re.compile(
    r"^(?P<file>[^:]+)"  # filename (no colons)
    r":(?P<line>\d+)"  # :LINE
    r"(?::\d+)?"  # optional :COL
    r":\s*(?P<severity>error|warning|note)"  # : severity
    r":\s*(?P<message>.+?)"  # : message
    r"(?:\s*\[(?P<code>[^\]]+)\])?$"  # optional [error-code]
)

_SEVERITY_MAP: dict[str, FindingSeverity] = {
    "error": FindingSeverity.ERROR,
    "warning": FindingSeverity.WARNING,
    # "note" is intentionally excluded — notes are skipped
}


def parse_raw(
    raw: str,
    *,
    repo: str,
    pr_id: int,
    commit_sha: str,
    mypy_version: str = _UNKNOWN_VERSION,
) -> list[ReviewFindingObserved]:
    """Parse mypy text output into findings.

    Args:
        raw: mypy stdout text (default output format, not ``--output json``).
        repo: Repository slug in ``owner/name`` format.
        pr_id: Pull request number.
        commit_sha: Git SHA at which the findings were observed.
        mypy_version: Version of the mypy tool, if known.

    Returns:
        List of ``ReviewFindingObserved`` events. Empty list if parsing fails
        or input contains no valid diagnostics.
    """
    if not isinstance(raw, str):
        logger.warning("mypy adapter: expected str input, got %s", type(raw).__name__)
        return []

    findings: list[ReviewFindingObserved] = []

    for idx, line in enumerate(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        finding = _parse_line(
            line,
            repo=repo,
            pr_id=pr_id,
            commit_sha=commit_sha,
            mypy_version=mypy_version,
            idx=idx,
        )
        if finding is not None:
            findings.append(finding)

    return findings


def _parse_line(
    line: str,
    *,
    repo: str,
    pr_id: int,
    commit_sha: str,
    mypy_version: str,
    idx: int,
) -> ReviewFindingObserved | None:
    """Parse a single mypy output line into a ``ReviewFindingObserved``.

    Returns ``None`` for note-level lines, summary lines, and parse failures.
    """
    match = _LINE_RE.match(line)
    if not match:
        # Not a diagnostic line (e.g., summary "Found N errors in M files")
        return None

    severity_str = match.group("severity")
    if severity_str not in _SEVERITY_MAP:
        # Skip "note" level
        return None

    severity = _SEVERITY_MAP[severity_str]
    filename = match.group("file").strip()
    line_num_str = match.group("line")
    raw_message = match.group("message").strip()
    error_code = match.group("code")

    if not filename:
        logger.warning("mypy adapter[%d]: empty filename, skipping", idx)
        return None

    try:
        line_num = max(1, int(line_num_str))
    except ValueError:
        logger.warning(
            "mypy adapter[%d]: invalid line number %r, skipping", idx, line_num_str
        )
        return None

    # Build rule_id: "mypy:return-value" or "mypy:misc" if no error code
    rule_id = f"mypy:{error_code}" if error_code else "mypy:misc"

    normalized = normalize_message(raw_message, _TOOL_NAME)

    try:
        return ReviewFindingObserved(
            finding_id=uuid4(),
            repo=repo,
            pr_id=pr_id,
            rule_id=rule_id,
            severity=severity,
            file_path=filename,
            line_start=line_num,
            line_end=None,  # mypy reports single-line errors
            tool_name=_TOOL_NAME,
            tool_version=mypy_version,
            normalized_message=normalized or raw_message or rule_id,
            raw_message=raw_message or rule_id,
            commit_sha_observed=commit_sha,
            observed_at=utcnow(),
        )
    except (ValueError, TypeError) as exc:
        logger.warning(
            "mypy adapter[%d]: failed to build finding: %s — line=%r", idx, exc, line
        )
        return None


def get_confidence_tier() -> str:
    """Return the confidence tier for this adapter."""
    return DETERMINISTIC
