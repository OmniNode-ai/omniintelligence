# Label Case Consistency Test Suite

## Overview

Integration test suite to validate Memgraph label case consistency across all layers and prevent regression of the label case bug discovered on 2025-11-12.

## Test File

`tests/integration/test_label_case_consistency.py`

## Test Coverage

### 1. Constants Layer Validation

- **test_constants_match_production_labels** ✅
  - Verifies `MemgraphLabels` enum has correct case-sensitive values
  - Validates: `FILE → "File"`, `PROJECT → "PROJECT"`, `DIRECTORY → "Directory"`, etc.
  - Ensures legacy `LABEL_*` constants match enum values

- **test_relationship_constants** ✅
  - Verifies `MemgraphRelationships` enum values
  - Validates: `CONTAINS`, `IMPORTS`, `HAS_CONCEPT`, etc.

### 2. Database Layer Validation

- **test_memgraph_has_correct_label_case** ✅
  - Queries actual Memgraph database
  - Verifies nodes use correct label case:
    - `:File` nodes (not `:FILE`)
    - `:PROJECT` nodes (not `:Project`)
    - `:Directory` nodes (not `:DIRECTORY`)
  - Counts nodes with incorrect case variants (should be zero)

### 3. Validation Function Testing

- **test_validate_label_function** ✅
  - Tests the `validate_label()` helper function
  - Used for pre-commit hooks and runtime validation
  - Validates:
    - `validate_label("File")` → `True`
    - `validate_label("FILE")` → `False` (wrong case)
    - `validate_label("PROJECT")` → `True`
    - `validate_label("Project")` → `False` (wrong case)

### 4. Static Code Analysis

- **test_no_raw_label_strings_in_production** ❌ (currently failing - expected)
  - Scans production code for raw label strings in Cypher queries
  - Examples: `"MATCH (n:FILE)"` instead of `f"MATCH (n:{MemgraphLabels.FILE})"`
  - **Production code violations** → FAIL test (4 files found)
  - **Script violations** → WARNING only (14 legacy scripts logged)
  - Skips:
    - Comments and docstrings
    - Example code (lines with `>>>` or `example`)
    - Cache key patterns (`file_location:project:`)
    - Legacy migration scripts

### 5. Comprehensive Regression Prevention

- **test_label_case_regression_prevention** ✅
  - Multi-layer validation combining all checks
  - Verifies:
    1. Constants correct
    2. Validation function works
    3. Memgraph has no incorrect labels
    4. All label variants covered
  - Generates comprehensive summary report

## Current Status

**5 of 6 tests passing** ✅

**1 test failing** (expected) ❌:
- `test_no_raw_label_strings_in_production` found **4 production files** with raw label strings

### Production Code Issues Found

1. `services/intelligence/src/schemas/memgraph_schemas.py`
   - Using `:Project` instead of `:PROJECT`
   - 6 violations found

2. `services/intelligence/src/integrations/tree_stamping_bridge.py`
   - Using `:Project` instead of `:PROJECT`
   - 1 violation found

3. `services/intelligence/src/api/knowledge_graph/service.py`
   - Using `:Project` instead of `:PROJECT`
   - 1 violation found

4. `services/intelligence/src/api/data_quality/routes.py`
   - Using `:FILE` and `:DIRECTORY` instead of `:File` and `:Directory`
   - Multiple violations found

### Script Issues (Logged as Warnings)

14 legacy/diagnostic scripts have violations but don't fail the test:
- `validate_graph_health.py`
- `migrate_file_labels.py`
- `verify_pipeline_status.py`
- `data_quality_dashboard.py`
- `monitor_orphans.py`
- `analyze_node_properties.py`
- `diagnose_pipeline_issue.py`
- `build_directory_tree.py`
- `check_file_paths.py`
- `migrate_orphaned_file_nodes.py`
- `orphan_alerting.py`
- `delete_all_file_nodes.py`
- `analyze_entity_id_formats.py`
- `quick_relationship_validation.py`

## Running the Tests

```bash
# Run all label consistency tests
python3 -m pytest tests/integration/test_label_case_consistency.py -v

# Run specific test
python3 -m pytest tests/integration/test_label_case_consistency.py::test_constants_match_production_labels -v

# Run with detailed output
python3 -m pytest tests/integration/test_label_case_consistency.py -v --tb=short

# Run static analysis only
python3 -m pytest tests/integration/test_label_case_consistency.py::test_no_raw_label_strings_in_production -v
```

## Next Steps

### To Fix Production Code Issues

1. **Update memgraph_schemas.py**:
   ```python
   # Before:
   query = "MERGE (p:Project {name: $name})"

   # After:
   from services.intelligence.src.constants import MemgraphLabels
   query = f"MERGE (p:{MemgraphLabels.PROJECT} {{name: $name}})"
   ```

2. **Update tree_stamping_bridge.py**:
   ```python
   # Before:
   query = "MERGE (p:Project {name: file.project_name})"

   # After:
   from services.intelligence.src.constants import MemgraphLabels
   query = f"MERGE (p:{MemgraphLabels.PROJECT} {{name: file.project_name}})"
   ```

3. **Update knowledge_graph/service.py**:
   ```python
   # Before:
   query = "OPTIONAL MATCH project_path = (:Project {name: $project_name})-[:CONTAINS*]->(n)"

   # After:
   from services.intelligence.src.constants import MemgraphLabels
   query = f"OPTIONAL MATCH project_path = (:{MemgraphLabels.PROJECT} {{name: $project_name}})-[:CONTAINS*]->(n)"
   ```

4. **Update data_quality/routes.py**:
   ```python
   # Before:
   query = "MATCH (f:FILE)"
   query = "MATCH (d:DIRECTORY)"

   # After:
   from services.intelligence.src.constants import MemgraphLabels
   query = f"MATCH (f:{MemgraphLabels.FILE})"
   query = f"MATCH (d:{MemgraphLabels.DIRECTORY})"
   ```

### To Verify Fixes

```bash
# After fixing production code, all tests should pass
python3 -m pytest tests/integration/test_label_case_consistency.py -v

# Expected output:
# ✅ test_constants_match_production_labels PASSED
# ✅ test_relationship_constants PASSED
# ✅ test_memgraph_has_correct_label_case PASSED
# ✅ test_validate_label_function PASSED
# ✅ test_no_raw_label_strings_in_production PASSED (with script warnings)
# ✅ test_label_case_regression_prevention PASSED
#
# 6 of 6 tests passing
```

## Test Philosophy

This test suite follows a **pragmatic regression prevention** approach:

1. **Critical for production code** - Must use constants (test fails if violated)
2. **Permissive for scripts** - Logged as warnings (legacy/diagnostic tools)
3. **Multi-layer validation** - Constants, database, static analysis, runtime
4. **Clear failure messages** - Developers know exactly what to fix
5. **Regression prevention** - Prevents reintroduction of label case bugs

## References

- **Constants**: `services/intelligence/src/constants/memgraph_labels.py`
- **Runtime validation**: `tests/integration/test_node_label_consistency.py`
- **Bug context**: Label case inconsistency discovered 2025-11-12
- **ONEX Pattern**: Multi-layer schema validation testing

---

**Created**: 2025-11-12
**Correlation ID**: 2d4eef60-fa9f-411d-8ee5-76a9fc972cd9
**Priority**: MEDIUM
**Status**: Test suite complete, production code fixes needed
