<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/omninode-inline-white.png">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/brand/omninode-inline-full-color.svg">
    <img alt="omninode" src="docs/assets/brand/omninode-inline-full-color.svg" width="420">
  </picture>
</p>

# omniintelligence

Intelligence, pattern learning, code analysis, and evaluation as first-class ONEX (OmniNode eXecution) nodes.

[![CI](https://github.com/OmniNode-ai/omniintelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/OmniNode-ai/omniintelligence/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## What this repo is

OmniIntelligence is the intelligence platform for the ONEX ecosystem. It provides pattern learning, code quality analysis, evaluation, intent classification, document analysis, CI failure tracking, bloom evaluation, and Claude Code hook processing as 60 first-class ONEX nodes. All nodes follow the ONEX Four-Node Architecture (Effect / Compute / Reducer / Orchestrator) and delegate all business logic to handler modules.

---

## Who uses it

- **omniclaude** — publishes Claude Code hook events consumed here; subscribes to intelligence events for hook routing
- **omnimemory** — consumes intent-classified and pattern events for graph and vector storage
- **omnidash** — projects quality-assessment, bloom-eval, routing-feedback, and pattern events into read-model dashboards
- **omnimarket** — portable workflow packages invoke intelligence nodes via the ONEX node entry-point registry

---

## What this repo owns

- Pattern learning: extraction, ML learning pipeline, storage, promotion, demotion, lifecycle management
- Code quality scoring and ONEX compliance assessment
- Semantic analysis, AST extraction, and code entity bridging
- Intent classification from Claude Code hook events
- Intent drift detection, cost forecasting, and LLM routing decisions
- Document ingestion, parsing, retrieval, and staleness detection
- CI failure tracking, error classification, and fingerprinting
- Bloom evaluation orchestration and plan multi-model review
- Routing feedback processing and compliance evaluation
- Claude Code hook event processing (`UserPromptSubmit`, `Stop`, and others)
- REST API for pattern query by enforcement nodes (`GET /api/v1/patterns`)

For the full node list see [Node Inventory](https://github.com/OmniNode-ai/knowledge-base/blob/main/reference/omniintelligence-node-inventory.md).

---

## What this repo does not own

| Concern | Canonical owner |
|---------|-----------------|
| ONEX kernel, node execution, contracts, validation | [omnibase_core](https://github.com/OmniNode-ai/omnibase_core) |
| Kafka, PostgreSQL, runtime host, registration | [omnibase_infra](https://github.com/OmniNode-ai/omnibase_infra) |
| Protocol interfaces | [omnibase_spi](https://github.com/OmniNode-ai/omnibase_spi) |
| Portable workflow packages and automation logic | [omnimarket](https://github.com/OmniNode-ai/omnimarket) |
| Vector and graph storage (Qdrant, Memgraph) | [omnimemory](https://github.com/OmniNode-ai/omnimemory) |
| Dashboard UI and read-model projection surface | [omnidash](https://github.com/OmniNode-ai/omnidash) |
| Claude Code hooks, invocation UX, skills | [omniclaude](https://github.com/OmniNode-ai/omniclaude) |

---

## Install

```bash
uv add omninode-intelligence
```

Or install from source alongside sibling repos (editable):

```bash
uv sync --group all
```

---

## Common workflows

```bash
# Full test suite (required before any PR)
uv run pytest tests/ -v

# Unit tests only (fast, no infrastructure)
uv run pytest tests/ -v -m unit

# Audit tests (AST purity enforcement)
uv run pytest tests/ -v -m audit

# Integration tests (requires Postgres + Kafka on the runtime host)
uv run pytest tests/ -v -m integration

# Lint and format
uv run ruff format src/ tests/
uv run ruff check --fix src/ tests/

# Type check
uv run mypy src/

# Pre-commit (run before staging)
pre-commit run --all-files

# Review calibration CLI
uv run python -m omniintelligence.review_pairing \
  --file plan.md --ground-truth codex --challenger deepseek-r1
```

---

## Architecture summary

OmniIntelligence is built on the ONEX Four-Node Architecture. Nodes are thin shells that delegate all logic to handler modules. Contract YAML files declare event bus subscriptions, publish topics, handler routing, and dependencies — no hardcoded topic strings in Python.

**Node types:**

| Type | Example nodes | I/O |
|------|---------------|-----|
| Compute (24) | `NodeQualityScoringCompute`, `NodeIntentClassifierCompute` | None — pure transforms |
| Effect (30) | `NodeClaudeHookEventEffect`, `NodePatternStorageEffect` | Kafka, PostgreSQL, external APIs |
| Reducer (2) | `NodeDocPromotionReducer`, `NodePolicyStateReducer` | FSM state transitions |
| Orchestrator (2) | `NodeBloomEvalOrchestrator`, `NodePatternAssemblerOrchestrator` | Workflow coordination |

**Key pipelines:**

- Claude Code Hook → intent classification → omnimemory graph
- Session end (Stop hook) → pattern learning → pattern storage → PostgreSQL
- Pattern promotion/demotion → lifecycle transition → audit trail
- Quality assessment command → scoring compute → quality-assessment-completed → omnidash

**Dash integration boundary (architectural rule):** omnidash must never query this repo's database directly — the intended path is Kafka topics projected into `omnidash_analytics`. This repo's producer side is verified live; the omnidash-side consumer wiring is not (tracked on OMN-16577).

For topology diagrams and full pipeline details see [ONEX Four-Node Architecture](https://github.com/OmniNode-ai/knowledge-base/blob/main/architecture/omniintelligence-four-node-architecture.md).

---

## Documentation map

| Document | Purpose |
|----------|---------|
| [ONEX Four-Node Architecture](https://github.com/OmniNode-ai/knowledge-base/blob/main/architecture/omniintelligence-four-node-architecture.md) | Node topology, data flow, pipeline diagrams |
| [Node Inventory](https://github.com/OmniNode-ai/knowledge-base/blob/main/reference/omniintelligence-node-inventory.md) | Full node inventory sourced from `pyproject.toml` |
| [Event Surface](https://github.com/OmniNode-ai/knowledge-base/blob/main/reference/omniintelligence-event-surface.md) | Produced, consumed, dashboard-visible, and deprecated topics |
| [CLAUDE.md](CLAUDE.md) | Developer context, invariants, quick reference |

---

## Development and test commands

```bash
# Install (all groups including dev)
uv sync --group all

# Full test suite
uv run pytest tests/ -v

# Lint and format
uv run ruff format src/ tests/ && uv run ruff check --fix src/ tests/

# Type check
uv run mypy src/

# Pre-commit
pre-commit run --all-files
```

---

## Security, contributing, and license

- [SECURITY.md](SECURITY.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [LICENSE](LICENSE) — MIT
