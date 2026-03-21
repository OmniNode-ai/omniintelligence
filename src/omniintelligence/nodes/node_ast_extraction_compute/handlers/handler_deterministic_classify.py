# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Deterministic node classifier for code entities.

Ported from Archive/omninode_bridge NodeClassifier. Adapted to work on
ModelCodeEntity fields and read classification rules from contract config.

Multi-factor weighted scoring:
- domain: 0.30 (database → effect, math → compute)
- operation: 0.30 (aggregate → reducer, coordinate → orchestrator)
- keyword: 0.25 (keyword presence in entity metadata)
- feature: 0.15 (connection_pooling → effect, caching → compute)

All classification rules live in contract YAML — adding a new keyword = editing config.

Reference: OMN-5674
"""

from __future__ import annotations

import logging
from typing import Any

from omniintelligence.nodes.node_ast_extraction_compute.models.model_classification_result import (
    ModelClassificationResult,
)

logger = logging.getLogger(__name__)


class DeterministicClassifier:
    """Classifies code entities into architectural roles using weighted scoring.

    All classification rules (keywords, domains, operations, features, weights)
    are read from contract config. No hardcoded classification logic.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize from contract config's deterministic_classification section.

        Args:
            config: The ``config.deterministic_classification`` dict.
        """
        weights = config.get("scoring_weights", {})
        self._weight_domain = weights.get("domain", 0.30)
        self._weight_operation = weights.get("operation", 0.30)
        self._weight_keyword = weights.get("keyword", 0.25)
        self._weight_feature = weights.get("feature", 0.15)
        self._min_confidence = config.get("min_confidence", 0.4)

        # Build classification rules from config
        self._classifications: dict[str, dict[str, list[str]]] = {}
        for name, rules in config.get("classifications", {}).items():
            self._classifications[name] = {
                "keywords": [k.lower() for k in rules.get("keywords", [])],
                "domains": [d.lower() for d in rules.get("domains", [])],
                "operations": [o.lower() for o in rules.get("operations", [])],
                "features": [f.lower() for f in rules.get("features", [])],
            }

    def classify(
        self,
        *,
        entity_name: str,
        bases: list[str] | None = None,
        methods: list[dict[str, Any]] | None = None,
        decorators: list[str] | None = None,
        docstring: str | None = None,
    ) -> ModelClassificationResult:
        """Classify an entity using multi-factor weighted scoring.

        Args:
            entity_name: Name of the entity.
            bases: Base class names.
            methods: Method descriptors [{name, args, ...}].
            decorators: Decorator expressions.
            docstring: Entity docstring.

        Returns:
            ModelClassificationResult with node_type, confidence, alternatives.
        """
        # Build searchable text from entity metadata
        text_parts = [entity_name.lower()]
        if bases:
            text_parts.extend(b.lower() for b in bases)
        if methods:
            text_parts.extend(m.get("name", "").lower() for m in methods)
        if decorators:
            text_parts.extend(d.lower() for d in decorators)
        if docstring:
            text_parts.append(docstring.lower())

        text = " ".join(text_parts)

        # Extract method names for operation matching
        method_names = [m.get("name", "").lower() for m in (methods or [])]

        # Score each classification
        scores: dict[str, float] = {}
        for cls_name, rules in self._classifications.items():
            score = 0.0

            # Factor 1: Domain (from base classes and entity name)
            domain_score = self._score_list_match(
                rules["domains"], text_parts[:1] + (bases or [])
            )
            score += domain_score * self._weight_domain

            # Factor 2: Operations (from method names)
            operation_score = self._score_list_overlap(
                rules["operations"], method_names
            )
            score += operation_score * self._weight_operation

            # Factor 3: Keywords (from all text)
            keyword_score = self._score_keyword_presence(rules["keywords"], text)
            score += keyword_score * self._weight_keyword

            # Factor 4: Features (from decorators, docstring, method names)
            feature_text = " ".join(
                (decorators or []) + method_names + ([docstring or ""])
            ).lower()
            feature_score = self._score_list_match(rules["features"], [feature_text])
            score += feature_score * self._weight_feature

            scores[cls_name] = score

        if not scores:
            return ModelClassificationResult(
                node_type="unclassified", confidence=0.0, alternatives={}
            )

        # Select best
        best_type = max(scores, key=lambda k: scores[k])
        best_score = scores[best_type]

        # Build alternatives (exclude best, only those > 0.1)
        alternatives = {
            k: round(v, 4)
            for k, v in sorted(scores.items(), key=lambda x: -x[1])
            if k != best_type and v > 0.1
        }

        # Apply minimum confidence threshold
        if best_score < self._min_confidence:
            return ModelClassificationResult(
                node_type="unclassified",
                confidence=round(best_score, 4),
                alternatives=alternatives,
            )

        return ModelClassificationResult(
            node_type=best_type,
            confidence=round(best_score, 4),
            alternatives=alternatives,
        )

    @staticmethod
    def _score_list_match(needles: list[str], haystacks: list[str]) -> float:
        """Score based on whether any needle appears in any haystack string."""
        if not needles:
            return 0.0
        haystack_text = " ".join(h.lower() for h in haystacks)
        matches = sum(1 for n in needles if n in haystack_text)
        return min(matches / max(len(needles), 1), 1.0)

    @staticmethod
    def _score_list_overlap(needles: list[str], targets: list[str]) -> float:
        """Score based on overlap between needle set and target set."""
        if not needles or not targets:
            return 0.0
        target_set = set(targets)
        matches = sum(1 for n in needles if n in target_set)
        return min(matches / len(targets) if targets else 0.0, 1.0)

    @staticmethod
    def _score_keyword_presence(keywords: list[str], text: str) -> float:
        """Score based on keyword presence in text."""
        if not keywords:
            return 0.0
        matches = sum(1 for kw in keywords if kw in text)
        return min(matches / 3.0, 1.0)  # 3+ matches = full score
