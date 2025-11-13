"""
Mock data generators for Analytics API
Generates realistic test data until database integration is complete
"""

import random
from datetime import timedelta
from typing import List
from uuid import uuid4

from faker import Faker
from src.api.analytics.models import (
    AgentChainPattern,
    AgentEffectivenessResponse,
    DashboardSummaryResponse,
    EndpointCallDetail,
    ErrorPattern,
    ExecutionTraceResponse,
    HookExecutionDetail,
    SuccessPatternResponse,
)

fake = Faker()

# Known agents from agent registry
AGENTS = [
    "agent-workflow-coordinator",
    "agent-code-quality-analyzer",
    "agent-performance",
    "agent-debug-intelligence",
    "agent-testing",
    "agent-api-architect",
    "agent-ticket-manager",
    "agent-pr-workflow",
    "agent-devops-infrastructure",
    "agent-documentation-architect",
    "agent-rag-query",
]

HOOK_TYPES = [
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "SessionStart",
    "SessionEnd",
]

SERVICES = [
    "RAG",
    "quality_assessment",
    "performance_monitoring",
    "enhanced_search",
]

ERROR_TYPES = [
    "ConnectionError",
    "TimeoutError",
    "ValidationError",
    "NotFoundError",
    "RateLimitError",
]


def generate_execution_trace(
    status: str = None, success: bool = None, agent: str = None, days_ago: int = 0
) -> ExecutionTraceResponse:
    """Generate a single execution trace"""
    trace_id = uuid4()
    correlation_id = uuid4()
    session_id = uuid4()

    status = status or random.choice(
        ["completed", "completed", "completed", "in_progress", "failed"]
    )

    if status == "completed":
        success = success if success is not None else random.random() > 0.2
        started_at = fake.date_time_between(
            start_date=f"-{days_ago+1}d", end_date=f"-{days_ago}d"
        )
        duration_ms = random.randint(200, 5000)
        completed_at = started_at + timedelta(milliseconds=duration_ms)
    elif status == "failed":
        success = False
        started_at = fake.date_time_between(
            start_date=f"-{days_ago+1}d", end_date=f"-{days_ago}d"
        )
        duration_ms = random.randint(100, 2000)
        completed_at = started_at + timedelta(milliseconds=duration_ms)
    else:  # in_progress
        success = None
        started_at = fake.date_time_between(start_date="-1h")
        duration_ms = None
        completed_at = None

    agent_selected = agent or random.choice(AGENTS)
    routing_confidence = round(random.uniform(0.7, 0.99), 4)

    return ExecutionTraceResponse(
        id=trace_id,
        correlation_id=correlation_id,
        session_id=session_id,
        prompt_text=fake.sentence(nb_words=10),
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        status=status,
        success=success,
        agent_selected=agent_selected,
        routing_confidence=routing_confidence,
        hook_count=random.randint(1, 5),
        endpoint_count=random.randint(0, 3),
        error_type=random.choice(ERROR_TYPES) if status == "failed" else None,
    )


def generate_hook_execution(
    hook_type: str = None, order: int = 1
) -> HookExecutionDetail:
    """Generate a hook execution detail"""
    hook_type = hook_type or random.choice(HOOK_TYPES)

    return HookExecutionDetail(
        hook_type=hook_type,
        hook_name=f"{hook_type.lower()}_hook",
        duration_ms=random.randint(10, 500),
        order=order,
        rag_query_performed=random.random() > 0.6,
        quality_check_performed=random.random() > 0.7,
        error_message=None if random.random() > 0.1 else fake.sentence(),
    )


