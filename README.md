# OmniIntelligence

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-managed-261230.svg)](https://docs.astral.sh/uv/)
[![Linting: ruff](https://img.shields.io/badge/linting-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy.readthedocs.io/)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Nodes: 18](https://img.shields.io/badge/nodes-18-blue.svg)](#architecture)

**Intelligence, pattern learning, and code quality analysis as first-class ONEX nodes.**

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Development](#development)
- [Testing](#testing)

## Overview

OmniIntelligence is the intelligence platform for the ONEX ecosystem. It provides code quality analysis, ML-based pattern learning, semantic analysis, and Claude Code hook processing — all implemented as declarative ONEX nodes following the thin-shell pattern.

The system is registered as a domain plugin (`PluginIntelligence`) and discovered at runtime by `RuntimeHostProcess` from `omnibase_infra`. Nodes declare their Kafka subscriptions and handler routing in `contract.yaml`; the runtime wires everything automatically.

For architecture details, invariants, and handler patterns, see [CLAUDE.md](CLAUDE.md).

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management (required — do not use pip or Poetry directly)

## Installation

```bash
# Core node system + all infrastructure dependencies
uv sync --group core

# Development tools (ruff, mypy, pytest)
uv sync --group dev

# Everything (core + dev)
uv sync --group all
```

**ONEX ecosystem dependencies** (published on PyPI — installed automatically by `uv sync`):

| Package | Version | Purpose |
|---------|---------|---------|
| `omnibase-core` | `>=0.17.0,<0.18.0` | Node base classes, protocols, validation |
| `omnibase-spi` | `>=0.8.0,<0.9.0` | Service Provider Interface protocols |
| `omnibase-infra` | `>=0.7.0,<0.8.0` | Kafka, PostgreSQL, runtime infrastructure |

## Architecture

The system decomposes intelligence operations into 18 specialized ONEX nodes across four types.

### Node Inventory

**Orchestrators** — coordinate multi-step workflows

| Node | Purpose |
|------|---------|
| `NodeIntelligenceOrchestrator` | Main workflow coordination (contract-driven) |
| `NodePatternAssemblerOrchestrator` | Pattern assembly from execution traces |

**Reducer** — FSM state management

| Node | Purpose |
|------|---------|
| `NodeIntelligenceReducer` | Unified FSM handler for ingestion, pattern learning, and quality assessment |

**Compute nodes** — pure data processing, no side effects

| Node | Purpose |
|------|---------|
| `NodeQualityScoringCompute` | Code quality scoring with ONEX compliance |
| `NodeSemanticAnalysisCompute` | Semantic code analysis |
| `NodePatternExtractionCompute` | Extract patterns from code |
| `NodePatternLearningCompute` | ML pattern learning pipeline |
| `NodePatternMatchingCompute` | Match patterns against code |
| `NodeIntentClassifierCompute` | User prompt intent classification |
| `NodeExecutionTraceParserCompute` | Parse execution traces |
| `NodeSuccessCriteriaMatcherCompute` | Match success criteria against outcomes |

**Effect nodes** — external I/O (Kafka, PostgreSQL)

| Node | Purpose |
|------|---------|
| `NodeClaudeHookEventEffect` | Process Claude Code hook events; emit classified intents to Kafka |
| `NodePatternStorageEffect` | Persist patterns to PostgreSQL |
| `NodePatternPromotionEffect` | Promote patterns (provisional → validated) |
| `NodePatternDemotionEffect` | Demote patterns (validated → deprecated) |
| `NodePatternFeedbackEffect` | Record session outcomes and metrics |
| `NodePatternLifecycleEffect` | Atomic lifecycle transitions with audit trail |
| `NodePatternLearningEffect` | Pattern learning effect (contract-only) |

### Runtime Plugin

`PluginIntelligence` (`omniintelligence.runtime.plugin`) is the domain plugin entry point registered under `onex.domain_plugins`. It is discovered by `RuntimeHostProcess`, which scans `contract.yaml` files to wire Kafka subscriptions, handler routing, health checks, and graceful shutdown automatically.

### API Module

`omniintelligence.api` exposes HTTP endpoints (FastAPI/uvicorn) for intelligence operations.

## Project Structure

```text
src/omniintelligence/
├── nodes/                              # 18 ONEX nodes
│   ├── node_claude_hook_event_effect/
│   ├── node_execution_trace_parser_compute/
│   ├── node_intelligence_orchestrator/
│   ├── node_intelligence_reducer/
│   ├── node_intent_classifier_compute/
│   ├── node_pattern_assembler_orchestrator/
│   ├── node_pattern_demotion_effect/
│   ├── node_pattern_extraction_compute/
│   ├── node_pattern_feedback_effect/
│   ├── node_pattern_learning_compute/
│   ├── node_pattern_learning_effect/
│   ├── node_pattern_lifecycle_effect/
│   ├── node_pattern_matching_compute/
│   ├── node_pattern_promotion_effect/
│   ├── node_pattern_storage_effect/
│   ├── node_quality_scoring_compute/
│   ├── node_semantic_analysis_compute/
│   └── node_success_criteria_matcher_compute/
├── runtime/                            # PluginIntelligence, RuntimeHostProcess wiring
├── api/                                # FastAPI HTTP endpoints
├── repositories/                       # Database access layer
├── handlers/                           # Shared handler functions
├── models/                             # Shared Pydantic models
├── enums/                              # Domain enumerations
├── protocols/                          # Protocol interfaces
├── utils/                              # Utilities
└── _legacy/                            # Legacy code (do not import)

tests/
├── audit/                              # I/O purity enforcement (AST analysis)
├── unit/                               # Unit tests (no infrastructure)
├── integration/                        # Integration tests
├── nodes/                              # Node-specific tests
└── fixtures/                           # Shared test data
```

Each node directory contains:

```text
node_example_compute/
├── contract.yaml        # Declarative: I/O models, handler routing, event bus topics
├── node.py              # Thin shell (~20-50 lines), delegates to handler
├── models/              # Input/output Pydantic models
└── handlers/            # All business logic, error handling, logging
```

## Development

```bash
# Lint (includes import sorting)
uv run ruff check src tests

# Auto-fix lint issues
uv run ruff check --fix src tests

# Format
uv run ruff format src tests

# Type check
uv run mypy src

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/omniintelligence --cov-report=html
```

## Testing

```bash
uv run pytest tests/unit          # Unit tests (no infrastructure required)
uv run pytest tests/integration   # Integration tests (requires Kafka + PostgreSQL)
uv run pytest -m unit             # Only @pytest.mark.unit tests
uv run pytest -m audit            # I/O purity enforcement
uv run pytest -m "not slow"       # Exclude slow tests
uv run pytest -k "test_name"      # Single test by name
```

### pytest Markers

| Marker | Purpose |
|--------|---------|
| `unit` | Fast, isolated unit tests |
| `integration` | Tests requiring live infrastructure |
| `slow` | Long-running tests |
| `audit` | AST-based I/O purity enforcement (node line count, no logging in nodes, no try/except in nodes) |
| `performance` | Performance benchmarks |

For infrastructure configuration (Kafka, PostgreSQL, remote server topology), see [`~/.claude/CLAUDE.md`](~/.claude/CLAUDE.md).

---

Copyright &copy; 2024 OmniNode Team
