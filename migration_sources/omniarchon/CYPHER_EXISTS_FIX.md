# Cypher EXISTS Syntax Fix

**Date**: 2025-11-12
**Issue**: "Unbounded variables are not allowed in exists!" error in Memgraph
**Status**: ✅ RESOLVED

## Problem

Memgraph Cypher implementation differs from Neo4j in how it handles pattern matching in WHERE clauses:

### ❌ Invalid Syntax (caused errors)

```cypher
MATCH (n:File)
WHERE EXISTS((p:Project {name: $project_name})-[:CONTAINS]->(n))
-- Error: Unbounded variables not allowed (p is not matched)

MATCH (n:File)
WHERE (p:Project {name: $project_name})-[:CONTAINS]->(n)
-- Error: Not yet implemented: atom expression pattern matching
```

### ✅ Valid Syntax (Memgraph-compatible)

```cypher
-- Approach 1: OPTIONAL MATCH with path variable
MATCH (n:File)
OPTIONAL MATCH project_path = (:Project {name: $project_name})-[:CONTAINS*]->(n)
WHERE project_path IS NOT NULL

-- Approach 2: Match both variables first, then check relationship
MATCH (p:Project {name: $project_name})
MATCH (n:File)
WHERE (p)-[:CONTAINS*]->(n)

-- Approach 3: Check with already-bound variables
MATCH (f:File)
WHERE NOT (()-[:CONTAINS]->(f))  -- Works when f is already bound
```

## Key Rules for Memgraph

1. **All variables in WHERE patterns must be bound** - You cannot introduce new variables in WHERE clause patterns
2. **Pattern expressions not supported in WHERE** - `WHERE (p)-[:REL]->(n)` doesn't work as boolean even if both are bound
3. **Use OPTIONAL MATCH + IS NOT NULL** - This is the Memgraph-compatible way to check pattern existence
4. **EXISTS syntax varies by version** - Older Memgraph doesn't support `EXISTS { MATCH ... }` subqueries

## Files Fixed

### 1. services/intelligence/src/api/knowledge_graph/service.py

**Before** (line 182):
```python
where_conditions.append(
    "(NOT n:File OR EXISTS((p:Project {name: $project_name})-[:CONTAINS]->(n)))"
)
```

**After** (lines 171-180):
```python
# Add project filter using OPTIONAL MATCH
if project_name:
    parameters["project_name"] = project_name
    query_parts.append(
        "OPTIONAL MATCH project_path = (:Project {name: $project_name})-[:CONTAINS*]->(n)"
    )
    where_conditions.append("(NOT n:File OR project_path IS NOT NULL)")
```

## Generated Query Examples

### With Project Filter
```cypher
MATCH (n)
OPTIONAL MATCH project_path = (:Project {name: $project_name})-[:CONTAINS*]->(n)
WHERE (NOT n:File OR project_path IS NOT NULL)
WITH n LIMIT $limit
OPTIONAL MATCH (n)-[r]->(m)
RETURN ...
```

### Without Project Filter
```cypher
MATCH (n)
WITH n LIMIT $limit
OPTIONAL MATCH (n)-[r]->(m)
RETURN ...
```

## Testing

### Verification Query
```bash
python3 -c "
import asyncio
from neo4j import AsyncGraphDatabase

async def test():
    driver = AsyncGraphDatabase.driver('bolt://localhost:7687')
    async with driver.session() as session:
        result = await session.run('''
            MATCH (n)
            OPTIONAL MATCH project_path = (:Project {name: \$project_name})-[:CONTAINS*]->(n)
            WHERE (NOT n:File OR project_path IS NOT NULL)
            WITH n LIMIT \$limit
            RETURN count(n) as count
        ''', project_name='omniarchon', limit=10)
        record = await result.single()
        print(f'Count: {record[\"count\"]}')
    await driver.close()

asyncio.run(test())
"
```

Expected: ✅ No syntax errors, returns count

### 2. scripts/verify_environment.py

**Before** (line 473):
```python
orphaned_files = session.run("""
    MATCH (f:File)
    WHERE NOT (f)<-[:CONTAINS*]-(:PROJECT)
      AND (f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/')
    RETURN count(f) as count
""")
```

**After** (lines 473-480):
```python
orphaned_files = session.run("""
    MATCH (f:File)
    WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
    OPTIONAL MATCH path = (f)<-[:CONTAINS*]-(:PROJECT)
    WITH f, path
    WHERE path IS NULL
    RETURN count(f) as count
""")
```

### 3. services/intelligence/src/services/orphan_detector.py

**Fixed two queries** (lines 220-230 and 349-359):
- Removed `WHERE NOT (file)<-[:IMPORTS]-()`
- Changed to `OPTIONAL MATCH import_path = (file)<-[:IMPORTS]-()` + `WHERE import_path IS NULL`
- Also fixed compound pattern check for dead code detection

### 4. tests/e2e/test_ingestion_pipeline.py

**Before** (line 386):
```python
WHERE NOT (()-[:CONTAINS]->(f))
```

**After** (lines 386-388):
```python
OPTIONAL MATCH contains_path = ()-[:CONTAINS]->(f)
WITH f, contains_path
WHERE contains_path IS NULL
```

### 5. tests/integration/test_e2e_file_indexing.py

**Before** (line 180):
```python
WHERE NOT (f)-[:IMPORTS]->() AND NOT ()-[:IMPORTS]->(f)
```

**After** (lines 180-183):
```python
OPTIONAL MATCH outgoing = (f)-[:IMPORTS]->()
OPTIONAL MATCH incoming = ()-[:IMPORTS]->(f)
WITH f, outgoing, incoming
WHERE outgoing IS NULL AND incoming IS NULL
```

### 6. tests/integration/test_large_repository.py

**Same fix as test_e2e_file_indexing.py** (lines 223-226)

## Other Files Checked

These files were verified and found to be OK (no unbounded variables or pattern expressions):

- `scripts/build_directory_tree.py` - Proper orphan detection with OPTIONAL MATCH
- `scripts/quick_fix_tree.py` - Matches both nodes before checking relationship
- `tests/integration/test_project_name_propagation.py` - Both nodes bound before WHERE

## References

- Memgraph Cypher documentation: https://memgraph.com/docs/cypher-manual
- Original issue: Tree building verification queries failing with "Unbounded variables" error
- Related fix: TREE_BUILDING_IMPORT_FIX.md (previous EXISTS syntax fixes)
