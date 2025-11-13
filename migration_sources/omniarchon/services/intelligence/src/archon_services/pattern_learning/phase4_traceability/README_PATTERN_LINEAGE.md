# Pattern Lineage Tracker - ONEX Effect Node

**Track 3 Phase 4 - Pattern Traceability**

Track pattern ancestry and evolution over time with complete lineage graphs stored in PostgreSQL.

## Overview

The Pattern Lineage Tracker is an ONEX Effect Node that provides comprehensive tracking of pattern evolution, relationships, and usage across the pattern learning system. It maintains a complete directed acyclic graph (DAG) of pattern lineage, enabling:

- **Ancestry Tracking**: Full lineage from any pattern back to its roots
- **Evolution Monitoring**: Track how patterns change and improve over time
- **Relationship Mapping**: Understand dependencies and derivations
- **Usage Analytics**: Track when and where patterns are applied
- **Deprecation Management**: Handle pattern lifecycle including deprecation

## Architecture

### ONEX Compliance

- **Node Type**: Effect (External I/O, database operations)
- **Naming**: `NodePatternLineageTrackerEffect`
- **File Pattern**: `node_pattern_lineage_tracker_effect.py`
- **Method Signature**: `async def execute_effect(self, contract: ModelPatternLineageInput) -> ModelResult`

### Database Schema

Four main tables form the lineage graph:

1. **`pattern_lineage_nodes`** - Pattern instances with version snapshots
2. **`pattern_lineage_edges`** - Directed relationships between patterns
3. **`pattern_lineage_events`** - Complete event log for audit trail
4. **`pattern_ancestry_cache`** - Materialized paths for fast queries

### Performance Targets

- **Event Tracking**: <50ms per operation
- **Ancestry Query**: <200ms for depth up to 10 generations
- **Graph Traversal**: <300ms for complex relationships

## Quick Start

### 1. Database Setup

```bash
# Initialize the schema
psql -U postgres -d omninode_bridge -f schema_pattern_lineage.sql

# Verify tables created
psql -U postgres -d omninode_bridge -c "\dt pattern_lineage*"
```

### 2. Basic Usage

```python
import asyncio
import asyncpg
from pattern_learning.phase4_traceability import (
    NodePatternLineageTrackerEffect,
    ModelPatternLineageInput,
    LineageEventType,
    EdgeType,
    TransformationType
)

async def main():
    # Create connection pool
    pool = await asyncpg.create_pool(
        "postgresql://postgres:password@localhost:5436/omninode_bridge"
    )

    # Create lineage tracker
    tracker = NodePatternLineageTrackerEffect(pool)

    # Track pattern creation
    contract = ModelPatternLineageInput(
        operation="track_creation",
        event_type=LineageEventType.PATTERN_CREATED,
        pattern_id="async_db_writer_v1",
        pattern_name="AsyncDatabaseWriter",
        pattern_type="code",
        pattern_version="1.0.0",
        pattern_data={
            "template_code": "async def execute_effect(self, contract): ...",
            "language": "python",
            "framework": "onex"
        },
        triggered_by="pattern_extraction_system"
    )

    result = await tracker.execute_effect(contract)
    print(f"Success: {result.success}")
    print(f"Lineage ID: {result.data['lineage_id']}")
    print(f"Duration: {result.metadata['duration_ms']}ms")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Core Operations

### 1. Track Pattern Creation

Record when a new pattern is created (root of lineage).

```python
contract = ModelPatternLineageInput(
    operation="track_creation",
    event_type=LineageEventType.PATTERN_CREATED,
    pattern_id="unique_pattern_id",
    pattern_name="PatternName",
    pattern_type="code",  # code, config, template, workflow
    pattern_version="1.0.0",
    pattern_data={
        "template_code": "...",
        "language": "python",
        "category": "async_io"
    },
    triggered_by="ai_assistant",
    reason="Extracted from production codebase"
)

