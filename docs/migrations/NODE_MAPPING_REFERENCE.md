# ONEX Node Mapping Reference

Quick reference for mapping Omniarchon components to ONEX nodes.

---

## Node Architecture Summary

```
                           ORCHESTRATORS
         ┌───────────────────────────────────────────────┐
         │      NodeIntelligenceOrchestrator             │
         │      NodePatternAssemblerOrchestrator         │
         │                                               │
         │  Handles ALL Workflows via operation_type:    │
         │  - DOCUMENT_INGESTION                         │
         │  - PATTERN_LEARNING                           │
         │  - QUALITY_ASSESSMENT                         │
         │  - PATTERN_ASSEMBLY                           │
         └──────────────────────┬────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
   │     REDUCER     │ │     COMPUTE     │ │     EFFECTS     │
   │    (Unified)    │ │     (Pure)      │ │      (I/O)      │
   ├─────────────────┤ ├─────────────────┤ ├─────────────────┤
   │ NodeIntelligence│ │ 11 Compute      │ │ 6 Effect        │
   │ Reducer         │ │ Nodes           │ │ Nodes           │
   │                 │ │                 │ │                 │
   │ Handles ALL     │ │ - Vectorization │ │ - Kafka         │
   │ FSMs via        │ │ - Entity Extr.  │ │ - Qdrant        │
   │ fsm_type enum:  │ │ - Pattern Match │ │ - Memgraph      │
   │ - INGESTION     │ │ - Quality Score │ │ - PostgreSQL    │
   │ - PATTERN       │ │ - Semantic      │ │ - API Gateway   │
   │ - QUALITY       │ │ - Intent Class. │ │ - Adapter       │
   └─────────────────┘ └─────────────────┘ └─────────────────┘
           │                                        ▲
           └────────────(intents)───────────────────┘
```

---

## Complete Node Inventory (20 Nodes)

### 2 Orchestrator Nodes

| Node Directory | Class Name | Purpose | Status |
|----------------|------------|---------|--------|
| `intelligence_orchestrator` | `NodeIntelligenceOrchestrator` | Coordinates ALL intelligence workflows via operation_type enum | Active |
| `pattern_assembler_orchestrator` | `NodePatternAssemblerOrchestrator` | Coordinates pattern assembly workflows | Active |

### 1 Unified Reducer Node

| Node Directory | Class Name | FSMs Handled | Database Table | Status |
|----------------|------------|--------------|----------------|--------|
| `intelligence_reducer` | `NodeIntelligenceReducer` | **ALL FSMs via fsm_type enum:** INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT | `fsm_state` (unified) | Active |

### 11 Compute Nodes

| Node Directory | Class Name | Input Type | Output Type | Status |
|----------------|------------|------------|-------------|--------|
| `vectorization_compute` | `NodeVectorizationCompute` | ModelVectorizationInput | ModelVectorizationOutput | Active |
| `entity_extraction_compute` | `NodeEntityExtractionCompute` | ModelEntityExtractionInput | ModelEntityExtractionOutput | Active |
| `pattern_matching_compute` | `NodePatternMatchingCompute` | ModelPatternMatchingInput | ModelPatternMatchingOutput | Active |
| `quality_scoring_compute` | `NodeQualityScoringCompute` | ModelQualityScoringInput | ModelQualityScoringOutput | Active |
| `semantic_analysis_compute` | `NodeSemanticAnalysisCompute` | ModelSemanticAnalysisInput | ModelSemanticAnalysisOutput | Active |
| `relationship_detection_compute` | `NodeRelationshipDetectionCompute` | ModelRelationshipDetectionInput | ModelRelationshipDetectionOutput | Active |
| `context_keyword_extractor_compute` | `NodeContextKeywordExtractorCompute` | ModelContextKeywordInput | ModelContextKeywordOutput | Active |
| `execution_trace_parser_compute` | `NodeExecutionTraceParserCompute` | ModelExecutionTraceInput | ModelExecutionTraceOutput | Active |
| `success_criteria_matcher_compute` | `NodeSuccessCriteriaMatcherCompute` | ModelSuccessCriteriaInput | ModelSuccessCriteriaOutput | Active |
| `intent_classifier_compute` | `NodeIntentClassifierCompute` | ModelIntentClassifierInput | ModelIntentClassifierOutput | Active |
| `pattern_learning_compute` | `NodePatternLearningCompute` | ModelPatternLearningInput | ModelPatternLearningOutput | **Stub** |

