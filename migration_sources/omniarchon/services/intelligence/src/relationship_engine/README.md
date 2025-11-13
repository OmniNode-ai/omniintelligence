

# Pattern Relationship Detection and Graph Engine

Detects relationships between code patterns and builds a knowledge graph for intelligent pattern discovery.

## Features

### Relationship Detection

Automatically detects four types of relationships from Python source code:

1. **USES** - Import relationships
   - Detects `import module` and `from module import name`
   - Confidence: 1.0 (explicit imports)

2. **EXTENDS** - Inheritance relationships
   - Detects `class MyClass(BaseClass)`
   - Supports multiple inheritance
   - Confidence: 1.0 (explicit inheritance)

3. **COMPOSED_OF** - Function call relationships
   - Detects function calls within code
   - Confidence: 0.8-1.0 (based on call frequency)

4. **SIMILAR_TO** - Semantic similarity
   - Uses AST structure comparison
   - Weighs function count, class count, signatures, imports
   - Confidence: 0.0-1.0 (similarity score)

### Knowledge Graph

- **Graph Building**: Build dependency graphs with configurable depth
- **Graph Traversal**: BFS and DFS for path finding and cycle detection
- **Dependency Chains**: Find shortest path between patterns
- **Circular Dependency Detection**: Identify and warn about cycles
- **PostgreSQL Storage**: Stores relationships in `pattern_relationships` table
- **Optional Memgraph Integration**: Advanced graph queries with Cypher

## Usage

### Basic Relationship Detection

```python
from relationship_engine import RelationshipDetector

detector = RelationshipDetector()

source_code = """
import os
from pathlib import Path

class MyClass(BaseClass):
    def process(self):
        os.path.exists("/tmp")
        self.helper()
"""

relationships = detector.detect_all_relationships(
    source_code,
    pattern_name="MyClass",
    pattern_id="uuid-here"
)

for rel in relationships:
    print(f"{rel.relationship_type.value}: {rel.target_pattern_name}")
    print(f"  Confidence: {rel.confidence}")
```

### Semantic Similarity

```python
code_a = "def foo(x, y): return x + y"
code_b = "def bar(a, b): return a + b"

similarity = detector.calculate_structural_similarity(code_a, code_b)
print(f"Similarity: {similarity:.2f}")  # 0.80
```

### Graph Building

```python
from relationship_engine import GraphBuilder

builder = GraphBuilder(
    db_host="192.168.86.200",
    db_port=5436,
    db_name="omninode_bridge",
    db_user="postgres",
    db_password="your-password"
)

# Store relationships
await builder.store_relationship(
    source_pattern_id="uuid-a",
    target_pattern_id="uuid-b",
    relationship_type="uses",
    strength=1.0,
    context={"detection_method": "import_analysis"}
)

# Build graph
graph = await builder.build_graph(
    root_pattern_id="uuid-a",
    depth=2
)

print(f"Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

# Find dependency chain
chain = await builder.find_dependency_chain("uuid-a", "uuid-z")
if chain:
    print(f"Dependency chain: {' -> '.join(chain)}")

# Detect circular dependencies
cycles = await builder.detect_circular_dependencies("uuid-a")
if cycles:
    print(f"Warning: Found {len(cycles)} circular dependencies")
```

### API Endpoints

```bash
# Get all relationships for a pattern
GET /api/patterns/{pattern_id}/relationships

# Build dependency graph
GET /api/patterns/graph?root_pattern_id={uuid}&depth=2

# Find dependency chain
GET /api/patterns/dependency-chain?source_pattern_id={uuid}&target_pattern_id={uuid}

# Detect circular dependencies
GET /api/patterns/{pattern_id}/circular-dependencies

# Create relationship manually
POST /api/patterns/relationships
{
  "source_pattern_id": "uuid",
  "target_pattern_id": "uuid",
  "relationship_type": "uses",
  "strength": 0.95
}

# Auto-detect relationships from source code
POST /api/patterns/{pattern_id}/detect-relationships
{
  "source_code": "import os\nclass MyClass(Base): pass",
  "detect_types": ["uses", "extends"]
}
```

## Database Schema

### pattern_relationships Table

```sql
CREATE TABLE pattern_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_pattern_id UUID NOT NULL REFERENCES pattern_templates(id),
    target_pattern_id UUID NOT NULL REFERENCES pattern_templates(id),
    relationship_type VARCHAR(50) NOT NULL,
    strength DECIMAL(3,2) DEFAULT 0.5 CHECK (strength BETWEEN 0 AND 1),
    description TEXT,
    context JSONB,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_pattern_relationship UNIQUE (source_pattern_id, target_pattern_id, relationship_type),
    CONSTRAINT chk_no_self_relationship CHECK (source_pattern_id != target_pattern_id)
);
```

### Indexes

- `idx_relationship_source` - Source pattern queries
- `idx_relationship_target` - Target pattern queries
- `idx_relationship_type` - Filter by relationship type
- `idx_relationship_strength` - Sort by strength
- `idx_relationship_bidirectional` - Bidirectional queries
- `idx_high_confidence_relationships` - High-confidence filtering (strength >= 0.8)
- `idx_relationship_context_gin` - JSONB metadata queries

## Performance

- **Relationship Detection**: <50ms per pattern (AST parsing)
- **Graph Building (depth=2)**: <200ms (PostgreSQL + indexes)
- **Dependency Chain (BFS)**: <100ms
- **Circular Dependency Detection (DFS)**: <150ms

## Architecture

```
relationship_engine/
├── __init__.py                   # Module exports
├── relationship_detector.py      # AST-based relationship detection
├── graph_builder.py              # Graph building and queries
├── similarity_analyzer.py        # Semantic similarity analysis
└── test_relationship_detector.py # Unit tests
```

## Testing

```bash
# Run unit tests
pytest relationship_engine/test_relationship_detector.py -v

# Test specific relationship type
pytest relationship_engine/test_relationship_detector.py::TestRelationshipDetector::test_detect_import_relationships_basic -v
```

## Future Enhancements

1. **Memgraph Integration**: Advanced graph queries with Cypher
2. **ML-Based Similarity**: Use embeddings for semantic similarity
3. **Relationship Strength Learning**: Automatically adjust strength based on usage
4. **Pattern Recommendations**: Suggest related patterns based on graph
5. **Visualization**: Interactive graph visualization in dashboard
6. **Cross-Language Support**: Extend to TypeScript, Rust, etc.

## Contributing

See main Omniarchon documentation for contribution guidelines.

## License

See main Omniarchon LICENSE file.