result = await tracker.execute_effect(contract)
```

**Returns**:
- `lineage_id`: UUID identifying the lineage family
- `pattern_node_id`: UUID of this specific pattern version
- `event_id`: UUID of the creation event
- `created_at`: ISO timestamp

### 2. Track Pattern Modification

Record when a pattern is modified, creating a new version.

```python
contract = ModelPatternLineageInput(
    operation="track_modification",
    event_type=LineageEventType.PATTERN_MODIFIED,
    pattern_id="pattern_v2",
    pattern_name="ImprovedPattern",
    pattern_type="code",
    pattern_version="2.0.0",
    pattern_data={
        "template_code": "...",  # Updated code
        "enhancements": ["retry_logic", "error_handling"]
    },
    parent_pattern_ids=["pattern_v1"],  # Reference to parent
    edge_type=EdgeType.MODIFIED_FROM,
    transformation_type=TransformationType.ENHANCEMENT,
    triggered_by="ai_assistant",
    reason="Added retry logic and better error handling"
)

result = await tracker.execute_effect(contract)
```

**Returns**:
- All creation fields plus:
- `parent_node_ids`: List of parent node UUIDs
- `generation`: Generation number in lineage (e.g., 2 for child of root)

### 3. Track Pattern Merge

Record when multiple patterns are combined into one.

```python
contract = ModelPatternLineageInput(
    operation="track_merge",
    event_type=LineageEventType.PATTERN_MERGED,
    pattern_id="unified_pattern",
    pattern_name="UnifiedDatabaseWriter",
    pattern_type="code",
    pattern_version="1.0.0",
    pattern_data={
        "template_code": "...",  # Merged code
        "merged_features": ["async_support", "sync_support"]
    },
    parent_pattern_ids=["async_writer_v2", "sync_writer_v1"],  # Multiple parents
    edge_type=EdgeType.MERGED_FROM,
    transformation_type=TransformationType.MERGE,
    triggered_by="refactoring_system",
    reason="Unified async and sync database writers"
)

result = await tracker.execute_effect(contract)
```

**Returns**:
- All modification fields plus:
- `parent_count`: Number of parent patterns merged

### 4. Track Pattern Application

Record when a pattern is actually used in execution.

```python
contract = ModelPatternLineageInput(
    operation="track_application",
    event_type=LineageEventType.PATTERN_APPLIED,
    pattern_id="async_db_writer_v2",
    pattern_data={
        "execution_context": "production",
        "use_case": "user_registration_flow"
    },
    metadata={
        "execution_time_ms": 42,
        "success": True
    },
    triggered_by="runtime_system",
    reason="Applied in user registration feature"
)

result = await tracker.execute_effect(contract)
```

**Returns**:
- `event_id`: UUID of application event
- `pattern_node_id`: UUID of applied pattern version
- `timestamp`: When pattern was applied

### 5. Track Pattern Deprecation

Record when a pattern is deprecated and should no longer be used.

```python
contract = ModelPatternLineageInput(
    operation="track_deprecation",
    event_type=LineageEventType.PATTERN_DEPRECATED,
    pattern_id="old_pattern_v1",
    triggered_by="maintenance_system",
    reason="Replaced by more efficient v3 implementation"
)

result = await tracker.execute_effect(contract)
```

**Returns**:
- `event_id`: UUID of deprecation event
- `deprecated`: Boolean (always True)
- `timestamp`: When pattern was deprecated

### 6. Query Pattern Ancestry

Retrieve complete ancestry chain for a pattern.

```python
contract = ModelPatternLineageInput(
    operation="query_ancestry",
    pattern_id="current_pattern_v5"
)

result = await tracker.execute_effect(contract)

# Access ancestry data
print(f"Ancestry depth: {result.data['ancestry_depth']}")
print(f"Total ancestors: {result.data['total_ancestors']}")

for ancestor in result.data['ancestors']:
    print(f"  {ancestor['ancestor_pattern_id']} (gen {ancestor['generation']})")
    print(f"    Edge: {ancestor['edge_type']}")
    print(f"    Created: {ancestor['created_at']}")
```

**Returns**:
- `ancestors`: List of ancestor records (oldest to newest)
- `ancestry_depth`: Number of generations from root
- `total_ancestors`: Total count excluding self
- `lineage_id`: UUID of lineage family

### 7. Query Pattern Descendants

Retrieve all direct descendants of a pattern.

```python
contract = ModelPatternLineageInput(
    operation="query_descendants",
    pattern_id="parent_pattern"
)

