# Entity_ID Format Quick Reference

**Last Updated**: 2025-11-09
**Purpose**: Developer reference for entity_id formats in Memgraph

---

## Current State (BEFORE FIX)

### ❌ Problem: Two Incompatible Formats

**Format 1**: `file_<hash>` - Used by indexing (REAL nodes)
**Format 2**: `file:project:module` - Used by relationships (PLACEHOLDERs)

**Result**: Relationships don't connect to real indexed files!

---

## Entity_ID Formats by Node Type

### FILE Nodes

#### ✅ REAL FILE Nodes (343 nodes)
```
Format:   file_<hash12>
Example:  file_91f521860bc3
Created:  During document indexing
Props:    15-16 properties (full metadata)
Status:   ORPHANED (0 relationships)
```

**Properties**:
- entity_id, name, path, project_name
- content_type, language, file_size, line_count
- file_hash, entity_count, import_count
- indexed_at, created_at, last_modified
- relative_path

**Used in**:
- `services/intelligence/storage/memgraph_adapter.py`
- Document indexing pipeline

---

#### ⚠️ PLACEHOLDER FILE Nodes - Import Type (636 nodes)
```
Format:   file:<project>:<module>
Example:  file:omniarchon:asyncio
          file:omniarchon:httpx
          file:omniarchon:typing.Any
Created:  During relationship creation (for imports)
Props:    4 properties (minimal stub)
Status:   CONNECTED (has IMPORTS relationships)
```

**Properties**:
- entity_id, name (always "unknown"), path, created_at

**Used in**:
- Relationship creation code
- Import dependency tracking

---

#### ⚠️ PLACEHOLDER FILE Nodes - Path Type (206 nodes)
```
Format:   file:<project>:<archon://path>
Example:  file:omniarchon:archon://projects/omniarchon/documents//Volumes/PRO-G40/Code/omniarchon/python/tests/real_integration/test_kafka_event_flow.py
Created:  During relationship creation (for file refs)
Props:    4 properties (minimal stub)
Status:   CONNECTED (has IMPORTS relationships)
```

**Properties**:
- entity_id, name (always "unknown"), path, created_at

---

### Entity Nodes

#### ✅ Full Entity Nodes (5,812 nodes)
```
Format:   entity_<hash8>_<hash8>
Example:  entity_7275cb2b_f839d8c2
          entity_79775386_91f52186
Created:  During semantic extraction
Props:    11 properties (rich metadata)
Status:   CONNECTED (has RELATES relationships)
```

**Properties**:
- entity_id, name, description, entity_type
- confidence_score, extraction_method
- file_hash, source_path, source_line_number
- properties (JSON), created_at

**Entity Types**:
- CONCEPT, FUNCTION, CLASS, VARIABLE, etc.

---

#### ⚠️ Stub Entity Nodes (5 nodes)
```
Format:   <simple_name>
Example:  httpx, inline, time, json, sys
Created:  As relationship targets (references)
Props:    4 properties (minimal stub)
Status:   CONNECTED (relationship targets)
```

**Properties**:
- entity_id, name, entity_type (always "reference"), is_stub (True)

---

## Format Decision Tree

### When Creating a FILE Node Entity_ID

```
Is this a REAL indexed file?
├─ YES → Use: file_<hash>
│         Where: hash = first 12 chars of file_hash or BLAKE3
│         Example: file_91f521860bc3
│
└─ NO → Is it an import reference?
    ├─ YES → Use: file:<project>:<module>
    │         Example: file:omniarchon:asyncio
    │
    └─ NO → Is it a path reference?
        └─ YES → Use: file:<project>:<path>
                  Example: file:omniarchon:archon://projects/...
```

### When Creating an Entity Node Entity_ID

```
Is this a full semantic entity?
├─ YES → Use: entity_<hash1>_<hash2>
│         Where: hash1 = entity content hash (8 chars)
│                hash2 = source file hash (8 chars)
│         Example: entity_7275cb2b_f839d8c2
│
└─ NO → Is it a reference stub?
    └─ YES → Use: <simple_name>
              Example: httpx, inline
```

---

## Code Location Reference

### Entity_ID Generation

#### FILE nodes (file_* format)
```
Location: services/intelligence/storage/memgraph_adapter.py
Function: _create_file_node()
Logic:    entity_id = f"file_{hash[:12]}"
```

