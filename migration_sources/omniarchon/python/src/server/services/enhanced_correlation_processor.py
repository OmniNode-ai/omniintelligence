"""
Enhanced Correlation Processor Service

Extended correlation processor that integrates with rich intelligence documents.
Provides enhanced processing capabilities while maintaining backward compatibility
with the existing correlation processing workflow.

This service extends the base CorrelationProcessor with:
- Integration with intelligence correlation integration service
- Rich data detection and processing optimization
- Enhanced result persistence with technology and architecture data
- Performance monitoring and fallback mechanisms
- Backward compatibility with existing workflow
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Optional

from server.data.intelligence_data_access import QueryParameters
from server.services.correlation_analyzer import (
    CorrelationAnalysisResult,
    DocumentContext,
)
from server.services.correlation_processor import (
    CorrelationProcessor,
    CorrelationTask,
    ProcessingStats,
    ProcessingStatus,
)
from server.services.intelligence_correlation_integration import (
    AnalysisMode,
    IntegrationConfig,
    get_intelligence_correlation_integration,
)

logger = logging.getLogger(__name__)


@dataclass
class EnhancedProcessingStats(ProcessingStats):
    """Enhanced processing statistics with intelligence integration metrics."""

    enhanced_analyses: int = 0
    basic_analyses: int = 0
    rich_data_correlations: int = 0
    technology_correlations: int = 0
    architecture_correlations: int = 0
    enhanced_avg_processing_time: float = 0.0
    fallback_to_basic_count: int = 0


class EnhancedCorrelationProcessor(CorrelationProcessor):
    """
    Enhanced correlation processor with intelligence integration.

    This processor extends the base functionality to leverage rich intelligence
    document data while maintaining full backward compatibility.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        """
        Initialize enhanced correlation processor.

        Args:
            config: Configuration dictionary with processing and integration parameters
        """
        super().__init__(config)

        # Initialize structured logging
        from ..utils.correlation_logging import processor_logger

        self.correlation_logger = processor_logger

        # Enhanced configuration
        self.integration_config = self._create_integration_config(config)

        # Initialize intelligence integration
        self.intelligence_integration = get_intelligence_correlation_integration(
            self.integration_config, self.get_data_access()
        )

        # Enhanced statistics
        self.enhanced_stats = EnhancedProcessingStats()

        # Performance tracking
        self.enhanced_processing_times: list[float] = []
        self.basic_processing_times: list[float] = []

        # Log initialization
        self.correlation_logger.log_info(
            "enhanced_processor_initialized",
            {
                "analysis_mode": self.integration_config.analysis_mode.value,
                "enhanced_threshold": self.integration_config.enhanced_threshold,
                "technology_weight": self.integration_config.technology_weight,
                "architecture_weight": self.integration_config.architecture_weight,
                "performance_monitoring": self.integration_config.performance_monitoring,
                "version": "2.0.0-enhanced-logging",
            },
        )

    def _create_integration_config(
        self, config: Optional[dict[str, Any]]
    ) -> IntegrationConfig:
        """Create integration configuration from processor config."""

        if not config:
            config = {}

        integration_config = IntegrationConfig()

        # Map processor config to integration config
        if "analysis_mode" in config:
            mode_map = {
                "auto": AnalysisMode.AUTO,
                "enhanced": AnalysisMode.ENHANCED,
                "basic": AnalysisMode.BASIC,
                "hybrid": AnalysisMode.HYBRID,
            }
            integration_config.analysis_mode = mode_map.get(
                config["analysis_mode"], AnalysisMode.AUTO
            )

        # Enhanced analyzer weights
        integration_config.technology_weight = config.get("technology_weight", 0.4)
        integration_config.architecture_weight = config.get("architecture_weight", 0.3)
        integration_config.rich_content_bonus = config.get("rich_content_bonus", 0.2)

        # Performance settings
        integration_config.enhanced_threshold = config.get("enhanced_threshold", 0.5)
        integration_config.performance_monitoring = config.get(
            "performance_monitoring", True
        )
        integration_config.fallback_timeout_seconds = config.get(
            "fallback_timeout_seconds", 30
        )
        integration_config.cache_analysis_results = config.get(
            "cache_analysis_results", True
        )

        # Base analyzer settings - get from config or use defaults
        integration_config.temporal_threshold_hours = config.get(
            "temporal_threshold_hours", 72
        )
        integration_config.semantic_threshold = config.get("semantic_threshold", 0.3)
        integration_config.max_correlations_per_document = config.get(
            "max_correlations_per_document", 10
        )

        return integration_config

    async def _process_single_task(
        self, task: CorrelationTask, context_documents: list[DocumentContext]
    ):
        """Enhanced single task processing with intelligence integration."""

        correlation_id = self.correlation_logger.generate_correlation_id()

        with self.correlation_logger.correlation_context(correlation_id):
            task.status = ProcessingStatus.IN_PROGRESS
            task.attempts += 1
            start_time = datetime.now(UTC)

            self.correlation_logger.log_processing_start(
                f"enhanced_task_processing_{task.document_id}",
                {
                    "task_document_id": task.document_id,
                    "repository": task.repository,
                    "commit_sha": task.commit_sha[:8] if task.commit_sha else "unknown",
                    "attempt_number": task.attempts,
                    "max_retries": self.max_retries,
                    "context_documents_count": len(context_documents),
                    "task_priority": task.priority,
                    "processing_mode": "enhanced_intelligence_integration",
                },
            )

            try:
                # Get target document data with logging
                self.correlation_logger.log_debug(
                    "retrieving_target_document",
                    {
                        "task_document_id": task.document_id,
                        "repository": task.repository,
                        "operation": "get_target_document",
                    },
                )

                target_document = await self._get_target_document(task)
                if not target_document:
                    raise ValueError(
                        f"Could not retrieve document data for {task.document_id}"
                    )

                # Log document retrieval success
                self.correlation_logger.log_debug(
                    "target_document_retrieved",
                    {
                        "task_document_id": task.document_id,
                        "document_has_content": hasattr(target_document, "content")
                        and bool(target_document.content),
                        "document_modified_files_count": (
                            len(target_document.modified_files)
                            if hasattr(target_document, "modified_files")
                            else 0
                        ),
                    },
                )

                # Use intelligence-aware correlation analysis with document enrichment
                self.correlation_logger.log_debug(
                    "starting_intelligence_analysis",
                    {
                        "task_document_id": task.document_id,
                        "integration_mode": self.integration_config.analysis_mode.value,
                        "enhanced_threshold": self.integration_config.enhanced_threshold,
                        "context_documents_available": len(context_documents),
                    },
                )

                analysis_result = (
                    await self.intelligence_integration.analyze_document_correlations(
                        target_document, context_documents
                    )
                )

                # Log analysis results
                self.correlation_logger.log_document_analysis(
                    task.document_id,
                    task.repository,
                    analysis_result.analysis_metadata.get(
                        "integration_mode", "unknown"
                    ),
                    analysis_result.analysis_metadata.get("rich_data_available", False),
                    {
                        "temporal_correlations": len(
                            analysis_result.temporal_correlations
                        ),
                        "semantic_correlations": len(
                            analysis_result.semantic_correlations
                        ),
                        "breaking_changes": len(analysis_result.breaking_changes),
                        "technology_correlations": self._count_technology_correlations(
                            analysis_result
                        ),
                        "architecture_correlations": self._count_architecture_correlations(
                            analysis_result
                        ),
                    },
                )

                # Enhance result with additional metadata
                enhanced_result = self._enhance_analysis_result(
                    analysis_result, task, start_time
                )

                # Save enhanced results with comprehensive logging
                self.correlation_logger.log_debug(
                    "saving_enhanced_results",
                    {
                        "task_document_id": task.document_id,
                        "correlations_to_save": {
                            "temporal": len(enhanced_result.temporal_correlations),
                            "semantic": len(enhanced_result.semantic_correlations),
                            "breaking_changes": len(enhanced_result.breaking_changes),
                        },
                        "database_operation": "save_correlation_results",
                    },
                )

                success = await self._save_enhanced_correlation_results(
                    task, enhanced_result
                )

                if success:
                    task.status = ProcessingStatus.COMPLETED
                    processing_duration = (
                        datetime.now(UTC) - start_time
                    ).total_seconds()

                    # Update task metadata
                    task.processing_metadata = {
                        "processing_time_seconds": processing_duration,
                        "temporal_correlations": len(
                            enhanced_result.temporal_correlations
                        ),
                        "semantic_correlations": len(
                            enhanced_result.semantic_correlations
                        ),
                        "breaking_changes": len(enhanced_result.breaking_changes),
                        "analysis_mode": enhanced_result.analysis_metadata.get(
                            "integration_mode", "unknown"
                        ),
                        "rich_data_available": enhanced_result.analysis_metadata.get(
                            "rich_data_available", False
                        ),
                        "technology_correlations": self._count_technology_correlations(
                            enhanced_result
                        ),
                        "architecture_correlations": self._count_architecture_correlations(
                            enhanced_result
                        ),
                    }

                    # Log database operation success
                    self.correlation_logger.log_database_operation(
                        "update", "correlation_results", task.document_id, True, 1
                    )

                    # Log rich intelligence usage if applicable
                    if enhanced_result.analysis_metadata.get(
                        "rich_data_available", False
                    ):
                        self.correlation_logger.log_rich_intelligence_usage(
                            task.document_id,
                            enhanced_result.analysis_metadata.get(
                                "technologies_detected", []
                            ),
                            enhanced_result.analysis_metadata.get(
                                "architecture_patterns", []
                            ),
                            True,
                        )

                    # Update enhanced statistics
                    self._update_enhanced_statistics(
                        enhanced_result, processing_duration
                    )

                    # Update base statistics
                    self.processing_stats.total_documents_processed += 1
                    self.processing_stats.successful_correlations += 1
                    self.processing_stats.total_correlations_generated += len(
                        enhanced_result.temporal_correlations
                    ) + len(enhanced_result.semantic_correlations)

                    # Log performance metrics
                    self.correlation_logger.log_performance_metrics(
                        f"enhanced_task_processing_{task.document_id}",
                        processing_duration,
                        additional_metrics={
                            "correlations_generated": len(
                                enhanced_result.temporal_correlations
                            )
                            + len(enhanced_result.semantic_correlations),
                            "analysis_mode": enhanced_result.analysis_metadata.get(
                                "integration_mode", "unknown"
                            ),
                            "technology_correlations": self._count_technology_correlations(
                                enhanced_result
                            ),
                            "architecture_correlations": self._count_architecture_correlations(
                                enhanced_result
                            ),
                        },
                    )

                    self.correlation_logger.log_processing_complete(
                        f"enhanced_task_processing_{task.document_id}",
                        {
                            "processing_duration_seconds": processing_duration,
                            "correlations_generated": {
                                "temporal": len(enhanced_result.temporal_correlations),
                                "semantic": len(enhanced_result.semantic_correlations),
                                "breaking_changes": len(
                                    enhanced_result.breaking_changes
                                ),
                            },
                            "analysis_mode": enhanced_result.analysis_metadata.get(
                                "integration_mode", "unknown"
                            ),
                            "rich_data_available": enhanced_result.analysis_metadata.get(
                                "rich_data_available", False
                            ),
                            "database_updated": True,
                            "task_completed": True,
                        },
                    )

                    logger.info(
                        f"Successfully processed enhanced correlations for document {task.document_id}: "
                        f"{len(enhanced_result.temporal_correlations)} temporal, "
                        f"{len(enhanced_result.semantic_correlations)} semantic, "
                        f"mode: {enhanced_result.analysis_metadata.get('integration_mode', 'unknown')}"
                    )
                else:
                    raise ValueError("Failed to save enhanced correlation results")

            except Exception as e:
                processing_duration = (datetime.now(UTC) - start_time).total_seconds()

                self.correlation_logger.log_processing_error(
                    f"enhanced_task_processing_{task.document_id}",
                    e,
                    {
                        "task_document_id": task.document_id,
                        "repository": task.repository,
                        "commit_sha": (
                            task.commit_sha[:8] if task.commit_sha else "unknown"
                        ),
                        "attempt_number": task.attempts,
                        "processing_duration_seconds": processing_duration,
                        "context_documents_count": len(context_documents),
                    },
                )

                # Log database operation failure
                self.correlation_logger.log_database_operation(
                    "update", "correlation_results", task.document_id, False, 0
                )

                logger.error(
                    f"Error in enhanced processing for document {task.document_id}: {e}"
                )
                task.status = ProcessingStatus.FAILED
                task.last_error = str(e)
                self.processing_stats.failed_processing += 1

                # Schedule retry if under retry limit
                if task.attempts < self.max_retries:
                    task.status = ProcessingStatus.RETRYING
                    self.correlation_logger.log_debug(
                        "scheduling_task_retry",
                        {
                            "task_document_id": task.document_id,
                            "current_attempt": task.attempts,
                            "max_retries": self.max_retries,
                            "retry_scheduled": True,
                        },
                    )
                    logger.info(
                        f"Will retry document {task.document_id} (attempt {task.attempts}/{self.max_retries})"
                    )

    def _enhance_analysis_result(
        self,
        analysis_result: CorrelationAnalysisResult,
        task: CorrelationTask,
        start_time: datetime,
    ) -> CorrelationAnalysisResult:
        """Enhance analysis result with additional metadata."""

        # Add enhanced metadata
        if "analysis_metadata" not in analysis_result.analysis_metadata:
            analysis_result.analysis_metadata = {}

        analysis_result.analysis_metadata.update(
            {
                "processor_version": "1.1.0-enhanced",
                "task_id": f"{task.document_id}_{task.attempts}",
                "processing_started": start_time.isoformat(),
                "repository": task.repository,
                "commit_sha": task.commit_sha,
                "task_priority": task.priority,
                "batch_processing": self.current_batch is not None,
                "enhanced_processor": True,
            }
        )

        return analysis_result

    async def _save_enhanced_correlation_results(
        self, task: CorrelationTask, analysis_result: CorrelationAnalysisResult
    ) -> bool:
        """
        Save enhanced correlation analysis results with rich data preservation.

        This method extends the base save functionality to preserve technology
        and architecture correlation data in the results.
        """
        try:
            # Extract enhanced correlation data
            enhanced_correlations = self._extract_enhanced_correlation_data(
                analysis_result
            )

            # Log enhanced correlation details
            logger.info(
                f"Saving enhanced correlations for document {task.document_id}: "
                f"{len(analysis_result.temporal_correlations)} temporal, "
                f"{len(analysis_result.semantic_correlations)} semantic, "
                f"{enhanced_correlations['technology_correlations']} technology-based, "
                f"{enhanced_correlations['architecture_correlations']} architecture-based"
            )

            # Enhanced logging for rich correlation data
            self._log_enhanced_correlations(analysis_result)

            # TODO: Implement actual database update with enhanced data
            # This would involve updating the document's correlation_analysis section
            # with the new rich intelligence correlation data

            # For now, use the base implementation with enhanced logging
            return await super()._save_correlation_results(task, analysis_result)

        except Exception as e:
            logger.error(
                f"Error saving enhanced correlation results for document {task.document_id}: {e}"
            )
            return False

    def _extract_enhanced_correlation_data(
        self, analysis_result: CorrelationAnalysisResult
    ) -> dict[str, Any]:
        """Extract enhanced correlation data for persistence."""

        enhanced_data = {
            "technology_correlations": 0,
            "architecture_correlations": 0,
            "rich_data_correlations": 0,
            "correlation_quality_score": 0.0,
        }

        # Count technology-based correlations
        for correlation in (
            analysis_result.temporal_correlations
            + analysis_result.semantic_correlations
        ):
            factors = getattr(correlation, "correlation_factors", []) or getattr(
                correlation, "similarity_factors", []
            )

            for factor in factors:
                if any(keyword in factor.lower() for keyword in ["technology", "tech"]):
                    enhanced_data["technology_correlations"] += 1
                if any(
                    keyword in factor.lower() for keyword in ["architecture", "pattern"]
                ):
                    enhanced_data["architecture_correlations"] += 1
                if "rich intelligence data" in factor.lower():
                    enhanced_data["rich_data_correlations"] += 1

        # Calculate quality score based on correlation strength and richness
        strengths = []
        for tc in analysis_result.temporal_correlations:
            strengths.append(tc.correlation_strength)
        for sc in analysis_result.semantic_correlations:
            strengths.append(sc.semantic_similarity)

        if strengths:
            enhanced_data["correlation_quality_score"] = sum(strengths) / len(strengths)

        return enhanced_data

    def _log_enhanced_correlations(self, analysis_result: CorrelationAnalysisResult):
        """Enhanced logging for correlation details."""

        # Log temporal correlations with enhanced factors
        for tc in analysis_result.temporal_correlations:
            enhanced_factors = [
                f
                for f in tc.correlation_factors
                if any(
                    keyword in f.lower()
                    for keyword in ["technology", "architecture", "rich"]
                )
            ]
            if enhanced_factors:
                logger.debug(
                    f"Enhanced temporal correlation: {tc.repository}:{tc.commit_sha} "
                    f"(strength: {tc.correlation_strength}, enhanced_factors: {enhanced_factors})"
                )

        # Log semantic correlations with rich data
        for sc in analysis_result.semantic_correlations:
            rich_factors = [
                f
                for f in sc.similarity_factors
                if any(
                    keyword in f.lower()
                    for keyword in ["technology", "architecture", "stack", "pattern"]
                )
            ]
            if rich_factors:
                logger.debug(
                    f"Enhanced semantic correlation: {sc.repository}:{sc.commit_sha} "
                    f"(similarity: {sc.semantic_similarity}, rich_factors: {rich_factors})"
                )

    def _count_technology_correlations(
        self, analysis_result: CorrelationAnalysisResult
    ) -> int:
        """Count correlations based on technology stack matching."""
        count = 0

        for correlation in (
            analysis_result.temporal_correlations
            + analysis_result.semantic_correlations
        ):
            factors = getattr(correlation, "correlation_factors", []) or getattr(
                correlation, "similarity_factors", []
            )

            if any("technology" in factor.lower() for factor in factors):
                count += 1

        return count

    def _count_architecture_correlations(
        self, analysis_result: CorrelationAnalysisResult
    ) -> int:
        """Count correlations based on architecture pattern matching."""
        count = 0

        for correlation in (
            analysis_result.temporal_correlations
            + analysis_result.semantic_correlations
        ):
            factors = getattr(correlation, "correlation_factors", []) or getattr(
                correlation, "similarity_factors", []
            )

            if any("architecture" in factor.lower() for factor in factors):
                count += 1

        return count

    def _update_enhanced_statistics(
        self, analysis_result: CorrelationAnalysisResult, processing_duration: float
    ):
        """Update enhanced processing statistics."""

        # Determine analysis mode used
        mode = analysis_result.analysis_metadata.get("integration_mode", "unknown")

        if mode == "enhanced":
            self.enhanced_stats.enhanced_analyses += 1
            self.enhanced_processing_times.append(processing_duration)

            # Update average enhanced processing time
            self.enhanced_stats.enhanced_avg_processing_time = sum(
                self.enhanced_processing_times
            ) / len(self.enhanced_processing_times)

        elif mode == "basic":
            self.enhanced_stats.basic_analyses += 1
            self.basic_processing_times.append(processing_duration)

        # Count rich data correlations
        if analysis_result.analysis_metadata.get("rich_data_available", False):
            self.enhanced_stats.rich_data_correlations += 1

        # Count specific correlation types
        self.enhanced_stats.technology_correlations += (
            self._count_technology_correlations(analysis_result)
        )
        self.enhanced_stats.architecture_correlations += (
            self._count_architecture_correlations(analysis_result)
        )

    def get_enhanced_processing_stats(self) -> dict[str, Any]:
        """Get enhanced processing statistics."""

        base_stats = super().get_processing_stats()

        # Add enhanced statistics
        enhanced_stats = {
            "enhanced_analyses": self.enhanced_stats.enhanced_analyses,
            "basic_analyses": self.enhanced_stats.basic_analyses,
            "rich_data_correlations": self.enhanced_stats.rich_data_correlations,
            "technology_correlations": self.enhanced_stats.technology_correlations,
            "architecture_correlations": self.enhanced_stats.architecture_correlations,
            "enhanced_avg_processing_time": self.enhanced_stats.enhanced_avg_processing_time,
            "fallback_to_basic_count": self.enhanced_stats.fallback_to_basic_count,
            "integration_stats": self.intelligence_integration.get_integration_stats(),
        }

        base_stats["enhanced_statistics"] = enhanced_stats
        return base_stats

    async def queue_documents_with_empty_correlations(self) -> int:
        """
        Enhanced queuing that prioritizes documents with rich intelligence data.

        This method extends the base functionality to prioritize documents that
        have rich intelligence data for enhanced correlation analysis.
        """
        correlation_id = self.correlation_logger.generate_correlation_id()

        with self.correlation_logger.correlation_context(correlation_id):
            self.correlation_logger.log_processing_start(
                "enhanced_document_queuing",
                {
                    "operation_type": "queue_empty_correlations",
                    "time_range": "7d",
                    "document_limit": 1000,
                    "prioritization": "rich_data_first",
                },
            )

            try:
                data_access = self.get_data_access()

                # Get documents from the last 7 days
                self.correlation_logger.log_debug(
                    "fetching_documents_for_queuing",
                    {"time_range": "7d", "limit": 1000, "offset": 0},
                )

                params = QueryParameters(time_range="7d", limit=1000, offset=0)

                documents = data_access.get_parsed_documents(params)
                queued_count = 0

                self.correlation_logger.log_debug(
                    "documents_retrieved_for_queuing",
                    {
                        "total_documents": len(documents),
                        "repositories": list({doc.repository for doc in documents}),
                    },
                )

                # Separate documents by rich data availability
                rich_data_docs = []
                basic_docs = []
                documents_with_correlations = []

                for doc in documents:
                    # Check if document has empty correlations
                    has_temporal = len(doc.temporal_correlations) > 0
                    has_semantic = len(doc.semantic_correlations) > 0

                    if not has_temporal and not has_semantic:
                        # Check for rich intelligence data
                        has_rich_data = self._check_document_rich_data(doc)

                        if has_rich_data:
                            rich_data_docs.append(doc)
                            self.correlation_logger.log_debug(
                                "document_prioritized_rich_data",
                                {
                                    "document_id": doc.id,
                                    "repository": doc.repository,
                                    "commit_sha": (
                                        doc.commit_sha[:8]
                                        if doc.commit_sha
                                        else "unknown"
                                    ),
                                    "has_technologies": (
                                        bool(
                                            doc.raw_content.get(
                                                "technologies_detected", []
                                            )
                                        )
                                        if hasattr(doc, "raw_content")
                                        and doc.raw_content
                                        else False
                                    ),
                                    "has_architecture": (
                                        bool(
                                            doc.raw_content.get(
                                                "architecture_patterns", []
                                            )
                                        )
                                        if hasattr(doc, "raw_content")
                                        and doc.raw_content
                                        else False
                                    ),
                                    "priority_category": "rich_data",
                                },
                            )
                        else:
                            basic_docs.append(doc)
                            self.correlation_logger.log_debug(
                                "document_queued_basic",
                                {
                                    "document_id": doc.id,
                                    "repository": doc.repository,
                                    "commit_sha": (
                                        doc.commit_sha[:8]
                                        if doc.commit_sha
                                        else "unknown"
                                    ),
                                    "priority_category": "basic",
                                },
                            )
                    else:
                        documents_with_correlations.append(doc)

                self.correlation_logger.log_info(
                    "document_categorization_complete",
                    {
                        "total_documents_analyzed": len(documents),
                        "rich_data_documents": len(rich_data_docs),
                        "basic_documents": len(basic_docs),
                        "documents_with_existing_correlations": len(
                            documents_with_correlations
                        ),
                        "queuing_targets": len(rich_data_docs) + len(basic_docs),
                    },
                )

                # Queue rich data documents with higher priority
                for doc in rich_data_docs:
                    doc_age_hours = (
                        datetime.now(UTC)
                        - datetime.fromisoformat(doc.created_at.replace("Z", "+00:00"))
                    ).total_seconds() / 3600.0

                    # Higher priority for newer documents with rich data
                    priority = max(
                        6, min(10, int(12 - (doc_age_hours / 24)))
                    )  # 6-10 for rich data

                    self.correlation_logger.log_debug(
                        "queuing_rich_data_document",
                        {
                            "document_id": doc.id,
                            "repository": doc.repository,
                            "commit_sha": (
                                doc.commit_sha[:8] if doc.commit_sha else "unknown"
                            ),
                            "age_hours": doc_age_hours,
                            "assigned_priority": priority,
                            "priority_range": "6-10_rich_data",
                        },
                    )

                    if await self.queue_document_for_processing(
                        doc.id, doc.repository, doc.commit_sha, priority
                    ):
                        queued_count += 1
                        self.correlation_logger.log_debug(
                            "document_queued_successfully",
                            {
                                "document_id": doc.id,
                                "repository": doc.repository,
                                "priority": priority,
                                "queue_position": queued_count,
                            },
                        )

                # Queue basic documents with standard priority
                for doc in basic_docs:
                    doc_age_hours = (
                        datetime.now(UTC)
                        - datetime.fromisoformat(doc.created_at.replace("Z", "+00:00"))
                    ).total_seconds() / 3600.0

                    # Standard priority for basic documents
                    priority = max(
                        1, min(5, int(10 - (doc_age_hours / 24)))
                    )  # 1-5 for basic

                    self.correlation_logger.log_debug(
                        "queuing_basic_document",
                        {
                            "document_id": doc.id,
                            "repository": doc.repository,
                            "commit_sha": (
                                doc.commit_sha[:8] if doc.commit_sha else "unknown"
                            ),
                            "age_hours": doc_age_hours,
                            "assigned_priority": priority,
                            "priority_range": "1-5_basic",
                        },
                    )

                    if await self.queue_document_for_processing(
                        doc.id, doc.repository, doc.commit_sha, priority
                    ):
                        queued_count += 1
                        self.correlation_logger.log_debug(
                            "document_queued_successfully",
                            {
                                "document_id": doc.id,
                                "repository": doc.repository,
                                "priority": priority,
                                "queue_position": queued_count,
                            },
                        )

                self.correlation_logger.log_processing_complete(
                    "enhanced_document_queuing",
                    {
                        "total_documents_queued": queued_count,
                        "rich_data_documents_queued": len(rich_data_docs),
                        "basic_documents_queued": len(basic_docs),
                        "documents_skipped": len(documents_with_correlations),
                        "queuing_success_rate": (
                            (
                                queued_count
                                / (len(rich_data_docs) + len(basic_docs))
                                * 100
                            )
                            if (rich_data_docs or basic_docs)
                            else 0
                        ),
                    },
                )

                logger.info(
                    f"Queued {queued_count} documents for enhanced processing: "
                    f"{len(rich_data_docs)} with rich data, {len(basic_docs)} basic"
                )
                return queued_count

            except Exception as e:
                self.correlation_logger.log_processing_error(
                    "enhanced_document_queuing",
                    e,
                    {
                        "operation_type": "queue_empty_correlations",
                        "time_range": "7d",
                        "document_limit": 1000,
                    },
                )

                logger.error(f"Error queuing documents for enhanced processing: {e}")
                return 0

    def _check_document_rich_data(self, doc) -> bool:
        """Check if a document has rich intelligence data."""
        try:
            raw_content = getattr(doc, "raw_content", {})

            has_technologies = bool(raw_content.get("technologies_detected"))
            has_architecture = bool(raw_content.get("architecture_patterns"))

            return has_technologies or has_architecture

        except Exception as e:
            logger.debug(f"Error checking rich data for document {doc.id}: {e}")
            return False


# Global enhanced processor instance (singleton pattern)
_enhanced_processor_instance = None


def get_enhanced_correlation_processor(
    config: Optional[dict[str, Any]] = None,
) -> EnhancedCorrelationProcessor:
    """
    Get the global enhanced correlation processor instance.

    Args:
        config: Configuration dictionary (only used on first call)

    Returns:
        EnhancedCorrelationProcessor instance
    """
    global _enhanced_processor_instance
    if _enhanced_processor_instance is None:
        _enhanced_processor_instance = EnhancedCorrelationProcessor(config)
    return _enhanced_processor_instance
