# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Shared Infrastructure**: For PostgreSQL, Kafka/Redpanda, remote server topology (192.168.86.200), Docker networking, and environment variables, see **`~/.claude/CLAUDE.md`**. This file covers OmniIntelligence-specific architecture only.

## Overview

OmniIntelligence is a migration/rebuild of the legacy `omniarchon` intelligence platform into canonical ONEX nodes following the Omninode architecture patterns. The system provides code quality analysis, pattern learning, semantic analysis, and intelligence APIs as first-class nodes. (Vector storage operations are handled by the `omnimemory` repository.)

## Development Commands

```bash
# Install dependencies (using uv)
uv sync --group dev        # Development dependencies
uv sync --group core       # Core node system + infrastructure
uv sync --group all        # Everything

# Run tests
pytest                     # All tests
pytest tests/unit          # Unit tests only
pytest tests/integration   # Integration tests (requires infrastructure)
pytest -k "test_name"      # Single test by name
pytest --cov=src/omniintelligence --cov-report=html  # With coverage

# Code quality
ruff check src tests       # Lint
ruff check --fix src tests # Auto-fix
black src tests            # Format
isort src tests            # Sort imports
mypy src                   # Type check
```

## Architecture

The system decomposes intelligence operations into specialized ONEX nodes following a four-node pattern:

### Node Types

| Type | Purpose | Examples |
|------|---------|----------|
| **Orchestrator** | Coordinate workflows, route operations | `intelligence_orchestrator` |
| **Reducer** | Manage state, FSM transitions | `intelligence_reducer` (unified, handles all FSMs via fsm_type) |
| **Compute** | Pure data processing, no side effects | `pattern_learning_compute`, `quality_scoring_compute`, `semantic_analysis_compute` |
| **Effect** | External I/O (Kafka, DB, HTTP) | `intelligence_adapter` |

### Operation Flow

```
Client Request
    ↓
Orchestrator (routes to workflows)
    ↓
├── Compute Nodes (pattern learning, quality scoring, semantic analysis)
├── Reducer Nodes (state management, FSM)
└── Effect Nodes (Kafka publish, external service calls)
```

### Key Orchestrator Workflows

The `IntelligenceOrchestrator` uses Llama Index workflows to coordinate:

- **PATTERN_LEARNING**: 4-phase (Foundation → Matching → Validation → Traceability)
- **QUALITY_ASSESSMENT**: Score code quality → Check ONEX compliance → Generate recommendations
- **SEMANTIC_ANALYSIS**: Generate embeddings → Compute similarity → Return results
- **PATTERN_ASSEMBLY**: Assemble patterns from execution traces and success criteria

> **Note**: Vector storage and graph operations (Qdrant, Memgraph) are handled by the `omnimemory` repository.

## Node Development Pattern

Each node follows a versioned canonical structure:

```
nodes/
└── node_name/
    ├── __init__.py
    └── v1_0_0/
        ├── contracts/           # YAML contract definitions
        ├── models/              # Pydantic models
        ├── node.py              # Main implementation
        ├── introspection.py     # Introspection support
        ├── scenarios/           # Integration test scenarios
        └── node_tests/          # Node-specific tests
```

### Naming Conventions

- **Effect nodes**: `Node{Name}Effect` (e.g., `NodeIntelligenceAdapterEffect`)
- **Compute nodes**: `Node{Name}Compute`
- **Reducer nodes**: `Node{Name}Reducer`
- **Orchestrator nodes**: `Node{Name}Orchestrator`

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `omnibase_core` | ONEX node base classes, error handling, validation |
| `omnibase_spi` | Service Provider Interface protocols |
| `omninode_bridge` | Intelligence service clients, API contracts |
| `llama_index` | Workflow orchestration |
| `confluent-kafka` | Kafka consumer/producer |

## Event-Driven Architecture

### Kafka Topics (prefix: `dev.archon-intelligence.`)

- `intelligence.code-analysis-requested.v1` - Trigger code analysis
- `intelligence.code-analysis-completed.v1` - Analysis results
- `intelligence.code-analysis-failed.v1` - Analysis failures
- `.dlq` suffix topics for dead letter queues

### Event Flow Pattern

```python
# Effect nodes consume events, process, and publish results
class NodeIntelligenceAdapterEffect:
    async def _consume_events_loop(self):
        # 1. Poll Kafka for messages
        # 2. Route to operation handler
        # 3. Publish completion/failure event
        # 4. Commit offset
```

### DLQ Routing

All effect nodes implement Dead Letter Queue routing for failed messages with full context (original payload, error details, processing metadata).

## Testing

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures (Kafka mocks, sample data)
├── unit/                    # Unit tests (no infrastructure)
├── integration/             # Integration tests (requires Kafka, DBs)
└── nodes/                   # Node-specific tests
```

### Key Fixtures

- `mock_kafka_consumer/producer` - For testing event-driven nodes
- `mock_intelligence_client` - Mock Archon intelligence service
- `sample_code`, `sample_metadata` - Test data
- `correlation_id` - Trace testing

### pytest Markers

```bash
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests
pytest -m slow          # Slow tests
pytest -m performance   # Performance benchmarks
```

## Intelligence Operations (45+)

Operation types are defined in `EnumIntelligenceOperationType`:

- **Quality Assessment**: `assess_code_quality`, `analyze_document_quality`, `get_quality_patterns`, `check_architectural_compliance`
- **Pattern Learning**: `pattern_match`, `hybrid_score`, `semantic_analyze`, `get_pattern_metrics`, `get_cache_stats`, `clear_pattern_cache`, `get_pattern_health`
- **Performance**: `establish_performance_baseline`, `identify_optimization_opportunities`, `apply_performance_optimization`, `get_optimization_report`, `monitor_performance_trends`
- **Document Freshness**: `analyze_document_freshness`, `get_stale_documents`, `refresh_documents`, `get_freshness_stats`, `get_document_freshness`, `cleanup_freshness_data`
- **Vector Operations**: `advanced_vector_search`, `quality_weighted_search`, `batch_index_documents`, `get_vector_stats`, `optimize_vector_index`
- **Pattern Traceability**: `track_pattern_lineage`, `get_pattern_lineage`, `get_execution_logs`, `get_execution_summary`
- **Autonomous Learning**: `ingest_patterns`, `record_success_pattern`, `predict_agent`, `predict_execution_time`, `calculate_safety_score`, `get_autonomous_stats`, `get_autonomous_health`

## Migration Context

Legacy source code is preserved in `migration_sources/omniarchon/` for reference. See:
- `docs/migrations/omniarchon_to_omniintelligence.md` - Migration guide
- `docs/migrations/NODE_MAPPING_REFERENCE.md` - Node mapping reference
- `docs/migrations/CONTRACT_CORRECTIONS.md` - Contract corrections
- `docs/migrations/ONEX_MIGRATION_PLAN.md` - Detailed migration plan

## Configuration

Configuration uses Pydantic Settings with environment variables:

```python
from omniintelligence.models import ModelIntelligenceConfig

config = ModelIntelligenceConfig.from_environment_variable()
# Uses: INTELLIGENCE_SERVICE_URL, INTELLIGENCE_TIMEOUT, etc.
```

### Kafka Connection (CRITICAL)

Use correct bootstrap servers based on context:
- **Docker services**: `omninode-bridge-redpanda:9092`
- **Host scripts**: `192.168.86.200:29092`

See `~/.claude/CLAUDE.md` for full infrastructure topology.
