# Entity Extraction Compute Node

AST-based entity extraction for Python source code following the ONEX architecture pattern.

## Overview

The Entity Extraction Compute Node analyzes Python source code and extracts structured entities including:

- **Functions** (regular and async)
- **Classes** (with methods, attributes, and inheritance)
- **Variables** (module-level and constants)
- **Imports** (standard and from-imports)
- **Module metadata** (docstrings, line numbers)

## Features

### Entity Types Supported

- `MODULE`: Module-level entity with docstring and file metadata
- `FUNCTION`: Functions with signatures, arguments, return types, and async support
- `CLASS`: Classes with base classes, methods, and attributes
- `VARIABLE`: Module-level variables
- `CONSTANT`: All-uppercase module-level constants
- `DEPENDENCY`: Import statements (both `import` and `from...import`)

### Metadata Extraction

Each entity includes rich metadata:

- **Location**: Start and end line numbers
- **Documentation**: Docstrings (when available)
- **Type Information**: Function arguments, return types, class bases
- **Decorators**: Applied decorators (functions and classes)
- **Access Modifiers**: Private (`_name`) and dunder (`__name__`) detection
- **Async Support**: Async function and method detection
- **Relationships**: Class methods and attributes

## Usage

```python
from omnibase_core.models.container import ModelONEXContainer
from omniintelligence.nodes.entity_extraction_compute.v1_0_0 import (
    EntityExtractionCompute,
    ModelEntityExtractionInput,
)

# Create ONEX container
container = ModelONEXContainer(enable_service_registry=False)

# Initialize compute node
compute = EntityExtractionCompute(container=container)

# Prepare input
input_data = ModelEntityExtractionInput(
    content=source_code,
    file_path="path/to/file.py",
    language="python",
    extract_docstrings=True,
    extract_decorators=True,
)

# Extract entities
result = await compute.process(input_data)

if result.success:
    for entity in result.entities:
        print(f"{entity.entity_type}: {entity.name}")
        print(f"  Lines: {entity.metadata.get('line_start')}-{entity.metadata.get('line_end')}")
else:
    print(f"Errors: {result.parse_errors}")
```

## Input Model

```python
class ModelEntityExtractionInput(BaseModel):
    content: str                    # Source code to analyze
    file_path: str                  # Path to source file
    language: str = "python"        # Programming language
    extract_docstrings: bool = True # Extract docstrings
    extract_decorators: bool = True # Extract decorators
```

## Output Model

```python
class ModelEntityExtractionOutput(BaseModel):
    success: bool                   # Whether extraction succeeded
    entities: list[ModelEntity]     # Extracted entities
    parse_errors: list[str]         # Parse errors encountered
    metadata: dict[str, Any]        # Extraction metadata
```

## Configuration

```python
class ModelEntityExtractionConfig(BaseModel):
    supported_languages: list[str] = ["python"]
    max_content_size: int = 1_000_000
    extract_module_level_vars: bool = True
    extract_private_members: bool = True
```

## Entity Metadata Examples

### Function Entity

```python
{
    "file_path": "example.py",
    "line_start": 10,
    "line_end": 15,
    "is_async": False,
    "arguments": ["x", "y"],
    "returns": "int",
    "is_private": False,
    "is_dunder": False,
    "docstring": "Add two numbers.",
    "decorators": ["@cache"]
}
```

### Class Entity

```python
{
    "file_path": "example.py",
    "line_start": 20,
    "line_end": 45,
    "bases": ["BaseClass", "Mixin"],
    "methods": ["__init__", "process", "_helper"],
    "attributes": ["name", "value"],
    "is_private": False,
    "docstring": "Example class.",
    "decorators": ["@dataclass"]
}
```

### Import Entity

```python
{
    "file_path": "example.py",
    "line_number": 5,
    "import_type": "from_import",
    "module": "typing",
    "imported_name": "Optional",
    "alias": None,
    "level": 0  # Relative import level
}
```

## Error Handling

The compute node handles errors gracefully:

- **Syntax Errors**: Returns parse error with line number and message
- **Unsupported Language**: Returns error indicating unsupported language
- **Content Size Limit**: Rejects content exceeding max size
- **Unexpected Errors**: Captures and reports all exceptions

## Implementation Details

### AST-Based Extraction

Uses Python's `ast` module for robust parsing:

- Walks the AST tree to find all node types
- Extracts metadata using AST node attributes
- Handles both Python 3.10+ and earlier versions
- Supports modern Python syntax (async, type hints, etc.)

### ONEX Compliance

Follows the ONEX NodeCompute pattern:

- Inherits from `NodeCompute` base class
- Uses Pydantic models for input/output
- Implements `async def process()` method
- Returns structured `ModelEntity` objects

### Performance

- Single-pass AST traversal
- Efficient entity creation with UUID generation
- Minimal memory footprint
- Handles files up to 1MB by default

## Version History

### v1.0.0

Initial implementation with:

- Python source code support
- 6 entity types (MODULE, FUNCTION, CLASS, VARIABLE, CONSTANT, DEPENDENCY)
- Rich metadata extraction
- Docstring and decorator support
- Error handling and validation
- Type hints and async support
