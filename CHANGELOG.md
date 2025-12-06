# Changelog

All notable changes to OmniIntelligence will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Runtime Configuration (OMN-304)
- **IntelligenceRuntimeConfig**: Application-level configuration for the runtime host
  - `EventBusConfig`: Kafka event bus configuration with topic management
  - `TopicConfig`: Kafka topic configuration for commands, events, and DLQ
  - `HandlerConfig`: Handler dependency injection configuration
  - `RuntimeProfileConfig`: Optional node selection profiles
  - Environment variable interpolation (`${VAR_NAME}` syntax)
  - Factory methods: `from_yaml()`, `from_environment()`, `default_development()`, `default_production()`
  - Validators for runtime name format and port uniqueness
  - Helper methods: `get_handler_config()`, `has_handler()`, `to_yaml()`
- **YAML Contract**: `runtime/contracts/runtime_config.yaml` defining configuration schema

### Changed
- **Backlog Cleanup**: Canceled tickets that conflict with Runtime Host architecture
  - OMN-369: NodeEventConsumer → Kafka consumption belongs in omnibase_infra
  - OMN-372: Suffix removal → Redundant (nodes already in `_archived/` folder)

## [0.1.0] - 2025-12-04

### Added

#### Contract Linter (OMN-241)
- **Contract Validation Tool**: CLI tool for validating ONEX contract YAML files
  - Validates node contracts (compute, effect, reducer, orchestrator)
  - Validates FSM subcontracts and workflow coordination contracts
  - Structured error output with field paths
  - JSON output mode for CI/CD integration
  - Exit codes: 0 (success), 1 (validation errors), 2 (file errors)
- **CI/CD Integration**: GitHub Actions workflow for contract validation
- **Pre-commit Hooks**: Contract linter integrated with pre-commit

#### Intelligence Nodes
- **16 Intelligence Nodes**: Imported from omniarchon repository
  - **Compute Nodes** (6): vectorization, quality_scoring, entity_extraction, relationship_detection, semantic_analysis, pattern_matching
  - **Effect Nodes** (5): kafka_event, qdrant_vector, memgraph_graph, postgres_pattern, intelligence_api
  - **Orchestrator Nodes** (1): intelligence_orchestrator
  - **Reducer Nodes** (1): intelligence_reducer
- **YAML Contracts**: Contract definitions for all migrated nodes
- **FSM Definitions**: State machine contracts for ingestion, pattern learning, quality assessment

#### Documentation
- **CLAUDE.md**: Project-specific instructions for Claude Code
- **Reference Documentation**: Documentation from omniarchon
  - `OMNIARCHON_INVENTORY.md`: Detailed component inventory
  - `QUICK_REFERENCE.md`: API reference

#### Project Infrastructure
- **pyproject.toml**: uv-based dependency management with dependency groups
  - `core`: Core node system dependencies
  - `dev`: Development and testing tools
  - `all`: Complete dependency set
- **GitHub Workflows**: CI/CD for linting, type checking, and testing

### Architecture

#### Repository Structure
```
src/omniintelligence/
├── _archived/         # Archived nodes (to be refactored)
│   ├── nodes/         # 16 intelligence nodes
│   └── models/        # Shared models
├── runtime/           # Runtime host configuration
│   ├── runtime_config.py
│   └── contracts/
├── tools/             # CLI tools
│   └── contract_linter/
└── models/            # Pydantic models
```

#### Node Types
| Type | Count | Purpose |
|------|-------|---------|
| Compute | 6 | Pure data processing, no side effects |
| Effect | 5 | External I/O (Kafka, DB, HTTP) |
| Orchestrator | 1 | Coordinate workflows, route operations |
| Reducer | 1 | Manage state, FSM transitions |

### Known Limitations

#### Blocked on omnibase_core/spi/infra
- **IntelligenceNodeRegistry** (OMN-303): Blocked on Phase 5 (omnibase_core)
- **Runtime Host Entrypoint** (OMN-305): Blocked on OMN-303
- **Example Contracts** (OMN-374): Blocked on runtime architecture

#### Archived Code
- All nodes in `_archived/` contain direct I/O imports
- Nodes will be refactored once omnibase_spi handler protocols are available
- Direct Kafka, Qdrant, Memgraph, PostgreSQL imports to be removed

### Dependencies
- `omnibase_core` >= 0.3.5
- `pydantic` >= 2.0
- `pyyaml` >= 6.0

## Architecture Overview

### From OmniArchon
- Intelligence nodes (compute, effect, orchestrator, reducer)
- Node contracts (YAML definitions)
- FSM state machine contracts
- Shared models and enums

### OmniArchon Retained
- Service implementations
- Direct database clients
- HTTP API servers
- Kafka consumer loops

### Architecture Benefits
- **Before**: 1 container per node, direct I/O in nodes
- **After**: Runtime Host pattern, handlers injected via SPI protocols
- **Benefit**: Reduced from 10+ containers to 2-3, ~80% memory reduction

---

## Contributing

See CONTRIBUTING.md for guidelines. All changes should follow:
- ONEX naming conventions (`Node<Name><Type>`)
- Contract-driven development (YAML + Pydantic)
- No direct I/O in nodes (use SPI handler protocols)

## License

MIT License - See LICENSE file for details
