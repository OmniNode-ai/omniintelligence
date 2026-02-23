# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input models for NodeDocRetrievalCompute.

Defines DocSourceConfig (the policy configuration block added to ContextPolicyConfig)
and the input model for a single retrieval request.

Ticket: OMN-2396
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class DocSourceConfig(BaseModel):
    """Policy configuration for document-sourced context item retrieval.

    This model is intended to be embedded in ContextPolicyConfig as an optional
    field. None = document ingestion disabled (no behavior change vs. v0).

    Attributes:
        prefer_narrow_scope:        If True, repo-scoped items rank above
                                    org-wide items via scope_boost.
        doc_token_budget_fraction_default:
                                    Default fraction of session token budget
                                    reserved for document items (0.0-1.0).
        doc_token_budget_fraction_overrides:
                                    Per-intent overrides. Keys are intent
                                    category strings. First matching key wins.
        max_doc_items:              Hard cap on document items per session.
        doc_min_similarity:         Minimum Qdrant similarity for inclusion.
        allow_bootstrap_validated:  Include bootstrapped VALIDATED items
                                    (bootstrap_confidence > 0.0).
        allow_unscored_static_standards:
                                    Include STATIC_STANDARDS items with
                                    zero scored_runs (e.g., freshly ingested
                                    CLAUDE.md).
    """

    model_config = {"frozen": True, "extra": "ignore"}

    prefer_narrow_scope: bool = True
    doc_token_budget_fraction_default: float = Field(default=0.30, ge=0.0, le=1.0)
    doc_token_budget_fraction_overrides: dict[str, float] = Field(
        default_factory=lambda: {
            "architecture": 0.40,
            "refactoring": 0.40,
            "compliance": 0.40,
            "code_generation": 0.25,
            "debugging": 0.20,
        }
    )
    max_doc_items: int = Field(default=8, ge=1)
    doc_min_similarity: float = Field(default=0.65, ge=0.0, le=1.0)
    allow_bootstrap_validated: bool = True
    allow_unscored_static_standards: bool = True


class ModelDocSearchResult(BaseModel):
    """A single Qdrant search result for a context item.

    Represents raw output from a Qdrant semantic search before re-ranking.

    Attributes:
        item_id:              UUID of the ContextItem (matches PG context_items.id).
        similarity:           Cosine similarity score from Qdrant (0.0-1.0).
        source_ref:           Document path (e.g. 'docs/CLAUDE.md').
        tier:                 Promotion tier string ('quarantine', 'validated', 'shared').
        source_type:          Source type string ('static_standards', 'repo_derived', ...).
        crawl_scope:          Repository scope (e.g. 'omninode/omniintelligence').
        content_fingerprint:  SHA-256 fingerprint for deduplication.
        token_estimate:       Estimated token count for budget enforcement.
        bootstrap_confidence: Bootstrap confidence score (0.0 = not bootstrapped).
        section_heading:      Optional section heading from the document.
        correlation_id:       Optional correlation ID for tracing.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    item_id: UUID
    similarity: float = Field(ge=0.0, le=1.0)
    source_ref: str
    tier: str
    source_type: str
    crawl_scope: str
    content_fingerprint: str
    token_estimate: int = Field(ge=0)
    bootstrap_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    section_heading: str | None = None
    correlation_id: str | None = None


class ModelDocRetrievalInput(BaseModel):
    """Input for a single document retrieval pass.

    Attributes:
        search_results:   Raw Qdrant results (pre-filtered by tier/source_type).
        query_scope:      Scope of the current session (e.g. 'omninode/omniintelligence').
                          Used for scope_boost calculation.
        intent_category:  Intent classification of the current query (e.g. 'debugging').
                          Drives adaptive token budget selection.
        total_token_budget:
                          Total token budget available for context assembly.
                          doc items receive a fraction of this.
        config:           DocSourceConfig controlling retrieval behaviour.
        correlation_id:   Optional correlation ID for tracing.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    search_results: tuple[ModelDocSearchResult, ...]
    query_scope: str
    intent_category: str = Field(default="default")
    total_token_budget: int = Field(default=4096, ge=1)
    config: DocSourceConfig = Field(default_factory=DocSourceConfig)
    correlation_id: str | None = None


__all__ = ["DocSourceConfig", "ModelDocRetrievalInput", "ModelDocSearchResult"]
