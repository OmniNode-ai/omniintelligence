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

AI-backed sources (Phase 2 -- probabilistic):
    ai_reviewer — LLM-backed adversarial review (OMN-5790)
    codex_reviewer -- Codex CLI adversarial review (OMN-5792)

Reference: OMN-2542
"""

from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    async_parse_raw as async_parse_ai_reviewer,
)
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    parse_raw as parse_ai_reviewer,
)
from omniintelligence.review_pairing.adapters.adapter_codex_reviewer import (
    async_parse_raw as async_parse_codex_reviewer,
)
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
    "async_parse_ai_reviewer",
    "async_parse_codex_reviewer",
    "parse_ai_reviewer",
    "parse_eslint",
    "parse_github_checks",
    "parse_mypy",
    "parse_ruff",
]
