# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Run a review through Claude Code using only the host pool (OMN-20910).

The pool node owns credential storage and account availability. Its existing
resolve/mark-limited interface is also used by the remote-lane runner. Only
resolve's stdout holds a token: it stays in memory and the Claude child's env.
Neither subprocess output nor exception messages are ever logged or returned.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass

from omniintelligence.nodes.node_claude_code_review_effect.models.model_claude_code_review import (
    CLAUDE_ENV_KEYS,
    ClaudeCodeReviewError,
    ModelClaudeCodeReviewRequest,
    ModelClaudeCodeReviewResult,
)

POOL_MODULE = "omnimarket.nodes.node_claude_token_pool_effect"
_LABEL = re.compile(r"\blabel=([a-z0-9][a-z0-9-]*)\s*$", re.MULTILINE)
_LIMIT = re.compile(
    r"(?:you(?:'|\u2019)ve|you have) hit your (?:weekly |usage |session )?limit"
    r"|(?:usage|rate)[ _-]limit(?: reached| exceeded|_error)|out of extra usage",
    re.IGNORECASE,
)


async def _run(
    argv: tuple[str, ...],
    *,
    timeout: float,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    prompt: str | None = None,
) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE
        if prompt is not None
        else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=cwd,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(None if prompt is None else prompt.encode()),
            timeout=timeout,
        )
    except BaseException:
        # Cancellation must release the child, including on an outer vote deadline.
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.wait()
        raise
    return (
        process.returncode or 0,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )


@dataclass(frozen=True)
class HandlerClaudeCodeReview:
    """Reviews through Claude Code; the host handler injects its non-secret configuration."""

    pool_python: str | None = None
    environment: Mapping[str, str] | None = None

    async def handle(
        self, request: ModelClaudeCodeReviewRequest
    ) -> ModelClaudeCodeReviewResult:
        """Resolve at call time; mark and rotate limited accounts within one deadline."""

        def failure(code: ClaudeCodeReviewError) -> ModelClaudeCodeReviewResult:
            # Only our fixed codes pass here, never text from an external process.
            return ModelClaudeCodeReviewResult(
                correlation_id=request.correlation_id, error=code
            )

        python = self.pool_python
        if python is None:
            return failure("claude_pool_unavailable")
        deadline = time.monotonic() + request.timeout_seconds
        seen: set[str] = set()
        secrets: list[str] = []

        def remaining() -> float:
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise TimeoutError
            return budget

        stage = "pool"
        try:
            while True:
                stage = "pool"
                code, token, diagnostic = await _run(
                    (python, "-m", POOL_MODULE, "resolve"),
                    timeout=min(30, remaining()),
                )
                if code == 4:
                    return failure("claude_pool_all_limited")
                if code != 0:
                    return failure("claude_pool_unavailable")
                token = token.strip()
                labels = _LABEL.findall(diagnostic)
                if not token or any(c.isspace() for c in token) or not labels:
                    return failure("claude_pool_invalid_response")
                label = labels[-1]
                if label in seen or len(seen) >= 32:
                    return failure("claude_pool_rotation_stalled")
                seen.add(label)
                secrets.append(token)
                # An allowlist removes ambient API keys, provider redirects, model
                # overrides and debugging flags. The pool is the sole auth source.
                env = {
                    k: v
                    for k, v in (self.environment or {}).items()
                    if k in CLAUDE_ENV_KEYS
                }
                env["CLAUDE_CODE_OAUTH_TOKEN"] = token
                env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(request.max_output_tokens)
                argv = (
                    "claude",
                    "-p",
                    "--model",
                    request.model,
                    "--output-format",
                    "json",
                    "--system-prompt",
                    request.system_prompt,
                    "--tools",
                    "",
                    "--strict-mcp-config",
                    "--mcp-config",
                    '{"mcpServers":{}}',
                    "--setting-sources",
                    "",
                    "--settings",
                    '{"disableAllHooks":true}',
                    "--disable-slash-commands",
                    "--no-session-persistence",
                )
                stage = "claude"
                # A fresh cwd keeps the reviewed checkout's instructions/plugins out.
                with tempfile.TemporaryDirectory(prefix="claude-review-") as directory:
                    code, stdout, stderr = await _run(
                        argv,
                        timeout=remaining(),
                        env=env,
                        cwd=directory,
                        prompt=request.user_prompt,
                    )
                try:
                    payload = json.loads(stdout)
                except (ValueError, TypeError):
                    payload = None
                failed = (
                    code != 0
                    or not isinstance(payload, dict)
                    or payload.get("is_error") is not False
                )
                # Successful model prose cannot mark an account limited. Claude's
                # error result (or a failing process) must report the usage limit.
                if failed and _LIMIT.search(stdout + "\n" + stderr):
                    stage = "mark"
                    marked, _, _ = await _run(
                        (
                            python,
                            "-m",
                            POOL_MODULE,
                            "mark-limited",
                            "--label",
                            label,
                            "--seconds",
                            "3600",
                        ),
                        timeout=min(30, remaining()),
                    )
                    if marked == 4:
                        return failure("claude_pool_all_limited")
                    if marked != 0:
                        return failure("claude_pool_mark_failed")
                    continue
                if code != 0 or (isinstance(payload, dict) and payload.get("is_error")):
                    return failure("claude_code_failed")
                if (
                    not isinstance(payload, dict)
                    or payload.get("is_error") is not False
                ):
                    return failure("claude_code_invalid_response")
                response = payload.get("result")
                if not isinstance(response, str) or not response.strip():
                    return failure("claude_code_invalid_response")
                for secret in secrets:
                    response = response.replace(secret, "[REDACTED]")
                usage = payload.get("usage", {})
                if not isinstance(usage, dict):
                    return failure("claude_code_invalid_response")
                counts = [
                    usage.get(k, 0)
                    for k in (
                        "input_tokens",
                        "output_tokens",
                        "cache_creation_input_tokens",
                        "cache_read_input_tokens",
                    )
                ]
                if any(type(n) is not int or n < 0 for n in counts):
                    return failure("claude_code_invalid_response")
                return ModelClaudeCodeReviewResult(
                    correlation_id=request.correlation_id,
                    success=True,
                    response=response,
                    input_tokens=counts[0] + counts[2] + counts[3],
                    output_tokens=counts[1],
                )
        except TimeoutError:
            return failure("claude_code_timeout")
        except OSError:
            if stage == "pool":
                return failure("claude_pool_unavailable")
            if stage == "mark":
                return failure("claude_pool_mark_failed")
            return failure("claude_code_unavailable")
