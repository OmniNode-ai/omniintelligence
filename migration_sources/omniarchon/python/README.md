# OmniArchon Python Services

Intelligence platform for AI coding assistants via MCP (Model Context Protocol).

## Overview

This package contains the Python implementation of OmniArchon's intelligence services:

- **MCP Server** (`src/mcp_server/`) - Model Context Protocol server
- **Intelligence Services** (`src/intelligence/`) - Core intelligence APIs
- **Bridge Integration** (`src/omninode_bridge/`) - OmniNode bridge connectors
- **Server** (`src/server/`) - Main API server with authentication

## Key Features

- Code quality analysis with ONEX compliance scoring
- Performance optimization recommendations
- Pattern learning and traceability
- Vector search (Qdrant) and knowledge graph (Memgraph)
- Distributed caching with Valkey
- Event-driven architecture with Kafka/Redpanda

## Installation

```bash
# Install with Poetry
cd python
poetry install --with dev --with server

# Or with pip (from repository root)
pip install -e python/
```

## Running Services

See the main repository README for Docker Compose setup and service configuration.

## Testing

```bash
# Run all tests
poetry run pytest tests/

# Run with coverage
poetry run pytest tests/ --cov=src --cov-report=html

# Run specific test suite
poetry run pytest tests/unit/
poetry run pytest tests/integration/
```

## Development

This project uses:
- **Python 3.12+**
- **Poetry** for dependency management
- **Black** and **isort** for code formatting
- **pytest** for testing

See `.pre-commit-config.yaml` for pre-commit hooks configuration.

## License

See main repository for license information.
