# Automated Core-to-Dependent Migration System

**Version**: 1.0.0
**Status**: Planning
**Last Updated**: 2025-11-02
**Owner**: Platform Team

---

## Executive Summary

Automate migration of dependent packages when breaking changes occur between core versions by generating machine-readable Change Manifests directly from `.tree` and metadata artifacts.

**Goal**: Zero-manual intervention for dependency migrations while maintaining 100% safety and determinism.

**Key Innovation**: Derive complete migration instructions automatically from tree structure snapshots and symbol-level provenance metadata, eliminating manual change mapping.

---

## Problem Statement

### Current Pain Points

1. **Manual Migration Mapping**
   - Developers manually track class renames, path moves, signature changes
   - Error-prone and time-consuming
   - Incomplete documentation leads to missed changes

2. **Breaking Change Propagation**
   - Core updates require coordinated dependent package updates
   - Risk of version skew and incompatibility
   - Delayed adoption of core improvements

3. **No Deterministic Process**
   - Ad-hoc migration scripts
   - Inconsistent results across packages
   - Difficult to verify completeness

### Impact

- **Time Cost**: 4-8 hours per dependent package per core major version
- **Error Rate**: ~15-20% missed migrations in manual process
- **Adoption Lag**: 2-4 weeks delay for dependent packages to catch up

---

## Proposed Solution

### Core Concept

Generate machine-readable Change Manifests by comparing `.tree` snapshots and metadata stamps between core versions. Dependent packages consume these manifests to apply migrations safely and deterministically.

### Key Inputs

1. **`.tree` Structure Snapshots**
   - Canonical file and symbol inventory
   - Hash-based content verification (BLAKE3)
   - Hierarchical representation of codebase

2. **Metadata Stamps**
   - Symbol-level provenance
   - Stability indicators
   - Deprecation tracking
   - Export tags (`public_api`, `internal`, `experimental`)

3. **Git References**
   - Source version (`from`)
   - Target version (`to`)
   - Commit SHAs for reproducibility

### Key Outputs

1. **`change_manifest.yaml`**
   - Declarative, idempotent operations
   - Dependency-ordered
   - Confidence-scored
   - Provenance-tracked

2. **`manifest_report.json`**
   - Confidence scores per operation
   - Unresolved changes flagged for review
   - Statistics and metrics

3. **Migration Patches** (optional)
   - Preview patches per dependent repo
   - Dry-run validation
   - Test corpus verification

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CORE PACKAGE                         │
│  Version 0.9.0  ──────────→  Version 1.0.0              │
└─────────────┬────────────────────────┬──────────────────┘
              │                        │
              ↓                        ↓
┌─────────────────────┐    ┌─────────────────────┐
│  Snapshot A (0.9.0) │    │  Snapshot B (1.0.0) │
│  ├─ .tree           │    │  ├─ .tree           │
│  ├─ metadata        │    │  ├─ metadata        │
│  └─ symbol graph    │    │  └─ symbol graph    │
└──────────┬──────────┘    └──────────┬──────────┘
           │                          │
           └────────────┬─────────────┘
                        ↓
              ┌──────────────────┐
              │ INFERENCE ENGINE │
              │ ├─ Path matching │
              │ ├─ Symbol rename │
              │ ├─ Signature diff│
              │ ├─ Config moves  │
              │ └─ Confidence    │
              └────────┬─────────┘
                       ↓
              ┌──────────────────┐
              │ CHANGE MANIFEST  │
              │ (0.9.0 → 1.0.0)  │
              └────────┬─────────┘
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
 ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
 │ Dependent A │ │ Dependent B │ │ Dependent C │
 │ Auto-migrate│ │ Auto-migrate│ │ Auto-migrate│
 └─────────────┘ └─────────────┘ └─────────────┘