result = await tracker.execute_effect(contract)

# Access descendants data
print(f"Total descendants: {result.data['total_descendants']}")

for descendant in result.data['descendants']:
    print(f"  {descendant['descendant_pattern_id']}")
    print(f"    Relationship: {descendant['edge_type']}")
    print(f"    Transformation: {descendant['transformation_type']}")
```

**Returns**:
- `descendants`: List of descendant records
- `total_descendants`: Total count

## Event Types

### LineageEventType Enumeration

```python
class LineageEventType(str, Enum):
    PATTERN_CREATED = "pattern_created"       # New pattern registered
    PATTERN_MODIFIED = "pattern_modified"     # Existing pattern updated
    PATTERN_MERGED = "pattern_merged"         # Multiple patterns combined
    PATTERN_APPLIED = "pattern_applied"       # Pattern used in execution
    PATTERN_DEPRECATED = "pattern_deprecated" # Pattern marked obsolete
    PATTERN_FORKED = "pattern_forked"        # Pattern branched into variant
    PATTERN_VALIDATED = "pattern_validated"   # Pattern passed validation
```

## Edge Types

### EdgeType Enumeration

Defines relationships between patterns in the lineage graph:

```python
class EdgeType(str, Enum):
    DERIVED_FROM = "derived_from"       # Target derived from source
    MODIFIED_FROM = "modified_from"     # Target is modification of source
    MERGED_FROM = "merged_from"         # Target merged from source
    REPLACED_BY = "replaced_by"         # Source replaced by target
    INSPIRED_BY = "inspired_by"         # Target inspired by source
    DEPRECATED_BY = "deprecated_by"     # Source deprecated by target
```

## Transformation Types

### TransformationType Enumeration

Categorizes the type of change applied:

```python
class TransformationType(str, Enum):
    REFACTOR = "refactor"               # Code restructuring
    ENHANCEMENT = "enhancement"         # Feature addition
    BUGFIX = "bugfix"                  # Bug correction
    MERGE = "merge"                    # Pattern combination
    OPTIMIZATION = "optimization"       # Performance improvement
    SIMPLIFICATION = "simplification"   # Complexity reduction
```

## Advanced Usage

### Complete Lineage Example

Track a pattern from creation through multiple modifications:

```python
async def track_pattern_evolution():
    tracker = NodePatternLineageTrackerEffect(pool)

    # 1. Create root pattern
    create_result = await tracker.execute_effect(
        ModelPatternLineageInput(
            operation="track_creation",
            pattern_id="db_writer_v1",
            pattern_name="BasicDatabaseWriter",
            pattern_version="1.0.0",
            pattern_data={"code": "basic implementation"}
        )
    )

    # 2. Enhance with error handling
    enhance_result = await tracker.execute_effect(
        ModelPatternLineageInput(
            operation="track_modification",
            pattern_id="db_writer_v2",
            pattern_version="2.0.0",
            pattern_data={"code": "with error handling"},
            parent_pattern_ids=["db_writer_v1"],
            edge_type=EdgeType.MODIFIED_FROM,
            transformation_type=TransformationType.ENHANCEMENT
        )
    )

    # 3. Add async support
    async_result = await tracker.execute_effect(
        ModelPatternLineageInput(
            operation="track_modification",
            pattern_id="db_writer_v3",
            pattern_version="3.0.0",
            pattern_data={"code": "async with error handling"},
            parent_pattern_ids=["db_writer_v2"],
            edge_type=EdgeType.MODIFIED_FROM,
            transformation_type=TransformationType.ENHANCEMENT
        )
    )

    # 4. Query full ancestry
    ancestry_result = await tracker.execute_effect(
        ModelPatternLineageInput(
            operation="query_ancestry",
            pattern_id="db_writer_v3"
        )
    )

    # Ancestry should show: v3 -> v2 -> v1
    assert ancestry_result.data["ancestry_depth"] == 2
    assert len(ancestry_result.data["ancestors"]) == 3
