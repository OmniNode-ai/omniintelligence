# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node DocPromotionReducer -- source-type-aware ContextItem promotion.

Evaluates ContextItem candidates against source-type-specific promotion gates
and produces tier transition decisions. Pure reducer — does NOT persist.

This node follows the ONEX declarative pattern:
    - DECLARATIVE reducer driven by contract.yaml
    - Pure reduction: no I/O, no side effects
    - Lightweight shell that delegates to handle_doc_promotion

Responsibilities:
    - Dispatch on source_type to select PromotionThresholdSet
    - Apply demotion (VALIDATED->QUARANTINE), Q->V, and V->S gates
    - Enforce signal floor for document items (prevents small-sample promotion)
    - Process attribution signals: RULE_FOLLOWED, STANDARD_CITED,
      PATTERN_VIOLATED, DOC_SECTION_MATCHED

Does NOT:
    - Persist tier transitions (caller handles persistence)
    - Compute attribution signals (received via input candidates)
    - Own connection pool lifecycle

Related:
    - OMN-2395: This node implementation
    - OMN-2394: DocStalenessDetectorEffect (upstream)
    - OMN-2393: ContextItemWriterEffect (writes new items)
    - OMN-2383: DB migrations for context_items tables
"""

from __future__ import annotations

from omnibase_core.nodes.node_reducer import NodeReducer

from omniintelligence.nodes.node_doc_promotion_reducer.models.model_doc_promotion_input import (
    ModelDocPromotionInput,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.model_doc_promotion_output import (
    ModelDocPromotionOutput,
)


class NodeDocPromotionReducer(
    NodeReducer[ModelDocPromotionInput, ModelDocPromotionOutput]
):
    """Declarative reducer node for source-type-aware ContextItem promotion.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Threshold sets are defined in models/model_promotion_threshold_set.py
    and injected into the handler at call time.

    Supported Operations (defined in contract.yaml handler_routing):
        - evaluate_promotion: Evaluate candidates and return tier decisions

    Example:
        ```python
        from omniintelligence.nodes.node_doc_promotion_reducer.handlers import (
            handle_doc_promotion,
        )
        from omniintelligence.nodes.node_doc_promotion_reducer.models import (
            ModelDocPromotionInput,
            ModelPromotionCandidate,
        )

        result = await handle_doc_promotion(
            ModelDocPromotionInput(candidates=(candidate,)),
        )
        ```
    """

    # Pure declarative shell -- all behavior defined in contract.yaml


__all__ = ["NodeDocPromotionReducer"]
