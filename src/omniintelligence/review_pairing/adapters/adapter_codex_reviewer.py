# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Codex CLI adapter for adversarial plan review.

Calls ``codex exec`` in headless mode via asyncio.create_subprocess_exec
to conduct adversarial reviews using the Codex CLI (ChatGPT subscription).

NDJSON parsing is conservative: only the final assistant completion event
is considered. No heuristic semantic repair of malformed payloads.

Reference: OMN-5792
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import shutil

from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    parse_review_response,
    to_review_findings,
)
from omniintelligence.review_pairing.adapters.base import PROBABILISTIC
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)

# Default timeout for codex exec subprocess (seconds).
_CODEX_TIMEOUT_SECONDS: float = 180.0

# Model key used in rule_id and result envelope.
_CODEX_MODEL_KEY: str = "codex"


def _extract_assistant_content(ndjson_output: str) -> str | None:
    """Extract final assistant message content from Codex NDJSON stream.

    Parsing doctrine (conservative):
    1. Read all NDJSON lines
    2. Filter for events with type == "message" and role == "assistant"
    3. Take the last such event's content field
    4. If no unambiguous final assistant content, return None

    Args:
        ndjson_output: Raw NDJSON output from codex exec --json.

    Returns:
        Content string from the last assistant message, or None.
    """
    last_assistant_content: str | None = None

    for line in ndjson_output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(event, dict):
            continue

        # Check for assistant message events.
        event_type = event.get("type", "")
        role = event.get("role", "")

        if event_type == "message" and role == "assistant":
            content = event.get("content", "")
            if isinstance(content, str) and content.strip():
                last_assistant_content = content

    return last_assistant_content


async def async_parse_raw(
    plan_content: str,
    *,
    repo: str = "plan-review",
    pr_id: int = 0,
    commit_sha: str = "0000000",
    timeout_seconds: float = _CODEX_TIMEOUT_SECONDS,
) -> ModelExternalReviewResult:
    """Run adversarial review via Codex CLI.

    Invokes ``codex exec - --json --approval-mode full-auto`` with the
    adversarial review prompt piped via stdin.

    Args:
        plan_content: Raw plan text to review.
        repo: Repository slug.
        pr_id: Pull request number.
        commit_sha: Commit SHA.
        timeout_seconds: Subprocess timeout.

    Returns:
        ModelExternalReviewResult with findings or error.
    """
    # Check codex binary availability.
    codex_path = shutil.which("codex")
    if codex_path is None:
        return ModelExternalReviewResult(
            model=_CODEX_MODEL_KEY,
            prompt_version=PROMPT_VERSION,
            success=False,
            error="codex CLI not found",
        )

    # Build the prompt.
    user_prompt = USER_PROMPT_TEMPLATE.format(plan_content=plan_content)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    try:
        process = await asyncio.create_subprocess_exec(
            codex_path,
            "exec",
            "-",
            "--json",
            "--approval-mode",
            "full-auto",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(input=full_prompt.encode("utf-8")),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        # Kill the process on timeout.
        with contextlib.suppress(ProcessLookupError):
            process.kill()  # type: ignore[possibly-undefined]
        return ModelExternalReviewResult(
            model=_CODEX_MODEL_KEY,
            prompt_version=PROMPT_VERSION,
            success=False,
            error=f"codex exec timed out after {timeout_seconds:.0f}s",
        )
    except Exception as exc:
        return ModelExternalReviewResult(
            model=_CODEX_MODEL_KEY,
            prompt_version=PROMPT_VERSION,
            success=False,
            error=f"codex exec failed: {exc}",
        )

    stdout_text = stdout_bytes.decode("utf-8", errors="replace")

    # Extract assistant content from NDJSON stream.
    assistant_content = _extract_assistant_content(stdout_text)
    if assistant_content is None:
        return ModelExternalReviewResult(
            model=_CODEX_MODEL_KEY,
            prompt_version=PROMPT_VERSION,
            success=False,
            error="No recoverable assistant completion in Codex event stream",
        )

    # Parse findings from assistant content.
    parsed = parse_review_response(assistant_content)
    findings = to_review_findings(
        parsed,
        _CODEX_MODEL_KEY,
        repo=repo,
        pr_id=pr_id,
        commit_sha=commit_sha,
    )

    return ModelExternalReviewResult(
        model=_CODEX_MODEL_KEY,
        prompt_version=PROMPT_VERSION,
        success=True,
        findings=findings,
        result_count=len(findings),
    )


def get_confidence_tier() -> str:
    """Return the confidence tier for this adapter."""
    return PROBABILISTIC
