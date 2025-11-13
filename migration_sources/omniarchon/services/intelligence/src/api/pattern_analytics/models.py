"""
Pydantic models for Pattern Analytics API

Response models for pattern success rate tracking and analytics reporting.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# NOTE: correlation_id support enabled for tracing
class NodeType(str, Enum):
    """ONEX node type enumeration"""

    EFFECT = "effect"
    COMPUTE = "compute"
    REDUCER = "reducer"
    ORCHESTRATOR = "orchestrator"


# Type alias for pattern types
PatternType = Literal["architectural", "quality", "performance", "security", "other"]

# Type alias for sentiment values
SentimentType = Literal["positive", "neutral", "negative"]


class DateRange(BaseModel):
    """Structured date range model"""

    earliest: datetime = Field(..., description="Earliest date in range")
    latest: datetime = Field(..., description="Latest date in range")


class PatternSuccessRate(BaseModel):
    """Success rate for a single pattern"""

    pattern_id: str = Field(..., description="Pattern identifier")
    pattern_name: str = Field(..., description="Pattern name for display")
    pattern_type: PatternType = Field(
        ..., description="Type of pattern (architectural, quality, performance, etc.)"
    )
    success_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Success rate (0.0-1.0)"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score based on sample size"
    )
    sample_size: int = Field(..., ge=0, description="Number of feedback samples")
    avg_quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average quality score"
    )
    common_issues: List[str] = Field(
        default_factory=list, description="Common issues encountered"
    )


class PatternSuccessRateSummary(BaseModel):
    """Summary statistics for pattern success rates"""

    total_patterns: int = Field(
        ..., ge=0, description="Total number of patterns analyzed"
    )
    avg_success_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Average success rate across all patterns"
    )
    high_confidence_patterns: int = Field(
        ..., ge=0, description="Number of high confidence patterns (confidence >= 0.8)"
    )


class PatternSuccessRatesResponse(BaseModel):
    """Response model for GET /api/pattern-analytics/success-rates"""

    patterns: List[PatternSuccessRate] = Field(
        ..., description="List of pattern success rates"
    )
    summary: PatternSuccessRateSummary = Field(..., description="Summary statistics")


class TopPattern(BaseModel):
    """Top performing pattern"""

    pattern_id: str = Field(..., description="Pattern identifier")
    pattern_name: str = Field(..., description="Pattern name for display")
    pattern_type: PatternType = Field(..., description="Pattern type")
    node_type: Optional[NodeType] = Field(
        None, description="ONEX node type (Effect, Compute, Reducer, Orchestrator)"
    )
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    sample_size: int = Field(..., ge=0, description="Number of samples")
    avg_quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average quality score"
    )
    rank: int = Field(..., ge=1, description="Ranking position")


class TopPatternsResponse(BaseModel):
    """Response model for GET /api/pattern-analytics/top-patterns"""

    top_patterns: List[TopPattern] = Field(
        ..., description="List of top performing patterns"
    )
    total_patterns: int = Field(..., description="Total number of patterns in result")
    filter_criteria: Dict[str, Any] = Field(
        default_factory=dict, description="Applied filter criteria"
    )


class EmergingPattern(BaseModel):
    """Recently emerging pattern"""

    pattern_id: str = Field(..., description="Pattern identifier")
    pattern_name: str = Field(..., description="Pattern name")
    pattern_type: PatternType = Field(..., description="Pattern type")
    frequency: int = Field(..., ge=0, description="Usage frequency in time window")
    first_seen_at: datetime = Field(..., description="First occurrence timestamp")
    last_seen_at: datetime = Field(..., description="Most recent occurrence timestamp")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate")
    growth_rate: float = Field(
        ..., description="Usage growth rate (can be negative for declining patterns)"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class EmergingPatternsResponse(BaseModel):
    """Response model for GET /api/pattern-analytics/emerging-patterns"""

    emerging_patterns: List[EmergingPattern] = Field(
        ..., description="List of emerging patterns"
    )
    total_emerging: int = Field(
        ..., description="Total number of emerging patterns found"
    )
    time_window_hours: int = Field(..., description="Time window analyzed (hours)")
    filter_criteria: Dict[str, Any] = Field(
        default_factory=dict, description="Applied filter criteria"
    )


class PatternFeedbackHistoryItem(BaseModel):
    """Single feedback item in pattern history"""

    feedback_id: UUID = Field(..., description="Unique feedback identifier")
    execution_id: Optional[str] = Field(None, description="Execution ID if available")
    sentiment: SentimentType = Field(
        ..., description="Feedback sentiment (positive, neutral, negative)"
    )
    success: Optional[bool] = Field(None, description="Whether execution succeeded")
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Quality score (0.0-1.0)"
    )
    performance_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Performance score (0.0-1.0)"
    )
    execution_time_ms: Optional[float] = Field(
        None, ge=0.0, description="Execution time in milliseconds"
    )
    issues: List[str] = Field(default_factory=list, description="Issues encountered")
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Execution context"
    )
    created_at: datetime = Field(..., description="Feedback timestamp")


class PatternHistorySummary(BaseModel):
    """Summary of pattern feedback history"""

    total_feedback: int = Field(..., ge=0, description="Total number of feedback items")
    success_count: int = Field(..., ge=0, description="Number of successful executions")
    failure_count: int = Field(..., ge=0, description="Number of failed executions")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Overall success rate")
    avg_quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average quality score"
    )
    avg_execution_time_ms: float = Field(
        ..., ge=0.0, description="Average execution time in milliseconds"
    )
    date_range: Optional[DateRange] = Field(
        None, description="Date range of feedback (None if no feedback)"
    )


class PatternHistoryResponse(BaseModel):
    """Response model for GET /api/pattern-analytics/pattern/{pattern_id}/history"""

    pattern_id: str = Field(..., description="Pattern identifier")
    pattern_name: str = Field(..., description="Pattern name")
    feedback_history: List[PatternFeedbackHistoryItem] = Field(
        ..., description="List of feedback items"
    )
    summary: PatternHistorySummary = Field(..., description="Summary statistics")


# ============================================================================
# New Dashboard Endpoints Models (7 endpoints)
# ============================================================================


class PatternStats(BaseModel):
    """Overall pattern statistics"""

    total_patterns: int = Field(..., ge=0, description="Total number of patterns")
    total_feedback: int = Field(..., ge=0, description="Total feedback entries")
    avg_success_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Average success rate across all patterns"
    )
    avg_quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average quality score"
    )
    patterns_by_type: Dict[str, int] = Field(
        default_factory=dict, description="Count of patterns by type"
    )
    recent_activity_count: int = Field(
        ..., ge=0, description="Activity count in last 24 hours"
    )
    high_confidence_patterns: int = Field(
        ..., ge=0, description="Patterns with confidence >= 0.8"
    )


class PatternStatsResponse(BaseModel):
    """Response model for GET /api/patterns/stats"""

    stats: PatternStats = Field(..., description="Pattern statistics")
    generated_at: datetime = Field(
        ..., description="Timestamp when stats were generated"
    )


class DiscoveryDataPoint(BaseModel):
    """Single discovery rate data point"""

    timestamp: datetime = Field(..., description="Time bucket timestamp")
    count: int = Field(..., ge=0, description="Number of patterns discovered")
    pattern_types: Dict[str, int] = Field(
        default_factory=dict, description="Breakdown by pattern type"
    )


class DiscoveryRateResponse(BaseModel):
    """Response model for GET /api/patterns/discovery-rate"""

    data_points: List[DiscoveryDataPoint] = Field(
        ..., description="Time-series discovery data"
    )
    time_range: str = Field(..., description="Time range analyzed (e.g., '7d', '30d')")
    granularity: str = Field(
        ..., description="Data granularity (e.g., 'hour', 'day', 'week')"
    )
    total_discovered: int = Field(
        ..., ge=0, description="Total patterns discovered in time range"
    )


class QualityTrendDataPoint(BaseModel):
    """Quality trend data point"""

    timestamp: datetime = Field(..., description="Measurement timestamp")
    avg_quality: float = Field(..., ge=0.0, le=1.0, description="Average quality score")
    pattern_count: int = Field(..., ge=0, description="Number of patterns measured")
    min_quality: float = Field(..., ge=0.0, le=1.0, description="Minimum quality")
    max_quality: float = Field(..., ge=0.0, le=1.0, description="Maximum quality")


class QualityTrendsResponse(BaseModel):
    """Response model for GET /api/patterns/quality-trends"""

    trends: List[QualityTrendDataPoint] = Field(
        ..., description="Quality trend data over time"
    )
    time_range: str = Field(..., description="Time range analyzed")
    overall_trend: str = Field(
        ..., description="Overall trend direction (increasing, decreasing, stable)"
    )
    trend_velocity: float = Field(..., description="Rate of change in quality scores")


class TopPerformingPattern(BaseModel):
    """Top performing pattern summary"""

    pattern_id: str = Field(..., description="Pattern identifier")
    pattern_name: str = Field(..., description="Pattern display name")
    pattern_type: PatternType = Field(..., description="Pattern type")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate")
    usage_count: int = Field(..., ge=0, description="Total usage count")
    avg_quality: float = Field(..., ge=0.0, le=1.0, description="Average quality score")
    performance_score: float = Field(
        ..., ge=0.0, description="Weighted performance score"
    )
    rank: int = Field(..., ge=1, description="Ranking position")


class TopPerformingResponse(BaseModel):
    """Response model for GET /api/patterns/top-performing"""

    patterns: List[TopPerformingPattern] = Field(
        ..., description="Top performing patterns"
    )
    total_count: int = Field(..., ge=0, description="Total patterns analyzed")
    criteria: str = Field(
        ..., description="Ranking criteria (e.g., 'success_rate', 'usage', 'quality')"
    )


class PatternRelationship(BaseModel):
    """Pattern relationship for network graph"""

    source_pattern_id: str = Field(..., description="Source pattern ID")
    target_pattern_id: str = Field(..., description="Target pattern ID")
    relationship_type: str = Field(
        ...,
        description="Relationship type (e.g., 'similar', 'depends_on', 'used_with')",
    )
    strength: float = Field(..., ge=0.0, le=1.0, description="Relationship strength")
    co_occurrence_count: int = Field(
        ..., ge=0, description="Times patterns used together"
    )


class PatternNode(BaseModel):
    """Pattern node for network graph"""

    pattern_id: str = Field(..., description="Pattern identifier")
    pattern_name: str = Field(..., description="Pattern name")
    pattern_type: PatternType = Field(..., description="Pattern type")
    usage_count: int = Field(..., ge=0, description="Total usage")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate")
    centrality: float = Field(..., ge=0.0, description="Network centrality measure")


class PatternRelationshipsResponse(BaseModel):
    """Response model for GET /api/patterns/relationships"""

    nodes: List[PatternNode] = Field(..., description="Pattern nodes")
    relationships: List[PatternRelationship] = Field(
        ..., description="Pattern relationships"
    )
    total_nodes: int = Field(..., ge=0, description="Total nodes in graph")
    total_edges: int = Field(..., ge=0, description="Total edges in graph")


class PatternSearchResult(BaseModel):
    """Pattern search result"""

    pattern_id: str = Field(..., description="Pattern identifier")
    pattern_name: str = Field(..., description="Pattern name")
    pattern_type: PatternType = Field(..., description="Pattern type")
    description: Optional[str] = Field(None, description="Pattern description")
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Search relevance score"
    )
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate")
    usage_count: int = Field(..., ge=0, description="Usage count")
    tags: List[str] = Field(default_factory=list, description="Pattern tags")


class PatternSearchResponse(BaseModel):
    """Response model for GET /api/patterns/search"""

    results: List[PatternSearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., ge=0, description="Total matching patterns")
    query: str = Field(..., description="Search query")
    search_type: str = Field(
        ..., description="Search type (e.g., 'full_text', 'vector', 'hybrid')"
    )


class InfrastructureComponent(BaseModel):
    """Infrastructure component health"""

    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Status (healthy, degraded, unhealthy)")
    response_time_ms: Optional[float] = Field(
        None, ge=0.0, description="Response time in milliseconds"
    )
    last_check: datetime = Field(..., description="Last health check timestamp")
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional details"
    )


class InfrastructureHealthResponse(BaseModel):
    """Response model for GET /api/patterns/health"""

    overall_status: str = Field(
        ..., description="Overall health status (healthy, degraded, unhealthy)"
    )
    components: List[InfrastructureComponent] = Field(
        ..., description="Individual component health"
    )
    uptime_seconds: float = Field(..., ge=0.0, description="Service uptime")
    total_requests: int = Field(..., ge=0, description="Total requests served")
    avg_response_time_ms: float = Field(
        ..., ge=0.0, description="Average response time"
    )
    checked_at: datetime = Field(..., description="Health check timestamp")


# ============================================================================
# Usage Statistics Models (Section 2.3 - Pattern Usage Tracking)
# ============================================================================


class UsageDataPoint(BaseModel):
    """Single usage data point in time series"""

    timestamp: str = Field(..., description="ISO 8601 timestamp for the time bucket")
    count: int = Field(..., ge=0, description="Number of pattern usages in this bucket")


class PatternUsageData(BaseModel):
    """Usage data for a single pattern"""

    pattern_id: str = Field(..., description="Pattern identifier")
    pattern_name: str = Field(..., description="Pattern display name")
    usage_data: List[UsageDataPoint] = Field(
        ..., description="Time-series usage data points"
    )
    total_usage: int = Field(..., ge=0, description="Total usage count in time range")


class UsageStatsResponse(BaseModel):
    """Response model for GET /api/pattern-analytics/usage-stats"""

    patterns: List[PatternUsageData] = Field(
        ..., description="Usage statistics per pattern"
    )
    time_range: str = Field(
        ..., description="Time range analyzed (e.g., '1d', '7d', '30d', '90d')"
    )
    granularity: str = Field(
        ..., description="Data granularity (e.g., 'hour', 'day', 'week')"
    )
    total_patterns: int = Field(
        ..., ge=0, description="Number of patterns with usage in time range"
    )
