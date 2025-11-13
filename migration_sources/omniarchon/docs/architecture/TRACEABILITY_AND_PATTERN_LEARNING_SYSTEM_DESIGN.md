# Traceability and Pattern Learning System - Complete Design

**Version**: 1.0.0
**Date**: 2025-10-01
**Status**: Design Phase
**Author**: Architecture Team

---

## Executive Summary

This document presents a comprehensive design for a **unified traceability and pattern learning system** that tracks every interaction from user prompt through agent routing, hook executions, and Archon intelligence endpoint calls, enabling the system to learn from successful patterns and automatically improve execution paths over time.

### Key Objectives

1. **Full Traceability**: Track complete execution flow from user prompt → agent → hooks → endpoints → outcome
2. **Pattern Learning**: Identify successful execution patterns and automatically reuse them for similar contexts
3. **Self-Improvement**: System learns from experience and optimizes routing/execution over time
4. **Unified Observability**: Single source of truth for all execution traces and analytics

### Success Metrics

- **100% trace coverage**: Every interaction captured with correlation ID
- **<5ms trace overhead**: Minimal performance impact from tracing
- **>80% pattern match rate**: Successfully identify similar prompts for learned patterns
- **>90% pattern success rate**: Learned patterns should succeed when replayed
- **<100ms pattern lookup**: Fast retrieval of learned patterns

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Traceability System Design](#2-traceability-system-design)
3. [Pattern Learning System Design](#3-pattern-learning-system-design)
4. [Analytics Schema Design](#4-analytics-schema-design)
5. [Integration Strategy](#5-integration-strategy)
6. [Implementation Plan](#6-implementation-plan)
7. [Performance Considerations](#7-performance-considerations)
8. [Security & Privacy](#8-security--privacy)

---

## 1. Architecture Overview

### 1.1 System Context

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Traceability & Learning System                    │
├─────────────────┬─────────────────┬─────────────────┬───────────────┤
│  Data Capture   │   Processing    │     Learning    │    Storage    │
├─────────────────┼─────────────────┼─────────────────┼───────────────┤
│ • Hook Events   │ • Trace Assembly│ • Pattern Match │ • Supabase    │
│ • Router Events │ • Correlation   │ • Success Score │ • PostgreSQL  │
│ • Endpoint Logs │ • Context Enrich│ • Similarity    │ • Memgraph    │
│ • Agent Events  │ • Timeline Build│ • Confidence    │ • Qdrant      │
└─────────────────┴─────────────────┴─────────────────┴───────────────┘

Execution Flow with Tracing:
┌──────────────────────────────────────────────────────────────────────┐
│ 1. User Prompt                                                       │
│    ↓ [correlation_id generated]                                      │
│    ├─→ UserPromptSubmit Hook                                        │
│    │   • Captures: prompt text, timestamp, session_id               │
│    │   • Generates: correlation_id (UUID)                           │
│    │   • Stores: execution_traces table                             │
│    ↓                                                                 │
│ 2. Agent Routing (EnhancedAgentRouter)                              │
│    ↓ [correlation_id propagated]                                     │
│    ├─→ Route Decision Logged                                        │
│    │   • Captures: selected agent, confidence scores, alternatives  │
│    │   • Links: correlation_id                                      │
│    │   • Stores: agent_routing_decisions table                      │
│    ↓                                                                 │
│ 3. Hook Executions (PreToolUse, PostToolUse, etc.)                  │
│    ↓ [correlation_id in context]                                     │
│    ├─→ Each Hook Logs Execution                                     │
│    │   • Captures: hook type, tool, duration, intelligence gathered│
│    │   • Links: correlation_id, parent_trace_id                     │
│    │   • Stores: hook_executions table                              │
│    ↓                                                                 │
│ 4. Archon Intelligence Endpoints                                     │
│    ↓ [correlation_id in request headers]                             │
│    ├─→ Endpoint Call Logged                                         │
│    │   • Captures: endpoint, request, response, duration, status    │
│    │   • Links: correlation_id, hook_execution_id                   │
│    │   • Stores: endpoint_calls table                               │
│    ↓                                                                 │
│ 5. Execution Outcome                                                 │
│    ↓ [success/failure captured]                                      │
│    └─→ Pattern Learning Triggered                                    │
│        • Analyzes: entire trace chain                                │
│        • Identifies: successful patterns                             │
│        • Updates: success_patterns table                             │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Components

#### A. Trace Capture Layer
- **Location**: Claude Code hooks, agent router, Archon endpoints
- **Responsibility**: Capture execution events with correlation IDs
- **Technology**: Python async logging, structured JSON

#### B. Trace Assembly Service
- **Location**: Archon Intelligence Service
- **Responsibility**: Assemble fragmented traces into complete execution chains
- **Technology**: PostgreSQL queries, async aggregation

#### C. Pattern Learning Engine
- **Location**: Archon Intelligence Service (new module)
- **Responsibility**: Identify successful patterns, match similar prompts, recommend patterns
- **Technology**: Vector embeddings (Qdrant), graph analysis (Memgraph), ML scoring

#### D. Pattern Replay System
- **Location**: Enhanced Agent Router + Hook System
- **Responsibility**: Apply learned patterns to new requests
- **Technology**: Cache integration, confidence scoring

---

## 2. Traceability System Design

### 2.1 Correlation ID Propagation

#### Correlation ID Structure
```python
@dataclass
class CorrelationID:
    """
    Universally unique correlation identifier for tracing execution chains.
    """
    # Core identifier
    id: UUID  # Generated at UserPromptSubmit hook

    # Context identifiers
    session_id: UUID  # Claude Code session ID
    user_id: str | None  # Optional user identifier

    # Hierarchical relationships
    parent_id: UUID | None  # For nested executions (subagent calls)
    root_id: UUID  # Always points to original prompt

    # Timestamps
    created_at: datetime

    # Metadata
    source: str  # 'user_prompt', 'agent_delegation', 'hook_trigger', etc.

    def __str__(self) -> str:
        return f"corr-{self.id}"
```

#### Propagation Mechanism

**1. Generation (UserPromptSubmit Hook)**
```python
# ~/.claude/hooks/user-prompt-submit-agent-enhancer.sh
# Generate correlation ID at the very start
CORRELATION_ID=$(uuidgen)
SESSION_ID=$(get_claude_session_id)  # From Claude Code environment

# Store in environment for downstream hooks
export ARCHON_CORRELATION_ID="$CORRELATION_ID"
export ARCHON_SESSION_ID="$SESSION_ID"
export ARCHON_ROOT_ID="$CORRELATION_ID"  # This is the root

# Log initial trace
curl -X POST "${ARCHON_INTELLIGENCE_URL}/api/traces/start" \
    -H "Content-Type: application/json" \
    -H "X-Correlation-ID: ${CORRELATION_ID}" \
    -d "{
        \"correlation_id\": \"${CORRELATION_ID}\",
        \"session_id\": \"${SESSION_ID}\",
        \"source\": \"user_prompt\",
        \"prompt_text\": \"${PROMPT}\",
        \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
    }" &
```

**2. Propagation (All Hooks)**
```python
# All hooks receive correlation ID from environment
CORRELATION_ID="${ARCHON_CORRELATION_ID:-$(uuidgen)}"
ROOT_ID="${ARCHON_ROOT_ID:-${CORRELATION_ID}}"

# For nested executions (e.g., SubagentStop)
PARENT_ID="${ARCHON_PARENT_ID:-${CORRELATION_ID}}"
EXECUTION_ID=$(uuidgen)  # Unique ID for this specific execution

export ARCHON_PARENT_ID="${EXECUTION_ID}"  # For next level

# Log this hook execution
log_hook_execution() {
    curl -X POST "${ARCHON_INTELLIGENCE_URL}/api/traces/hook" \
        -H "Content-Type: application/json" \
        -H "X-Correlation-ID: ${CORRELATION_ID}" \
        -H "X-Root-ID: ${ROOT_ID}" \
        -H "X-Parent-ID: ${PARENT_ID}" \
        -H "X-Execution-ID: ${EXECUTION_ID}" \
        -d "{
            \"correlation_id\": \"${CORRELATION_ID}\",
            \"root_id\": \"${ROOT_ID}\",
            \"parent_id\": \"${PARENT_ID}\",
            \"execution_id\": \"${EXECUTION_ID}\",
            \"hook_type\": \"${HOOK_TYPE}\",
            \"tool_name\": \"${TOOL_NAME}\",
            \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
        }" &
}
```

**3. HTTP Header Propagation (Archon Endpoints)**
```python
# All Archon intelligence endpoint calls include correlation headers
async def call_archon_intelligence(
    endpoint: str,
    data: dict,
    correlation_id: str,
    root_id: str,
    parent_id: str | None = None
) -> dict:
    """Call Archon intelligence endpoint with full correlation context."""
    headers = {
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
        "X-Root-ID": root_id,
        "X-Parent-ID": parent_id or correlation_id,
        "X-Execution-ID": str(uuid.uuid4()),
        "X-Source": "claude-code-hooks"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ARCHON_INTELLIGENCE_URL}{endpoint}",
            json=data,
            headers=headers
        )
        return response.json()
```

**4. Agent Router Integration**
```python
# EnhancedAgentRouter tracks routing decisions
class EnhancedAgentRouter:
    async def route(
        self,
        user_request: str,
        context: dict | None = None,
        correlation_id: str | None = None
    ) -> List[AgentRecommendation]:
        """Route with tracing."""
        correlation_id = correlation_id or str(uuid.uuid4())

        # Log routing decision
        await self._log_routing_decision(
            correlation_id=correlation_id,
            user_request=user_request,
            recommendations=recommendations
        )

        return recommendations

    async def _log_routing_decision(
        self,
        correlation_id: str,
        user_request: str,
        recommendations: List[AgentRecommendation]
    ):
        """Log routing decision to Archon for traceability."""
        await call_archon_intelligence(
            endpoint="/api/traces/routing",
            data={
                "correlation_id": correlation_id,
                "user_request": user_request,
                "selected_agent": recommendations[0].agent_name if recommendations else None,
                "alternatives": [
                    {
                        "agent": rec.agent_name,
                        "confidence": rec.confidence.total
                    }
                    for rec in recommendations[1:5]  # Top 5 alternatives
                ],
                "selection_reason": recommendations[0].reason if recommendations else None
            },
            correlation_id=correlation_id,
            root_id=correlation_id
        )
```

### 2.2 Trace Data Model

#### Execution Trace (Master Record)
```sql
CREATE TABLE execution_traces (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL UNIQUE,  -- Main correlation ID
    root_id UUID NOT NULL,  -- Points to root trace
    parent_id UUID,  -- For nested executions

    -- Session context
    session_id UUID NOT NULL,  -- Claude Code session
    user_id TEXT,  -- Optional user identifier

    -- Source information
    source TEXT NOT NULL,  -- 'user_prompt', 'agent_delegation', etc.
    prompt_text TEXT,  -- Original user prompt (only for root)

    -- Execution metadata
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,  -- Calculated on completion
    status TEXT NOT NULL DEFAULT 'in_progress',  -- 'in_progress', 'success', 'error', 'timeout'

    -- Outcome tracking
    success BOOLEAN,  -- Was execution successful?
    error_message TEXT,  -- Error details if failed
    error_type TEXT,  -- Error category

    -- Context and metadata
    context JSONB,  -- Additional context data
    tags TEXT[],  -- For categorization and filtering

    -- Indexes
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX idx_execution_traces_correlation ON execution_traces(correlation_id);
CREATE INDEX idx_execution_traces_root ON execution_traces(root_id);
CREATE INDEX idx_execution_traces_session ON execution_traces(session_id);
CREATE INDEX idx_execution_traces_status ON execution_traces(status);
CREATE INDEX idx_execution_traces_started_at ON execution_traces(started_at DESC);
CREATE INDEX idx_execution_traces_tags ON execution_traces USING GIN(tags);
```

#### Agent Routing Decisions
```sql
CREATE TABLE agent_routing_decisions (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL REFERENCES execution_traces(correlation_id),

    -- Routing details
    user_request TEXT NOT NULL,
    selected_agent TEXT,  -- Agent that was selected
    selection_reason TEXT,  -- Why this agent was selected

    -- Confidence scoring
    confidence_total FLOAT NOT NULL,
    confidence_trigger FLOAT NOT NULL,
    confidence_context FLOAT NOT NULL,
    confidence_capability FLOAT NOT NULL,
    confidence_historical FLOAT NOT NULL,

    -- Alternative agents considered
    alternatives JSONB,  -- Array of alternative agents with scores

    -- Routing metadata
    routing_strategy TEXT,  -- 'explicit', 'fuzzy_match', 'learned_pattern', etc.
    pattern_id UUID,  -- If using learned pattern, link to it
    cache_hit BOOLEAN DEFAULT FALSE,  -- Was result from cache?

    -- Performance
    routing_duration_ms INTEGER NOT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_routing_correlation ON agent_routing_decisions(correlation_id);
CREATE INDEX idx_agent_routing_selected_agent ON agent_routing_decisions(selected_agent);
CREATE INDEX idx_agent_routing_pattern ON agent_routing_decisions(pattern_id) WHERE pattern_id IS NOT NULL;
```

#### Hook Executions
```sql
CREATE TABLE hook_executions (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL,  -- Unique ID for this hook execution
    correlation_id UUID NOT NULL REFERENCES execution_traces(correlation_id),
    parent_id UUID,  -- Parent execution (for nested hooks)

    -- Hook details
    hook_type TEXT NOT NULL,  -- 'UserPromptSubmit', 'PreToolUse', 'PostToolUse', etc.
    tool_name TEXT,  -- Tool being intercepted (e.g., 'Task', 'Write')
    hook_script TEXT,  -- Which hook script executed

    -- Execution details
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status TEXT NOT NULL DEFAULT 'in_progress',  -- 'success', 'error', 'timeout'

    -- Intelligence gathered
    intelligence_functions_executed TEXT[],  -- e.g., ['IC-001', 'IC-002']
    rag_queries_executed JSONB,  -- Array of RAG query details
    quality_gates_validated TEXT[],  -- e.g., ['SV-001', 'QC-001']

    -- Outcomes
    success BOOLEAN,
    error_message TEXT,
    modifications_made JSONB,  -- Any modifications hook made to tool call

    -- Metadata
    context JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_hook_executions_correlation ON hook_executions(correlation_id);
CREATE INDEX idx_hook_executions_execution ON hook_executions(execution_id);
CREATE INDEX idx_hook_executions_parent ON hook_executions(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX idx_hook_executions_hook_type ON hook_executions(hook_type);
CREATE INDEX idx_hook_executions_started_at ON hook_executions(started_at DESC);
```

#### Endpoint Calls
```sql
CREATE TABLE endpoint_calls (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL REFERENCES execution_traces(correlation_id),
    hook_execution_id UUID REFERENCES hook_executions(id),  -- Link to hook that triggered call

    -- Endpoint details
    service_name TEXT NOT NULL,  -- 'archon-intelligence', 'archon-mcp', etc.
    endpoint_path TEXT NOT NULL,  -- e.g., '/api/rag/query'
    http_method TEXT NOT NULL,  -- 'GET', 'POST', etc.

    -- Request/Response
    request_body JSONB,  -- Sanitized request (no secrets)
    response_body JSONB,  -- Response data
    response_status INTEGER,  -- HTTP status code

    -- Performance
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,

    -- Outcome
    success BOOLEAN NOT NULL,
    error_message TEXT,
    error_type TEXT,  -- 'timeout', 'connection_error', 'http_error', etc.
    retry_count INTEGER DEFAULT 0,

    -- Metadata
    headers JSONB,  -- Sanitized request headers
    context JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_endpoint_calls_correlation ON endpoint_calls(correlation_id);
CREATE INDEX idx_endpoint_calls_hook ON endpoint_calls(hook_execution_id) WHERE hook_execution_id IS NOT NULL;
CREATE INDEX idx_endpoint_calls_service ON endpoint_calls(service_name);
CREATE INDEX idx_endpoint_calls_endpoint ON endpoint_calls(endpoint_path);
CREATE INDEX idx_endpoint_calls_started_at ON endpoint_calls(started_at DESC);
```

### 2.3 Trace Assembly

#### Real-time Trace Assembly Service
```python
"""
Trace Assembly Service
Location: Archon Intelligence Service - /src/services/tracing/trace_assembly.py
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import asyncpg

@dataclass
class AssembledTrace:
    """Complete execution trace with all related data."""
    # Root trace
    correlation_id: str
    root_id: str
    session_id: str
    prompt_text: str

    # Timeline
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    status: str
    success: Optional[bool]

    # Routing decision
    routing_decision: Optional[dict]  # From agent_routing_decisions

    # Hook chain
    hook_executions: List[dict]  # All hooks, ordered by started_at

    # Endpoint calls
    endpoint_calls: List[dict]  # All endpoint calls, ordered by started_at

    # Nested traces (for agent delegations)
    child_traces: List['AssembledTrace']

    # Metadata
    total_hooks: int
    total_endpoints: int
    total_rag_queries: int
    total_quality_gates: int


class TraceAssemblyService:
    """Assembles fragmented traces into complete execution chains."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool

    async def assemble_trace(self, correlation_id: str) -> AssembledTrace:
        """
        Assemble complete trace for given correlation ID.

        Performs parallel queries for:
        1. Root execution trace
        2. Routing decision
        3. All hook executions
        4. All endpoint calls
        5. All child traces (recursive)
        """
        async with self.db.acquire() as conn:
            # Parallel fetch all components
            root_trace, routing, hooks, endpoints, children = await asyncio.gather(
                self._fetch_root_trace(conn, correlation_id),
                self._fetch_routing_decision(conn, correlation_id),
                self._fetch_hook_executions(conn, correlation_id),
                self._fetch_endpoint_calls(conn, correlation_id),
                self._fetch_child_traces(conn, correlation_id)
            )

            return AssembledTrace(
                correlation_id=correlation_id,
                root_id=root_trace['root_id'],
                session_id=root_trace['session_id'],
                prompt_text=root_trace['prompt_text'],
                started_at=root_trace['started_at'],
                completed_at=root_trace['completed_at'],
                duration_ms=root_trace['duration_ms'],
                status=root_trace['status'],
                success=root_trace['success'],
                routing_decision=routing,
                hook_executions=hooks,
                endpoint_calls=endpoints,
                child_traces=children,
                total_hooks=len(hooks),
                total_endpoints=len(endpoints),
                total_rag_queries=self._count_rag_queries(hooks),
                total_quality_gates=self._count_quality_gates(hooks)
            )

    async def get_trace_timeline(self, correlation_id: str) -> List[dict]:
        """
        Get chronological timeline of all events in trace.

        Returns list of events sorted by timestamp, including:
        - Prompt submission
        - Routing decision
        - Hook executions
        - Endpoint calls
        - Completion
        """
        trace = await self.assemble_trace(correlation_id)

        timeline = []

        # Add all events with timestamps
        timeline.append({
            'timestamp': trace.started_at,
            'event_type': 'prompt_submitted',
            'data': {'prompt': trace.prompt_text}
        })

        if trace.routing_decision:
            timeline.append({
                'timestamp': trace.routing_decision['created_at'],
                'event_type': 'agent_routed',
                'data': {
                    'agent': trace.routing_decision['selected_agent'],
                    'confidence': trace.routing_decision['confidence_total']
                }
            })

        for hook in trace.hook_executions:
            timeline.append({
                'timestamp': hook['started_at'],
                'event_type': 'hook_executed',
                'data': {
                    'hook_type': hook['hook_type'],
                    'tool': hook['tool_name'],
                    'duration_ms': hook['duration_ms']
                }
            })

        for endpoint in trace.endpoint_calls:
            timeline.append({
                'timestamp': endpoint['started_at'],
                'event_type': 'endpoint_called',
                'data': {
                    'service': endpoint['service_name'],
                    'endpoint': endpoint['endpoint_path'],
                    'status': endpoint['response_status'],
                    'duration_ms': endpoint['duration_ms']
                }
            })

        if trace.completed_at:
            timeline.append({
                'timestamp': trace.completed_at,
                'event_type': 'execution_completed',
                'data': {
                    'status': trace.status,
                    'success': trace.success,
                    'total_duration_ms': trace.duration_ms
                }
            })

        # Sort chronologically
        timeline.sort(key=lambda x: x['timestamp'])

        return timeline
```

---

## 3. Pattern Learning System Design

### 3.1 Success Pattern Identification

#### Success Criteria
```python
@dataclass
class SuccessCriteria:
    """Defines what makes an execution "successful"."""

    # Core success indicators
    execution_completed: bool  # Trace reached completion
    no_errors: bool  # No error status or error messages
    hooks_succeeded: bool  # All mandatory hooks succeeded
    quality_gates_passed: bool  # All quality gates validated

    # Performance indicators
    within_performance_thresholds: bool  # Met performance targets
    no_timeouts: bool  # No timeout errors

    # Intelligence indicators
    intelligence_gathered: bool  # RAG queries succeeded
    patterns_identified: bool  # Known patterns matched

    # User satisfaction indicators (future)
    user_confirmed_success: bool = True  # Assume success unless user reports issue

    def is_successful(self) -> bool:
        """Overall success determination."""
        return (
            self.execution_completed
            and self.no_errors
            and self.hooks_succeeded
            and self.quality_gates_passed
            and self.no_timeouts
        )

    def success_score(self) -> float:
        """Weighted success score (0.0 - 1.0)."""
        weights = {
            'execution_completed': 0.25,
            'no_errors': 0.25,
            'hooks_succeeded': 0.15,
            'quality_gates_passed': 0.15,
            'within_performance_thresholds': 0.10,
            'intelligence_gathered': 0.05,
            'user_confirmed_success': 0.05
        }

        score = sum(
            weights[field]
            for field, value in self.__dict__.items()
            if value and field in weights
        )

        return min(score, 1.0)
```

#### Pattern Extraction
```python
class PatternExtractor:
    """Extracts reusable patterns from successful executions."""

    async def extract_pattern(
        self,
        trace: AssembledTrace,
        success_criteria: SuccessCriteria
    ) -> Optional['ExecutionPattern']:
        """
        Extract pattern from successful trace.

        Pattern includes:
        1. Prompt characteristics (embedding, keywords, intent)
        2. Routing decision (agent selection, confidence)
        3. Hook execution sequence (which hooks, order, outcomes)
        4. Endpoint call patterns (which endpoints, parameters, results)
        5. Performance characteristics (timing, resource usage)
        """
        if not success_criteria.is_successful():
            return None

        # Generate prompt embedding for similarity matching
        prompt_embedding = await self._generate_embedding(trace.prompt_text)

        # Extract intent and keywords
        intent = await self._classify_intent(trace.prompt_text)
        keywords = await self._extract_keywords(trace.prompt_text)

        # Extract execution path
        execution_path = self._extract_execution_path(trace)

        # Extract successful hook sequence
        hook_sequence = self._extract_hook_sequence(trace)

        # Extract endpoint call pattern
        endpoint_pattern = self._extract_endpoint_pattern(trace)

        # Performance profile
        performance_profile = self._extract_performance_profile(trace)

        return ExecutionPattern(
            pattern_id=str(uuid.uuid4()),
            source_correlation_id=trace.correlation_id,
            prompt_text=trace.prompt_text,
            prompt_embedding=prompt_embedding,
            intent=intent,
            keywords=keywords,
            execution_path=execution_path,
            hook_sequence=hook_sequence,
            endpoint_pattern=endpoint_pattern,
            performance_profile=performance_profile,
            success_score=success_criteria.success_score(),
            usage_count=0,
            success_count=0,
            created_at=datetime.now()
        )

    def _extract_execution_path(self, trace: AssembledTrace) -> dict:
        """Extract the execution path taken."""
        return {
            'agent': trace.routing_decision['selected_agent'] if trace.routing_decision else None,
            'routing_strategy': trace.routing_decision['routing_strategy'] if trace.routing_decision else None,
            'hook_types': [h['hook_type'] for h in trace.hook_executions],
            'tool_names': [h['tool_name'] for h in trace.hook_executions if h.get('tool_name')],
            'endpoint_paths': [e['endpoint_path'] for e in trace.endpoint_calls]
        }

    def _extract_hook_sequence(self, trace: AssembledTrace) -> List[dict]:
        """Extract successful hook execution sequence."""
        return [
            {
                'hook_type': hook['hook_type'],
                'tool_name': hook.get('tool_name'),
                'intelligence_functions': hook.get('intelligence_functions_executed', []),
                'quality_gates': hook.get('quality_gates_validated', []),
                'duration_ms': hook.get('duration_ms')
            }
            for hook in trace.hook_executions
            if hook.get('success', True)
        ]

    def _extract_endpoint_pattern(self, trace: AssembledTrace) -> List[dict]:
        """Extract successful endpoint call pattern."""
        return [
            {
                'service': call['service_name'],
                'endpoint': call['endpoint_path'],
                'method': call['http_method'],
                # Sanitize request to remove specific values, keep structure
                'request_template': self._sanitize_request(call['request_body']),
                'expected_response_schema': self._extract_schema(call['response_body']),
                'typical_duration_ms': call['duration_ms']
            }
            for call in trace.endpoint_calls
            if call.get('success', False)
        ]
```

### 3.2 Pattern Matching Algorithm

#### Similarity Scoring
```python
class PatternMatcher:
    """Matches user requests to learned patterns."""

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        qdrant_client: QdrantClient,
        embedding_model: str = "text-embedding-3-small"
    ):
        self.db = db_pool
        self.qdrant = qdrant_client
        self.embedding_model = embedding_model

    async def find_matching_patterns(
        self,
        user_request: str,
        context: dict,
        min_confidence: float = 0.70,
        max_results: int = 5
    ) -> List['PatternMatch']:
        """
        Find learned patterns matching user request.

        Uses multi-dimensional matching:
        1. Semantic similarity (embeddings)
        2. Keyword overlap
        3. Intent classification
        4. Context alignment
        5. Historical success rate
        """
        # Generate embedding for user request
        request_embedding = await self._generate_embedding(user_request)

        # 1. Semantic similarity search (Qdrant)
        semantic_matches = await self._semantic_search(
            embedding=request_embedding,
            limit=max_results * 2  # Get more candidates for filtering
        )

        # 2. Score each match
        scored_matches = []
        for pattern in semantic_matches:
            score = await self._calculate_match_score(
                user_request=user_request,
                context=context,
                pattern=pattern,
                request_embedding=request_embedding
            )

            if score.total >= min_confidence:
                scored_matches.append(PatternMatch(
                    pattern=pattern,
                    score=score,
                    recommendation=self._generate_recommendation(pattern, score)
                ))

        # 3. Sort by confidence and historical success
        scored_matches.sort(
            key=lambda m: (m.score.total * m.pattern.success_rate),
            reverse=True
        )

        return scored_matches[:max_results]

    async def _calculate_match_score(
        self,
        user_request: str,
        context: dict,
        pattern: ExecutionPattern,
        request_embedding: List[float]
    ) -> 'PatternMatchScore':
        """
        Calculate multi-dimensional match score.

        Components:
        - Semantic similarity (40%): Vector similarity
        - Keyword overlap (20%): Common keywords/phrases
        - Intent alignment (20%): Same intent classification
        - Context fit (10%): Domain/context match
        - Historical success (10%): Pattern success rate
        """
        # Semantic similarity (cosine similarity)
        semantic_score = self._cosine_similarity(
            request_embedding,
            pattern.prompt_embedding
        )

        # Keyword overlap
        request_keywords = await self._extract_keywords(user_request)
        common_keywords = set(request_keywords) & set(pattern.keywords)
        keyword_score = (
            len(common_keywords) / max(len(request_keywords), len(pattern.keywords))
            if request_keywords or pattern.keywords else 0.0
        )

        # Intent alignment
        request_intent = await self._classify_intent(user_request)
        intent_score = 1.0 if request_intent == pattern.intent else 0.3

        # Context fit
        context_domain = context.get('domain', 'general')
        pattern_context = pattern.context or {}
        context_score = 1.0 if context_domain == pattern_context.get('domain', 'general') else 0.5

        # Historical success rate
        historical_score = pattern.success_rate

        # Weighted total
        total_score = (
            semantic_score * 0.40 +
            keyword_score * 0.20 +
            intent_score * 0.20 +
            context_score * 0.10 +
            historical_score * 0.10
        )

        return PatternMatchScore(
            total=total_score,
            semantic=semantic_score,
            keyword=keyword_score,
            intent=intent_score,
            context=context_score,
            historical=historical_score,
            explanation=self._explain_score(
                semantic_score, keyword_score, intent_score,
                context_score, historical_score, common_keywords
            )
        )
```

### 3.3 Pattern Replay Mechanism

#### Replay Strategy
```python
class PatternReplaySystem:
    """Replays learned patterns for similar requests."""

    async def apply_pattern(
        self,
        pattern: ExecutionPattern,
        user_request: str,
        context: dict
    ) -> 'ReplayPlan':
        """
        Generate replay plan from pattern.

        Returns:
        - Agent to route to
        - Hooks to execute
        - Intelligence queries to run
        - Expected endpoints
        - Performance expectations
        """
        # Extract agent from pattern
        agent = pattern.execution_path['agent']

        # Build hook execution plan
        hook_plan = self._build_hook_plan(pattern)

        # Build intelligence gathering plan
        intelligence_plan = self._build_intelligence_plan(pattern)

        # Build endpoint call expectations
        endpoint_expectations = self._build_endpoint_expectations(pattern)

        # Performance expectations
        performance_expectations = {
            'expected_duration_ms': pattern.performance_profile.get('avg_duration_ms'),
            'max_duration_ms': pattern.performance_profile.get('max_duration_ms'),
            'expected_hook_count': len(pattern.hook_sequence),
            'expected_endpoint_count': len(pattern.endpoint_pattern)
        }

        return ReplayPlan(
            pattern_id=pattern.pattern_id,
            agent=agent,
            hook_plan=hook_plan,
            intelligence_plan=intelligence_plan,
            endpoint_expectations=endpoint_expectations,
            performance_expectations=performance_expectations,
            confidence=pattern.success_rate
        )

    def _build_hook_plan(self, pattern: ExecutionPattern) -> List[dict]:
        """Build hook execution plan from pattern."""
        return [
            {
                'hook_type': hook['hook_type'],
                'tool_name': hook.get('tool_name'),
                'expected_intelligence_functions': hook.get('intelligence_functions', []),
                'expected_quality_gates': hook.get('quality_gates', []),
                'expected_duration_ms': hook.get('duration_ms')
            }
            for hook in pattern.hook_sequence
        ]

    def _build_intelligence_plan(self, pattern: ExecutionPattern) -> List[dict]:
        """Extract intelligence queries from successful pattern."""
        intelligence_functions = set()
        rag_queries = []

        for hook in pattern.hook_sequence:
            # Collect all intelligence functions executed
            intelligence_functions.update(hook.get('intelligence_functions', []))

            # Collect RAG query patterns
            if 'rag_queries_executed' in hook:
                for query in hook['rag_queries_executed']:
                    rag_queries.append({
                        'query_type': query.get('query_type'),
                        'context': query.get('context'),
                        'typical_duration_ms': query.get('duration_ms')
                    })

        return {
            'intelligence_functions': list(intelligence_functions),
            'rag_query_patterns': rag_queries
        }
```

#### Integration with Enhanced Router
```python
# Modify EnhancedAgentRouter to use learned patterns

class EnhancedAgentRouter:
    def __init__(self, ...):
        # Add pattern matcher
        self.pattern_matcher = PatternMatcher(db_pool, qdrant_client)
        self.pattern_replay = PatternReplaySystem()

    async def route(
        self,
        user_request: str,
        context: dict | None = None,
        correlation_id: str | None = None
    ) -> List[AgentRecommendation]:
        """Route with pattern learning."""
        correlation_id = correlation_id or str(uuid.uuid4())
        context = context or {}

        # 1. Check for learned patterns FIRST
        learned_patterns = await self.pattern_matcher.find_matching_patterns(
            user_request=user_request,
            context=context,
            min_confidence=0.75,  # High confidence threshold
            max_results=3
        )

        if learned_patterns:
            # Use learned pattern if high confidence
            best_pattern = learned_patterns[0]

            if best_pattern.score.total >= 0.85:  # Very high confidence
                replay_plan = await self.pattern_replay.apply_pattern(
                    pattern=best_pattern.pattern,
                    user_request=user_request,
                    context=context
                )

                # Log that we're using a learned pattern
                await self._log_pattern_usage(
                    correlation_id=correlation_id,
                    pattern=best_pattern.pattern,
                    replay_plan=replay_plan
                )

                # Return recommendation based on pattern
                return [AgentRecommendation(
                    agent_name=replay_plan.agent,
                    agent_title=self.registry['agents'][replay_plan.agent]['title'],
                    confidence=ConfidenceScore(
                        total=best_pattern.score.total,
                        trigger_score=best_pattern.score.semantic,
                        context_score=best_pattern.score.context,
                        capability_score=best_pattern.score.keyword,
                        historical_score=best_pattern.score.historical,
                        explanation=f"Learned pattern match: {best_pattern.score.explanation}"
                    ),
                    reason=f"Matched learned pattern (success rate: {best_pattern.pattern.success_rate:.0%})",
                    definition_path=self.registry['agents'][replay_plan.agent]['definition_path'],
                    replay_plan=replay_plan  # Include replay plan for hooks
                )]

        # 2. Fall back to normal routing if no confident pattern match
        return await self._normal_route(user_request, context, correlation_id)
```

---

## 4. Analytics Schema Design

### 4.1 Success Patterns Table
```sql
CREATE TABLE success_patterns (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id UUID NOT NULL UNIQUE,

    -- Source trace
    source_correlation_id UUID NOT NULL REFERENCES execution_traces(correlation_id),

    -- Pattern characteristics
    prompt_text TEXT NOT NULL,
    prompt_embedding VECTOR(1536),  -- Using pgvector extension
    intent TEXT NOT NULL,  -- 'debugging', 'api_design', 'performance', etc.
    keywords TEXT[] NOT NULL,

    -- Execution path
    agent TEXT NOT NULL,
    routing_strategy TEXT NOT NULL,
    hook_sequence JSONB NOT NULL,  -- Array of hook execution details
    endpoint_pattern JSONB NOT NULL,  -- Array of endpoint call details

    -- Performance profile
    avg_duration_ms INTEGER NOT NULL,
    min_duration_ms INTEGER NOT NULL,
    max_duration_ms INTEGER NOT NULL,
    avg_hook_count INTEGER NOT NULL,
    avg_endpoint_count INTEGER NOT NULL,
    avg_rag_query_count INTEGER NOT NULL,

    -- Success metrics
    success_score FLOAT NOT NULL,  -- Initial success score
    usage_count INTEGER NOT NULL DEFAULT 0,  -- How many times pattern used
    success_count INTEGER NOT NULL DEFAULT 0,  -- How many successful replays
    failure_count INTEGER NOT NULL DEFAULT 0,  -- How many failed replays

    -- Context
    context JSONB,  -- Domain, environment, etc.
    tags TEXT[],

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Computed column for success rate
ALTER TABLE success_patterns ADD COLUMN success_rate FLOAT GENERATED ALWAYS AS (
    CASE
        WHEN usage_count > 0 THEN success_count::FLOAT / usage_count::FLOAT
        ELSE 1.0  -- Initial success score
    END
) STORED;

-- Indexes
CREATE INDEX idx_success_patterns_embedding ON success_patterns USING ivfflat (prompt_embedding vector_cosine_ops);
CREATE INDEX idx_success_patterns_intent ON success_patterns(intent);
CREATE INDEX idx_success_patterns_agent ON success_patterns(agent);
CREATE INDEX idx_success_patterns_success_rate ON success_patterns(success_rate DESC);
CREATE INDEX idx_success_patterns_keywords ON success_patterns USING GIN(keywords);
CREATE INDEX idx_success_patterns_tags ON success_patterns USING GIN(tags);
CREATE INDEX idx_success_patterns_last_used ON success_patterns(last_used_at DESC NULLS LAST);
```

### 4.2 Pattern Usage Tracking
```sql
CREATE TABLE pattern_usage_log (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id UUID NOT NULL REFERENCES success_patterns(pattern_id),
    correlation_id UUID NOT NULL REFERENCES execution_traces(correlation_id),

    -- Usage details
    user_request TEXT NOT NULL,
    match_score FLOAT NOT NULL,  -- How confident was the match

    -- Outcome
    used BOOLEAN NOT NULL,  -- Was pattern actually used?
    outcome TEXT,  -- 'success', 'failure', 'partial_success'
    success BOOLEAN,  -- Did execution succeed?

    -- Deviations from pattern
    deviations JSONB,  -- Any differences from expected pattern

    -- Performance comparison
    expected_duration_ms INTEGER,
    actual_duration_ms INTEGER,
    performance_variance FLOAT,  -- (actual - expected) / expected

    -- Feedback
    user_feedback TEXT,  -- Future: user confirmation of success

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pattern_usage_pattern ON pattern_usage_log(pattern_id);
CREATE INDEX idx_pattern_usage_correlation ON pattern_usage_log(correlation_id);
CREATE INDEX idx_pattern_usage_outcome ON pattern_usage_log(outcome);
CREATE INDEX idx_pattern_usage_created_at ON pattern_usage_log(created_at DESC);
```

### 4.3 Agent Chaining Patterns
```sql
CREATE TABLE agent_chaining_patterns (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Chain details
    primary_agent TEXT NOT NULL,
    delegated_agents TEXT[] NOT NULL,  -- Agents called in sequence
    delegation_depth INTEGER NOT NULL,  -- How many levels deep

    -- Context
    trigger_context TEXT NOT NULL,  -- What triggered this chain
    success_rate FLOAT NOT NULL DEFAULT 1.0,
    usage_count INTEGER NOT NULL DEFAULT 0,

    -- Timing
    avg_total_duration_ms INTEGER NOT NULL,
    avg_coordination_overhead_ms INTEGER NOT NULL,

    -- Pattern metadata
    source_traces UUID[] NOT NULL,  -- Source correlation IDs
    tags TEXT[],

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_chaining_primary ON agent_chaining_patterns(primary_agent);
CREATE INDEX idx_agent_chaining_success_rate ON agent_chaining_patterns(success_rate DESC);
CREATE INDEX idx_agent_chaining_usage_count ON agent_chaining_patterns(usage_count DESC);
```

### 4.4 Error Patterns Table
```sql
CREATE TABLE error_patterns (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Error details
    error_type TEXT NOT NULL,  -- 'timeout', 'api_error', 'validation_error', etc.
    error_message_pattern TEXT NOT NULL,  -- Regex or template

    -- Context when errors occur
    agent TEXT,
    hook_type TEXT,
    endpoint_path TEXT,

    -- Occurrence tracking
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Related traces
    sample_correlation_ids UUID[] NOT NULL,  -- Sample traces with this error

    -- Resolution strategies
    known_fix JSONB,  -- If we know how to fix this
    prevention_strategy JSONB,  -- How to prevent this

    -- Metadata
    tags TEXT[],
    severity TEXT,  -- 'critical', 'high', 'medium', 'low'

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_error_patterns_type ON error_patterns(error_type);
CREATE INDEX idx_error_patterns_agent ON error_patterns(agent) WHERE agent IS NOT NULL;
CREATE INDEX idx_error_patterns_endpoint ON error_patterns(endpoint_path) WHERE endpoint_path IS NOT NULL;
CREATE INDEX idx_error_patterns_occurrence ON error_patterns(occurrence_count DESC);
CREATE INDEX idx_error_patterns_severity ON error_patterns(severity);
```

### 4.5 Views for Analytics

#### Success Rate by Agent
```sql
CREATE VIEW agent_success_rates AS
SELECT
    ard.selected_agent as agent,
    COUNT(*) as total_executions,
    SUM(CASE WHEN et.success = true THEN 1 ELSE 0 END) as successful_executions,
    AVG(CASE WHEN et.success = true THEN 1.0 ELSE 0.0 END) as success_rate,
    AVG(et.duration_ms) as avg_duration_ms,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY et.duration_ms) as median_duration_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY et.duration_ms) as p95_duration_ms
FROM execution_traces et
JOIN agent_routing_decisions ard ON et.correlation_id = ard.correlation_id
WHERE et.completed_at IS NOT NULL
GROUP BY ard.selected_agent
ORDER BY success_rate DESC, total_executions DESC;
```

#### Hook Performance Summary
```sql
CREATE VIEW hook_performance_summary AS
SELECT
    hook_type,
    tool_name,
    COUNT(*) as execution_count,
    AVG(duration_ms) as avg_duration_ms,
    MIN(duration_ms) as min_duration_ms,
    MAX(duration_ms) as max_duration_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
    SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as success_count,
    AVG(CASE WHEN success = true THEN 1.0 ELSE 0.0 END) as success_rate,
    AVG(array_length(intelligence_functions_executed, 1)) as avg_intelligence_functions,
    AVG(array_length(quality_gates_validated, 1)) as avg_quality_gates
FROM hook_executions
WHERE completed_at IS NOT NULL
GROUP BY hook_type, tool_name
ORDER BY execution_count DESC;
```

#### Endpoint Reliability
```sql
CREATE VIEW endpoint_reliability AS
SELECT
    service_name,
    endpoint_path,
    COUNT(*) as call_count,
    SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as success_count,
    AVG(CASE WHEN success = true THEN 1.0 ELSE 0.0 END) as success_rate,
    AVG(duration_ms) as avg_duration_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
    SUM(retry_count) as total_retries,
    AVG(retry_count) as avg_retries_per_call,
    COUNT(DISTINCT error_type) as unique_error_types,
    array_agg(DISTINCT error_type) FILTER (WHERE error_type IS NOT NULL) as error_types
FROM endpoint_calls
WHERE completed_at IS NOT NULL
GROUP BY service_name, endpoint_path
ORDER BY call_count DESC;
```

---

## 5. Integration Strategy

### 5.1 Hook System Integration

#### Trace Capture in Hooks
```bash
# Common tracing functions for all hooks
# File: ~/.claude/hooks/lib/tracing_utils.sh

#!/bin/bash

# Get correlation ID from environment or generate new one
get_correlation_id() {
    echo "${ARCHON_CORRELATION_ID:-$(uuidgen)}"
}

# Get root ID
get_root_id() {
    echo "${ARCHON_ROOT_ID:-$(get_correlation_id)}"
}

# Get parent ID
get_parent_id() {
    echo "${ARCHON_PARENT_ID:-$(get_correlation_id)}"
}

# Log trace event to Archon
log_trace_event() {
    local event_type="$1"
    local event_data="$2"
    local correlation_id=$(get_correlation_id)
    local root_id=$(get_root_id)
    local parent_id=$(get_parent_id)
    local execution_id=$(uuidgen)

    # Non-blocking async call
    curl -s -X POST "${ARCHON_INTELLIGENCE_URL}/api/traces/${event_type}" \
        -H "Content-Type: application/json" \
        -H "X-Correlation-ID: ${correlation_id}" \
        -H "X-Root-ID: ${root_id}" \
        -H "X-Parent-ID: ${parent_id}" \
        -H "X-Execution-ID: ${execution_id}" \
        -d "${event_data}" > /dev/null 2>&1 &
}

# Start trace timing
start_trace_timer() {
    echo $(date +%s%3N)  # Milliseconds since epoch
}

# Calculate duration
calculate_duration() {
    local start_ms="$1"
    local end_ms=$(date +%s%3N)
    echo $((end_ms - start_ms))
}
```

#### Modified UserPromptSubmit Hook
```bash
#!/bin/bash
# ~/.claude/hooks/user-prompt-submit-agent-enhancer.sh
# WITH TRACING

source ~/.claude/hooks/lib/tracing_utils.sh

# Start timing
START_TIME=$(start_trace_timer)

# Read prompt
PROMPT=$(cat)

# Generate correlation ID
CORRELATION_ID=$(uuidgen)
SESSION_ID=$(get_session_id)

# Export for downstream hooks
export ARCHON_CORRELATION_ID="$CORRELATION_ID"
export ARCHON_ROOT_ID="$CORRELATION_ID"
export ARCHON_SESSION_ID="$SESSION_ID"

# Log trace start
log_trace_event "start" "$(cat <<EOF
{
    "correlation_id": "${CORRELATION_ID}",
    "session_id": "${SESSION_ID}",
    "source": "user_prompt",
    "prompt_text": "${PROMPT}",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)"

# Detect agent (existing logic)
AGENT_NAME=$(detect_agent "$PROMPT")

# Execute RAG queries if agent detected
if [[ -n "$AGENT_NAME" ]]; then
    execute_rag_queries "$AGENT_NAME" "$CORRELATION_ID"
fi

# Enhance prompt (existing logic)
ENHANCED_PROMPT=$(enhance_prompt "$PROMPT" "$AGENT_NAME" "$CORRELATION_ID")

# Calculate duration
DURATION=$(calculate_duration "$START_TIME")

# Log hook completion
log_trace_event "hook" "$(cat <<EOF
{
    "hook_type": "UserPromptSubmit",
    "duration_ms": ${DURATION},
    "agent_detected": "${AGENT_NAME}",
    "status": "success"
}
EOF
)"

# Output enhanced prompt
echo "$ENHANCED_PROMPT"
```

#### Modified PreToolUse Hook
```bash
#!/bin/bash
# ~/.claude/hooks/pre-tool-use-intelligence.sh
# WITH TRACING

source ~/.claude/hooks/lib/tracing_utils.sh

START_TIME=$(start_trace_timer)

# Read tool call
TOOL_CALL=$(cat)
TOOL_NAME=$(echo "$TOOL_CALL" | jq -r '.tool // "unknown"')

# Get correlation context
CORRELATION_ID=$(get_correlation_id)
EXECUTION_ID=$(uuidgen)

# Export for potential nested calls
export ARCHON_PARENT_ID="$EXECUTION_ID"

# Log hook start
log_trace_event "hook" "$(cat <<EOF
{
    "execution_id": "${EXECUTION_ID}",
    "hook_type": "PreToolUse",
    "tool_name": "${TOOL_NAME}",
    "status": "started"
}
EOF
)"

# Execute intelligence gathering (existing logic)
INTELLIGENCE=$(gather_intelligence "$TOOL_CALL" "$CORRELATION_ID")

# Inject intelligence into tool call
ENHANCED_TOOL_CALL=$(inject_intelligence "$TOOL_CALL" "$INTELLIGENCE")

# Calculate duration
DURATION=$(calculate_duration "$START_TIME")

# Log hook completion with intelligence details
INTEL_FUNCTIONS=$(echo "$INTELLIGENCE" | jq -r '.functions_executed[]' | tr '\n' ',' | sed 's/,$//')

log_trace_event "hook" "$(cat <<EOF
{
    "execution_id": "${EXECUTION_ID}",
    "hook_type": "PreToolUse",
    "tool_name": "${TOOL_NAME}",
    "duration_ms": ${DURATION},
    "intelligence_functions_executed": [${INTEL_FUNCTIONS}],
    "status": "success"
}
EOF
)"

# Output enhanced tool call
echo "$ENHANCED_TOOL_CALL"
```

### 5.2 Agent Router Integration

#### Pattern-Aware Routing
```python
# Modification to EnhancedAgentRouter class

class EnhancedAgentRouter:
    async def route_with_learning(
        self,
        user_request: str,
        context: dict | None = None,
        correlation_id: str | None = None
    ) -> Tuple[List[AgentRecommendation], Optional[ReplayPlan]]:
        """
        Route with pattern learning and tracing.

        Returns:
            (recommendations, replay_plan)
            replay_plan is None if not using learned pattern
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        context = context or {}

        # Start routing timer
        start_time = time.time()

        # Check for learned patterns
        learned_patterns = await self.pattern_matcher.find_matching_patterns(
            user_request=user_request,
            context=context,
            min_confidence=0.75
        )

        replay_plan = None
        routing_strategy = "normal"

        # Use learned pattern if high confidence
        if learned_patterns and learned_patterns[0].score.total >= 0.85:
            routing_strategy = "learned_pattern"
            best_pattern = learned_patterns[0]

            replay_plan = await self.pattern_replay.apply_pattern(
                pattern=best_pattern.pattern,
                user_request=user_request,
                context=context
            )

            recommendations = [self._pattern_to_recommendation(
                best_pattern,
                replay_plan
            )]
        else:
            # Normal routing
            recommendations = await self._normal_route(
                user_request,
                context,
                correlation_id
            )

        # Calculate routing duration
        routing_duration_ms = int((time.time() - start_time) * 1000)

        # Log routing decision with tracing
        await self._log_routing_decision_with_trace(
            correlation_id=correlation_id,
            user_request=user_request,
            recommendations=recommendations,
            routing_strategy=routing_strategy,
            routing_duration_ms=routing_duration_ms,
            pattern_used=learned_patterns[0] if replay_plan else None
        )

        return recommendations, replay_plan
```

### 5.3 Archon Endpoint Integration

#### Trace Middleware
```python
# Add to Archon Intelligence Service
# File: /services/intelligence/middleware/tracing_middleware.py

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time

class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware to capture and log all endpoint calls with correlation IDs."""

    async def dispatch(self, request: Request, call_next):
        # Extract correlation headers
        correlation_id = request.headers.get('X-Correlation-ID')
        root_id = request.headers.get('X-Root-ID', correlation_id)
        parent_id = request.headers.get('X-Parent-ID', correlation_id)
        execution_id = request.headers.get('X-Execution-ID', str(uuid.uuid4()))

        # Start timing
        start_time = time.time()

        # Call endpoint
        try:
            response = await call_next(request)
            success = True
            error_message = None
        except Exception as e:
            success = False
            error_message = str(e)
            response = Response(status_code=500)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log endpoint call (async, non-blocking)
        asyncio.create_task(self._log_endpoint_call(
            correlation_id=correlation_id,
            root_id=root_id,
            parent_id=parent_id,
            execution_id=execution_id,
            request=request,
            response=response,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message
        ))

        return response

    async def _log_endpoint_call(
        self,
        correlation_id: str,
        root_id: str,
        parent_id: str,
        execution_id: str,
        request: Request,
        response: Response,
        duration_ms: int,
        success: bool,
        error_message: str | None
    ):
        """Log endpoint call to database."""
        # Sanitize request body (remove secrets)
        request_body = await self._sanitize_request(request)

        # Extract response body (if available)
        response_body = await self._extract_response(response)

        # Insert into endpoint_calls table
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO endpoint_calls (
                    correlation_id,
                    service_name,
                    endpoint_path,
                    http_method,
                    request_body,
                    response_body,
                    response_status,
                    duration_ms,
                    success,
                    error_message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                correlation_id,
                "archon-intelligence",
                str(request.url.path),
                request.method,
                Json(request_body),
                Json(response_body),
                response.status_code,
                duration_ms,
                success,
                error_message
            )
```

---

## 6. Implementation Plan

### Phase 1: Foundation (Weeks 1-2)

**Goal**: Establish basic traceability infrastructure

**Deliverables**:
1. Database schema (all tables created in Supabase)
2. Correlation ID generation in UserPromptSubmit hook
3. Basic trace logging in all hooks
4. Trace assembly service (basic version)

**Tasks**:
- [ ] Create all database tables in Supabase
- [ ] Add pgvector extension for embeddings
- [ ] Implement tracing_utils.sh library
- [ ] Modify all hooks to include trace logging
- [ ] Create TraceAssemblyService class
- [ ] Add tracing middleware to Archon Intelligence Service
- [ ] Create /api/traces/* endpoints for trace ingestion

**Success Criteria**:
- Correlation IDs propagated through entire execution chain
- All execution traces stored in database
- Can assemble complete trace for any correlation ID
- <5ms trace logging overhead

### Phase 2: Pattern Extraction (Weeks 3-4)

**Goal**: Extract and store successful execution patterns

**Deliverables**:
1. Success criteria evaluation system
2. Pattern extraction engine
3. Pattern storage in success_patterns table
4. Background job for pattern extraction

**Tasks**:
- [ ] Implement SuccessCriteria evaluation
- [ ] Create PatternExtractor class
- [ ] Add embedding generation for prompts (OpenAI API)
- [ ] Implement intent classification
- [ ] Create background job to extract patterns from successful traces
- [ ] Store patterns in success_patterns table
- [ ] Index patterns in Qdrant for semantic search

**Success Criteria**:
- Patterns extracted from all successful executions
- Patterns stored with embeddings
- Pattern extraction completes within 30 seconds of trace completion
- At least 50 patterns collected after 1 week of usage

### Phase 3: Pattern Matching (Weeks 5-6)

**Goal**: Match new requests to learned patterns

**Deliverables**:
1. Pattern matching algorithm
2. Similarity scoring system
3. Pattern confidence calculation
4. Integration with Enhanced Router

**Tasks**:
- [ ] Implement PatternMatcher class
- [ ] Create multi-dimensional similarity scoring
- [ ] Integrate pattern matching with EnhancedAgentRouter
- [ ] Add pattern usage logging
- [ ] Implement pattern success rate tracking
- [ ] Create pattern recommendation API endpoint

**Success Criteria**:
- Pattern matching completes in <100ms
- Match accuracy >80% (validated manually on sample)
- Pattern confidence scores correlate with actual success
- Router successfully uses learned patterns

### Phase 4: Pattern Replay (Weeks 7-8)

**Goal**: Apply learned patterns to new executions

**Deliverables**:
1. Pattern replay system
2. Replay plan generation
3. Hook integration with replay plans
4. Performance monitoring and comparison

**Tasks**:
- [ ] Implement PatternReplaySystem class
- [ ] Create replay plan data structure
- [ ] Modify hooks to use replay plans when available
- [ ] Track deviations from expected pattern
- [ ] Monitor performance vs. expectations
- [ ] Update pattern success rates based on replay outcomes

**Success Criteria**:
- Replay plans successfully guide execution
- Pattern replay success rate >90%
- Performance stays within expected ranges
- System updates pattern success rates automatically

### Phase 5: Analytics & Optimization (Weeks 9-10)

**Goal**: Provide insights and optimize system

**Deliverables**:
1. Analytics dashboard
2. Pattern effectiveness reports
3. Agent performance insights
4. Error pattern detection
5. System optimization

**Tasks**:
- [ ] Create analytics views in database
- [ ] Build analytics dashboard (React UI)
- [ ] Implement agent success rate tracking
- [ ] Create error pattern detection
- [ ] Add pattern pruning (remove low-performing patterns)
- [ ] Implement pattern versioning
- [ ] Create system health monitoring

**Success Criteria**:
- Dashboard shows real-time metrics
- Agent success rates tracked and displayed
- Error patterns automatically detected
- Low-performing patterns identified and removed
- System maintains <100ms pattern lookup performance

### Phase 6: Advanced Features (Weeks 11-12)

**Goal**: Add sophisticated learning capabilities

**Deliverables**:
1. Agent chaining pattern detection
2. Context-aware pattern selection
3. User feedback integration
4. A/B testing framework
5. Pattern evolution tracking

**Tasks**:
- [ ] Implement agent chaining pattern detection
- [ ] Add context-aware pattern filtering
- [ ] Create user feedback collection mechanism
- [ ] Build A/B testing framework for pattern variants
- [ ] Track pattern evolution over time
- [ ] Implement pattern merge/split logic
- [ ] Add pattern explanation generation

**Success Criteria**:
- Agent chaining patterns automatically detected
- Context improves pattern selection accuracy
- User feedback incorporated into pattern scoring
- A/B testing validates pattern improvements
- System learns from pattern evolution

---

## 7. Performance Considerations

### 7.1 Performance Targets

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Trace logging | <5ms | Per log call |
| Correlation ID propagation | <1ms | Per hop |
| Trace assembly | <50ms | Full trace |
| Pattern matching | <100ms | Including embedding |
| Pattern extraction | <30s | Background job |
| Database queries | <20ms | Single query |
| Analytics views | <200ms | Dashboard load |

### 7.2 Optimization Strategies

#### Async/Non-blocking Logging
```python
# All trace logging must be non-blocking
asyncio.create_task(log_trace_event(...))  # Fire and forget
```

#### Batch Processing
```python
# Batch pattern extraction instead of per-trace
async def batch_extract_patterns(batch_size: int = 100):
    """Extract patterns from recent successful traces in batches."""
    successful_traces = await fetch_recent_successful_traces(limit=batch_size)

    # Process in parallel
    pattern_tasks = [
        extract_pattern(trace)
        for trace in successful_traces
    ]

    patterns = await asyncio.gather(*pattern_tasks)

    # Bulk insert patterns
    await bulk_insert_patterns(patterns)
```

#### Caching
```python
# Cache frequently matched patterns
class PatternCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.cache = TTLCache(maxsize=1000, ttl=ttl_seconds)

    async def get_top_patterns(self) -> List[ExecutionPattern]:
        """Get cached top patterns by usage count."""
        if 'top_patterns' not in self.cache:
            self.cache['top_patterns'] = await self._fetch_top_patterns()
        return self.cache['top_patterns']
```

#### Database Indexes
```sql
-- Ensure all foreign keys are indexed
-- Use partial indexes for common filters
CREATE INDEX idx_execution_traces_successful
ON execution_traces(correlation_id, started_at DESC)
WHERE success = true;

-- Use GiST indexes for JSONB queries
CREATE INDEX idx_success_patterns_context
ON success_patterns USING GIN(context);
```

#### Connection Pooling
```python
# Use connection pools for database access
db_pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=10,
    max_size=50,
    command_timeout=60
)
```

### 7.3 Monitoring

#### Performance Metrics to Track
```python
METRICS = {
    'trace_log_duration_ms': Histogram(),
    'pattern_match_duration_ms': Histogram(),
    'pattern_extraction_duration_ms': Histogram(),
    'trace_assembly_duration_ms': Histogram(),
    'db_query_duration_ms': Histogram(),
    'pattern_cache_hit_rate': Gauge(),
    'active_traces': Gauge(),
    'patterns_total': Gauge(),
    'pattern_usage_rate': Counter()
}
```

---

## 8. Security & Privacy

### 8.1 Data Sanitization

#### Sensitive Data Removal
```python
def sanitize_request(request_body: dict) -> dict:
    """Remove sensitive data from request before logging."""
    SENSITIVE_FIELDS = {
        'password', 'token', 'api_key', 'secret',
        'authorization', 'credentials', 'private_key'
    }

    sanitized = {}
    for key, value in request_body.items():
        if key.lower() in SENSITIVE_FIELDS:
            sanitized[key] = '[REDACTED]'
        elif isinstance(value, dict):
            sanitized[key] = sanitize_request(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_request(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized
```

### 8.2 Access Control

#### Row-Level Security (RLS) in Supabase
```sql
-- Only allow access to user's own traces
CREATE POLICY user_traces_policy ON execution_traces
    FOR SELECT
    USING (user_id = auth.uid() OR user_id IS NULL);

-- Only allow system to write traces
CREATE POLICY system_write_traces ON execution_traces
    FOR INSERT
    WITH CHECK (auth.role() = 'service_role');
```

### 8.3 Data Retention

#### Automated Cleanup
```python
async def cleanup_old_traces(retention_days: int = 90):
    """Remove traces older than retention period."""
    async with db_pool.acquire() as conn:
        # Archive to cold storage before deletion
        await conn.execute("""
            INSERT INTO traces_archive
            SELECT * FROM execution_traces
            WHERE started_at < NOW() - INTERVAL '%s days'
        """, retention_days)

        # Delete old traces
        await conn.execute("""
            DELETE FROM execution_traces
            WHERE started_at < NOW() - INTERVAL '%s days'
        """, retention_days)
```

---

## Conclusion

This traceability and pattern learning system provides:

1. **Complete Visibility**: Every interaction traced from prompt to outcome
2. **Intelligent Learning**: System learns from successful patterns automatically
3. **Self-Improvement**: Routing and execution optimize over time
4. **Performance**: <5ms overhead, <100ms pattern matching
5. **Scalability**: Designed for millions of traces
6. **Privacy**: Sensitive data sanitized, RLS enforced
7. **Integration**: Seamlessly integrates with existing infrastructure

### Next Steps

1. **Review & Approval**: Architecture team review this design
2. **Phase 1 Kickoff**: Create database schema and basic tracing
3. **Incremental Rollout**: Phase-by-phase implementation
4. **Monitoring**: Track metrics and adjust as needed
5. **Iteration**: Continuous improvement based on real-world usage

### Success Metrics (6 months)

- **100% trace coverage**: Every execution captured
- **>10,000 patterns**: Learned from successful executions
- **>85% pattern success rate**: Learned patterns work reliably
- **>80% faster routing**: Pattern-based routing faster than fuzzy matching
- **>90% agent success rate**: Improved through pattern learning
- **<100ms end-to-end latency**: Tracing + pattern matching + routing

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-01
**Status**: Ready for Implementation
