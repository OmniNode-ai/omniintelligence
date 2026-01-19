# ONEX Node Mapping Reference

Quick reference for mapping Omniarchon components to ONEX nodes.

---

## Node Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│              INTELLIGENCE ORCHESTRATOR (Unified)                 │
│               (NodeOmniAgentOrchestrator)                        │
│                                                                   │
│  Handles ALL Workflows via operation_type enum:                  │
│  • DOCUMENT_INGESTION → document_ingestion_workflow             │
│  • PATTERN_LEARNING → pattern_learning_workflow                 │
│  • QUALITY_ASSESSMENT → quality_assessment_workflow             │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  REDUCER    │  │   COMPUTE   │  │   EFFECTS   │
│  (Unified)  │  │   (Pure)    │  │  (I/O)      │
├─────────────┤  ├─────────────┤  ├─────────────┤
│ Handles     │  │ Vectorize   │  │ Kafka       │
│ ALL FSMs:   │  │ Extract     │  │ Qdrant      │
│ • Ingest    │  │ Match       │  │ Memgraph    │
│ • Pattern   │  │ Score       │  │ PostgreSQL  │
│ • Quality   │  │ Analyze     │  │ API Gateway │
│ via enum    │  │ Detect      │  │             │
└─────────────┘  └─────────────┘  └─────────────┘
       │                                  ▲
       └──────────(intents)──────────────┘
