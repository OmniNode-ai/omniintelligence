# Parallel Build Quick Start Guide

**Ready to Execute**: This guide provides immediate next steps for starting parallel development.

---

## TL;DR - Start Building Today

### 5 Independent Tracks, Start Immediately:

1. **Track 1: Database** → Create schema files → Deploy to Supabase
2. **Track 2: Hooks** → Create tracing library → Update hooks
3. **Track 3: Patterns** → Build pattern extractor → Index in Qdrant
4. **Track 4: Router** → Integrate patterns → Add replay logic
5. **Track 5: Analytics** → Build API → Create dashboard

**Timeline**: 6-8 weeks (vs 12 weeks sequential)

---

## Visual Dependency Map

```
┌─────────────────────────────────────────────────────────────────┐
│                         WEEK 1-2: FOUNDATION                     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Track 1: Database Schema (CRITICAL PATH)                │   │
│  │ ├─ execution_traces table                               │   │
│  │ ├─ agent_routing_decisions table                        │   │
│  │ ├─ hook_executions table                                │   │
│  │ ├─ endpoint_calls table                                 │   │
│  │ └─ success_patterns table                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            │ (schema ready)                      │
│                            ▼                                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         WEEK 3-6: PARALLEL BUILD                 │
│                                                                  │
│  ┌────────────────────────┐  ┌────────────────────────┐        │
│  │ Track 2: Hooks         │  │ Track 3: Patterns      │        │
│  │ (Weeks 3-4)            │  │ (Weeks 3-6)            │        │
│  ├─ tracing_utils.sh     │  ├─ PatternExtractor     │        │
│  ├─ UserPromptSubmit     │  ├─ Embeddings           │        │
│  ├─ PreToolUse hooks     │  ├─ Qdrant indexing      │        │
│  └─ PostToolUse hooks    │  └─ PatternMatcher       │        │
│  └────────────────────────┘  └────────────────────────┘        │
│           │                            │                         │
│           └────────────┬───────────────┘                         │
│                        │ (traces + patterns)                     │
│                        ▼                                         │
│  ┌────────────────────────────────────────────────┐            │
│  │ Track 4: Router Integration (Weeks 5-6)        │            │
│  ├─ Pattern-aware routing                         │            │
│  ├─ Pattern replay                                │            │
│  └─ Performance monitoring                        │            │
│  └────────────────────────────────────────────────┘            │
│                                                                  │
│  ┌────────────────────────────────────────────────┐            │
│  │ Track 5: Analytics (Weeks 3-6, parallel)       │            │
│  ├─ Analytics API                                 │            │
│  ├─ Dashboard UI                                  │            │
│  └─ Error detection                               │            │
│  └────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     WEEK 7-8: INTEGRATION & TESTING              │
│                                                                  │
│  All Tracks → End-to-end testing → Performance tuning           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Day 1: Immediate Actions

### Action 1: Set Up Work Structure (30 minutes)

```bash
# Create GitHub project boards
gh project create --title "Track 1: Database & Infrastructure"
gh project create --title "Track 2: Hook System & Tracing"
gh project create --title "Track 3: Pattern Learning Engine"
gh project create --title "Track 4: Router & Integration"
gh project create --title "Track 5: Analytics & Visualization"

# Create feature branches
cd /Volumes/PRO-G40/Code/Archon
git checkout -b feature/traceability-track-1-database
git checkout -b feature/traceability-track-2-hooks
git checkout -b feature/traceability-track-3-patterns
git checkout -b feature/traceability-track-4-router
git checkout -b feature/traceability-track-5-analytics

# Create communication channels (example)
# In Slack: #traceability-track-1, #traceability-track-2, etc.
```

### Action 2: Assign Teams (15 minutes)

**Option A: 5-Person Team**
```
Track 1: Developer A (Database specialist)
Track 2: Developer B (Shell scripting expert)
Track 3: Developer C (ML/Python backend)
Track 4: Developer D (Python backend)
Track 5: Developer E (Full-stack/Frontend)
```

**Option B: 3-Person Team** (recommended for smaller teams)
```
Week 1-2: All three on Track 1
Week 3-4: Split to Tracks 2, 3, 5
Week 5-6: Split to Tracks 3, 4, 5
Week 7-8: All on integration
```

### Action 3: Track 1 - Start Database Schema (Today!)

```bash
# Create schema directory
cd /Volumes/PRO-G40/Code/Archon
git checkout feature/traceability-track-1-database
mkdir -p services/intelligence/database/schema

