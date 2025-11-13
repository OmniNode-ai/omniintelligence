"""
Intelligence Correlation Integration Service

Service layer that manages the integration between rich intelligence documents
and the correlation analysis engine. Provides seamless fallback and configuration
management for enhanced correlation analysis.

This service handles:
- Automatic detection of rich intelligence data availability
- Seamless fallback between enhanced and basic analysis
- Configuration management for correlation analysis modes
- Performance monitoring and optimization
- Integration with existing correlation processor workflow
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional, Union

from server.data.intelligence_data_access import (
    IntelligenceDataAccess,
    IntelligenceDocumentData,
)
from server.services.correlation_analyzer import (
    CorrelationAnalysisResult,
    CorrelationAnalyzer,
    DocumentContext,
)

logger = logging.getLogger(__name__)


def create_enhanced_correlation_analyzer(config=None):
    """Factory function for creating enhanced correlation analyzer."""
    return CorrelationAnalyzer(config)


class AnalysisMode(Enum):
    """Analysis mode selection."""

    AUTO = "auto"  # Automatic selection based on data availability
    ENHANCED = "enhanced"  # Force enhanced analysis
    BASIC = "basic"  # Force basic analysis
    HYBRID = "hybrid"  # Use both and compare results


@dataclass
class IntegrationConfig:
    """Configuration for intelligence correlation integration."""

    analysis_mode: AnalysisMode = AnalysisMode.AUTO
    enhanced_threshold: float = 0.5  # Minimum rich data coverage to use enhanced mode
    performance_monitoring: bool = True
    fallback_timeout_seconds: int = 30
    cache_analysis_results: bool = True

    # Enhanced analyzer specific config
    technology_weight: float = 0.4
    architecture_weight: float = 0.3
    rich_content_bonus: float = 0.2

    # Base analyzer config passthrough
    temporal_threshold_hours: int = 72
    semantic_threshold: float = 0.3
    max_correlations_per_document: int = 10


@dataclass
class IntegrationStats:
    """Statistics for integration performance and usage."""

    total_analyses: int = 0
    enhanced_analyses: int = 0
    basic_analyses: int = 0
    hybrid_analyses: int = 0
    fallback_count: int = 0
    average_enhanced_duration: float = 0.0
    average_basic_duration: float = 0.0
    rich_data_documents: int = 0
    performance_improvement_ratio: float = 0.0


class IntelligenceCorrelationIntegration:
    """
    Main integration service for intelligence-enhanced correlation analysis.

    This service orchestrates the selection and execution of appropriate
    correlation analysis based on data availability and configuration.
    """

    def __init__(
        self,
        config: Optional[IntegrationConfig] = None,
        data_access: Optional[IntelligenceDataAccess] = None,
    ):
        """
        Initialize integration service.

        Args:
            config: Integration configuration
            data_access: Intelligence data access instance
        """
        # Initialize structured logging
        from ..utils.correlation_logging import integration_logger

        self.correlation_logger = integration_logger

        self.config = config or IntegrationConfig()
        self.data_access = data_access
        self.stats = IntegrationStats()

        # Initialize analyzers
        self._init_analyzers()

        # Performance cache
        self.analysis_cache: dict[str, CorrelationAnalysisResult] = {}
        self.rich_data_cache: dict[str, bool] = {}

        # Log initialization
        self.correlation_logger.log_info(
            "intelligence_integration_initialized",
            {
                "analysis_mode": self.config.analysis_mode.value,
                "enhanced_threshold": self.config.enhanced_threshold,
                "technology_weight": self.config.technology_weight,
                "architecture_weight": self.config.architecture_weight,
                "rich_content_bonus": self.config.rich_content_bonus,
                "performance_monitoring": self.config.performance_monitoring,
                "cache_enabled": self.config.cache_analysis_results,
                "version": "2.0.0-enhanced-logging",
            },
        )

    def _init_analyzers(self):
        """Initialize correlation analyzers."""
        # Base analyzer config
        base_config = {
            "temporal_threshold_hours": self.config.temporal_threshold_hours,
            "semantic_threshold": self.config.semantic_threshold,
            "max_correlations_per_document": self.config.max_correlations_per_document,
        }

        # Enhanced analyzer config
        enhanced_config = base_config.copy()
        enhanced_config.update(
            {
                "technology_weight": self.config.technology_weight,
                "architecture_weight": self.config.architecture_weight,
                "rich_content_bonus": self.config.rich_content_bonus,
            }
        )

        self.basic_analyzer = CorrelationAnalyzer(base_config)
        self.enhanced_analyzer = create_enhanced_correlation_analyzer(enhanced_config)

    async def analyze_document_correlations(
        self,
        target_document: Union[DocumentContext, IntelligenceDocumentData],
        context_documents: list[Union[DocumentContext, IntelligenceDocumentData]],
    ) -> CorrelationAnalysisResult:
        """
        Analyze document correlations using intelligence-aware analysis.

        Args:
            target_document: Document to analyze correlations for
            context_documents: Context documents for correlation analysis

        Returns:
            CorrelationAnalysisResult with enhanced or basic analysis
        """
        correlation_id = self.correlation_logger.generate_correlation_id()

        with self.correlation_logger.correlation_context(correlation_id):
            analysis_start = datetime.now(UTC)

            # Extract document identifiers for logging
            target_id = getattr(target_document, "id", "unknown")
            target_repo = getattr(target_document, "repository", "unknown")

            self.correlation_logger.log_processing_start(
                "intelligence_correlation_analysis",
                {
                    "target_document_id": target_id,
                    "target_repository": target_repo,
                    "context_documents_count": len(context_documents),
                    "analysis_mode_configured": self.config.analysis_mode.value,
                    "enhanced_threshold": self.config.enhanced_threshold,
                    "cache_enabled": self.config.cache_analysis_results,
                },
            )

            try:
                # Convert to DocumentContext if needed and enrich with intelligence data
                self.correlation_logger.log_debug(
                    "converting_target_document",
                    {
                        "target_document_id": target_id,
                        "target_document_type": type(target_document).__name__,
                        "conversion_needed": not isinstance(
                            target_document, DocumentContext
                        ),
                    },
                )

                target_ctx = await self._ensure_document_context(target_document)

                self.correlation_logger.log_debug(
                    "enriching_target_with_intelligence",
                    {
                        "target_document_id": target_ctx.id,
                        "target_repository": target_ctx.repository,
                        "enrichment_operation": "enrich_with_intelligence_data",
                    },
                )

                target_ctx = await self._enrich_document_with_intelligence_data(
                    target_ctx
                )

                # Check if target document has rich data
                target_has_rich_data = await self._has_rich_data(target_ctx)
                self.correlation_logger.log_debug(
                    "target_document_rich_data_status",
                    {
                        "target_document_id": target_ctx.id,
                        "has_rich_data": target_has_rich_data,
                        "rich_data_cache_used": target_ctx.id in self.rich_data_cache,
                    },
                )

                # Process context documents
                context_ctx = []
                rich_context_count = 0

                self.correlation_logger.log_debug(
                    "processing_context_documents",
                    {
                        "context_documents_count": len(context_documents),
                        "operation": "convert_and_enrich",
                    },
                )

                for index, doc in enumerate(context_documents):
                    ctx_doc = await self._ensure_document_context(doc)
                    ctx_doc = await self._enrich_document_with_intelligence_data(
                        ctx_doc
                    )
                    context_ctx.append(ctx_doc)

                    # Track rich data availability in context
                    if await self._has_rich_data(ctx_doc):
                        rich_context_count += 1

                    if index < 5:  # Log first 5 for debugging
                        self.correlation_logger.log_debug(
                            "context_document_processed",
                            {
                                "context_document_index": index,
                                "context_document_id": ctx_doc.id,
                                "context_repository": ctx_doc.repository,
                                "has_rich_data": await self._has_rich_data(ctx_doc),
                            },
                        )

                # Log rich data coverage
                total_docs_with_rich_data = (
                    1 if target_has_rich_data else 0
                ) + rich_context_count
                rich_data_coverage = total_docs_with_rich_data / (
                    len(context_documents) + 1
                )

                self.correlation_logger.log_info(
                    "rich_data_coverage_analysis",
                    {
                        "target_has_rich_data": target_has_rich_data,
                        "context_documents_with_rich_data": rich_context_count,
                        "total_documents_with_rich_data": total_docs_with_rich_data,
                        "total_documents": len(context_documents) + 1,
                        "rich_data_coverage_percentage": rich_data_coverage * 100,
                        "enhanced_threshold_percentage": self.config.enhanced_threshold
                        * 100,
                    },
                )

                # Determine analysis mode
                self.correlation_logger.log_debug(
                    "determining_analysis_mode",
                    {
                        "configured_mode": self.config.analysis_mode.value,
                        "rich_data_coverage": rich_data_coverage,
                        "enhanced_threshold": self.config.enhanced_threshold,
                    },
                )

                analysis_mode = await self._determine_analysis_mode(
                    target_ctx, context_ctx
                )

                self.correlation_logger.log_info(
                    "analysis_mode_determined",
                    {
                        "selected_mode": analysis_mode.value,
                        "rich_data_coverage": rich_data_coverage,
                        "mode_selection_reason": self._get_mode_selection_reason(
                            analysis_mode, rich_data_coverage
                        ),
                    },
                )

                # Execute analysis based on mode
                if analysis_mode == AnalysisMode.ENHANCED:
                    result = await self._execute_enhanced_analysis(
                        target_ctx, context_ctx, analysis_start
                    )
                    self.stats.enhanced_analyses += 1

                elif analysis_mode == AnalysisMode.BASIC:
                    result = await self._execute_basic_analysis(
                        target_ctx, context_ctx, analysis_start
                    )
                    self.stats.basic_analyses += 1

                elif analysis_mode == AnalysisMode.HYBRID:
                    result = await self._execute_hybrid_analysis(
                        target_ctx, context_ctx, analysis_start
                    )
                    self.stats.hybrid_analyses += 1

                else:  # AUTO mode
                    result = await self._execute_auto_analysis(
                        target_ctx, context_ctx, analysis_start
                    )

                # Update statistics
                self.stats.total_analyses += 1

                # Cache result if enabled
                if self.config.cache_analysis_results:
                    cache_key = f"{target_ctx.id}_{len(context_ctx)}"
                    self.analysis_cache[cache_key] = result
                    self.correlation_logger.log_debug(
                        "analysis_result_cached",
                        {"cache_key": cache_key, "result_cached": True},
                    )

                # Log final analysis results
                analysis_duration = (datetime.now(UTC) - analysis_start).total_seconds()

                self.correlation_logger.log_processing_complete(
                    "intelligence_correlation_analysis",
                    {
                        "target_document_id": target_ctx.id,
                        "analysis_mode_used": analysis_mode.value,
                        "analysis_duration_seconds": analysis_duration,
                        "correlations_found": {
                            "temporal": len(result.temporal_correlations),
                            "semantic": len(result.semantic_correlations),
                            "breaking_changes": len(result.breaking_changes),
                        },
                        "rich_data_utilized": result.analysis_metadata.get(
                            "rich_data_available", False
                        ),
                        "total_correlations": len(result.temporal_correlations)
                        + len(result.semantic_correlations),
                        "analysis_successful": True,
                    },
                )

                logger.info(
                    f"Completed correlation analysis for {target_ctx.id} using {analysis_mode.value} mode"
                )
                return result

            except Exception as e:
                analysis_duration = (datetime.now(UTC) - analysis_start).total_seconds()

                self.correlation_logger.log_processing_error(
                    "intelligence_correlation_analysis",
                    e,
                    {
                        "target_document_id": target_id,
                        "target_repository": target_repo,
                        "context_documents_count": len(context_documents),
                        "analysis_duration_seconds": analysis_duration,
                        "fallback_attempt": "will_try_basic_analysis",
                    },
                )

                logger.error(f"Error in intelligence correlation integration: {e}")

                # Fallback to basic analysis
                try:
                    self.correlation_logger.log_debug(
                        "attempting_fallback_analysis",
                        {
                            "target_document_id": target_id,
                            "fallback_mode": "basic_analysis",
                            "original_error": str(e),
                        },
                    )

                    target_ctx = await self._ensure_document_context(target_document)
                    context_ctx = [
                        await self._ensure_document_context(doc)
                        for doc in context_documents
                    ]
                    result = await self._execute_basic_analysis(
                        target_ctx, context_ctx, analysis_start
                    )

                    self.stats.fallback_count += 1

                    self.correlation_logger.log_info(
                        "fallback_analysis_successful",
                        {
                            "target_document_id": target_ctx.id,
                            "fallback_mode": "basic_analysis",
                            "correlations_found": len(result.temporal_correlations)
                            + len(result.semantic_correlations),
                            "fallback_recovery": True,
                        },
                    )

                    return result

                except Exception as fallback_error:
                    fallback_duration = (
                        datetime.now(UTC) - analysis_start
                    ).total_seconds()

                    self.correlation_logger.log_processing_error(
                        "fallback_correlation_analysis",
                        fallback_error,
                        {
                            "target_document_id": target_id,
                            "original_error": str(e),
                            "fallback_error": str(fallback_error),
                            "total_duration_seconds": fallback_duration,
                            "complete_failure": True,
                        },
                    )

                    logger.error(f"Fallback analysis also failed: {fallback_error}")
                    raise

    def _get_mode_selection_reason(
        self, mode: AnalysisMode, rich_data_coverage: float
    ) -> str:
        """Get human-readable reason for mode selection."""
        if mode == AnalysisMode.ENHANCED:
            return f"Rich data coverage {rich_data_coverage:.2f} exceeds threshold {self.config.enhanced_threshold}"
        elif mode == AnalysisMode.BASIC:
            return f"Rich data coverage {rich_data_coverage:.2f} below threshold {self.config.enhanced_threshold}"
        elif mode == AnalysisMode.HYBRID:
            return "Hybrid mode configured to run both analyses"
        else:
            return f"Auto mode selected based on coverage {rich_data_coverage:.2f}"

    async def _determine_analysis_mode(
        self, target_document: DocumentContext, context_documents: list[DocumentContext]
    ) -> AnalysisMode:
        """Determine the appropriate analysis mode based on data and configuration."""

        # Force modes
        if self.config.analysis_mode in [
            AnalysisMode.ENHANCED,
            AnalysisMode.BASIC,
            AnalysisMode.HYBRID,
        ]:
            return self.config.analysis_mode

        # AUTO mode: determine based on data availability
        rich_data_coverage = await self._calculate_rich_data_coverage(
            target_document, context_documents
        )

        if rich_data_coverage >= self.config.enhanced_threshold:
            logger.debug(
                f"Rich data coverage {rich_data_coverage:.2f} exceeds threshold, using enhanced mode"
            )
            return AnalysisMode.ENHANCED
        else:
            logger.debug(
                f"Rich data coverage {rich_data_coverage:.2f} below threshold, using basic mode"
            )
            return AnalysisMode.BASIC

    async def _calculate_rich_data_coverage(
        self, target_document: DocumentContext, context_documents: list[DocumentContext]
    ) -> float:
        """Calculate the coverage of rich intelligence data in the document set."""

        total_documents = len(context_documents) + 1  # Include target
        rich_documents = 0

        # Check target document
        if await self._has_rich_data(target_document):
            rich_documents += 1
            self.stats.rich_data_documents += 1

        # Check context documents
        for doc in context_documents:
            if await self._has_rich_data(doc):
                rich_documents += 1

        return rich_documents / total_documents if total_documents > 0 else 0.0

    async def _has_rich_data(self, document: DocumentContext) -> bool:
        """Check if a document has rich intelligence data."""

        # Check cache first
        cache_key = document.id
        if cache_key in self.rich_data_cache:
            await self._log_debug_to_intelligence_system(
                "rich_data_check_cached",
                {
                    "document_id": document.id,
                    "repository": document.repository,
                    "cached_result": self.rich_data_cache[cache_key],
                    "cache_hit": True,
                },
            )
            return self.rich_data_cache[cache_key]

        has_rich = False
        rich_data_details = {}

        try:
            if hasattr(document, "content") and document.content:
                # Check for rich intelligence fields
                has_technologies = bool(document.content.get("technologies_detected"))
                has_architecture = bool(document.content.get("architecture_patterns"))
                has_correlation_analysis = bool(
                    document.content.get("correlation_analysis")
                )

                has_rich = (
                    has_technologies or has_architecture or has_correlation_analysis
                )

                rich_data_details = {
                    "document_id": document.id,
                    "repository": document.repository,
                    "commit_sha": document.commit_sha,
                    "has_technologies_detected": has_technologies,
                    "has_architecture_patterns": has_architecture,
                    "has_correlation_analysis": has_correlation_analysis,
                    "technologies_count": (
                        len(document.content.get("technologies_detected", []))
                        if has_technologies
                        else 0
                    ),
                    "patterns_count": (
                        len(document.content.get("architecture_patterns", []))
                        if has_architecture
                        else 0
                    ),
                    "content_keys": list(document.content.keys()),
                    "cache_hit": False,
                }

                if has_rich:
                    await self._log_debug_to_intelligence_system(
                        "rich_data_check_found", rich_data_details
                    )
                else:
                    await self._log_debug_to_intelligence_system(
                        "rich_data_check_missing", rich_data_details
                    )

        except Exception as e:
            await self._log_debug_to_intelligence_system(
                "rich_data_check_error",
                {
                    "document_id": document.id,
                    "repository": document.repository,
                    "error": str(e),
                    "has_content": hasattr(document, "content"),
                    "content_type": (
                        type(document.content).__name__
                        if hasattr(document, "content")
                        else "none"
                    ),
                },
            )
            has_rich = False

        # Cache result
        self.rich_data_cache[cache_key] = has_rich
        return has_rich

    async def _log_debug_to_intelligence_system(
        self, debug_type: str, debug_data: dict[str, Any]
    ):
        """
        Log debug information to the intelligence system for future queryability.

        This method captures detailed debug information about correlation processing
        and stores it in the intelligence system where it can be queried later to
        understand and troubleshoot correlation issues.

        Args:
            debug_type: Type of debug information (e.g., "rich_data_check_cached", "analysis_mode_selection")
            debug_data: Debug information to log
        """
        try:
            # Create debug document for intelligence system
            debug_document = {
                "document_type": "debug_log",
                "debug_type": debug_type,
                "timestamp": datetime.now(UTC).isoformat(),
                "service": "intelligence_correlation_integration",
                "data": debug_data,
                "queryable_keywords": [
                    debug_type,
                    "correlation_debug",
                    "intelligence_integration",
                    debug_data.get("repository", ""),
                    (
                        debug_data.get("commit_sha", "")[:8]
                        if debug_data.get("commit_sha")
                        else ""
                    ),
                    "rich_data_analysis",
                ],
                "intelligence_metadata": {
                    "purpose": "Debug correlation integration processing",
                    "searchable": True,
                    "retention_policy": "30_days",
                    "priority": "debug",
                },
            }

            # Log locally for immediate visibility
            logger.info(f"[INTELLIGENCE_DEBUG] {debug_type}: {debug_data}")

            # Try to send to intelligence system (graceful failure if not available)
            try:
                # This would integrate with the MCP intelligence system
                # For now, we'll use the logger but structure the data for future integration
                logger.info(
                    f"[INTELLIGENCE_SYSTEM] Integration debug log: {debug_document}"
                )

                # TODO: Implement actual MCP intelligence system integration
                # await self.intelligence_client.create_debug_document(debug_document)

            except Exception as intelligence_error:
                logger.debug(
                    f"Could not send debug data to intelligence system: {intelligence_error}"
                )
                # Don't fail the main operation if intelligence logging fails

        except Exception as e:
            logger.error(f"Error logging debug information: {e}")
            # Don't fail the main operation if debug logging fails

    async def _enrich_document_with_intelligence_data(
        self, document: DocumentContext
    ) -> DocumentContext:
        """
        Enrich document with intelligence data from MCP API if available.

        This method attempts to fetch rich intelligence data for documents that
        don't already have technologies_detected or architecture_patterns.
        """
        try:
            # If document already has rich data, return as-is
            if await self._has_rich_data(document):
                return document

            # Try to fetch intelligence data via direct MCP API calls
            enhanced_content = await self._fetch_intelligence_data_for_document(
                document
            )

            if enhanced_content:
                # Update document content with rich intelligence data
                updated_content = document.content.copy() if document.content else {}
                updated_content.update(enhanced_content)

                # Create new DocumentContext with enhanced content
                enhanced_document = DocumentContext(
                    id=document.id,
                    repository=document.repository,
                    commit_sha=document.commit_sha,
                    author=document.author,
                    created_at=document.created_at,
                    change_type=document.change_type,
                    content=updated_content,
                    modified_files=document.modified_files,
                    commit_message=document.commit_message,
                )

                logger.debug(
                    f"Successfully enriched document {document.id} with intelligence data"
                )
                return enhanced_document

            # Return original document if no enrichment possible
            return document

        except Exception as e:
            logger.debug(
                f"Could not enrich document {document.id} with intelligence data: {e}"
            )
            return document

    async def _fetch_intelligence_data_for_document(
        self, document: DocumentContext
    ) -> dict[str, Any]:
        """
        Fetch intelligence data for a document using various strategies.

        This method implements multiple strategies to find rich intelligence data:
        1. Direct MCP API lookup by document metadata
        2. Search by repository and commit information
        3. Pattern matching on file changes
        """
        try:
            # Strategy 1: Try to use MCP API to get documents with intelligence data
            intelligence_data = await self._query_mcp_for_intelligence_data(document)
            if intelligence_data:
                return intelligence_data

            # Strategy 2: Generate basic intelligence data from document analysis
            generated_data = await self._generate_basic_intelligence_data(document)
            if generated_data:
                return generated_data

            return {}

        except Exception as e:
            logger.debug(
                f"Error fetching intelligence data for document {document.id}: {e}"
            )
            return {}

    async def _query_mcp_for_intelligence_data(
        self, document: DocumentContext
    ) -> dict[str, Any]:
        """
        Query MCP API for intelligence data related to this document.

        Uses the available MCP tools to search for intelligence documents
        that might contain rich data for this commit/repository.
        """
        try:
            # This would use the actual MCP tools available in the system
            # For now, we implement a simplified version that could be expanded

            # Try to search for intelligence documents related to this repository/commit
            search_query = (
                f"repository:{document.repository} commit:{document.commit_sha}"
            )

            # Use the MCP service client if available
            if hasattr(self, "mcp_client") and self.mcp_client:
                search_result = await self.mcp_client.search(
                    query=search_query, match_count=5
                )

                if search_result.get("success") and search_result.get("results"):
                    # Extract intelligence data from search results
                    return self._extract_intelligence_from_search_results(
                        search_result["results"], document
                    )

            return {}

        except Exception as e:
            logger.debug(f"Error querying MCP for intelligence data: {e}")
            return {}

    def _extract_intelligence_from_search_results(
        self, results: list[dict[str, Any]], document: DocumentContext
    ) -> dict[str, Any]:
        """Extract intelligence data from MCP search results."""
        intelligence_data = {}

        try:
            technologies_detected = set()
            architecture_patterns = set()

            for result in results:
                content = result.get("content", "")
                title = result.get("title", "")

                # Extract technologies from content and title
                if content or title:
                    text_content = f"{title} {content}".lower()

                    # Technology detection patterns
                    tech_patterns = {
                        "docker": ["docker", "dockerfile", "container"],
                        "kubernetes": ["kubernetes", "k8s", "kubectl", "helm"],
                        "python": ["python", ".py", "pip", "pytest", "django", "flask"],
                        "javascript": [
                            "javascript",
                            "js",
                            "node",
                            "npm",
                            "react",
                            "vue",
                        ],
                        "typescript": ["typescript", "ts", ".ts", ".tsx"],
                        "github actions": ["github actions", "workflows", ".github"],
                        "postgresql": ["postgresql", "postgres", "psql"],
                        "redis": ["redis", "redis-server"],
                        "nginx": ["nginx", "proxy"],
                        "terraform": ["terraform", ".tf", "infrastructure"],
                        "consul": ["consul", "service discovery"],
                        "prometheus": ["prometheus", "metrics", "monitoring"],
                    }

                    for tech, patterns in tech_patterns.items():
                        if any(pattern in text_content for pattern in patterns):
                            technologies_detected.add(tech)

                    # Architecture pattern detection
                    arch_patterns_map = {
                        "microservices": [
                            "microservice",
                            "service mesh",
                            "distributed",
                        ],
                        "api_gateway": ["api gateway", "gateway", "proxy"],
                        "event_driven": ["event", "message queue", "pub/sub"],
                        "database_migration": [
                            "migration",
                            "schema change",
                            "db update",
                        ],
                        "ci_cd": ["ci/cd", "pipeline", "deployment", "build"],
                        "monitoring": ["monitoring", "observability", "metrics"],
                        "security": [
                            "security",
                            "auth",
                            "authentication",
                            "authorization",
                        ],
                    }

                    for pattern, keywords in arch_patterns_map.items():
                        if any(keyword in text_content for keyword in keywords):
                            architecture_patterns.add(pattern)

            if technologies_detected:
                intelligence_data["technologies_detected"] = list(technologies_detected)

            if architecture_patterns:
                intelligence_data["architecture_patterns"] = list(architecture_patterns)

            return intelligence_data

        except Exception as e:
            logger.debug(f"Error extracting intelligence from search results: {e}")
            return {}

    async def _generate_basic_intelligence_data(
        self, document: DocumentContext
    ) -> dict[str, Any]:
        """
        REMOVED: Basic file extension analysis completely removed.

        This method previously performed basic file extension analysis which produced
        useless correlations like "Tech: Python" and "Files: ...py". This functionality
        has been completely removed to force the system to rely only on rich intelligence
        document data.

        Args:
            document: Document context (ignored)

        Returns:
            Empty dict to indicate no basic analysis should be used
        """
        # Log the removal of basic analysis
        await self._log_debug_to_intelligence_system(
            "basic_intelligence_generation_bypassed",
            {
                "document_id": document.id,
                "repository": document.repository,
                "commit_sha": document.commit_sha,
                "message": "Basic intelligence data generation bypassed - forcing rich data requirement",
                "modified_files_count": len(document.modified_files),
                "reason": "Eliminated basic file extension analysis that produces useless correlations",
            },
        )

        # Return empty dict to indicate no basic analysis data available
        # This forces the system to either use rich intelligence data or fail gracefully
        return {}

    async def _execute_enhanced_analysis(
        self,
        target_document: DocumentContext,
        context_documents: list[DocumentContext],
        analysis_start: datetime,
    ) -> CorrelationAnalysisResult:
        """Execute enhanced correlation analysis."""

        start_time = datetime.now(UTC)

        try:
            result = await asyncio.wait_for(
                self.enhanced_analyzer.analyze_document_correlations(
                    target_document, context_documents
                ),
                timeout=self.config.fallback_timeout_seconds,
            )

            # Update performance statistics
            duration = (datetime.now(UTC) - start_time).total_seconds()
            self._update_performance_stats("enhanced", duration)

            # Add integration metadata
            if "analysis_metadata" not in result.analysis_metadata:
                result.analysis_metadata = {}

            result.analysis_metadata.update(
                {
                    "integration_mode": "enhanced",
                    "rich_data_available": True,
                    "analysis_duration_enhanced": duration,
                }
            )

            return result

        except TimeoutError:
            logger.warning(
                f"Enhanced analysis timed out after {self.config.fallback_timeout_seconds}s, falling back to basic"
            )
            self.stats.fallback_count += 1
            return await self._execute_basic_analysis(
                target_document, context_documents, analysis_start
            )

    async def _execute_basic_analysis(
        self,
        target_document: DocumentContext,
        context_documents: list[DocumentContext],
        analysis_start: datetime,
    ) -> CorrelationAnalysisResult:
        """Execute basic correlation analysis."""

        start_time = datetime.now(UTC)
        result = await self.basic_analyzer.analyze_document_correlations(
            target_document, context_documents
        )

        # Update performance statistics
        duration = (datetime.now(UTC) - start_time).total_seconds()
        self._update_performance_stats("basic", duration)

        # Add integration metadata
        if "analysis_metadata" not in result.analysis_metadata:
            result.analysis_metadata = {}

        result.analysis_metadata.update(
            {
                "integration_mode": "basic",
                "rich_data_available": False,
                "analysis_duration_basic": duration,
            }
        )

        return result

    async def _execute_hybrid_analysis(
        self,
        target_document: DocumentContext,
        context_documents: list[DocumentContext],
        analysis_start: datetime,
    ) -> CorrelationAnalysisResult:
        """Execute both enhanced and basic analysis for comparison."""

        # Run both analyses in parallel
        enhanced_task = asyncio.create_task(
            self._execute_enhanced_analysis(
                target_document, context_documents, analysis_start
            )
        )
        basic_task = asyncio.create_task(
            self._execute_basic_analysis(
                target_document, context_documents, analysis_start
            )
        )

        enhanced_result, basic_result = await asyncio.gather(
            enhanced_task, basic_task, return_exceptions=True
        )

        # Use enhanced result if successful, otherwise basic
        if isinstance(enhanced_result, CorrelationAnalysisResult):
            primary_result = enhanced_result
            comparison_result = (
                basic_result
                if isinstance(basic_result, CorrelationAnalysisResult)
                else None
            )
        else:
            primary_result = basic_result
            comparison_result = None

        # Add comparison metadata
        primary_result.analysis_metadata.update(
            {
                "integration_mode": "hybrid",
                "comparison_available": comparison_result is not None,
                "enhanced_correlation_count": (
                    len(enhanced_result.temporal_correlations)
                    + len(enhanced_result.semantic_correlations)
                    if isinstance(enhanced_result, CorrelationAnalysisResult)
                    else 0
                ),
                "basic_correlation_count": (
                    len(basic_result.temporal_correlations)
                    + len(basic_result.semantic_correlations)
                    if isinstance(basic_result, CorrelationAnalysisResult)
                    else 0
                ),
            }
        )

        return primary_result

    async def _execute_auto_analysis(
        self,
        target_document: DocumentContext,
        context_documents: list[DocumentContext],
        analysis_start: datetime,
    ) -> CorrelationAnalysisResult:
        """Execute analysis in auto mode based on data availability."""

        rich_data_coverage = await self._calculate_rich_data_coverage(
            target_document, context_documents
        )

        if rich_data_coverage >= self.config.enhanced_threshold:
            return await self._execute_enhanced_analysis(
                target_document, context_documents, analysis_start
            )
        else:
            return await self._execute_basic_analysis(
                target_document, context_documents, analysis_start
            )

    async def _ensure_document_context(
        self, document: Union[DocumentContext, IntelligenceDocumentData]
    ) -> DocumentContext:
        """Ensure document is in DocumentContext format."""

        if isinstance(document, DocumentContext):
            return document

        # Convert IntelligenceDocumentData to DocumentContext
        if isinstance(document, IntelligenceDocumentData):
            return DocumentContext(
                id=document.id,
                repository=document.repository,
                commit_sha=document.commit_sha,
                author=document.author,
                created_at=datetime.fromisoformat(
                    document.created_at.replace("Z", "+00:00")
                ),
                change_type=document.change_type,
                content=getattr(document, "raw_content", {}),
                modified_files=(
                    document.diff_analysis.modified_files
                    if document.diff_analysis
                    else []
                ),
                commit_message=None,  # Not available in current structure
            )

        raise TypeError(f"Unsupported document type: {type(document)}")

    def _update_performance_stats(self, mode: str, duration: float):
        """Update performance statistics."""

        if mode == "enhanced":
            if self.stats.enhanced_analyses > 0:
                self.stats.average_enhanced_duration = (
                    self.stats.average_enhanced_duration
                    * (self.stats.enhanced_analyses - 1)
                    + duration
                ) / self.stats.enhanced_analyses
            else:
                self.stats.average_enhanced_duration = duration

        elif mode == "basic":
            if self.stats.basic_analyses > 0:
                self.stats.average_basic_duration = (
                    self.stats.average_basic_duration * (self.stats.basic_analyses - 1)
                    + duration
                ) / self.stats.basic_analyses
            else:
                self.stats.average_basic_duration = duration

        # Calculate performance improvement ratio
        if (
            self.stats.average_basic_duration > 0
            and self.stats.average_enhanced_duration > 0
        ):
            # Ratio of correlation quality improvement vs time cost
            # (This would need actual quality metrics to be meaningful)
            self.stats.performance_improvement_ratio = (
                self.stats.average_enhanced_duration / self.stats.average_basic_duration
            )

    def get_integration_stats(self) -> dict[str, Any]:
        """Get integration performance and usage statistics."""

        return {
            "total_analyses": self.stats.total_analyses,
            "mode_breakdown": {
                "enhanced": self.stats.enhanced_analyses,
                "basic": self.stats.basic_analyses,
                "hybrid": self.stats.hybrid_analyses,
            },
            "performance": {
                "average_enhanced_duration_seconds": self.stats.average_enhanced_duration,
                "average_basic_duration_seconds": self.stats.average_basic_duration,
                "performance_improvement_ratio": self.stats.performance_improvement_ratio,
            },
            "reliability": {
                "fallback_count": self.stats.fallback_count,
                "fallback_rate": self.stats.fallback_count
                / max(1, self.stats.total_analyses),
            },
            "data_coverage": {
                "rich_data_documents": self.stats.rich_data_documents,
                "rich_data_rate": self.stats.rich_data_documents
                / max(1, self.stats.total_analyses),
            },
            "configuration": {
                "analysis_mode": self.config.analysis_mode.value,
                "enhanced_threshold": self.config.enhanced_threshold,
                "performance_monitoring": self.config.performance_monitoring,
                "cache_enabled": self.config.cache_analysis_results,
            },
        }

    def clear_cache(self):
        """Clear analysis and rich data caches."""
        self.analysis_cache.clear()
        self.rich_data_cache.clear()
        logger.info("Integration caches cleared")


# Global integration instance (singleton pattern)
_integration_instance = None


def get_intelligence_correlation_integration(
    config: Optional[IntegrationConfig] = None,
    data_access: Optional[IntelligenceDataAccess] = None,
) -> IntelligenceCorrelationIntegration:
    """
    Get the global intelligence correlation integration instance.

    Args:
        config: Integration configuration (only used on first call)
        data_access: Intelligence data access instance (only used on first call)

    Returns:
        IntelligenceCorrelationIntegration instance
    """
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = IntelligenceCorrelationIntegration(config, data_access)
    return _integration_instance