#### FILE nodes (file:project:module format)
```
Location: [TO BE IDENTIFIED]
Function: [Relationship creation]
Logic:    entity_id = f"file:{project}:{module}"
```

#### Entity nodes (entity_* format)
```
Location: services/intelligence/storage/memgraph_adapter.py
Function: _create_entity_node()
Logic:    entity_id = f"entity_{content_hash[:8]}_{file_hash[:8]}"
```

---

## Lookup/Matching Strategy

### Problem
Given a module name `asyncio`, how do we find the actual FILE node?

#### Current Broken Flow
```python
# Relationship code does:
target_id = f"file:{project}:asyncio"  # Creates PLACEHOLDER

# But database has:
real_id = "file_91f521860bc3"  # From indexing

# Result: No match, creates orphaned PLACEHOLDER
```

#### Proposed Solution
```python
def resolve_file_entity_id(project: str, module_or_path: str) -> str:
    """
    Resolve module/path to canonical entity_id

    1. Try exact match: file_<hash>
    2. Try path lookup in database
    3. Create PLACEHOLDER if not found (fallback)
    """

    # Query Memgraph for existing node
    cypher = """
    MATCH (f:FILE)
    WHERE f.path CONTAINS $module_or_path
       OR f.name = $module_or_path
    RETURN f.entity_id
    LIMIT 1
    """

    result = session.run(cypher, module_or_path=module_or_path)
    if result.single():
        return result.single()["f.entity_id"]  # Return REAL entity_id

    # Fallback: create placeholder format
    return f"file:{project}:{module_or_path}"
```

---

## Migration Strategy

### Phase 1: Audit (COMPLETE)
- ✅ Identified all entity_id formats in database
- ✅ Counted REAL vs PLACEHOLDER nodes
- ✅ Documented orphaned nodes

### Phase 2: Code Unification (TODO)
1. Find all entity_id generation points
2. Standardize to single format (`file_<hash>`)
3. Implement lookup service for cross-references

### Phase 3: Relationship Fixing (TODO)
1. Update relationship creation to lookup existing nodes
2. Delete orphaned PLACEHOLDERs
3. Reconnect relationships to REAL nodes

### Phase 4: Validation (TODO)
1. Verify 0 orphaned REAL nodes
2. Verify all relationships target REAL nodes
3. Verify PLACEHOLDER count = 0

---

## Validation Queries

### Count nodes by format
```cypher
MATCH (f:FILE)
WITH f.entity_id STARTS WITH 'file_' as is_real,
     f.entity_id CONTAINS ':' as is_placeholder
RETURN is_real, is_placeholder, count(*) as count
```

### Find orphaned REAL nodes
```cypher
MATCH (f:FILE)
WHERE f.entity_id STARTS WITH 'file_'
WITH f, size([(f)-[]-() | 1]) as rel_count
WHERE rel_count = 0
RETURN count(*) as orphaned_count
```

### Compare property completeness
```cypher
MATCH (f:FILE)
WITH f.entity_id STARTS WITH 'file_' as is_real,
     size(keys(f)) as props
RETURN is_real, AVG(props) as avg_properties, count(*) as nodes
```

---

## Best Practices

### DO ✅
- Use `file_<hash>` format for all REAL indexed files
- Use `entity_<hash1>_<hash2>` for all semantic entities
- Lookup existing nodes before creating relationships
- Validate entity_id format before insertion

### DON'T ❌
- Mix entity_id formats within same node type
- Create PLACEHOLDERs when REAL node exists
- Assume entity_id format from node label alone
- Skip validation during relationship creation

---

## Quick Stats (as of 2025-11-09)

| Metric | Count | % |
|--------|-------|---|
| **REAL FILE nodes** | 343 | 29% of FILE |
| **PLACEHOLDER FILE nodes** | 842 | 71% of FILE |
| **Full Entity nodes** | 5,812 | 99.9% of Entity |
| **Stub Entity nodes** | 5 | 0.1% of Entity |
| **Orphaned REAL FILES** | 343 | **100% orphaned** |
| **Total relationships** | 2,552 | - |
| **Relationships to REAL FILES** | **0** | **0%** |

---

## Contact & Updates

**Report**: See `MEMGRAPH_SCHEMA_ANALYSIS_REPORT.md` for full analysis
**Scripts**:
- `scripts/analyze_entity_id_formats.py` - Format distribution
- `scripts/analyze_node_properties.py` - Property analysis
- `scripts/inspect_memgraph.py` - General inspection

**Last Updated**: 2025-11-09
