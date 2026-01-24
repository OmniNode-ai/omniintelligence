# OMN-1437: Intelligence Adapter - Architecture Decision Required

**Status**: RESOLVED - Decision made, node deleted as furniture
**PR**: https://github.com/OmniNode-ai/omniintelligence/pull/20
**Date**: 2026-01-24

---

## What Was Done

Refactored `NodeIntelligenceAdapterEffect` from 2397-line monolith to ~140-line shell:
- Extracted event models to `omniintelligence/models/events/`
- Extracted enums to `omniintelligence/enums/enum_code_analysis.py`
- Created `HandlerCodeAnalysisRequested` implementing `ProtocolMessageHandler`
- Enabled `handler_routing` in contract.yaml
- Moved legacy monolith to `migration_sources/`

---

## The Problem

**The node is furniture, not architecture.**

The handler I created does this:
```python
async def _execute_analysis(self, payload, correlation_id):
    base_result = {"success": True, ...}  # ← FAKE DATA
    quality_result = transform_quality_response(base_result)  # ← just transforms nothing
    return quality_result
```

There is **no intelligence service** to call. The node:
- Consumes `code-analysis-requested.v1`
- Pretends to do analysis (but actually does nothing)
- Emits `completed/failed`

This is a lie with good docstrings.

---

## Decision Required

### Option A: Delete the Node Entirely

If the orchestrator (`intelligence_orchestrator/`) already handles coordination:
- Delete `intelligence_adapter/`
- Move any useful pieces to compute nodes or orchestrator
- External events go directly to orchestrator

### Option B: Convert to Orchestrator

Rename to `NodeCodeAnalysisOrchestrator` and make it actually call compute nodes:
```
code-analysis-requested.v1
    ↓
NodeCodeAnalysisOrchestrator
    ├── quality_scoring_compute
    ├── pattern_learning_compute
    └── semantic_analysis_compute
    ↓
code-analysis-completed.v1
```

### Option C: Convert to Honest Ingress Effect

If boundary enforcement is needed:
- Rename to `NodeCodeAnalysisIngressEffect`
- Only does: validation, normalization, metadata stamping
- Publishes internal work order event
- Orchestrator handles actual workflow

---

## Files Changed in PR

| File | Status |
|------|--------|
| `models/events/__init__.py` | NEW - event payload models |
| `models/events/model_code_analysis_*.py` | NEW - 3 payload models |
| `enums/enum_code_analysis.py` | NEW - analysis enums |
| `handlers/handler_code_analysis_requested.py` | NEW - **FAKE** handler |
| `handlers/handler_unknown_event.py` | NEW - fallback handler |
| `intelligence_adapter/node.py` | NEW - minimal shell |
| `intelligence_adapter/contract.yaml` | MODIFIED - handler_routing enabled |
| `migration_sources/...` | MOVED - legacy monolith |

---

## Existing Architecture (Already in Place)

**`NodeIntelligenceOrchestrator` already exists and does coordination:**

```yaml
# From intelligence_orchestrator/contract.yaml
workflow_coordination:
  execution_graph:
    nodes:
      - node_id: "route_operation"
        routing_field: "operation_type"
        routing_strategy: "operation_type_match"
      - node_id: "execute_compute"
        dispatch_strategy: "dynamic_compute_selection"
        available_compute_nodes:
          - pattern_matching_compute
          - quality_scoring_compute
          - semantic_analysis_compute
```

The orchestrator:
- Routes based on `operation_type`
- Dispatches to compute nodes
- Already has workflow_coordination defined

**The `intelligence_adapter` node I created is orphaned.**

---

## Questions to Answer

1. **Is the orchestrator event-driven (Kafka) or request-driven (direct call)?**
   - Check if orchestrator has `consumed_events` in contract
   - If event-driven → adapter is 100% redundant

2. **Do we need boundary enforcement before orchestrator?**
   - Validation, rate limiting, auth?
   - If yes → convert adapter to ingress effect
   - If no → delete adapter entirely