def generate_endpoint_call(service: str = None) -> EndpointCallDetail:
    """Generate an endpoint call detail"""
    service = service or random.choice(SERVICES)

    endpoint_map = {
        "RAG": "/api/rag/query",
        "quality_assessment": "/api/intelligence/quality",
        "performance_monitoring": "/api/intelligence/performance",
        "enhanced_search": "/api/search/enhanced",
    }

    return EndpointCallDetail(
        service=service,
        endpoint_url=endpoint_map.get(service, "/api/unknown"),
        method="POST",
        status_code=random.choice([200, 200, 200, 200, 500, 429]),
        duration_ms=random.randint(50, 1500),
        rag_query=fake.sentence() if service == "RAG" else None,
        quality_score=(
            round(random.uniform(0.6, 0.95), 4)
            if service == "quality_assessment"
            else None
        ),
    )


def generate_success_pattern() -> SuccessPatternResponse:
    """Generate a success pattern"""
    pattern_id = uuid4()
    agent_sequence = random.sample(AGENTS, k=random.randint(1, 3))
    success_count = random.randint(10, 200)
    failure_count = random.randint(0, 20)
    total_usage = success_count + failure_count
    success_rate = round(success_count / total_usage, 4)

    return SuccessPatternResponse(
        id=pattern_id,
        pattern_hash=fake.sha256()[:16],
        intent_classification=random.choice(
            [
                "code_generation",
                "debugging",
                "refactoring",
                "documentation",
                "testing",
            ]
        ),
        keywords=fake.words(nb=random.randint(3, 7)),
        agent_sequence=agent_sequence,
        success_count=success_count,
        failure_count=failure_count,
        total_usage_count=total_usage,
        success_rate=success_rate,
        avg_duration_ms=random.randint(500, 4000),
        confidence_score=round(random.uniform(0.75, 0.99), 4),
        last_used_at=(
            fake.date_time_between(start_date="-7d") if random.random() > 0.2 else None
        ),
    )


def generate_agent_effectiveness(agent_name: str = None) -> AgentEffectivenessResponse:
    """Generate agent effectiveness metrics"""
    agent_name = agent_name or random.choice(AGENTS)
    total_executions = random.randint(50, 500)
    success_rate_pct = round(random.uniform(70, 98), 2)
    successful = int(total_executions * success_rate_pct / 100)
    failed = total_executions - successful

    return AgentEffectivenessResponse(
        agent_name=agent_name,
        total_executions=total_executions,
        successful_executions=successful,
        failed_executions=failed,
        success_rate_pct=success_rate_pct,
        avg_duration_ms=random.randint(800, 4000),
        p95_duration_ms=random.randint(3000, 8000),
        avg_routing_confidence=round(random.uniform(0.75, 0.95), 4),
        patterns_used=random.randint(5, 25),
        last_used_at=fake.date_time_between(start_date="-7d"),
    )


def generate_agent_chain_pattern() -> AgentChainPattern:
    """Generate agent chaining pattern"""
    chain_length = random.randint(2, 4)
    chain_pattern = random.sample(AGENTS, k=chain_length)

    return AgentChainPattern(
        chain_pattern=chain_pattern,
        occurrence_count=random.randint(10, 100),
        avg_success_rate=round(random.uniform(0.7, 0.95), 4),
        avg_total_duration_ms=random.randint(2000, 10000),
        common_triggers=fake.words(nb=3),
        example_trace_ids=[uuid4() for _ in range(3)],
    )


def generate_error_pattern(error_type: str = None) -> ErrorPattern:
    """Generate error pattern"""
    error_type = error_type or random.choice(ERROR_TYPES)
    error_count = random.randint(5, 50)
    occurrences_24h = random.randint(0, 5)
    occurrences_7d = random.randint(occurrences_24h, 15)

    return ErrorPattern(
        error_type=error_type,
        error_category=random.choice(
            ["network", "validation", "system", "integration"]
        ),
        severity=random.choice(["critical", "high", "medium", "low"]),
        error_count=error_count,
        last_occurrence_at=fake.date_time_between(start_date="-24h"),
        affected_agents=random.sample(AGENTS, k=random.randint(1, 3)),
        resolution_pattern=(
            {"steps": ["step1", "step2"]} if random.random() > 0.3 else None
        ),
        resolution_success_rate=(
            round(random.uniform(0.5, 0.9), 4) if random.random() > 0.3 else None
        ),
        prevention_strategies=(
            {"strategy": "retry_with_backoff"} if random.random() > 0.4 else None
        ),
        occurrences_24h=occurrences_24h,
        occurrences_7d=occurrences_7d,
    )


