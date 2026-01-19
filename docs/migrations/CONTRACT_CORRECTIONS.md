# Contract and Model Corrections

## Using Proper ONEX Models from omnibase_core

### Version Management

**INCORRECT** (strings):
```yaml
version: "1.0.0"
```

**CORRECT** (ModelSemVer):
```python
from omnibase_core.models.versioning import ModelSemVer

version = ModelSemVer(major=1, minor=0, patch=0)
```

```yaml
version:
  major: 1
  minor: 0
  patch: 0
```

---

## Contract Structure with Subcontracts

### Main Contract Structure

Each node has a main contract that references subcontracts:

```
nodes/intelligence_orchestrator/v1_0_0/
├── contracts/
│   ├── orchestrator_contract.yaml      # Main contract
│   ├── subcontracts/
│   │   ├── processing.yaml             # Processing operations
│   │   ├── management.yaml             # Lifecycle management
│   │   └── monitoring.yaml             # Health & metrics
│   └── workflows/
│       ├── document_ingestion.yaml
│       ├── pattern_learning.yaml
│       └── quality_assessment.yaml
```

### Main Orchestrator Contract

```yaml
# contracts/orchestrator_contract.yaml
node_type: orchestrator
node_name: intelligence_orchestrator
version:
  major: 1
  minor: 0
  patch: 0

# Reference to subcontracts
subcontracts:
  processing: ./subcontracts/processing.yaml
  management: ./subcontracts/management.yaml
  monitoring: ./subcontracts/monitoring.yaml

# Node capabilities
capabilities:
  - WORKFLOW_COORDINATION
  - MULTI_STEP_ORCHESTRATION
  - LEASE_MANAGEMENT
  - COMPENSATION_LOGIC

# Python compatibility
python_version:
  min:
    major: 3
    minor: 12
    patch: 0
  max:
    major: 3
    minor: 13
    patch: 0

# ONEX framework version
onex_version:
  major: 4
  minor: 0
  patch: 0
```

### Processing Subcontract

```yaml
# contracts/subcontracts/processing.yaml
subcontract_name: processing
version:
  major: 1
  minor: 0
  patch: 0

operations:
  - operation_id: EXECUTE_WORKFLOW
    operation_type: DOCUMENT_INGESTION
    description: "Execute document ingestion workflow"

    input_schema:
      type: object
      properties:
        operation_type:
          type: string
          enum: [DOCUMENT_INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT]
        document_id:
          type: string
          format: uuid
        content:
          type: string
        language:
          type: string
        context:
          type: object
      required: [operation_type, document_id]

    output_schema:
      type: object
      properties:
        success:
          type: boolean
        workflow_id:
          type: string
        steps_completed:
          type: integer
        result:
          type: object
        execution_time_ms:
          type: integer
      required: [success]

    performance:
      timeout_ms: 60000
      target_p95_ms: 30000
      target_p99_ms: 50000

    circuit_breaker:
      failure_threshold: 5
      recovery_timeout_ms: 60000
      half_open_max_calls: 3

  - operation_id: EXECUTE_WORKFLOW
    operation_type: PATTERN_LEARNING
    # ... similar structure

  - operation_id: EXECUTE_WORKFLOW
    operation_type: QUALITY_ASSESSMENT
    # ... similar structure
```

### Management Subcontract

```yaml
# contracts/subcontracts/management.yaml
subcontract_name: management
version:
  major: 1
  minor: 0
  patch: 0

lifecycle:
  initialization:
    required_dependencies:
      - ingestion_effect
      - postgres_pattern_effect
      - intelligence_reducer

    configuration:
      workflow_config_path: ./workflows/
      lease_timeout_ms: 300000
      max_concurrent_workflows: 10

    health_check:
      endpoint: /health
      interval_ms: 30000
      timeout_ms: 5000

  shutdown:
    graceful_timeout_ms: 60000
    force_timeout_ms: 120000
    cleanup_actions:
      - release_all_leases
      - flush_pending_intents
      - save_workflow_state
```

### Monitoring Subcontract

