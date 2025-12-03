# Memgraph Graph Effect Node - Usage Guide

## Overview

The **Memgraph Graph Effect Node** (`NodeMemgraphGraphEffect`) is an ONEX Effect node that provides graph database operations for storing and querying entities and relationships in Memgraph.

## Features

- **Entity Management**: Create, update, and delete entity nodes
- **Relationship Management**: Create typed relationships between entities
- **Batch Operations**: Bulk upsert with transaction support
- **Graph Queries**: Execute parameterized Cypher queries
- **Connection Pooling**: Efficient connection management
- **Retry Logic**: Automatic retry with exponential backoff
- **Type Safety**: Strong typing with Pydantic models

## Installation

The node requires the `neo4j` Python driver (Memgraph uses the Bolt protocol):

```bash
# Already included in pyproject.toml
uv sync --group all
```

## Configuration

Set the following environment variables:

```bash
# Connection URI (defaults to bolt://localhost:7687)
export MEMGRAPH_URI="bolt://memgraph-host:7687"

# Or set host/port separately
export MEMGRAPH_HOST="localhost"
export MEMGRAPH_PORT="7687"

# Authentication (optional)
export MEMGRAPH_USER="your_username"
export MEMGRAPH_PASSWORD="your_password"
```

## Basic Usage

### 1. Initialize the Node

```python
from omniintelligence.nodes.memgraph_graph_effect import (
    NodeMemgraphGraphEffect,
    ModelMemgraphGraphConfig,
)

# Create configuration
config = ModelMemgraphGraphConfig(
    memgraph_uri="bolt://localhost:7687",
    memgraph_user="",
    memgraph_password="",
)

# Create and initialize node
node = NodeMemgraphGraphEffect(container=None, config=config)
await node.initialize()
```

### 2. Create Entity Nodes

```python
from uuid import uuid4
from omniintelligence.models import ModelEntity
from omniintelligence.enums import EnumEntityType
from omniintelligence.nodes.memgraph_graph_effect import (
    ModelMemgraphGraphInput,
)

# Create entity
entity = ModelEntity(
    entity_id="ent_class_123",
    entity_type=EnumEntityType.CLASS,
    name="UserService",
    metadata={
        "file_path": "src/services/user_service.py",
        "line_number": 42,
        "docstring": "Service for user operations",
    },
)

# Create entity in graph
input_data = ModelMemgraphGraphInput(
    operation="CREATE_ENTITY",
    entity=entity,
    correlation_id=uuid4(),
)

output = await node.execute_effect(input_data)
print(f"Success: {output.success}")
print(f"Nodes created: {output.nodes_created}")
```

### 3. Create Relationships

```python
from omniintelligence.models import ModelRelationship
from omniintelligence.enums import EnumRelationshipType

# Create relationship
relationship = ModelRelationship(
    source_id="ent_class_123",
    target_id="ent_function_456",
    relationship_type=EnumRelationshipType.CONTAINS,
    metadata={"access_level": "public"},
)

# Create relationship in graph
input_data = ModelMemgraphGraphInput(
    operation="CREATE_RELATIONSHIP",
    relationship=relationship,
    correlation_id=uuid4(),
)

output = await node.execute_effect(input_data)
print(f"Relationships created: {output.relationships_created}")
```

### 4. Batch Operations

```python
# Create multiple entities and relationships in one transaction
entities = [
    ModelEntity(
        entity_id="ent_1",
        entity_type=EnumEntityType.CLASS,
        name="Class1",
        metadata={},
    ),
    ModelEntity(
        entity_id="ent_2",
        entity_type=EnumEntityType.FUNCTION,
        name="function1",
        metadata={},
    ),
]

relationships = [
    ModelRelationship(
        source_id="ent_1",
        target_id="ent_2",
        relationship_type=EnumRelationshipType.CONTAINS,
        metadata={},
    ),
]

input_data = ModelMemgraphGraphInput(
    operation="BATCH_UPSERT",
    entities=entities,
    relationships=relationships,
    correlation_id=uuid4(),
)

output = await node.execute_effect(input_data)
print(f"Nodes created: {output.nodes_created}")
print(f"Relationships created: {output.relationships_created}")
```

### 5. Query the Graph

```python
# Execute Cypher query
input_data = ModelMemgraphGraphInput(
    operation="QUERY_GRAPH",
    query="""
        MATCH (c:CLASS)-[:CONTAINS]->(f:FUNCTION)
        WHERE c.name = $class_name
        RETURN f.name AS function_name, f.metadata AS metadata
        LIMIT 10
    """,
    query_params={"class_name": "UserService"},
    correlation_id=uuid4(),
)

output = await node.execute_effect(input_data)
if output.success:
    for result in output.query_results:
        print(f"Function: {result['function_name']}")
```