```

---

## Components

### 1. Snapshot Capture Service

**Responsibility**: Generate `.tree` and metadata for any git reference

**Input**:
- Git repository path
- Git ref (tag, commit SHA, branch)
- Configuration options

**Output**:
- `.tree` file (canonical structure)
- Metadata stamps (symbol-level provenance)
- Symbol graph (import/export relationships)

**Storage**: `artifacts/core_diff/{from}_{to}/`

### 2. Symbol Graph Extractor

**Responsibility**: Build import/export relationship graphs

**Features**:
- Fully-qualified symbol names (`pkg.mod.Class.method`)
- Import edges (dependencies)
- Inheritance edges (class hierarchies)
- Re-export edges (symbol exposure)

**Output**: `graph_from.json`, `graph_to.json`

### 3. Inference Engine

**Responsibility**: Detect changes and infer operations

**Inference Rules**:

| Change Type | Detection Method | Operation |
|-------------|------------------|-----------|
| **Module Move** | Identical hash + path change | `rename.import` or `move.file` |
| **Symbol Rename** | High AST/doc similarity + usage graph | `rename.symbol` |
| **Callable Arg Rename** | Same body + param rename | `arg.rename` |
| **Default Added** | New param with safe default | `arg.add_default` |
| **Config Key Move** | Identical type/value patterns | `config.key_rename` |

**Confidence Scoring**:
- AST structure similarity (0.0-1.0)
- Docstring similarity (0.0-1.0)
- Import graph overlap (0.0-1.0)
- Weighted combination → final confidence

### 4. Manifest Synthesis

**Responsibility**: Generate declarative migration manifest

**Features**:
- Idempotent operations
- Dependency ordering
- Confidence thresholds
- Provenance tracking
- Review flags for ambiguous cases

### 5. Verification Pipeline

**Responsibility**: Validate generated codemods

**Process**:
1. Apply manifest to reference corpus
2. Run tests
3. Generate patches
4. Produce migration report

---

## Data Formats

### `.tree` Snapshot

```yaml
version: 2
root: omninode/
files:
  - path: omninode/validators/base.py
    lang: python
    sha256: 97ff...
    symbols:
      - fq: omninode.validators.base.BaseValidator
        kind: class
        sig_sha: 7f3a...
```

### Metadata Stamp

```yaml
file: omninode/validators/base.py
exports:
  - fq: omninode.validators.base.BaseValidator
    tags: [validator, public_api]
    since: 0.7.0
    deprecated: false
```

### Change Manifest

```yaml
manifest_version: 1
from: 0.9.0
to: 1.0.0
summary: Path normalization, class renames, minor argument changes.

operations:
  - id: OP001
    kind: rename.import
    match:
      from: "omninode.core.validators.base"
      to: "omninode.validators.base"
    evidence:
      symbol_sha: "7f3a..."
    confidence: 1.0

  - id: OP002
    kind: rename.symbol
    match:
      module: "omninode.validators.base"
      from: "BaseValidator"
      to: "ValidatorBase"
    evidence:
      sig_from: "a1b2..."
      sig_to: "a1b2..."
    confidence: 1.0

  - id: OP003
    kind: arg.rename
    match:
      callable: "omninode.utils.io.read_file_text"
      from: "encoding"
      to: "codec"
      default: "utf-8"
      required: false
    evidence:
      callsites_sampled: 37
      safe_auto_fix_rate: 1.0
    confidence: 0.98
```

---

## CLI Design

### Generate Manifest

```bash
onx-manifest generate \
  --core-path ./core \
  --from 0.9.0 \
  --to 1.0.0 \
  --out artifacts/core_diff/0.9.0_1.0.0 \
  --confidence-threshold 0.8 \
  --parallel 4
```

**Steps**:
1. Checkout refs for both versions
2. Build `.tree` snapshots
3. Stamp metadata
4. Build symbol graphs
5. Infer operations
6. Score and synthesize manifest
7. Verify codemods
8. Emit report and patches

### Apply Manifest

```bash
onx-migrate apply \
  --manifest registry://core_migrations/0.9.0_1.0.0 \
  --target ./my_dependent_package \
  --dry-run \
  --diff-output migration_preview.patch
```

### Check Compatibility

```bash
onx-manifest compat \
  --package my_dependent_package \
  --core-versions ">=0.9.0,<2.0.0"
```

### Rollback

```bash
onx-migrate rollback \
  --package ./my_dependent_package \
  --to-version 0.9.0 \
  --checkpoint artifacts/rollback/checkpoint_pre_1.0.0
```

---

## Integration Points

### Services

**Tree Service**: `POST /snapshot` → `.tree` for any git ref
**Metadata Stamper**: `POST /stamp` → export-level metadata
**Registry**: Publishes manifests to `registry://core_migrations/{from}_{to}/`
**Event Bus**: Emits `core.migration.ready` with manifest URI
**Dependent Clients**: Subscribe and run `onx-migrate apply`

### Event Flow

