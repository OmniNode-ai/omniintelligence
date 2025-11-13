# Shared Resource Versioning Strategy

**Version**: 1.0.0
**Date**: 2025-10-01
**Status**: ✅ Final Design

---

## Problem Statement

When models or protocols are shared between multiple nodes in a group:
- How do we version them independently from nodes?
- How do we handle breaking changes?
- How do we deprecate old versions?
- How do we allow gradual migration?

---

## Solution: Independent Versioning with `shared/` Directory

### Structure

```
<node_group>/                           # e.g., "canary"
│
├── shared/                             # Shared resources with independent versioning
│   │
│   ├── models/                         # Shared Pydantic models
│   │   ├── v1/                         # Major version 1 (stable)
│   │   │   ├── __init__.py
│   │   │   ├── model_http_headers.py
│   │   │   └── model_common_types.py
│   │   │
│   │   └── v2/                         # Major version 2 (breaking changes)
│   │       ├── __init__.py
│   │       ├── model_http_headers.py  # Different from v1
│   │       └── model_common_types.py
│   │
│   └── protocols/                      # Shared protocols (if truly shared)
│       ├── v1/
│       │   ├── __init__.py
│       │   └── protocol_common.py
│       │
│       └── v2/
│           ├── __init__.py
│           └── protocol_common.py
│
└── <node_name>/
    ├── v1_0_0/
    │   └── node.py                     # imports from shared/models/v1/
    └── v2_0_0/
        └── node.py                     # imports from shared/models/v2/
```

---

## Key Principles

### 1. Independent Lifecycle

**Shared resources version INDEPENDENTLY from nodes**:
- `shared/models/v1` is NOT tied to any node version
- `shared/models/v2` can be created when ANY node needs breaking changes
- Nodes choose which shared version they need

### 2. Major Version Only

Use **major versions only** (v1, v2, v3), not semantic versioning (v1_0_0):

**Why**:
- Non-breaking changes can be added to existing version
- Avoids directory explosion
- Follows Python stdlib pattern (urllib, urllib2, typing)