# Create first schema file
cat > services/intelligence/database/schema/001_execution_traces.sql <<'EOF'
-- Execution Traces Table
-- Purpose: Track every user prompt and its execution flow

CREATE TABLE IF NOT EXISTS execution_traces (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL UNIQUE,
    root_id UUID NOT NULL,
    parent_id UUID,

    -- Session context
    session_id UUID NOT NULL,
    user_id TEXT,

    -- Source information
    source TEXT NOT NULL,
    prompt_text TEXT,

    -- Execution metadata
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status TEXT NOT NULL DEFAULT 'in_progress',

    -- Outcome tracking
    success BOOLEAN,
    error_message TEXT,
    error_type TEXT,

    -- Context and metadata
    context JSONB,
    tags TEXT[],

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_execution_traces_correlation ON execution_traces(correlation_id);
CREATE INDEX IF NOT EXISTS idx_execution_traces_root ON execution_traces(root_id);
CREATE INDEX IF NOT EXISTS idx_execution_traces_session ON execution_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_execution_traces_status ON execution_traces(status);
CREATE INDEX IF NOT EXISTS idx_execution_traces_started_at ON execution_traces(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_traces_tags ON execution_traces USING GIN(tags);

-- Comments for documentation
COMMENT ON TABLE execution_traces IS 'Master record for all execution traces';
COMMENT ON COLUMN execution_traces.correlation_id IS 'Unique identifier for this execution chain';
COMMENT ON COLUMN execution_traces.root_id IS 'Points to the root trace in a nested execution';
COMMENT ON COLUMN execution_traces.parent_id IS 'Parent execution for nested/delegated executions';
EOF

# Test locally (requires Supabase connection)
# psql $DATABASE_URL -f services/intelligence/database/schema/001_execution_traces.sql
```

---

## Week 1: Foundation Sprint

### Track 1: Database Schema (Critical Path)

**Day 1-2: Core Tables**
```bash
# Create all schema files
cd /Volumes/PRO-G40/Code/Archon/services/intelligence/database/schema

# Files to create:
# 001_execution_traces.sql (done above)
# 002_agent_routing_decisions.sql
# 003_hook_executions.sql
# 004_endpoint_calls.sql
# 005_success_patterns.sql (with pgvector)
# 006_pattern_usage_log.sql
# 007_agent_chaining_patterns.sql
# 008_error_patterns.sql
# 009_indexes.sql

# Deploy to Supabase
for file in *.sql; do
    echo "Deploying $file..."
    psql $DATABASE_URL -f "$file"
done
```

**Day 3-4: Connection Pooling**
```python
# services/intelligence/database/connection.py
import asyncpg
from typing import Optional
import os

class DatabasePool:
    """Singleton database connection pool."""

    _instance: Optional['DatabasePool'] = None
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_instance(cls) -> 'DatabasePool':
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance._initialize_pool()
        return cls._instance

    async def _initialize_pool(self):
        """Initialize connection pool."""
        self._pool = await asyncpg.create_pool(
            dsn=os.getenv('DATABASE_URL'),
            min_size=10,
            max_size=50,
            command_timeout=60
        )

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Pool not initialized")
        return self._pool

    async def close(self):
        """Close all connections."""
        if self._pool:
            await self._pool.close()

# Test
if __name__ == "__main__":
    import asyncio

    async def test_connection():
        db = await DatabasePool.get_instance()
        async with db.pool.acquire() as conn:
            result = await conn.fetchval('SELECT 1')
            print(f"Connection test: {result}")

    asyncio.run(test_connection())
```

**Day 5: Validation & Handoff**
```bash
# Create validation script
cd /Volumes/PRO-G40/Code/Archon

cat > scripts/validate_database_schema.sh <<'EOF'
#!/bin/bash
# Validate database schema deployment

set -e

echo "Validating database schema..."

# Check all tables exist
TABLES=(
    "execution_traces"
    "agent_routing_decisions"
    "hook_executions"
    "endpoint_calls"
    "success_patterns"
    "pattern_usage_log"
    "agent_chaining_patterns"
    "error_patterns"
)

for table in "${TABLES[@]}"; do
    echo -n "Checking $table... "
    count=$(psql $DATABASE_URL -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='$table'")
    if [ "$count" -eq 1 ]; then
        echo "✓"
    else
        echo "✗ MISSING"
        exit 1
    fi
done

# Check pgvector extension
echo -n "Checking pgvector extension... "
has_pgvector=$(psql $DATABASE_URL -t -c "SELECT COUNT(*) FROM pg_extension WHERE extname='vector'")
if [ "$has_pgvector" -eq 1 ]; then
    echo "✓"
else
    echo "✗ MISSING"
    exit 1
fi

# Test connection pooling
echo "Testing connection pooling..."
python -c "
import asyncio
from services.intelligence.database.connection import DatabasePool

async def test():
    db = await DatabasePool.get_instance()
    async with db.pool.acquire() as conn:
        result = await conn.fetchval('SELECT COUNT(*) FROM execution_traces')
        print(f'Execution traces count: {result}')

asyncio.run(test())
"

echo ""
echo "✓ Database schema validation complete!"
echo "All tracks can now start parallel work."
EOF

chmod +x scripts/validate_database_schema.sh
./scripts/validate_database_schema.sh
```

---

## Week 2-4: Parallel Development

### Track 2: Hook System (Weeks 2-4)

**Week 2: Tracing Library**
```bash
# Create tracing utilities
mkdir -p ~/.claude/hooks/lib

cat > ~/.claude/hooks/lib/tracing_utils.sh <<'EOF'
#!/bin/bash
# Tracing utilities for correlation ID propagation and logging

# Configuration
ARCHON_INTELLIGENCE_URL="${ARCHON_INTELLIGENCE_URL:-http://localhost:8181}"

# Get correlation ID from environment or generate new
get_correlation_id() {
    echo "${ARCHON_CORRELATION_ID:-$(uuidgen)}"
}

# Get root trace ID
get_root_id() {
    echo "${ARCHON_ROOT_ID:-$(get_correlation_id)}"
}

# Get parent execution ID
get_parent_id() {
    echo "${ARCHON_PARENT_ID:-$(get_correlation_id)}"
}

# Start performance timer (milliseconds)
start_trace_timer() {
    # macOS compatible millisecond timestamp
    python3 -c "import time; print(int(time.time() * 1000))"
}

# Calculate duration from start time
calculate_duration() {
    local start_ms="$1"
    local end_ms=$(python3 -c "import time; print(int(time.time() * 1000))")
    echo $((end_ms - start_ms))
}

# Log trace event (async, non-blocking)
log_trace_event() {
    local event_type="$1"
    local event_data="$2"

    local correlation_id=$(get_correlation_id)
    local root_id=$(get_root_id)
    local parent_id=$(get_parent_id)
    local execution_id=$(uuidgen)

    # Async call (background, no waiting)
    curl -s -X POST "${ARCHON_INTELLIGENCE_URL}/api/traces/${event_type}" \
        -H "Content-Type: application/json" \
        -H "X-Correlation-ID: ${correlation_id}" \
        -H "X-Root-ID: ${root_id}" \
        -H "X-Parent-ID: ${parent_id}" \
        -H "X-Execution-ID: ${execution_id}" \
        -d "${event_data}" > /dev/null 2>&1 &
}

# Export all functions
export -f get_correlation_id
export -f get_root_id
export -f get_parent_id
export -f start_trace_timer
export -f calculate_duration
export -f log_trace_event
EOF

chmod +x ~/.claude/hooks/lib/tracing_utils.sh

# Test tracing library
source ~/.claude/hooks/lib/tracing_utils.sh
CORRELATION_ID=$(get_correlation_id)
echo "Generated correlation ID: $CORRELATION_ID"
START=$(start_trace_timer)
sleep 0.1
DURATION=$(calculate_duration "$START")
echo "Duration test: ${DURATION}ms"
```

**Week 3-4: Hook Updates**
```bash
# Update UserPromptSubmit hook
# See PARALLEL_BUILD_PLAN.md Track 2 for full implementation
# Key: Add correlation ID generation, export to environment, log to Archon
```

### Track 3: Pattern Learning Engine

#### 🚀 AI-Accelerated Approach (RECOMMENDED)

**NEW**: Track 3 now uses AI-accelerated implementation with 68% automated code generation.

**Timeline**: 22 days (vs 30 days manual)
**Automation**: 68% AI-generated code
**Quality**: +15% test coverage, +10% ONEX compliance

**Phase 1: Core Loop Foundation (Days 1-5) - AI-Powered**

**Step 1: Multi-Model Schema Consensus (Day 1)**
```bash
# Use Zen MCP for multi-model consensus on schema design
mcp__zen__consensus \
  --step "Design Pattern schema with fields: pattern_type (str), context (dict),
         success_criteria (dict), metadata (dict), provenance (dict), embedding (vector).
         Optimize for: PostgreSQL storage efficiency, Qdrant vector matching,
         ONEX compliance, eval framework integration" \
  --models '[
    {"model":"gemini-2.5-pro","stance":"for","rationale":"Storage optimization expert"},
    {"model":"codestral","stance":"neutral","rationale":"ONEX compliance validator"},
    {"model":"deepseek","stance":"against","rationale":"Devil'\''s advocate for edge cases"}
  ]' \
  --model gemini-2.5-pro

# Output: Consensus report with schema design and rationale
# Save to: /docs/design/pattern_schema_consensus.md
```

**Step 2: Codestral Storage Layer Generation (Day 1-2)**
```bash
# Generate PostgreSQL storage layer with Codestral (75% automation)
# Create prompt file for storage generation
cat > /tmp/storage_prompt.txt <<'EOF'
Generate Python storage layer for Pattern Learning Engine:

Schema (from consensus):
- pattern_id: UUID (primary key)
- pattern_type: Enum(agent_routing, hook_sequence, endpoint_chain)
- context: JSONB (user_request, domain, tags)
- success_criteria: JSONB (execution_completed, no_errors, quality_gates_passed)
- metadata: JSONB (extracted_at, source_correlation_id, usage_count)
- provenance: JSONB (source_traces, extraction_method, confidence_score)
- embedding: vector(1536) (OpenAI text-embedding-3-small)

Requirements:
- ONEX-compliant node architecture
- AsyncPG connection pooling
- Prepared statements for performance
- Transaction management
- Error handling with correlation IDs
- Type hints and Pydantic models
- Unit tests with pytest-asyncio

Generate files:
1. model_pattern.py - Pydantic Pattern model
2. node_pattern_storage_effect.py - Storage operations (CRUD)
3. model_contract_pattern_storage.py - Storage contract
4. test_pattern_storage.py - Unit tests
EOF

# Use AI agent to generate code
agent-code-generator \
  --prompt-file /tmp/storage_prompt.txt \
  --output-dir /Volumes/PRO-G40/Code/Archon/services/intelligence/src/services/pattern_learning \
  --model codestral \
  --onex-compliant \
  --test-coverage 90

# Human review: Focus on business logic, validate ONEX compliance
agent-code-quality-analyzer \
  --path /services/intelligence/src/services/pattern_learning \
  --check-compliance \
  --min-score 0.9
```

**Step 3: DeepSeek Extraction Algorithms (Day 2-3)**
```bash
# Generate pattern extraction algorithms with DeepSeek (70% automation)
cat > /tmp/extraction_prompt.txt <<'EOF'
Generate pattern extraction algorithms for successful execution traces:

Input: AssembledTrace (execution_trace + routing_decision + hook_executions + endpoint_calls)
Output: ExecutionPattern (pattern_type, context, success_criteria, metadata, provenance)

Algorithms needed:
1. Intent classification (user_request → intent: debug|develop|test|deploy)
2. Keyword extraction (user_request → keywords: List[str])
3. Execution path analysis (trace → path_signature: str)
4. Hook sequence pattern (hooks → sequence_hash: str)
5. Endpoint pattern (endpoints → call_pattern: str)
6. Success scoring (criteria → score: 0.0-1.0)

Requirements:
- Use OpenAI embeddings for intent classification
- TF-IDF for keyword extraction
- Graph algorithms for path analysis
- ONEX-compliant compute nodes
- Comprehensive error handling
- 85%+ test coverage

Generate files:
1. node_intent_classifier_compute.py
2. node_keyword_extractor_compute.py
3. node_execution_analyzer_compute.py
4. node_success_scorer_compute.py
5. node_pattern_assembler_orchestrator.py (coordinates all)
6. test_extraction_algorithms.py
EOF

# Generate with DeepSeek
agent-code-generator \
  --prompt-file /tmp/extraction_prompt.txt \
  --output-dir /services/intelligence/src/services/pattern_learning \
  --model deepseek-coder \
  --onex-compliant \
  --optimization-level high
```

**Step 4: Agent-Testing Auto-Generated Tests (Day 4)**
```bash
# Generate comprehensive test suite with agent-testing
agent-testing \
  --target-dir /services/intelligence/src/services/pattern_learning \
  --test-types unit,integration,property \
  --coverage-target 95 \
  --frameworks pytest,hypothesis \
  --async-support \
  --generate-fixtures

# Output: test_pattern_storage.py, test_extraction.py, test_integration.py
# Human review: Validate test scenarios cover edge cases
```

**Step 5: Integration & Validation (Day 5)**
```bash
# Run all tests
poetry run pytest services/intelligence/tests/services/pattern_learning/ -v --cov

# ONEX compliance check
agent-code-quality-analyzer \
  --path /services/intelligence/src/services/pattern_learning \
  --check-compliance \
  --check-patterns \
  --min-score 0.9

# Performance baseline
poetry run pytest services/intelligence/tests/performance/test_pattern_extraction.py

# Code review with multi-model consensus
mcp__zen__codereview \
  --relevant_files '[
    "/services/intelligence/src/services/pattern_learning/node_pattern_storage_effect.py",
    "/services/intelligence/src/services/pattern_learning/node_pattern_assembler_orchestrator.py"
  ]' \
  --step "Review Pattern Learning Phase 1 implementation for ONEX compliance,
         performance, error handling, and test coverage" \
  --model gemini-2.5-pro
```

**Phase 1 Artifacts (Reused in Later Phases)**:
- ✅ Pattern schema (Pydantic models)
- ✅ Storage interface (CRUD operations)
- ✅ Example patterns (test fixtures)
- ✅ ONEX compliance templates
- ✅ Performance benchmarks
- ✅ Integration test patterns

---

#### 📝 Traditional Approach (Manual Development)

**For teams without AI infrastructure or preferring manual control**

**Week 2-3: Pattern Extractor** (Manual Implementation)
```python
# services/intelligence/src/services/pattern_learning/pattern_extractor.py
from dataclasses import dataclass
from typing import List, Optional
import openai

@dataclass
class ExecutionPattern:
    """Learned execution pattern."""
    pattern_id: str
    source_correlation_id: str
    prompt_text: str
    prompt_embedding: List[float]
    intent: str
    keywords: List[str]
    execution_path: dict
    hook_sequence: List[dict]
    endpoint_pattern: List[dict]
    success_score: float

class PatternExtractor:
    """Extract reusable patterns from successful executions."""

    def __init__(self, openai_api_key: str):
        self.openai_client = openai.Client(api_key=openai_api_key)

    async def extract_pattern(
        self,
        trace: dict,
        success_criteria: dict
    ) -> Optional[ExecutionPattern]:
        """Extract pattern from successful trace."""

        # 1. Generate embedding
        embedding = await self._generate_embedding(trace['prompt_text'])

        # 2. Classify intent
        intent = await self._classify_intent(trace['prompt_text'])

        # 3. Extract keywords
        keywords = await self._extract_keywords(trace['prompt_text'])

        # 4. Build pattern
        return ExecutionPattern(
            pattern_id=str(uuid.uuid4()),
            source_correlation_id=trace['correlation_id'],
            prompt_text=trace['prompt_text'],
            prompt_embedding=embedding,
            intent=intent,
            keywords=keywords,
            execution_path=self._extract_execution_path(trace),
            hook_sequence=self._extract_hook_sequence(trace),
            endpoint_pattern=self._extract_endpoint_pattern(trace),
            success_score=success_criteria['score']
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate OpenAI embedding."""
        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

# Test
if __name__ == "__main__":
    import asyncio

    async def test():
        extractor = PatternExtractor(os.getenv('OPENAI_API_KEY'))

        # Mock trace
        trace = {
            'correlation_id': str(uuid.uuid4()),
            'prompt_text': 'debug API performance issue',
            'routing_decision': {'selected_agent': 'agent-debug-intelligence'},
            'hook_executions': [],
            'endpoint_calls': []
        }

        success_criteria = {'score': 0.95}

        pattern = await extractor.extract_pattern(trace, success_criteria)
        print(f"Pattern extracted: {pattern.pattern_id}")
        print(f"Intent: {pattern.intent}")
        print(f"Keywords: {pattern.keywords}")

    asyncio.run(test())
```

### Track 4: Router Integration (Weeks 5-6)

See PARALLEL_BUILD_PLAN.md Track 4 for full implementation.

### Track 5: Analytics (Weeks 3-6)

See PARALLEL_BUILD_PLAN.md Track 5 for full implementation.

---

## Integration Testing Schedule

### Week 4: First Integration Test
```bash
# Test: Hooks → Database → Pattern Extraction

# 1. Generate trace
echo "debug performance issue" | ~/.claude/hooks/user-prompt-submit-agent-enhancer.sh

# 2. Verify trace in database
psql $DATABASE_URL -c "SELECT correlation_id, prompt_text FROM execution_traces ORDER BY created_at DESC LIMIT 1;"

# 3. Extract pattern
curl -X POST http://localhost:8181/api/patterns/extract-recent \
  -H "Content-Type: application/json"

# 4. Verify pattern stored
psql $DATABASE_URL -c "SELECT pattern_id, intent FROM success_patterns ORDER BY created_at DESC LIMIT 1;"
```

### Week 6: Second Integration Test
```bash
# Test: Pattern Matching → Router

# 1. Match patterns
curl -X POST http://localhost:8181/api/patterns/match \
  -H "Content-Type: application/json" \
  -d '{"user_request": "debug API performance"}'

# 2. Router uses pattern
python -c "
from lib.enhanced_router import EnhancedAgentRouter
router = EnhancedAgentRouter()
recs = router.route('debug API performance issue')
print(f'Agent: {recs[0].agent_name}')
print(f'Using pattern: {hasattr(recs[0], \"pattern_id\")}')
"
```

### Week 8: Full End-to-End Test
See PARALLEL_BUILD_PLAN.md Week 8 section for complete E2E test.

---

## Daily Standup Template

**Track: [Track Number and Name]**
**Date**: [YYYY-MM-DD]
**Developer**: [Name]

**Yesterday**:
- Completed: [What was finished]
- Blockers: [Any issues encountered]

**Today**:
- Working on: [Current task]
- Expected completion: [When task will be done]

**Blockers/Dependencies**:
- Waiting on: [Any dependencies from other tracks]
- Needs help with: [Technical assistance needed]

---

## Performance Checklist

Run this checklist at each integration milestone:

### Trace Logging Performance
```bash
# Test: <5ms overhead
time (echo "test" | ~/.claude/hooks/user-prompt-submit-agent-enhancer.sh > /dev/null)
# Should show <5ms for tracing portion
```

### Pattern Matching Performance
```bash
# Test: <100ms total
time curl -X POST http://localhost:8181/api/patterns/match \
  -H "Content-Type: application/json" \
  -d '{"user_request": "debug performance"}'
# Should complete in <100ms
```

### Database Query Performance
```bash
# Test: <20ms per query
psql $DATABASE_URL -c "EXPLAIN ANALYZE SELECT * FROM execution_traces WHERE correlation_id = '...';"
# Execution time should be <20ms
```

---

## Emergency Rollback Plan

If a track encounters critical issues:

```bash
# Rollback Track 2 (Hooks)
git checkout main ~/.claude/hooks/
source ~/.claude/hooks/user-prompt-submit-agent-enhancer.sh  # Restore original

# Rollback Track 3 (Patterns)
curl -X DELETE http://localhost:8181/api/patterns/disable
# Disable pattern extraction and matching

# Rollback Track 4 (Router)
# Router has fallback to non-pattern routing built-in
# No action needed

# Rollback database changes
psql $DATABASE_URL -f services/intelligence/database/rollback_schema.sql
```

---

## Success Criteria Checklist

### Week 2 ✓
- [ ] Database schema deployed
- [ ] All tables exist and indexed
- [ ] Connection pooling working
- [ ] All tracks can access database

### Week 4 ✓
- [ ] Hooks generating traces
- [ ] Traces stored correctly
- [ ] Pattern extraction working
- [ ] First integration test passed

### Week 6 ✓
- [ ] Pattern matching active
- [ ] Router using patterns
- [ ] Performance targets met
- [ ] Second integration test passed

### Week 8 ✓
- [ ] Full E2E test passing
- [ ] All features implemented
- [ ] Performance validated
- [ ] Documentation complete

---

## Next Steps: Start Today!

1. **Create GitHub projects** (30 min)
2. **Assign teams to tracks** (15 min)
3. **Start Track 1 database schema** (TODAY!)
4. **Schedule Week 1 daily standups** (15 min)
5. **Set integration test dates** (Week 4, 6, 8)

**Ready to build? Let's go! 🚀**