```yaml
# contracts/subcontracts/monitoring.yaml
subcontract_name: monitoring
version:
  major: 1
  minor: 0
  patch: 0

metrics:
  - name: workflow_execution_duration_ms
    type: histogram
    labels: [operation_type, status]
    buckets: [100, 500, 1000, 5000, 10000, 30000, 60000]

  - name: workflow_step_failures_total
    type: counter
    labels: [operation_type, step_id, failure_reason]

  - name: active_workflows
    type: gauge
    labels: [operation_type]

  - name: lease_acquisition_failures_total
    type: counter
    labels: [workflow_id]

health_indicators:
  - name: workflow_engine_healthy
    check_type: internal
    severity: critical

  - name: downstream_nodes_reachable
    check_type: dependency
    severity: high
    targets:
      - intelligence_reducer
      - ingestion_effect
      - postgres_pattern_effect
```

---

## Unified Reducer Contract Structure

### Main Reducer Contract

```yaml
# nodes/intelligence_reducer/v1_0_0/contracts/reducer_contract.yaml
node_type: reducer
node_name: intelligence_reducer
version:
  major: 1
  minor: 0
  patch: 0

subcontracts:
  processing: ./subcontracts/processing.yaml
  management: ./subcontracts/management.yaml
  monitoring: ./subcontracts/monitoring.yaml

# FSM definitions
fsm_types:
  - INGESTION
  - PATTERN_LEARNING
  - QUALITY_ASSESSMENT

# Purity guarantees
purity:
  immutable_configuration: true
  zero_instance_state: true
  side_effects_via_intents: true
  deterministic: true

# State persistence
state_management:
  persistence_type: database
  table_name: fsm_state
  update_mechanism: intent_emission

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

### Reducer Processing Subcontract

```yaml
# contracts/subcontracts/processing.yaml
subcontract_name: processing
version:
  major: 1
  minor: 0
  patch: 0

state_machines:
  INGESTION:
    description: "Document ingestion FSM"

    states:
      - name: RECEIVED
        is_initial: true
        is_final: false
      - name: PARSED
        is_initial: false
        is_final: false
      - name: VECTORIZED
        is_initial: false
        is_final: false
      - name: INDEXED
        is_initial: false
        is_final: false
      - name: COMPLETED
        is_initial: false
        is_final: true
      - name: FAILED
        is_initial: false
        is_final: true

    transitions:
      - from_state: RECEIVED
        to_state: PARSED
        event: PARSE_COMPLETED
        intents_emitted:
          - STATE_UPDATE
          - WORKFLOW_TRIGGER
          - LOG
          - METRIC

      - from_state: PARSED
        to_state: VECTORIZED
        event: VECTORIZATION_COMPLETED
        intents_emitted:
          - STATE_UPDATE
          - CACHE_WRITE
          - LOG
          - METRIC

      - from_state: VECTORIZED
        to_state: INDEXED
        event: INDEXING_COMPLETED
        intents_emitted:
          - STATE_UPDATE
          - LOG
          - METRIC

      - from_state: INDEXED
        to_state: COMPLETED
        event: PROCESSING_COMPLETED
        intents_emitted:
          - STATE_UPDATE
          - EVENT_PUBLISH
          - LOG
          - METRIC

      - from_state: "*"
        to_state: FAILED
        event: ERROR_OCCURRED
        intents_emitted:
          - STATE_UPDATE
          - EVENT_PUBLISH
          - LOG

  PATTERN_LEARNING:
    description: "4-phase pattern learning FSM"

    states:
      - name: FOUNDATION
        is_initial: true
        is_final: false
      - name: MATCHING
        is_initial: false
        is_final: false
      - name: VALIDATION
        is_initial: false
        is_final: false
      - name: TRACEABILITY
        is_initial: false
        is_final: false
      - name: COMPLETED
        is_initial: false
        is_final: true

    transitions:
      - from_state: FOUNDATION
        to_state: MATCHING
        event: FOUNDATION_LOADED
        intents_emitted:
          - STATE_UPDATE
          - DATA_FETCH
          - WORKFLOW_TRIGGER

      - from_state: MATCHING
        to_state: VALIDATION
        event: PATTERNS_MATCHED
        intents_emitted:
          - STATE_UPDATE
          - CACHE_WRITE

      - from_state: VALIDATION
        to_state: TRACEABILITY
        event: PATTERNS_VALIDATED
        intents_emitted:
          - STATE_UPDATE

      - from_state: TRACEABILITY
        to_state: COMPLETED
        event: LINEAGE_TRACKED
        intents_emitted:
          - STATE_UPDATE
          - EVENT_PUBLISH

  QUALITY_ASSESSMENT:
    description: "Quality assessment FSM"

    states:
      - name: RAW
        is_initial: true
        is_final: false
      - name: ANALYZED
        is_initial: false
        is_final: false
      - name: SCORED
        is_initial: false
        is_final: false
      - name: STORED
        is_initial: false
        is_final: false
      - name: COMPLETED
        is_initial: false
        is_final: true

    transitions:
      - from_state: RAW
        to_state: ANALYZED
        event: ANALYSIS_COMPLETED
        intents_emitted:
          - STATE_UPDATE
          - WORKFLOW_TRIGGER

      - from_state: ANALYZED
        to_state: SCORED
        event: SCORING_COMPLETED
        intents_emitted:
          - STATE_UPDATE
          - CACHE_WRITE

      - from_state: SCORED
        to_state: STORED
        event: STORAGE_COMPLETED
        intents_emitted:
          - STATE_UPDATE

      - from_state: STORED
        to_state: COMPLETED
        event: PROCESSING_COMPLETED
        intents_emitted:
          - STATE_UPDATE
          - EVENT_PUBLISH