### 6 Effect Nodes

| Node Directory | Class Name | Operations | External System | Status |
|----------------|------------|------------|-----------------|--------|
| `ingestion_effect` | `NodeIngestionEffect` | PUBLISH_EVENT, CONSUME_EVENTS, PUBLISH_DLQ | Kafka/Redpanda | **Stub** |
| `qdrant_vector_effect` | `NodeQdrantVectorEffect` | INDEX_VECTORS, SEARCH_VECTORS, DELETE_VECTORS | Qdrant | Active |
| `memgraph_graph_effect` | `NodeMemgraphGraphEffect` | CREATE_NODES, CREATE_RELATIONSHIPS, QUERY_GRAPH | Memgraph | Active |
| `postgres_pattern_effect` | `NodePostgresPatternEffect` | STORE_PATTERN, QUERY_PATTERNS, TRACK_LINEAGE, UPDATE_STATE | PostgreSQL | Active |
| `intelligence_api_effect` | `NodeIntelligenceApiEffect` | HANDLE_REQUEST, STREAM_RESPONSE, BATCH_REQUEST | HTTP API | Active |
| `intelligence_adapter` | `NodeIntelligenceAdapterEffect` | Adapter for external intelligence services | Multiple | Active |

### Caching Strategy

> **Note**: There is **no dedicated `valkey_cache` effect node**. Caching is handled through the **intent system**:
>
> - Reducers emit `CACHE_WRITE` and `CACHE_READ` intents
> - The orchestrator routes these intents to the appropriate effect node
> - This decouples caching logic from business logic and maintains reducer purity

Example intent for caching:
```python
ModelIntent(
    intent_type=EnumIntentType.CACHE_WRITE,
    target="cache_handler",  # Resolved by orchestrator
    payload={
        "key": "quality:file:/src/main.py",
        "value": {"score": 8.5, "dimensions": {...}},
        "ttl_seconds": 300
    }
)
```

---

## Omniarchon to ONEX Mapping

### Intelligence Service APIs (78 endpoints)

| Omniarchon Module | API Count | ONEX Node | Node Type | Notes |
|-------------------|-----------|-----------|-----------|-------|
| **Bridge Intelligence** | 3 | `intelligence_api_effect` | Effect | HTTP endpoints |
| **Code Intelligence** | 4 | `entity_extraction_compute` | Compute | Pure extraction |
| **Pattern Learning (Phase 2)** | 7 | `pattern_matching_compute` | Compute | Pure matching |
| **Pattern Traceability (Phase 4)** | 11 | `intelligence_reducer` | Reducer | FSM with lineage (via fsm_type) |
| **Quality Scoring** | 6 | `quality_scoring_compute` | Compute | Pure scoring |
| **Performance Optimization** | 5 | `intelligence_reducer` | Reducer | FSM with analysis (via fsm_type) |
| **Document Freshness** | 9 | `intelligence_orchestrator` | Orchestrator | Workflow coordination |
| **Pattern Analytics** | 5 | `intelligence_api_effect` | Effect | Analytics API |
| **Custom Quality Rules** | 8 | `quality_scoring_compute` | Compute | Rule evaluation |
| **Quality Trends** | 7 | `postgres_pattern_effect` | Effect | Trend persistence |
| **Performance Analytics** | 6 | `intelligence_api_effect` | Effect | Analytics API |
| **Usage Tracking** | 7 | `postgres_pattern_effect` | Effect | Usage persistence |

### Event Handlers (20 handlers)

