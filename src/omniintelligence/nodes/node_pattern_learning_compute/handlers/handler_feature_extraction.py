# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""AST-based feature extraction handler for pattern learning.

This handler extracts features from training data items to enable pattern clustering.
It sits between the orchestrator (receives TrainingDataItemDict) and clustering
(emits ExtractedFeaturesDict).

OUTPUT CONTRACT (STRICT):
    - Output is normalized, domain-agnostic ExtractedFeaturesDict
    - Downstream handlers MUST NOT re-parse ASTs
    - All features are deterministic given the same input

PROVENANCE INVARIANT:
    - item_id is preserved from input to output
    - labels are preserved from input to output
    - language is preserved from input to output

DETERMINISM INVARIANT:
    - Same input always produces same output
    - Identifiers are normalized (lowercase, sorted, deduped)
    - Batch processing sorts by item_id before processing

GRACEFUL FALLBACK:
    - Non-Python code returns minimal features with extraction_quality="minimal"
    - Syntax errors return minimal features with extraction_quality="minimal"
    - Handler NEVER crashes - always returns valid ExtractedFeaturesDict

Usage:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_feature_extraction import (
        extract_features,
        extract_features_batch,
    )

    # Single item extraction
    features = extract_features(training_item)

    # Batch extraction with deterministic ordering
    features_list = extract_features_batch(training_items)
"""

from __future__ import annotations

from omniintelligence.nodes.node_pattern_learning_compute.handlers.feature_extraction_core import (
    _extract_features,
    _extract_features_batch,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    ExtractedFeaturesDict,
)
from omniintelligence.nodes.node_pattern_learning_compute.models.model_feature_extraction_item_request import (
    ModelFeatureExtractionItemRequest,
)
from omniintelligence.nodes.node_pattern_learning_compute.models.model_feature_extraction_request import (
    ModelFeatureExtractionRequest,
)


class HandlerFeatureExtractionItem:
    """Typed entry point for _extract_features."""

    def handle(
        self, request: ModelFeatureExtractionItemRequest
    ) -> ExtractedFeaturesDict:
        """Delegate to the preserved computation."""
        return _extract_features(request.item)


class HandlerFeatureExtraction:
    """Typed entry point for _extract_features_batch."""

    def handle(
        self, request: ModelFeatureExtractionRequest
    ) -> list[ExtractedFeaturesDict]:
        """Delegate to the preserved computation."""
        return _extract_features_batch(request.items)


__all__ = [
    "HandlerFeatureExtractionItem",
    "HandlerFeatureExtraction",
]
