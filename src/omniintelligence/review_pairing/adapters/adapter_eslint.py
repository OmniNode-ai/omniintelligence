# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ESLint JSON output adapter for the Review Signal Adapters.

Parses ``eslint --format json`` output and converts each message into a
``ReviewFindingObserved`` event.

ESLint JSON format::

    [
      {
        "filePath": "/absolute/path/src/foo.ts",
        "messages": [
          {
            "ruleId": "no-unused-vars",
            "severity": 2,
            "message": "'foo' is defined but never used.",
            "line": 10,
            "column": 5,
            "endLine": 10,
            "endColumn": 8,
            "fix": null
          }
        ],
        "errorCount": 1,
        "warningCount": 0
      }
    ]

Severity mapping:
    - ESLint ``severity: 2`` (error) → ``FindingSeverity.ERROR``
    - ESLint ``severity: 1`` (warning) → ``FindingSeverity.WARNING``
    - ESLint ``severity: 0`` (off) → skipped

Confidence tier: ``deterministic`` (rule_id = ``eslint:{ruleId}``, exact location)

Usage::

    from omniintelligence.review_pairing.adapters.adapter_eslint import parse_raw

    findings = parse_raw(eslint_json_string, repo="OmniNode-ai/omnidash",
                         pr_id=42, commit_sha="abc1234", repo_root="/workspace")

Reference: OMN-2542
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
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

_TOOL_NAME = "eslint"
_UNKNOWN_VERSION = "unknown"

_ESLINT_SEVERITY_MAP: dict[int, FindingSeverity] = {
    2: FindingSeverity.ERROR,
    1: FindingSeverity.WARNING,
}


def parse_raw(
    raw: str | list[dict[str, Any]],
    *,
    repo: str,
    pr_id: int,
    commit_sha: str,
    eslint_version: str = _UNKNOWN_VERSION,
    repo_root: str = "",
) -> list[ReviewFindingObserved]:
    """Parse ``eslint --format json`` output into findings.

    Args:
        raw: Either a JSON string (eslint stdout) or an already-decoded list
            of file result dicts.
        repo: Repository slug in ``owner/name`` format.
        pr_id: Pull request number.
        commit_sha: Git SHA at which the findings were observed.
        eslint_version: Version of eslint, if known.
        repo_root: Absolute path to the repository root, used to make
            ``filePath`` values relative. If empty, paths are used as-is.

    Returns:
        List of ``ReviewFindingObserved`` events.
    """
    if isinstance(raw, str):
        try:
            data: list[dict[str, Any]] = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("eslint adapter: failed to parse JSON input: %s", exc)
            return []
    else:
        data = raw

    if not isinstance(data, list):
        logger.warning(
            "eslint adapter: expected JSON array, got %s", type(data).__name__
        )
        return []

    findings: list[ReviewFindingObserved] = []

    for file_idx, file_result in enumerate(data):
        if not isinstance(file_result, dict):
            logger.warning(
                "eslint adapter: file_result[%d] is not a dict, skipping", file_idx
            )
            continue

        file_path_raw: str = str(file_result.get("filePath") or "")
        if not file_path_raw:
            logger.warning(
                "eslint adapter: file_result[%d] missing filePath, skipping", file_idx
            )
            continue

        # Make path relative to repo root if possible
        file_path = _relativize(file_path_raw, repo_root)

        messages = file_result.get("messages") or []
        if not isinstance(messages, list):
            continue

        for msg_idx, msg in enumerate(messages):
            finding = _parse_message(
                msg,
                file_path=file_path,
                repo=repo,
                pr_id=pr_id,
                commit_sha=commit_sha,
                eslint_version=eslint_version,
                label=f"file[{file_idx}].msg[{msg_idx}]",
            )
            if finding is not None:
                findings.append(finding)

    return findings


def _relativize(file_path: str, repo_root: str) -> str:
    """Make an absolute file path relative to repo_root."""
    if not repo_root:
        return file_path
    try:
        return str(Path(file_path).relative_to(repo_root))
    except ValueError:
        # Path is not under repo_root — use as-is
        return file_path


def _parse_message(
    msg: dict[str, Any],
    *,
    file_path: str,
    repo: str,
    pr_id: int,
    commit_sha: str,
    eslint_version: str,
    label: str,
) -> ReviewFindingObserved | None:
    """Parse a single ESLint message dict into a ``ReviewFindingObserved``.

    Returns ``None`` on malformed input or severity 0 (disabled rule).
    """
    try:
        severity_int: int = int(msg.get("severity") or 0)
        if severity_int not in _ESLINT_SEVERITY_MAP:
            # severity 0 = off (disabled rule output, should not appear but handle gracefully)
            return None

        severity = _ESLINT_SEVERITY_MAP[severity_int]
        rule_id_raw: str = str(msg.get("ruleId") or "unknown")
        raw_message: str = str(msg.get("message") or "")
        line_num: int = max(1, int(msg.get("line") or 1))
        end_line_val = msg.get("endLine")
        line_end: int | None = int(end_line_val) if end_line_val is not None else None

        # Normalize line_end to None for single-line findings
        if line_end is not None and line_end == line_num:
            line_end = None

        rule_id = f"eslint:{rule_id_raw}"
        normalized = normalize_message(raw_message, _TOOL_NAME)

        return ReviewFindingObserved(
            finding_id=uuid4(),
            repo=repo,
            pr_id=pr_id,
            rule_id=rule_id,
            severity=severity,
            file_path=file_path,
            line_start=line_num,
            line_end=line_end,
            tool_name=_TOOL_NAME,
            tool_version=eslint_version,
            normalized_message=normalized or raw_message or rule_id,
            raw_message=raw_message or rule_id,
            commit_sha_observed=commit_sha,
            observed_at=utcnow(),
        )

    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "eslint adapter %s: failed to parse message: %s — msg=%r", label, exc, msg
        )
        return None


def get_confidence_tier() -> str:
    """Return the confidence tier for this adapter."""
    return DETERMINISTIC
