# Quick Reference: Add Missing DEBUG Logging

**File**: `services/intelligence/storage/memgraph_adapter.py`

---

## 📝 Copy-Paste Code Snippets

### 1. FILE Node - Entry Logging (Add after line 163, before line 164)
```python
        logger.debug(
            f"🔍 [ENTITY_CREATION] create_file_node called: entity_id={file_data.get('entity_id', 'MISSING')}, "
            f"name={file_data.get('name', 'MISSING')}, path={file_data.get('path', 'MISSING')}"
        )
```

### 2. FILE Node - Entity ID Validation (Add after line 173, replace existing validation)
```python
        # Validate entity_id format
        entity_id = file_data["entity_id"]
        is_valid = validate_file_entity_id(entity_id)
        logger.debug(
            f"✅ [VALIDATION] Entity ID validated: {entity_id}, is_valid={is_valid}"
        )
        if not is_valid:
            logger.error(
                f"❌ [VALIDATION] Invalid entity_id format: {entity_id} (expected hash-based)"
            )
```

### 3. FILE Node - CYPHER Log (Add before line 240, before session.run)
```python
                logger.debug(f"📝 [CYPHER] Executing query: MERGE (f:FILE {{entity_id: $entity_id}}) ...")
```

### 4. FILE Node - Success Log (Add after line 258, inside if record block)
```python
                    logger.debug(
                        f"✅ [NODE_CREATED] Successfully created FILE node: {record['file_id']}"
                    )
```

### 5. IMPORTS - Hash Resolver Logging (Replace lines 321-323)
```python
            # Generate hash-based entity IDs from file paths
            logger.debug(
                f"🔑 [HASH_RESOLVER] Generating entity_id for path={source_path}, project={project_name}"
            )
            source_id = generate_file_entity_id(source_path, project_name)
            logger.debug(
                f"🔑 [HASH_RESOLVER] Generating entity_id for path={source_path}, result={source_id}"
            )

            logger.debug(
                f"🔑 [HASH_RESOLVER] Generating entity_id for path={target_path}, project={project_name}"
            )
            target_id = generate_file_entity_id(target_path, project_name)
            logger.debug(
                f"🔑 [HASH_RESOLVER] Generating entity_id for path={target_path}, result={target_id}"
            )
```

### 6. IMPORTS - Validation Logging (Replace lines 325-333)
```python
            # Validate entity ID formats (prevent path-based IDs)
            source_valid = validate_file_entity_id(source_id)
            logger.debug(
                f"✅ [VALIDATION] Entity ID validated: {source_id}, is_valid={source_valid}"
            )
            if not source_valid:
                raise ValueError(
                    f"Invalid source entity_id format: '{source_id}' (expected hash-based)"
                )

            target_valid = validate_file_entity_id(target_id)
            logger.debug(
                f"✅ [VALIDATION] Entity ID validated: {target_id}, is_valid={target_valid}"
            )
            if not target_valid:
                raise ValueError(
                    f"Invalid target entity_id format: '{target_id}' (expected hash-based)"
                )
```

### 7. IMPORTS - CYPHER Log (Add before line 369, before session.run)
```python
                logger.debug(f"📝 [CYPHER] Executing query: MATCH (source:FILE) MATCH (target:FILE) MERGE (source)-[r:IMPORTS]->(target) ...")
```

### 8. Entity Storage - Entry Log (Add after line 461, in the entity loop)
```python
                            logger.debug(
                                f"🔍 [ENTITY_CREATION] store_entity called: entity_id={entity.entity_id}, type={entity.entity_type.value}"
                            )
```

### 9. Entity Storage - CYPHER Log (Add before line 513, before session.run)
```python
                            logger.debug(f"📝 [CYPHER] Executing query: MERGE (e:Entity {{entity_id: $entity_id}}) ...")
```

### 10. Entity Storage - Success Log (Add after line 532, inside if record block)
```python
                                logger.debug(
                                    f"✅ [NODE_CREATED] Successfully created Entity node: {entity.entity_id}"
                                )
```

---

## ⚡ Quick Command to Apply All Changes

Since the file keeps being modified, you may want to apply these changes manually. Here's the order:

1. Open `services/intelligence/storage/memgraph_adapter.py`
2. Search for each comment below and add the logging
3. Save and restart the service

### Search Terms:
- `async def create_file_node` → Add entry logging
- `missing_fields = [field for field` → Add validation after this
- `result = await session.run(query, params)` in create_file_node → Add CYPHER log before
- `f"✅ [FILE NODE] File node stored successfully` → Add NODE_CREATED log after
- `source_id = generate_file_entity_id(source_path` → Add hash resolver logs
- `if not validate_file_entity_id(source_id)` → Add validation logs
- `result = await session.run(query, params)` in create_file_import_relationship → Add CYPHER log before
- `for idx, entity in enumerate(batch_entities` → Add entry log after
- `result = await session.run(query, params)` in store_entities → Add CYPHER log before
- `f"✅ [MEMGRAPH STORAGE] Entity stored successfully` → Add NODE_CREATED log after

---

## 🧪 Test the Logging

After adding all logging points:

```bash
# 1. Restart intelligence service
docker compose restart archon-intelligence

# 2. Watch logs in real-time
docker logs -f archon-intelligence 2>&1 | grep -E "ENTITY_CREATION|HASH_RESOLVER|VALIDATION|CYPHER|NODE_CREATED"

# 3. In another terminal, trigger indexing
python3 scripts/bulk_ingest_repository.py /path/to/test/project --project-name test-logging

# 4. You should see output like:
# 🔍 [ENTITY_CREATION] create_file_node called: entity_id=file_abc123, name=test.py, path=test.py
# ✅ [VALIDATION] Entity ID validated: file_abc123, is_valid=True
# 📝 [CYPHER] Executing query: MERGE (f:FILE {entity_id: $entity_id}) ...
# 📊 [QUERY_RESULT] FILE node MERGE result | nodes_created=1 | properties_set=13 | labels_added=1
# ✅ [NODE_CREATED] Successfully created FILE node: file_abc123
```