All event handlers route through the **unified reducer** (`NodeIntelligenceReducer`) using the `fsm_type` enum:

| Omniarchon Handler | FSM Type | Processing Pattern |
|--------------------|----------|-------------------|
| `QualityAssessmentHandler` | `FSM_TYPE.QUALITY_ASSESSMENT` | RAW -> ANALYZED -> SCORED -> STORED -> COMPLETED |
| `PatternLearningHandler` | `FSM_TYPE.PATTERN_LEARNING` | FOUNDATION -> MATCHING -> VALIDATION -> TRACEABILITY -> COMPLETED |
| `DocumentProcessingHandler` | `FSM_TYPE.INGESTION` | RECEIVED -> PARSED -> VECTORIZED -> INDEXED -> COMPLETED |
| `PerformanceHandler` | `FSM_TYPE.QUALITY_ASSESSMENT` | With metrics enrichment |
| `FreshnessHandler` | `FSM_TYPE.INGESTION` | State update for freshness |
| `PatternTraceabilityHandler` | `FSM_TYPE.PATTERN_LEARNING` | Lineage tracking |
| `CodegenValidationHandler` | N/A (Compute) | Routes to `quality_scoring_compute` |
| `AutonomousLearningHandler` | N/A (Compute) | Routes to `pattern_matching_compute` |
| All other handlers | Workflow | Routes to `intelligence_orchestrator` |

### Kafka Topics (8 topics)

| Topic | Producer Node | Consumer Node | Purpose |
|-------|---------------|---------------|---------|
| `enrichment.requested.v1` | `ingestion_effect` | `intelligence_orchestrator` | Trigger ingestion workflow |
| `code-analysis.requested.v1` | `ingestion_effect` | `intelligence_orchestrator` | Trigger analysis workflow |
| `quality.assessed.v1` | `intelligence_reducer` | `intelligence_api_effect` | Quality results |
| `pattern.matched.v1` | `intelligence_reducer` | `postgres_pattern_effect` | Pattern results |
| `tree.discover.v1` | External | `intelligence_orchestrator` | Tree discovery trigger |
| `tree.index.v1` | External | `intelligence_reducer` | Tree indexing trigger |
| `stamping.generate.v1` | External | `intelligence_orchestrator` | ONEX stamping trigger |
| `*.failed.v1` | Any reducer | `ingestion_effect` | DLQ for failures |

### Database Operations

| Database | Omniarchon Usage | ONEX Effect Node | Operations |
|----------|------------------|------------------|------------|
| **Qdrant** | Vector search, 2+ collections | `qdrant_vector_effect` | INDEX_VECTORS, SEARCH_VECTORS, DELETE_VECTORS, CREATE_COLLECTION |
| **Memgraph** | Knowledge graph, 7+ node types | `memgraph_graph_effect` | CREATE_NODES, CREATE_RELATIONSHIPS, QUERY_GRAPH, TRAVERSE_PATH |
| **PostgreSQL** | Pattern traceability, lineage | `postgres_pattern_effect` | STORE_PATTERN, QUERY_PATTERNS, TRACK_LINEAGE, UPDATE_STATE |
| **Valkey/Redis** | Cache (512MB LRU, 300s TTL) | **Via Intents** | CACHE_WRITE, CACHE_READ (emitted by reducers, handled by effect system) |

---

## Workflow Mappings

### 1. Document Ingestion Workflow

**Omniarchon Flow**:
```
Kafka enrichment.requested.v1
  -> IntelligenceConsumer._process_enrichment_event()
    -> DocumentProcessingHandler
      -> Entity extraction
      -> Vectorization
      -> Qdrant indexing
      -> Memgraph storage
        -> Publish completion event
```