```

### Pattern Merge Example

Combine multiple patterns into a unified implementation:

```python
async def track_pattern_merge():
    tracker = NodePatternLineageTrackerEffect(pool)

    # Create two independent patterns
    await tracker.execute_effect(
        ModelPatternLineageInput(
            operation="track_creation",
            pattern_id="async_writer",
            pattern_data={"type": "async"}
        )
    )

    await tracker.execute_effect(
        ModelPatternLineageInput(
            operation="track_creation",
            pattern_id="sync_writer",
            pattern_data={"type": "sync"}
        )
    )

    # Merge them
    merge_result = await tracker.execute_effect(
        ModelPatternLineageInput(
            operation="track_merge",
            pattern_id="unified_writer",
            pattern_data={"type": "unified"},
            parent_pattern_ids=["async_writer", "sync_writer"],
            edge_type=EdgeType.MERGED_FROM,
            transformation_type=TransformationType.MERGE
        )
    )

    # Query descendants of each parent
    async_descendants = await tracker.execute_effect(
        ModelPatternLineageInput(
            operation="query_descendants",
            pattern_id="async_writer"
        )
    )

    # Both parents should have unified_writer as descendant
    assert async_descendants.data["total_descendants"] == 1
```

## Database Schema

### Pattern Lineage Nodes

```sql
CREATE TABLE pattern_lineage_nodes (
    id UUID PRIMARY KEY,
    pattern_id VARCHAR(255) NOT NULL,
    pattern_name VARCHAR(255) NOT NULL,
    pattern_type VARCHAR(100) NOT NULL,
    pattern_version VARCHAR(50) NOT NULL,
    lineage_id UUID NOT NULL,
    generation INTEGER NOT NULL,
    pattern_data JSONB NOT NULL,
    metadata JSONB,
    correlation_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Pattern Lineage Edges

```sql
CREATE TABLE pattern_lineage_edges (
    id UUID PRIMARY KEY,
    source_node_id UUID NOT NULL REFERENCES pattern_lineage_nodes(id),
    target_node_id UUID NOT NULL REFERENCES pattern_lineage_nodes(id),
    edge_type VARCHAR(100) NOT NULL,
    transformation_type VARCHAR(100),
    edge_weight FLOAT DEFAULT 1.0,
    metadata JSONB,
    correlation_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Utility Functions

The schema includes PostgreSQL functions for common queries:

```sql
-- Get full ancestry chain
SELECT * FROM get_pattern_ancestry('pattern_node_uuid');

-- Get direct descendants
SELECT * FROM get_pattern_descendants('pattern_node_uuid');

-- Invalidate ancestry cache
SELECT invalidate_ancestry_cache('pattern_node_uuid');
```

## Performance Optimization

### Ancestry Cache

The system maintains a materialized `pattern_ancestry_cache` table for fast queries:

```sql
SELECT
    pattern_id,
    ancestry_depth,
    total_ancestors,
    ancestor_ids,
    ancestor_pattern_ids
FROM pattern_ancestry_cache
WHERE pattern_node_id = $1;
```

**Benefits**:
- <200ms ancestry queries even for deep lineages
- Automatic invalidation on lineage changes
- Periodic rebuild for staleness management

### Indexes

Optimized indexes for fast graph traversal:

- `idx_lineage_nodes_pattern_id` - Find latest version of pattern
- `idx_lineage_edges_bidirectional` - Traverse relationships
- `idx_lineage_events_pattern_id` - Query event history
- `idx_ancestry_cache_ancestors` - Fast ancestry lookups (GIN)

## Testing

### Run Tests

```bash
# From repository root
cd /Volumes/PRO-G40/Code/omniarchon
pytest services/intelligence/tests/unit/pattern_learning/phase4_traceability/test_pattern_lineage_tracker.py -v

# With coverage
pytest services/intelligence/tests/unit/pattern_learning/phase4_traceability/test_pattern_lineage_tracker.py \
    --cov=services/intelligence/src/archon_services/pattern_learning/phase4_traceability \
    --cov-report=html
```

### Test Coverage

The test suite includes:

- ✅ Unit tests for each operation handler
- ✅ Integration tests with PostgreSQL
- ✅ Performance tests (<50ms, <200ms targets)
- ✅ Error handling tests
- ✅ Edge case tests (duplicate patterns, missing parents, etc.)
- ✅ Full lifecycle integration tests

**Target**: >90% code coverage

### Manual Testing

```bash
# Run example usage
python -m src.services.pattern_learning.phase4_traceability.node_pattern_lineage_tracker_effect
```

## Error Handling

The Effect node returns `ModelResult` with comprehensive error information:

```python
result = await tracker.execute_effect(contract)

if not result.success:
    print(f"Error: {result.error}")
    print(f"Error Type: {result.metadata.get('error_type')}")
    print(f"Duration: {result.metadata.get('duration_ms')}ms")

    # Common error types:
    # - unique_violation: Pattern already exists
    # - foreign_key_violation: Parent pattern not found
    # - validation_error: Missing required fields
```

## Integration with Pattern Learning

The lineage tracker integrates with other Track 3 components:

- **Phase 1 (Foundation)**: Stores patterns that are tracked
- **Phase 2 (Matching)**: Tracks when patterns are matched and applied
- **Phase 3 (Validation)**: Records validation results in lineage
- **Phase 4 (Analytics)**: Provides data for usage analytics

## API Reference

### Core Classes

- **`NodePatternLineageTrackerEffect`**: Main Effect node
- **`ModelPatternLineageInput`**: Input contract
- **`ModelPatternLineageOutput`**: Output contract
- **`ModelResult`**: Standard result format

### Enumerations

- **`LineageEventType`**: Event type classification
- **`EdgeType`**: Relationship type between patterns
- **`TransformationType`**: Type of change applied

### Result Models

- **`ModelAncestorRecord`**: Single ancestor in chain
- **`ModelDescendantRecord`**: Single descendant
- **`ModelLineageGraph`**: Complete lineage graph

## Best Practices

### 1. Use Semantic Versioning

```python
pattern_version="2.1.3"  # MAJOR.MINOR.PATCH
```

### 2. Provide Meaningful Reasons

```python
reason="Added connection pooling to improve performance by 40%"
```

### 3. Track All Pattern Usage

```python
# Always track when patterns are applied
await tracker.execute_effect(
    ModelPatternLineageInput(
        operation="track_application",
        pattern_id=pattern_id,
        metadata={"context": "production", "success": True}
    )
)
```

### 4. Use Correlation IDs

```python
correlation_id = uuid4()

# Use same correlation ID for related operations
create_contract = ModelPatternLineageInput(
    correlation_id=correlation_id,
    ...
)

modify_contract = ModelPatternLineageInput(
    correlation_id=correlation_id,  # Same ID
    ...
)
```

### 5. Query Before Deprecating

```python
# Check descendants before deprecating
descendants = await tracker.execute_effect(
    ModelPatternLineageInput(
        operation="query_descendants",
        pattern_id=pattern_to_deprecate
    )
)

if descendants.data["total_descendants"] > 0:
    print(f"Warning: {descendants.data['total_descendants']} patterns depend on this")
```

## Troubleshooting

### Common Issues

**Issue**: "Pattern not found" when querying
```python
# Solution: Ensure pattern_id matches exactly
# Pattern IDs are case-sensitive
```

**Issue**: "Unique violation" on creation
```python
# Solution: Pattern with same ID and version already exists
# Use different version number or pattern_id
```

**Issue**: Slow ancestry queries
```python
# Solution: Rebuild ancestry cache
await conn.execute("SELECT invalidate_ancestry_cache($1)", pattern_node_id)
# Cache will rebuild on next query
```

## Future Enhancements

- [ ] Lineage visualization API
- [ ] Pattern similarity based on lineage
- [ ] Automated pattern deprecation suggestions
- [ ] Lineage-based pattern recommendations
- [ ] Export lineage to GraphML/DOT formats

## License

Part of Archon Intelligence Service - Track 3 Pattern Learning System

## Support

For issues or questions:
1. Check test suite for examples
2. Review schema documentation
3. Consult ONEX architecture patterns
4. Open issue in Archon repository
