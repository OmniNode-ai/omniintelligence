> **Navigation**: Home (You are here)

# OmniIntelligence Documentation

Welcome to the OmniIntelligence (`omniintelligence3`) documentation — the intelligence platform for the ONEX ecosystem.

## Documentation Authority Model

| Source | Purpose | Authority |
|--------|---------|-----------|
| **[CLAUDE.md](../CLAUDE.md)** | Hard constraints, repository invariants, node rules, quick reference | **Authoritative** — definitive rules for agents and developers |
| **docs/** | Explanations, architecture, conventions, guides | Supplementary — context and how-to guidance |

**When in conflict, CLAUDE.md takes precedence.** This separation ensures:
- Constraints are concise and enforceable in CLAUDE.md
- Documentation provides depth without bloating the rules file
- No content is duplicated between them

**Quick Reference:**
- Need a rule or invariant? Check [CLAUDE.md](../CLAUDE.md)
- Need an explanation? Check [docs/](.)
- Need naming conventions? Check [docs/conventions/NAMING_CONVENTIONS.md](conventions/NAMING_CONVENTIONS.md)

---

## Quick Navigation

| I want to... | Go to... |
|--------------|----------|
| Understand node types and architecture | [ONEX Four-Node Architecture](architecture/ONEX_FOUR_NODE_ARCHITECTURE.md) |
| Understand naming conventions | [Naming Conventions](conventions/NAMING_CONVENTIONS.md) |
| Understand node state transitions | [Node State Policy](NODE_STATE_POLICY.md) |
| Validate contracts | [Contract Validation Guide](CONTRACT_VALIDATION_GUIDE.md) |
| See the full constraint set | [CLAUDE.md](../CLAUDE.md) |
| Understand documentation standards | [Standard Doc Layout](standards/STANDARD_DOC_LAYOUT.md) |

---

## Documentation Structure

### Architecture

Understand how OmniIntelligence nodes and workflows are designed.

| Document | Description |
|----------|-------------|
| [ONEX Four-Node Architecture](architecture/ONEX_FOUR_NODE_ARCHITECTURE.md) | Effect, Compute, Reducer, Orchestrator archetypes and how they compose |

### Conventions

Coding and naming standards specific to this repository.

| Document | Description |
|----------|-------------|
| [Naming Conventions](conventions/NAMING_CONVENTIONS.md) | Node, handler, model, and file naming standards |

### Standards

Normative specifications for document and code layout.

| Document | Description |
|----------|-------------|
| [Standard Doc Layout](standards/STANDARD_DOC_LAYOUT.md) | Canonical structure for documentation files in this repository |

### Guides

Reference guides for working with OmniIntelligence infrastructure.

| Document | Description |
|----------|-------------|
| [Contract Validation Guide](CONTRACT_VALIDATION_GUIDE.md) | How to create and validate ONEX contract YAML files |
| [Node State Policy](NODE_STATE_POLICY.md) | Node implementation states, enforcement, and orchestrator dependency rules |

---

## Document Status

| Document | Status | Notes |
|----------|--------|-------|
| [ONEX Four-Node Architecture](architecture/ONEX_FOUR_NODE_ARCHITECTURE.md) | Active | Core architecture reference |
| [Naming Conventions](conventions/NAMING_CONVENTIONS.md) | Active | Canonical naming standard |
| [Standard Doc Layout](standards/STANDARD_DOC_LAYOUT.md) | Active | Documentation structure standard |
| [Contract Validation Guide](CONTRACT_VALIDATION_GUIDE.md) | Active | Contract linting and validation reference |
| [Node State Policy](NODE_STATE_POLICY.md) | Active | Node state and lifecycle policy |