# Input/output schemas
input_schema:
  type: object
  properties:
    fsm_type:
      type: string
      enum: [INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT]
    entity_id:
      type: string
    current_state:
      type: string
    event:
      type: string
    metadata:
      type: object
  required: [fsm_type, entity_id, current_state, event]

output_schema:
  type: object
  properties:
    success:
      type: boolean
    result:
      type: object
      properties:
        previous_state:
          type: string
        new_state:
          type: string
        entity_id:
          type: string
    intents:
      type: array
      items:
        type: object
        properties:
          intent_id:
            type: string
            format: uuid
          intent_type:
            type: string
          target:
            type: string
          payload:
            type: object
          timestamp:
            type: string
            format: date-time
  required: [success, result, intents]
```

---

## Compute Node Contracts

### Vectorization Compute Contract

```yaml
# nodes/vectorization_compute/v1_0_0/contracts/compute_contract.yaml
node_type: compute
node_name: vectorization_compute
version:
  major: 1
  minor: 0
  patch: 0

subcontracts:
  processing: ./subcontracts/processing.yaml
  management: ./subcontracts/management.yaml
  monitoring: ./subcontracts/monitoring.yaml

capabilities:
  - PURE_COMPUTATION
  - BATCH_PROCESSING
  - CONCURRENT_EXECUTION

purity_guarantee: true
stateless: true

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

### Vectorization Processing Subcontract

```yaml
# contracts/subcontracts/processing.yaml
subcontract_name: processing
version:
  major: 1
  minor: 0
  patch: 0

operations:
  - operation_id: GENERATE_EMBEDDINGS
    description: "Generate embeddings for text"
    pure: true

    input_schema:
      type: object
      properties:
        operation_type:
          type: string
          enum: [GENERATE_EMBEDDINGS, BATCH_VECTORIZE, SEMANTIC_SIMILARITY]
        text:
          type: string
          minLength: 1
          maxLength: 100000
        model:
          type: string
          default: "sentence-transformers/all-MiniLM-L6-v2"
        normalize:
          type: boolean
          default: true
      required: [operation_type, text]

    output_schema:
      type: object
      properties:
        success:
          type: boolean
        embeddings:
          type: array
          items:
            type: number
        dimension:
          type: integer
        model:
          type: string
        execution_time_ms:
          type: integer
      required: [success, embeddings, dimension]

    performance:
      timeout_ms: 10000
      target_p95_ms: 1000
      target_p99_ms: 2000

    resource_limits:
      max_memory_mb: 512
      max_cpu_percent: 80

  - operation_id: BATCH_VECTORIZE
    description: "Batch vectorization of multiple texts"
    pure: true

    input_schema:
      type: object
      properties:
        operation_type:
          type: string
          const: BATCH_VECTORIZE
        texts:
          type: array
          items:
            type: string
          minItems: 1
          maxItems: 100
        model:
          type: string
        normalize:
          type: boolean
      required: [operation_type, texts]

    output_schema:
      type: object
      properties:
        success:
          type: boolean
        batch_embeddings:
          type: array
          items:
            type: array
            items:
              type: number
        count:
          type: integer
        execution_time_ms:
          type: integer
      required: [success, batch_embeddings, count]

    performance:
      timeout_ms: 60000
      target_p95_ms: 5000
      target_p99_ms: 10000
```

---

## Effect Node Contracts

### Kafka Event Effect Contract

