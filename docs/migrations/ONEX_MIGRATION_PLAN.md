# ONEX Migration Plan: Omniarchon → OmniIntelligence

**Version**: 1.0
**Date**: 2025-11-14
**Status**: Planning
**Target Architecture**: ONEX 4.0 with Llama Index Workflows

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Node Mapping Strategy](#node-mapping-strategy)
3. [Orchestrator Design](#orchestrator-design)
4. [Reducer Design](#reducer-design)
5. [Compute Nodes](#compute-nodes)
6. [Effect Nodes](#effect-nodes)
7. [Workflow Definitions](#workflow-definitions)
8. [State Management](#state-management)
9. [Intent System](#intent-system)
10. [Implementation Phases](#implementation-phases)

---

## Architecture Overview

### ONEX Principles Applied

1. **Contract-Driven Workflows**: All orchestration declared in YAML contracts using Llama Index workflows
2. **Pure Reducers**: All state persisted in database; reducers are side-effect-free FSMs
3. **Intent-Based Communication**: Reducers communicate with orchestrators via intents (not direct calls)
4. **Type Safety**: Full Pydantic models with generics across all layers
5. **Action Lease Management**: Distributed coordination using lease_id + epoch for concurrency control

### Node Type Distribution

```
NodeOmniAgentOrchestrator (1 unified node)
├─ Handles ALL workflows via operation_type enum
├─ document_ingestion_workflow
├─ pattern_learning_workflow
├─ quality_assessment_workflow
└─ semantic_enrichment_workflow

NodeOmniAgentReducer (1 unified node)
├─ Handles ALL FSMs via fsm_type enum
├─ Ingestion FSM (document → indexed)
├─ Pattern Learning FSM (foundation → validated)
├─ Quality Assessment FSM (raw → scored)
└─ State persistence for all FSMs in single database

Compute Nodes (6 nodes)
├─ Vectorization
├─ Entity Extraction
├─ Pattern Matching
├─ Quality Scoring
├─ Semantic Analysis
└─ Relationship Detection

Effect Nodes (5 nodes)
├─ Kafka Event Bus
├─ Qdrant Vector Store
├─ Memgraph Knowledge Graph
├─ PostgreSQL Pattern Store
└─ Intelligence API Gateway
```

---

## Node Mapping Strategy

### From 78 Omniarchon APIs → ONEX Nodes

| Omniarchon Component | ONEX Node Type | Node Name | Justification |
|---------------------|----------------|-----------|---------------|
| **Intelligence Consumer** | Orchestrator | `intelligence_orchestrator` | Single orchestrator handling ALL workflows via operation_type |
| **Pattern Learning (4 phases)** | Reducer | `intelligence_reducer` | Single reducer handling ALL FSMs (ingestion, pattern, quality) via fsm_type |
| **Ingestion Pipeline** | Reducer | `intelligence_reducer` | Same unified reducer with FSM_TYPE.INGESTION |
| **Quality Assessment** | Reducer | `intelligence_reducer` | Same unified reducer with FSM_TYPE.QUALITY |
| **Vectorization** | Compute | `vectorization_compute` | Pure: text → embeddings |
| **Entity Extraction** | Compute | `entity_extraction_compute` | Pure: code → entities |
| **Pattern Matching** | Compute | `pattern_matching_compute` | Pure: code → patterns |
| **Quality Scoring** | Compute | `quality_scoring_compute` | Pure: metrics → score |
| **Semantic Analysis** | Compute | `semantic_analysis_compute` | Pure: code → analysis |
| **Relationship Detection** | Compute | `relationship_detection_compute` | Pure: entities → relationships |
| **Kafka Handlers (20+)** | Effect | `kafka_event_effect` | Kafka produce/consume |
| **Qdrant Operations** | Effect | `qdrant_vector_effect` | Vector CRUD operations |
| **Memgraph Operations** | Effect | `memgraph_graph_effect` | Graph CRUD operations |
| **PostgreSQL Operations** | Effect | `postgres_pattern_effect` | Pattern persistence |
| **Intelligence APIs (78)** | Effect | `intelligence_api_effect` | HTTP API facade |

---

## Orchestrator Design

### Single Unified NodeOmniAgentOrchestrator

**Location**: `src/omniintelligence/nodes/intelligence_orchestrator/v1_0_0/`

**Key Principle**: One orchestrator handles ALL workflows, routing based on `operation_type` enum.

#### Workflow Declaration (Contract-Driven)

All workflows declared in `contracts/orchestrator_workflows.yaml`:

```yaml
workflows:
  document_ingestion_workflow:
    description: "Complete document ingestion from receipt to indexing"
    steps:
      - step_id: "parse_document"
        action_type: "EXECUTE_COMPUTATION"
        target_node: "entity_extraction_compute"
        timeout_ms: 5000

      - step_id: "generate_embeddings"
        action_type: "EXECUTE_COMPUTATION"
        target_node: "vectorization_compute"
        dependencies: ["parse_document"]
        timeout_ms: 10000

      - step_id: "store_vectors"
        action_type: "EXECUTE_EFFECT"
        target_node: "qdrant_vector_effect"
        dependencies: ["generate_embeddings"]
        timeout_ms: 3000

      - step_id: "update_graph"
        action_type: "EXECUTE_EFFECT"
        target_node: "memgraph_graph_effect"
        dependencies: ["parse_document"]
        timeout_ms: 3000

      - step_id: "publish_completion"
        action_type: "EMIT_EVENT"
        target_node: "kafka_event_effect"
        dependencies: ["store_vectors", "update_graph"]
        timeout_ms: 1000

  pattern_learning_workflow:
    description: "4-phase pattern learning pipeline"
    steps:
      - step_id: "foundation_patterns"
        action_type: "EXECUTE_REDUCTION"
        target_node: "pattern_learning_reducer"
        reducer_transition: "INIT_FOUNDATION"

      - step_id: "match_patterns"
        action_type: "EXECUTE_COMPUTATION"
        target_node: "pattern_matching_compute"
        dependencies: ["foundation_patterns"]

      - step_id: "validate_patterns"
        action_type: "EXECUTE_REDUCTION"
        target_node: "pattern_learning_reducer"
        reducer_transition: "FOUNDATION_TO_VALIDATION"
        dependencies: ["match_patterns"]

      - step_id: "track_lineage"
        action_type: "EXECUTE_EFFECT"
        target_node: "postgres_pattern_effect"
        dependencies: ["validate_patterns"]

  quality_assessment_workflow:
    description: "Code quality assessment pipeline"
    steps:
      - step_id: "extract_metrics"
        action_type: "EXECUTE_COMPUTATION"
        target_node: "quality_scoring_compute"

      - step_id: "assess_quality"
        action_type: "EXECUTE_REDUCTION"
        target_node: "quality_assessment_reducer"
        reducer_transition: "METRICS_TO_SCORED"
        dependencies: ["extract_metrics"]

      - step_id: "store_trends"
        action_type: "EXECUTE_EFFECT"
        target_node: "postgres_pattern_effect"
        dependencies: ["assess_quality"]
```

#### Implementation Structure

```python
from omnibase_spi import NodeOmniAgentOrchestrator
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step

class IntelligenceOrchestrator(NodeOmniAgentOrchestrator[
    ModelIntelligenceInput,
    ModelIntelligenceOutput,
    ModelIntelligenceConfig
]):
    """
    Unified orchestrator for ALL intelligence workflows.

    Handles multiple workflows via operation_type enum:
    - DOCUMENT_INGESTION: Document ingestion pipeline
    - PATTERN_LEARNING: Pattern learning (4 phases)
    - QUALITY_ASSESSMENT: Quality assessment workflows
    - SEMANTIC_ENRICHMENT: Semantic enrichment pipeline

    Each operation_type maps to a specific Llama Index workflow.
    """

    def __init__(self, config: ModelIntelligenceConfig):
        super().__init__(config)
        # Load ALL workflows from contracts
        self.workflows = self._load_workflows_from_contracts()

    async def process(
        self,
        input_data: ModelIntelligenceInput
    ) -> ModelIntelligenceOutput:
        """
        Route to appropriate workflow based on operation_type.

        Operation types:
        - DOCUMENT_INGESTION → document_ingestion_workflow
        - PATTERN_LEARNING → pattern_learning_workflow
        - QUALITY_ASSESSMENT → quality_assessment_workflow
        - SEMANTIC_ENRICHMENT → semantic_enrichment_workflow
        """
        # Select workflow based on operation type
        workflow = self._select_workflow(input_data.operation_type)

        # Create lease for distributed ownership
        lease_id = self._create_lease(workflow.id)
        epoch = 0

        try:
            # Execute workflow steps with lease management
            result = await self._execute_workflow_with_lease(
                workflow=workflow,
                input_data=input_data,
                lease_id=lease_id,
                epoch=epoch
            )

            return ModelIntelligenceOutput(
                success=True,
                result=result,
                workflow_id=workflow.id,
                steps_completed=len(workflow.steps)
            )

        except Exception as e:
            # Compensation logic
            await self._compensate_workflow(workflow, lease_id)
            raise
        finally:
            # Release lease
            await self._release_lease(lease_id)

    async def _execute_workflow_with_lease(
        self,
        workflow: LlamaIndexWorkflow,
        input_data: ModelIntelligenceInput,
        lease_id: str,
        epoch: int
    ) -> Any:
        """Execute Llama Index workflow with action lease management."""

        for step in workflow.steps:
            # Create Action with lease
            action = ModelAction(
                action_type=step.action_type,
                lease_id=lease_id,
                epoch=epoch,
                payload={
                    "target_node": step.target_node,
                    "input_data": input_data.dict(),
                    "timeout_ms": step.timeout_ms
                }
            )

            # Execute action (delegates to appropriate node type)
            result = await self._execute_action(action)

            # Increment epoch for next step
            epoch += 1

            # Store intermediate state
            await self._save_workflow_state(workflow.id, step.step_id, result)

        return result

    def _load_workflows_from_contracts(self) -> Dict[str, LlamaIndexWorkflow]:
        """Load workflow definitions from YAML contracts."""
        # Parse contracts/orchestrator_workflows.yaml
        # Build Llama Index Workflow objects
        pass
```

---

## Reducer Design

### Single Unified NodeOmniAgentReducer

**Location**: `src/omniintelligence/nodes/intelligence_reducer/v1_0_0/`

**Key Principle**: One reducer handles ALL FSMs, routing based on `fsm_type` enum.

**Pure FSM Pattern**:
1. **Pure FSM**: No side effects in `process()`
2. **Database State**: All state persisted via intents
3. **Intent Emission**: Communicate via `ModelIntent` objects
4. **Immutable Config**: Only read-only configuration in `__init__`
5. **Multi-FSM**: Handles multiple state machines via `fsm_type`

### FSM Type Enumeration

```python
class EnumFSMType(str, Enum):
    """FSM types handled by intelligence reducer."""
    INGESTION = "INGESTION"          # Document ingestion pipeline
    PATTERN_LEARNING = "PATTERN_LEARNING"  # Pattern learning phases
    QUALITY_ASSESSMENT = "QUALITY_ASSESSMENT"  # Quality scoring
```

### FSM Definitions

#### 1. Ingestion FSM (FSM_TYPE.INGESTION)

**States**:
```
RECEIVED → PARSED → VECTORIZED → INDEXED → COMPLETED
                 ↓ (error)
              FAILED → DLQ
```

**Implementation**:
```python
from omnibase_spi import NodeOmniAgentReducer, ModelIntent, EnumIntentType

class IntelligenceReducer(NodeOmniAgentReducer[
    ModelReducerInput,
    ModelReducerOutput,
    ModelReducerConfig
]):
    """
    Unified reducer for ALL intelligence FSMs.

    Handles multiple FSMs via fsm_type enum:
    - INGESTION: Document ingestion (RECEIVED → INDEXED)
    - PATTERN_LEARNING: Pattern learning (FOUNDATION → TRACEABILITY)
    - QUALITY_ASSESSMENT: Quality scoring (RAW → STORED)

    All state stored in PostgreSQL via intents.
    Pure FSM with zero instance state.
    """

    def __init__(self, config: ModelReducerConfig):
        # ONLY immutable configuration
        self.batch_size: int = config.batch_size
        self.max_retry_count: int = config.max_retry_count
        self.performance_threshold_ms: int = config.performance_threshold_ms
        # FSM-specific configs
        self.ingestion_config: IngestionFSMConfig = config.ingestion
        self.pattern_config: PatternLearningFSMConfig = config.pattern_learning
        self.quality_config: QualityFSMConfig = config.quality

    async def process(
        self,
        input_data: ModelReducerInput
    ) -> ModelReducerOutput:
        """
        Route to appropriate FSM based on fsm_type.

        Pure reduction: (fsm_type, current_state, event) → (new_state, intents)

        NO side effects. All state changes via intents.
        """
        # Route to appropriate FSM handler
        if input_data.fsm_type == EnumFSMType.INGESTION:
            return await self._process_ingestion_fsm(input_data)
        elif input_data.fsm_type == EnumFSMType.PATTERN_LEARNING:
            return await self._process_pattern_learning_fsm(input_data)
        elif input_data.fsm_type == EnumFSMType.QUALITY_ASSESSMENT:
            return await self._process_quality_assessment_fsm(input_data)
        else:
            raise ValueError(f"Unknown FSM type: {input_data.fsm_type}")

    async def _process_ingestion_fsm(
        self,
        input_data: ModelReducerInput
    ) -> ModelReducerOutput:
        """Process ingestion FSM transitions."""
        intents: List[ModelIntent] = []

        # Pure state transition logic
        current_state = input_data.current_state
        event = input_data.event

        if current_state == EnumIngestionState.RECEIVED:
            # Transition to PARSED
            new_state = EnumIngestionState.PARSED

            # Emit intent to update state in database
            intents.append(ModelIntent(
                intent_type=EnumIntentType.STATE_UPDATE,
                target="postgres_pattern_effect",
                payload={
                    "document_id": input_data.document_id,
                    "new_state": new_state.value,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ))

            # Emit intent to trigger orchestrator workflow
            intents.append(ModelIntent(
                intent_type=EnumIntentType.WORKFLOW_TRIGGER,
                target="intelligence_orchestrator",
                payload={
                    "workflow": "document_ingestion_workflow",
                    "document_id": input_data.document_id,
                    "next_step": "generate_embeddings"
                }
            ))

        elif current_state == EnumIngestionState.PARSED:
            new_state = EnumIngestionState.VECTORIZED

            # Emit cache write intent
            intents.append(ModelIntent(
                intent_type=EnumIntentType.CACHE_WRITE,
                target="valkey_cache",
                payload={
                    "key": f"doc:{input_data.document_id}:vectors",
                    "value": input_data.vectors,
                    "ttl_seconds": 300
                }
            ))

        elif current_state == EnumIngestionState.VECTORIZED:
            new_state = EnumIngestionState.INDEXED

        elif current_state == EnumIngestionState.INDEXED:
            new_state = EnumIngestionState.COMPLETED

            # Emit event intent for downstream services
            intents.append(ModelIntent(
                intent_type=EnumIntentType.EVENT_PUBLISH,
                target="kafka_event_effect",
                payload={
                    "topic": "dev.intelligence.ingestion.completed.v1",
                    "event": {
                        "document_id": input_data.document_id,
                        "completed_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            ))

        else:
            raise ValueError(f"Invalid state: {current_state}")

        # Emit logging intent
        intents.append(ModelIntent(
            intent_type=EnumIntentType.LOG,
            target="logger",
            payload={
                "level": "info",
                "message": f"State transition: {current_state} → {new_state}",
                "document_id": input_data.document_id
            }
        ))

        # Emit metrics intent
        intents.append(ModelIntent(
            intent_type=EnumIntentType.METRIC,
            target="metrics",
            payload={
                "metric": "ingestion.state_transition",
                "labels": {
                    "from_state": current_state.value,
                    "to_state": new_state.value
                },
                "value": 1
            }
        ))

        # Return pure result
        return ModelReducerOutput(
            result={
                "previous_state": current_state.value,
                "new_state": new_state.value,
                "document_id": input_data.document_id
            },
            intents=intents,
            success=True
        )
```

#### 2. Pattern Learning FSM (FSM_TYPE.PATTERN_LEARNING)

**States** (4 Phases):
```
FOUNDATION → MATCHING → VALIDATION → TRACEABILITY → COMPLETED
```

**Implementation** (within unified reducer):
```python
    async def _process_pattern_learning_fsm(
        self,
        input_data: ModelReducerInput
    ) -> ModelReducerOutput:
        """Process pattern learning FSM transitions (4 phases)."""
        intents: List[ModelIntent] = []
        current_phase = input_data.current_phase

        if current_phase == EnumPatternPhase.FOUNDATION:
            # Transition to MATCHING
            new_phase = EnumPatternPhase.MATCHING

            # Intent: Load foundation patterns from database
            intents.append(ModelIntent(
                intent_type=EnumIntentType.DATA_FETCH,
                target="postgres_pattern_effect",
                payload={
                    "query": "SELECT * FROM foundation_patterns WHERE active = true"
                }
            ))

            # Intent: Trigger orchestrator for matching workflow
            intents.append(ModelIntent(
                intent_type=EnumIntentType.WORKFLOW_TRIGGER,
                target="intelligence_orchestrator",
                payload={
                    "workflow": "pattern_learning_workflow",
                    "next_step": "match_patterns"
                }
            ))

        elif current_phase == EnumPatternPhase.MATCHING:
            new_phase = EnumPatternPhase.VALIDATION

            # Filter patterns by confidence threshold (pure logic)
            validated_patterns = [
                p for p in input_data.matched_patterns
                if p.confidence >= self.confidence_threshold
            ]

            # Intent: Store validated patterns
            intents.append(ModelIntent(
                intent_type=EnumIntentType.STATE_UPDATE,
                target="postgres_pattern_effect",
                payload={
                    "patterns": validated_patterns,
                    "phase": "VALIDATION"
                }
            ))

        elif current_phase == EnumPatternPhase.VALIDATION:
            new_phase = EnumPatternPhase.TRACEABILITY

        elif current_phase == EnumPatternPhase.TRACEABILITY:
            new_phase = EnumPatternPhase.COMPLETED

            # Intent: Publish completion event
            intents.append(ModelIntent(
                intent_type=EnumIntentType.EVENT_PUBLISH,
                target="kafka_event_effect",
                payload={
                    "topic": "dev.intelligence.pattern.completed.v1",
                    "event": {
                        "pattern_id": input_data.pattern_id,
                        "phases_completed": 4
                    }
                }
            ))

        return ModelReducerOutput(
            result={
                "previous_phase": current_phase.value,
                "new_phase": new_phase.value
            },
            intents=intents,
            success=True
        )
```

#### 3. Quality Assessment FSM (FSM_TYPE.QUALITY_ASSESSMENT)

**States**:
```
RAW → ANALYZED → SCORED → STORED → COMPLETED
```

**Implementation** (within unified reducer):
```python
    async def _process_quality_assessment_fsm(
        self,
        input_data: ModelReducerInput
    ) -> ModelReducerOutput:
        """Process quality assessment FSM transitions."""
        intents: List[ModelIntent] = []

        current_state = input_data.current_state
        event = input_data.event

        if current_state == EnumQualityState.RAW:
            new_state = EnumQualityState.ANALYZED

            # Intent: Trigger quality scoring
            intents.append(ModelIntent(
                intent_type=EnumIntentType.WORKFLOW_TRIGGER,
                target="intelligence_orchestrator",
                payload={
                    "workflow": "quality_assessment_workflow",
                    "file_path": input_data.file_path
                }
            ))

        elif current_state == EnumQualityState.ANALYZED:
            new_state = EnumQualityState.SCORED

        elif current_state == EnumQualityState.SCORED:
            new_state = EnumQualityState.STORED

        elif current_state == EnumQualityState.STORED:
            new_state = EnumQualityState.COMPLETED

        return ModelReducerOutput(
            result={"new_state": new_state.value},
            intents=intents,
            success=True
        )
```

---

## Compute Nodes

### 1. Vectorization Compute

**Location**: `src/omniintelligence/nodes/vectorization_compute/v1_0_0/`

**Pure Function**: `text → embeddings`

```python
from omnibase_spi import NodeCompute

class VectorizationCompute(NodeCompute[
    ModelVectorizationInput,
    ModelVectorizationOutput,
    ModelVectorizationConfig
]):
    """
    Pure vectorization: text → embeddings.

    Operations:
    - GENERATE_EMBEDDINGS: Text to vector
    - BATCH_VECTORIZE: Multiple texts
    - SEMANTIC_SIMILARITY: Cosine similarity
    """

    async def process(
        self,
        input_data: ModelVectorizationInput
    ) -> ModelVectorizationOutput:
        """Pure computation with no side effects."""

        if input_data.operation_type == EnumVectorizationOp.GENERATE_EMBEDDINGS:
            # Pure: text → embeddings
            embeddings = await self._generate_embeddings_pure(
                text=input_data.text,
                model=self.config.embedding_model
            )

            return ModelVectorizationOutput(
                success=True,
                embeddings=embeddings,
                dimension=len(embeddings),
                model=self.config.embedding_model
            )

        elif input_data.operation_type == EnumVectorizationOp.BATCH_VECTORIZE:
            # Pure: list[text] → list[embeddings]
            results = await asyncio.gather(*[
                self._generate_embeddings_pure(text, self.config.embedding_model)
                for text in input_data.texts
            ])

            return ModelVectorizationOutput(
                success=True,
                batch_embeddings=results,
                count=len(results)
            )

    async def _generate_embeddings_pure(
        self,
        text: str,
        model: str
    ) -> List[float]:
        """Pure embedding generation (stateless)."""
        # Use sentence-transformers or OpenAI
        # No side effects, no state
        pass
```

### 2. Entity Extraction Compute

**Pure Function**: `code → entities`

### 3. Pattern Matching Compute

**Pure Function**: `code + patterns → matches`

### 4. Quality Scoring Compute

**Pure Function**: `metrics → quality_score`

### 5. Semantic Analysis Compute

**Pure Function**: `code → semantic_features`

### 6. Relationship Detection Compute

**Pure Function**: `entities → relationships`

---

## Effect Nodes

### 1. Kafka Event Effect

**Location**: `src/omniintelligence/nodes/kafka_event_effect/v1_0_0/`

**Operations**:
- PUBLISH_EVENT: Produce to topic
- CONSUME_EVENTS: Consume from topic
- PUBLISH_DLQ: Send to dead-letter queue

```python
from omnibase_spi import NodeEffectService

class KafkaEventEffect(NodeEffectService[
    ModelKafkaInput,
    ModelKafkaOutput,
    ModelKafkaConfig
]):
    """
    Kafka operations effect node.

    Handles all Kafka interactions:
    - Event publishing
    - DLQ routing
    - Consumer management
    """

    async def process(
        self,
        input_data: ModelKafkaInput
    ) -> ModelKafkaOutput:
        """Execute Kafka operation."""

        if input_data.operation_type == EnumKafkaOp.PUBLISH_EVENT:
            await self._publish_to_kafka(
                topic=input_data.topic,
                event=input_data.event,
                correlation_id=input_data.correlation_id
            )

        elif input_data.operation_type == EnumKafkaOp.PUBLISH_DLQ:
            await self._publish_to_dlq(
                original_topic=input_data.original_topic,
                event=input_data.event,
                error=input_data.error,
                retry_count=input_data.retry_count
            )

        return ModelKafkaOutput(success=True)

    async def _publish_to_kafka(
        self,
        topic: str,
        event: Dict[str, Any],
        correlation_id: str
    ) -> None:
        """Publish event to Kafka topic."""
        # Use aiokafka producer
        pass
```

### 2. Qdrant Vector Effect

**Operations**:
- INDEX_VECTORS: Store vectors
- SEARCH_VECTORS: Similarity search
- DELETE_VECTORS: Remove vectors
- CREATE_COLLECTION: Collection management

### 3. Memgraph Graph Effect

**Operations**:
- CREATE_NODES: Create graph nodes
- CREATE_RELATIONSHIPS: Create edges
- QUERY_GRAPH: Cypher queries
- TRAVERSE_PATH: Path finding

### 4. PostgreSQL Pattern Effect

**Operations**:
- STORE_PATTERN: Persist pattern
- QUERY_PATTERNS: Fetch patterns
- TRACK_LINEAGE: Lineage tracking
- UPDATE_STATE: State persistence

### 5. Intelligence API Effect

**Operations**:
- HANDLE_REQUEST: Process HTTP request
- STREAM_RESPONSE: SSE streaming
- BATCH_REQUEST: Batch operations

---

## Workflow Definitions

### Contract Structure

All workflows defined in `contracts/workflows/`:

```yaml
# contracts/workflows/document_ingestion.yaml
workflow_id: "document_ingestion_workflow"
version: "1.0.0"
description: "Complete document ingestion pipeline"

trigger:
  event_type: "document.received"
  source: "kafka_event_effect"

steps:
  - id: "parse_document"
    type: "compute"
    node: "entity_extraction_compute"
    input_mapping:
      document_content: "${trigger.payload.content}"
      language: "${trigger.payload.language}"
    timeout_ms: 5000
    retry_policy:
      max_attempts: 3
      backoff_ms: 1000

  - id: "generate_embeddings"
    type: "compute"
    node: "vectorization_compute"
    input_mapping:
      text: "${steps.parse_document.output.text}"
    dependencies:
      - "parse_document"
    timeout_ms: 10000

  - id: "update_ingestion_state"
    type: "reducer"
    node: "ingestion_reducer"
    input_mapping:
      current_state: "PARSED"
      event: "VECTORIZATION_COMPLETED"
      vectors: "${steps.generate_embeddings.output.embeddings}"
    dependencies:
      - "generate_embeddings"

  - id: "store_vectors"
    type: "effect"
    node: "qdrant_vector_effect"
    input_mapping:
      operation: "INDEX_VECTORS"
      vectors: "${steps.generate_embeddings.output.embeddings}"
      metadata: "${steps.parse_document.output.entities}"
    dependencies:
      - "update_ingestion_state"
    timeout_ms: 3000

  - id: "store_entities"
    type: "effect"
    node: "memgraph_graph_effect"
    input_mapping:
      operation: "CREATE_NODES"
      entities: "${steps.parse_document.output.entities}"
    dependencies:
      - "parse_document"
    parallel_with:
      - "store_vectors"

  - id: "publish_completion"
    type: "effect"
    node: "kafka_event_effect"
    input_mapping:
      operation: "PUBLISH_EVENT"
      topic: "dev.intelligence.ingestion.completed.v1"
      event:
        document_id: "${trigger.payload.document_id}"
        vector_count: "${steps.generate_embeddings.output.count}"
        entity_count: "${steps.parse_document.output.entity_count}"
    dependencies:
      - "store_vectors"
      - "store_entities"

error_handling:
  on_step_failure:
    action: "compensate"
    compensation_workflow: "document_ingestion_rollback"

  on_timeout:
    action: "retry_with_backoff"
    max_retries: 3

  on_fatal_error:
    action: "publish_dlq"
    dlq_topic: "dev.intelligence.ingestion.failed.v1"
```

---

## State Management

### Database Schema for Reducer State

**Single unified table for ALL FSMs**:

```sql
-- Unified FSM state tracking
CREATE TABLE fsm_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fsm_type VARCHAR(50) NOT NULL,  -- INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT
    entity_id VARCHAR(255) NOT NULL,  -- document_id, pattern_id, or assessment_id
    current_state VARCHAR(50) NOT NULL,
    previous_state VARCHAR(50),
    transition_timestamp TIMESTAMPTZ NOT NULL,
    retry_count INT DEFAULT 0,
    error_message TEXT,
    metadata JSONB,  -- FSM-specific data
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Composite unique constraint
    UNIQUE(fsm_type, entity_id)
);

-- Indexes for efficient querying
CREATE INDEX idx_fsm_state_type ON fsm_state(fsm_type);
CREATE INDEX idx_fsm_state_current ON fsm_state(fsm_type, current_state);
CREATE INDEX idx_fsm_state_entity ON fsm_state(entity_id);
CREATE INDEX idx_fsm_state_timestamp ON fsm_state(transition_timestamp);

-- Example FSM-specific metadata structures:
-- For INGESTION:
-- metadata = {
--   "document_id": "doc-123",
--   "vector_count": 10,
--   "entity_count": 5
-- }

-- For PATTERN_LEARNING:
-- metadata = {
--   "pattern_id": "pattern-456",
--   "foundation_patterns": [...],
--   "matched_patterns": [...],
--   "confidence_score": 0.95
-- }

-- For QUALITY_ASSESSMENT:
-- metadata = {
--   "assessment_id": "assess-789",
--   "file_path": "/src/main.py",
--   "quality_score": 8.5,
--   "dimensions": {...}
-- }
```

### State Persistence via Intents

Reducers emit `STATE_UPDATE` intents:

```python
# In unified reducer
intents.append(ModelIntent(
    intent_type=EnumIntentType.STATE_UPDATE,
    target="postgres_pattern_effect",
    payload={
        "table": "fsm_state",
        "fsm_type": input_data.fsm_type.value,  # INGESTION, PATTERN_LEARNING, etc.
        "entity_id": input_data.entity_id,
        "updates": {
            "current_state": new_state.value,
            "previous_state": current_state.value,
            "transition_timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": input_data.metadata  # FSM-specific data
        }
    }
))
```

Effect node executes:

```python
# In postgres_pattern_effect
async def _handle_state_update(self, payload: Dict[str, Any]):
    """Execute state update in unified fsm_state table."""
    await self.db_pool.execute(
        """
        UPDATE fsm_state
        SET current_state = $1,
            previous_state = $2,
            transition_timestamp = $3,
            metadata = $4,
            updated_at = NOW()
        WHERE fsm_type = $5 AND entity_id = $6
        """,
        payload["updates"]["current_state"],
        payload["updates"]["previous_state"],
        payload["updates"]["transition_timestamp"],
        json.dumps(payload["updates"]["metadata"]),
        payload["fsm_type"],
        payload["entity_id"]
    )
```

---

## Intent System

### Intent Types (Enumeration)

```python
class EnumIntentType(str, Enum):
    """Intent types for reducer → orchestrator/effect communication."""

    # State management
    STATE_UPDATE = "STATE_UPDATE"
    STATE_FETCH = "STATE_FETCH"

    # Workflow control
    WORKFLOW_TRIGGER = "WORKFLOW_TRIGGER"
    WORKFLOW_PAUSE = "WORKFLOW_PAUSE"
    WORKFLOW_RESUME = "WORKFLOW_RESUME"

    # Data operations
    DATA_FETCH = "DATA_FETCH"
    DATA_STORE = "DATA_STORE"

    # Event publishing
    EVENT_PUBLISH = "EVENT_PUBLISH"
    EVENT_SUBSCRIBE = "EVENT_SUBSCRIBE"

    # Caching
    CACHE_WRITE = "CACHE_WRITE"
    CACHE_READ = "CACHE_READ"
    CACHE_INVALIDATE = "CACHE_INVALIDATE"

    # Logging and metrics
    LOG = "LOG"
    METRIC = "METRIC"
    TRACE = "TRACE"
```

### Intent Model

```python
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime
from uuid import uuid4

class ModelIntent(BaseModel):
    """
    Intent emitted by reducers for side effects.

    Reducers are pure and communicate via intents.
    """
    intent_id: str = Field(default_factory=lambda: str(uuid4()))
    intent_type: EnumIntentType
    target: str  # Target node or service
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    priority: int = Field(default=5, ge=1, le=10)
    ttl_seconds: Optional[int] = None
```

### Intent Processing Flow

```
Reducer.process()
    ↓ (emits intents)
ModelReducerOutput(result=..., intents=[...])
    ↓
Intent Router (in orchestrator or intent bus)
    ↓
    ├→ EnumIntentType.STATE_UPDATE → postgres_pattern_effect
    ├→ EnumIntentType.WORKFLOW_TRIGGER → intelligence_orchestrator
    ├→ EnumIntentType.EVENT_PUBLISH → kafka_event_effect
    ├→ EnumIntentType.CACHE_WRITE → valkey_cache_effect
    ├→ EnumIntentType.LOG → logger_effect
    └→ EnumIntentType.METRIC → metrics_effect
```

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

**Goal**: Set up ONEX infrastructure and shared components

- [ ] Create directory structure for all nodes
- [ ] Define all contract schemas (YAML)
- [ ] Implement shared models and enums
- [ ] Set up database schemas for state management
- [ ] Create intent routing system
- [ ] Implement base node classes

**Deliverables**:
- All node directories with v1_0_0 structure
- Complete contract definitions
- Database migration scripts
- Intent router implementation

### Phase 2: Compute Nodes (Weeks 3-4)

**Goal**: Implement pure computation nodes

- [ ] Vectorization compute
- [ ] Entity extraction compute
- [ ] Pattern matching compute
- [ ] Quality scoring compute
- [ ] Semantic analysis compute
- [ ] Relationship detection compute

**Deliverables**:
- 6 compute nodes with unit tests
- Performance benchmarks
- Contract validation tests

### Phase 3: Effect Nodes (Weeks 5-6)

**Goal**: Implement infrastructure interaction nodes

- [ ] Kafka event effect
- [ ] Qdrant vector effect
- [ ] Memgraph graph effect
- [ ] PostgreSQL pattern effect
- [ ] Intelligence API effect

**Deliverables**:
- 5 effect nodes with integration tests
- Database connection pooling
- Circuit breaker implementations
- Health check endpoints

### Phase 4: Unified Reducer (Weeks 7-8)

**Goal**: Implement single unified pure FSM reducer

- [ ] Intelligence reducer (unified)
- [ ] Ingestion FSM implementation
- [ ] Pattern learning FSM implementation
- [ ] Quality assessment FSM implementation
- [ ] FSM routing based on fsm_type enum
- [ ] Intent emission logic
- [ ] State transition tests for all FSMs

**Deliverables**:
- 1 unified reducer node with 3 FSMs
- FSM validation for all types
- Intent emission verification
- Unified database state persistence

### Phase 5: Orchestrator (Weeks 9-10)

**Goal**: Implement workflow orchestration with Llama Index

- [ ] Intelligence orchestrator
- [ ] Llama Index workflow integration
- [ ] Contract-driven workflow loading
- [ ] Action lease management
- [ ] Compensation logic

**Deliverables**:
- Orchestrator node with workflow engine
- All 3 workflows implemented
- End-to-end integration tests
- Performance benchmarks

### Phase 6: Integration & Testing (Weeks 11-12)

**Goal**: Complete integration and validation

- [ ] End-to-end workflow tests
- [ ] Performance testing (78 API equivalents)
- [ ] Load testing
- [ ] Chaos engineering tests
- [ ] Documentation completion
- [ ] Production deployment plan

**Deliverables**:
- Complete test coverage (>90%)
- Performance benchmarks vs. omniarchon
- Production-ready deployment manifests
- Migration runbook

---

## Success Metrics

### Functional Parity
- [ ] All 78 omniarchon APIs mapped to ONEX nodes
- [ ] All 20 event handlers migrated
- [ ] All 8 Kafka topics integrated
- [ ] All 4 databases connected

### Performance Targets
- [ ] Ingestion latency: <500ms (p95)
- [ ] Pattern matching: <2s (p95)
- [ ] Quality assessment: <1s (p95)
- [ ] Vector search: <100ms (p95)
- [ ] Event processing: <200ms (p95)

### Quality Metrics
- [ ] Test coverage: >90%
- [ ] Contract validation: 100%
- [ ] Zero state in reducer instances
- [ ] All side effects via intents
- [ ] Full distributed tracing

### Operational Readiness
- [ ] Health checks: All nodes
- [ ] Metrics: All operations
- [ ] Logging: Structured JSON
- [ ] Alerts: Critical paths
- [ ] Documentation: Complete

---

## References

- [Omniarchon Inventory](../../../OMNIARCHON_MIGRATION_INVENTORY.md)
- [ONEX Orchestrator Template](https://github.com/OmniNode-ai/omnibase_core/tree/main/docs/guides/templates/ORCHESTRATOR_NODE_TEMPLATE.md)
- [ONEX Reducer Template](https://github.com/OmniNode-ai/omnibase_core/tree/main/docs/guides/templates/REDUCER_NODE_TEMPLATE.md)
- [Llama Index Workflows](https://docs.llamaindex.ai/en/stable/module_guides/workflow/)

---

**Document Status**: Planning Complete
**Next Action**: Begin Phase 1 implementation
**Review Date**: 2025-11-21
