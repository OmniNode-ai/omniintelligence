# Validation Integration Plan for OmniIntelligence

This document outlines the plan to integrate `omnibase_core` validators to establish a standard quality baseline.

## Current Structure

```
src/omniintelligence/
├── _archived/        # Archived code (excluded from validation)
│   ├── adapters/
│   ├── clients/
│   ├── contracts/
│   ├── enums/
│   ├── events/
│   ├── models/
│   ├── shared/
│   └── utils/
├── nodes/            # Node implementations (contracts validated)
└── tools/            # New code (full validation)
```

## Current Baseline Assessment

| Validator | Status | Scope | Notes |
|-----------|--------|-------|-------|
| **ruff** | ✅ PASSED | tools/ | New code only |
| **mypy** | ✅ PASSED | tools/ | --strict mode |
| **Architecture** | ✅ PASSED | non-archived | After _archived move |
| **Contracts** | ✅ PASSED | nodes/ | 16 contracts validated |
| **Union-Usage** | ✅ PASSED | all | No issues |
| **Patterns** | ✅ PASSED | all | No issues |
| **contract_linter** | ✅ PASSED | nodes/ | Custom linter |

## Validation Commands

```bash
# Run all validators
poetry run python -m omnibase_core.validation.cli all src/omniintelligence

# Individual validators
poetry run python -m omnibase_core.validation.cli architecture src/omniintelligence
poetry run python -m omnibase_core.validation.cli contracts src/omniintelligence
poetry run python -m omnibase_core.validation.cli union-usage src/omniintelligence
poetry run python -m omnibase_core.validation.cli patterns src/omniintelligence

# With options
poetry run python -m omnibase_core.validation.cli architecture src/omniintelligence --verbose
poetry run python -m omnibase_core.validation.cli all src/omniintelligence --strict
```

---

## Phase 1: CI Integration (Immediate)

### 1.1 Add Validation Script

Create `scripts/validate.sh`:
```bash
#!/bin/bash
set -e

echo "Running ONEX validation suite..."

# Run validators that currently pass (block on failures)
poetry run python -m omnibase_core.validation.cli union-usage src/omniintelligence
poetry run python -m omnibase_core.validation.cli patterns src/omniintelligence

# Run validators that currently fail (report only, don't block)
poetry run python -m omnibase_core.validation.cli architecture src/omniintelligence --exit-zero
poetry run python -m omnibase_core.validation.cli contracts src/omniintelligence --exit-zero

echo "Validation complete!"
```

### 1.2 Add to pyproject.toml

```toml
[tool.poetry.scripts]
validate = "scripts.validate:main"
```

### 1.3 Pre-commit Hook (Optional)

Add to `.pre-commit-config.yaml`:
```yaml
- repo: local
  hooks:
    - id: onex-validate
      name: ONEX Validation
      entry: poetry run python -m omnibase_core.validation.cli patterns src/omniintelligence
      language: system
      pass_filenames: false
```

---

## Phase 2: Architecture Compliance (28 Issues)

### Issue Categories

| Category | Count | Description |
|----------|-------|-------------|
| Multiple enums per file | ~8 | Files with 2+ enum definitions |
| Multiple models per file | ~15 | Files with 2+ Pydantic models |
| Mixed types per file | ~5 | Files mixing models and enums |

### 2.1 Enum Refactoring

**Current:**
```
src/omniintelligence/enums/enum_fsm.py  # 5 enums
src/omniintelligence/enums/enum_entity.py  # 2 enums
```

**Target:**
```
src/omniintelligence/enums/
├── enum_fsm_type.py           # EnumFSMType
├── enum_fsm_action.py         # EnumFSMAction
├── enum_ingestion_state.py    # EnumIngestionState
├── enum_pattern_learning_state.py  # EnumPatternLearningState
├── enum_quality_assessment_state.py  # EnumQualityAssessmentState
├── enum_entity_type.py        # EnumEntityType
└── enum_relationship_type.py  # EnumRelationshipType
```

### 2.2 Model Refactoring

**Current:**
```
src/omniintelligence/models/model_intelligence_output.py  # 3 models
src/omniintelligence/models/model_intelligence_adapter_events.py  # 7 models + 3 enums
```

**Target:**
```
src/omniintelligence/models/
├── model_pattern_detection.py
├── model_intelligence_metrics.py
├── model_intelligence_output.py
├── model_code_analysis_request_payload.py
├── model_code_analysis_completed_payload.py
├── model_code_analysis_failed_payload.py
...
```

### 2.3 Implementation Strategy

1. **Create new files** with single model/enum each
2. **Update imports** in existing code
3. **Add re-exports** in `__init__.py` for backwards compatibility
4. **Remove old multi-model files** after refactoring
5. **Run architecture validator** to confirm compliance

---

## Phase 3: Contract Compliance (27 Issues)