```yaml
# nodes/ingestion_effect/v1_0_0/contracts/effect_contract.yaml
node_type: effect
node_name: ingestion_effect
version:
  major: 1
  minor: 0
  patch: 0

subcontracts:
  processing: ./subcontracts/processing.yaml
  management: ./subcontracts/management.yaml
  monitoring: ./subcontracts/monitoring.yaml

external_dependencies:
  - name: kafka
    type: message_broker
    endpoints:
      - omninode-bridge-redpanda:9092
    health_check:
      type: tcp
      port: 9092
      interval_ms: 30000

circuit_breaker:
  failure_threshold: 5
  recovery_timeout_ms: 60000
  half_open_max_calls: 3

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

### Kafka Processing Subcontract

```yaml
# contracts/subcontracts/processing.yaml
subcontract_name: processing
version:
  major: 1
  minor: 0
  patch: 0

operations:
  - operation_id: PUBLISH_EVENT
    description: "Publish event to Kafka topic"

    input_schema:
      type: object
      properties:
        operation_type:
          type: string
          const: PUBLISH_EVENT
        topic:
          type: string
          pattern: "^dev\\.intelligence\\.[a-z_]+\\.[a-z_]+\\.v[0-9]+$"
        event:
          type: object
        correlation_id:
          type: string
          format: uuid
        headers:
          type: object
      required: [operation_type, topic, event]

    output_schema:
      type: object
      properties:
        success:
          type: boolean
        message_id:
          type: string
        partition:
          type: integer
        offset:
          type: integer
        timestamp:
          type: string
          format: date-time
      required: [success]

    performance:
      timeout_ms: 3000
      target_p95_ms: 100
      target_p99_ms: 500

    retry_policy:
      max_attempts: 3
      backoff_ms: 1000
      backoff_multiplier: 2.0
      max_backoff_ms: 10000

  - operation_id: PUBLISH_DLQ
    description: "Publish failed event to dead-letter queue"

    input_schema:
      type: object
      properties:
        operation_type:
          type: string
          const: PUBLISH_DLQ
        original_topic:
          type: string
        event:
          type: object
        error:
          type: object
          properties:
            message:
              type: string
            stack_trace:
              type: string
            error_code:
              type: string
        retry_count:
          type: integer
          minimum: 0
      required: [operation_type, original_topic, event, error]

    output_schema:
      type: object
      properties:
        success:
          type: boolean
        dlq_topic:
          type: string
        message_id:
          type: string
      required: [success]

    performance:
      timeout_ms: 3000
      target_p95_ms: 100

    retry_policy:
      max_attempts: 1  # DLQ publish should not retry
```

---

## Model Classes from omnibase_core

### Using Correct Classes

```python
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.models.contracts import (
    ModelNodeContract,
    ModelSubcontract,
    ModelOperationSpec,
)
from omnibase_core.models.metadata import (
    ModelNodeMetadata,
    ModelPerformanceTarget,
)
from omnibase_core.enums import (
    EnumNodeType,
    EnumCapability,
)

# Version specification
version = ModelSemVer(major=1, minor=0, patch=0)

# Operation spec
operation_spec = ModelOperationSpec(
    operation_id="GENERATE_EMBEDDINGS",
    description="Generate embeddings for text",
    input_schema={...},
    output_schema={...},
    performance=ModelPerformanceTarget(
        timeout_ms=10000,
        target_p95_ms=1000,
        target_p99_ms=2000
    ),
    pure=True
)

# Node metadata
metadata = ModelNodeMetadata(
    node_name="vectorization_compute",
    node_type=EnumNodeType.COMPUTE,
    version=version,
    capabilities=[
        EnumCapability.PURE_COMPUTATION,
        EnumCapability.BATCH_PROCESSING
    ]
)
```

---

## Summary of Corrections

### ✅ Version Management
- Use `ModelSemVer` with major/minor/patch fields
- Never use version strings

### ✅ Contract Structure
- Main contract references subcontracts
- Subcontracts: processing, management, monitoring
- All version fields use ModelSemVer format

### ✅ Model Classes
- Use omnibase_core.models classes
- Use omnibase_core.enums for type-safe enumerations
- Use convenience classes for common patterns

### ✅ YAML Structure
- Proper subcontract references
- Version objects with major/minor/patch
- Complete schema definitions
- Performance targets and resource limits

---

**Action Required**: Update all contracts in the migration plan to follow these patterns.
