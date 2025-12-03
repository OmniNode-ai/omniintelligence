# Handoff Document: Intelligence Orchestrator Full Implementation

**Date**: 2025-11-29
**Branch**: `feature/intelligence-nodes-migration`
**Last Commit**: `ffed34c fix: address all PR #3 review feedback`

---

## Session Summary

### Completed Work (PR #3 Fixes)

13 issues fixed and committed:

| Priority | Issue | File | Fix |
|----------|-------|------|-----|
| CRITICAL | Git dependencies | `pyproject.toml` | `branch="main"` → `tag="v0.1.0"` |
| CRITICAL | Kafka idempotence | `event_publisher.py` | Disabled idempotence (app-level retries) |
| CRITICAL | Blocking commit | `node_intelligence_adapter_effect.py` | `asynchronous=True` |
| MAJOR | DLQ routing | `node_intelligence_adapter_effect.py` | Full implementation with topic routing |
| MAJOR | Pydantic v2 | `model_intelligence_config.py` | `ConfigDict()` pattern |
| MAJOR | Unused vars | `node_intent_classifier_compute.py` | Removed dead code |
| MINOR | Comment count | `enum_intelligence_operation_type.py` | "(11)" → "(4)" |
| MINOR | Regex hyphens | `model_event_envelope.py` | `[a-z_-]+` |
| MINOR | success default | `model_intelligence_output.py` | `False` (fail-safe) |
| MINOR | Flaky assertion | `node_context_keyword_extractor_compute.py` | Removed |
| MINOR | Keyword overlap | `node_context_keyword_extractor_compute.py` | Fixed STOP_WORDS |
| MINOR | Normalization | `node_intent_classifier_compute.py` | Sum-based |
| MINOR | Circuit breaker test | `test_node_intelligence_adapter_effect.py` | State verification |

### Investigation Results

| Issue | Verdict |
|-------|---------|
| SQL Injection in Reducer | **SAFE** - Uses parameterized queries |
| DLQ Secret Sanitization | **SAFE** - Correct timing |
| Orchestrator Placeholders | **BLOCKING** - All 5 workflows return fake data |

---

## Remaining Work: Orchestrator Full Implementation

### The Problem

All 5 workflows in `orchestrator.py` return hardcoded placeholder data:

```python
# Example from QualityAssessmentWorkflow
results = {
    "overall_score": 0.85,      # ALWAYS 0.85
    "onex_compliant": True,     # ALWAYS True
}
```

### Files to Modify

1. **Orchestrator**: `src/omniintelligence/nodes/intelligence_orchestrator/v1_0_0/orchestrator.py`
2. **VectorizationCompute**: `src/omniintelligence/nodes/vectorization_compute/v1_0_0/compute.py`
3. **QualityScoringCompute**: `src/omniintelligence/nodes/quality_scoring_compute/v1_0_0/compute.py`

### Existing Node Structure

```
src/omniintelligence/nodes/
├── intelligence_orchestrator/v1_0_0/orchestrator.py  # LlamaIndex Workflow orchestrator
├── vectorization_compute/v1_0_0/compute.py           # Returns zero embeddings
├── quality_scoring_compute/v1_0_0/compute.py         # Returns hardcoded 0.85
├── intelligence_reducer/v1_0_0/reducer.py            # FSM state machine (working)
├── intelligence_adapter/node_intelligence_adapter_effect.py  # Kafka consumer (working)
└── pattern_extraction/                               # Intent classifiers (working)
```

### Compute Node Interface Pattern

```python
class VectorizationCompute(NodeOmniAgentCompute[
    ModelVectorizationInput,
    ModelVectorizationOutput,
    ModelVectorizationConfig
]):
    async def process(self, input_data: ModelVectorizationInput) -> ModelVectorizationOutput:
        # IMPLEMENT: Call embedding API
        pass
```

---

## Environment Configuration

**.env file copied from omniarchon** (added to .gitignore)