**Within a major version** (non-breaking changes allowed):
- ✅ Add optional fields with defaults
- ✅ Add new models
- ✅ Deprecate fields (mark but don't remove)
- ❌ Remove fields
- ❌ Rename fields
- ❌ Change field types

**Breaking changes** → New major version (v2)

### 3. Lazy Promotion to `shared/`

**Don't create `shared/` upfront**. Follow this progression:

```
Phase 1: Model in node
node_1/v1_0_0/models/model_data.py

Phase 2: Second node needs it → Promote to shared/v1/
shared/models/v1/model_data.py
node_1/v1_0_0/  # updates imports
node_2/v1_0_0/  # uses shared version

Phase 3: Breaking change needed → Create v2
shared/models/v1/model_data.py  # Old version (frozen)
shared/models/v2/model_data.py  # New version (breaking changes)
node_1/v1_0_0/  # still uses v1
node_2/v2_0_0/  # uses v2
```

### 4. Gradual Migration

**Old versions remain until all nodes migrate**:

```python
# shared/models/v1/__init__.py
import warnings

warnings.warn(
    "shared.models.v1 is deprecated. "
    "Migrate to shared.models.v2. "
    "Will be archived when all nodes migrate.",
    DeprecationWarning,
    stacklevel=2
)
```

**Archive criteria**: Archive vN when `grep -r "shared/models/vN" <node_group>` returns 0 results

---

## Usage Examples

### Example 1: Initial Promotion

**Before** (node-local):
```python
# node_1/v1_0_0/models/model_http_headers.py
from pydantic import BaseModel

class ModelHttpHeaders(BaseModel):
    content_type: str
    authorization: str
```

**After** (promoted to shared):
```
# 1. Create shared/models/v1/
mkdir -p shared/models/v1

# 2. Move model
mv node_1/v1_0_0/models/model_http_headers.py shared/models/v1/

# 3. Update imports in node_1
# node_1/v1_0_0/node.py
from ...shared.models.v1.model_http_headers import ModelHttpHeaders

# 4. Use in node_2
# node_2/v1_0_0/node.py
from ...shared.models.v1.model_http_headers import ModelHttpHeaders
```

### Example 2: Non-Breaking Change (within v1)

**Add optional field** (allowed in v1):
```python
# shared/models/v1/model_http_headers.py
from pydantic import BaseModel
from typing import Optional

class ModelHttpHeaders(BaseModel):
    content_type: str
    authorization: str
    cache_control: Optional[str] = None  # ✅ Non-breaking: optional with default
```

**All nodes using v1 continue to work** (don't need code changes).

### Example 3: Breaking Change (requires v2)

**Need to rename field** (breaking change):
```python
# shared/models/v2/model_http_headers.py
from pydantic import BaseModel

class ModelHttpHeaders(BaseModel):
    content_type: str
    auth_token: str  # ❌ Breaking: renamed from 'authorization'
```

**Migration**:
```python
# node_2/v2_0_0/node.py
from ...shared.models.v2.model_http_headers import ModelHttpHeaders
# Must update code to use 'auth_token' instead of 'authorization'

# node_1/v1_0_0/node.py (unchanged)
from ...shared.models.v1.model_http_headers import ModelHttpHeaders
# Still uses v1 with 'authorization' - no changes needed
```

### Example 4: Deprecation and Removal

**Step 1**: Mark v1 as deprecated
```python
# shared/models/v1/__init__.py
import warnings
warnings.warn("Deprecated. Use shared.models.v2", DeprecationWarning)
```

**Step 2**: Migrate nodes
```bash
# Check which nodes still use v1
grep -r "shared.models.v1" canary/

# Migrate node_1 to v2
# Update node_1/v2_0_0/node.py imports
```

**Step 3**: Archive when no references
```bash
# Verify no nodes use v1
grep -r "shared.models.v1" canary/
# (returns nothing)

# Archive v1
mv shared/models/v1 archived/shared_models_v1/
```

---

## Protocols: Same Strategy

**Same versioning applies to protocols**:

```
shared/protocols/
├── v1/
│   └── protocol_file_system.py
└── v2/
    └── protocol_file_system.py
```

**But**: Prefer node-local protocols unless truly shared across 2+ nodes.

**Decision rule**:
- Node-specific protocol → `node/v1_0_0/protocols/`
- Shared across 2+ nodes → `shared/protocols/v1/`
- Framework-wide → `omnibase_spi/protocols/`

---

## Version Coordination

### compatibility.yaml Tracks Shared Versions

```yaml
# <node_group>/compatibility.yaml
version: 1.0.0
description: "Version compatibility matrix"

compatible_sets:
  - set_id: "stable-2024-08"
    shared_models_version: "v1"
    shared_protocols_version: "v1"
    nodes:
      canary_impure_tool: "v1_0_0"
      canary_pure_tool: "v1_0_0"

  - set_id: "experimental-2024-09"
    shared_models_version: "v2"  # Uses newer shared models
    shared_protocols_version: "v1"
    nodes:
      canary_impure_tool: "v1_0_0"  # Still on old node version, uses v1 models
      canary_pure_tool: "v2_0_0"    # New node version, uses v2 models
```

---

## Migration Checklist

### Creating New Shared Version

- [ ] Identify breaking change needed
- [ ] Create `shared/models/vN+1/` directory
- [ ] Copy models from `vN/` to `vN+1/`
- [ ] Make breaking changes in `vN+1/`
- [ ] Add deprecation warning to `vN/__init__.py`
- [ ] Update `compatibility.yaml` with new version
- [ ] Document migration guide in `shared/models/vN+1/MIGRATION.md`

### Archiving Old Version

- [ ] Verify no nodes reference old version: `grep -r "shared.models.vN"`
- [ ] Move to archive: `mv shared/models/vN archived/`
- [ ] Update `compatibility.yaml` (remove deprecated sets)
- [ ] Add archive notice to `CHANGELOG.md`

---

## Anti-Patterns

### ❌ Creating shared/v1/ Upfront

```
# WRONG - created before any node needs it
shared/models/v1/
  └── model_*.py  # "Just in case"
```

**Correct**: Create `shared/v1/` only when 2nd node needs the model.

### ❌ Semantic Versioning (v1_0_0)

```
# WRONG - too granular
shared/models/v1_0_0/
shared/models/v1_1_0/
shared/models/v2_0_0/
```

**Correct**: Major version only (v1, v2, v3).

### ❌ Making Breaking Changes in Existing Version

```python
# WRONG - breaking change in v1
# shared/models/v1/model_data.py
class ModelData(BaseModel):
    new_field: str  # Breaking: removed old_field, added required new_field
```

**Correct**: Create v2 for breaking changes.

### ❌ Premature Promotion

```
# WRONG - only one node uses it
shared/models/v1/model_unique.py  # Only node_1 uses it

# CORRECT - keep in node until 2+ need it
node_1/v1_0_0/models/model_unique.py
```

---

## Decision Trees

### Should I Promote This Model to shared/?

```
Does model exist in 2+ nodes?
  NO  → Keep in node/v1_0_0/models/
  YES → Is it semantically identical?
          NO  → Keep separate (similar ≠ same)
          YES → Promote to shared/models/v1/
```

### Should I Create shared/models/v2/?

```
Need to make a change to shared/models/v1/?
  NO  → Keep using v1
  YES → Is it non-breaking?
          YES → Add to existing v1/
          NO  → Create v2/ (new major version)
```

### When Should I Archive shared/models/v1/?

```
Is v2 available?
  NO  → Keep v1 active
  YES → Do any nodes still import from v1?
          YES → Keep v1 (deprecated but working)
          NO  → Archive v1 (no references)
```

---

## Summary

**Shared resource versioning strategy**:

1. ✅ **Independent versioning**: `shared/models/v1/` separate from node versions
2. ✅ **Major version only**: v1, v2, v3 (not v1_0_0)
3. ✅ **Lazy promotion**: Create shared/ only when 2+ nodes need it
4. ✅ **Gradual migration**: Old versions remain until all nodes migrate
5. ✅ **Non-breaking within major**: Add optional fields in existing version
6. ✅ **Breaking → new major**: Create v2/ for breaking changes
7. ✅ **Deprecation warnings**: Mark old versions as deprecated
8. ✅ **Archive when unused**: Remove only when no references remain

This allows:
- Independent node evolution
- Shared resource stability
- Gradual migration paths
- Clear versioning semantics
