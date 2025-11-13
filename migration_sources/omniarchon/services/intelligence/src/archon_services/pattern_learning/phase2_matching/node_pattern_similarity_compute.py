#!/usr/bin/env python3
"""
Pattern Similarity Scoring Algorithm - ONEX Compliant Compute Node

Implements 5-component pattern similarity calculation for semantic pattern matching.

Components:
1. Concept Overlap (30%): Jaccard similarity of concepts
2. Theme Similarity (20%): Jaccard similarity of themes
3. Domain Alignment (20%): Domain indicator overlap
4. Structural Pattern Match (15%): Pattern type overlap
5. Relationship Type Match (15%): Relationship chain similarity

Performance Target: <100ms per comparison

Author: Archon Intelligence Team
Date: 2025-10-02
Track: 3 Phase 2 - Pattern Matching
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# ============================================================================
# SemanticAnalysisResult Mock (will be imported from langextract in production)
# ============================================================================


@dataclass
class SemanticAnalysisResult:
    """
    Results from semantic analysis (from langextract service).

    This is a simplified version for the pattern similarity scorer.
    In production, this will be imported from langextract service.
    """

    # Semantic features
    concepts: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    domain_indicators: List[str] = field(default_factory=list)

    # Pattern information
    semantic_patterns: List[Any] = field(default_factory=list)

    # Metrics
    semantic_density: float = 0.0
    conceptual_coherence: float = 0.0
    thematic_consistency: float = 0.0

    # Context
    semantic_context: Dict[str, Any] = field(default_factory=dict)
    primary_topics: List[str] = field(default_factory=list)
    topic_weights: Dict[str, float] = field(default_factory=dict)


# ============================================================================
# Configuration
# ============================================================================


@dataclass
class PatternSimilarityConfig:
    """
    Configuration for pattern similarity scoring.

    Defines weights for each component of the similarity calculation.
    All weights must sum to 1.0 for proper normalization.
    """

    concept_weight: float = 0.30
    theme_weight: float = 0.20
    domain_weight: float = 0.20
    structure_weight: float = 0.15
    relationship_weight: float = 0.15

    def __post_init__(self):
        """Validate that weights sum to 1.0."""
        total_weight = (
            self.concept_weight
            + self.theme_weight
            + self.domain_weight
            + self.structure_weight
            + self.relationship_weight
        )
        if not (0.99 <= total_weight <= 1.01):  # Allow small floating point errors
            raise ValueError(
                f"Weights must sum to 1.0, got {total_weight}. "
                f"Weights: concept={self.concept_weight}, theme={self.theme_weight}, "
                f"domain={self.domain_weight}, structure={self.structure_weight}, "
                f"relationship={self.relationship_weight}"
            )


# ============================================================================
# Pattern Similarity Scorer
# ============================================================================


class PatternSimilarityScorer:
    """
    Calculates semantic similarity between task and pattern.

    Uses 5-component weighted scoring:
    1. Concept Overlap (30%): Jaccard similarity of concepts
    2. Theme Similarity (20%): Jaccard similarity of themes
    3. Domain Alignment (20%): Domain indicator overlap
    4. Structural Pattern Match (15%): Pattern type overlap
    5. Relationship Type Match (15%): Relationship chain similarity

    Performance: <100ms per comparison
    """

    def __init__(self, config: Optional[PatternSimilarityConfig] = None):
        """
        Initialize the pattern similarity scorer.

        Args:
            config: Optional configuration with custom weights
        """
        self.config = config or PatternSimilarityConfig()

    def calculate_similarity(
        self,
        task_semantic: SemanticAnalysisResult,
        pattern_semantic: SemanticAnalysisResult,
    ) -> Dict[str, float]:
        """
        Calculate similarity between task and pattern semantic features.

        Args:
            task_semantic: Semantic analysis result from the current task
            pattern_semantic: Semantic analysis result from the historical pattern

        Returns:
            Dictionary containing:
                - concept_score: Concept overlap score (0.0-1.0)
                - theme_score: Theme similarity score (0.0-1.0)
                - domain_score: Domain alignment score (0.0-1.0)
                - structure_score: Structural pattern match score (0.0-1.0)
                - relationship_score: Relationship type match score (0.0-1.0)
                - final_similarity: Weighted final similarity score (0.0-1.0)
        """
        # Calculate component scores
        concept_score = self._calculate_jaccard_similarity(
            task_semantic.concepts, pattern_semantic.concepts
        )

        theme_score = self._calculate_jaccard_similarity(
            task_semantic.themes, pattern_semantic.themes
        )

        domain_score = self._calculate_jaccard_similarity(
            task_semantic.domain_indicators, pattern_semantic.domain_indicators
        )

        structure_score = self._calculate_structure_similarity(
            task_semantic, pattern_semantic
        )

        relationship_score = self._calculate_relationship_similarity(
            task_semantic, pattern_semantic
        )

        # Calculate weighted final similarity
        final_similarity = (
            concept_score * self.config.concept_weight
            + theme_score * self.config.theme_weight
            + domain_score * self.config.domain_weight
            + structure_score * self.config.structure_weight
            + relationship_score * self.config.relationship_weight
        )

        return {
            "concept_score": concept_score,
            "theme_score": theme_score,
            "domain_score": domain_score,
            "structure_score": structure_score,
            "relationship_score": relationship_score,
            "final_similarity": final_similarity,
        }

    def _calculate_jaccard_similarity(
        self, set_a: List[str], set_b: List[str]
    ) -> float:
        """
        Calculate Jaccard similarity between two sets.

        Jaccard similarity = |A ∩ B| / |A ∪ B|

        Args:
            set_a: First set of items
            set_b: Second set of items

        Returns:
            Jaccard similarity score (0.0-1.0)
        """
        # Handle empty lists
        if not set_a and not set_b:
            return 1.0  # Both empty = perfect match
        if not set_a or not set_b:
            return 0.0  # One empty = no match

        # Convert to sets for efficient operations
        set_a_norm = set(item.lower() for item in set_a)
        set_b_norm = set(item.lower() for item in set_b)

        # Calculate Jaccard similarity
        intersection = len(set_a_norm & set_b_norm)
        union = len(set_a_norm | set_b_norm)

        if union == 0:
            return 0.0

        return intersection / union

    def _calculate_structure_similarity(
        self,
        task_semantic: SemanticAnalysisResult,
        pattern_semantic: SemanticAnalysisResult,
    ) -> float:
        """
        Calculate structural pattern similarity.

        Compares pattern types and structural features from semantic patterns.

        Args:
            task_semantic: Task semantic analysis
            pattern_semantic: Pattern semantic analysis

        Returns:
            Structure similarity score (0.0-1.0)
        """
        # Extract pattern types from semantic patterns
        task_pattern_types = self._extract_pattern_types(
            task_semantic.semantic_patterns
        )
        pattern_pattern_types = self._extract_pattern_types(
            pattern_semantic.semantic_patterns
        )

        # Use Jaccard similarity for pattern types
        return self._calculate_jaccard_similarity(
            task_pattern_types, pattern_pattern_types
        )

    def _calculate_relationship_similarity(
        self,
        task_semantic: SemanticAnalysisResult,
        pattern_semantic: SemanticAnalysisResult,
    ) -> float:
        """
        Calculate relationship type similarity.

        Compares relationship chains and types from semantic context.

        Args:
            task_semantic: Task semantic analysis
            pattern_semantic: Pattern semantic analysis

        Returns:
            Relationship similarity score (0.0-1.0)
        """
        # Extract relationship types from semantic context
        task_relationships = self._extract_relationship_types(
            task_semantic.semantic_context
        )
        pattern_relationships = self._extract_relationship_types(
            pattern_semantic.semantic_context
        )

        # Use Jaccard similarity for relationship types
        return self._calculate_jaccard_similarity(
            task_relationships, pattern_relationships
        )

    def _extract_pattern_types(self, semantic_patterns: List[Any]) -> List[str]:
        """
        Extract pattern types from semantic patterns.

        Args:
            semantic_patterns: List of semantic pattern objects

        Returns:
            List of pattern type strings
        """
        pattern_types = []
        for pattern in semantic_patterns:
            # Handle both dict and object patterns
            if isinstance(pattern, dict):
                pattern_type = pattern.get("pattern_type") or pattern.get("type")
                if pattern_type:
                    pattern_types.append(str(pattern_type))
            elif hasattr(pattern, "pattern_type"):
                pattern_types.append(str(pattern.pattern_type))
            elif hasattr(pattern, "type"):
                pattern_types.append(str(pattern.type))

        return pattern_types

    def _extract_relationship_types(
        self, semantic_context: Dict[str, Any]
    ) -> List[str]:
        """
        Extract relationship types from semantic context.

        Args:
            semantic_context: Dictionary containing semantic context information

        Returns:
            List of relationship type strings
        """
        relationship_types = []

        # Check for relationships in context
        if "relationships" in semantic_context:
            relationships = semantic_context["relationships"]
            if isinstance(relationships, list):
                for rel in relationships:
                    if isinstance(rel, dict):
                        rel_type = rel.get("type") or rel.get("relationship_type")
                        if rel_type:
                            relationship_types.append(str(rel_type))
                    elif hasattr(rel, "type"):
                        relationship_types.append(str(rel.type))
                    elif hasattr(rel, "relationship_type"):
                        relationship_types.append(str(rel.relationship_type))

        # Check for relationship chains
        if "relationship_chains" in semantic_context:
            chains = semantic_context["relationship_chains"]
            if isinstance(chains, list):
                for chain in chains:
                    if isinstance(chain, dict) and "types" in chain:
                        relationship_types.extend(chain["types"])

        return relationship_types


# ============================================================================
# ONEX Compute Node
# ============================================================================


class NodePatternSimilarityCompute:
    """
    ONEX-compliant Compute node for pattern similarity calculation.

    Pure functional computation with no side effects.
    Implements the 5-component similarity scoring algorithm.

    Performance: <100ms per comparison
    ONEX Compliance: Pure Compute node, deterministic, no I/O
    """

    def __init__(self, config: Optional[PatternSimilarityConfig] = None):
        """
        Initialize the compute node.

        Args:
            config: Optional configuration with custom weights
        """
        self.scorer = PatternSimilarityScorer(config)

    async def execute_compute(
        self,
        task_semantic: SemanticAnalysisResult,
        pattern_semantic: SemanticAnalysisResult,
        correlation_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Execute pattern similarity computation (ONEX Compute interface).

        Args:
            task_semantic: Semantic analysis result from the current task
            pattern_semantic: Semantic analysis result from the historical pattern
            correlation_id: Optional correlation ID for tracing

        Returns:
            Dictionary containing:
                - similarity_scores: Component and final similarity scores
                - correlation_id: Correlation ID for tracing
                - computation_metadata: Metadata about the computation
        """
        # Calculate similarity scores
        similarity_scores = self.scorer.calculate_similarity(
            task_semantic, pattern_semantic
        )

        # Build result
        result = {
            "similarity_scores": similarity_scores,
            "correlation_id": str(correlation_id or uuid4()),
            "computation_metadata": {
                "concept_count_task": len(task_semantic.concepts),
                "concept_count_pattern": len(pattern_semantic.concepts),
                "theme_count_task": len(task_semantic.themes),
                "theme_count_pattern": len(pattern_semantic.themes),
                "domain_count_task": len(task_semantic.domain_indicators),
                "domain_count_pattern": len(pattern_semantic.domain_indicators),
            },
        }

        return result

    def compute_similarity_sync(
        self,
        task_semantic: SemanticAnalysisResult,
        pattern_semantic: SemanticAnalysisResult,
    ) -> Dict[str, float]:
        """
        Synchronous version for simpler usage patterns.

        Args:
            task_semantic: Semantic analysis result from the current task
            pattern_semantic: Semantic analysis result from the historical pattern

        Returns:
            Dictionary containing component and final similarity scores
        """
        return self.scorer.calculate_similarity(task_semantic, pattern_semantic)
