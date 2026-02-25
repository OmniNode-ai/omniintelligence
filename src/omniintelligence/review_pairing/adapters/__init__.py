# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Review signal adapters for the Review-Fix Pairing subsystem.

Each adapter is a stateless pure function:

    parse_raw(raw: str | dict) -> list[ReviewFindingObserved]

Supported sources (Phase 1 — deterministic):
    ruff       — Ruff JSON output (``ruff check --output-format json``)
    mypy       — mypy text output
    eslint     — ESLint JSON output (``eslint --format json``)
    github     — GitHub Checks API annotations (via REST API)

Stub sources (documented interface, not yet implemented):
    ai_reviewer — AI reviewer comments (interface contract only)

Reference: OMN-2542
"""

from omniintelligence.review_pairing.adapters.adapter_eslint import (
    parse_raw as parse_eslint,
)
from omniintelligence.review_pairing.adapters.adapter_github_checks import (
    parse_raw as parse_github_checks,
)
from omniintelligence.review_pairing.adapters.adapter_mypy import (
    parse_raw as parse_mypy,
)
from omniintelligence.review_pairing.adapters.adapter_ruff import (
    parse_raw as parse_ruff,
)

__all__ = [
    "parse_eslint",
    "parse_github_checks",
    "parse_mypy",
    "parse_ruff",
]
