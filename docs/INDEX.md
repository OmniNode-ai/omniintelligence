> **Navigation**: Home (You are here)

# OmniIntelligence Documentation

Intelligence platform for the ONEX ecosystem: pattern learning, code analysis, evaluation, and Claude Code hook processing as first-class ONEX nodes.

**Shared standard:** [omni_home docs/standards/REPO_DOCUMENTATION_STANDARD.md](https://github.com/OmniNode-ai/omni_home/blob/main/docs/standards/REPO_DOCUMENTATION_STANDARD.md)

---

## Documentation Authority Model

| Source | Purpose | Authority |
|--------|---------|-----------|
| **[CLAUDE.md](../CLAUDE.md)** | Hard constraints, repository invariants, node rules, quick reference | **Authoritative** — definitive rules for agents and developers |
| **docs/** | Explanations, architecture, guides, conventions, decisions | Supplementary — context and how-to guidance |

**When in conflict, CLAUDE.md takes precedence.**

---

## Start Here

| I want to... | Go to... |
|--------------|----------|
| Understand what this repo owns | [README.md](../README.md#what-this-repo-owns) |
| Run tests or install locally | [README.md](../README.md#common-workflows) |
| See all 59 nodes | [docs/reference/NODE_INVENTORY.md](reference/NODE_INVENTORY.md) |
| Understand node types and architecture | [docs/architecture/ONEX_FOUR_NODE_ARCHITECTURE.md](architecture/ONEX_FOUR_NODE_ARCHITECTURE.md) |
| Understand Kafka topics produced/consumed | [docs/reference/EVENT_SURFACE.md](reference/EVENT_SURFACE.md) |
| Understand which events reach omnidash | [docs/reference/DASH_INTEGRATION_TRUTH_BOUNDARY.md](reference/DASH_INTEGRATION_TRUTH_BOUNDARY.md) |
| Understand naming conventions | [docs/conventions/NAMING_CONVENTIONS.md](conventions/NAMING_CONVENTIONS.md) |
| Validate a node contract | [docs/CONTRACT_VALIDATION_GUIDE.md](CONTRACT_VALIDATION_GUIDE.md) |
| Understand node state lifecycle | [docs/NODE_STATE_POLICY.md](NODE_STATE_POLICY.md) |
| See documentation standards | [docs/standards/STANDARD_DOC_LAYOUT.md](standards/STANDARD_DOC_LAYOUT.md) |
| See hard rules and invariants | [CLAUDE.md](../CLAUDE.md) |

---

## Current Architecture

| Document | Description | Status |
|----------|-------------|--------|
| [ONEX Four-Node Architecture](architecture/ONEX_FOUR_NODE_ARCHITECTURE.md) | Effect, Compute, Reducer, Orchestrator archetypes, pipeline diagrams, and dispatch engine | Active |
| [Contract Package Spec](architecture/contract-package-spec.md) | Contract YAML schema, handler routing, event bus configuration | Active |
| [Node State Policy](NODE_STATE_POLICY.md) | Node implementation states (Implemented, Shell, Stub), enforcement, and orchestrator dependency rules | Active |

---

## Reference

| Document | Description | Status |
|----------|-------------|--------|
| [Node Inventory](reference/NODE_INVENTORY.md) | Full list of 59 ONEX nodes declared in `pyproject.toml [project.entry-points."onex.nodes"]` | Active |
| [Event Surface](reference/EVENT_SURFACE.md) | All produced, consumed, dashboard-visible, internal, and deprecated Kafka topics | Active |
| [Dash Integration Truth Boundary](reference/DASH_INTEGRATION_TRUTH_BOUNDARY.md) | Which topics are live in omnidash vs. dead constants, gaps, and deprecated | Active |
| [Contract Validation Guide](CONTRACT_VALIDATION_GUIDE.md) | How to create and validate ONEX contract YAML files | Active |
| [Naming Conventions](conventions/NAMING_CONVENTIONS.md) | Node, handler, model, and file naming standards | Active |

---

## Runbooks

No current operational runbooks. For runtime startup, see the `PluginIntelligence` bootstrap section in [CLAUDE.md](../CLAUDE.md#runtime-module) and the [ONEX Four-Node Architecture](architecture/ONEX_FOUR_NODE_ARCHITECTURE.md#pluginintelligence-node-discovery-and-wiring) doc.

---

## Migrations

No active migrations. Historical migration context (omniarchon to omniintelligence) has been cleaned up. See git log for removed migration docs.

---

## Decisions

No formal ADRs yet. Architecture decisions are recorded in CLAUDE.md as repository invariants and in the architecture docs.

---

## Testing and Validation

```bash
# Full test suite (required before any PR)
uv run pytest tests/ -v

# By marker
uv run pytest tests/ -v -m unit          # unit tests only
uv run pytest tests/ -v -m audit         # AST purity enforcement
uv run pytest tests/ -v -m integration   # requires Postgres + Kafka

# Lint/format/type
uv run ruff format src/ tests/ && uv run ruff check --fix src/ tests/
uv run mypy src/

# Pre-commit
pre-commit run --all-files
```

See [docs/standards/STANDARD_DOC_LAYOUT.md](standards/STANDARD_DOC_LAYOUT.md) for documentation quality standards.

---

## Historical Context

Dated plans and migration context are in `omni_home/docs/plans/`. They are not promoted as active architecture docs. Key context docs:

| Plan | Purpose |
|------|---------|
| [2026-04-09-omniintelligence-wiring-gaps.md](https://github.com/OmniNode-ai/omni_home/blob/main/docs/plans/2026-04-09-omniintelligence-wiring-gaps.md) | Topic-truth audit, dead constants, and omnidash wiring gap analysis. Source material for `DASH_INTEGRATION_TRUTH_BOUNDARY.md`. |

---

## Document Status

| Document | Status | Notes |
|----------|--------|-------|
| [ONEX Four-Node Architecture](architecture/ONEX_FOUR_NODE_ARCHITECTURE.md) | Active | Updated 2026-02-19; pipeline diagrams reflect dispatch engine routing |
| [Contract Package Spec](architecture/contract-package-spec.md) | Active | Contract YAML reference |
| [Naming Conventions](conventions/NAMING_CONVENTIONS.md) | Active | Canonical naming standard |
| [Standard Doc Layout](standards/STANDARD_DOC_LAYOUT.md) | Active | Documentation structure standard |
| [Contract Validation Guide](CONTRACT_VALIDATION_GUIDE.md) | Active | Contract linting and validation reference |
| [Node State Policy](NODE_STATE_POLICY.md) | Active | Node state and lifecycle policy |
| [Node Inventory](reference/NODE_INVENTORY.md) | Active | Sourced from `pyproject.toml` — updated 2026-04-29 |
| [Event Surface](reference/EVENT_SURFACE.md) | Active | Sourced from CLAUDE.md and contract YAML files — updated 2026-04-29 |
| [Dash Integration Truth Boundary](reference/DASH_INTEGRATION_TRUTH_BOUNDARY.md) | Active | Sourced from wiring-gaps plan — updated 2026-04-29 |