### Key Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| **Embedding API** | `http://192.168.86.201:8002` | GTE embeddings (RTX 4090) |
| **vLLM DeepSeek** | `http://192.168.86.201:8000/v1` | Code generation |
| **Qdrant** | `http://localhost:6333` | Vector storage |
| **Memgraph** | `bolt://localhost:7687` | Knowledge graph |
| **PostgreSQL** | `192.168.86.200:5436` | Traceability DB |

### Embedding Model

```
EMBEDDING_MODEL_URL=http://192.168.86.201:8002
EMBEDDING_MODEL=text-embedding-gte
```

**NOT OpenAI** - Uses local GTE model on GPU server.

---

## Implementation Plan

### Phase 1: VectorizationCompute (Priority 1)

Wire up to local embedding API:

```python
async def process(self, input_data: ModelVectorizationInput) -> ModelVectorizationOutput:
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{os.getenv('EMBEDDING_MODEL_URL')}/v1/embeddings",
            json={"input": input_data.content, "model": "text-embedding-gte"}
        )
        data = response.json()
        embeddings = data["data"][0]["embedding"]

    return ModelVectorizationOutput(
        success=True,
        embeddings=embeddings,
        model_used="text-embedding-gte",
    )
```

### Phase 2: QualityScoringCompute (Priority 2)

Options:
- Call Intelligence Service API at `http://localhost:8053/assess/code`
- Implement local AST analysis
- Use LLM for code review

### Phase 3: Wire Orchestrator Workflows

Connect workflows to compute nodes:

```python
class QualityAssessmentWorkflow(Workflow):
    @step
    async def start(self, ctx: Context, ev: StartEvent) -> StopEvent:
        # Instead of placeholder:
        quality_compute = QualityScoringCompute(config)
        result = await quality_compute.process(ModelQualityScoringInput(
            file_path=payload.get("file_path"),
            content=payload.get("content"),
            language=payload.get("language", "python"),
        ))
        return StopEvent(result=result.model_dump())
```

### Phase 4: Add Missing Effect Nodes

Create these effect nodes that don't exist:
- `qdrant_vector_effect` - Store vectors
- `memgraph_graph_effect` - Store relationships
- `kafka_event_effect` - Publish events

---

## Test Coverage Gaps

| Component | Tests | Status |
|-----------|-------|--------|
| VectorizationCompute | 0 | **MISSING** |
| QualityScoringCompute | 0 | **MISSING** |
| EventPublisher | 0 | **MISSING** (628 lines!) |
| Orchestrator workflows | 6 | Incomplete |
| Reducer FSM | 4 | Incomplete |

---

## Commands to Resume

```bash
# Navigate to project
cd /Volumes/PRO-G40/Code/omniintelligence

# Check current state
git status
git log --oneline -5

# Run tests
poetry run pytest tests/ -v

# Key files to edit
code src/omniintelligence/nodes/vectorization_compute/v1_0_0/compute.py
code src/omniintelligence/nodes/intelligence_orchestrator/v1_0_0/orchestrator.py
```

---

## Next Session Prompt

```
Continue implementing the Intelligence Orchestrator. See HANDOFF_ORCHESTRATOR_IMPLEMENTATION.md for full context.

Priority:
1. Implement VectorizationCompute to call embedding API at http://192.168.86.201:8002
2. Wire QualityAssessmentWorkflow to call QualityScoringCompute
3. Wire DocumentIngestionWorkflow to call VectorizationCompute
4. Add tests for compute nodes

Environment is configured in .env (from omniarchon).
```

---

## Architecture Reference

```
┌─────────────────────────────────────────────────────────────┐
│                 IntelligenceOrchestrator                     │
│  (LlamaIndex Workflows)                                      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Document     │  │ Quality      │  │ Pattern      │       │
│  │ Ingestion    │  │ Assessment   │  │ Learning     │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │                │
└─────────┼─────────────────┼─────────────────┼────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Vectorization   │ │ QualityScoring  │ │ PatternMatching │
│ Compute         │ │ Compute         │ │ Compute         │
│ (GTE @ :8002)   │ │ (AST/LLM)       │ │ (TBD)           │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Qdrant Effect   │ │ Intelligence    │ │ Postgres Effect │
│ (Vector Store)  │ │ API Effect      │ │ (Lineage)       │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```
