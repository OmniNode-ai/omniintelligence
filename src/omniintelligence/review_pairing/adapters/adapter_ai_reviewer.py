# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""AI reviewer adapter stub for the Review Signal Adapters.

This module is a STUB — it documents the interface contract for AI reviewer
source adapters (e.g., CodeRabbit, GitHub Copilot, custom AI reviewers)
but does NOT implement parsing logic.

## Interface Contract

All AI reviewer adapters must implement:

    def parse_raw(
        raw: str | dict,
        *,
        repo: str,
        pr_id: int,
        commit_sha: str,
        **kwargs: Any,
    ) -> list[ReviewFindingObserved]:
        ...

### Input Contract

``raw`` is the verbatim output from the AI reviewer. Format is tool-specific:
- CodeRabbit: JSON via webhook payload or REST API response
- GitHub Copilot: GitHub PR review comment objects
- Custom AI reviewers: tool-specific JSON or text

### Output Contract

Each adapter must:
1. Return a list of ``ReviewFindingObserved`` events (may be empty).
2. Use ``confidence_tier = "probabilistic"`` for all AI-sourced findings.
3. Handle malformed/partial input gracefully (log warning, skip, do not crash).
4. Never mutate global state.
5. Never log the ``GITHUB_TOKEN`` or any other secret.

### Rule ID convention for AI reviewers

AI reviewers do not emit stable rule IDs. Use the convention:
    ``ai-reviewer:{tool_name}:{category}``

Where ``category`` is the best available classification (e.g.,
``security``, ``performance``, ``style``, ``correctness``, ``unknown``).

Example: ``ai-reviewer:coderabbit:security``

### Confidence tier

AI reviewer findings must use ``confidence_tier = "probabilistic"``
because:
- Rule IDs are not stable across review sessions
- Locations may be approximate (comment thread on a hunk, not an exact line)
- The same code may receive different findings on different runs

### Normalization

Since AI reviewer messages are natural language, normalization should:
- Truncate to 512 chars max
- Strip markdown formatting (``**``, ``_``, backticks)
- Remove quoted code blocks (between ``` fences)

## Implementation Guide (future)

To implement a concrete AI reviewer adapter:

1. Create ``adapter_{tool_name}.py`` in ``review_pairing/adapters/``
2. Implement ``parse_raw()`` following this interface contract
3. Add import and re-export to ``adapters/__init__.py``
4. Add ≥10 unit tests in ``tests/unit/review_pairing/adapters/``
5. Document the input format in the module docstring

## Why probabilistic?

AI reviewers produce useful signals but with lower reliability than
deterministic linters:
- The same finding may not appear on re-run (non-deterministic models)
- Location anchoring depends on diff context (may shift after rebases)
- Rule IDs are not standardized across tools or versions

The pairing engine applies lower confidence scores to probabilistic findings
and requires a higher ``fix_frequency`` threshold before promoting them to
pattern candidates.

Reference: OMN-2542
"""

from __future__ import annotations

from typing import Any

from omniintelligence.review_pairing.adapters.base import PROBABILISTIC
from omniintelligence.review_pairing.models import ReviewFindingObserved


def parse_raw(
    raw: str | dict[str, Any],  # noqa: ARG001
    *,
    repo: str,  # noqa: ARG001
    pr_id: int,  # noqa: ARG001
    commit_sha: str,  # noqa: ARG001
    **kwargs: Any,  # noqa: ARG001
) -> list[ReviewFindingObserved]:
    """Stub implementation — always returns empty list.

    This function exists to satisfy the adapter interface contract.
    A concrete implementation must be provided when an AI reviewer source
    is onboarded.

    Args:
        raw: Raw output from the AI reviewer (format is tool-specific).
        repo: Repository slug in ``owner/name`` format.
        pr_id: Pull request number.
        commit_sha: Git SHA at which findings were observed.
        **kwargs: Tool-specific parameters.

    Returns:
        Empty list (stub — not implemented).
    """
    # Stub: no-op
    return []


def get_confidence_tier() -> str:
    """Return the confidence tier for this adapter."""
    return PROBABILISTIC
