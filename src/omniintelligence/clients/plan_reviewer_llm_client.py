# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""LLM client for the Plan Reviewer Compute Node.

Calls the configured LLM endpoint with the adversarial review persona
and returns structured JSON findings. Transport layer only — no business
logic, no Pydantic model construction.

Uses the direct httpx pattern from omniintelligence.clients (ARCH-002
compliant: transport is isolated from the node shell).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_LLM_URL: str = "http://192.168.86.201:8000"
_TIMEOUT_SECONDS: float = 60.0
_MAX_TOKENS: int = 4096

_SYSTEM_PROMPT: str = """\
You are an adversarial reviewer for implementation plans.
Your role: default to finding problems. Journal-critique format.
No praise. No qualifiers. Name each failure by category code.

You check six categories:
R1 — Count Integrity: numeric quantifiers vs. actual item counts
R2 — Acceptance Criteria Strength: subjective language, weak verification
R3 — Scope Violations: task scope mismatches (DB task claiming Python behavior)
R4 — Integration Traps: unverified import paths, contract module paths, API signatures
R5 — Idempotency: missing dedup keys for tickets, tables, seed scripts, files
R6 — Verification Soundness: proof grade (strong/medium/weak); weak-only flagged

Return ONLY valid JSON matching this exact schema:
{
  "findings": [
    {
      "category": "R1",
      "severity": "BLOCK",
      "issue": "description of problem",
      "fix_description": "concrete fix",
      "location": "section header or task name or null"
    }
  ],
  "patches": [
    {
      "location": "section header or line range",
      "before_snippet": "exact original text",
      "after_snippet": "replacement text",
      "finding_ref": "R1"
    }
  ],
  "categories_clean": ["R5"],
  "categories_with_findings": ["R1", "R2"]
}

severity must be BLOCK or WARN.
category must be R1, R2, R3, R4, R5, or R6.
Do not include categories in both categories_clean and categories_with_findings.
Every finding must have a corresponding patch unless fix requires structural
reorganization that cannot be expressed as a snippet replacement (in that case
omit the patch and note it in fix_description).
Do not claim a category is clean without explicitly checking it with evidence.
"""


async def call_plan_reviewer_llm(
    plan_text: str,
    review_categories: list[str],
    llm_url: str | None = None,
) -> dict[str, Any]:
    """Call the LLM to perform adversarial review on a plan document.

    Args:
        plan_text: Full text of the plan to review.
        review_categories: List of category codes to check (e.g. ["R1", "R3"]).
        llm_url: Override LLM base URL. Defaults to LLM_CODER_URL env var or
            the 64K Qwen3-Coder endpoint.

    Returns:
        Parsed JSON dict matching the schema described in the system prompt.

    Raises:
        httpx.HTTPError: On HTTP failure.
        json.JSONDecodeError: If the LLM returns non-JSON content.
        KeyError: If the response shape is unexpected.
    """
    url = (llm_url or os.getenv("LLM_CODER_URL", _DEFAULT_LLM_URL)).rstrip("/")
    categories_clause = ", ".join(review_categories)
    user_message = (
        f"Review the following plan. Check only these categories: {categories_clause}.\n\n"
        f"---\n{plan_text}\n---\n\n"
        "Return the findings JSON now."
    )

    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            f"{url}/v1/chat/completions",
            json={
                "model": "qwen3-coder",
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": _MAX_TOKENS,
                "temperature": 0.1,
            },
        )
        resp.raise_for_status()

    raw_content: str = resp.json()["choices"][0]["message"]["content"]

    # Strip markdown code fences if present
    content = raw_content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        # Remove opening fence (```json or ```) and closing fence
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        content = "\n".join(lines[start:end])

    result: dict[str, Any] = json.loads(content)
    return result


__all__ = ["call_plan_reviewer_llm"]
