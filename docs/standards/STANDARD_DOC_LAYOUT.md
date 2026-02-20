> **Navigation**: [Home](../INDEX.md) > [Standards](.) > Standard Doc Layout

# Standard Documentation Layout

Prescriptive structure for the `docs/` directory in omniintelligence.

---

## Documentation Authority Model

| Location | Contains | Does NOT Contain |
|----------|----------|------------------|
| **CLAUDE.md** | Hard constraints, invariants, rules, navigation pointers | Tutorials, architecture explanations, code examples, how-to content |
| **docs/** | Explanations, architecture, guides, conventions, decisions | Rules that override CLAUDE.md |

**Rule**: If the same content appears in both CLAUDE.md and docs/, one of them is wrong. CLAUDE.md links to docs/ — it does not re-explain what docs/ already covers.

---

## Required Directories

```text
docs/
├── architecture/          # Node topology, data flow, system design
├── conventions/           # Naming, file structure, coding style
├── standards/             # Doc standards (this file)
└── INDEX.md               # Top-level navigation
```

| Directory | Purpose | Required |
|-----------|---------|----------|
| `docs/architecture/` | Node topology, data flow, system design | Yes |
| `docs/conventions/` | Naming conventions, file structure, coding style | Yes |
| `docs/standards/` | Documentation standards (this file) | Yes |
| `docs/INDEX.md` | Top-level navigation index | Yes |

---

## Optional Directories

Add these only when content exists that warrants them.

| Directory | When to Add |
|-----------|-------------|
| `docs/decisions/` | Architecture Decision Records (ADRs) |
| `docs/guides/` | Step-by-step how-to guides |
| `docs/patterns/` | Repeating code and design patterns |
| `docs/testing/` | Testing strategies and patterns |
| `docs/troubleshooting/` | Known issues and fixes |

---

## File Naming

| Pattern | Use | Example |
|---------|-----|---------|
| `UPPER_SNAKE_CASE.md` | All documentation files except ADRs and index files | `NAMING_CONVENTIONS.md` |
| `README.md` | Directory index files only | `README.md` |
| `ADR-NNN-<lowercase-hyphenated-slug>.md` | Architecture Decision Records in `decisions/` | `ADR-001-pattern-storage-strategy.md` |

No lowercase filenames except `README.md` and ADR slugs in `decisions/`.

---

## INDEX.md Requirements

The root `docs/INDEX.md` must include:

1. **Documentation Authority Model** table (CLAUDE.md vs docs/ roles)
2. **Quick Navigation** table (intent-based: "I want to...")
3. **Documentation Structure** with per-section tables linking to every doc

All links in `INDEX.md` must use relative paths and resolve to existing files.

---

## Deleted Content Policy

| Content Type | Action |
|--------------|--------|
| Completed migration plans | Delete |
| Point-in-time handoff docs | Delete |
| Stale analyses | Delete |
| Outdated specs with no current value | Delete |

- No `docs/archive/` directory — if unused, delete it
- No `docs/old/` directory — same rule
- Inbound links to deleted files must be removed or updated in the same commit

**Files removed in the omnibase_core format migration (commit bcfc816)** — verify no remaining links point to these paths:

| Deleted File | Reason |
|--------------|--------|
| `docs/RUNTIME_HOST_REFACTORING_PLAN.md` | Completed work; point-in-time planning doc |
| `docs/VALIDATION_INTEGRATION_PLAN.md` | Completed work; point-in-time planning doc |
| `docs/TODO_TRACKING.md` | Completed work; stale tracking doc |
| `docs/migrations/CONTRACT_CORRECTIONS.md` | Completed migration; stale |
| `docs/migrations/MIGRATION_SUMMARY.md` | Completed migration; stale |
| `docs/migrations/NODE_MAPPING_REFERENCE.md` | Completed migration; stale |
| `docs/migrations/OMNIARCHON_MIGRATION_INVENTORY.md` | Completed migration; stale |
| `docs/migrations/ONEX_MIGRATION_PLAN.md` | Completed migration; stale |
| `docs/migrations/omniarchon_to_omniintelligence.md` | Completed migration; stale |
| `docs/plans/OMN-1757-declarative-node-refactor.md` | Completed work; stale plan |
| `docs/specs/DECLARATIVE_EFFECT_NODES_SPEC.md` | Superseded; no current value |

---

## Document Quality Standards

| Standard | Rule |
|----------|------|
| Purpose statement | Every doc must open with a single-sentence statement of what it covers |
| No duplication | Each fact lives in exactly one document; others link to it |
| Relative links | All cross-doc links use relative paths, never absolute filesystem paths |
| Link verification | All links must resolve to existing files before committing |