```

---

## Complete Node Inventory

### 1 Unified Orchestrator Node

| Node Name | Class | Purpose | Workflows Handled |
|-----------|-------|---------|-------------------|
| `intelligence_orchestrator` | NodeOmniAgentOrchestrator | **Coordinates ALL intelligence workflows via operation_type enum** | document_ingestion, pattern_learning, quality_assessment, semantic_enrichment |

### 1 Unified Reducer Node

| Node Name | Class | FSMs Handled | Database Table |
|-----------|-------|--------------|----------------|
| `intelligence_reducer` | NodeOmniAgentReducer | **ALL FSMs via fsm_type enum:** INGESTION (RECEIVED → INDEXED), PATTERN_LEARNING (FOUNDATION → TRACEABILITY), QUALITY_ASSESSMENT (RAW → STORED) | `fsm_state` (unified) |

### 6 Compute Nodes

| Node Name | Class | Input Type | Output Type | Pure Function |
|-----------|-------|------------|-------------|---------------|
| `vectorization_compute` | NodeCompute | ModelVectorizationInput | ModelVectorizationOutput | text → embeddings |
| `entity_extraction_compute` | NodeCompute | ModelEntityExtractionInput | ModelEntityExtractionOutput | code → entities |
| `pattern_matching_compute` | NodeCompute | ModelPatternMatchingInput | ModelPatternMatchingOutput | code + patterns → matches |
| `quality_scoring_compute` | NodeCompute | ModelQualityScoringInput | ModelQualityScoringOutput | metrics → score |
| `semantic_analysis_compute` | NodeCompute | ModelSemanticAnalysisInput | ModelSemanticAnalysisOutput | code → semantic_features |
| `relationship_detection_compute` | NodeCompute | ModelRelationshipDetectionInput | ModelRelationshipDetectionOutput | entities → relationships |

### 5 Effect Nodes

| Node Name | Class | Operations | External System |
|-----------|-------|------------|-----------------|
| `ingestion_effect` | NodeEffectService | PUBLISH_EVENT, CONSUME_EVENTS, PUBLISH_DLQ | Kafka/Redpanda |
| `qdrant_vector_effect` | NodeEffectService | INDEX_VECTORS, SEARCH_VECTORS, DELETE_VECTORS | Qdrant |
| `memgraph_graph_effect` | NodeEffectService | CREATE_NODES, CREATE_RELATIONSHIPS, QUERY_GRAPH | Memgraph |
| `postgres_pattern_effect` | NodeEffectService | STORE_PATTERN, QUERY_PATTERNS, TRACK_LINEAGE, UPDATE_STATE | PostgreSQL |
| `intelligence_api_effect` | NodeEffectService | HANDLE_REQUEST, STREAM_RESPONSE, BATCH_REQUEST | HTTP API |

---

## Omniarchon → ONEX Mapping

### Intelligence Service APIs (78 endpoints)

| Omniarchon Module | API Count | ONEX Node | Node Type | Notes |
|-------------------|-----------|-----------|-----------|-------|
| **Bridge Intelligence** | 3 | `intelligence_api_effect` | Effect | HTTP endpoints |
| **Code Intelligence** | 4 | `entity_extraction_compute` | Compute | Pure extraction |
| **Pattern Learning (Phase 2)** | 7 | `pattern_matching_compute` | Compute | Pure matching |
| **Pattern Traceability (Phase 4)** | 11 | `pattern_learning_reducer` | Reducer | FSM with lineage |
| **Quality Scoring** | 6 | `quality_scoring_compute` | Compute | Pure scoring |
| **Performance Optimization** | 5 | `quality_assessment_reducer` | Reducer | FSM with analysis |
| **Document Freshness** | 9 | `intelligence_orchestrator` | Orchestrator | Workflow coordination |
| **Pattern Analytics** | 5 | `intelligence_api_effect` | Effect | Analytics API |
| **Custom Quality Rules** | 8 | `quality_scoring_compute` | Compute | Rule evaluation |
| **Quality Trends** | 7 | `postgres_pattern_effect` | Effect | Trend persistence |
| **Performance Analytics** | 6 | `intelligence_api_effect` | Effect | Analytics API |
| **Usage Tracking** | 7 | `postgres_pattern_effect` | Effect | Usage persistence |

### Event Handlers (20 handlers)

| Omniarchon Handler | ONEX Node | Processing Pattern |
|--------------------|-----------|-------------------|
| `QualityAssessmentHandler` | `intelligence_reducer` | FSM_TYPE.QUALITY_ASSESSMENT: RAW → SCORED |
| `PatternLearningHandler` | `intelligence_reducer` | FSM_TYPE.PATTERN_LEARNING: FOUNDATION → TRACEABILITY |
| `DocumentProcessingHandler` | `intelligence_reducer` | FSM_TYPE.INGESTION: RECEIVED → INDEXED |
| `PerformanceHandler` | `intelligence_reducer` | FSM_TYPE.QUALITY_ASSESSMENT with metrics |
| `FreshnessHandler` | `intelligence_reducer` | FSM_TYPE.INGESTION state update |
| `PatternTraceabilityHandler` | `intelligence_reducer` | FSM_TYPE.PATTERN_LEARNING lineage tracking |
| `CodegenValidationHandler` | `quality_scoring_compute` | Pure validation |
| `AutonomousLearningHandler` | `pattern_matching_compute` | Pure learning |
| All other handlers | `intelligence_orchestrator` | Workflow steps |

### Kafka Topics (8 topics)

| Topic | Producer Node | Consumer Node | Purpose |
|-------|---------------|---------------|---------|
| `enrichment.requested.v1` | `ingestion_effect` | `intelligence_orchestrator` | Trigger ingestion workflow |
| `code-analysis.requested.v1` | `ingestion_effect` | `intelligence_orchestrator` | Trigger analysis workflow |
| `quality.assessed.v1` | `quality_assessment_reducer` | `intelligence_api_effect` | Quality results |
| `pattern.matched.v1` | `pattern_learning_reducer` | `postgres_pattern_effect` | Pattern results |
| `tree.discover.v1` | External | `intelligence_orchestrator` | Tree discovery trigger |
| `tree.index.v1` | External | `ingestion_reducer` | Tree indexing trigger |
| `stamping.generate.v1` | External | `intelligence_orchestrator` | ONEX stamping trigger |
| `*.failed.v1` | Any reducer | `ingestion_effect` | DLQ for failures |

### Database Operations

| Database | Omniarchon Usage | ONEX Effect Node | Operations |
|----------|------------------|------------------|------------|
| **Qdrant** | Vector search, 2+ collections | `qdrant_vector_effect` | INDEX_VECTORS, SEARCH_VECTORS, DELETE_VECTORS, CREATE_COLLECTION |
| **Memgraph** | Knowledge graph, 7+ node types | `memgraph_graph_effect` | CREATE_NODES, CREATE_RELATIONSHIPS, QUERY_GRAPH, TRAVERSE_PATH |
| **PostgreSQL** | Pattern traceability, lineage | `postgres_pattern_effect` | STORE_PATTERN, QUERY_PATTERNS, TRACK_LINEAGE, UPDATE_STATE |
| **Valkey** | Cache (512MB LRU, 300s TTL) | Intent: CACHE_WRITE/READ | Via intents from reducers |

---

## Workflow Mappings

### 1. Document Ingestion Workflow

**Omniarchon Flow**:
```
Kafka enrichment.requested.v1
  → IntelligenceConsumer._process_enrichment_event()
    → DocumentProcessingHandler
      → Entity extraction
      → Vectorization
      → Qdrant indexing
      → Memgraph storage
        → Publish completion event
