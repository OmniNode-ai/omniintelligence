# Problem Statement: Intelligence Adapter Event Handler

**Created**: 2025-10-21
**Status**: 🔴 Blocking - Integration test failing
**Priority**: P0 - Critical path for event bus integration

## The Problem

The Intelligence service consumes `CODE_ANALYSIS_REQUESTED` events from Kafka/Redpanda but **does not process them** because no event handler is registered.

### Observable Symptoms

1. **Integration test timeout** - Test publishes event and waits 30s for response, receives nothing
2. **Service logs show consumption but no processing**:
   ```
   INFO:src.kafka_consumer:Processing event: type=omninode.intelligence.event.code_analysis_requested.v1
   WARNING:src.kafka_consumer:No handler found for event type: omninode.intelligence.event.code_analysis_requested.v1
   INFO:src.kafka_consumer:Event processed successfully: duration=0.08ms
   ```
3. **No `CODE_ANALYSIS_COMPLETED` or `FAILED` events published** - Event flow is one-way

### Root Cause

The `IntelligenceAdapterEventHandler` **does not exist**. Previous session summary incorrectly marked it as "completed" in todo list, but:
- Handler file doesn't exist in codebase
- Not registered in `kafka_consumer.py`
- Never implemented

Current handlers in `kafka_consumer.py`:
- `CodegenValidationHandler` - for codegen validation
- `CodegenAnalysisHandler` - for codegen analysis
- `CodegenPatternHandler` - for pattern matching
- `CodegenMixinHandler` - for mixin recommendations

**Missing**: Handler for `omninode.intelligence.event.code_analysis_requested.v1`

## What We're Building

### Event Flow (Target State)

```
┌─────────────────────────────────────────────────────────────────┐
│  Test/Client                                                     │
│  └─> Publishes CODE_ANALYSIS_REQUESTED                         │
└────────────────────┬────────────────────────────────────────────┘
                     │ Redpanda Topic:
                     │ dev.archon-intelligence.code-analysis-requested.v1
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│  Intelligence Service (Docker Container)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Kafka Consumer                                           │  │
│  │  └─> Receives event from Redpanda                        │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       ↓                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ❌ IntelligenceAdapterEventHandler (MISSING)            │  │
│  │  └─> Should process event and analyze code               │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       ↓                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Kafka Producer                                           │  │
│  │  └─> Publishes CODE_ANALYSIS_COMPLETED/FAILED            │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────────┘
                     │ Redpanda Topics:
                     │ dev.archon-intelligence.code-analysis-completed.v1
                     │ dev.archon-intelligence.code-analysis-failed.v1
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│  Test/Client                                                     │
│  └─> Receives response event with results                       │
└─────────────────────────────────────────────────────────────────┘
```

### Handler Requirements

The handler must:

1. **Consume events** from `dev.archon-intelligence.code-analysis-requested.v1`
2. **Provide full intelligence suite**:
   - Quality assessment (ONEX compliance, complexity metrics)
   - Pattern matching (18 quality patterns, 21 architectural patterns)
   - RAG search (similar code examples, documentation)
   - Entity extraction (functions, classes, relationships)
3. **Deduplicate via metadata stamping** (Bridge service at localhost:8057)
4. **Execute operations in parallel** (asyncio.gather for performance)
5. **Support flexible operation types**:
   - `QUALITY_ASSESSMENT` - Quality scorer only
   - `COMPREHENSIVE_ANALYSIS` - All services in parallel
   - `RAG_SEARCH` - RAG + patterns only
   - `ENTITY_EXTRACTION` - Entities only
6. **Publish response events**:
   - `CODE_ANALYSIS_COMPLETED` on success
   - `CODE_ANALYSIS_FAILED` on error
7. **Preserve correlation ID** throughout event flow

### Performance Targets

- **Quality assessment**: < 2s
- **Comprehensive analysis**: < 5s (300-1000ms for RAG is acceptable if intelligence is better)
- **Metadata stamp check**: < 100ms
- **Event processing**: < 50ms overhead

## Technical Context

### Existing Infrastructure ✅

1. **Docker services running**:
   - `archon-intelligence` (port 8053) - Intelligence service with Kafka consumer
   - `archon-bridge` (port 8054) - Bridge with metadata stamping
   - `omninode-bridge-metadata-stamping` (port 8057) - BLAKE3 content hashing
   - `omninode-bridge-redpanda` (ports 29092, 29102) - Kafka event bus
   - `archon-memgraph` (port 7687) - Knowledge graph

