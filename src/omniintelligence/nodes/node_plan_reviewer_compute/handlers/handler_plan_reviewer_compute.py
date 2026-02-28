# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler for Plan Reviewer Compute Node.

Orchestrates the adversarial plan review workflow:
1. Calls the LLM client with the plan text and selected categories.
2. Parses structured JSON output into typed Pydantic models.
3. Computes per-snippet SHA-256 hashes for patch integrity.
4. Applies patches sequentially to produce plan_text_revised.
5. Returns ModelPlanReviewerComputeOutput.

On LLM or parse failure, returns a single BLOCK finding describing the error
so callers always receive a typed output model rather than a raised exception.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

from omniintelligence.clients.plan_reviewer_llm_client import (
    call_plan_reviewer_llm,
)
from omniintelligence.nodes.node_plan_reviewer_compute.models.model_plan_reviewer_input import (
    ModelPlanReviewerComputeCommand,
)
from omniintelligence.nodes.node_plan_reviewer_compute.models.model_plan_reviewer_output import (
    EnumPlanReviewCategory,
    EnumPlanReviewSeverity,
    ModelPlanReviewerComputeOutput,
    PlanReviewFinding,
    PlanReviewPatch,
)

logger = logging.getLogger(__name__)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _parse_findings(raw_findings: list[dict[str, Any]]) -> list[PlanReviewFinding]:
    findings: list[PlanReviewFinding] = []
    for item in raw_findings:
        try:
            findings.append(
                PlanReviewFinding(
                    category=EnumPlanReviewCategory(item["category"]),
                    severity=EnumPlanReviewSeverity(item["severity"]),
                    issue=item["issue"],
                    fix_description=item["fix_description"],
                    location=item.get("location"),
                )
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping malformed finding item: %s — %s", item, exc)
    return findings


def _parse_patches(
    raw_patches: list[dict[str, Any]],
) -> list[PlanReviewPatch]:
    patches: list[PlanReviewPatch] = []
    for item in raw_patches:
        try:
            before_snippet: str = item["before_snippet"]
            patches.append(
                PlanReviewPatch(
                    location=item["location"],
                    before_snippet_hash=_sha256_hex(before_snippet),
                    before_snippet=before_snippet,
                    after_snippet=item["after_snippet"],
                    finding_ref=EnumPlanReviewCategory(item["finding_ref"]),
                )
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping malformed patch item: %s — %s", item, exc)
    return patches


def _apply_patches(plan_text: str, patches: list[PlanReviewPatch]) -> str:
    """Apply patches sequentially. Skips a patch if before_snippet is not found."""
    result = plan_text
    for patch in patches:
        expected_hash = _sha256_hex(patch.before_snippet)
        if expected_hash != patch.before_snippet_hash:
            logger.warning(
                "Patch hash mismatch for location %r — skipping", patch.location
            )
            continue
        if patch.before_snippet not in result:
            logger.warning(
                "Patch before_snippet not found in plan at location %r — skipping",
                patch.location,
            )
            continue
        result = result.replace(patch.before_snippet, patch.after_snippet, 1)
    return result


def _error_output(message: str) -> ModelPlanReviewerComputeOutput:
    return ModelPlanReviewerComputeOutput(
        findings=[
            PlanReviewFinding(
                category=EnumPlanReviewCategory.R1,
                severity=EnumPlanReviewSeverity.BLOCK,
                issue=f"Plan review failed: {message}",
                fix_description="Retry after resolving the underlying error.",
                location=None,
            )
        ],
        patches=[],
        plan_text_revised=None,
        categories_clean=[],
        categories_with_findings=[EnumPlanReviewCategory.R1],
    )


def handle_plan_reviewer_compute(
    input_data: ModelPlanReviewerComputeCommand,
    llm_url: str | None = None,
) -> ModelPlanReviewerComputeOutput:
    """Run adversarial review on a plan document.

    Synchronous entry point — runs the async LLM call in a new event loop.
    This matches the `type: "sync"` handler_routing declaration in contract.yaml.

    Args:
        input_data: Plan text and selected review categories.
        llm_url: Optional LLM base URL override (for testing).

    Returns:
        Typed output model with findings, patches, and revised plan text.
        Never raises — errors are returned as BLOCK findings.
    """
    category_codes = [c.value for c in input_data.review_categories]

    try:
        raw = asyncio.run(
            call_plan_reviewer_llm(
                plan_text=input_data.plan_text,
                review_categories=category_codes,
                llm_url=llm_url,
            )
        )
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        return _error_output(str(exc))

    try:
        findings = _parse_findings(raw.get("findings", []))
        patches = _parse_patches(raw.get("patches", []))

        categories_with_findings = [
            EnumPlanReviewCategory(c)
            for c in raw.get("categories_with_findings", [])
            if c in EnumPlanReviewCategory._value2member_map_
        ]
        categories_clean = [
            EnumPlanReviewCategory(c)
            for c in raw.get("categories_clean", [])
            if c in EnumPlanReviewCategory._value2member_map_
        ]

        plan_text_revised: str | None = None
        if patches:
            plan_text_revised = _apply_patches(input_data.plan_text, patches)

        return ModelPlanReviewerComputeOutput(
            findings=findings,
            patches=patches,
            plan_text_revised=plan_text_revised,
            categories_clean=categories_clean,
            categories_with_findings=categories_with_findings,
        )
    except Exception as exc:
        logger.error("Output parsing failed: %s", exc)
        return _error_output(f"output parsing failed: {exc}")


__all__ = ["handle_plan_reviewer_compute"]