---

## 🎯 What This Will Diagnose

| Issue | Logging Point | What It Shows |
|-------|---------------|---------------|
| **FILE nodes not being created** | 🔍 [ENTITY_CREATION] | Is create_file_node() being called at all? |
| **Invalid entity IDs** | ✅ [VALIDATION] | Are entity_ids hash-based or path-based? |
| **Hash generation failing** | 🔑 [HASH_RESOLVER] | Is hash generation producing valid blake3 hashes? |
| **Cypher query failing** | 📝 [CYPHER] | What exact query is being executed? |
| **Nodes not persisting** | 📊 [QUERY_RESULT] | Does nodes_created counter show 0 or 1? |
| **Success but no node** | ✅ [NODE_CREATED] | Does the method return success but node isn't in DB? |

---

## 📊 Expected Outcomes

### ✅ Healthy Logging Output
```
🔍 [ENTITY_CREATION] create_file_node called: entity_id=file_a1b2c3d4, name=app.py, path=src/app.py
✅ [VALIDATION] Entity ID validated: file_a1b2c3d4, is_valid=True
📝 [CYPHER] Executing query: MERGE (f:FILE {entity_id: $entity_id}) ...
📊 [QUERY_RESULT] FILE node MERGE result | nodes_created=1 | properties_set=13 | labels_added=1
✅ [NODE_CREATED] Successfully created FILE node: file_a1b2c3d4
```
**Interpretation**: Everything working correctly ✅

### ❌ Problem: Invalid Entity IDs
```
🔍 [ENTITY_CREATION] create_file_node called: entity_id=src/app.py, name=app.py, path=src/app.py
✅ [VALIDATION] Entity ID validated: src/app.py, is_valid=False
❌ [VALIDATION] Invalid entity_id format: src/app.py (expected hash-based)
```
**Interpretation**: Path-based entity IDs being used instead of hash-based ❌

### ❌ Problem: create_file_node() Not Being Called
```
(No 🔍 [ENTITY_CREATION] logs at all)
```
**Interpretation**: FILE node creation method is not being invoked ❌

### ❌ Problem: Nodes Not Persisting
```
🔍 [ENTITY_CREATION] create_file_node called: entity_id=file_a1b2c3d4, name=app.py, path=src/app.py
✅ [VALIDATION] Entity ID validated: file_a1b2c3d4, is_valid=True
📝 [CYPHER] Executing query: MERGE (f:FILE {entity_id: $entity_id}) ...
📊 [QUERY_RESULT] FILE node MERGE result | nodes_created=0 | properties_set=0 | labels_added=0
⚠️ [FILE NODE] MERGE returned no record
```
**Interpretation**: Query executes but doesn't create nodes (possible Memgraph issue) ❌

---

## 🔍 Debugging Commands

### Check FILE node count in Memgraph
```bash
docker exec archon-intelligence sh -c '
python3 << EOF
from neo4j import GraphDatabase
driver = GraphDatabase.driver("bolt://memgraph:7687")
with driver.session() as session:
    result = session.run("MATCH (f:FILE) RETURN count(f) as count")
    print(f"FILE nodes: {result.single()[\"count\"]}")
driver.close()
EOF
'
```

### Check IMPORTS relationship count
```bash
docker exec archon-intelligence sh -c '
python3 << EOF
from neo4j import GraphDatabase
driver = GraphDatabase.driver("bolt://memgraph:7687")
with driver.session() as session:
    result = session.run("MATCH ()-[r:IMPORTS]->() RETURN count(r) as count")
    print(f"IMPORTS relationships: {result.single()[\"count\"]}")
driver.close()
EOF
'
```

### View sample FILE nodes (if any exist)
```bash
docker exec archon-intelligence sh -c '
python3 << EOF
from neo4j import GraphDatabase
driver = GraphDatabase.driver("bolt://memgraph:7687")
with driver.session() as session:
    result = session.run("MATCH (f:FILE) RETURN f LIMIT 5")
    for record in result:
        print(f"FILE node: {dict(record[\"f\"])}")
driver.close()
EOF
'
```

---

## ✅ Completion Checklist

- [ ] Added 🔍 [ENTITY_CREATION] entry logging to create_file_node()
- [ ] Added ✅ [VALIDATION] entity ID validation logging to create_file_node()
- [ ] Added 📝 [CYPHER] query logging to create_file_node()
- [ ] Added ✅ [NODE_CREATED] success logging to create_file_node()
- [ ] Added 🔑 [HASH_RESOLVER] hash generation logging to create_file_import_relationship()
- [ ] Added ✅ [VALIDATION] entity ID validation logging to create_file_import_relationship()
- [ ] Added 📝 [CYPHER] query logging to create_file_import_relationship()
- [ ] Added 🔍 [ENTITY_CREATION] entry logging to store_entities()
- [ ] Added 📝 [CYPHER] query logging to store_entities()
- [ ] Added ✅ [NODE_CREATED] success logging to store_entities()
- [ ] Restarted archon-intelligence service
- [ ] Tested with small repository indexing
- [ ] Verified DEBUG logs are appearing
- [ ] Reviewed logs for errors/warnings
