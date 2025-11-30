# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Shared Infrastructure**: For PostgreSQL, Kafka/Redpanda, remote server topology (192.168.86.200), Docker networking, and environment variables, see **`~/.claude/CLAUDE.md`**. This file covers OmniIntelligence-specific architecture only.

## Overview

OmniIntelligence is a migration/rebuild of the legacy `omniarchon` intelligence platform into canonical ONEX nodes following the Omninode architecture patterns. The system provides code quality analysis, pattern learning, vectorization, and intelligence APIs as first-class nodes.

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
| **Reducer** | Manage state, FSM transitions | `intelligence_reducer`, `ingestion_reducer` |
| **Compute** | Pure data processing, no side effects | `vectorization_compute`, `pattern_learning_compute`, `quality_scoring_compute` |
| **Effect** | External I/O (Kafka, DB, HTTP) | `ingestion_effect`, `intelligence_api_effect`, `intelligence_adapter` |

### Operation Flow

```
Client Request
    ↓
Orchestrator (routes to workflows)
    ↓
├── Compute Nodes (vectorization, pattern learning, quality scoring)
├── Reducer Nodes (state management, FSM)
└── Effect Nodes (Kafka publish, Qdrant/Memgraph storage)
```

### Key Orchestrator Workflows

The `IntelligenceOrchestrator` uses Llama Index workflows to coordinate:

- **DOCUMENT_INGESTION**: Vectorize → Extract entities → Store in Qdrant/Memgraph
- **PATTERN_LEARNING**: 4-phase (Foundation → Matching → Validation → Traceability)
- **QUALITY_ASSESSMENT**: Score code quality → Check ONEX compliance → Generate recommendations
- **SEMANTIC_ANALYSIS**: Generate embeddings → Compute similarity → Store vectors
- **RELATIONSHIP_DETECTION**: Detect relationships → Classify → Store in graph

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

- **Quality Assessment**: `assess_code_quality`, `assess_document`, `compliance/check`
- **Pattern Learning**: `pattern/match`, `hybrid/score`, `semantic/analyze`
- **Performance**: `baseline`, `opportunities`, `optimize`, `trends`
- **Vectorization**: Semantic search, indexing, batch operations
- **Traceability**: Lineage tracking, execution logs, analytics

## Migration Context

Legacy source code is preserved in `migration_sources/omniarchon/` for reference. See:
- `MIGRATION_SUMMARY.md` - Migration overview
- `OMNIARCHON_MIGRATION_INVENTORY.md` - Detailed component inventory
- `QUICK_REFERENCE.md` - Legacy API reference

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
