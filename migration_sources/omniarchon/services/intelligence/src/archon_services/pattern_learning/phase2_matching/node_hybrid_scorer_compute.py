#!/usr/bin/env python3
"""
Hybrid Score Combiner - ONEX Compute Node

Combines vector similarity (Phase 1 Ollama/Qdrant) and pattern similarity
(Phase 2 langextract) into adaptive hybrid score with confidence metrics.

Part of Track 3 Phase 2 - Pattern Learning Engine.

Author: Archon Intelligence Team
Date: 2025-10-02
"""

import time
from typing import Dict, Optional, Tuple

from src.archon_services.pattern_learning.phase2_matching.models.model_hybrid_score import (
    EnumAdaptiveStrategy,
    ModelHybridScore,
    ModelHybridScoreConfig,
    ModelHybridScoreInput,
    ModelHybridScoreOutput,
)

# ============================================================================
# ONEX Compute Node Implementation
# ============================================================================


class NodeHybridScorerCompute:
    """
    ONEX-Compliant Compute Node for Hybrid Score Calculation.

    Combines vector and pattern similarity scores using adaptive weighting
    strategies based on task characteristics.

    Adaptive Strategies:
    - High complexity → Increase pattern weight (more structural analysis)
    - Low complexity → Increase vector weight (simple semantic matching)
    - Domain-specific → Increase pattern weight by 0.1
    - Score agreement → Higher confidence when scores align

    ONEX Patterns:
    - Pure functional computation (no side effects)
    - Deterministic results for same inputs
    - Correlation ID propagation
    - Performance optimized (<10ms target)
    """

    def __init__(self, config: Optional[ModelHybridScoreConfig] = None) -> None:
        """
        Initialize hybrid scorer with configuration.

        Args:
            config: Optional configuration override
        """
        # Use default config with HYBRID strategy to support both complexity and domain adjustments
        default_config = ModelHybridScoreConfig(
            default_vector_weight=0.7,
            default_pattern_weight=0.3,
            enable_adaptive_weights=True,
            adaptive_strategy=EnumAdaptiveStrategy.HYBRID,  # Support all adaptations
        )
        self.config = config or default_config

        # Statistics tracking
        self._calculation_count = 0
        self._total_processing_time = 0.0
        self._adaptive_adjustment_count = 0

    # ========================================================================
    # ONEX Execute Compute Method (Primary Interface)
    # ========================================================================

    async def execute_compute(
        self, input_state: ModelHybridScoreInput
    ) -> ModelHybridScoreOutput:
        """
        Execute hybrid score calculation (ONEX NodeCompute interface).

        Pure functional method with no side effects, deterministic results.

        Args:
            input_state: Input state with vector and pattern scores

        Returns:
            ModelHybridScoreOutput: Hybrid score with confidence metrics
        """
        start_time = time.time()

        try:
            # Use config override if provided
            config = input_state.config or self.config

            # Calculate weights (adaptive or fixed)
            vector_weight, pattern_weight, weights_adjusted, adjustment_reason = (
                self._calculate_weights(
                    config=config,
                    task_characteristics=input_state.task_characteristics,
                )
            )

            # Calculate hybrid score
            hybrid_score = (
                input_state.vector_similarity * vector_weight
                + input_state.pattern_similarity * pattern_weight
            )

            # Calculate confidence metrics
            confidence, score_agreement = self._calculate_confidence(
                vector_score=input_state.vector_similarity,
                pattern_score=input_state.pattern_similarity,
                hybrid_score=hybrid_score,
            )

            # Build result
            result = ModelHybridScore(
                hybrid_score=hybrid_score,
                vector_score=input_state.vector_similarity,
                pattern_score=input_state.pattern_similarity,
                vector_weight=vector_weight,
                pattern_weight=pattern_weight,
                weights_adjusted=weights_adjusted,
                adjustment_reason=adjustment_reason,
                confidence=confidence,
                score_agreement=score_agreement,
                correlation_id=input_state.correlation_id,
                metadata={
                    "config_used": {
                        "adaptive_enabled": config.enable_adaptive_weights,
                        "strategy": config.adaptive_strategy.value,
                    }
                },
            )

            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000

            # Track statistics
            self._calculation_count += 1
            self._total_processing_time += processing_time_ms
            if weights_adjusted:
                self._adaptive_adjustment_count += 1

            return ModelHybridScoreOutput(
                result=result,
                processing_time_ms=processing_time_ms,
                correlation_id=input_state.correlation_id,
                metadata={
                    "calculation_count": self._calculation_count,
                    "avg_processing_time_ms": self._total_processing_time
                    / self._calculation_count,
                    "adaptive_adjustment_rate": (
                        self._adaptive_adjustment_count / self._calculation_count
                        if self._calculation_count > 0
                        else 0.0
                    ),
                },
            )

        except Exception as e:
            # Graceful error handling with fallback to default weights
            processing_time_ms = (time.time() - start_time) * 1000

            fallback_result = ModelHybridScore(
                hybrid_score=(
                    input_state.vector_similarity * 0.7
                    + input_state.pattern_similarity * 0.3
                ),
                vector_score=input_state.vector_similarity,
                pattern_score=input_state.pattern_similarity,
                vector_weight=0.7,
                pattern_weight=0.3,
                weights_adjusted=False,
                confidence=0.0,
                score_agreement=0.0,
                correlation_id=input_state.correlation_id,
                metadata={"error": str(e), "fallback": True},
            )

            return ModelHybridScoreOutput(
                result=fallback_result,
                processing_time_ms=processing_time_ms,
                correlation_id=input_state.correlation_id,
                metadata={"error": str(e)},
            )

    # ========================================================================
    # Synchronous Interface (for non-async contexts)
    # ========================================================================

    def calculate_hybrid_score(
        self,
        vector_similarity: float,
        pattern_similarity: float,
        task_characteristics: Optional[Dict] = None,
    ) -> Dict:
        """
        Synchronous interface for hybrid score calculation.

        Args:
            vector_similarity: Vector similarity score (0.0-1.0)
            pattern_similarity: Pattern similarity score (0.0-1.0)
            task_characteristics: Optional task characteristics for adaptation

        Returns:
            Dictionary with hybrid score and metadata
        """
        start_time = time.time()

        # Validate inputs
        if not (0.0 <= vector_similarity <= 1.0):
            raise ValueError(
                f"vector_similarity must be in [0.0, 1.0], got {vector_similarity}"
            )
        if not (0.0 <= pattern_similarity <= 1.0):
            raise ValueError(
                f"pattern_similarity must be in [0.0, 1.0], got {pattern_similarity}"
            )

        # Calculate weights
        vector_weight, pattern_weight, weights_adjusted, adjustment_reason = (
            self._calculate_weights(
                config=self.config,
                task_characteristics=task_characteristics,
            )
        )

        # Calculate hybrid score
        hybrid_score = (
            vector_similarity * vector_weight + pattern_similarity * pattern_weight
        )

        # Calculate confidence
        confidence, score_agreement = self._calculate_confidence(
            vector_score=vector_similarity,
            pattern_score=pattern_similarity,
            hybrid_score=hybrid_score,
        )

        # Track statistics
        processing_time_ms = (time.time() - start_time) * 1000
        self._calculation_count += 1
        self._total_processing_time += processing_time_ms
        if weights_adjusted:
            self._adaptive_adjustment_count += 1

        return {
            "hybrid_score": hybrid_score,
            "vector_score": vector_similarity,
            "pattern_score": pattern_similarity,
            "vector_weight": vector_weight,
            "pattern_weight": pattern_weight,
            "weights_adjusted": weights_adjusted,
            "adjustment_reason": adjustment_reason,
            "confidence": confidence,
            "score_agreement": score_agreement,
        }

    # ========================================================================
    # Pure Functional Weight Calculation Methods
    # ========================================================================

    def _calculate_weights(
        self,
        config: ModelHybridScoreConfig,
        task_characteristics: Optional[Dict] = None,
    ) -> Tuple[float, float, bool, Optional[str]]:
        """
        Calculate adaptive weights based on task characteristics.

        Args:
            config: Scoring configuration
            task_characteristics: Optional task characteristics

        Returns:
            Tuple of (vector_weight, pattern_weight, adjusted, reason)
        """
        # Default weights
        vector_weight = config.default_vector_weight
        pattern_weight = config.default_pattern_weight
        weights_adjusted = False
        adjustment_reason = None

        # Skip adaptation if disabled or no characteristics provided
        if not config.enable_adaptive_weights or not task_characteristics:
            return vector_weight, pattern_weight, weights_adjusted, adjustment_reason

        # Extract characteristics
        complexity = task_characteristics.get("complexity", "moderate")
        task_characteristics.get("task_type", "unknown")
        is_domain_specific = task_characteristics.get("feature_label") is not None

        # Apply adaptive strategy
        if config.adaptive_strategy in [
            EnumAdaptiveStrategy.COMPLEXITY_BASED,
            EnumAdaptiveStrategy.HYBRID,
        ]:
            complexity_adjustment = self._get_complexity_adjustment(complexity)
            if complexity_adjustment != 0.0:
                # Adjust pattern weight, maintain sum = 1.0
                pattern_weight = min(
                    config.max_weight,
                    max(config.min_weight, pattern_weight + complexity_adjustment),
                )
                vector_weight = 1.0 - pattern_weight
                weights_adjusted = True
                adjustment_reason = (
                    f"Complexity-based adjustment for {complexity} complexity"
                )

        if config.adaptive_strategy in [
            EnumAdaptiveStrategy.DOMAIN_BASED,
            EnumAdaptiveStrategy.HYBRID,
        ]:
            if is_domain_specific:
                # Increase pattern weight by 0.1 for domain-specific tasks
                pattern_weight = min(config.max_weight, pattern_weight + 0.1)
                vector_weight = 1.0 - pattern_weight
                weights_adjusted = True
                adjustment_reason = (
                    adjustment_reason or ""
                ) + " | Domain-specific adjustment"

        # Ensure weights are normalized and within bounds
        total = vector_weight + pattern_weight
        if abs(total - 1.0) > 0.001:
            vector_weight = vector_weight / total
            pattern_weight = pattern_weight / total

        # Clamp to min/max constraints
        vector_weight = max(config.min_weight, min(config.max_weight, vector_weight))
        pattern_weight = 1.0 - vector_weight

        return vector_weight, pattern_weight, weights_adjusted, adjustment_reason

    def _get_complexity_adjustment(self, complexity: str) -> float:
        """
        Get weight adjustment based on complexity.

        High complexity → Increase pattern weight (more structural analysis)
        Low complexity → Increase vector weight (simple semantic matching)

        Args:
            complexity: Complexity level string

        Returns:
            Adjustment to pattern weight (-0.2 to +0.2)
        """
        complexity_adjustments = {
            "trivial": -0.2,  # Much less pattern weight (0.3 → 0.1)
            "simple": -0.1,  # Less pattern weight (0.3 → 0.2)
            "moderate": 0.0,  # No change (0.3 → 0.3)
            "complex": +0.1,  # More pattern weight (0.3 → 0.4)
            "very_complex": +0.2,  # Much more pattern weight (0.3 → 0.5)
        }

        return complexity_adjustments.get(complexity.lower(), 0.0)

    def _calculate_confidence(
        self,
        vector_score: float,
        pattern_score: float,
        hybrid_score: float,
    ) -> Tuple[float, float]:
        """
        Calculate confidence metrics based on score agreement.

        High confidence when both scores agree (similar values).
        Low confidence when scores diverge significantly.

        Args:
            vector_score: Vector similarity score
            pattern_score: Pattern similarity score
            hybrid_score: Combined hybrid score

        Returns:
            Tuple of (confidence, score_agreement)
        """
        # Calculate score agreement (inverse of difference)
        score_diff = abs(vector_score - pattern_score)
        score_agreement = 1.0 - score_diff

        # Calculate average score
        avg_score = (vector_score + pattern_score) / 2.0

        # Confidence is high when:
        # 1. Scores agree (low difference)
        # 2. Average score is high
        # Formula: confidence = agreement * avg_score
        # This penalizes both disagreement and low scores
        confidence = score_agreement * avg_score

        return confidence, score_agreement

    # ========================================================================
    # Statistics and Monitoring
    # ========================================================================

    def get_statistics(self) -> Dict:
        """
        Get computation statistics.

        Returns:
            Dictionary with calculation statistics
        """
        if self._calculation_count == 0:
            return {
                "calculation_count": 0,
                "avg_processing_time_ms": 0.0,
                "adaptive_adjustment_rate": 0.0,
            }

        return {
            "calculation_count": self._calculation_count,
            "avg_processing_time_ms": self._total_processing_time
            / self._calculation_count,
            "total_processing_time_ms": self._total_processing_time,
            "adaptive_adjustment_count": self._adaptive_adjustment_count,
            "adaptive_adjustment_rate": self._adaptive_adjustment_count
            / self._calculation_count,
        }

    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        self._calculation_count = 0
        self._total_processing_time = 0.0
        self._adaptive_adjustment_count = 0
