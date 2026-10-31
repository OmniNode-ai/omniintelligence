# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Host configuration boundary for the Claude Code review effect (OMN-20910)."""

from __future__ import annotations

import os
from pathlib import Path

from omniintelligence.nodes.node_claude_code_review_effect.handlers.handler_claude_code_review import (
    HandlerClaudeCodeReview,
)
from omniintelligence.nodes.node_claude_code_review_effect.models.model_claude_code_review import (
    CLAUDE_ENV_KEYS,
    ModelClaudeCodeReviewRequest,
    ModelClaudeCodeReviewResult,
)


class HandlerClaudeCodeReviewHost:
    """Typed host handler shared by contract routing and direct review calls."""

    async def handle(
        self, request: ModelClaudeCodeReviewRequest
    ) -> ModelClaudeCodeReviewResult:
        """Resolve non-secret host configuration, then inject it into the effect."""
        python = os.environ.get("ONEX_CLAUDE_POOL_PY")
        root = os.environ.get("OMNI_HOME")
        if not python and root:
            candidate = Path(root) / ".onex-dispatch-venv" / "bin" / "python"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                python = str(candidate)
        environment = {k: v for k, v in os.environ.items() if k in CLAUDE_ENV_KEYS}
        return await HandlerClaudeCodeReview(
            pool_python=python, environment=environment
        ).handle(request)


async def handle(request: ModelClaudeCodeReviewRequest) -> ModelClaudeCodeReviewResult:
    """Invoke the contract-bound host handler from the CLI and bus adapters."""
    return await HandlerClaudeCodeReviewHost().handle(request)
