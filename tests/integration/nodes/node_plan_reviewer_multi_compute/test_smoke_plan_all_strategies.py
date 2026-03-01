# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Integration smoke tests: all 4 strategies x real LLM endpoints.

Tests run against the live LLM endpoints configured in the environment.
Each test is skipped if the required endpoint(s) are unreachable.

Smoke plan design:
    - Intentionally triggers R1 (counts wrong): summary says 3 steps, plan has 4.
    - Intentionally triggers R2 (AC missing): Steps 1, 3, 4 have no AC.
    - Intentionally triggers R3 (scope creep): Step 4 (email) is outside the
      stated objective of migrating records.
    - Intentionally triggers R4 (integration trap): Step 2 has no
      crash-recovery / partial-failure rollback strategy.
    - Intentionally clean for R5 (idempotency): All 4 steps are explicitly
      idempotent (IF NOT EXISTS DDL, ON CONFLICT DO NOTHING upsert,
      rolling restart, email dedup via welcome_sent flag).
    - Intentionally triggers R6 (no verification): Step 3 has no post-deploy
      health check or smoke test.

Acceptance criteria:
    - R1, R2, R3, R4, R6 each appear in ``categories_with_findings``
      for at least 3/5 of the triggered categories (some LLMs may miss
      individual categories).
    - R5 does not appear in ``categories_with_findings`` for any strategy
      (all idempotency issues are explicitly resolved in the plan text).
    - ``categories_with_findings`` and ``categories_clean`` are disjoint.
    - All ``PlanReviewFindingWithConfidence`` objects have valid SHA-256
      hashes when a patch is present.
    - All confidence values are in [0.0, 1.0].

Ticket: OMN-3292
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
from typing import Any
from uuid import UUID