3. **What's the entry point for analysis today?**
   - Direct `process()` call on orchestrator?
   - Kafka event consumption?
   - HTTP API?

---

## Litmus Test

> If you can delete the node and nothing meaningful breaks except "we lose a place to put comments," then it wasn't architecture — it was furniture.

---

## Recommendation

Based on review, **delete `intelligence_adapter`** because:

1. `NodeIntelligenceOrchestrator` already exists with full workflow coordination
2. Compute nodes (`quality_scoring_compute`, `pattern_matching_compute`, `semantic_analysis_compute`) do actual work
3. The "adapter" has no real job - it's furniture

**Keep the extracted models/enums** - they're useful regardless:
- `omniintelligence/models/events/` - event payloads
- `omniintelligence/enums/enum_code_analysis.py` - analysis enums

---

## Final Decision

**Decision: Option 2 - ONEX-native consumption via RuntimeHostProcess**

### The Architectural Principle

**RuntimeHostProcess owns Kafka consumption, not effect nodes.**

The canonical ONEX architecture is:
```
Hooks emit events → RuntimeHostProcess consumes → Nodes process
```

Effect nodes perform side effects (Memgraph writes, Kafka emission, HTTP calls) but they **do not own consumer loops**. There is **one ingress path only** - through RuntimeHostProcess.

### Why This Decision

1. **RuntimeHostProcess is the canonical Kafka boundary** - It's the established pattern in ONEX for event consumption
2. **Effect nodes do side effects, not consumption** - An effect node that owns a Kafka consumer loop violates ONEX separation of concerns
3. **The intelligence_adapter was furniture** - It consumed events and pretended to do analysis, but had no actual work to perform
4. **Orchestrator handles coordination** - `NodeIntelligenceOrchestrator` already exists with full workflow coordination via LlamaIndex workflows

### What Was Done

| Action | Item |
|--------|------|
| **DELETED** | `src/omniintelligence/nodes/intelligence_adapter/` directory |
| **DELETED** | `src/omniintelligence/handlers/handler_code_analysis_requested.py` |
| **DELETED** | `src/omniintelligence/handlers/handler_unknown_event.py` |
| **KEPT** | `src/omniintelligence/models/events/` - Event payload models (useful as contracts) |
| **KEPT** | `src/omniintelligence/enums/enum_code_analysis.py` - Analysis enums |

### Key Architectural Principles Established

1. **One ingress path**: Events flow through RuntimeHostProcess, not through effect node consumer loops
2. **Effect nodes do side effects**: Write to Memgraph, emit to Kafka, call HTTP endpoints - but don't own consumers
3. **Extracted models are contracts**: The event models (`ModelCodeAnalysisRequest`, `ModelCodeAnalysisCompleted`, etc.) serve as event contracts for producers/consumers
4. **Orchestrators coordinate**: Workflow orchestration happens in orchestrator nodes, not in adapter/ingress effects

### Future Implementation Path

When external Kafka events need to trigger intelligence workflows:

1. **RuntimeHostProcess** consumes `code-analysis-requested.v1`
2. **RuntimeHostProcess** calls `NodeIntelligenceOrchestrator.process()`
3. **Orchestrator** routes to appropriate compute nodes
4. **Effect nodes** emit `code-analysis-completed.v1` or `code-analysis-failed.v1`

This maintains the canonical ONEX pattern: single ingress, orchestrator coordination, effect-based egress.

---

## Lessons Learned

1. **Architecture vs Furniture Test**: If you can delete a node and nothing meaningful breaks except "we lose a place to put comments," it wasn't architecture - it was furniture.

2. **Question Consumer Ownership**: When creating an effect node, ask: "Should this node own a consumer loop, or should RuntimeHostProcess own consumption and dispatch to this node?"

3. **Extract Models Regardless**: Even when deleting a node, extracted models/enums have value as event contracts. Keep clean extractions.
