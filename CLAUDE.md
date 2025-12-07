# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Shared Infrastructure**: For PostgreSQL, Kafka/Redpanda, remote server topology (192.168.86.200), Docker networking, and environment variables, see **`~/.claude/CLAUDE.md`**. This file covers OmniIntelligence-specific architecture only.

## Overview

OmniIntelligence provides code quality analysis, pattern learning, vectorization, and intelligence APIs as canonical ONEX nodes following the Omninode architecture patterns.

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

# Contract validation
python -m omniintelligence.tools.contract_linter path/to/contract.yaml           # Validate single contract
python -m omniintelligence.tools.contract_linter file1.yaml file2.yaml --verbose # Validate multiple contracts
python -m omniintelligence.tools.contract_linter contract.yaml --json            # JSON output
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

## Naming Conventions

All code artifacts must follow ONEX naming standards. See [NAMING_CONVENTIONS.md](docs/conventions/NAMING_CONVENTIONS.md) for complete reference.

### File Prefixes

| Prefix | Usage | Example |
|--------|-------|---------|
| `model_*` | Pydantic models | `model_intelligence_input.py` |
| `enum_*` | Enumerations | `enum_operation_type.py` |
| `protocol_*` | Protocol interfaces | `protocol_intelligence.py` |
| `service_*` | Service implementations | `service_quality_scoring.py` |
| `node_*` | ONEX nodes | `node_intelligence_reducer.py` |

### Node Class Naming

- **Effect nodes**: `Node{Name}Effect` (e.g., `NodeIntelligenceAdapterEffect`)
- **Compute nodes**: `Node{Name}Compute` (e.g., `NodeVectorizationCompute`)
- **Reducer nodes**: `Node{Name}Reducer` (e.g., `NodeIntelligenceReducer`)
- **Orchestrator nodes**: `Node{Name}Orchestrator` (e.g., `NodeIntelligenceOrchestrator`)

### Field Naming Quick Reference

| Pattern | Usage | Example |
|---------|-------|---------|
| `{entity}_id` | Identifiers | `task_id`, `correlation_id` |
| `{entity}_type` | Type discriminators | `event_type`, `operation_type` |
| `*_at` | Timestamps | `created_at`, `completed_at` |
| `*_ms` | Durations (milliseconds) | `timeout_ms`, `latency_ms` |
| `*_count` | Counts | `retry_count`, `completed_count` |
| `*_score` | Scores (0.0-1.0) | `confidence_score`, `quality_score` |
| `*_enabled` | Boolean feature flags | `cache_enabled`, `parallel_enabled` |
| `is_*` | Boolean state checks | `is_success`, `is_complete` |
| `has_*` | Boolean presence checks | `has_dependencies` |

### Common Mistakes

```python
# ❌ Wrong
timeout_seconds: int    # Use timeout_ms
completed_tasks: int    # Use completed_count (it's a count, not a list)
results: dict           # Use task_results (too generic)
status: str             # Use batch_status (add entity prefix)
timestamp: datetime     # Use created_at

# ✅ Correct
timeout_ms: int
completed_count: int
task_results: dict
batch_status: str
created_at: datetime
```

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

## Reference Documentation

Source reference material is preserved in `reference_sources/omniarchon/` for context. See:
- `OMNIARCHON_INVENTORY.md` - Detailed component inventory
- `QUICK_REFERENCE.md` - API reference

## Tools

OmniIntelligence provides CLI tools for development and validation:

### Contract Linter

Validates ONEX contract YAML files against canonical Pydantic models:

```bash
# Validate single contract
uv run python -m omniintelligence.tools.contract_linter path/to/contract.yaml

# Validate multiple contracts with verbose output
uv run python -m omniintelligence.tools.contract_linter file1.yaml file2.yaml --verbose

# JSON output for CI/CD integration
uv run python -m omniintelligence.tools.contract_linter contract.yaml --json
```

**Features:**
- Validates node contracts (compute, effect, reducer, orchestrator)
- Validates FSM subcontracts and workflow coordination contracts
- Integrated with pre-commit hooks and GitHub Actions CI
- Structured error output with field paths
- Exit codes: 0 (success), 1 (validation errors), 2 (file errors)

See [tools/README.md](src/omniintelligence/tools/README.md) for complete documentation.

### I/O Audit

Enforces ONEX node purity by detecting forbidden I/O patterns in compute nodes:

```bash
# Run I/O audit on default targets
uv run python -m omniintelligence.audit.io_audit

# Run with custom whitelist
uv run python -m omniintelligence.audit.io_audit --whitelist tests/audit/io_audit_whitelist.yaml
```

**Forbidden Patterns:**
- `net-client`: Network/DB client imports (confluent_kafka, httpx, asyncpg, etc.)
- `env-access`: Environment variable access (os.environ, os.getenv)
- `file-io`: File system operations (open(), Path.read_text(), FileHandler)

**Whitelist Hierarchy (CRITICAL):**

The I/O audit uses a two-level whitelist with a strict hierarchy:

1. **YAML Whitelist** (`tests/audit/io_audit_whitelist.yaml`) - Primary source of truth
2. **Inline Pragmas** (`# io-audit: ignore-next-line <rule>`) - Line-level granularity

**IMPORTANT**: Inline pragmas ONLY work for files already listed in the YAML whitelist. If you add a pragma to a file not in the whitelist, it will be silently ignored.

**Correct Usage Pattern:**

```yaml
# Step 1: Add to io_audit_whitelist.yaml
files:
  - path: "src/omniintelligence/nodes/my_effect_node.py"
    reason: "Effect node requires Kafka client"
    allowed_rules:
      - "net-client"
```

```python
# Step 2: Use inline pragma in the whitelisted file
# io-audit: ignore-next-line net-client
from confluent_kafka import Producer  # Now correctly whitelisted
```

See the module docstring in `src/omniintelligence/audit/io_audit.py` for complete documentation.

## Configuration

### Pre-commit and CI Synchronization

The pre-commit hooks and GitHub Actions CI workflow must stay synchronized to ensure consistent validation between local development and CI pipelines. When path patterns diverge, hooks may run on different files locally vs in CI, causing missed issues or false failures.

**Files to keep in sync:**
- `.pre-commit-config.yaml` - Local pre-commit hook configuration
- `.github/workflows/ci.yaml` - GitHub Actions CI workflow

**Validation:**

```bash
# Validate alignment between pre-commit and CI configurations
uv run python scripts/validate_ci_precommit_alignment.py --verbose
```

The validation script checks:
- Path filter patterns match between configurations
- Hook types correspond to CI job steps
- No drift between local and CI validation

This validation runs automatically in CI and as a pre-commit hook.

### Environment Configuration

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
