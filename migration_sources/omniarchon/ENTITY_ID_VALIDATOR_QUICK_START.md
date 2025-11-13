# Entity ID Validator - Quick Start Guide

**Quick reference for integrating entity_id validation into your code**

---

## Installation

```python
# Already installed - no additional dependencies needed
from utils.entity_id_validator import (
    EntityIDValidator,
    validate_file_entity_id,
    is_deprecated_format,
)
```

---

## Common Use Cases

### 1. Validate Before Creating Memgraph Relationships

```python
# File: services/intelligence/storage/memgraph_adapter.py

from utils.entity_id_validator import EntityIDValidator

async def create_relationship(
    self,
    source_id: str,
    target_id: str,
    relationship_type: str,
    properties: dict
):
    """Create relationship with entity_id validation."""

    # ✅ VALIDATE: Enforce format before creating relationship
    try:
        EntityIDValidator.validate_and_raise(source_id, "FILE")
        EntityIDValidator.validate_and_raise(target_id, "FILE")
    except ValueError as e:
        logger.error(
            "Invalid entity_id in relationship creation",
            extra={
                "source_id": source_id,
                "target_id": target_id,
                "error": str(e),
                "correlation_id": get_correlation_id()
            }
        )
        raise

    # Proceed with relationship creation
    query = """
    MATCH (source {entity_id: $source_id})
    MATCH (target {entity_id: $target_id})
    CREATE (source)-[r:%s]->(target)
    SET r = $properties
    RETURN r
    """ % relationship_type

    await self.execute(query, {
        "source_id": source_id,
        "target_id": target_id,
        "properties": properties
    })
```

---

### 2. Validate Entity IDs During Document Indexing

```python
# File: services/intelligence/src/services/document_processor.py

from utils.entity_id_validator import EntityIDValidator

async def index_document(self, document: DocumentModel):
    """Index document with entity_id validation."""

    # Generate entity_id
    entity_id = f"file_{document.blake3_hash[:12]}"

    # ✅ VALIDATE: Ensure entity_id is valid before indexing
    result = EntityIDValidator.validate_file_id(entity_id)
    if not result.is_valid:
        logger.error(
            "Generated invalid entity_id during indexing",
            extra={
                "entity_id": entity_id,
                "error": result.error_message,
                "detected_format": result.detected_format,
                "document_path": document.file_path
            }
        )
        raise ValueError(f"Invalid entity_id: {result.error_message}")

    # Proceed with indexing
    await self.memgraph.create_file_node({
        "entity_id": entity_id,
        "file_path": document.file_path,
        # ... other properties
    })
```

---

### 3. Detect and Reject Deprecated Entity IDs

```python
# File: services/intelligence/src/services/migration_helper.py

from utils.entity_id_validator import is_deprecated_format, is_placeholder_format

async def audit_entity_ids(self):
    """Audit database for deprecated entity_id formats."""

    deprecated_count = 0
    placeholder_count = 0

    # Query all FILE nodes
    query = "MATCH (f:FILE) RETURN f.entity_id AS entity_id"
    results = await self.memgraph.execute(query)

    for record in results:
        entity_id = record["entity_id"]

        # ✅ CHECK: Detect deprecated formats
        if is_deprecated_format(entity_id):
            deprecated_count += 1
            logger.warning(
                "Found deprecated path-based entity_id",
                extra={"entity_id": entity_id}
            )

        # ✅ CHECK: Detect placeholder formats
        if is_placeholder_format(entity_id):
            placeholder_count += 1
            logger.warning(
                "Found placeholder entity_id",
                extra={"entity_id": entity_id}
            )

    logger.info(
        "Entity ID audit complete",
        extra={
            "deprecated_count": deprecated_count,
            "placeholder_count": placeholder_count
        }
    )

    return {
        "deprecated": deprecated_count,
        "placeholders": placeholder_count
    }
```

---

### 4. Pydantic Model Validation

```python
# File: services/intelligence/src/models/graph_models.py

from pydantic import BaseModel, Field, field_validator
from utils.entity_id_validator import EntityIDValidator

class FileNodeModel(BaseModel):
    """Pydantic model for FILE node with validation."""

    entity_id: str = Field(..., description="File entity ID (hash-based)")
    file_path: str
    project_name: str
    blake3_hash: str

    @field_validator('entity_id')
    @classmethod
    def validate_entity_id(cls, value: str) -> str:
        """✅ VALIDATE: Entity ID must be hash-based format."""
        return EntityIDValidator.validate_and_raise(value, "FILE")

class EntityNodeModel(BaseModel):
    """Pydantic model for ENTITY node with validation."""

    entity_id: str = Field(..., description="Entity ID (hash-based or stub)")
    name: str
    entity_type: str

    @field_validator('entity_id')
    @classmethod
    def validate_entity_id(cls, value: str) -> str:
        """✅ VALIDATE: Entity ID must be valid format."""
        return EntityIDValidator.validate_and_raise(value, "ENTITY")

# Usage
file_node = FileNodeModel(
    entity_id="file_91f521860bc3",  # ✅ Valid
    file_path="/path/to/file.py",
    project_name="omniarchon",
    blake3_hash="91f521860bc3..."
)

# This will raise ValidationError
invalid_node = FileNodeModel(
    entity_id="file:omniarchon:asyncio",  # ❌ Invalid (deprecated)
    ...
)
```

