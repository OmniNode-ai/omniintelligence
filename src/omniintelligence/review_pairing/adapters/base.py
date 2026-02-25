# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Shared utilities for Review Signal Adapters.

Provides:
- Confidence tier constants
- Common normalization helpers
- Shared type aliases

All adapters must be stateless pure functions:
    parse_raw(raw: str | dict) -> list[ReviewFindingObserved]

Reference: OMN-2542
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Confidence Tier
# ---------------------------------------------------------------------------

ConfidenceTier = Literal["deterministic", "semi_deterministic", "probabilistic"]
"""Confidence tier for a review finding adapter.

deterministic     — Tool produces rule_id + exact location (ruff, mypy, eslint).
semi_deterministic — Tool produces structured output but location may be approximate
                    (GitHub Checks annotations with file+line but no rule_id).
probabilistic      — Unanchored natural language comments (AI reviewers, humans).
"""

DETERMINISTIC: ConfidenceTier = "deterministic"
SEMI_DETERMINISTIC: ConfidenceTier = "semi_deterministic"
PROBABILISTIC: ConfidenceTier = "probabilistic"


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def normalize_message(raw_message: str, tool_name: str) -> str:
    """Strip tool-specific location references from a raw message.

    Removes patterns like:
    - ``file.py:10:5:`` prefixes
    - ``(col 5)`` suffixes
    - Tool version strings like ``(mypy 1.11.0)``

    Args:
        raw_message: Verbatim message as emitted by the tool.
        tool_name: Name of the tool (used for tool-specific stripping).

    Returns:
        Normalized message suitable for clustering.
    """
    msg = raw_message.strip()

    # Strip leading file:line:col: prefix (e.g. "src/foo.py:10:5: E501 ...")
    msg = re.sub(r"^[^\s]+:\d+:\d+:\s*", "", msg)

    # Strip leading file:line: prefix (e.g. "src/foo.py:10: error: ...")
    msg = re.sub(r"^[^\s]+:\d+:\s*", "", msg)

    # Strip "(col N)" suffixes
    msg = re.sub(r"\s*\(col\s+\d+\)", "", msg)

    # Strip mypy version suffixes like "(mypy 1.11.0)"
    if tool_name == "mypy":
        msg = re.sub(r"\s*\(mypy[\s\d.]+\)", "", msg)

    # Strip ruff rule code from start if present (e.g. "E501 Line too long" → "Line too long")
    # Keep the code in raw_message but normalize without it
    msg = re.sub(r"^[A-Z]\d{3,4}\s+", "", msg)

    return msg.strip()


def utcnow() -> datetime:
    """Return current UTC-aware datetime."""
    return datetime.now(tz=UTC)


def clamp_sha(sha: str) -> str:
    """Ensure SHA is between 7 and 40 characters.

    Args:
        sha: Raw git SHA string.

    Returns:
        SHA truncated to 40 chars or padded with '0' to reach 7 chars minimum.
    """
    sha = sha.strip()[:40]
    if len(sha) < 7:
        sha = sha.ljust(7, "0")
    return sha
