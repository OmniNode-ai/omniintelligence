# Intelligence Adapter Architecture Considerations

> **Status**: Future Consideration (v2.0)
> **Created**: 2026-01-18
> **Origin**: PR Review Feedback - NITPICK item

## Overview

This document captures architectural considerations for the `intelligence_adapter` node, specifically the recommendation to decompose it into smaller, more focused adapters. This is a **future consideration** and does not require immediate action.

---

## Current State

### NodeIntelligenceAdapterEffect Responsibilities

The current `NodeIntelligenceAdapterEffect` handles multiple responsibilities:

#### 1. Kafka Event Infrastructure (Lines 301-604)
- Consumer lifecycle management (`initialize()`, `shutdown()`)
- Event consumption loop (`_consume_events_loop()`)
- Message routing (`_route_event_to_operation()`)
- Dead Letter Queue routing (`_route_to_dlq()`)
- Event publishing (completed/failed events)

#### 2. Multiple Intelligence Operations (Lines 1097-1339)
The `analyze_code()` method handles four distinct operation types:

| Operation Type | Backend Endpoint | Transform Method |
|---------------|------------------|------------------|
| `assess_code_quality` | `/assess/code` | `_transform_quality_response()` |
| `check_architectural_compliance` | `/assess/code` | `_transform_quality_response()` |
| `analyze_performance` | `/patterns/performance` | `_transform_performance_response()` |
| `get_quality_patterns` | `/patterns/extract` | `_transform_pattern_response()` |

#### 3. Response Transformation (Lines 1379-1568)
- `_transform_quality_response()` - Quality assessment results
- `_transform_performance_response()` - Performance analysis results
- `_transform_pattern_response()` - Pattern detection results

#### 4. Metrics and Statistics (Lines 1614-1652)
- Analysis statistics tracking (`get_analysis_stats()`)
- Kafka event metrics (`get_metrics()`)
- Processing time tracking

---

## Potential Decomposition

### Option A: Operation-Based Split

Decompose into adapters based on intelligence operation domain:

```
nodes/
├── intelligence_adapter/              # Base infrastructure (Kafka)
│   ├── node_intelligence_adapter_effect.py  # Consumer/publisher only
│   └── contract.yaml
├── quality_adapter/                   # Quality assessment operations
│   ├── node_quality_adapter_effect.py
│   └── contract.yaml
├── pattern_adapter/                   # Pattern detection operations
│   ├── node_pattern_adapter_effect.py
│   └── contract.yaml
└── performance_adapter/               # Performance analysis operations
    ├── node_performance_adapter_effect.py
    └── contract.yaml
```

**Responsibilities**:
- `intelligence_adapter` - Kafka infrastructure, event routing, DLQ
- `quality_adapter` - `assess_code_quality`, `check_architectural_compliance`, ONEX compliance
- `pattern_adapter` - `get_quality_patterns`, pattern matching, semantic analysis
- `performance_adapter` - `analyze_performance`, optimization opportunities

### Option B: Layer-Based Split

Decompose into infrastructure vs business logic layers:

```
nodes/
├── kafka_event_adapter/               # Pure Kafka infrastructure
│   ├── node_kafka_event_adapter_effect.py
│   └── contract.yaml
└── intelligence_router/               # Operation routing and transformation
    ├── node_intelligence_router_compute.py
    └── contract.yaml
```

### Option C: Handler-Based Architecture (Contract-Defined)

The contract.yaml already sketches a handler-based architecture (currently commented):

```yaml
handler_routing:
  routing_strategy: "payload_type_match"
  handlers:
    - operation: "analyze_code"
      handler: HandlerAnalyzeCode
    - operation: "assess_quality"
      handler: HandlerAssessQuality
    - operation: "detect_patterns"
      handler: HandlerDetectPatterns
    - operation: "analyze_performance"
      handler: HandlerAnalyzePerformance
```

This keeps the single adapter but moves operation logic to pluggable handlers.

---

## Tradeoffs Analysis

### Benefits of Splitting

| Benefit | Description |
|---------|-------------|
| **Single Responsibility** | Each adapter has one clear purpose |
| **Easier Testing** | Smaller units with focused test coverage |
| **Independent Scaling** | Scale quality analysis separately from performance analysis |
| **Independent Deployment** | Deploy pattern adapter without affecting quality adapter |
| **Clearer Contracts** | Each adapter has a focused contract.yaml |
| **Team Ownership** | Different teams can own different adapters |

### Costs of Splitting

| Cost | Description |
|------|-------------|
| **More Nodes to Maintain** | 3-4 adapters instead of 1 |
| **Coordination Overhead** | Cross-adapter communication needed |
| **Shared Infrastructure** | Kafka configuration duplicated |
| **Migration Effort** | Refactoring existing code and tests |
| **Consumer Group Complexity** | Multiple consumer groups to manage |

### Recommendation

**Option C (Handler-Based Architecture)** is recommended as a first step:

1. **Lower Risk**: No structural changes to node layout
2. **Incremental**: Add handlers one at a time
3. **Foundation**: Handlers can later become separate adapters
4. **Contract Support**: Already sketched in contract.yaml

If Option C proves insufficient, **Option A (Operation-Based Split)** provides the cleanest separation of concerns.

---

## Current Metrics (Reference)

From the existing implementation:

- **Code Size**: ~1650 lines in `node_intelligence_adapter_effect.py`
- **Methods**: 25+ public and private methods
- **Dependencies**: 15+ imports from omniintelligence, omnibase_core, confluent_kafka
- **Event Types**: 3 (requested, completed, failed) + DLQ
- **Operation Types**: 4 distinct operation categories

---

## Implementation Roadmap

### Phase 1: Handler Architecture (Recommended First)

1. Create `handlers/` directory in intelligence_adapter
2. Implement `HandlerAnalyzeCode` as first handler
3. Migrate `_transform_quality_response()` to handler
4. Add handler routing to main node
5. Repeat for remaining operation types

### Phase 2: Adapter Split (If Needed)

1. Extract Kafka infrastructure to base class or utility
2. Create quality_adapter with dedicated contract
3. Create pattern_adapter with dedicated contract
4. Create performance_adapter with dedicated contract
5. Update event routing to dispatch to appropriate adapter

### Phase 3: Independent Scaling

1. Configure separate consumer groups
2. Add adapter-specific health checks
3. Implement cross-adapter communication if needed
4. Deploy adapters to separate pods/containers

---

## Related Files

- `/workspace/omniintelligence/src/omniintelligence/nodes/intelligence_adapter/node_intelligence_adapter_effect.py` - Main implementation
- `/workspace/omniintelligence/src/omniintelligence/nodes/intelligence_adapter/contract.yaml` - Node contract
- `/workspace/omniintelligence/src/omniintelligence/_legacy/models/model_intelligence_api_contracts.py` - API request models

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-18 | Document as future consideration | PR review feedback; current implementation functional |
| TBD | Choose decomposition approach | Based on scaling needs and team structure |
| TBD | Begin implementation | When complexity or scaling demands warrant |

---

## References

- PR Review: Suggested splitting intelligence_adapter (NITPICK)
- ONEX 4-Node Architecture: Effect/Compute/Reducer/Orchestrator pattern
- Handler Routing Pattern: contract.yaml commented section
