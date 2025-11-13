"""
Codegen LangExtract Service

Event-driven wrapper for LangExtract semantic analysis service.
Integrates with CodegenAnalysisHandler for PRD semantic analysis.

Created: 2025-10-14
Purpose: PRD semantic analysis for autonomous code generation
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from src.archon_services.pattern_learning.phase2_matching.client_langextract_http import (
    ClientLangextractHttp,
)
from src.archon_services.pattern_learning.phase2_matching.exceptions_langextract import (
    LangextractError,
    LangextractTimeoutError,
    LangextractUnavailableError,
    LangextractValidationError,
)

logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class CodegenLangExtractService:
    """
    Event-driven wrapper for LangExtract semantic analysis.

    Analyzes PRD (Product Requirements Document) content to extract:
    - Semantic concepts and themes
    - Domain entities and relationships
    - Domain-specific keywords
    - Node type hints for ONEX code generation

    Uses ClientLangextractHttp for HTTP communication with LangExtract service.
    """

    def __init__(
        self,
        langextract_client: Optional[ClientLangextractHttp] = None,
        base_url: str = "http://archon-langextract:8156",
    ):
        """
        Initialize Codegen LangExtract Service.

        Args:
            langextract_client: Optional ClientLangextractHttp instance (creates new if None)
            base_url: Base URL for LangExtract service (default: http://archon-langextract:8156)
        """
        self.langextract_client = langextract_client or ClientLangextractHttp(
            base_url=base_url
        )
        self._is_connected = False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Initialize LangExtract client connection."""
        if not self._is_connected:
            await self.langextract_client.connect()
            self._is_connected = True
            logger.info("CodegenLangExtractService connected to LangExtract")

    async def close(self) -> None:
        """Close LangExtract client connection."""
        if self._is_connected:
            await self.langextract_client.close()
            self._is_connected = False
            logger.info("CodegenLangExtractService disconnected from LangExtract")

    async def analyze_prd_semantics(
        self,
        prd_content: str,
        analysis_type: str = "full",
        context: Optional[str] = None,
        min_confidence: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Analyze PRD content for semantic understanding and code generation hints.

        This is the main entry point called by CodegenAnalysisHandler.

        Args:
            prd_content: PRD content to analyze
            analysis_type: Type of analysis ("full", "quick", "detailed")
            context: Optional context to guide analysis (e.g., "REST API", "data processing")
            min_confidence: Minimum confidence threshold (0.0-1.0, default: 0.7)

        Returns:
            Analysis result dictionary with:
            {
                "concepts": List[Dict] - Semantic concepts extracted
                "entities": List[Dict] - Domain entities identified
                "relationships": List[Dict] - Entity relationships
                "domain_keywords": List[str] - Domain-specific keywords
                "node_type_hints": Dict[str, float] - Suggested ONEX node types with confidence
                "confidence": float - Overall analysis confidence (0.0-1.0)
                "metadata": Dict - Additional metadata (processing time, language, etc.)
            }

        Raises:
            LangextractError: Base exception for all LangExtract errors
            LangextractUnavailableError: Service unavailable
            LangextractTimeoutError: Request timed out
            LangextractValidationError: Request validation failed
        """
        try:
            if not self._is_connected:
                await self.connect()

            # Validate input
            if not prd_content or not prd_content.strip():
                logger.error("Empty PRD content provided for analysis")
                return self._create_error_response(
                    "Empty PRD content provided for analysis"
                )

            # Build analysis context
            analysis_context = self._build_analysis_context(
                analysis_type=analysis_type, user_context=context
            )

            logger.info(
                f"Analyzing PRD semantics: type={analysis_type}, "
                f"content_length={len(prd_content)}, min_confidence={min_confidence}"
            )

            # Execute semantic analysis via LangExtract client
            semantic_result = await self.langextract_client.analyze_semantic(
                content=prd_content,
                context=analysis_context,
                language="en",
                min_confidence=min_confidence,
            )

            # Transform LangExtract result to codegen format
            analysis_result = self._transform_semantic_result(semantic_result)

            # Enhance with node type hints
            analysis_result = self._enhance_with_node_type_hints(
                analysis_result, semantic_result
            )

            logger.info(
                f"PRD analysis complete: {len(analysis_result['concepts'])} concepts, "
                f"{len(analysis_result['entities'])} entities, "
                f"confidence={analysis_result['confidence']:.2f}"
            )

            return analysis_result

        except LangextractValidationError as e:
            logger.error(f"PRD validation failed: {e}")
            return self._create_error_response(
                f"Validation error: {e.message}", validation_errors=e.validation_errors
            )

        except LangextractTimeoutError as e:
            logger.error(f"PRD analysis timed out: {e}")
            return self._create_error_response(
                f"Analysis timed out after {e.timeout_seconds}s"
            )

        except LangextractUnavailableError as e:
            logger.error(f"LangExtract service unavailable: {e}")
            return self._create_error_response(
                "LangExtract service is currently unavailable"
            )

        except LangextractError as e:
            logger.error(f"LangExtract error: {e}", exc_info=True)
            return self._create_error_response(f"Analysis error: {e.message}")

        except Exception as e:
            logger.error(f"Unexpected error during PRD analysis: {e}", exc_info=True)
            return self._create_error_response(f"Unexpected error: {str(e)}")

    def _build_analysis_context(
        self, analysis_type: str, user_context: Optional[str] = None
    ) -> str:
        """
        Build context string for semantic analysis.

        Args:
            analysis_type: Type of analysis requested
            user_context: Optional user-provided context

        Returns:
            Formatted context string for LangExtract
        """
        context_parts = [
            "Analyze this PRD for autonomous code generation.",
            "Focus on extracting entities, relationships, and architectural patterns.",
        ]

        if analysis_type == "quick":
            context_parts.append("Prioritize high-confidence concepts only.")
        elif analysis_type == "detailed":
            context_parts.append(
                "Include comprehensive semantic analysis with all relationships."
            )

        if user_context:
            context_parts.append(f"Domain context: {user_context}")

        return " ".join(context_parts)

    def _transform_semantic_result(self, semantic_result) -> Dict[str, Any]:
        """
        Transform LangExtract SemanticAnalysisResult to codegen format.

        Args:
            semantic_result: SemanticAnalysisResult from LangExtract

        Returns:
            Transformed analysis result dictionary
        """
        # Extract concepts
        concepts = [
            {
                "name": concept.concept,
                "confidence": concept.score,
                "type": "concept",
                "context": concept.context or "",
            }
            for concept in semantic_result.concepts
        ]

        # Extract entities (from high-confidence concepts)
        entities = [
            {
                "name": concept.concept,
                "confidence": concept.score,
                "context": concept.context or "",
            }
            for concept in semantic_result.concepts
            if concept.score >= 0.7  # High-confidence concepts become entities
        ]

        # Extract relationships from patterns
        relationships = [
            {
                "pattern": pattern.pattern_type,
                "confidence": pattern.strength,
                "description": pattern.description,
            }
            for pattern in semantic_result.patterns
        ]

        # Extract domain keywords from themes
        domain_keywords = [theme.theme for theme in semantic_result.themes]

        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(semantic_result)

        return {
            "concepts": concepts,
            "entities": entities,
            "relationships": relationships,
            "domain_keywords": domain_keywords,
            "node_type_hints": {},  # Will be populated by _enhance_with_node_type_hints
            "confidence": overall_confidence,
            "metadata": {
                "processing_time_ms": semantic_result.processing_time_ms,
                "language": semantic_result.language,
                "total_concepts": len(semantic_result.concepts),
                "total_themes": len(semantic_result.themes),
                "total_domains": len(semantic_result.domains),
                "total_patterns": len(semantic_result.patterns),
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    def _enhance_with_node_type_hints(
        self, analysis_result: Dict[str, Any], semantic_result
    ) -> Dict[str, Any]:
        """
        Enhance analysis result with ONEX node type hints.

        Analyzes semantic patterns to suggest appropriate ONEX node types:
        - Effect: External I/O, APIs, side effects
        - Compute: Pure transforms, algorithms
        - Reducer: Aggregation, persistence, state
        - Orchestrator: Workflow coordination, dependencies

        Args:
            analysis_result: Current analysis result
            semantic_result: Original semantic result from LangExtract

        Returns:
            Enhanced analysis result with node_type_hints populated
        """
        node_type_scores = {
            "effect": 0.0,
            "compute": 0.0,
            "reducer": 0.0,
            "orchestrator": 0.0,
        }

        # Analyze patterns for node type indicators
        for pattern in semantic_result.patterns:
            pattern_type_lower = pattern.pattern_type.lower()
            pattern_desc_lower = pattern.description.lower()

            # Effect node indicators
            if any(
                keyword in pattern_type_lower or keyword in pattern_desc_lower
                for keyword in ["api", "http", "external", "io", "fetch", "request"]
            ):
                node_type_scores["effect"] += pattern.strength * 0.3

            # Compute node indicators
            if any(
                keyword in pattern_type_lower or keyword in pattern_desc_lower
                for keyword in [
                    "transform",
                    "calculate",
                    "compute",
                    "process",
                    "algorithm",
                ]
            ):
                node_type_scores["compute"] += pattern.strength * 0.3

            # Reducer node indicators
            if any(
                keyword in pattern_type_lower or keyword in pattern_desc_lower
                for keyword in ["aggregate", "reduce", "store", "persist", "state"]
            ):
                node_type_scores["reducer"] += pattern.strength * 0.3

            # Orchestrator node indicators
            if any(
                keyword in pattern_type_lower or keyword in pattern_desc_lower
                for keyword in [
                    "orchestrate",
                    "coordinate",
                    "workflow",
                    "pipeline",
                    "flow",
                ]
            ):
                node_type_scores["orchestrator"] += pattern.strength * 0.3

        # Analyze domain keywords
        for keyword in analysis_result["domain_keywords"]:
            keyword_lower = keyword.lower()

            if any(
                term in keyword_lower for term in ["service", "api", "client", "http"]
            ):
                node_type_scores["effect"] += 0.2

            if any(term in keyword_lower for term in ["data", "model", "entity"]):
                node_type_scores["reducer"] += 0.1

        # Normalize scores to sum to 1.0 (probability distribution)
        total_score = sum(node_type_scores.values())
        if total_score > 0:
            node_type_scores = {k: v / total_score for k, v in node_type_scores.items()}

        analysis_result["node_type_hints"] = node_type_scores
        return analysis_result

    def _calculate_overall_confidence(self, semantic_result) -> float:
        """
        Calculate overall confidence score from semantic analysis result.

        Args:
            semantic_result: SemanticAnalysisResult from LangExtract

        Returns:
            Overall confidence score (0.0-1.0)
        """
        if not semantic_result.concepts:
            return 0.0

        # Average confidence across all concepts
        concept_scores = [c.score for c in semantic_result.concepts]
        avg_concept_confidence = sum(concept_scores) / len(concept_scores)

        # Boost confidence if we have patterns and themes
        pattern_boost = min(len(semantic_result.patterns) * 0.05, 0.2)
        theme_boost = min(len(semantic_result.themes) * 0.03, 0.15)

        overall_confidence = min(
            avg_concept_confidence + pattern_boost + theme_boost, 1.0
        )

        return round(overall_confidence, 2)

    def _create_error_response(
        self, error_message: str, validation_errors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create error response in standard format.

        Args:
            error_message: Error description
            validation_errors: Optional list of validation errors

        Returns:
            Error response dictionary
        """
        return {
            "concepts": [],
            "entities": [],
            "relationships": [],
            "domain_keywords": [],
            "node_type_hints": {},
            "confidence": 0.0,
            "metadata": {
                "error": error_message,
                "validation_errors": validation_errors or [],
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    def get_client_metrics(self) -> Dict[str, Any]:
        """
        Get LangExtract client metrics.

        Returns:
            Client metrics dictionary
        """
        return self.langextract_client.get_metrics()

    async def check_service_health(self) -> Dict[str, Any]:
        """
        Check LangExtract service health.

        Returns:
            Health check result dictionary
        """
        if not self._is_connected:
            return {
                "healthy": False,
                "error": "Service not connected",
            }

        return await self.langextract_client.check_health()