```

**ONEX Flow**:
```
Kafka enrichment.requested.v1
  → intelligence_orchestrator (operation_type: DOCUMENT_INGESTION)
    Step 1: entity_extraction_compute (code → entities)
    Step 2: vectorization_compute (text → embeddings)
    Step 3: intelligence_reducer (fsm_type: INGESTION, RECEIVED → PARSED)
    Step 4: qdrant_vector_effect (INDEX_VECTORS)
    Step 5: memgraph_graph_effect (CREATE_NODES)
    Step 6: intelligence_reducer (fsm_type: INGESTION, PARSED → INDEXED)
    Step 7: ingestion_effect (PUBLISH_EVENT: completion)
```

### 2. Pattern Learning Workflow (4 Phases)

**Omniarchon Flow**:
```
Phase 1: Foundation patterns loaded
Phase 2: PatternLearningHandler matches against codebase
Phase 3: Validation and scoring
Phase 4: PatternTraceabilityHandler tracks lineage
```

**ONEX Flow**:
```
intelligence_orchestrator (operation_type: PATTERN_LEARNING)
  Step 1: intelligence_reducer (fsm_type: PATTERN_LEARNING, INIT → FOUNDATION)
    → Intent: DATA_FETCH (load foundation patterns)
  Step 2: pattern_matching_compute (code + patterns → matches)
  Step 3: intelligence_reducer (fsm_type: PATTERN_LEARNING, FOUNDATION → MATCHING)
    → Intent: STATE_UPDATE (store matches)
  Step 4: quality_scoring_compute (validate pattern quality)
  Step 5: intelligence_reducer (fsm_type: PATTERN_LEARNING, MATCHING → VALIDATION)
  Step 6: postgres_pattern_effect (TRACK_LINEAGE)
  Step 7: intelligence_reducer (fsm_type: PATTERN_LEARNING, VALIDATION → TRACEABILITY)
    → Intent: EVENT_PUBLISH (pattern.completed.v1)
```

### 3. Quality Assessment Workflow

**Omniarchon Flow**:
```
POST /assess/code
  → QualityAssessmentHandler
    → Quality scoring
    → ONEX compliance check
    → Store trends
      → Return quality report
```

**ONEX Flow**:
```
intelligence_orchestrator (operation_type: QUALITY_ASSESSMENT)
  Step 1: quality_scoring_compute (metrics → score)
  Step 2: intelligence_reducer (fsm_type: QUALITY_ASSESSMENT, RAW → ANALYZED)
    → Intent: STATE_UPDATE (store metrics)
  Step 3: semantic_analysis_compute (code → features)
  Step 4: intelligence_reducer (fsm_type: QUALITY_ASSESSMENT, ANALYZED → SCORED)
    → Intent: CACHE_WRITE (cache score, TTL 300s)
  Step 5: postgres_pattern_effect (UPDATE_STATE: store trends)
  Step 6: intelligence_reducer (fsm_type: QUALITY_ASSESSMENT, SCORED → COMPLETED)
    → Intent: EVENT_PUBLISH (quality.assessed.v1)
