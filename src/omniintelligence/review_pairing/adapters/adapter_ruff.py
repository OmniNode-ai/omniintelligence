# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Ruff JSON output adapter for the Review Signal Adapters.

Parses ``ruff check --output-format json`` output and converts each
diagnostic into a ``ModelReviewFindingObserved`` event.

Ruff JSON format (single diagnostic):

.. code-block:: json

    {
      "code": "E501",
      "message": "Line too long (95 > 88 characters)",
      "url": "https://docs.astral.sh/ruff/rules/line-too-long",
      "filename": "src/foo/bar.py",
      "location": {"row": 10, "column": 1},
      "end_location": {"row": 10, "column": 95},
      "fix": null,
      "noqa_row": null
    }

Confidence tier: ``deterministic`` (rule_id = ``ruff:{code}``, exact location)

Usage::

    from omniintelligence.review_pairing.adapters.adapter_ruff import parse_raw

    findings = parse_raw(ruff_json_string, repo="OmniNode-ai/omniintelligence",
                         pr_id=42, commit_sha="abc1234")

Reference: OMN-2542
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from omniintelligence.review_pairing.adapters.base import (
    DETERMINISTIC,
    normalize_message,
    utcnow,
)
from omniintelligence.review_pairing.models import (
    EnumFindingSeverity,
    ModelReviewFindingObserved,
)

logger = logging.getLogger(__name__)

_TOOL_NAME = "ruff"

# Ruff does not provide severity in JSON output; all findings are treated as
# "error" since ruff --output-format json only surfaces violations that would
# cause a non-zero exit code (i.e., they are all rule violations).
_DEFAULT_SEVERITY = EnumFindingSeverity.ERROR

# Version sentinel used when ruff_version is not provided
_UNKNOWN_VERSION = "unknown"


def parse_raw(
    raw: str | list[dict[str, Any]],
    *,
    repo: str,
    pr_id: int,
    commit_sha: str,
    ruff_version: str = _UNKNOWN_VERSION,
) -> list[ModelReviewFindingObserved]:
    """Parse ``ruff check --output-format json`` output into findings.

    Args:
        raw: Either a JSON string (``ruff`` stdout) or an already-decoded list
            of diagnostic dicts.
        repo: Repository slug in ``owner/name`` format.
        pr_id: Pull request number.
        commit_sha: Git SHA at which the findings were observed.
        ruff_version: Version of the ruff tool, if known.

    Returns:
        List of ``ModelReviewFindingObserved`` events. Empty list if parsing fails
        or input contains no valid diagnostics.
    """
    data: list[Any]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("ruff adapter: failed to parse JSON input: %s", exc)
            return []
    else:
        data = list(raw)

    findings: list[ModelReviewFindingObserved] = []

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "ruff adapter[%d]: expected dict, got %s, skipping",
                idx,
                type(item).__name__,
            )
            continue
        finding = _parse_one(
            item,
            repo=repo,
            pr_id=pr_id,
            commit_sha=commit_sha,
            ruff_version=ruff_version,
            idx=idx,
        )
        if finding is not None:
            findings.append(finding)

    return findings


def _parse_one(
    item: dict[str, Any],
    *,
    repo: str,
    pr_id: int,
    commit_sha: str,
    ruff_version: str,
    idx: int,
) -> ModelReviewFindingObserved | None:
    """Parse a single ruff diagnostic dict into a ``ModelReviewFindingObserved``.

    Returns ``None`` on malformed/incomplete input (logs a warning).
    """
    try:
        code: str = str(item.get("code") or "UNKNOWN")
        raw_message: str = str(item.get("message") or "")
        filename: str = str(item.get("filename") or "")

        if not filename:
            logger.warning("ruff adapter[%d]: missing filename, skipping", idx)
            return None

        location = item.get("location") or {}
        end_location = item.get("end_location") or {}

        line_start: int = int(location.get("row") or 1)
        line_end_val = end_location.get("row")
        line_end: int | None = int(line_end_val) if line_end_val is not None else None

        # Normalize line_end to None if same as line_start (single-line finding)
        if line_end is not None and line_end == line_start:
            line_end = None

        rule_id = f"ruff:{code}"
        normalized = normalize_message(f"{code} {raw_message}", _TOOL_NAME)

        return ModelReviewFindingObserved(
            finding_id=uuid4(),
            repo=repo,
            pr_id=pr_id,
            rule_id=rule_id,
            severity=_DEFAULT_SEVERITY,
            file_path=filename,
            line_start=max(1, line_start),
            line_end=line_end,
            tool_name=_TOOL_NAME,
            tool_version=ruff_version,
            normalized_message=normalized or raw_message or rule_id,
            raw_message=raw_message or rule_id,
            commit_sha_observed=commit_sha,
            observed_at=utcnow(),
        )

    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "ruff adapter[%d]: failed to parse diagnostic: %s — item=%r", idx, exc, item
        )
        return None


def get_confidence_tier() -> str:
    """Return the confidence tier for this adapter."""
    return DETERMINISTIC