2. **Services initialized in Intelligence consumer**:
   - `quality_scorer` (ComprehensiveONEXScorer)
   - `pattern_service` (pattern matching)
   - `langextract_service` (entity extraction)
   - Memgraph driver (knowledge graph)

3. **Event contracts defined**:
   - `ModelCodeAnalysisRequestPayload`
   - `ModelCodeAnalysisCompletedPayload`
   - `ModelCodeAnalysisFailedPayload`
   - Helper functions: `create_request_event()`, `create_completed_event()`, `create_failed_event()`

4. **Integration test ready**:
   - `/Volumes/PRO-G40/Code/omniarchon/python/tests/intelligence/integration/test_intelligence_event_flow_real.py`
   - Uses **real Redpanda** (no mocks)
   - Tests end-to-end flow with correlation ID tracking

### Configuration

**Kafka Topics** (all prefixed with `dev.archon-intelligence.intelligence.`):
- `code-analysis-requested.v1` (consume)
- `code-analysis-completed.v1` (produce)
- `code-analysis-failed.v1` (produce)

**Environment** (.env file):
```bash
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092  # Internal Docker network
KAFKA_ENABLE_CONSUMER=true
INTELLIGENCE_SERVICE_PORT=8053
MEMGRAPH_URI=bolt://memgraph:7687
```

**Event Type String**: `omninode.intelligence.event.code_analysis_requested.v1`

## Design Decisions Made

### 1. Monolithic Handler (Temporary)
**Decision**: Build one handler that orchestrates all intelligence operations
**Rationale**:
- Validates integration quickly
- Proves event contract works
- Easy to split later when we have performance data

**Future**: Split into separate Effect nodes per operation type

### 2. Async/Parallel by Default
**Decision**: Use `asyncio.gather()` to run services in parallel
**Rationale**:
- Better performance (1s total vs 3s sequential)
- Natural fit for IO-bound operations
- Graceful degradation with `return_exceptions=True`

### 3. Metadata Stamping for Deduplication
**Decision**: Call Bridge stamping service (port 8057) before analysis
**Rationale**:
- BLAKE3 content hashing avoids redundant analysis
- Bridge service already has this functionality
- Can cache results by hash

### 4. Flexible Operation Routing
**Decision**: Support multiple operation types, don't force all services
**Rationale**:
- Client may only want quality assessment (fast)
- Or only want RAG search
- Comprehensive analysis runs everything

## Success Criteria

### Must Have (MVP)
- [ ] Handler registered in `kafka_consumer.py`
- [ ] Consumes `CODE_ANALYSIS_REQUESTED` events
- [ ] Calls quality scorer and returns results
- [ ] Publishes `CODE_ANALYSIS_COMPLETED` event
- [ ] Preserves correlation ID
- [ ] Integration test passes (3 test cases)

### Should Have (Phase 1)
- [ ] Metadata stamping integration (deduplication)
- [ ] Parallel execution of quality + patterns
- [ ] Graceful degradation (continue if RAG fails)
- [ ] Error handling with `CODE_ANALYSIS_FAILED` events

### Nice to Have (Phase 2)
- [ ] Full RAG search integration
- [ ] Entity extraction + knowledge graph indexing
- [ ] Performance metrics tracking
- [ ] Circuit breaker for resilience

## Next Steps

1. **Create handler file**: `services/intelligence/src/handlers/intelligence_adapter_event_handler.py`
2. **Implement core logic**: Quality assessment + event response
3. **Register handler**: Add to `kafka_consumer.py` handler list
4. **Rebuild Docker image**: `docker compose up archon-intelligence --build`
5. **Run integration test**: Verify end-to-end event flow

## References

- Event contract: `services/intelligence/src/events/models/intelligence_adapter_events.py`
- Existing handler pattern: `services/intelligence/src/handlers/codegen_validation_handler.py`
- Database adapter pattern: `omninode_bridge/src/omninode_bridge/nodes/database_adapter_effect/v1_0_0/node.py`
- Integration test: `python/tests/intelligence/integration/test_intelligence_event_flow_real.py`
- Kafka config: `services/intelligence/src/kafka_topics_config.py`

---

**Problem Owner**: Intelligence Team
**Blocking**: Event bus integration, production deployment
**Estimated Effort**: 4-6 hours (monolithic handler) or 13-17 hours (full Effect node with Pollys)