### 6. Delete Entities

```python
# Delete entity and all its relationships
input_data = ModelMemgraphGraphInput(
    operation="DELETE_ENTITY",
    entity_id="ent_class_123",
    correlation_id=uuid4(),
)

output = await node.execute_effect(input_data)
print(f"Nodes deleted: {output.nodes_deleted}")
```

### 7. Shutdown

```python
# Clean shutdown
await node.shutdown()
```

## Entity Types

The following entity types are supported (from `EnumEntityType`):

- **Code Entities**: `CLASS`, `FUNCTION`, `MODULE`, `VARIABLE`, `CONSTANT`, `INTERFACE`, `TYPE`
- **Project Entities**: `PROJECT`, `PACKAGE`, `FILE`, `DEPENDENCY`
- **Documentation**: `DOCUMENT`, `PATTERN`, `TEST`, `CONFIGURATION`

## Relationship Types

The following relationship types are supported (from `EnumRelationshipType`):

- **Structural**: `CONTAINS`, `DEFINES`
- **Dependencies**: `IMPORTS`, `DEPENDS_ON`, `USES`, `REFERENCES`
- **Inheritance**: `IMPLEMENTS`, `EXTENDS`
- **Execution**: `CALLS`
- **Similarity**: `MATCHES_PATTERN`, `SIMILAR_TO`

## Error Handling

The node handles errors gracefully:

```python
output = await node.execute_effect(input_data)

if not output.success:
    print(f"Operation failed: {output.error}")
    # Handle error appropriately
```

## Metrics

Retrieve operation metrics:

```python
metrics = node.get_metrics()
print(f"Operations executed: {metrics['operations_executed']}")
print(f"Nodes created: {metrics['nodes_created']}")
print(f"Relationships created: {metrics['relationships_created']}")
print(f"Average operation time: {metrics['avg_operation_time_ms']:.2f}ms")
```

## Advanced Usage

### Custom Connection Configuration

```python
config = ModelMemgraphGraphConfig(
    memgraph_uri="bolt://production-memgraph:7687",
    memgraph_user="app_user",
    memgraph_password="secure_password",
    max_connection_pool_size=100,
    connection_timeout_s=30,
    max_retries=5,
    retry_backoff_ms=2000,
)
```

### Complex Queries

```python
# Find all classes that call a specific function
input_data = ModelMemgraphGraphInput(
    operation="QUERY_GRAPH",
    query="""
        MATCH (c:CLASS)-[:CONTAINS]->(f1:FUNCTION)-[:CALLS]->(f2:FUNCTION)
        WHERE f2.name = $target_function
        RETURN DISTINCT c.name AS class_name,
               c.metadata.file_path AS file_path,
               count(f1) AS call_count
        ORDER BY call_count DESC
    """,
    query_params={"target_function": "authenticate"},
    correlation_id=uuid4(),
)
```

### Pattern Matching

```python
# Find similar code patterns
input_data = ModelMemgraphGraphInput(
    operation="QUERY_GRAPH",
    query="""
        MATCH (p:PATTERN)<-[:MATCHES_PATTERN]-(e)
        WHERE p.name = $pattern_name
        RETURN e.entity_id AS entity_id,
               e.name AS entity_name,
               labels(e)[0] AS entity_type
    """,
    query_params={"pattern_name": "singleton_pattern"},
    correlation_id=uuid4(),
)
```

## Best Practices

1. **Use Batch Operations**: For bulk inserts, use `BATCH_UPSERT` instead of individual operations
2. **Parameterized Queries**: Always use parameterized queries to prevent injection
3. **Connection Pooling**: Reuse the same node instance for multiple operations
4. **Error Handling**: Check `output.success` before accessing results
5. **Metrics Monitoring**: Regularly check metrics for performance insights
6. **Proper Shutdown**: Always call `shutdown()` to clean up connections

## Troubleshooting

### Connection Issues

```python
# Check if driver is initialized
if node.driver is None:
    await node.initialize()
```

### Query Debugging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Transaction Failures

Batch operations automatically rollback on error:

```python
output = await node.execute_effect(input_data)
if not output.success:
    print(f"Transaction rolled back: {output.error}")
```

## Testing

Run the test suite:

```bash
uv run pytest src/omniintelligence/nodes/memgraph_graph_effect/v1_0_0/test_effect.py -v
```

## References

- [Memgraph Documentation](https://memgraph.com/docs)
- [Neo4j Bolt Protocol](https://neo4j.com/docs/bolt/current/)
- [ONEX Node Patterns](../../../docs/ONEX_PATTERNS.md)