**ONEX Flow**:
```
Kafka enrichment.requested.v1
  -> NodeIntelligenceOrchestrator (operation_type: DOCUMENT_INGESTION)
    Step 1: NodeEntityExtractionCompute (code -> entities)
    Step 2: NodeVectorizationCompute (text -> embeddings)
    Step 3: NodeIntelligenceReducer (fsm_type: INGESTION, RECEIVED -> PARSED)
    Step 4: NodeQdrantVectorEffect (INDEX_VECTORS)
    Step 5: NodeMemgraphGraphEffect (CREATE_NODES)
    Step 6: NodeIntelligenceReducer (fsm_type: INGESTION, PARSED -> INDEXED)
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
NodeIntelligenceOrchestrator (operation_type: PATTERN_LEARNING)
  Step 1: NodeIntelligenceReducer (fsm_type: PATTERN_LEARNING, INIT -> FOUNDATION)
    -> Intent: DATA_FETCH (load foundation patterns)
  Step 2: NodePatternMatchingCompute (code + patterns -> matches)
  Step 3: NodeIntelligenceReducer (fsm_type: PATTERN_LEARNING, FOUNDATION -> MATCHING)
    -> Intent: STATE_UPDATE (store matches)
  Step 4: NodeQualityScoringCompute (validate pattern quality)
  Step 5: NodeIntelligenceReducer (fsm_type: PATTERN_LEARNING, MATCHING -> VALIDATION)
  Step 6: NodePostgresPatternEffect (TRACK_LINEAGE)
  Step 7: NodeIntelligenceReducer (fsm_type: PATTERN_LEARNING, VALIDATION -> TRACEABILITY)
    -> Intent: EVENT_PUBLISH (pattern.completed.v1)
```

### 3. Quality Assessment Workflow

**Omniarchon Flow**:
```
POST /assess/code
  -> QualityAssessmentHandler
    -> Quality scoring
    -> ONEX compliance check
    -> Store trends
      -> Return quality report
```

**ONEX Flow**:
```
NodeIntelligenceOrchestrator (operation_type: QUALITY_ASSESSMENT)
  Step 1: NodeQualityScoringCompute (metrics -> score)
  Step 2: NodeIntelligenceReducer (fsm_type: QUALITY_ASSESSMENT, RAW -> ANALYZED)
    -> Intent: STATE_UPDATE (store metrics)
  Step 3: NodeSemanticAnalysisCompute (code -> features)
  Step 4: NodeIntelligenceReducer (fsm_type: QUALITY_ASSESSMENT, ANALYZED -> SCORED)
    -> Intent: CACHE_WRITE (cache score, TTL 300s)
  Step 5: NodePostgresPatternEffect (UPDATE_STATE: store trends)
  Step 6: NodeIntelligenceReducer (fsm_type: QUALITY_ASSESSMENT, SCORED -> COMPLETED)
    -> Intent: EVENT_PUBLISH (quality.assessed.v1)
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

### Example 3: Quality Reducer Cache Write (via Intent)

**Reducer emits**:
```python
ModelIntent(
    intent_type=EnumIntentType.CACHE_WRITE,
    target="cache_handler",  # Resolved by orchestrator to appropriate effect
    payload={
        "key": "quality:file:/src/main.py",
        "value": {"score": 8.5, "dimensions": {...}},
        "ttl_seconds": 300
    }
)
```

**Note**: The cache intent is routed by the orchestrator to the appropriate cache handler. There is no dedicated `valkey_cache` effect node - caching is managed through the intent system to maintain separation of concerns.

---

## Contract Examples

### Orchestrator Contract

```yaml
# src/omniintelligence/nodes/intelligence_orchestrator/contracts/orchestrator_contract.yaml

node_type: orchestrator
node_name: intelligence_orchestrator
version:
  major: 1
  minor: 0
  patch: 0

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

python_version:
  min:
    major: 3
    minor: 12
    patch: 0
  max:
    major: 3
    minor: 13
    patch: 0

onex_version:
  major: 4
  minor: 0
  patch: 0
```

### Unified Reducer Contract

```yaml
# src/omniintelligence/nodes/intelligence_reducer/contracts/reducer_contract.yaml

node_type: reducer
node_name: intelligence_reducer
version:
  major: 1
  minor: 0
  patch: 0

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