### Issue Analysis

The contract validator checks against `omnibase_core` schema. Our contracts use omniintelligence-specific conventions:

| Our Convention | omnibase_core Expectation |
|----------------|---------------------------|
| `operations` section | Type-specific fields |
| `base_class` field | Not in base schema |
| FSM subcontracts | Different schema entirely |

### 3.1 Options

**Option A: Align with omnibase_core schema**
- Update all contract YAMLs to match omnibase_core exactly
- May lose omniintelligence-specific fields

**Option B: Extend omnibase_core validators**
- Create omniintelligence-specific contract validator
- Inherits from core, adds local conventions
- Already implemented in `src/omniintelligence/tools/contract_linter.py`

**Option C: Configure validator exceptions**
- Use `--exit-zero` for contracts in CI
- Document known differences
- Address over time

### 3.2 Recommended Approach

Use **Option C** for now, transition to **Option B**:

1. Keep using our `contract_linter.py` for omniintelligence-specific validation
2. Use `omnibase_core` contract validator with `--exit-zero` for visibility
3. Gradually align contracts where possible

---

## Phase 4: Validation Script Implementation

### 4.1 Create Unified Validation Script

Location: `scripts/validate.py`

```python
#!/usr/bin/env python3
"""Unified validation script for omniintelligence."""

import subprocess
import sys
from pathlib import Path

def run_validator(validator: str, strict: bool = False) -> bool:
    """Run a single validator and return success status."""
    cmd = [
        "python", "-m", "omnibase_core.validation.cli",
        validator, "src/omniintelligence"
    ]
    if not strict:
        cmd.append("--exit-zero")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0

def main():
    print("=" * 60)
    print("ONEX Validation Suite for OmniIntelligence")
    print("=" * 60)

    results = {}

    # Blocking validators (must pass)
    for validator in ["union-usage", "patterns"]:
        print(f"\n▶ Running {validator}...")
        results[validator] = run_validator(validator, strict=True)

    # Non-blocking validators (report only)
    for validator in ["architecture", "contracts"]:
        print(f"\n▶ Running {validator} (non-blocking)...")
        results[validator] = run_validator(validator, strict=False)

    # Run our custom contract linter
    print("\n▶ Running omniintelligence contract linter...")
    # Convert glob generator to list of strings for subprocess
    contract_files = [str(p) for p in Path("src/omniintelligence/nodes").glob("*/v1_0_0/contracts/*.yaml")]
    linter_result = subprocess.run([
        "python", "-m", "omniintelligence.tools.contract_linter"
    ] + contract_files)
    results["contract_linter"] = linter_result.returncode == 0

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    for name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {name}: {status}")

    # Exit with failure if blocking validators failed
    blocking_failed = not all(results.get(v, True) for v in ["union-usage", "patterns"])
    sys.exit(1 if blocking_failed else 0)

if __name__ == "__main__":
    main()
```

---

## Phase 5: Quality Gates

### 5.1 Gate Definitions

| Gate | Validators | Mode | When |
|------|------------|------|------|
| **Pre-commit** | patterns | Blocking | Every commit |
| **PR Check** | union-usage, patterns | Blocking | PR creation |
| **Nightly** | all | Report | Scheduled |

### 5.2 GitHub Actions Integration

```yaml
# .github/workflows/validate.yml
name: ONEX Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install poetry
      - run: poetry install --with dev,core
      - run: poetry run python scripts/validate.py
```

---

## Phase 6: Tracking & Metrics

### 6.1 Baseline Metrics

| Metric | Current | Target (MVP) | Target (Beta) |
|--------|---------|--------------|---------------|
| Architecture violations | 28 | 20 | 0 |
| Contract violations | 27 | 20 | 10 |
| Union-usage violations | 0 | 0 | 0 |
| Pattern violations | 0 | 0 | 0 |

### 6.2 Progress Tracking

Create Linear issues for major refactoring:
- [ ] Split enum files (8 files → 15+ files)
- [ ] Split model files (15 files → 30+ files)
- [ ] Align contract schema where possible

---

## Implementation Order

1. **Immediate**: Add `scripts/validate.py`
2. **This Sprint**: CI integration with non-blocking validators
3. **Phase 2-3**: Architecture refactoring (gradual)
4. **Ongoing**: Contract alignment

---

## Commands Reference

```bash
# Quick check (blocking validators only)
poetry run python -m omnibase_core.validation.cli union-usage src/omniintelligence
poetry run python -m omnibase_core.validation.cli patterns src/omniintelligence

# Full check (all validators, verbose)
poetry run python -m omnibase_core.validation.cli all src/omniintelligence --verbose

# With custom contract linter
poetry run python -m omniintelligence.tools.contract_linter \
    src/omniintelligence/nodes/*/v1_0_0/contracts/*.yaml
```
