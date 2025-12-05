# Relationship Detection Compute Node

Detects relationships between code entities extracted from source code using AST analysis.

## Overview

The Relationship Detection Compute Node analyzes Python source code to identify various types of relationships between code entities (functions, classes, variables, etc.). It works in conjunction with the Entity Extraction Compute Node to build a comprehensive knowledge graph of code structure.

## Supported Relationship Types

### 1. IMPORTS
- **Description**: Module imports another module or package
- **Example**: `import os` creates IMPORTS relationship from module to `os`

### 2. EXTENDS (Inheritance)
- **Description**: Class inherits from another class
- **Example**: `class Child(Parent):` creates EXTENDS relationship from `Child` to `Parent`

### 3. CONTAINS
- **Description**: Containment relationships in code structure
- **Subtypes**:
  - Module contains class
  - Module contains function
  - Class contains method
  - Class contains attribute
- **Example**: A module contains top-level classes and functions

### 4. CALLS
- **Description**: Function calls another function
- **Example**: Function `process()` calling `helper()` creates CALLS relationship
- **Metadata**: Includes caller name, callee name, and line number

### 5. USES
- **Description**: Function uses a variable or constant
- **Example**: Function using module-level constant `MAX_SIZE`
- **Metadata**: Includes variable name and line number

### 6. REFERENCES (Decorators & Instantiation)
- **Description**: Decorator applications and class instantiation
- **Subtypes**:
  - `decorates`: Decorator applied to function/class
  - `instantiates`: Class instantiation
- **Example**: `@property` decorator or `obj = MyClass()`

## Input Model

```python
ModelRelationshipDetectionInput(
    content: str,              # Source code content
    file_path: str,           # Path to source file
    entities: list[ModelEntity],  # Pre-extracted entities
    language: str = "python",     # Programming language
    detect_cross_file: bool = True  # Detect cross-file relationships
)
```

## Output Model

```python
ModelRelationshipDetectionOutput(
    success: bool,                         # Detection success status
    relationships: list[ModelRelationship],  # Detected relationships
    parse_errors: list[str],               # Parse errors if any
    metadata: dict[str, Any]               # Detection metadata
)
```

## Configuration

```python
ModelRelationshipDetectionConfig(
    supported_languages: list[str] = ["python"],
    max_content_size: int = 1_000_000,
    detect_calls: bool = True,
    detect_imports: bool = True,
    detect_inheritance: bool = True,
    detect_contains: bool = True,
    detect_uses: bool = True,
    detect_decorators: bool = True,
    detect_instantiation: bool = True,
)
```

## Usage Example

```python
from omniintelligence.nodes.relationship_detection_compute import (
    RelationshipDetectionCompute,
    ModelRelationshipDetectionInput,
)
from omniintelligence.nodes.entity_extraction_compute import (
    EntityExtractionCompute,
    ModelEntityExtractionInput,
)

# Step 1: Extract entities
entity_extractor = EntityExtractionCompute(container=container)
entity_output = await entity_extractor.process(
    ModelEntityExtractionInput(
        content=source_code,
        file_path="example.py",
    )
)

# Step 2: Detect relationships
relationship_detector = RelationshipDetectionCompute(container=container)
relationship_output = await relationship_detector.process(
    ModelRelationshipDetectionInput(
        content=source_code,
        file_path="example.py",
        entities=entity_output.entities,
    )
)

# Process results
for rel in relationship_output.relationships:
    print(f"{rel.relationship_type}: {rel.source_id} -> {rel.target_id}")
```

## Technical Details

### AST Visitor Pattern

The node uses custom AST visitor classes to traverse the syntax tree and detect different relationship types:

- **CallVisitor**: Detects function call relationships
- **UsageVisitor**: Detects variable/constant usage
- **InstantiationVisitor**: Detects class instantiation

### Relationship Detection Strategy

1. **Build Entity Lookup Maps**: Create fast lookup dictionaries by entity name and ID
2. **Detect Import Relationships**: Analyze import statements
3. **Detect Inheritance**: Analyze class base classes
4. **Detect Containment**: Build parent-child relationships in code structure
5. **Detect Calls**: Track function calls within function bodies
6. **Detect Decorators**: Identify decorator applications
7. **Detect Usage**: Track variable/constant references
8. **Detect Instantiation**: Identify class instantiation

### Performance Considerations

- **Entity Lookup**: Uses dictionary lookups for O(1) entity resolution
- **Single AST Parse**: Reuses parsed AST tree for all relationship detection
- **Selective Detection**: Configuration allows disabling specific relationship types
- **Size Limits**: Configurable maximum content size (default 1MB)

## Integration with Knowledge Graph

The detected relationships are stored as `ModelRelationship` objects that include:

- **source_id**: Entity ID of the source (e.g., calling function)
- **target_id**: Entity ID of the target (e.g., called function)
- **relationship_type**: One of the EnumRelationshipType values
- **metadata**: Additional context (line numbers, names, types)

These relationships can be stored in a graph database to enable:
- Call graph analysis
- Dependency tracking
- Impact analysis
- Code navigation
- Refactoring support

## Limitations

- **Python Only**: Currently supports Python source code only
- **Single File Scope**: Cross-file relationships limited to import analysis
- **Static Analysis**: Cannot detect runtime/dynamic relationships
- **Name Resolution**: Relies on simple name matching (doesn't resolve complex module paths)

## Future Enhancements

- Multi-language support (JavaScript, TypeScript, Java)
- Cross-file call graph analysis
- Type-based relationship detection
- Advanced name resolution (scope analysis)
- Confidence scoring for uncertain relationships
- Relationship strength metrics (call frequency, etc.)

## Version

v1.0.0 - Initial implementation with core relationship types

## Dependencies

- `omnibase_core.nodes.NodeCompute`: Base compute node class
- `pydantic`: Data validation and models
- `ast`: Python Abstract Syntax Tree module
- `omniintelligence.enums`: Relationship and entity type enums
- `omniintelligence.models`: Entity and relationship models