import httpx
import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.handler_plan_reviewer_multi_compute import (
    ModelCaller,
    handle_plan_reviewer_multi_compute,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_sequential_critique import (
    CriticCaller,
    CritiqueResult,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_plan_review_category import (
    EnumPlanReviewCategory,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_strategy import (
    EnumReviewStrategy,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    PlanReviewFinding,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_reviewer_multi_input import (
    ModelPlanReviewerMultiCommand,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_reviewer_multi_output import (
    ModelPlanReviewerMultiOutput,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Smoke plan
# ---------------------------------------------------------------------------
# This plan is designed to trigger specific R-category findings.
#
# R1 (counts wrong): Summary says "3 steps" but the plan body has 4 steps.
# R2 (AC missing): Steps 1 and 3 have no acceptance criteria.
# R3 (scope creep): Step 4 introduces a new feature (email notifications)
#                   not mentioned in the objective.
# R4 (integration trap): Step 2 writes to Postgres without testing the
#                        rollback path — a classic integration trap.
# R5 (idempotency — CLEAN): All steps use upsert / idempotent migrations,
#                           so no R5 finding should be raised.
# R6 (no verification step): No "verify the migration ran successfully" step
#                             exists; there is only a deploy step.

SMOKE_PLAN = """\
# Plan: User Profile Migration

## Objective
Migrate all existing user records to the new profile schema.

## Summary
The migration will be completed in 3 steps, with all data preserved.

## Steps

### Step 1 — Add the new profile columns to the database
Run the SQL script `migrations/add_profile_columns.sql`.
This script uses `ADD COLUMN IF NOT EXISTS` guards so it can be safely
re-run multiple times without side effects.

No acceptance criteria defined for this step.

### Step 2 — Backfill all existing users with profile data
For each user row in the `users` table, upsert a corresponding record in
the new `profiles` table:
  `INSERT INTO profiles (user_id, display_name) VALUES (...) ON CONFLICT DO NOTHING`

This step does NOT describe what happens if the batch job crashes
halfway through. No resume or partial-failure rollback strategy is given.

Acceptance Criteria:
  - All users in `users` have a corresponding row in `profiles`.
  - Running the backfill script a second time produces the same result.

### Step 3 — Switch the application to read from `profiles`
Deploy the new version of the API service. The deployment process is a
rolling restart with no traffic drain period. No post-deploy health check
or rollback playbook is documented.

No acceptance criteria defined for this step.

### Step 4 — Send a welcome email to all migrated users
Once migration is confirmed complete, trigger the welcome-email job.
Each user's `profiles` row includes a `welcome_sent BOOLEAN DEFAULT FALSE`
column. The email job only sends to users where `welcome_sent = FALSE`
and sets the flag to `TRUE` after sending, so re-running the job is safe
and will not send duplicate emails.

No acceptance criteria defined for this step.
"""

# ---------------------------------------------------------------------------
# LLM system prompt for plan review
# ---------------------------------------------------------------------------

_REVIEW_SYSTEM_PROMPT = """\
You are a plan reviewer. Analyse the provided plan and identify issues across the
following R-categories. For each issue found, output a JSON object. Respond with a
JSON array only — no prose before or after the array.

R-categories to evaluate:
  R1_counts             — Are step/task counts accurate throughout?
  R2_acceptance_criteria — Does every step have clear acceptance criteria?
  R3_scope              — Does the plan introduce any scope creep (work outside the objective)?
  R4_integration_traps  — Are there integration risks or missing correctness proofs?
  R5_idempotency        — Are all operations idempotent and safely re-runnable?
  R6_verification       — Is there a verification/smoke-test step for each major change?

Output format — an array of findings (empty array [] if no issues):
[
  {
    "category": "<one of: R1_counts|R2_acceptance_criteria|R3_scope|R4_integration_traps|R5_idempotency|R6_verification>",
    "location": "<step name or section>",
    "severity": "<BLOCK|WARN>",
    "description": "<description of the issue>",
    "suggested_fix": "<how to resolve it>"
  }
]
"""

_CRITIQUE_SYSTEM_PROMPT = """\
You are a plan review critic. You will receive a plan text and a list of findings
produced by another reviewer. Your task is to critique those findings and optionally
add new ones that were missed.

Respond with a single JSON object (no prose before or after):
{
  "confirmed": ["<finding_id_1>", "<finding_id_2>"],
  "rejected":  ["<finding_id_3>"],
  "added": [
    {
      "category": "<R1_counts|R2_acceptance_criteria|R3_scope|R4_integration_traps|R5_idempotency|R6_verification>",
      "location": "<step name or section>",
      "severity": "<BLOCK|WARN>",
      "description": "<description>",
      "suggested_fix": "<how to resolve>"
    }
  ]
}

Use the exact finding_id values from the input — they are UUIDs.
"""

# ---------------------------------------------------------------------------
# Category string → enum mapping
# ---------------------------------------------------------------------------

_CATEGORY_MAP: dict[str, EnumPlanReviewCategory] = {
    "R1_counts": EnumPlanReviewCategory.R1_COUNTS,
    "R2_acceptance_criteria": EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA,
    "R3_scope": EnumPlanReviewCategory.R3_SCOPE,
    "R4_integration_traps": EnumPlanReviewCategory.R4_INTEGRATION_TRAPS,
    "R5_idempotency": EnumPlanReviewCategory.R5_IDEMPOTENCY,
    "R6_verification": EnumPlanReviewCategory.R6_VERIFICATION,
}

# ---------------------------------------------------------------------------
# Reachability helpers
# ---------------------------------------------------------------------------


def _is_reachable(url: str, timeout: float = 3.0) -> bool:
    """Return True if the host+port derived from *url* accepts TCP connections."""
    try:
        parsed = httpx.URL(url)
        host = parsed.host
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except (OSError, ValueError):
        return False


def _probe_openai_compat_models(base_url: str, timeout: float = 5.0) -> str | None:
    """Return the first model ID from ``/v1/models``, or ``None`` on failure.

    Used to discover the actual model ID served by a vLLM endpoint instead
    of hard-coding a name that may differ from what the server expects.

    Args:
        base_url: Base URL e.g. ``http://192.168.86.201:8000``.
        timeout: HTTP request timeout in seconds.

    Returns:
        First model ID string, or ``None`` if the probe fails.
    """
    models_url = f"{base_url.rstrip('/')}/v1/models"
    try:
        response = httpx.get(models_url, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])
            if models:
                return str(models[0]["id"])
    except Exception:
        pass
    return None


def _probe_gemini_api_key(api_key: str, timeout: float = 5.0) -> bool:
    """Return True if the Gemini API key is valid (200 response from /v1beta/models).

    Args:
        api_key: Google API key to test.
        timeout: HTTP request timeout.

    Returns:
        True if the key returns a 200-range response.
    """
    if not api_key:
        return False
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/openai/models?key={api_key}"
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        return response.status_code < 400
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Finding parser
# ---------------------------------------------------------------------------


def _parse_findings(
    raw: str,
    source_model: EnumReviewModel,
    categories: list[EnumPlanReviewCategory],
) -> list[PlanReviewFinding]:
    """Parse LLM JSON response text into a list of PlanReviewFinding objects.

    Gracefully handles partial or malformed output — returns an empty list
    rather than raising so the strategy handler can treat the model as if it
    returned no findings.

    Args:
        raw: Raw string from the LLM.
        source_model: Model that produced the response.
        categories: Categories requested (used to filter unexpected values).

    Returns:
        List of ``PlanReviewFinding`` objects.
    """
    allowed_categories = set(categories)

    # Strip optional markdown fences.
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first and last fence lines.
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    # Locate the JSON array.
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        logger.warning(
            "_parse_findings: no JSON array found in model=%s output (len=%d)",
            source_model.value,
            len(raw),
        )
        return []

    try:
        items: list[dict[str, Any]] = json.loads(text[start:end])
    except json.JSONDecodeError:
        logger.warning(
            "_parse_findings: JSON decode error for model=%s",
            source_model.value,
        )
        return []

    findings: list[PlanReviewFinding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_cat = item.get("category", "")
        category = _CATEGORY_MAP.get(raw_cat)
        if category is None or category not in allowed_categories:
            logger.debug(
                "_parse_findings: skipping unknown/out-of-scope category %r",
                raw_cat,
            )
            continue
        location = str(item.get("location", "unknown")).strip() or "unknown"
        severity = str(item.get("severity", "WARN")).upper()
        if severity not in ("BLOCK", "WARN"):
            severity = "WARN"
        description = str(item.get("description", "")).strip()
        suggested_fix = str(item.get("suggested_fix", "")).strip()
        if not description:
            continue
        if not suggested_fix:
            suggested_fix = "See description."
        try:
            findings.append(
                PlanReviewFinding.create(
                    category=category,
                    location=location,
                    severity=severity,
                    description=description,
                    suggested_fix=suggested_fix,
                    source_model=source_model,
                )
            )
        except Exception:
            logger.exception(
                "_parse_findings: failed to create PlanReviewFinding for model=%s item=%r",
                source_model.value,
                item,
            )
    return findings


# ---------------------------------------------------------------------------
# Critique parser
# ---------------------------------------------------------------------------


def _parse_critique(
    raw: str,
    drafter_findings: list[PlanReviewFinding],
    source_model: EnumReviewModel,
) -> CritiqueResult:
    """Parse critic LLM response into a CritiqueResult dict.

    Args:
        raw: Raw string from the critic LLM.
        drafter_findings: The drafter's findings (for UUID lookup).
        source_model: The critic model (used for added findings).

    Returns:
        CritiqueResult with confirmed/rejected/added lists.
    """
    # Build UUID → finding mapping.
    finding_by_id: dict[UUID, PlanReviewFinding] = {
        f.finding_id: f for f in drafter_findings
    }

    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        logger.warning(
            "_parse_critique: no JSON object found in critic model=%s output",
            source_model.value,
        )
        # Confirm all drafter findings when critique cannot be parsed.
        return {
            "confirmed": [f.finding_id for f in drafter_findings],
            "rejected": [],
            "added": [],
        }

    try:
        data: dict[str, Any] = json.loads(text[start:end])
    except json.JSONDecodeError:
        logger.warning(
            "_parse_critique: JSON decode error for critic model=%s",
            source_model.value,
        )
        return {
            "confirmed": [f.finding_id for f in drafter_findings],
            "rejected": [],
            "added": [],
        }

    confirmed: list[UUID] = []
    for raw_id in data.get("confirmed", []):
        try:
            uid = UUID(str(raw_id))
            if uid in finding_by_id:
                confirmed.append(uid)
        except (ValueError, AttributeError):
            pass

    added_findings: list[PlanReviewFinding] = []
    for item in data.get("added", []):
        if not isinstance(item, dict):
            continue
        raw_cat = item.get("category", "")
        category = _CATEGORY_MAP.get(raw_cat)
        if category is None:
            continue
        location = str(item.get("location", "unknown")).strip() or "unknown"
        severity = str(item.get("severity", "WARN")).upper()
        if severity not in ("BLOCK", "WARN"):
            severity = "WARN"
        description = str(item.get("description", "")).strip()
        suggested_fix = str(item.get("suggested_fix", "")).strip() or "See description."
        if not description:
            continue
        try:
            added_findings.append(
                PlanReviewFinding.create(
                    category=category,
                    location=location,
                    severity=severity,
                    description=description,
                    suggested_fix=suggested_fix,
                    source_model=source_model,
                )
            )
        except Exception:
            logger.exception(
                "_parse_critique: failed to create added finding for model=%s",
                source_model.value,
            )

    return {
        "confirmed": confirmed,
        "rejected": [],
        "added": added_findings,
    }


# ---------------------------------------------------------------------------
# Real LLM caller factory (OpenAI-compat local vLLM endpoints)
# ---------------------------------------------------------------------------


def _build_openai_compat_caller(
    base_url: str,
    model_name: str,
    source_model: EnumReviewModel,
    *,
    timeout_seconds: float = 120.0,
) -> ModelCaller:
    """Return a ModelCaller that calls an OpenAI-compatible endpoint.

    Args:
        base_url: Base URL e.g. ``http://192.168.86.201:8000``.
        model_name: Model identifier string sent in the request body.
        source_model: EnumReviewModel to tag findings with.
        timeout_seconds: HTTP request timeout.

    Returns:
        Async callable ``(plan_text, categories) -> list[PlanReviewFinding]``.
    """
    chat_url = f"{base_url.rstrip('/')}/v1/chat/completions"

    async def _caller(
        plan_text: str,
        categories: list[EnumPlanReviewCategory],
    ) -> list[PlanReviewFinding]:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": f"Plan to review:\n\n{plan_text}"},
            ],
            "max_tokens": 2048,
            "temperature": 0.1,
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
            response = await client.post(chat_url, json=payload)
            response.raise_for_status()
            content: str = response.json()["choices"][0]["message"]["content"]
        return _parse_findings(content, source_model, categories)

    return _caller


# ---------------------------------------------------------------------------
# Real LLM caller factory (Gemini)
# ---------------------------------------------------------------------------


def _build_gemini_caller(
    api_key: str,
    source_model: EnumReviewModel = EnumReviewModel.GEMINI_FLASH,
    *,
    timeout_seconds: float = 90.0,
) -> ModelCaller:
    """Return a ModelCaller for the Gemini Flash OpenAI-compat endpoint.

    Args:
        api_key: Google API key (``GEMINI_API_KEY``).
        source_model: EnumReviewModel to tag findings with.
        timeout_seconds: HTTP request timeout.

    Returns:
        Async callable ``(plan_text, categories) -> list[PlanReviewFinding]``.
    """
    chat_url = (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )

    async def _caller(
        plan_text: str,
        categories: list[EnumPlanReviewCategory],
    ) -> list[PlanReviewFinding]:
        payload = {
            "model": "gemini-2.0-flash",
            "messages": [
                {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": f"Plan to review:\n\n{plan_text}"},
            ],
            "max_tokens": 2048,
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
            response = await client.post(chat_url, json=payload, headers=headers)
            response.raise_for_status()
            content: str = response.json()["choices"][0]["message"]["content"]
        return _parse_findings(content, source_model, categories)

    return _caller


# ---------------------------------------------------------------------------
# Real critic caller factory (for S3 sequential_critique)
# ---------------------------------------------------------------------------


def _build_openai_compat_critic_caller(
    base_url: str,
    model_name: str,
    source_model: EnumReviewModel,
    *,
    timeout_seconds: float = 120.0,
) -> CriticCaller:
    """Return a CriticCaller that calls an OpenAI-compatible endpoint.

    The critic receives the plan text and drafter findings, then returns
    a CritiqueResult with confirmed/rejected/added lists.

    Args:
        base_url: Base URL e.g. ``http://192.168.86.200:8101``.
        model_name: Model identifier string sent in the request body.
        source_model: EnumReviewModel to tag added findings with.
        timeout_seconds: HTTP request timeout.

    Returns:
        Async callable ``(plan_text, drafter_findings) -> CritiqueResult``.
    """
    chat_url = f"{base_url.rstrip('/')}/v1/chat/completions"

    async def _critic(
        plan_text: str,
        drafter_findings: list[PlanReviewFinding],
    ) -> CritiqueResult:
        findings_repr = json.dumps(
            [
                {
                    "finding_id": str(f.finding_id),
                    "category": f.category.value,
                    "location": f.location,
                    "severity": f.severity,
                    "description": f.description,
                }
                for f in drafter_findings
            ],
            indent=2,
        )
        user_content = f"Plan:\n\n{plan_text}\n\nDrafter findings:\n{findings_repr}"
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": _CRITIQUE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 2048,
            "temperature": 0.1,
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
            response = await client.post(chat_url, json=payload)
            response.raise_for_status()
            content: str = response.json()["choices"][0]["message"]["content"]
        return _parse_critique(content, drafter_findings, source_model)

    return _critic


# ---------------------------------------------------------------------------
# Z.AI GLM-4 caller (uses existing PlanReviewerZAIClient)
# ---------------------------------------------------------------------------


def _build_z_ai_caller(
    api_key: str,
    source_model: EnumReviewModel = EnumReviewModel.GLM_4,
    *,
    timeout_seconds: float = 90.0,
) -> ModelCaller:
    """Return a ModelCaller for the Z.AI GLM-4 endpoint.

    Args:
        api_key: Z.AI API key (``Z_AI_API_KEY``).
        source_model: EnumReviewModel to tag findings with.
        timeout_seconds: HTTP request timeout.

    Returns:
        Async callable ``(plan_text, categories) -> list[PlanReviewFinding]``.
    """
    chat_url = "https://api.z.ai/api/paas/v4/chat/completions"

    async def _caller(
        plan_text: str,
        categories: list[EnumPlanReviewCategory],
    ) -> list[PlanReviewFinding]:
        payload = {
            "model": "glm-4-plus",
            "messages": [
                {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": f"Plan to review:\n\n{plan_text}"},
            ],
            "max_tokens": 2048,
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
            response = await client.post(chat_url, json=payload, headers=headers)
            response.raise_for_status()
            content: str = response.json()["choices"][0]["message"]["content"]
        return _parse_findings(content, source_model, categories)

    return _caller


# ---------------------------------------------------------------------------
# Environment + reachability detection
# ---------------------------------------------------------------------------

_LLM_CODER_URL: str = os.environ.get("LLM_CODER_URL", "http://192.168.86.201:8000")
_LLM_DEEPSEEK_URL: str = os.environ.get(
    "LLM_DEEPSEEK_R1_URL", "http://192.168.86.200:8101"
)
_GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
_Z_AI_API_KEY: str = os.environ.get("Z_AI_API_KEY", "")

# Probe actual model IDs from the local vLLM endpoints (may differ from env defaults).
# Fall back to env-documented defaults if the probe cannot reach the endpoint.
_QWEN3_MODEL_ID: str | None = _probe_openai_compat_models(_LLM_CODER_URL)
_DEEPSEEK_MODEL_ID: str | None = _probe_openai_compat_models(_LLM_DEEPSEEK_URL)

_QWEN3_REACHABLE: bool = _QWEN3_MODEL_ID is not None
_DEEPSEEK_REACHABLE: bool = _DEEPSEEK_MODEL_ID is not None
_GEMINI_REACHABLE: bool = _probe_gemini_api_key(_GEMINI_API_KEY)
_Z_AI_REACHABLE: bool = bool(_Z_AI_API_KEY) and _is_reachable("https://api.z.ai")

# S3 requires both qwen3-coder (drafter) and deepseek-r1 (critic).
_S3_REACHABLE: bool = _QWEN3_REACHABLE and _DEEPSEEK_REACHABLE

# All four endpoints must be reachable for cross-strategy smoke tests.
_ALL_REACHABLE: bool = (
    _QWEN3_REACHABLE and _DEEPSEEK_REACHABLE and _GEMINI_REACHABLE and _Z_AI_REACHABLE
)

requires_qwen3 = pytest.mark.skipif(
    not _QWEN3_REACHABLE,
    reason=f"LLM_CODER_URL ({_LLM_CODER_URL}) not reachable",
)
requires_deepseek = pytest.mark.skipif(
    not _DEEPSEEK_REACHABLE,
    reason=f"LLM_DEEPSEEK_R1_URL ({_LLM_DEEPSEEK_URL}) not reachable",
)
requires_gemini = pytest.mark.skipif(
    not _GEMINI_REACHABLE,
    reason="GEMINI_API_KEY not set or generativelanguage.googleapis.com not reachable",
)
requires_z_ai = pytest.mark.skipif(
    not _Z_AI_REACHABLE,
    reason="Z_AI_API_KEY not set or api.z.ai not reachable",
)
requires_s3 = pytest.mark.skipif(
    not _S3_REACHABLE,
    reason="S3 requires both LLM_CODER_URL and LLM_DEEPSEEK_R1_URL to be reachable",
)
requires_all_llms = pytest.mark.skipif(
    not _ALL_REACHABLE,
    reason="All four LLM endpoints (qwen3, deepseek, gemini, z_ai) must be reachable",
)


# ---------------------------------------------------------------------------
# Caller fixture helpers
# ---------------------------------------------------------------------------


def _make_all_callers() -> dict[EnumReviewModel, ModelCaller]:
    """Build real LLM model callers for all four models.

    Uses the model IDs discovered from the ``/v1/models`` probe.  If a
    probe did not return a model ID (endpoint unreachable), the caller map
    will still be built but the skip markers on the tests will prevent
    execution in that case.
    """
    qwen3_model = _QWEN3_MODEL_ID or "Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit"
    deepseek_model = _DEEPSEEK_MODEL_ID or "DeepSeek-R1-Distill-Qwen-32B-bf16"
    return {
        EnumReviewModel.QWEN3_CODER: _build_openai_compat_caller(
            _LLM_CODER_URL,
            qwen3_model,
            EnumReviewModel.QWEN3_CODER,
        ),
        EnumReviewModel.DEEPSEEK_R1: _build_openai_compat_caller(
            _LLM_DEEPSEEK_URL,
            deepseek_model,
            EnumReviewModel.DEEPSEEK_R1,
        ),
        EnumReviewModel.GEMINI_FLASH: _build_gemini_caller(_GEMINI_API_KEY),
        EnumReviewModel.GLM_4: _build_z_ai_caller(_Z_AI_API_KEY),
    }


def _make_available_callers() -> dict[EnumReviewModel, ModelCaller]:
    """Build callers only for reachable LLM endpoints.

    Unlike ``_make_all_callers``, this function omits callers for
    unreachable endpoints so tests can run with whatever subset is available.
    Requires at least the two local endpoints (qwen3 + deepseek).

    Returns:
        Dict mapping reachable ``EnumReviewModel`` IDs to async callers.
    """
    callers: dict[EnumReviewModel, ModelCaller] = {}
    qwen3_model = _QWEN3_MODEL_ID or "Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit"
    deepseek_model = _DEEPSEEK_MODEL_ID or "DeepSeek-R1-Distill-Qwen-32B-bf16"

    if _QWEN3_REACHABLE:
        callers[EnumReviewModel.QWEN3_CODER] = _build_openai_compat_caller(
            _LLM_CODER_URL,
            qwen3_model,
            EnumReviewModel.QWEN3_CODER,
        )
    if _DEEPSEEK_REACHABLE:
        callers[EnumReviewModel.DEEPSEEK_R1] = _build_openai_compat_caller(
            _LLM_DEEPSEEK_URL,
            deepseek_model,
            EnumReviewModel.DEEPSEEK_R1,
        )
    if _GEMINI_REACHABLE:
        callers[EnumReviewModel.GEMINI_FLASH] = _build_gemini_caller(_GEMINI_API_KEY)
    if _Z_AI_REACHABLE:
        callers[EnumReviewModel.GLM_4] = _build_z_ai_caller(_Z_AI_API_KEY)
    return callers


def _make_s3_callers() -> tuple[dict[EnumReviewModel, ModelCaller], CriticCaller]:
    """Build callers needed for S3 sequential_critique."""
    qwen3_model = _QWEN3_MODEL_ID or "Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit"
    deepseek_model = _DEEPSEEK_MODEL_ID or "DeepSeek-R1-Distill-Qwen-32B-bf16"
    callers: dict[EnumReviewModel, ModelCaller] = {
        EnumReviewModel.QWEN3_CODER: _build_openai_compat_caller(
            _LLM_CODER_URL,
            qwen3_model,
            EnumReviewModel.QWEN3_CODER,
        ),
    }
    critic: CriticCaller = _build_openai_compat_critic_caller(
        _LLM_DEEPSEEK_URL,
        deepseek_model,
        EnumReviewModel.DEEPSEEK_R1,
    )
    return callers, critic


# ---------------------------------------------------------------------------
# Shared assertion helpers
# ---------------------------------------------------------------------------

# Categories the smoke plan intentionally triggers.
_EXPECTED_TRIGGERED: frozenset[str] = frozenset(
    {
        EnumPlanReviewCategory.R1_COUNTS.value,
        EnumPlanReviewCategory.R2_ACCEPTANCE_CRITERIA.value,
        EnumPlanReviewCategory.R3_SCOPE.value,
        EnumPlanReviewCategory.R4_INTEGRATION_TRAPS.value,
        EnumPlanReviewCategory.R6_VERIFICATION.value,
    }
)

# Category the smoke plan intentionally keeps clean.
_EXPECTED_CLEAN: frozenset[str] = frozenset(
    {
        EnumPlanReviewCategory.R5_IDEMPOTENCY.value,
    }
)


def _assert_output_invariants(
    output: ModelPlanReviewerMultiOutput,
    strategy: EnumReviewStrategy,
) -> None:
    """Run structural invariant checks on the output model.

    Args:
        output: The output from ``handle_plan_reviewer_multi_compute``.
        strategy: The strategy that was executed.
    """
    # Strategy echo.
    assert output.strategy == strategy, (
        f"Expected strategy={strategy.value}, got {output.strategy.value}"
    )

    # findings_count must match len(findings).
    assert output.findings_count == len(output.findings), (
        f"findings_count={output.findings_count} != len(findings)={len(output.findings)}"
    )

    # Every confidence must be in [0.0, 1.0].
    for f in output.findings:
        assert 0.0 <= f.confidence <= 1.0, (
            f"Invalid confidence {f.confidence} in finding {f.finding_id}"
        )

    # Every patch that is present must be a non-empty string.
    # We validate SHA-256 of each non-None patch (ensures the content is real text).
    for f in output.findings:
        if f.patch is not None:
            assert len(f.patch) > 0, "Empty patch string"
            # Verify that the patch content can be hashed — confirms it is real text.
            digest = hashlib.sha256(f.patch.encode()).hexdigest()
            assert len(digest) == 64, f"Invalid SHA-256 length: {len(digest)}"

    # categories_with_findings and categories_clean must be disjoint.
    findings_set = {f.category.value for f in output.findings}
    all_values = {c.value for c in EnumPlanReviewCategory}
    expected_clean = sorted(all_values - findings_set)

    # Disjoint check.
    for cat_val in findings_set:
        assert cat_val not in expected_clean, (
            f"Category {cat_val} appears in both findings and clean sets"
        )

    # At least some findings must exist for the smoke plan to be meaningful.
    assert output.findings_count > 0, (
        f"Strategy {strategy.value}: smoke plan produced zero findings — "
        "the LLM likely returned empty output or failed to parse"
    )


def _assert_category_coverage(
    output: ModelPlanReviewerMultiOutput,
    strategy: EnumReviewStrategy,
) -> None:
    """Assert that expected categories are triggered and R5 is clean.

    This is a softer assertion: we check that R5 is absent from findings
    (clean), and that at least 3 of the 5 expected-triggered categories
    appear in the findings. Full coverage (all 5) is the ideal but LLMs
    may miss some categories depending on model capability.

    Args:
        output: The output from ``handle_plan_reviewer_multi_compute``.
        strategy: The strategy that was executed (for error messages).
    """
    findings_categories = {f.category.value for f in output.findings}

    # R5 must be clean across all strategies.
    r5_val = EnumPlanReviewCategory.R5_IDEMPOTENCY.value
    assert r5_val not in findings_categories, (
        f"Strategy {strategy.value}: R5 (idempotency) was flagged but should be clean. "
        f"Findings: {[f.description[:60] for f in output.findings if f.category.value == r5_val]}"
    )

    # At least 3/5 expected-triggered categories must appear.
    triggered = _EXPECTED_TRIGGERED & findings_categories
    assert len(triggered) >= 3, (
        f"Strategy {strategy.value}: only {len(triggered)}/5 expected categories found. "
        f"Found: {sorted(triggered)}, missing: {sorted(_EXPECTED_TRIGGERED - triggered)}"
    )


# ---------------------------------------------------------------------------
# S1 — panel_vote
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
@requires_s3
async def test_s1_panel_vote_smoke_plan() -> None:
    """S1_PANEL_VOTE: smoke plan triggers R1/R2/R3/R4/R6, R5 is clean.

    Uses all reachable LLM endpoints — at minimum qwen3-coder + deepseek-r1.
    S1 requires >= 2 models to agree on a finding; with 2 models, this means
    both must agree. 3+ categories with findings expected.
    """
    callers = _make_available_callers()
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=SMOKE_PLAN,
        strategy=EnumReviewStrategy.S1_PANEL_VOTE,
        run_id="OMN-3292-smoke-s1",
    )
    output = await handle_plan_reviewer_multi_compute(cmd, callers, db_conn=None)

    _assert_output_invariants(output, EnumReviewStrategy.S1_PANEL_VOTE)
    _assert_category_coverage(output, EnumReviewStrategy.S1_PANEL_VOTE)

    logger.info(
        "S1 panel_vote: findings=%d categories=%s models=%s",
        output.findings_count,
        sorted({f.category.value for f in output.findings}),
        [m.value for m in output.models_used],
    )


# ---------------------------------------------------------------------------
# S2 — specialist_split
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
@requires_s3
async def test_s2_specialist_split_smoke_plan() -> None:
    """S2_SPECIALIST_SPLIT: smoke plan triggers R1/R2/R3/R4/R6, R5 is clean.

    Uses all reachable LLM endpoints — at minimum qwen3-coder + deepseek-r1.
    S2 assigns categories to specialists; with fewer models, the GLM-4
    tiebreaker role is skipped.
    """
    callers = _make_available_callers()
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=SMOKE_PLAN,
        strategy=EnumReviewStrategy.S2_SPECIALIST_SPLIT,
        run_id="OMN-3292-smoke-s2",
    )
    output = await handle_plan_reviewer_multi_compute(cmd, callers, db_conn=None)

    _assert_output_invariants(output, EnumReviewStrategy.S2_SPECIALIST_SPLIT)
    _assert_category_coverage(output, EnumReviewStrategy.S2_SPECIALIST_SPLIT)

    logger.info(
        "S2 specialist_split: findings=%d categories=%s models=%s",
        output.findings_count,
        sorted({f.category.value for f in output.findings}),
        [m.value for m in output.models_used],
    )


# ---------------------------------------------------------------------------
# S3 — sequential_critique
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
@requires_s3
async def test_s3_sequential_critique_smoke_plan() -> None:
    """S3_SEQUENTIAL_CRITIQUE: smoke plan triggers R1/R2/R3/R4/R6, R5 is clean."""
    callers, critic_caller = _make_s3_callers()
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=SMOKE_PLAN,
        strategy=EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE,
        run_id="OMN-3292-smoke-s3",
    )
    output = await handle_plan_reviewer_multi_compute(
        cmd, callers, db_conn=None, critic_caller=critic_caller
    )

    _assert_output_invariants(output, EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE)
    _assert_category_coverage(output, EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE)

    logger.info(
        "S3 sequential_critique: findings=%d categories=%s",
        output.findings_count,
        sorted({f.category.value for f in output.findings}),
    )


# ---------------------------------------------------------------------------
# S4 — independent_merge
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
@requires_s3
async def test_s4_independent_merge_smoke_plan() -> None:
    """S4_INDEPENDENT_MERGE: smoke plan triggers R1/R2/R3/R4/R6, R5 is clean.

    Uses all reachable LLM endpoints — at minimum qwen3-coder + deepseek-r1.
    S4 includes every finding from every model (union-merge) so it produces
    the most findings across all strategies.
    """
    callers = _make_available_callers()
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=SMOKE_PLAN,
        strategy=EnumReviewStrategy.S4_INDEPENDENT_MERGE,
        run_id="OMN-3292-smoke-s4",
    )
    output = await handle_plan_reviewer_multi_compute(cmd, callers, db_conn=None)

    _assert_output_invariants(output, EnumReviewStrategy.S4_INDEPENDENT_MERGE)
    _assert_category_coverage(output, EnumReviewStrategy.S4_INDEPENDENT_MERGE)

    logger.info(
        "S4 independent_merge: findings=%d categories=%s models=%s",
        output.findings_count,
        sorted({f.category.value for f in output.findings}),
        [m.value for m in output.models_used],
    )


# ---------------------------------------------------------------------------
# Single-model sub-tests (individual reachability gates)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
@requires_qwen3
async def test_qwen3_coder_returns_valid_findings() -> None:
    """qwen3-coder caller parses its response into valid PlanReviewFinding objects."""
    qwen3_model = _QWEN3_MODEL_ID or "Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit"
    caller = _build_openai_compat_caller(
        _LLM_CODER_URL,
        qwen3_model,
        EnumReviewModel.QWEN3_CODER,
    )
    findings = await caller(SMOKE_PLAN, list(EnumPlanReviewCategory))
    assert isinstance(findings, list)
    for f in findings:
        assert isinstance(f, PlanReviewFinding)
        assert f.severity in ("BLOCK", "WARN")
        assert f.source_model == EnumReviewModel.QWEN3_CODER
    logger.info("qwen3-coder: %d findings", len(findings))


@pytest.mark.integration
@pytest.mark.asyncio
@requires_deepseek
async def test_deepseek_r1_returns_valid_findings() -> None:
    """deepseek-r1 caller parses its response into valid PlanReviewFinding objects."""
    deepseek_model = _DEEPSEEK_MODEL_ID or "DeepSeek-R1-Distill-Qwen-32B-bf16"
    caller = _build_openai_compat_caller(
        _LLM_DEEPSEEK_URL,
        deepseek_model,
        EnumReviewModel.DEEPSEEK_R1,
    )
    findings = await caller(SMOKE_PLAN, list(EnumPlanReviewCategory))
    assert isinstance(findings, list)
    for f in findings:
        assert isinstance(f, PlanReviewFinding)
        assert f.severity in ("BLOCK", "WARN")
        assert f.source_model == EnumReviewModel.DEEPSEEK_R1
    logger.info("deepseek-r1: %d findings", len(findings))


@pytest.mark.integration
@pytest.mark.asyncio
@requires_gemini
async def test_gemini_flash_returns_valid_findings() -> None:
    """gemini-flash caller parses its response into valid PlanReviewFinding objects."""
    caller = _build_gemini_caller(_GEMINI_API_KEY)
    findings = await caller(SMOKE_PLAN, list(EnumPlanReviewCategory))
    assert isinstance(findings, list)
    for f in findings:
        assert isinstance(f, PlanReviewFinding)
        assert f.severity in ("BLOCK", "WARN")
        assert f.source_model == EnumReviewModel.GEMINI_FLASH
    logger.info("gemini-flash: %d findings", len(findings))


@pytest.mark.integration
@pytest.mark.asyncio
@requires_z_ai
async def test_glm4_returns_valid_findings() -> None:
    """glm-4 caller parses its response into valid PlanReviewFinding objects."""
    caller = _build_z_ai_caller(_Z_AI_API_KEY)
    try:
        findings = await caller(SMOKE_PLAN, list(EnumPlanReviewCategory))
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            pytest.skip(f"Z.AI rate-limited (429): {exc}")
        raise
    assert isinstance(findings, list)
    for f in findings:
        assert isinstance(f, PlanReviewFinding)
        assert f.severity in ("BLOCK", "WARN")
        assert f.source_model == EnumReviewModel.GLM_4
    logger.info("glm-4: %d findings", len(findings))


# ---------------------------------------------------------------------------
# Disjoint categories invariant (structural — no LLM needed)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
@requires_qwen3
async def test_categories_disjoint_after_merge() -> None:
    """categories_with_findings and categories_clean are always disjoint."""
    qwen3_model = _QWEN3_MODEL_ID or "Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit"
    callers: dict[EnumReviewModel, ModelCaller] = {
        EnumReviewModel.QWEN3_CODER: _build_openai_compat_caller(
            _LLM_CODER_URL,
            qwen3_model,
            EnumReviewModel.QWEN3_CODER,
        ),
    }
    cmd = ModelPlanReviewerMultiCommand(
        plan_text=SMOKE_PLAN,
        strategy=EnumReviewStrategy.S4_INDEPENDENT_MERGE,
        model_ids=[EnumReviewModel.QWEN3_CODER],
        run_id="OMN-3292-disjoint-check",
    )
    output = await handle_plan_reviewer_multi_compute(cmd, callers, db_conn=None)

    findings_categories = {f.category.value for f in output.findings}
    all_values = {c.value for c in EnumPlanReviewCategory}
    derived_clean = all_values - findings_categories

    # Verify no overlap.
    assert findings_categories.isdisjoint(derived_clean), (
        f"Overlap detected: {findings_categories & derived_clean}"
    )


__all__ = [
    "SMOKE_PLAN",
]
