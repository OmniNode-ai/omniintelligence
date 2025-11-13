"""
Enhanced Knowledge Service with ResearchOrchestrator Integration

This service demonstrates the migration strategy for integrating Knowledge APIs
with the new ResearchOrchestrator and multi-service architecture while maintaining
backward compatibility.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from server.config.logfire_config import (
    get_logger,
    safe_logfire_error,
    safe_logfire_info,
)
from server.services.knowledge.knowledge_item_service import KnowledgeItemService

# Core service imports
from server.services.search.rag_service import RAGService

logger = get_logger(__name__)


class SearchMode(Enum):
    """Enhanced search modes available through orchestration."""

    LEGACY = "legacy"
    ORCHESTRATED = "orchestrated"
    HYBRID = "hybrid"
    DEGRADED = "degraded"


@dataclass
class EnhancedSearchRequest:
    """Enhanced search request with orchestration options."""

    query: str
    knowledge_type: Optional[str] = None
    source_types: list[str] = None
    min_quality_score: float = 0.0
    match_count: int = 5
    enhancement_options: dict[str, Any] = None
    orchestration_mode: SearchMode = SearchMode.ORCHESTRATED


@dataclass
class OrchestrationResult:
    """Result from orchestrated multi-service research."""

    results: list[dict[str, Any]]
    sources_successful: list[str]
    duration_ms: int
    confidence_score: float
    correlations: dict[str, Any]
    service_mode: SearchMode
    failed_services: list[str] = None


class ResearchOrchestratorClient:
    """
    Client interface for ResearchOrchestrator integration.

    This simulates the interface to the new ResearchOrchestrator
    service from sync-from-archon changes.
    """

    def __init__(self):
        self.base_url = "http://localhost:8053"  # Intelligence service URL
        self.timeout = 30.0

    async def perform_research(
        self,
        query: str,
        context: str = "knowledge_search",
        services: list[str] = None,
        match_count: int = 5,
    ) -> OrchestrationResult:
        """
        Perform orchestrated research across multiple services.

        This would integrate with the actual ResearchOrchestrator
        from sync-from-archon changes.
        """
        try:
            # Simulate orchestrated multi-service research
            # In real implementation, this would call the ResearchOrchestrator
            start_time = datetime.now()

            results = []
            successful_services = []
            failed_services = []

            # Simulate RAG service call
            try:
                rag_results = await self._call_rag_service(query, match_count)
                results.extend(rag_results)
                successful_services.append("rag_search")
            except Exception as e:
                failed_services.append("rag_search")
                logger.warning(f"RAG service failed: {e}")

            # Simulate Vector service call
            try:
                vector_results = await self._call_vector_service(query, match_count)
                results.extend(vector_results)
                successful_services.append("vector_search")
            except Exception as e:
                failed_services.append("vector_search")
                logger.warning(f"Vector service failed: {e}")

            # Simulate Knowledge Graph service call
            try:
                kg_results = await self._call_knowledge_graph_service(
                    query, match_count
                )
                results.extend(kg_results)
                successful_services.append("knowledge_graph")
            except Exception as e:
                failed_services.append("knowledge_graph")
                logger.warning(f"Knowledge Graph service failed: {e}")

            # Calculate metrics
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            confidence_score = (
                len(successful_services) / 3.0
            )  # Simple confidence calculation

            # Generate correlations
            correlations = await self._generate_correlations(query, results)

            return OrchestrationResult(
                results=results,
                sources_successful=successful_services,
                duration_ms=duration_ms,
                confidence_score=confidence_score,
                correlations=correlations,
                service_mode=SearchMode.ORCHESTRATED,
                failed_services=failed_services,
            )

        except Exception as e:
            logger.error(f"Research orchestration failed: {e}")
            raise

    async def _call_rag_service(self, query: str, match_count: int) -> list[dict]:
        """Simulate RAG service call."""
        # This would be replaced with actual service integration
        await asyncio.sleep(0.1)  # Simulate network delay
        return [
            {
                "id": f"rag_{i}",
                "content": f"RAG result {i} for query: {query}",
                "similarity": 0.9 - (i * 0.1),
                "source": "rag_search",
                "metadata": {"service": "rag", "quality_score": 0.8},
            }
            for i in range(min(match_count, 3))
        ]

    async def _call_vector_service(self, query: str, match_count: int) -> list[dict]:
        """Simulate Vector service call."""
        await asyncio.sleep(0.1)
        return [
            {
                "id": f"vector_{i}",
                "content": f"Vector result {i} for query: {query}",
                "similarity": 0.85 - (i * 0.1),
                "source": "vector_search",
                "metadata": {"service": "vector", "quality_score": 0.75},
            }
            for i in range(min(match_count, 2))
        ]

    async def _call_knowledge_graph_service(
        self, query: str, match_count: int
    ) -> list[dict]:
        """Simulate Knowledge Graph service call."""
        await asyncio.sleep(0.1)
        return [
            {
                "id": f"kg_{i}",
                "content": f"Knowledge Graph result {i} for query: {query}",
                "similarity": 0.8 - (i * 0.1),
                "source": "knowledge_graph",
                "metadata": {"service": "knowledge_graph", "quality_score": 0.85},
            }
            for i in range(min(match_count, 2))
        ]

    async def _generate_correlations(
        self, query: str, results: list[dict]
    ) -> dict[str, Any]:
        """Generate cross-service correlations."""
        return {
            "cross_service_matches": len(results),
            "semantic_clusters": self._identify_semantic_clusters(results),
            "quality_distribution": self._calculate_quality_distribution(results),
            "recommendation_score": 0.8,
        }

    def _identify_semantic_clusters(self, results: list[dict]) -> list[dict]:
        """Identify semantic clusters in results."""
        # Simplified clustering simulation
        return [
            {"cluster_id": "technical_docs", "result_count": len(results) // 2},
            {"cluster_id": "code_examples", "result_count": len(results) // 2},
        ]

    def _calculate_quality_distribution(self, results: list[dict]) -> dict[str, float]:
        """Calculate quality score distribution."""
        if not results:
            return {"average": 0.0, "high_quality_percentage": 0.0}

        quality_scores = [
            result.get("metadata", {}).get("quality_score", 0.0) for result in results
        ]

        average = sum(quality_scores) / len(quality_scores)
        high_quality_count = sum(1 for score in quality_scores if score > 0.8)
        high_quality_percentage = high_quality_count / len(quality_scores)

        return {"average": average, "high_quality_percentage": high_quality_percentage}


class KnowledgeQualityService:
    """
    Service for assessing knowledge item quality using intelligence services.
    """

    def __init__(self):
        self.intelligence_service = None  # Would be initialized with actual service

    async def assess_knowledge_item_quality(
        self, knowledge_item: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Assess knowledge item quality using intelligence services.
        """
        try:
            content = knowledge_item.get("content", "")
            metadata = knowledge_item.get("metadata", {})

            # Simulate intelligence service quality assessment
            quality_score = await self._calculate_quality_score(content, metadata)

            return {
                "overall_score": quality_score,
                "completeness_score": min(quality_score + 0.1, 1.0),
                "accuracy_indicators": ["citations_present", "code_examples_valid"],
                "freshness_score": self._calculate_freshness_score(metadata),
                "relevance_score": quality_score * 0.9,
                "code_quality_score": await self._assess_code_examples_quality(
                    knowledge_item
                ),
                "recommendations": [
                    "Add more code examples",
                    "Update deprecated information",
                    "Improve documentation structure",
                ],
            }

        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
            return {"overall_score": 0.5, "error": str(e)}

    async def _calculate_quality_score(self, content: str, metadata: dict) -> float:
        """Calculate base quality score."""
        score = 0.7  # Base score

        # Content length factor
        if len(content) > 1000:
            score += 0.1

        # Metadata completeness
        if metadata.get("tags"):
            score += 0.1

        # Knowledge type factor
        if metadata.get("knowledge_type") == "technical":
            score += 0.1

        return min(score, 1.0)

    def _calculate_freshness_score(self, metadata: dict) -> float:
        """Calculate freshness score based on last update."""
        last_updated = metadata.get("last_scraped")
        if not last_updated:
            return 0.5

        # Simplified freshness calculation
        return 0.8  # Assume reasonably fresh

    async def _assess_code_examples_quality(self, knowledge_item: dict) -> float:
        """Assess quality of code examples in knowledge item."""
        code_examples = knowledge_item.get("code_examples", [])

        if not code_examples:
            return 0.0

        # Simplified code quality assessment
        return 0.75 if len(code_examples) > 2 else 0.5


