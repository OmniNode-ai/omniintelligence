#!/usr/bin/env python3
"""
Intelligence Operation Type Enumeration for Intelligence Adapter Effect Node.

Defines operation types for the Intelligence Adapter that routes requests to
various Archon intelligence services (quality assessment, performance analysis,
document freshness, pattern learning, etc.).

ONEX v2.0 Compliance:
- Enum-based naming: EnumIntelligenceOperationType
- String-based enum for JSON serialization
- Integration with ModelIntelligenceInput
- Categorical grouping for clear operation domains

Architecture:
The Intelligence Adapter acts as a unified interface to Archon's intelligence
services, routing operations to the appropriate backend service based on the
operation type.

See Also:
- ModelIntelligenceInput for request structure
- Intelligence Service APIs at http://localhost:8053
- /CLAUDE.md for complete intelligence API reference
"""

from enum import Enum


class EnumIntelligenceOperationType(str, Enum):
    """
    Intelligence operation types for routing to backend intelligence services.

    This enum provides operation types that route to Archon's intelligence
    services including quality assessment, performance analysis, document
    freshness, pattern learning, and vector operations.

    Operation Categories:
        Quality Assessment: Code and document quality analysis
        Performance: Baseline establishment, optimization, trend monitoring
        Document Freshness: Freshness analysis and refresh operations
        Pattern Learning: Pattern matching, analytics, traceability
        Vector Operations: Semantic search and indexing
        Knowledge Graph: Entity extraction and relationship analysis
        Autonomous Learning: Pattern ingestion and prediction

    Usage Examples:
        # Quality assessment operation
        operation_type = EnumIntelligenceOperationType.ASSESS_CODE_QUALITY

        # Performance baseline operation
        operation_type = EnumIntelligenceOperationType.ESTABLISH_PERFORMANCE_BASELINE

        # Document freshness analysis
        operation_type = EnumIntelligenceOperationType.ANALYZE_DOCUMENT_FRESHNESS

    See Also:
        /CLAUDE.md Intelligence APIs (78) section for complete API reference
    """

    # =============================================================================
    # Quality Assessment Operations (4)
    # =============================================================================

    ASSESS_CODE_QUALITY = "assess_code_quality"
    """
    Analyze code for ONEX compliance and quality scoring (6 dimensions).

    Requires:
        - content: Source code to analyze
        - source_path: Path to source file
        - language: Programming language (python, typescript, rust, etc.)

    Returns:
        - quality_score: Overall quality (0.0-1.0)
        - complexity: Complexity metrics (cyclomatic, cognitive)
        - onex_compliance: ONEX architectural compliance score
        - issues: List of quality issues with severity
        - recommendations: Improvement suggestions

    Backend: POST /assess/code
    """

    ANALYZE_DOCUMENT_QUALITY = "analyze_document_quality"
    """
    Analyze document quality and completeness.

    Requires:
        - content: Document content
        - source_path: Path to document

    Returns:
        - quality_score: Document quality (0.0-1.0)
        - completeness: Coverage metrics
        - issues: Documentation gaps and issues

    Backend: POST /assess/document
    """

    GET_QUALITY_PATTERNS = "get_quality_patterns"
    """
    Extract quality patterns and anti-patterns from code.

    Requires:
        - content: Source code to analyze
        - language: Programming language

    Returns:
        - patterns: Detected best practices
        - anti_patterns: Detected anti-patterns
        - security_patterns: Security-related patterns

    Backend: POST /patterns/extract
    """

    CHECK_ARCHITECTURAL_COMPLIANCE = "check_architectural_compliance"
    """
    Verify architectural compliance with ONEX standards.

    Requires:
        - content: Source code to validate
        - source_path: Path to source file

    Returns:
        - compliance_score: ONEX compliance (0.0-1.0)
        - violations: List of compliance violations
        - recommendations: Compliance improvements

    Backend: POST /compliance/check
    """

    # =============================================================================
    # Performance Operations (5)
    # =============================================================================

    ESTABLISH_PERFORMANCE_BASELINE = "establish_performance_baseline"
    """
    Establish performance baselines for operations.

    Requires:
        - operation_name: Name of operation to baseline
        - options: Baseline configuration

    Returns:
        - baseline_metrics: Established performance baselines
        - thresholds: Recommended performance thresholds

    Backend: POST /performance/baseline
    """

    IDENTIFY_OPTIMIZATION_OPPORTUNITIES = "identify_optimization_opportunities"
    """
    Identify performance optimization opportunities.

    Requires:
        - operation_name: Operation to analyze
        - options: Analysis parameters

    Returns:
        - opportunities: List of optimization opportunities
        - roi_estimates: Return on investment estimates
        - priority: ROI-ranked priorities

    Backend: GET /performance/opportunities/{operation_name}
    """

    APPLY_PERFORMANCE_OPTIMIZATION = "apply_performance_optimization"
    """
    Apply performance optimizations.

    Requires:
        - operation_name: Operation to optimize
        - optimization_id: ID of optimization to apply
        - options: Optimization parameters

    Returns:
        - applied_optimizations: List of applied optimizations
        - performance_impact: Before/after metrics

    Backend: POST /performance/optimize
    """

    GET_OPTIMIZATION_REPORT = "get_optimization_report"
    """
    Generate comprehensive optimization report.

    Requires:
        - operation_name: Operation to report on (optional)
        - options: Report parameters

    Returns:
        - report: Comprehensive optimization analysis
        - metrics: Performance metrics and trends

    Backend: GET /performance/report
    """

    MONITOR_PERFORMANCE_TRENDS = "monitor_performance_trends"
    """
    Monitor performance trends over time.

    Requires:
        - operation_name: Operation to monitor
        - options: Trend analysis parameters

    Returns:
        - trends: Performance trend analysis
        - predictions: Predicted future performance
        - anomalies: Detected performance anomalies

    Backend: GET /performance/trends
    """

    # =============================================================================
    # Document Freshness Operations (6)
    # =============================================================================

    ANALYZE_DOCUMENT_FRESHNESS = "analyze_document_freshness"
    """
    Analyze document freshness and staleness.

    Requires:
        - source_path: Path to document
        - options: Freshness analysis parameters

    Returns:
        - freshness_score: Freshness score (0.0-1.0)
        - staleness_indicators: Indicators of staleness
        - refresh_recommendations: Refresh recommendations

    Backend: POST /freshness/analyze
    """

    GET_STALE_DOCUMENTS = "get_stale_documents"
    """
    Retrieve list of stale documents.

    Requires:
        - options: Staleness threshold parameters

    Returns:
        - stale_documents: List of stale documents
        - staleness_scores: Staleness metrics per document

    Backend: GET /freshness/stale
    """

    REFRESH_DOCUMENTS = "refresh_documents"
    """
    Refresh stale documents with quality gates.

    Requires:
        - source_path: Path to document(s) to refresh
        - options: Refresh parameters

    Returns:
        - refreshed_documents: List of refreshed documents
        - quality_scores: Post-refresh quality scores

    Backend: POST /freshness/refresh
    """

    GET_FRESHNESS_STATS = "get_freshness_stats"
    """
    Get comprehensive freshness statistics.

    Returns:
        - statistics: Freshness statistics across all documents
        - distribution: Freshness score distribution

    Backend: GET /freshness/stats
    """

    GET_DOCUMENT_FRESHNESS = "get_document_freshness"
    """
    Get freshness score for specific document.

    Requires:
        - source_path: Path to specific document

    Returns:
        - freshness_score: Document freshness (0.0-1.0)
        - last_updated: Last update timestamp
        - staleness_reason: Reason for staleness if applicable

    Backend: GET /freshness/document/{path}
    """

    CLEANUP_FRESHNESS_DATA = "cleanup_freshness_data"
    """
    Clean up old freshness analysis data.

    Requires:
        - options: Cleanup parameters (age threshold, etc.)

    Returns:
        - cleaned_records: Number of records cleaned

    Backend: POST /freshness/cleanup
    """

    # =============================================================================
    # Pattern Learning Operations (7)
    # =============================================================================

    PATTERN_MATCH = "pattern_match"
    """
    Match code against learned patterns.

    Requires:
        - content: Code to match
        - options: Matching parameters

    Returns:
        - matches: Matched patterns with confidence
        - recommendations: Pattern-based recommendations

    Backend: POST /api/pattern-learning/pattern/match
    """

    HYBRID_SCORE = "hybrid_score"
    """
    Calculate hybrid pattern scoring.

    Requires:
        - content: Code to score
        - options: Scoring parameters

    Returns:
        - hybrid_score: Combined pattern score
        - score_components: Individual score components

    Backend: POST /api/pattern-learning/hybrid/score
    """

    SEMANTIC_ANALYZE = "semantic_analyze"
    """
    Perform semantic analysis on code patterns.

    Requires:
        - content: Code to analyze semantically
        - options: Analysis parameters

    Returns:
        - semantic_patterns: Detected semantic patterns
        - relationships: Semantic relationships

    Backend: POST /api/pattern-learning/semantic/analyze
    """

    GET_PATTERN_METRICS = "get_pattern_metrics"
    """
    Retrieve pattern learning metrics.

    Returns:
        - metrics: Pattern learning performance metrics
        - statistics: Usage statistics

    Backend: GET /api/pattern-learning/metrics
    """

    GET_CACHE_STATS = "get_cache_stats"
    """
    Get pattern cache statistics.

    Returns:
        - cache_stats: Cache hit/miss rates, sizes
        - performance: Cache performance metrics

    Backend: GET /api/pattern-learning/cache/stats
    """

    CLEAR_PATTERN_CACHE = "clear_pattern_cache"
    """
    Clear pattern learning cache.

    Returns:
        - cache_cleared: Confirmation of cache clear

    Backend: POST /api/pattern-learning/cache/clear
    """

    GET_PATTERN_HEALTH = "get_pattern_health"
    """
    Check pattern learning service health.

    Returns:
        - status: Service health status
        - metrics: Health metrics

    Backend: GET /api/pattern-learning/health
    """

    # =============================================================================
    # Vector Operations (5)
    # =============================================================================

    ADVANCED_VECTOR_SEARCH = "advanced_vector_search"
    """
    Perform high-performance semantic vector search.

    Requires:
        - content: Query text for semantic search
        - options: Search parameters (limit, filters, etc.)

    Returns:
        - results: Search results with similarity scores
        - search_time_ms: Search performance metrics

    Backend: Uses Qdrant vector search
    """

    QUALITY_WEIGHTED_SEARCH = "quality_weighted_search"
    """
    Vector search weighted by ONEX quality scores.

    Requires:
        - content: Query text
        - options: Quality weight (0.0-1.0), min quality score

    Returns:
        - results: Quality-weighted search results
        - quality_scores: ONEX compliance scores per result

    Backend: Hybrid vector search + quality scoring
    """

    BATCH_INDEX_DOCUMENTS = "batch_index_documents"
    """
    Batch index documents for vector search.

    Requires:
        - content: Documents to index (list)
        - options: Indexing parameters

    Returns:
        - indexed_count: Number of documents indexed
        - duration_ms: Indexing performance

    Backend: Bulk vector indexing
    """

    GET_VECTOR_STATS = "get_vector_stats"
    """
    Get vector collection statistics.

    Returns:
        - statistics: Vector collection stats
        - health: Vector DB health metrics

    Backend: Qdrant collection info
    """

    OPTIMIZE_VECTOR_INDEX = "optimize_vector_index"
    """
    Optimize vector index for performance.

    Requires:
        - options: Optimization parameters

    Returns:
        - optimization_result: Optimization results
        - performance_impact: Before/after metrics

    Backend: Qdrant index optimization
    """

    # =============================================================================
    # Pattern Traceability Operations (4)
    # =============================================================================

    TRACK_PATTERN_LINEAGE = "track_pattern_lineage"
    """
    Track pattern creation and lineage.

    Requires:
        - content: Pattern data
        - options: Lineage tracking parameters

    Returns:
        - lineage_id: Pattern lineage identifier
        - tracked_metadata: Lineage metadata

    Backend: POST /api/pattern-traceability/lineage/track
    """

    GET_PATTERN_LINEAGE = "get_pattern_lineage"
    """
    Retrieve pattern lineage history.

    Requires:
        - options: Pattern ID or query filters

    Returns:
        - lineage: Complete pattern lineage
        - evolution: Pattern evolution over time

    Backend: GET /api/pattern-traceability/lineage/{pattern_id}
    """

    GET_EXECUTION_LOGS = "get_execution_logs"
    """
    Get agent execution logs.

    Requires:
        - options: Log query parameters

    Returns:
        - logs: Agent execution logs
        - metadata: Execution metadata

    Backend: GET /api/pattern-traceability/executions/logs
    """

    GET_EXECUTION_SUMMARY = "get_execution_summary"
    """
    Get execution summary statistics.

    Returns:
        - summary: Execution summary statistics
        - metrics: Performance and success metrics

    Backend: GET /api/pattern-traceability/executions/summary
    """

    # =============================================================================
    # Autonomous Learning Operations (7)
    # =============================================================================

    INGEST_PATTERNS = "ingest_patterns"
    """
    Ingest patterns for autonomous learning.

    Requires:
        - content: Pattern data to ingest
        - options: Ingestion parameters

    Returns:
        - ingestion_result: Ingestion confirmation
        - pattern_count: Number of patterns ingested

    Backend: POST /api/autonomous/patterns/ingest
    """

    RECORD_SUCCESS_PATTERN = "record_success_pattern"
    """
    Record successful pattern execution.

    Requires:
        - content: Pattern execution data
        - options: Success metrics

    Returns:
        - recorded: Confirmation of recording
        - learning_impact: Impact on learning models

    Backend: POST /api/autonomous/patterns/success
    """

    PREDICT_AGENT = "predict_agent"
    """
    Predict optimal agent for task.

    Requires:
        - content: Task description
        - options: Prediction parameters

    Returns:
        - predicted_agent: Recommended agent
        - confidence: Prediction confidence
        - alternatives: Alternative agents

    Backend: POST /api/autonomous/predict/agent
    """

    PREDICT_EXECUTION_TIME = "predict_execution_time"
    """
    Predict task execution time.

    Requires:
        - content: Task description
        - options: Prediction parameters

    Returns:
        - predicted_time_ms: Predicted execution time
        - confidence: Prediction confidence

    Backend: POST /api/autonomous/predict/time
    """

    CALCULATE_SAFETY_SCORE = "calculate_safety_score"
    """
    Calculate autonomous action safety score.

    Requires:
        - content: Action description
        - options: Safety parameters

    Returns:
        - safety_score: Safety score (0.0-1.0)
        - risk_factors: Identified risk factors

    Backend: GET /api/autonomous/calculate/safety
    """

    GET_AUTONOMOUS_STATS = "get_autonomous_stats"
    """
    Get autonomous learning statistics.

    Returns:
        - statistics: Learning statistics
        - performance: Learning performance metrics

    Backend: GET /api/autonomous/stats
    """

    GET_AUTONOMOUS_HEALTH = "get_autonomous_health"
    """
    Check autonomous learning service health.

    Returns:
        - status: Service health status
        - metrics: Health metrics

    Backend: GET /api/autonomous/health
    """

    # =============================================================================
    # Utility Methods
    # =============================================================================

    def is_quality_operation(self) -> bool:
        """
        Check if this operation is quality-related.

        Returns:
            True for quality assessment operations
        """
        return self in (
            EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
            EnumIntelligenceOperationType.ANALYZE_DOCUMENT_QUALITY,
            EnumIntelligenceOperationType.GET_QUALITY_PATTERNS,
            EnumIntelligenceOperationType.CHECK_ARCHITECTURAL_COMPLIANCE,
        )

    def is_performance_operation(self) -> bool:
        """
        Check if this operation is performance-related.

        Returns:
            True for performance analysis operations
        """
        return self in (
            EnumIntelligenceOperationType.ESTABLISH_PERFORMANCE_BASELINE,
            EnumIntelligenceOperationType.IDENTIFY_OPTIMIZATION_OPPORTUNITIES,
            EnumIntelligenceOperationType.APPLY_PERFORMANCE_OPTIMIZATION,
            EnumIntelligenceOperationType.GET_OPTIMIZATION_REPORT,
            EnumIntelligenceOperationType.MONITOR_PERFORMANCE_TRENDS,
        )

    def is_document_operation(self) -> bool:
        """
        Check if this operation is document-related.

        Returns:
            True for document freshness operations
        """
        return self in (
            EnumIntelligenceOperationType.ANALYZE_DOCUMENT_FRESHNESS,
            EnumIntelligenceOperationType.GET_STALE_DOCUMENTS,
            EnumIntelligenceOperationType.REFRESH_DOCUMENTS,
            EnumIntelligenceOperationType.GET_FRESHNESS_STATS,
            EnumIntelligenceOperationType.GET_DOCUMENT_FRESHNESS,
            EnumIntelligenceOperationType.CLEANUP_FRESHNESS_DATA,
        )

    def is_pattern_operation(self) -> bool:
        """
        Check if this operation is pattern learning-related.

        Returns:
            True for pattern learning operations
        """
        return self in (
            EnumIntelligenceOperationType.PATTERN_MATCH,
            EnumIntelligenceOperationType.HYBRID_SCORE,
            EnumIntelligenceOperationType.SEMANTIC_ANALYZE,
            EnumIntelligenceOperationType.GET_PATTERN_METRICS,
            EnumIntelligenceOperationType.GET_CACHE_STATS,
            EnumIntelligenceOperationType.CLEAR_PATTERN_CACHE,
            EnumIntelligenceOperationType.GET_PATTERN_HEALTH,
        )

    def is_vector_operation(self) -> bool:
        """
        Check if this operation is vector search-related.

        Returns:
            True for vector operations
        """
        return self in (
            EnumIntelligenceOperationType.ADVANCED_VECTOR_SEARCH,
            EnumIntelligenceOperationType.QUALITY_WEIGHTED_SEARCH,
            EnumIntelligenceOperationType.BATCH_INDEX_DOCUMENTS,
            EnumIntelligenceOperationType.GET_VECTOR_STATS,
            EnumIntelligenceOperationType.OPTIMIZE_VECTOR_INDEX,
        )

    def is_autonomous_operation(self) -> bool:
        """
        Check if this operation is autonomous learning-related.

        Returns:
            True for autonomous learning operations
        """
        return self in (
            EnumIntelligenceOperationType.INGEST_PATTERNS,
            EnumIntelligenceOperationType.RECORD_SUCCESS_PATTERN,
            EnumIntelligenceOperationType.PREDICT_AGENT,
            EnumIntelligenceOperationType.PREDICT_EXECUTION_TIME,
            EnumIntelligenceOperationType.CALCULATE_SAFETY_SCORE,
            EnumIntelligenceOperationType.GET_AUTONOMOUS_STATS,
            EnumIntelligenceOperationType.GET_AUTONOMOUS_HEALTH,
        )

    def requires_content(self) -> bool:
        """
        Check if this operation requires content field.

        Returns:
            True for operations that analyze code/document content
        """
        return self in (
            # Quality operations requiring content
            EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
            EnumIntelligenceOperationType.ANALYZE_DOCUMENT_QUALITY,
            EnumIntelligenceOperationType.GET_QUALITY_PATTERNS,
            EnumIntelligenceOperationType.CHECK_ARCHITECTURAL_COMPLIANCE,
            # Pattern operations requiring content
            EnumIntelligenceOperationType.PATTERN_MATCH,
            EnumIntelligenceOperationType.HYBRID_SCORE,
            EnumIntelligenceOperationType.SEMANTIC_ANALYZE,
            # Vector operations requiring query content
            EnumIntelligenceOperationType.ADVANCED_VECTOR_SEARCH,
            EnumIntelligenceOperationType.QUALITY_WEIGHTED_SEARCH,
        )

    def requires_source_path(self) -> bool:
        """
        Check if this operation requires source_path field.

        Returns:
            True for operations that need file path context
        """
        return self in (
            # Quality operations requiring file context
            EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
            EnumIntelligenceOperationType.ANALYZE_DOCUMENT_QUALITY,
            EnumIntelligenceOperationType.CHECK_ARCHITECTURAL_COMPLIANCE,
            # Document freshness operations requiring path
            EnumIntelligenceOperationType.ANALYZE_DOCUMENT_FRESHNESS,
            EnumIntelligenceOperationType.REFRESH_DOCUMENTS,
            EnumIntelligenceOperationType.GET_DOCUMENT_FRESHNESS,
        )

    def is_read_only(self) -> bool:
        """
        Check if this operation is read-only (no state modification).

        Returns:
            True for operations that only read/analyze without modifying state
        """
        return self not in (
            # Write operations
            EnumIntelligenceOperationType.APPLY_PERFORMANCE_OPTIMIZATION,
            EnumIntelligenceOperationType.REFRESH_DOCUMENTS,
            EnumIntelligenceOperationType.CLEANUP_FRESHNESS_DATA,
            EnumIntelligenceOperationType.CLEAR_PATTERN_CACHE,
            EnumIntelligenceOperationType.BATCH_INDEX_DOCUMENTS,
            EnumIntelligenceOperationType.OPTIMIZE_VECTOR_INDEX,
            EnumIntelligenceOperationType.TRACK_PATTERN_LINEAGE,
            EnumIntelligenceOperationType.INGEST_PATTERNS,
            EnumIntelligenceOperationType.RECORD_SUCCESS_PATTERN,
        )


__all__ = [
    "EnumIntelligenceOperationType",
]
