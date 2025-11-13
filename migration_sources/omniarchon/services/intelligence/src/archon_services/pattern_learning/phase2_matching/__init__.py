#!/usr/bin/env python3
"""
Phase 2: Pattern Matching - Semantic Similarity Scoring and Caching

This module implements the pattern matching and similarity scoring algorithms
for the Pattern Learning Engine.

Components:
- Hybrid Scorer: Combines vector and pattern similarity with adaptive weights (Agent 4)
- Pattern Similarity Scorer: 5-component weighted similarity calculation (Agent 3 - IMPLEMENTED)
- Pattern Matcher: Find similar patterns based on semantic features (future)
- Scoring Algorithm: Jaccard similarity with configurable weights (IMPLEMENTED)
- Semantic Cache: Multi-tier LRU cache with TTL for analysis results

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from src.archon_services.pattern_learning.phase2_matching.model_contract_cache_optimizer import (
    CacheOptimizerOperation,
    ModelContractCacheOptimizer,
    ModelHitRateAnalysis,
    ModelPerformanceBenchmark,
    ModelTTLOptimization,
)

# Import hybrid scorer (Agent 4 - implemented)
from src.archon_services.pattern_learning.phase2_matching.models import (
    EnumAdaptiveStrategy,
    ModelHybridScore,
    ModelHybridScoreConfig,
    ModelHybridScoreInput,
    ModelHybridScoreOutput,
)
from src.archon_services.pattern_learning.phase2_matching.models_cache import (
    AccessPattern,
    CacheAccessEvent,
    CacheAccessType,
    TTLOptimizationResult,
)
from src.archon_services.pattern_learning.phase2_matching.node_hybrid_scorer_compute import (
    NodeHybridScorerCompute,
)

# Import pattern similarity scorer (Agent 3 - implemented)
from src.archon_services.pattern_learning.phase2_matching.node_pattern_similarity_compute import (
    NodePatternSimilarityCompute,
    PatternSimilarityConfig,
    PatternSimilarityScorer,
)

# Import cache optimizer (Agent 5 - implemented)
from src.archon_services.pattern_learning.phase2_matching.optimizer_cache_tuning import (
    CacheOptimizer,
    NodeCacheOptimizerOrchestrator,
)

# Import cache components (currently implemented)
from src.archon_services.pattern_learning.phase2_matching.reducer_semantic_cache import (
    CacheEntry,
    CacheMetrics,
    SemanticAnalysisResult,
    SemanticCacheReducer,
)

__all__ = [
    # Hybrid Scorer (Agent 4)
    "NodeHybridScorerCompute",
    "EnumAdaptiveStrategy",
    "ModelHybridScore",
    "ModelHybridScoreConfig",
    "ModelHybridScoreInput",
    "ModelHybridScoreOutput",
    # Semantic Cache
    "SemanticCacheReducer",
    "CacheMetrics",
    "SemanticAnalysisResult",
    "CacheEntry",
    # Pattern Similarity Scorer (Agent 3)
    "NodePatternSimilarityCompute",
    "PatternSimilarityConfig",
    "PatternSimilarityScorer",
    # Cache Optimizer (Agent 5)
    "NodeCacheOptimizerOrchestrator",
    "CacheOptimizer",
    "CacheOptimizerOperation",
    "ModelContractCacheOptimizer",
    "ModelHitRateAnalysis",
    "ModelTTLOptimization",
    "ModelPerformanceBenchmark",
    "CacheAccessEvent",
    "CacheAccessType",
    "AccessPattern",
    "TTLOptimizationResult",
]