python_version:
  min:
    major: 3
    minor: 12
    patch: 0
  max:
    major: 3
    minor: 13
    patch: 0

onex_version:
  major: 4
  minor: 0
  patch: 0
```

### Compute Contract

```yaml
# src/omniintelligence/nodes/vectorization_compute/contracts/compute_contract.yaml

node_type: compute
node_name: vectorization_compute
version:
  major: 1
  minor: 0
  patch: 0

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

python_version:
  min:
    major: 3
    minor: 12
    patch: 0

onex_version:
  major: 4
  minor: 0
  patch: 0
```

### Effect Contract

```yaml
# src/omniintelligence/nodes/ingestion_effect/contracts/effect_contract.yaml

node_type: effect
node_name: ingestion_effect
version:
  major: 1
  minor: 0
  patch: 0

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

python_version:
  min:
    major: 3
    minor: 12
    patch: 0

onex_version:
  major: 4
  minor: 0
  patch: 0
```

---

## Directory Structure

```
src/omniintelligence/nodes/
|-- __init__.py                           # Exports all 20 nodes
|
|-- # ORCHESTRATORS (2)
|-- intelligence_orchestrator/
|   |-- node.py                           # NodeIntelligenceOrchestrator
|   |-- models/
|   |   |-- model_orchestrator_input.py
|   |   |-- model_orchestrator_output.py
|   |   `-- __init__.py
|   |-- contracts/
|   `-- __init__.py
|
|-- pattern_assembler_orchestrator/
|   |-- node.py                           # NodePatternAssemblerOrchestrator
|   |-- models/
|   `-- __init__.py
|
|-- # REDUCERS (1 unified)
|-- intelligence_reducer/
|   |-- node.py                           # NodeIntelligenceReducer (handles ALL FSMs)
|   |-- models/
|   |   |-- model_reducer_input.py
|   |   |-- model_reducer_output.py
|   |   `-- __init__.py
|   |-- contracts/
|   `-- __init__.py
|
|-- # COMPUTE NODES (11)
|-- vectorization_compute/
|   |-- node.py                           # NodeVectorizationCompute
|   |-- models/
|   `-- __init__.py
|
|-- entity_extraction_compute/
|   |-- node.py                           # NodeEntityExtractionCompute
|   |-- models/
|   `-- __init__.py
|
|-- pattern_matching_compute/
|   |-- node.py                           # NodePatternMatchingCompute
|   |-- models/
|   `-- __init__.py
|
|-- pattern_learning_compute/             # STUB - not yet implemented
|   |-- node.py                           # NodePatternLearningCompute
|   |-- models/
|   `-- __init__.py
|
|-- quality_scoring_compute/
|   |-- node.py                           # NodeQualityScoringCompute
|   |-- models/
|   `-- __init__.py
|
|-- semantic_analysis_compute/
|   |-- node.py                           # NodeSemanticAnalysisCompute
|   |-- models/
|   `-- __init__.py
|
|-- relationship_detection_compute/
|   |-- node.py                           # NodeRelationshipDetectionCompute
|   |-- models/
|   `-- __init__.py
|
|-- context_keyword_extractor_compute/
|   |-- node.py                           # NodeContextKeywordExtractorCompute
|   |-- models/
|   `-- __init__.py
|
|-- execution_trace_parser_compute/
|   |-- node.py                           # NodeExecutionTraceParserCompute
|   |-- models/
|   `-- __init__.py
|
|-- success_criteria_matcher_compute/
|   |-- node.py                           # NodeSuccessCriteriaMatcherCompute
|   |-- models/
|   `-- __init__.py
|
|-- intent_classifier_compute/
|   |-- node.py                           # NodeIntentClassifierCompute
|   |-- models/
|   `-- __init__.py
|
|-- # EFFECT NODES (6)
|-- ingestion_effect/                     # STUB - not yet implemented
|   |-- node.py                           # NodeIngestionEffect
|   |-- models/
|   `-- __init__.py
|
|-- qdrant_vector_effect/
|   |-- node.py                           # NodeQdrantVectorEffect
|   |-- models/
|   `-- __init__.py
|
|-- memgraph_graph_effect/
|   |-- node.py                           # NodeMemgraphGraphEffect
|   |-- models/
|   `-- __init__.py
|
|-- postgres_pattern_effect/
|   |-- node.py                           # NodePostgresPatternEffect
|   |-- models/
|   `-- __init__.py
|
|-- intelligence_api_effect/
|   |-- node.py                           # NodeIntelligenceApiEffect
|   |-- models/
|   `-- __init__.py
|
`-- intelligence_adapter/
    |-- node_intelligence_adapter_effect.py  # NodeIntelligenceAdapterEffect
    |-- contract.yaml
    `-- __init__.py
```

