# OmniIntelligence

Intelligence, indexing, and pattern services as first-class Omninode nodes.

## Overview

OmniIntelligence is a rebuild of the legacy `omniarchon` intelligence platform, transformed into a set of canonical ONEX nodes following the Omninode architecture patterns. This migration preserves contract-driven ingestion, vector search, and intelligence APIs while aligning with canonical node standards.

## Architecture

The system is decomposed into specialized ONEX nodes:

### Orchestrator Nodes
- **intelligence_orchestrator** - Coordinates ingestion, enrichment, vectorization, and persistence pipelines

### Reducer Nodes
- **ingestion_reducer** - Manages ingestion FSM, state transitions, and lease management

### Compute Nodes
- **vectorization_compute** - Encapsulates embedding generation, scoring, and fallback models
- **pattern_learning_compute** - Pattern enrichment and learning operations

### Effect Nodes
- **ingestion_effect** - Handles Kafka/Qdrant/PostgreSQL side effects
- **intelligence_api_effect** - Provides HTTP/Kafka façade for intelligence APIs

## Project Structure

```
omniintelligence/
├── src/
│   └── omniintelligence/
│       ├── nodes/                    # ONEX nodes
│       │   ├── intelligence_orchestrator/
│       │   ├── ingestion_reducer/
│       │   ├── ingestion_effect/
│       │   ├── vectorization_compute/
│       │   ├── pattern_learning_compute/
│       │   └── intelligence_api_effect/
│       ├── adapters/                 # External adapters (HTTP, etc.)
│       ├── shared/                   # Shared models and utilities
│       └── utils/                    # Common utilities
├── tests/
│   ├── unit/                         # Unit tests
│   ├── integration/                  # Integration tests
│   ├── fixtures/                     # Test fixtures
│   └── contracts/                    # Contract validation tests
├── scripts/                          # Automation scripts
├── deployment/                       # Deployment manifests
├── config/                           # Configuration files
├── docs/                             # Documentation
│   └── migrations/                   # Migration guides
└── migration_sources/                # Legacy source reference
    └── omniarchon/                   # Original omniarchon codebase
```

## Setup

### Prerequisites

- Python 3.12+
- Poetry or uv for dependency management
- Docker for local infrastructure (Kafka, Qdrant, PostgreSQL, Memgraph)

### Installation

```bash
# Install core dependencies
uv sync --group core

# Install development dependencies
uv sync --group dev

# Install all dependencies (development + testing)
uv sync --group all
```

### Running Tests

```bash
# Run unit tests
pytest tests/unit

# Run integration tests (requires infrastructure)
pytest tests/integration

# Run all tests
pytest

# Run with coverage
pytest --cov=src/omniintelligence --cov-report=html
```

## Development

### Node Development Pattern

Each node follows the canonical ONEX structure:

```
node_name/
├── v1_0_0/                          # Versioned implementation
│   ├── contracts/                   # YAML contract definitions
│   ├── models/                      # Pydantic models
│   ├── node.py                      # Main node implementation
│   ├── introspection.py            # Introspection support
│   ├── scenarios/                   # Integration test scenarios
│   └── node_tests/                  # Node-specific tests
└── __init__.py
```

### Code Quality

```bash
# Format code
black src tests
isort src tests

# Lint
ruff check src tests

# Type check
mypy src
```

### Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) to ensure code quality before commits.

#### Installation

```bash
# Install pre-commit (if not already installed)
pip install pre-commit

# Install the git hooks
pre-commit install
```

#### Running Manually

```bash
# Run on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files

# Run contract linter hook
pre-commit run contract-linter --all-files
```

#### Configured Hooks

| Hook | Description |
|------|-------------|
| **ruff** | Fast Python linter with auto-fix |
| **ruff-format** | Python code formatter |
| **mypy** | Static type checking (strict mode) |
| **onex-patterns** | ONEX pattern validation |
| **onex-union-usage** | ONEX union usage validation |
| **contract-linter** | ONEX contract YAML validation |
| **pytest-tools** | Unit tests for tools (runs on push only) |

> **Note**: Most hooks run on `pre-commit` stage. The `pytest-tools` hook runs on `pre-push` to avoid slowing down commits.

## Migration from OmniArchon

This project is a migration from the legacy `omniarchon` system. See:
- [Migration Guide](docs/migrations/omniarchon_to_omniintelligence.md)
- [Legacy Sources](migration_sources/omniarchon/)

## Documentation

- [Architecture Overview](docs/migrations/omniarchon_to_omniintelligence.md#4-service-decomposition)
- [Node Stack Blueprint](docs/migrations/omniarchon_to_omniintelligence.md#5-node-stack-blueprint)
- [Migration Steps](docs/migrations/omniarchon_to_omniintelligence.md#6-migration-steps)
- [Testing Strategy](docs/migrations/omniarchon_to_omniintelligence.md#7-testing--validation)

## License

Copyright © 2024 OmniNode Team