---

### 5. Quick Validation in Scripts

```python
# File: scripts/validate_memgraph_entity_ids.py

from utils.entity_id_validator import validate_file_entity_id

def check_entity_id(entity_id: str) -> bool:
    """Quick validation check."""

    # ✅ VALIDATE: Boolean check
    if validate_file_entity_id(entity_id):
        print(f"✅ Valid: {entity_id}")
        return True
    else:
        print(f"❌ Invalid: {entity_id}")
        return False

# Check multiple IDs
entity_ids = [
    "file_91f521860bc3",           # ✅ Valid
    "file:omniarchon:asyncio",     # ❌ Deprecated
    "file_placeholder_abc",        # ❌ Placeholder
]

for entity_id in entity_ids:
    check_entity_id(entity_id)
```

---

### 6. Detailed Validation with Error Messages

```python
# File: services/intelligence/src/validators/pre_storage_validator.py

from utils.entity_id_validator import EntityIDValidator

def validate_and_log(entity_id: str, entity_type: str) -> bool:
    """Validate entity_id with detailed error logging."""

    # ✅ VALIDATE: Get detailed validation result
    result = EntityIDValidator.validate(entity_id, entity_type)

    if result.is_valid:
        logger.debug(
            "Entity ID validation passed",
            extra={
                "entity_id": entity_id,
                "entity_type": result.entity_type,
                "detected_format": result.detected_format
            }
        )
        return True
    else:
        logger.error(
            "Entity ID validation failed",
            extra={
                "entity_id": entity_id,
                "entity_type": result.entity_type,
                "error_message": result.error_message,
                "detected_format": result.detected_format
            }
        )
        return False

# Usage
if not validate_and_log("file:omniarchon:asyncio", "FILE"):
    # Log shows: "DEPRECATED: Path-based FILE entity_id ..."
    # Take corrective action
    pass
```

---

### 7. Migration Script Entity ID Checks

```python
# File: scripts/migrate_orphaned_relationships.py

from utils.entity_id_validator import EntityIDValidator, is_deprecated_format

async def migrate_relationship(placeholder_id: str, real_id: str):
    """Migrate relationship from placeholder to real node."""

    # ✅ VALIDATE: Ensure target ID is valid canonical format
    if is_deprecated_format(real_id):
        logger.error(
            "Cannot migrate to deprecated entity_id",
            extra={
                "placeholder_id": placeholder_id,
                "real_id": real_id
            }
        )
        return False

    # Validate real_id is hash-based
    result = EntityIDValidator.validate_file_id(real_id)
    if not result.is_valid:
        logger.error(
            "Target entity_id validation failed",
            extra={
                "placeholder_id": placeholder_id,
                "real_id": real_id,
                "error": result.error_message
            }
        )
        return False

    # Proceed with migration
    # ... migration logic
    return True
```

---

## Error Handling Patterns

### Pattern 1: Fail-Closed (Recommended for Production)

```python
def store_entity(entity_id: str, data: dict):
    """Fail-closed: Reject invalid entity_ids."""

    # Validate before storage
    EntityIDValidator.validate_and_raise(entity_id, "FILE")

    # If we get here, entity_id is valid
    db.store(entity_id, data)
```

### Pattern 2: Fail-Open with Logging (Use for Gradual Migration)

```python
def store_entity(entity_id: str, data: dict):
    """Fail-open: Log but allow invalid entity_ids during migration."""

    result = EntityIDValidator.validate_file_id(entity_id)

    if not result.is_valid:
        logger.warning(
            "Storing entity with invalid entity_id (migration mode)",
            extra={
                "entity_id": entity_id,
                "error": result.error_message
            }
        )
        # Increment metric
        validation_failures.labels(reason="invalid_format").inc()

    # Store regardless (migration mode)
    db.store(entity_id, data)
```

### Pattern 3: Validation with Fallback

```python
def get_or_create_entity_id(file_path: str, blake3_hash: str) -> str:
    """Generate entity_id with validation fallback."""

    # Generate entity_id
    entity_id = f"file_{blake3_hash[:12]}"

    # Validate
    result = EntityIDValidator.validate_file_id(entity_id)

    if not result.is_valid:
        # Fallback: regenerate with different method
        logger.error(
            "Generated invalid entity_id, using fallback",
            extra={
                "entity_id": entity_id,
                "error": result.error_message
            }
        )
        # Fallback method
        entity_id = f"file_{hashlib.sha256(file_path.encode()).hexdigest()[:12]}"

    return entity_id
```

---

## Testing Your Integration

### Unit Test Example