class EnhancedKnowledgeService:
    """
    Enhanced Knowledge Service with ResearchOrchestrator integration.

    This service provides the migration strategy implementation that integrates
    Knowledge APIs with the new multi-service architecture while maintaining
    backward compatibility.
    """

    def __init__(self, supabase_client=None):
        """Initialize enhanced knowledge service."""
        from ..utils import get_database_client

        self.supabase_client = supabase_client or get_database_client()

        # Core services
        self.knowledge_service = KnowledgeItemService(self.supabase_client)
        self.rag_service = RAGService(self.supabase_client)

        # New orchestration services
        self.research_orchestrator = ResearchOrchestratorClient()
        self.quality_service = KnowledgeQualityService()
        self.correlation_processor = None  # Would be initialized with actual service

        # Configuration
        self.orchestration_enabled = self._get_orchestration_setting()
        self.quality_scoring_enabled = self._get_quality_scoring_setting()

    def _get_orchestration_setting(self) -> bool:
        """Check if orchestration is enabled."""
        import os

        return os.getenv("ENABLE_RESEARCH_ORCHESTRATION", "true").lower() == "true"

    def _get_quality_scoring_setting(self) -> bool:
        """Check if quality scoring is enabled."""
        import os

        return os.getenv("ENABLE_KNOWLEDGE_QUALITY_SCORING", "true").lower() == "true"

    async def perform_enhanced_rag_query(
        self, query: str, source: str = None, match_count: int = 5
    ) -> tuple[bool, dict[str, Any]]:
        """
        Perform enhanced RAG query with orchestration support.

        This method provides backward compatibility while adding orchestration
        capabilities when enabled.
        """
        try:
            if self.orchestration_enabled:
                return await self._perform_orchestrated_query(
                    query, source, match_count
                )
            else:
                return await self._perform_legacy_query(query, source, match_count)

        except Exception as e:
            return await self._handle_query_failure(query, str(e))

    async def _perform_orchestrated_query(
        self, query: str, source: str, match_count: int
    ) -> tuple[bool, dict[str, Any]]:
        """Perform orchestrated multi-service query."""
        try:
            # Use ResearchOrchestrator for comprehensive search
            orchestration_result = await self.research_orchestrator.perform_research(
                query=query,
                context="knowledge_search",
                services=["rag", "vector", "knowledge_graph"],
                match_count=match_count,
            )

            # Apply quality scoring if enabled
            if self.quality_scoring_enabled:
                scored_results = await self._apply_quality_scoring(
                    orchestration_result.results
                )
            else:
                scored_results = orchestration_result.results

            # Format response for compatibility
            response = {
                "results": scored_results,
                "query": query,
                "source": source,
                "match_count": match_count,
                "total_found": len(scored_results),
                "execution_path": "enhanced_orchestrated",
                "orchestration_metadata": {
                    "sources_successful": orchestration_result.sources_successful,
                    "duration_ms": orchestration_result.duration_ms,
                    "confidence_score": orchestration_result.confidence_score,
                    "service_mode": orchestration_result.service_mode.value,
                },
                "intelligence_insights": orchestration_result.correlations,
                "quality_distribution": self._calculate_quality_distribution(
                    scored_results
                ),
            }

            safe_logfire_info(
                f"Enhanced RAG query completed | "
                f"query={query[:50]} | "
                f"results={len(scored_results)} | "
                f"duration={orchestration_result.duration_ms}ms"
            )

            return True, response

        except Exception as e:
            logger.error(f"Orchestrated query failed: {e}")
            # Fall back to legacy query
            return await self._perform_legacy_query(query, source, match_count)

    async def _perform_legacy_query(
        self, query: str, source: str, match_count: int
    ) -> tuple[bool, dict[str, Any]]:
        """Perform legacy RAG query for fallback compatibility."""
        try:
            success, result = await self.rag_service.perform_rag_query(
                query=query, source=source, match_count=match_count
            )

            if success:
                # Add compatibility metadata
                result["execution_path"] = "legacy_fallback"
                result["orchestration_metadata"] = {
                    "service_mode": SearchMode.LEGACY.value,
                    "fallback_reason": "orchestration_disabled_or_failed",
                }

            return success, result

        except Exception as e:
            logger.error(f"Legacy query failed: {e}")
            raise

    async def _apply_quality_scoring(self, results: list[dict]) -> list[dict]:
        """Apply quality scoring to search results."""
        scored_results = []

        for result in results:
            try:
                # Simulate knowledge item for quality assessment
                knowledge_item = {
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "code_examples": [],
                }

                quality_assessment = (
                    await self.quality_service.assess_knowledge_item_quality(
                        knowledge_item
                    )
                )

                # Add quality scores to result
                enhanced_result = result.copy()
                enhanced_result["quality_scores"] = quality_assessment
                enhanced_result["overall_quality"] = quality_assessment.get(
                    "overall_score", 0.5
                )

                scored_results.append(enhanced_result)

            except Exception as e:
                logger.warning(f"Quality scoring failed for result: {e}")
                scored_results.append(result)  # Include without scoring

        return scored_results

    async def enhanced_knowledge_search(
        self, request: EnhancedSearchRequest
    ) -> tuple[bool, dict[str, Any]]:
        """
        Perform enhanced knowledge search with full orchestration capabilities.
        """
        try:
            # Use orchestrated search
            orchestration_result = await self.research_orchestrator.perform_research(
                query=request.query,
                context="enhanced_knowledge_search",
                services=["rag", "vector", "knowledge_graph"],
                match_count=request.match_count,
            )

            # Apply knowledge-specific enhancements
            enhanced_results = await self._enhance_search_results(
                orchestration_result.results, request
            )

            response = {
                "results": enhanced_results,
                "search_metadata": {
                    "total_sources_searched": len(
                        orchestration_result.sources_successful
                    ),
                    "cross_service_correlations": orchestration_result.correlations,
                    "quality_distribution": self._calculate_quality_distribution(
                        enhanced_results
                    ),
                    "search_performance": {
                        "duration_ms": orchestration_result.duration_ms,
                        "confidence_score": orchestration_result.confidence_score,
                    },
                },
                "recommendations": self._generate_search_recommendations(
                    request, enhanced_results
                ),
            }

            return True, response

        except Exception as e:
            return await self._handle_enhanced_search_failure(request.query, str(e))

    async def _enhance_search_results(
        self, results: list[dict], request: EnhancedSearchRequest
    ) -> list[dict]:
        """Apply knowledge-specific enhancements to search results."""
        enhanced_results = []

        for result in results:
            enhanced_result = result.copy()

            # Apply quality filtering
            if request.min_quality_score > 0:
                quality_score = result.get("metadata", {}).get("quality_score", 0.5)
                if quality_score < request.min_quality_score:
                    continue

            # Add knowledge-specific metadata
            enhanced_result["knowledge_metadata"] = {
                "source_type": self._determine_source_type(result),
                "content_category": self._categorize_content(result),
                "relevance_indicators": self._extract_relevance_indicators(
                    result, request.query
                ),
            }

            enhanced_results.append(enhanced_result)

        return enhanced_results

    def _determine_source_type(self, result: dict) -> str:
        """Determine the source type of a search result."""
        result.get("source", "unknown")
        if "code" in result.get("content", "").lower():
            return "code_documentation"
        elif "api" in result.get("content", "").lower():
            return "api_documentation"
        else:
            return "general_documentation"

    def _categorize_content(self, result: dict) -> str:
        """Categorize the content type of a search result."""
        content = result.get("content", "").lower()
        if "example" in content or "tutorial" in content:
            return "educational"
        elif "reference" in content or "specification" in content:
            return "reference"
        else:
            return "informational"

    def _extract_relevance_indicators(self, result: dict, query: str) -> list[str]:
        """Extract relevance indicators for a search result."""
        indicators = []
        content = result.get("content", "").lower()
        query_lower = query.lower()

        # Simple relevance indicators
        if query_lower in content:
            indicators.append("exact_match")

        # Check for code examples
        if "def " in content or "function" in content:
            indicators.append("code_examples")

        # Check for detailed explanation
        if len(content) > 500:
            indicators.append("detailed_content")

        return indicators

    def _generate_search_recommendations(
        self, request: EnhancedSearchRequest, results: list[dict]
    ) -> list[str]:
        """Generate search recommendations based on results."""
        recommendations = []

        if len(results) < 3:
            recommendations.append("Try broader search terms")

        if not any("code" in r.get("content", "").lower() for r in results):
            recommendations.append(
                "Add 'example' or 'code' to find implementation details"
            )

        quality_scores = [
            r.get("quality_scores", {}).get("overall_score", 0.5) for r in results
        ]

        if quality_scores and sum(quality_scores) / len(quality_scores) < 0.7:
            recommendations.append(
                "Consider refining search terms for higher quality results"
            )

        return recommendations

    def _calculate_quality_distribution(self, results: list[dict]) -> dict[str, float]:
        """Calculate quality score distribution for results."""
        if not results:
            return {"average": 0.0, "high_quality_percentage": 0.0}

        quality_scores = []
        for result in results:
            if "quality_scores" in result:
                quality_scores.append(
                    result["quality_scores"].get("overall_score", 0.5)
                )
            else:
                quality_scores.append(0.5)  # Default score

        average = sum(quality_scores) / len(quality_scores)
        high_quality_count = sum(1 for score in quality_scores if score > 0.8)
        high_quality_percentage = high_quality_count / len(quality_scores)

        return {
            "average": average,
            "high_quality_percentage": high_quality_percentage,
            "total_results": len(results),
        }

    async def _handle_query_failure(
        self, query: str, error: str
    ) -> tuple[bool, dict[str, Any]]:
        """Handle query failure with appropriate error response."""
        safe_logfire_error(
            f"Knowledge query failed | query={query[:50]} | error={error}"
        )

        return False, {
            "error": "Knowledge search temporarily unavailable",
            "error_details": error,
            "query": query,
            "execution_path": "error_handler",
            "retry_suggestions": [
                "Try simpler search terms",
                "Check system status",
                "Retry in a few moments",
            ],
        }

    async def _handle_enhanced_search_failure(
        self, query: str, error: str
    ) -> tuple[bool, dict[str, Any]]:
        """Handle enhanced search failure with fallback."""
        safe_logfire_error(
            f"Enhanced search failed | query={query[:50]} | error={error}"
        )

        # Try fallback to standard search
        try:
            fallback_success, fallback_result = await self._perform_legacy_query(
                query, None, 5
            )
            if fallback_success:
                fallback_result["execution_path"] = "enhanced_search_fallback"
                fallback_result["fallback_reason"] = "enhanced_search_failed"
                return True, fallback_result
        except Exception as fallback_error:
            logger.error(f"Fallback search also failed: {fallback_error}")

        return False, {
            "error": "All search methods failed",
            "error_details": error,
            "query": query,
            "execution_path": "total_failure",
        }


# Global service instance
_enhanced_knowledge_service = None


def get_enhanced_knowledge_service(supabase_client=None) -> EnhancedKnowledgeService:
    """Get the global enhanced knowledge service instance."""
    global _enhanced_knowledge_service
    if _enhanced_knowledge_service is None:
        _enhanced_knowledge_service = EnhancedKnowledgeService(supabase_client)
    return _enhanced_knowledge_service
