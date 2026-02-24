# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node DocRetrievalCompute -- scope-aware re-ranking and adaptive token budget.

Receives raw Qdrant search results for document-derived ContextItems and
produces a ranked, budget-enforced list ready for context assembly.

This node follows the ONEX declarative pattern:
    - DECLARATIVE compute node driven by contract.yaml
    - Pure computation: no I/O, no Qdrant calls, no side effects
    - Delegates entirely to handle_doc_retrieval

Responsibilities:
    - Filter results below doc_min_similarity threshold
    - Score: final_score = similarity * scope_boost * tier_multiplier * intent_weight
    - Enforce adaptive token budget by intent category
    - Deduplicate by content_fingerprint (first occurrence wins)
    - Cap at max_doc_items

Does NOT:
    - Execute Qdrant queries (caller handles search, passes results in input)
    - Emit DOC_SECTION_MATCHED attribution signals (caller handles emission)
    - Persist ranked items (caller assembles session context)

Related:
    - OMN-2396: This node implementation
    - OMN-2395: DocPromotionReducer (promotion tier management)
    - OMN-2393: ContextItemWriterEffect (writes items to Qdrant)
    - OMN-2394: DocStalenessDetectorEffect (detects stale items upstream)
"""

from __future__ import annotations

from omnibase_core.nodes.node_reducer import NodeReducer

from omniintelligence.nodes.node_doc_retrieval_compute.models.model_doc_retrieval_input import (
    ModelDocRetrievalInput,
)
from omniintelligence.nodes.node_doc_retrieval_compute.models.model_doc_retrieval_output import (
    ModelDocRetrievalOutput,
)


class NodeDocRetrievalCompute(
    NodeReducer[ModelDocRetrievalInput, ModelDocRetrievalOutput]
):
    """Declarative compute node for scope-aware document context retrieval.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Scoring factors (all multiplied together to produce final_score):
        scope_boost:      1.20 (exact) / 0.90 (same org) / 0.80 (org-wide)
        tier_multiplier:  1.15 (SHARED) / 1.00 (earned VALIDATED) /
                          0.85 (bootstrapped VALIDATED)
        intent_weight:    From DOCUMENT_INTENT_TYPE_WEIGHTS table

    Example:
        ```python
        from omniintelligence.nodes.node_doc_retrieval_compute.handlers import (
            handle_doc_retrieval,
        )
        from omniintelligence.nodes.node_doc_retrieval_compute.models import (
            DocSourceConfig,
            ModelDocRetrievalInput,
            ModelDocSearchResult,
        )

        result = await handle_doc_retrieval(
            ModelDocRetrievalInput(
                search_results=search_results,
                query_scope="omninode/omniintelligence",
                intent_category="compliance",
                total_token_budget=4096,
            )
        )
        ```
    """

    # Pure declarative shell -- all behavior defined in contract.yaml


__all__ = ["NodeDocRetrievalCompute"]