def generate_dashboard_summary() -> DashboardSummaryResponse:
    """Generate dashboard summary"""
    total_traces = random.randint(500, 2000)
    completed_traces = int(total_traces * 0.95)
    successful_traces = int(completed_traces * 0.88)

    return DashboardSummaryResponse(
        total_traces=total_traces,
        completed_traces=completed_traces,
        successful_traces=successful_traces,
        overall_success_rate=round(successful_traces / completed_traces * 100, 2),
        total_patterns=random.randint(50, 200),
        high_quality_patterns=random.randint(20, 80),
        avg_pattern_success_rate=round(random.uniform(0.75, 0.92), 4),
        active_agents=len(AGENTS),
        most_used_agent=random.choice(AGENTS),
        errors_24h=random.randint(2, 15),
        unique_error_types=len(ERROR_TYPES),
        median_duration_ms=random.randint(1200, 2500),
        p95_duration_ms=random.randint(4000, 7000),
    )


# Cache for consistent mock data across requests
_MOCK_TRACES: List[ExecutionTraceResponse] = []
_MOCK_PATTERNS: List[SuccessPatternResponse] = []
_MOCK_AGENTS: List[AgentEffectivenessResponse] = []
_MOCK_CHAINS: List[AgentChainPattern] = []
_MOCK_ERRORS: List[ErrorPattern] = []


def initialize_mock_data():
    """Initialize mock data cache"""
    global _MOCK_TRACES, _MOCK_PATTERNS, _MOCK_AGENTS, _MOCK_CHAINS, _MOCK_ERRORS

    # Generate 200 traces over last 30 days
    _MOCK_TRACES = [
        generate_execution_trace(days_ago=random.randint(0, 30)) for _ in range(200)
    ]

    # Generate 50 patterns
    _MOCK_PATTERNS = [generate_success_pattern() for _ in range(50)]

    # Generate effectiveness for all agents
    _MOCK_AGENTS = [generate_agent_effectiveness(agent) for agent in AGENTS]

    # Generate 20 chaining patterns
    _MOCK_CHAINS = [generate_agent_chain_pattern() for _ in range(20)]

    # Generate error patterns for all error types
    _MOCK_ERRORS = [generate_error_pattern(error) for error in ERROR_TYPES]


def get_mock_traces(
    limit: int = 50, offset: int = 0, status: str = None, success: bool = None
) -> List[ExecutionTraceResponse]:
    """Get filtered mock traces"""
    if not _MOCK_TRACES:
        initialize_mock_data()

    filtered = _MOCK_TRACES

    if status:
        filtered = [t for t in filtered if t.status == status]

    if success is not None:
        filtered = [t for t in filtered if t.success == success]

    # Sort by started_at desc
    filtered = sorted(filtered, key=lambda x: x.started_at, reverse=True)

    return filtered[offset : offset + limit]


def get_mock_patterns(
    limit: int = 20,
    offset: int = 0,
    min_success_rate: float = None,
    min_usage_count: int = None,
) -> List[SuccessPatternResponse]:
    """Get filtered mock patterns"""
    if not _MOCK_PATTERNS:
        initialize_mock_data()

    filtered = _MOCK_PATTERNS

    if min_success_rate:
        filtered = [p for p in filtered if p.success_rate >= min_success_rate]

    if min_usage_count:
        filtered = [p for p in filtered if p.total_usage_count >= min_usage_count]

    # Sort by success rate desc
    filtered = sorted(
        filtered, key=lambda x: (x.success_rate, x.total_usage_count), reverse=True
    )

    return filtered[offset : offset + limit]


# Initialize on module load
initialize_mock_data()
