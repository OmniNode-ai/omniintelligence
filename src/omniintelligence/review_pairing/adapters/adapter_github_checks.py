# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""GitHub Checks API annotations adapter for the Review Signal Adapters.

Parses GitHub Checks API annotation objects (from ``GET /repos/{owner}/{repo}/check-runs``
or ``GET /repos/{owner}/{repo}/check-runs/{check_run_id}/annotations``) and
converts each annotation into a ``ReviewFindingObserved`` event.

GitHub Checks annotation format::

    {
      "path": "src/foo/bar.py",
      "blob_href": "https://github.com/...",
      "start_line": 10,
      "end_line": 10,
      "start_column": null,
      "end_column": null,
      "annotation_level": "failure",
      "title": "Line too long",
      "message": "src/foo/bar.py:10:5: E501 Line too long (95 > 88 characters)",
      "raw_details": null
    }

Annotation level mapping:
    - ``failure`` → ``FindingSeverity.ERROR``
    - ``warning`` → ``FindingSeverity.WARNING``
    - ``notice`` → ``FindingSeverity.INFO``

Confidence tier: ``semi_deterministic`` (has file+line but may lack rule_id)

This adapter is a pure parser: it converts pre-fetched annotation dicts into
``ReviewFindingObserved`` events. HTTP fetching belongs in the Effect layer
(per ARCH-002: transport I/O must not appear in node source).

Usage::

    from omniintelligence.review_pairing.adapters.adapter_github_checks import parse_raw

    findings = parse_raw(annotations_list, repo="OmniNode-ai/omniintelligence",
                         pr_id=42, commit_sha="abc1234", check_run_name="Lint")

Reference: OMN-2542
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import uuid4

from omniintelligence.review_pairing.adapters.base import (
    SEMI_DETERMINISTIC,
    normalize_message,
    utcnow,
)
from omniintelligence.review_pairing.models import (
    FindingSeverity,
    ReviewFindingObserved,
)

logger = logging.getLogger(__name__)

_TOOL_NAME = "github-checks"
_UNKNOWN_VERSION = "unknown"

_LEVEL_MAP: dict[str, FindingSeverity] = {
    "failure": FindingSeverity.ERROR,
    "warning": FindingSeverity.WARNING,
    "notice": FindingSeverity.INFO,
}


def parse_raw(
    raw: str | list[dict[str, Any]],
    *,
    repo: str,
    pr_id: int,
    commit_sha: str,
    check_run_name: str = "github-checks",
    tool_version: str = _UNKNOWN_VERSION,
) -> list[ReviewFindingObserved]:
    """Parse GitHub Checks annotation objects into findings.

    Args:
        raw: Either a JSON string or an already-decoded list of annotation dicts
            from the GitHub Checks API.
        repo: Repository slug in ``owner/name`` format.
        pr_id: Pull request number.
        commit_sha: Git SHA at which the findings were observed.
        check_run_name: Name of the GitHub check run (e.g. ``"Lint"``,
            ``"Type Check"``). Used as part of the tool_name to disambiguate
            multiple check runs.
        tool_version: Version string, if known.

    Returns:
        List of ``ReviewFindingObserved`` events.
    """
    if isinstance(raw, str):
        try:
            data: list[dict[str, Any]] = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("github-checks adapter: failed to parse JSON input: %s", exc)
            return []
    else:
        data = raw

    if not isinstance(data, list):
        logger.warning(
            "github-checks adapter: expected JSON array, got %s", type(data).__name__
        )
        return []

    tool_name = (
        f"{_TOOL_NAME}/{check_run_name}"
        if check_run_name != "github-checks"
        else _TOOL_NAME
    )

    findings: list[ReviewFindingObserved] = []

    for idx, annotation in enumerate(data):
        if not isinstance(annotation, dict):
            logger.warning(
                "github-checks adapter[%d]: expected dict, got %s, skipping",
                idx,
                type(annotation).__name__,
            )
            continue
        finding = _parse_annotation(
            annotation,
            repo=repo,
            pr_id=pr_id,
            commit_sha=commit_sha,
            tool_name=tool_name,
            tool_version=tool_version,
            idx=idx,
        )
        if finding is not None:
            findings.append(finding)

    return findings


def _parse_annotation(
    annotation: dict[str, Any],
    *,
    repo: str,
    pr_id: int,
    commit_sha: str,
    tool_name: str,
    tool_version: str,
    idx: int,
) -> ReviewFindingObserved | None:
    """Parse a single GitHub Checks annotation into a ``ReviewFindingObserved``.

    Returns ``None`` on malformed/incomplete input.
    """
    try:
        file_path: str = str(annotation.get("path") or "")
        if not file_path:
            logger.warning("github-checks adapter[%d]: missing path, skipping", idx)
            return None

        annotation_level: str = str(
            annotation.get("annotation_level") or "notice"
        ).lower()
        severity = _LEVEL_MAP.get(annotation_level, FindingSeverity.INFO)

        start_line_val = annotation.get("start_line")
        end_line_val = annotation.get("end_line")
        line_start: int = (
            max(1, int(start_line_val)) if start_line_val is not None else 1
        )
        line_end: int | None = int(end_line_val) if end_line_val is not None else None
        if line_end is not None and line_end == line_start:
            line_end = None

        # GitHub Checks annotations often don't have a rule_id; use title or "github-checks:unknown"
        title: str = str(annotation.get("title") or "")
        raw_message: str = str(annotation.get("message") or title or "")

        # Attempt to extract rule_id from message (e.g., "E501" or "[return-value]")
        rule_match = re.search(r"\b([A-Z]\d{3,4}|[a-z-]+(?:-[a-z]+)+)\b", raw_message)
        rule_code = rule_match.group(1) if rule_match else "unknown"
        rule_id = f"github-checks:{rule_code}"

        normalized = normalize_message(raw_message, "github-checks")

        return ReviewFindingObserved(
            finding_id=uuid4(),
            repo=repo,
            pr_id=pr_id,
            rule_id=rule_id,
            severity=severity,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            tool_name=tool_name,
            tool_version=tool_version,
            normalized_message=normalized or raw_message or rule_id,
            raw_message=raw_message or rule_id,
            commit_sha_observed=commit_sha,
            observed_at=utcnow(),
        )

    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "github-checks adapter[%d]: failed to parse annotation: %s — item=%r",
            idx,
            exc,
            annotation,
        )
        return None


def get_confidence_tier() -> str:
    """Return the confidence tier for this adapter."""
    return SEMI_DETERMINISTIC
