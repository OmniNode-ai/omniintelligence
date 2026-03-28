# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Dispatch handler for LLM-based code entity enrichment.

Enriches code entities with classification, description, and architectural pattern
using Qwen3-14B (LLM_CODER_FAST_URL). Enrichment is supplementary, not foundational --
LLM classifications are stored but never used as primary retrieval keys.

Architecture Decisions:
    - Split file: NOT in dispatch_handlers.py (already large)
    - LLM failure is non-fatal: entity stays unenriched, retried next run
    - Low confidence (<0.7) -> "other": per Invariant S5, don't force an archetype label
    - Prompt template is configuration: constant now, movable to contract YAML later
    - Batch size 25: balances throughput with LLM latency
    - enrichment_version tracks which pass touched the entity

Related:
    - OMN-5664: LLM enrichment handler for code entities
    - OMN-5657: AST-based code pattern extraction system (epic)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

ENRICHMENT_BATCH_SIZE: int = 25
"""Maximum entities to enrich per handler invocation."""

ENRICHMENT_CLASSIFICATIONS: list[str] = [
    "factory",
    "handler",
    "adapter",
    "model",
    "protocol",
    "utility",
    "effect",
    "compute",
    "orchestrator",
    "reducer",
    "repository",
    "middleware",
]
"""Valid classification labels for code entities."""

LOW_CONFIDENCE_THRESHOLD: float = 0.7
"""Below this threshold, classification is stored as 'other'."""

PROMPT_TEMPLATE: str = """Given this Python class:
Name: {entity_name}
Base classes: {bases}
Methods: {methods}
Docstring: {docstring}

1. Classify it as one of: {classifications}
2. Write a 1-sentence description of what it does.
3. What architectural pattern does it follow?

If none fit confidently, use "other".
Respond as JSON: {{"classification": "...", "confidence": 0.0-1.0, "description": "...", "pattern": "..."}}"""
"""Prompt template for LLM classification. Designed to be movable to contract YAML."""


# =============================================================================
# Handler
# =============================================================================


async def handle_code_enrichment(
    *,
    repository: Any,  # RepositoryCodeEntity
    llm_endpoint: str | None = None,
    batch_size: int = ENRICHMENT_BATCH_SIZE,
) -> dict[str, int]:
    """Enrich unenriched code entities with LLM classification.

    Queries Postgres for entities where classification IS NULL, sends each
    to Qwen3-14B for classification, and stores results back. Failures are
    non-fatal: the entity stays unenriched and will be retried on the next run.

    Args:
        repository: RepositoryCodeEntity instance with get_entities_needing_enrichment()
            and update_enrichment() methods.
        llm_endpoint: Override for LLM endpoint URL. Defaults to LLM_CODER_FAST_URL
            env var or http://192.168.86.201:8001.
        batch_size: Maximum entities to process per invocation.

    Returns:
        Dict with 'enriched_count' and 'failed_count'.
    """
    endpoint = llm_endpoint or os.environ.get(
        "LLM_CODER_FAST_URL", "http://192.168.86.201:8001"
    )

    entities = await repository.get_entities_needing_enrichment(limit=batch_size)
    if not entities:
        logger.info("No entities needing enrichment")
        return {"enriched_count": 0, "failed_count": 0}

    enriched = 0
    failed = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for entity in entities:
            try:
                result = await _enrich_single_entity(client, endpoint, entity)
                if result:
                    classification = result.get("classification", "other")
                    confidence = result.get("confidence", 0.0)

                    # Low confidence -> store as "other" (Invariant S5)
                    if confidence < LOW_CONFIDENCE_THRESHOLD:
                        classification = "other"

                    await repository.update_enrichment(
                        entity_id=str(entity["id"]),
                        classification=classification,
                        llm_description=result.get("description", ""),
                        architectural_pattern=result.get("pattern", ""),
                        classification_confidence=confidence,
                        enrichment_version="1.0.0",
                    )
                    enriched += 1
                else:
                    failed += 1
            except Exception:
                logger.exception(
                    "Failed to enrich entity %s", entity.get("entity_name")
                )
                failed += 1

    logger.info("Enrichment complete: %d enriched, %d failed", enriched, failed)
    return {"enriched_count": enriched, "failed_count": failed}


# =============================================================================
# Single Entity Enrichment
# =============================================================================


async def _enrich_single_entity(
    client: httpx.AsyncClient,
    endpoint: str,
    entity: dict[str, Any],
) -> dict[str, Any] | None:
    """Call LLM for a single entity. Returns parsed JSON or None on failure."""
    prompt = PROMPT_TEMPLATE.format(
        entity_name=entity.get("entity_name", ""),
        bases=", ".join(entity.get("bases") or []),
        methods=", ".join(m.get("name", "") for m in (entity.get("methods") or [])),
        docstring=entity.get("docstring") or "(none)",
        classifications=", ".join(ENRICHMENT_CLASSIFICATIONS),
    )

    try:
        response = await client.post(
            f"{endpoint}/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.1,
            },
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        # Parse JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result: dict[str, Any] = json.loads(content)
        return result
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError):
        logger.warning("LLM enrichment failed for %s", entity.get("entity_name"))
        return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ENRICHMENT_BATCH_SIZE",
    "ENRICHMENT_CLASSIFICATIONS",
    "LOW_CONFIDENCE_THRESHOLD",
    "PROMPT_TEMPLATE",
    "handle_code_enrichment",
]