---

## Migration Checklist

### Phase 1: Foundation (Complete)
- [x] All node directories created
- [x] Node base classes implemented
- [x] Shared models and enums implemented
- [x] Intent routing system implemented
- [ ] All contract YAML files defined
- [ ] Database schemas created

### Phase 2: Compute Nodes (10/11 Active)
- [x] `vectorization_compute` - NodeVectorizationCompute
- [x] `entity_extraction_compute` - NodeEntityExtractionCompute
- [x] `pattern_matching_compute` - NodePatternMatchingCompute
- [x] `quality_scoring_compute` - NodeQualityScoringCompute
- [x] `semantic_analysis_compute` - NodeSemanticAnalysisCompute
- [x] `relationship_detection_compute` - NodeRelationshipDetectionCompute
- [x] `context_keyword_extractor_compute` - NodeContextKeywordExtractorCompute
- [x] `execution_trace_parser_compute` - NodeExecutionTraceParserCompute
- [x] `success_criteria_matcher_compute` - NodeSuccessCriteriaMatcherCompute
- [x] `intent_classifier_compute` - NodeIntentClassifierCompute
- [ ] `pattern_learning_compute` - NodePatternLearningCompute (STUB)

### Phase 3: Effect Nodes (5/6 Active)
- [x] `qdrant_vector_effect` - NodeQdrantVectorEffect
- [x] `memgraph_graph_effect` - NodeMemgraphGraphEffect
- [x] `postgres_pattern_effect` - NodePostgresPatternEffect
- [x] `intelligence_api_effect` - NodeIntelligenceApiEffect
- [x] `intelligence_adapter` - NodeIntelligenceAdapterEffect
- [ ] `ingestion_effect` - NodeIngestionEffect (STUB)

### Phase 4: Unified Reducer (Complete)
- [x] `intelligence_reducer` - NodeIntelligenceReducer (unified, pure FSM)
- [x] INGESTION FSM (within unified reducer)
- [x] PATTERN_LEARNING FSM (within unified reducer)
- [x] QUALITY_ASSESSMENT FSM (within unified reducer)
- [x] FSM routing via fsm_type enum

### Phase 5: Orchestrators (Complete)
- [x] `intelligence_orchestrator` - NodeIntelligenceOrchestrator
- [x] `pattern_assembler_orchestrator` - NodePatternAssemblerOrchestrator
- [ ] Llama Index workflow integration
- [ ] All workflows implemented
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
pytest src/omniintelligence/nodes/intelligence_reducer/ -v

# Validate contracts
python -m omnibase_core.validators.contract_validator \
  --contract src/omniintelligence/nodes/intelligence_orchestrator/contracts/orchestrator_contract.yaml

# Run integration tests
pytest tests/integration/test_document_ingestion_workflow.py

# Performance benchmarks
pytest -m performance tests/performance/

# List all nodes
python -c "from omniintelligence.nodes import __all__; print('\n'.join(sorted(__all__)))"
```

---

**Document Version**: 2.0
**Last Updated**: 2026-01-19
**Related**: [ONEX Migration Plan](./ONEX_MIGRATION_PLAN.md), [Contract Corrections](./CONTRACT_CORRECTIONS.md), [Omniarchon Inventory](../../OMNIARCHON_MIGRATION_INVENTORY.md)
