# Memgraph Graph Effect Node

**ONEX Effect Node for Memgraph Graph Database Operations**

## Overview

The Memgraph Graph Effect Node (`NodeMemgraphGraphEffect`) is a production-ready ONEX Effect node that provides comprehensive graph database operations for storing and querying code entities and relationships in Memgraph.

## Key Features

✅ **Entity Management** - Create, update, and delete entity nodes with MERGE operations
✅ **Relationship Management** - Create typed relationships between entities
✅ **Batch Operations** - Bulk upsert with ACID transaction guarantees
✅ **Graph Queries** - Execute parameterized Cypher queries for pattern matching
✅ **Connection Pooling** - Efficient connection management with configurable pool size
✅ **Type Safety** - Strong typing with Pydantic models and mypy compliance
✅ **Retry Logic** - Automatic retry with exponential backoff
✅ **Observability** - Comprehensive metrics and logging

## Quick Start

```python
from omniintelligence.nodes.memgraph_graph_effect import (
    NodeMemgraphGraphEffect,
    ModelMemgraphGraphInput,
)
from omniintelligence.models import ModelEntity
from omniintelligence.enums import EnumEntityType
from uuid import uuid4

# Initialize
node = NodeMemgraphGraphEffect(container=None)
await node.initialize()

# Create entity
entity = ModelEntity(
    entity_id="ent_123",
    entity_type=EnumEntityType.CLASS,
    name="MyClass",
    metadata={"file_path": "src/main.py"},
)

input_data = ModelMemgraphGraphInput(
    operation="CREATE_ENTITY",
    entity=entity,
    correlation_id=uuid4(),
)

# Execute
output = await node.execute_effect(input_data)
print(f"Success: {output.success}")

# Cleanup
await node.shutdown()
```

## Operations

### CREATE_ENTITY
Create or update entity nodes with properties.

```python
ModelMemgraphGraphInput(
    operation="CREATE_ENTITY",
    entity=ModelEntity(...),
)
```

### CREATE_RELATIONSHIP
Create typed relationships between entities.

```python
ModelMemgraphGraphInput(
    operation="CREATE_RELATIONSHIP",
    relationship=ModelRelationship(...),
)
```

### BATCH_UPSERT
Bulk create/update nodes and relationships in a single transaction.

```python
ModelMemgraphGraphInput(
    operation="BATCH_UPSERT",
    entities=[...],
    relationships=[...],
)
```

### QUERY_GRAPH
Execute Cypher queries with parameters.

```python
ModelMemgraphGraphInput(
    operation="QUERY_GRAPH",
    query="MATCH (n) RETURN n LIMIT 10",
    query_params={},
)
```

### DELETE_ENTITY
Delete entity and all its relationships.

```python
ModelMemgraphGraphInput(
    operation="DELETE_ENTITY",
    entity_id="ent_123",
)
```

## Entity Types

Supports all code entity types from `EnumEntityType`:

- **Code**: CLASS, FUNCTION, MODULE, VARIABLE, CONSTANT, INTERFACE, TYPE
- **Project**: PROJECT, PACKAGE, FILE, DEPENDENCY
- **Documentation**: DOCUMENT, PATTERN, TEST, CONFIGURATION

## Relationship Types

Supports all relationship types from `EnumRelationshipType`:

- **Structural**: CONTAINS, DEFINES
- **Dependencies**: IMPORTS, DEPENDS_ON, USES, REFERENCES
- **Inheritance**: IMPLEMENTS, EXTENDS
- **Execution**: CALLS
- **Similarity**: MATCHES_PATTERN, SIMILAR_TO

## Configuration

Environment variables:

```bash
MEMGRAPH_URI="bolt://localhost:7687"
MEMGRAPH_HOST="localhost"
MEMGRAPH_PORT="7687"
MEMGRAPH_USER=""
MEMGRAPH_PASSWORD=""
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│         NodeMemgraphGraphEffect (Effect Node)           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │  execute_effect(input_data)                     │  │
│  │  - Validates input                              │  │
│  │  - Routes to operation handler                  │  │
│  │  - Returns ModelMemgraphGraphOutput             │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  Operation Handlers:                                    │
│  ┌─────────────────┐  ┌─────────────────────────┐    │
│  │ _create_entity  │  │ _create_relationship    │    │
│  │ (MERGE node)    │  │ (MERGE edge)            │    │
│  └─────────────────┘  └─────────────────────────┘    │
│                                                         │
│  ┌─────────────────┐  ┌─────────────────────────┐    │
│  │ _batch_upsert   │  │ _query_graph            │    │
│  │ (Transaction)   │  │ (Parameterized Cypher)  │    │
│  └─────────────────┘  └─────────────────────────┘    │
│                                                         │
│  ┌─────────────────┐                                   │
│  │ _delete_entity  │                                   │
│  │ (DETACH DELETE) │                                   │
│  └─────────────────┘                                   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │  Neo4j Bolt Driver (AsyncGraphDatabase)         │  │
│  │  - Connection pooling                           │  │
│  │  - Async operations                             │  │
│  │  - Transaction support                          │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
                        ▼
              ┌──────────────────┐
              │  Memgraph Server │
              │  (Bolt Protocol) │
              └──────────────────┘
```

## ONEX Compliance

✅ **Naming Convention**: `NodeMemgraphGraphEffect` (suffix-based)
✅ **Effect Pattern**: Implements `async execute_effect()` method
✅ **Strong Typing**: Pydantic models for input/output/config
✅ **Correlation ID**: Preserves correlation IDs for tracing
✅ **Error Handling**: Returns errors in output model
✅ **Lifecycle Management**: `initialize()` and `shutdown()` methods

## Testing

```bash
# Run tests
uv run pytest src/omniintelligence/nodes/memgraph_graph_effect/v1_0_0/test_effect.py -v

# Run with coverage
uv run pytest src/omniintelligence/nodes/memgraph_graph_effect/v1_0_0/test_effect.py --cov

# Type checking
uv run mypy src/omniintelligence/nodes/memgraph_graph_effect/v1_0_0/effect.py

# Linting
uv run ruff check src/omniintelligence/nodes/memgraph_graph_effect/
```

## Performance

- **Connection Pooling**: Configurable pool size (default: 50)
- **Batch Operations**: Transaction-based for ACID guarantees
- **Async Operations**: Non-blocking I/O with asyncio
- **Retry Logic**: Exponential backoff for transient failures

## Metrics

```python
metrics = node.get_metrics()
# Returns:
# - operations_executed: Total successful operations
# - operations_failed: Total failed operations
# - nodes_created: Total nodes created
# - nodes_updated: Total nodes updated
# - nodes_deleted: Total nodes deleted
# - relationships_created: Total relationships created
# - queries_executed: Total queries executed
# - avg_operation_time_ms: Average operation time
```

## Documentation

- [Usage Guide](v1_0_0/USAGE.md) - Comprehensive usage examples
- [Test Suite](v1_0_0/test_effect.py) - Full test coverage

## Dependencies

- `neo4j>=5.28.2` - Neo4j Bolt driver (Memgraph compatible)
- `pydantic>=2.0.0` - Data validation
- `omniintelligence.models` - Entity and relationship models
- `omniintelligence.enums` - Entity and relationship types

## Version

**v1.0.0** - Initial production release

## License

Part of the OmniIntelligence project.

## Support

For issues or questions, see the main project documentation.
