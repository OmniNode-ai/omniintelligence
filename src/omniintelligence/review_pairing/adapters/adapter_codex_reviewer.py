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
import os
import shutil
from pathlib import Path

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
    USER_PROMPT_TEMPLATE_PR,
)

logger = logging.getLogger(__name__)

# Default timeout for codex exec subprocess (seconds).
_CODEX_TIMEOUT_SECONDS: float = 180.0

# Model key used in rule_id and result envelope.
_CODEX_MODEL_KEY: str = "codex"

# Known Homebrew/system locations where codex may be installed.
# shutil.which only searches PATH, which may be narrow in subprocess contexts.
_CODEX_FALLBACK_DIRS: tuple[str, ...] = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    os.path.expanduser("~/.local/bin"),
)


def _resolve_codex_binary() -> str | None:
    """Resolve the codex binary path.

    Resolution order:
    1. ``CODEX_BINARY`` env var (explicit override, cross-machine safe)
    2. ``shutil.which("codex")`` against the current PATH
    3. Direct stat against known Homebrew/system fallback directories

    Returns the resolved path string, or None if not found.
    """
    env_override = os.environ.get("CODEX_BINARY")
    if (
        env_override
        and Path(env_override).is_file()
        and os.access(env_override, os.X_OK)
    ):
        return env_override

    via_path = shutil.which("codex")
    if via_path is not None:
        return via_path

    for directory in _CODEX_FALLBACK_DIRS:
        candidate = Path(directory) / "codex"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    return None


def _extract_assistant_content(ndjson_output: str) -> str | None:
    """Extract final agent message content from Codex NDJSON stream.

    Codex NDJSON event format (as of 2026):
      {"type": "item.completed", "item": {"type": "agent_message", "text": "..."}}

    Other event types (ignored): thread.started, turn.started, turn.completed,
    turn.failed, item.started, command_execution, error.

    Parsing doctrine (conservative):
    1. Read all NDJSON lines
    2. Filter for item.completed events containing agent_message items
    3. Take the last such event's text field
    4. If no unambiguous final agent content, return None

    Args:
        ndjson_output: Raw NDJSON output from codex exec --json.

    Returns:
        Content string from the last agent message, or None.
    """
    last_agent_content: str | None = None

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

        event_type = event.get("type", "")

        # Primary format: item.completed with agent_message item.
        if event_type == "item.completed":
            item = event.get("item", {})
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text", "")
                if isinstance(text, str) and text.strip():
                    last_agent_content = text

    return last_agent_content


async def async_parse_raw(
    plan_content: str,
    *,
    review_type: str = "plan",
    repo: str = "plan-review",
    pr_id: int = 0,
    commit_sha: str = "0000000",
    timeout_seconds: float = _CODEX_TIMEOUT_SECONDS,
) -> ModelExternalReviewResult:
    """Run adversarial review via Codex CLI.

    Invokes ``codex exec - --json --full-auto`` with the
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
    codex_path = _resolve_codex_binary()
    if codex_path is None:
        return ModelExternalReviewResult(
            model=_CODEX_MODEL_KEY,
            prompt_version=PROMPT_VERSION,
            success=False,
            error=(
                "codex CLI not found — set CODEX_BINARY env var to the absolute path "
                "or ensure the binary is on PATH"
            ),
        )

    # Build the prompt.
    template = USER_PROMPT_TEMPLATE_PR if review_type == "pr" else USER_PROMPT_TEMPLATE
    user_prompt = template.format(plan_content=plan_content)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    try:
        process = await asyncio.create_subprocess_exec(
            codex_path,
            "exec",
            "-",
            "--json",
            "--full-auto",
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
            process.kill()
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