```

---

## Intent Flow Examples

### Example 1: Ingestion Reducer State Update

**Reducer emits**:
```python
ModelIntent(
    intent_type=EnumIntentType.STATE_UPDATE,
    target="postgres_pattern_effect",
    payload={
        "table": "ingestion_state",
        "document_id": "doc-123",
        "updates": {
            "current_state": "VECTORIZED",
            "previous_state": "PARSED"
        }
    }
)
```

**Effect executes**:
```sql
UPDATE ingestion_state
SET current_state = 'VECTORIZED',
    previous_state = 'PARSED',
    updated_at = NOW()
WHERE document_id = 'doc-123';
```

### Example 2: Pattern Reducer Workflow Trigger

**Reducer emits**:
```python
ModelIntent(
    intent_type=EnumIntentType.WORKFLOW_TRIGGER,
    target="intelligence_orchestrator",
    payload={
        "workflow": "pattern_learning_workflow",
        "pattern_id": "pattern-456",
        "next_step": "validate_patterns"
    }
)
```

**Orchestrator executes**:
```python
# Resume workflow at specific step
await self.resume_workflow(
    workflow_id="pattern_learning_workflow",
    context={"pattern_id": "pattern-456"},
    starting_step="validate_patterns"
)
```

### Example 3: Quality Reducer Cache Write

**Reducer emits**:
```python
ModelIntent(
    intent_type=EnumIntentType.CACHE_WRITE,
    target="valkey_cache",
    payload={
        "key": "quality:file:/src/main.py",
        "value": {"score": 8.5, "dimensions": {...}},
        "ttl_seconds": 300
    }
)
```

**Cache effect executes**:
```python
await redis.setex(
    "quality:file:/src/main.py",
    300,
    json.dumps({"score": 8.5, "dimensions": {...}})
)
```

---

## Contract Examples

### Orchestrator Contract

```yaml
# src/omniintelligence/nodes/intelligence_orchestrator/v1_0_0/contracts/orchestrator_contract.yaml

node_type: orchestrator
node_name: intelligence_orchestrator
version: 1.0.0

workflows:
  - workflow_id: document_ingestion_workflow
    trigger_events:
      - dev.intelligence.enrichment.requested.v1
    steps: 7
    timeout_ms: 30000

  - workflow_id: pattern_learning_workflow
    trigger_events:
      - dev.intelligence.pattern.learning.requested.v1
    steps: 7
    timeout_ms: 60000

capabilities:
  - WORKFLOW_COORDINATION
  - MULTI_STEP_ORCHESTRATION
  - LEASE_MANAGEMENT
  - COMPENSATION_LOGIC
```

### Unified Reducer Contract

```yaml
# src/omniintelligence/nodes/intelligence_reducer/v1_0_0/contracts/reducer_contract.yaml

node_type: reducer
node_name: intelligence_reducer
version: 1.0.0

fsm_types:
  - INGESTION
  - PATTERN_LEARNING
  - QUALITY_ASSESSMENT