```
1. Core version released (e.g., 1.0.0)
   ↓
2. CI triggers manifest generation
   ↓
3. Manifest published to registry
   ↓
4. Event: core.migration.ready
   ↓
5. Dependent packages notified
   ↓
6. Auto-create migration PR
   ↓
7. Run tests → merge or flag for review
```

---

## MVP Scope

### Phase 1: Foundation (Weeks 1-3)

- [x] `.tree` + metadata diffing for Python core
- [x] Operations supported:
  - `rename.import`
  - `rename.symbol`
  - `rename.callable`
  - `arg.rename`
  - `config.key_rename`
- [x] CLI with dry-run and diff report
- [x] Confidence scoring
- [x] Integration with Tree Service

### Phase 2: Intelligence (Weeks 4-6)

- [ ] Advanced inference algorithms
- [ ] Archon Intelligence integration
- [ ] Codemod generation (AST-based)
- [ ] Verification with test corpus
- [ ] Migration templates library

### Phase 3: Orchestration (Weeks 7-9)

- [ ] Dependency graph resolution
- [ ] Multi-package coordination
- [ ] Event bus integration
- [ ] Registry publishing
- [ ] Rollback mechanism

### Phase 4: Production (Weeks 10-12)

- [ ] Breaking change detection + semver
- [ ] Metrics and monitoring
- [ ] Documentation generation
- [ ] E2E testing suite
- [ ] Production deployment

---

## Safety and Review

### Determinism

- All manifests are regenerable from source
- Hash-based content verification
- Reproducible git refs

### Confidence Thresholds

| Confidence | Action |
|------------|--------|
| **≥ 0.9** | Auto-apply |
| **0.7-0.9** | Apply with warning |
| **< 0.7** | Flag for manual review |

### Provenance

Every operation includes:
- Inference method
- Evidence hashes
- Confidence calculation
- Source git refs

### Verification

- Test corpus validation
- Dry-run patch generation
- Manual review for ambiguous cases

---

## Benefits

### For Core Maintainers

- **Zero manual change documentation**
- **Automatic manifest generation**
- **Reduced support burden**
- **Faster adoption of improvements**

### For Dependent Package Owners

- **Automated migration**
- **Safe, deterministic updates**
- **Preview before applying**
- **Rollback capability**

### For the Ecosystem

- **Faster innovation cycles**
- **Reduced version skew**
- **Higher core quality**
- **Manifests double as release notes**

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Inference Accuracy** | >95% | Manual review of 100 migrations |
| **Confidence Calibration** | ±5% | Predicted vs actual success rate |
| **Processing Time** | <5min for 10k files | Benchmark on omnibase_core |
| **Manual Review Rate** | <10% of operations | Low-confidence operation count |
| **Migration Success Rate** | >98% | Applied migrations without failures |
| **Adoption Time** | <24 hours | Time to merge migration PRs |

---

## Risks and Mitigation

### Risk: Low confidence in symbol matching

**Mitigation**: Require manual review for confidence <0.7
**Fallback**: Generate todo comments instead of auto-fixing

### Risk: Cascading failures across dependent packages

**Mitigation**: Dependency graph with rollback checkpoints
**Fallback**: Package-by-package migration with validation gates

### Risk: Performance degradation on large repos

**Mitigation**: Incremental diffing, parallel processing, caching
**Fallback**: Batch processing with configurable chunk sizes

---

## Next Steps

1. **Create architecture document** (`docs/architecture/CORE_MIGRATION_ARCHITECTURE.md`)
2. **Define manifest schema v1** with comprehensive examples
3. **Build symbol graph prototype** using Archon's relationship detector
4. **Set up test corpus** with known migration scenarios
5. **Integrate with Tree Service** for snapshot capture
6. **Implement MVP inference engine**
7. **Create CLI with dry-run mode**

---

## References

- **Tree Service**: `/services/tree/` (ONEX tree indexing)
- **Metadata Stamper**: `/services/metadata_stamping/`
- **Archon Intelligence**: `/services/intelligence/` (pattern learning, relationship detection)
- **Related Docs**:
  - `AUTOMATED_TREE_STAMPING.md`
  - `MIGRATION_GUIDE.md`
  - `TRACEABILITY_AND_PATTERN_LEARNING_SYSTEM_DESIGN.md`

---

**Document Status**: Planning - Ready for Architecture Phase
**Next Document**: `CORE_MIGRATION_ARCHITECTURE.md`
