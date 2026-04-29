# omniintelligence

Intelligence, pattern learning, code analysis, and evaluation as first-class ONEX nodes.

[![CI](https://github.com/OmniNode-ai/omniintelligence/actions/workflows/test.yml/badge.svg)](https://github.com/OmniNode-ai/omniintelligence/actions/workflows/test.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## What this repo is

OmniIntelligence is the intelligence platform for the ONEX ecosystem. It provides pattern learning, code quality analysis, evaluation, intent classification, document analysis, CI failure tracking, bloom evaluation, and Claude Code hook processing as 59 first-class ONEX nodes. All nodes follow the ONEX Four-Node Architecture (Effect / Compute / Reducer / Orchestrator) and delegate all business logic to handler modules.

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

For the full node list see [docs/reference/NODE_INVENTORY.md](docs/reference/NODE_INVENTORY.md).

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

# Integration tests (requires Postgres + Kafka on .201)
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
| Compute (35+) | `NodeQualityScoringCompute`, `NodeIntentClassifierCompute` | None — pure transforms |
| Effect (14+) | `NodeClaudeHookEventEffect`, `NodePatternStorageEffect` | Kafka, PostgreSQL, external APIs |
| Reducer (2) | `NodeDocPromotionReducer`, `NodePolicyStateReducer` | FSM state transitions |
| Orchestrator (2) | `NodeBloomEvalOrchestrator`, `NodePatternAssemblerOrchestrator` | Workflow coordination |

**Key pipelines:**

- Claude Code Hook → intent classification → omnimemory graph
- Session end (Stop hook) → pattern learning → pattern storage → PostgreSQL
- Pattern promotion/demotion → lifecycle transition → audit trail
- Quality assessment command → scoring compute → quality-assessment-completed → omnidash

**Dash integration boundary:** omnidash never queries this repo's database directly. All data flows via Kafka topics projected into `omnidash_analytics`. See [docs/reference/DASH_INTEGRATION_TRUTH_BOUNDARY.md](docs/reference/DASH_INTEGRATION_TRUTH_BOUNDARY.md) for the live/dead/gap status of each topic.

For topology diagrams and full pipeline details see [docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md](docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md).

---

## Documentation map

| Document | Purpose |
|----------|---------|
| [docs/INDEX.md](docs/INDEX.md) | Canonical docs entrypoint |
| [docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md](docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md) | Node topology, data flow, pipeline diagrams |
| [docs/reference/NODE_INVENTORY.md](docs/reference/NODE_INVENTORY.md) | Full node inventory sourced from `pyproject.toml` |
| [docs/reference/EVENT_SURFACE.md](docs/reference/EVENT_SURFACE.md) | Produced, consumed, dashboard-visible, and deprecated topics |
| [docs/reference/DASH_INTEGRATION_TRUTH_BOUNDARY.md](docs/reference/DASH_INTEGRATION_TRUTH_BOUNDARY.md) | Omnidash integration truth boundary |
| [CLAUDE.md](CLAUDE.md) | Developer context, invariants, quick reference |
| [AGENT.md](AGENT.md) | LLM navigation guide |

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
