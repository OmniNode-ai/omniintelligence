"""
Codegen Pattern Service

Event-driven wrapper for pattern matching and mixin recommendations.
Integrates with CodegenPatternHandler and CodegenMixinHandler for event processing.

Created: 2025-10-14 (MVP Day 2)
Purpose: Pattern matching and mixin recommendation for autonomous code generation
"""

import logging
import os
import sys
from typing import Any, Dict, List
from uuid import UUID, uuid4

from src.archon_services.pattern_learning.phase1_foundation.storage.model_contract_vector_index import (
    ModelContractVectorSearchEffect,
)
from src.archon_services.pattern_learning.phase1_foundation.storage.node_qdrant_vector_index_effect import (
    NodeQdrantVectorIndexEffect,
)
from src.archon_services.pattern_learning.phase2_matching.node_hybrid_scorer_compute import (
    NodeHybridScorerCompute,
)
from src.archon_services.pattern_learning.phase2_matching.node_pattern_similarity_compute import (
    NodePatternSimilarityCompute,
)

# Add config path for centralized timeout configuration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
from src.config.timeout_config import get_retry_config

logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class CodegenPatternService:
    """
    Event-driven wrapper for pattern matching and mixin recommendations.

    Provides two main capabilities:
    1. find_similar_nodes: Find similar ONEX nodes from historical patterns
    2. recommend_mixins: Recommend mixins based on node requirements
    """

    # Known mixin categories for ONEX nodes
    ONEX_MIXINS = {
        "effect": [
            "EventBusMixin",
            "CachingMixin",
            "HealthCheckMixin",
            "MetricsMixin",
            "RetryMixin",
            "CircuitBreakerMixin",
        ],
        "compute": [
            "ValidationMixin",
            "CachingMixin",
            "MetricsMixin",
            "PerformanceTrackerMixin",
        ],
        "reducer": [
            "AggregationMixin",
            "StateManagementMixin",
            "CachingMixin",
            "MetricsMixin",
            "PersistenceMixin",
        ],
        "orchestrator": [
            "WorkflowMixin",
            "DependencyManagementMixin",
            "ErrorHandlingMixin",
            "MetricsMixin",
            "CircuitBreakerMixin",
        ],
    }

    # Default collection for codegen patterns
    DEFAULT_COLLECTION = "code_generation_patterns"

    def __init__(
        self,
        qdrant_url: str = "http://qdrant:6333",
        ollama_base_url: str = "http://192.168.86.200:11434",
    ):
        """
        Initialize Codegen Pattern Service.

        Args:
            qdrant_url: Qdrant server URL for vector search
            ollama_base_url: Ollama server URL for embeddings
        """
        self.vector_index = NodeQdrantVectorIndexEffect(
            qdrant_url=qdrant_url,
            ollama_base_url=ollama_base_url,
        )
        self.similarity_scorer = NodePatternSimilarityCompute()
        self.hybrid_scorer = NodeHybridScorerCompute()

    async def find_similar_nodes(
        self,
        node_description: str,
        node_type: str,
        limit: int = 5,
        score_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Find similar nodes from historical patterns using vector search.

        This method uses Qdrant vector search to find nodes with similar
        descriptions and functionality.

        Args:
            node_description: Natural language description of desired node
            node_type: Type of node (effect, compute, reducer, orchestrator)
            limit: Maximum number of results to return
            score_threshold: Minimum similarity score (0.0-1.0)

        Returns:
            List of similar nodes with:
            [
                {
                    "node_id": str,
                    "similarity_score": float,
                    "description": str,
                    "mixins_used": List[str],
                    "contracts": List[Dict],
                    "code_snippets": List[str],
                    "metadata": Dict
                }
            ]
        """
        try:
            logger.info(
                f"Searching for similar {node_type} nodes: '{node_description[:50]}...' "
                f"(limit={limit}, threshold={score_threshold})"
            )

            # Create search contract
            search_contract = ModelContractVectorSearchEffect(
                collection_name=self.DEFAULT_COLLECTION,
                query_text=f"{node_type}: {node_description}",
                limit=limit * 2,  # Get more results for filtering
                score_threshold=score_threshold,
            )

            # Perform vector search
            search_result = await self.vector_index.search_similar(search_contract)

            # Filter by node_type and transform results
            similar_nodes = []
            for hit in search_result.hits:
                payload = hit.payload

                # Filter by node type
                if payload.get("node_type") != node_type:
                    continue

                # Extract node information
                node_info = {
                    "node_id": hit.id,
                    "similarity_score": round(hit.score, 4),
                    "description": payload.get("text", payload.get("description", "")),
                    "mixins_used": payload.get("mixins", []),
                    "contracts": payload.get("contracts", []),
                    "code_snippets": payload.get("code_examples", []),
                    "metadata": {
                        "node_type": payload.get("node_type"),
                        "complexity": payload.get("complexity", "moderate"),
                        "success_rate": payload.get("success_rate", 0.0),
                        "usage_count": payload.get("usage_count", 0),
                        "last_used": payload.get("last_used"),
                    },
                }

                similar_nodes.append(node_info)

                # Stop if we have enough filtered results
                if len(similar_nodes) >= limit:
                    break

            logger.info(
                f"Found {len(similar_nodes)} similar {node_type} nodes "
                f"(avg score: {sum(n['similarity_score'] for n in similar_nodes) / len(similar_nodes) if similar_nodes else 0:.2f})"
            )

            return similar_nodes

        except Exception as e:
            logger.error(f"Failed to find similar nodes: {e}", exc_info=True)
            return []

    async def recommend_mixins(
        self,
        requirements: List[str],
        node_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Recommend mixins based on node requirements.

        Analyzes requirements and suggests appropriate mixins for the node type.
        Uses keyword matching and semantic analysis to determine best mixins.

        Args:
            requirements: List of requirement strings (e.g., ["needs caching", "retry logic"])
            node_type: Type of node (effect, compute, reducer, orchestrator)

        Returns:
            List of recommended mixins with:
            [
                {
                    "mixin_name": str,
                    "confidence": float,
                    "reason": str,
                    "required_config": Dict
                }
            ]
        """
        try:
            logger.info(
                f"Recommending mixins for {node_type} with {len(requirements)} requirements"
            )

            # Get base mixins for node type
            available_mixins = self.ONEX_MIXINS.get(node_type, [])

            if not available_mixins:
                logger.warning(f"No known mixins for node type: {node_type}")
                return []

            # Analyze requirements
            requirement_text = " ".join(requirements).lower()

            # Define mixin keywords and their associated mixins
            mixin_keywords = {
                "EventBusMixin": ["event", "publish", "subscribe", "messaging", "bus"],
                "CachingMixin": ["cache", "caching", "memoize", "store", "performance"],
                "HealthCheckMixin": ["health", "monitoring", "status", "diagnostic"],
                "MetricsMixin": [
                    "metric",
                    "metrics",
                    "telemetry",
                    "monitoring",
                    "observability",
                ],
                "RetryMixin": ["retry", "retries", "resilience", "fault tolerance"],
                "CircuitBreakerMixin": [
                    "circuit",
                    "breaker",
                    "failsafe",
                    "fault",
                    "protection",
                ],
                "ValidationMixin": ["validate", "validation", "check", "verify"],
                "PerformanceTrackerMixin": [
                    "performance",
                    "timing",
                    "profiling",
                    "benchmark",
                ],
                "AggregationMixin": ["aggregate", "aggregation", "combine", "reduce"],
                "StateManagementMixin": [
                    "state",
                    "stateful",
                    "persistence",
                    "maintain",
                ],
                "PersistenceMixin": ["persist", "save", "storage", "database"],
                "WorkflowMixin": ["workflow", "orchestrate", "coordinate", "sequence"],
                "DependencyManagementMixin": [
                    "dependency",
                    "dependencies",
                    "manage",
                    "coordinate",
                ],
                "ErrorHandlingMixin": ["error", "exception", "handling", "recovery"],
            }

            # Score each available mixin
            recommendations = []
            for mixin_name in available_mixins:
                keywords = mixin_keywords.get(mixin_name, [])

                # Calculate keyword match score
                matches = sum(1 for keyword in keywords if keyword in requirement_text)
                confidence = min(1.0, matches / len(keywords) if keywords else 0.0)

                # Generate recommendation if confidence is above threshold
                if confidence > 0.0:
                    reason = self._generate_mixin_reason(
                        mixin_name, requirements, matches, keywords
                    )

                    required_config = self._get_mixin_config(mixin_name)

                    recommendations.append(
                        {
                            "mixin_name": mixin_name,
                            "confidence": round(confidence, 4),
                            "reason": reason,
                            "required_config": required_config,
                        }
                    )

            # Sort by confidence (highest first)
            recommendations.sort(key=lambda x: x["confidence"], reverse=True)

            logger.info(
                f"Generated {len(recommendations)} mixin recommendations "
                f"for {node_type} (top confidence: {recommendations[0]['confidence'] if recommendations else 0:.2f})"
            )

            return recommendations

        except Exception as e:
            logger.error(f"Failed to recommend mixins: {e}", exc_info=True)
            return []

    def _generate_mixin_reason(
        self,
        mixin_name: str,
        requirements: List[str],
        match_count: int,
        keywords: List[str],
    ) -> str:
        """
        Generate human-readable reason for mixin recommendation.

        Args:
            mixin_name: Name of the mixin
            requirements: User requirements
            match_count: Number of keyword matches
            keywords: Keywords associated with mixin

        Returns:
            Explanation string
        """
        if match_count == 0:
            return f"{mixin_name} is commonly used for this node type"

        matched_reqs = [
            req for req in requirements if any(kw in req.lower() for kw in keywords)
        ]

        if matched_reqs:
            return (
                f"{mixin_name} matches requirements: {', '.join(matched_reqs[:2])}"
                + (
                    f" and {len(matched_reqs) - 2} more"
                    if len(matched_reqs) > 2
                    else ""
                )
            )
        else:
            return f"{mixin_name} provides {', '.join(keywords[:3])} capabilities"

    def _get_mixin_config(self, mixin_name: str) -> Dict[str, Any]:
        """
        Get required configuration for a mixin.

        Args:
            mixin_name: Name of the mixin

        Returns:
            Configuration dictionary
        """
        # Get centralized retry config
        retry_config = get_retry_config()

        # Define common configurations for each mixin
        mixin_configs = {
            "CachingMixin": {
                "cache_ttl_seconds": 300,
                "cache_strategy": "lru",
                "max_cache_size": 1000,
            },
            "RetryMixin": {
                "max_attempts": retry_config["max_attempts"],
                "backoff_multiplier": retry_config["backoff_multiplier"],
                "max_delay_seconds": retry_config["max_delay"],
            },
            "CircuitBreakerMixin": {
                "failure_threshold": 5,
                "timeout_seconds": 60,
                "half_open_attempts": 3,
            },
            "MetricsMixin": {
                "enable_histograms": True,
                "enable_counters": True,
            },
            "PerformanceTrackerMixin": {
                "track_latency": True,
                "track_throughput": True,
            },
        }

        return mixin_configs.get(mixin_name, {})

    async def close(self):
        """Clean up resources."""
        if hasattr(self.vector_index, "close"):
            await self.vector_index.close()