state_machines:
  INGESTION:
    states:
      - RECEIVED
      - PARSED
      - VECTORIZED
      - INDEXED
      - COMPLETED
      - FAILED
    transitions:
      - from: RECEIVED
        to: PARSED
        event: PARSE_COMPLETED
      - from: PARSED
        to: VECTORIZED
        event: VECTORIZATION_COMPLETED
      - from: VECTORIZED
        to: INDEXED
        event: INDEXING_COMPLETED
      - from: INDEXED
        to: COMPLETED
        event: PROCESSING_COMPLETED

  PATTERN_LEARNING:
    states:
      - FOUNDATION
      - MATCHING
      - VALIDATION
      - TRACEABILITY
      - COMPLETED
    transitions:
      - from: FOUNDATION
        to: MATCHING
        event: FOUNDATION_LOADED
      - from: MATCHING
        to: VALIDATION
        event: PATTERNS_MATCHED
      - from: VALIDATION
        to: TRACEABILITY
        event: PATTERNS_VALIDATED
      - from: TRACEABILITY
        to: COMPLETED
        event: LINEAGE_TRACKED

  QUALITY_ASSESSMENT:
    states:
      - RAW
      - ANALYZED
      - SCORED
      - STORED
      - COMPLETED
    transitions:
      - from: RAW
        to: ANALYZED
        event: ANALYSIS_COMPLETED
      - from: ANALYZED
        to: SCORED
        event: SCORING_COMPLETED
      - from: SCORED
        to: STORED
        event: STORAGE_COMPLETED
      - from: STORED
        to: COMPLETED
        event: PROCESSING_COMPLETED

intents_emitted:
  - STATE_UPDATE
  - WORKFLOW_TRIGGER
  - EVENT_PUBLISH
  - CACHE_WRITE
  - DATA_FETCH
  - LOG
  - METRIC

purity_guarantee: true
state_persistence: database
unified_table: fsm_state
```

### Compute Contract

```yaml
# src/omniintelligence/nodes/vectorization_compute/v1_0_0/contracts/compute_contract.yaml

node_type: compute
node_name: vectorization_compute
version: 1.0.0

operations:
  - operation_id: GENERATE_EMBEDDINGS
    input_schema: ModelVectorizationInput
    output_schema: ModelVectorizationOutput
    timeout_ms: 10000
    pure: true

  - operation_id: BATCH_VECTORIZE
    input_schema: ModelBatchVectorizationInput
    output_schema: ModelBatchVectorizationOutput
    timeout_ms: 60000
    pure: true

performance_targets:
  - operation: GENERATE_EMBEDDINGS
    p95_ms: 1000
    p99_ms: 2000

  - operation: BATCH_VECTORIZE
    p95_ms: 5000
    p99_ms: 10000
```

### Effect Contract

```yaml
# src/omniintelligence/nodes/ingestion_effect/v1_0_0/contracts/effect_contract.yaml

node_type: effect
node_name: ingestion_effect
version: 1.0.0

operations:
  - operation_id: PUBLISH_EVENT
    external_system: kafka
    timeout_ms: 3000
    retry_policy:
      max_attempts: 3
      backoff_ms: 1000

  - operation_id: PUBLISH_DLQ
    external_system: kafka
    timeout_ms: 3000
    retry_policy:
      max_attempts: 1

circuit_breaker:
  failure_threshold: 5
  recovery_timeout_ms: 60000
  half_open_max_calls: 3

external_dependencies:
  - name: kafka
    endpoints:
      - omninode-bridge-redpanda:9092
    health_check: /health
