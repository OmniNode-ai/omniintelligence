"""Intelligence operation type enum for routing requests to intelligence services."""

from enum import Enum


class EnumIntelligenceOperationType(str, Enum):
    """Intelligence operation types for routing to backend intelligence services.

    This enum provides operation types that route to intelligence services
    including quality assessment, performance analysis, pattern learning,
    and vector operations.

    Categories:
        - Quality Assessment: Code and document quality analysis
        - Performance: Baseline establishment, optimization, trends
        - Document Freshness: Freshness analysis and refresh operations
        - Pattern Learning: Pattern matching, analytics, traceability
        - Vector Operations: Semantic search and indexing
        - Autonomous Learning: Pattern ingestion and prediction
    """

    # Quality Assessment Operations
    ASSESS_CODE_QUALITY = "assess_code_quality"
    ANALYZE_DOCUMENT_QUALITY = "analyze_document_quality"
    GET_QUALITY_PATTERNS = "get_quality_patterns"
    CHECK_ARCHITECTURAL_COMPLIANCE = "check_architectural_compliance"

    # Performance Operations
    ESTABLISH_PERFORMANCE_BASELINE = "establish_performance_baseline"
    IDENTIFY_OPTIMIZATION_OPPORTUNITIES = "identify_optimization_opportunities"
    APPLY_PERFORMANCE_OPTIMIZATION = "apply_performance_optimization"
    GET_OPTIMIZATION_REPORT = "get_optimization_report"
    MONITOR_PERFORMANCE_TRENDS = "monitor_performance_trends"

    # Document Freshness Operations
    ANALYZE_DOCUMENT_FRESHNESS = "analyze_document_freshness"
    GET_STALE_DOCUMENTS = "get_stale_documents"
    REFRESH_DOCUMENTS = "refresh_documents"
    GET_FRESHNESS_STATS = "get_freshness_stats"
    GET_DOCUMENT_FRESHNESS = "get_document_freshness"
    CLEANUP_FRESHNESS_DATA = "cleanup_freshness_data"

    # Pattern Learning Operations
    PATTERN_MATCH = "pattern_match"
    HYBRID_SCORE = "hybrid_score"
    SEMANTIC_ANALYZE = "semantic_analyze"
    GET_PATTERN_METRICS = "get_pattern_metrics"
    GET_CACHE_STATS = "get_cache_stats"
    CLEAR_PATTERN_CACHE = "clear_pattern_cache"
    GET_PATTERN_HEALTH = "get_pattern_health"

    # Vector Operations
    ADVANCED_VECTOR_SEARCH = "advanced_vector_search"
    QUALITY_WEIGHTED_SEARCH = "quality_weighted_search"
    BATCH_INDEX_DOCUMENTS = "batch_index_documents"
    GET_VECTOR_STATS = "get_vector_stats"
    OPTIMIZE_VECTOR_INDEX = "optimize_vector_index"

    # Pattern Traceability Operations
    TRACK_PATTERN_LINEAGE = "track_pattern_lineage"
    GET_PATTERN_LINEAGE = "get_pattern_lineage"
    GET_EXECUTION_LOGS = "get_execution_logs"
    GET_EXECUTION_SUMMARY = "get_execution_summary"

    # Autonomous Learning Operations
    INGEST_PATTERNS = "ingest_patterns"
    RECORD_SUCCESS_PATTERN = "record_success_pattern"
    PREDICT_AGENT = "predict_agent"
    PREDICT_EXECUTION_TIME = "predict_execution_time"
    CALCULATE_SAFETY_SCORE = "calculate_safety_score"
    GET_AUTONOMOUS_STATS = "get_autonomous_stats"
    GET_AUTONOMOUS_HEALTH = "get_autonomous_health"


__all__ = ["EnumIntelligenceOperationType"]