```python
# File: tests/unit/test_memgraph_adapter.py

import pytest
from utils.entity_id_validator import EntityIDValidator

def test_create_relationship_validates_entity_ids():
    """Test relationship creation validates entity_ids."""

    adapter = MemgraphAdapter()

    # Valid entity_ids - should succeed
    await adapter.create_relationship(
        source_id="file_91f521860bc3",
        target_id="file_a1b2c3d4e5f6",
        relationship_type="IMPORTS",
        properties={}
    )

    # Invalid entity_id - should raise ValueError
    with pytest.raises(ValueError, match="DEPRECATED"):
        await adapter.create_relationship(
            source_id="file:omniarchon:asyncio",  # ❌ Deprecated
            target_id="file_a1b2c3d4e5f6",
            relationship_type="IMPORTS",
            properties={}
        )
```

---

## Monitoring Integration

### Prometheus Metrics

```python
# File: services/intelligence/src/monitoring/entity_id_metrics.py

from prometheus_client import Counter

entity_id_validation_failures = Counter(
    'entity_id_validation_failures_total',
    'Total entity ID validation failures',
    ['entity_type', 'failure_reason']
)

def record_validation_failure(entity_id: str, entity_type: str, reason: str):
    """Record validation failure metric."""

    entity_id_validation_failures.labels(
        entity_type=entity_type,
        failure_reason=reason
    ).inc()

    logger.error(
        "Entity ID validation failed",
        extra={
            "entity_id": entity_id,
            "entity_type": entity_type,
            "reason": reason
        }
    )

# Usage in validation code
result = EntityIDValidator.validate(entity_id, "FILE")
if not result.is_valid:
    record_validation_failure(
        entity_id,
        "FILE",
        result.detected_format or "unknown"
    )
```

---

## Common Mistakes to Avoid

### ❌ Don't: Skip validation

```python
# ❌ BAD: No validation
entity_id = f"file:{project}:{file_path}"  # Deprecated format!
await memgraph.create_relationship(source_id, target_id, ...)
```

### ✅ Do: Always validate

```python
# ✅ GOOD: Validate before use
entity_id = f"file_{blake3_hash[:12]}"
EntityIDValidator.validate_and_raise(entity_id, "FILE")
await memgraph.create_relationship(source_id, target_id, ...)
```

---

### ❌ Don't: Ignore validation results

```python
# ❌ BAD: Validate but don't check result
result = EntityIDValidator.validate(entity_id, "FILE")
# Continue without checking result.is_valid
await store_entity(entity_id, data)
```

### ✅ Do: Check and handle validation failures

```python
# ✅ GOOD: Check result and handle errors
result = EntityIDValidator.validate(entity_id, "FILE")
if not result.is_valid:
    logger.error(f"Invalid entity_id: {result.error_message}")
    raise ValueError(result.error_message)
await store_entity(entity_id, data)
```

---

### ❌ Don't: Use path-based entity_ids

```python
# ❌ BAD: Path-based entity_id
entity_id = f"file:{project_name}:{file_path}"
```

### ✅ Do: Use hash-based entity_ids

```python
# ✅ GOOD: Hash-based entity_id
from blake3 import blake3

content_hash = blake3(file_content.encode()).hexdigest()
entity_id = f"file_{content_hash[:12]}"
```

---

## Quick Reference

### Import Statements

```python
# Comprehensive validation
from utils.entity_id_validator import EntityIDValidator

# Quick boolean checks
from utils.entity_id_validator import (
    validate_file_entity_id,
    validate_entity_entity_id,
)

# Format detection
from utils.entity_id_validator import (
    is_deprecated_format,
    is_placeholder_format,
)

# Structured result
from utils.entity_id_validator import ValidationResult
```

### Validation Methods

| Method | Use Case | Returns |
|--------|----------|---------|
| `EntityIDValidator.validate(id, type)` | Comprehensive validation | `ValidationResult` |
| `EntityIDValidator.validate_and_raise(id, type)` | Pydantic validators | `str` or raises `ValueError` |
| `validate_file_entity_id(id)` | Quick FILE check | `bool` |
| `validate_entity_entity_id(id)` | Quick ENTITY check | `bool` |
| `is_deprecated_format(id)` | Detect deprecated | `bool` |
| `is_placeholder_format(id)` | Detect placeholder | `bool` |

---

## Support

**Documentation**:
- `ENTITY_ID_VALIDATOR_IMPLEMENTATION.md` - Full implementation details
- `ENTITY_ID_FORMAT_REFERENCE.md` - Format specifications
- `ENTITY_ID_SCHEMA_FIX_STRATEGY.md` - Migration strategy

**Code**:
- `services/intelligence/src/utils/entity_id_validator.py` - Validator implementation
- `services/intelligence/tests/unit/utils/test_entity_id_validator.py` - Test examples

**Questions?** Check the test file for 87 comprehensive examples of valid and invalid entity_ids.

---

**Quick Start Guide Version**: 1.0
**Last Updated**: 2025-11-09