```

---

## Directory Structure

```
src/omniintelligence/nodes/
├── intelligence_orchestrator/
│   └── v1_0_0/
│       ├── node.py                          # NodeOmniAgentOrchestrator (unified)
│       ├── models/
│       │   ├── input.py                     # ModelOrchestratorInput
│       │   ├── output.py                    # ModelOrchestratorOutput
│       │   └── config.py                    # ModelOrchestratorConfig
│       ├── enums/
│       │   └── operation_type.py            # EnumOperationType (routing enum)
│       ├── contracts/
│       │   ├── orchestrator_contract.yaml
│       │   └── workflows/
│       │       ├── document_ingestion.yaml
│       │       ├── pattern_learning.yaml
│       │       └── quality_assessment.yaml
│       ├── workflows/
│       │   ├── base_workflow.py
│       │   ├── document_ingestion.py
│       │   ├── pattern_learning.py
│       │   └── quality_assessment.py
│       └── utils/
│           ├── workflow_loader.py
│           └── lease_manager.py
│
├── intelligence_reducer/
│   └── v1_0_0/
│       ├── node.py                          # NodeOmniAgentReducer (unified)
│       ├── models/
│       │   ├── input.py                     # ModelReducerInput
│       │   ├── output.py                    # ModelReducerOutput
│       │   └── config.py                    # ModelReducerConfig
│       ├── enums/
│       │   ├── fsm_type.py                  # EnumFSMType (routing enum)
│       │   ├── ingestion_state.py           # EnumIngestionState
│       │   ├── pattern_state.py             # EnumPatternLearningState
│       │   └── quality_state.py             # EnumQualityState
│       ├── contracts/
│       │   └── reducer_contract.yaml
│       └── utils/
│           ├── ingestion_fsm.py             # Pure ingestion logic
│           ├── pattern_fsm.py               # Pure pattern logic
│           └── quality_fsm.py               # Pure quality logic
│
├── vectorization_compute/
│   └── v1_0_0/
│       ├── node.py                          # NodeCompute
│       ├── models/
│       ├── enums/
│       ├── contracts/
│       └── utils/
│           └── embedding_generator.py       # Pure function
│
└── ingestion_effect/
    └── v1_0_0/
        ├── node.py                          # NodeEffectService
        ├── models/
        ├── enums/
        ├── contracts/
        └── utils/
            ├── producer.py
            └── consumer.py
```

---

## Migration Checklist

### Phase 1: Foundation
- [ ] All node directories created
- [ ] All contract YAML files defined
- [ ] Shared models and enums implemented
- [ ] Database schemas created
- [ ] Intent routing system implemented

### Phase 2: Compute Nodes
- [ ] Vectorization compute
- [ ] Entity extraction compute
- [ ] Pattern matching compute
- [ ] Quality scoring compute
- [ ] Semantic analysis compute
- [ ] Relationship detection compute

### Phase 3: Effect Nodes
- [ ] Kafka event effect
- [ ] Qdrant vector effect
- [ ] Memgraph graph effect
- [ ] PostgreSQL pattern effect
- [ ] Intelligence API effect

### Phase 4: Unified Reducer
- [ ] Intelligence reducer (unified, pure FSM)
- [ ] Ingestion FSM (within unified reducer)
- [ ] Pattern learning FSM (within unified reducer)
- [ ] Quality assessment FSM (within unified reducer)
- [ ] FSM routing via fsm_type enum

### Phase 5: Unified Orchestrator
- [ ] Intelligence orchestrator
- [ ] Llama Index workflow integration
- [ ] All 3 workflows implemented
- [ ] Lease management
- [ ] Compensation logic

### Phase 6: Testing
- [ ] Unit tests (>90% coverage)
- [ ] Integration tests (all workflows)
- [ ] Contract validation tests
- [ ] Performance benchmarks
- [ ] End-to-end tests

---

## Quick Commands

```bash
# Generate node scaffold (when available)
python -m omnibase_core.scripts.generate_node \
  --node-type orchestrator \
  --node-name intelligence_orchestrator \
  --domain intelligence \
  --output src/omniintelligence/nodes

# Run tests for specific node
pytest src/omniintelligence/nodes/ingestion_reducer/v1_0_0/node_tests/

# Validate contracts
python -m omnibase_core.validators.contract_validator \
  --contract src/omniintelligence/nodes/intelligence_orchestrator/v1_0_0/contracts/orchestrator_contract.yaml

# Run integration tests
pytest tests/integration/test_document_ingestion_workflow.py

# Performance benchmarks
pytest -m performance tests/performance/
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Related**: [ONEX Migration Plan](./ONEX_MIGRATION_PLAN.md), [Omniarchon Inventory](../../OMNIARCHON_MIGRATION_INVENTORY.md)
