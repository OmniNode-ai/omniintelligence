"""
Pydantic models for Analytics API
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# Request Models


class TraceFilter(BaseModel):
    """Filter parameters for trace queries"""

    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    status: Optional[str] = Field(
        default=None, description="completed, in_progress, failed"
    )
    success: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    session_id: Optional[UUID] = None


class PatternFilter(BaseModel):
    """Filter parameters for pattern queries"""

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    min_success_rate: Optional[float] = Field(default=None, ge=0, le=1)
    min_usage_count: Optional[int] = Field(default=None, ge=1)
    domain: Optional[str] = None


# Response Models


class ExecutionTraceResponse(BaseModel):
    """Single execution trace response"""

    id: UUID
    correlation_id: UUID
    session_id: UUID
    prompt_text: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    status: str
    success: Optional[bool]
    agent_selected: Optional[str]
    routing_confidence: Optional[float]
    hook_count: int
    endpoint_count: int
    error_type: Optional[str]


class TraceListResponse(BaseModel):
    """Paginated list of traces"""

    traces: List[ExecutionTraceResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class HookExecutionDetail(BaseModel):
    """Hook execution details"""

    hook_type: str
    hook_name: str
    duration_ms: int
    order: int
    rag_query_performed: bool
    quality_check_performed: bool
    error_message: Optional[str]


class EndpointCallDetail(BaseModel):
    """Endpoint call details"""

    service: str
    endpoint_url: str
    method: str
    status_code: int
    duration_ms: int
    rag_query: Optional[str]
    quality_score: Optional[float]


class TraceDetailResponse(BaseModel):
    """Detailed trace information"""

    trace: ExecutionTraceResponse
    agent_routing: Dict[str, Any]
    hooks: List[HookExecutionDetail]
    endpoints: List[EndpointCallDetail]


class SuccessPatternResponse(BaseModel):
    """Success pattern response"""

    id: UUID
    pattern_hash: str
    intent_classification: Optional[str]
    keywords: List[str]
    agent_sequence: List[str]
    success_count: int
    failure_count: int
    total_usage_count: int
    success_rate: float
    avg_duration_ms: int
    confidence_score: float
    last_used_at: Optional[datetime]


class PatternListResponse(BaseModel):
    """Paginated list of patterns"""

    patterns: List[SuccessPatternResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class PatternUsageStats(BaseModel):
    """Pattern usage statistics"""

    pattern_id: UUID
    usage_over_time: List[Dict[str, Any]]  # [{date, count, success_rate}]
    total_usage: int
    success_rate: float
    avg_duration_ms: int
    recent_trend: str  # increasing, stable, decreasing


class AgentEffectivenessResponse(BaseModel):
    """Agent effectiveness metrics"""

    agent_name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate_pct: float
    avg_duration_ms: int
    p95_duration_ms: int
    avg_routing_confidence: float
    patterns_used: int
    last_used_at: datetime


class AgentEffectivenessListResponse(BaseModel):
    """List of agent effectiveness metrics"""

    agents: List[AgentEffectivenessResponse]
    total_agents: int


class AgentChainPattern(BaseModel):
    """Agent chaining pattern"""

    chain_pattern: List[str]
    occurrence_count: int
    avg_success_rate: float
    avg_total_duration_ms: int
    common_triggers: List[str]
    example_trace_ids: List[UUID]


class AgentChainingResponse(BaseModel):
    """Agent chaining patterns response"""

    patterns: List[AgentChainPattern]
    total_patterns: int


class ErrorPattern(BaseModel):
    """Error pattern response"""

    error_type: str
    error_category: str
    severity: str
    error_count: int
    last_occurrence_at: datetime
    affected_agents: List[str]
    resolution_pattern: Optional[Dict[str, Any]]
    resolution_success_rate: Optional[float]
    prevention_strategies: Optional[Dict[str, Any]]
    occurrences_24h: int
    occurrences_7d: int


class ErrorAnalysisResponse(BaseModel):
    """Error analysis response"""

    errors: List[ErrorPattern]
    total_error_types: int
    recent_errors_24h: int


class DashboardSummaryResponse(BaseModel):
    """Dashboard summary metrics"""

    total_traces: int
    completed_traces: int
    successful_traces: int
    overall_success_rate: float
    total_patterns: int
    high_quality_patterns: int
    avg_pattern_success_rate: float
    active_agents: int
    most_used_agent: str
    errors_24h: int
    unique_error_types: int
    median_duration_ms: int
    p95_duration_ms: int
