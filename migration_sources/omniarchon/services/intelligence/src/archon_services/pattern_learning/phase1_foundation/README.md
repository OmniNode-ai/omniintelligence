# Task Characteristics Extraction System

## Overview

The Task Characteristics Extraction System is a core component of the Archon autonomous agent selection system (Track 4). It analyzes Archon tasks to extract comprehensive characteristics that enable intelligent pattern matching and agent selection.

## Components

### 1. Model: `model_task_characteristics.py`

Defines the complete task characteristics schema using Pydantic models:

```python
from services.pattern_learning.phase1_foundation.models.model_task_characteristics import (
    ModelTaskCharacteristics,
    ModelTaskCharacteristicsInput,
    ModelTaskCharacteristicsOutput,
    EnumTaskType,
    EnumComplexity,
    EnumChangeScope,
)
```

**Key Features:**
- **Task Type Classification**: 12 task types (code_generation, debugging, refactoring, testing, etc.)
- **Complexity Levels**: 5 levels from trivial to very_complex
- **Change Scope**: 7 scope levels from single_function to system_wide
- **Context Indicators**: Tracks sources, code examples, acceptance criteria
- **Dependency Tracking**: Parent task relationships and chain length
- **Impact Estimation**: Affected files, components, and tokens
- **Embedding Generation**: `to_embedding_text()` for semantic search
- **Feature Vectors**: `to_feature_vector()` for ML-based matching

### 2. Extractor: `node_task_characteristics_extractor_compute.py`

ONEX-compliant Compute node that extracts characteristics from tasks:

```python
from services.pattern_learning.phase1_foundation import (
    NodeTaskCharacteristicsExtractorCompute,
)

extractor = NodeTaskCharacteristicsExtractorCompute()
result = await extractor.execute_compute(task_input)
```

**Extraction Capabilities:**
- **Task Type**: Keyword-based classification with TF-IDF scoring
- **Complexity**: Multi-factor analysis (length, sources, keywords)
- **Scope**: Heuristic-based scope detection
- **Context**: Automatic detection of available resources
- **Components**: Extraction of affected system components
- **Keywords**: Semantic keyword extraction for matching
- **Performance**: <100ms extraction time target

### 3. Example Characteristics: `example_task_characteristics.py`

Pre-defined examples for common task patterns:

```python
from services.pattern_learning.phase1_foundation.example_task_characteristics import (
    EXAMPLE_CODE_GENERATION_SIMPLE,
    EXAMPLE_DEBUGGING_COMPLEX,
    ALL_EXAMPLES,
    get_example_by_type,
)
```

**Available Examples:**
- Code generation (simple & complex)
- Debugging (simple & complex)
- Refactoring, Testing, Documentation
- Architecture, Performance, Security, Integration

## Usage Examples

### Basic Extraction

```python
import asyncio
from uuid import uuid4
from services.pattern_learning.phase1_foundation import (
    NodeTaskCharacteristicsExtractorCompute,
    ModelTaskCharacteristicsInput,
)

async def extract_characteristics():
    # Initialize extractor
    extractor = NodeTaskCharacteristicsExtractorCompute()

    # Create input from Archon task
    task_input = ModelTaskCharacteristicsInput(
        task_id=uuid4(),
        title="Implement User Authentication",
        description="""
        Build authentication system with JWT tokens.
        Should include user registration, login, and session management.
        """,
        assignee="AI IDE Agent",
        feature="authentication",
        sources=[{"url": "https://jwt.io/", "type": "docs"}],
    )

    # Extract characteristics
    result = await extractor.execute_compute(task_input)

    print(f"Task Type: {result.characteristics.task_type}")
    print(f"Complexity: {result.characteristics.complexity}")
    print(f"Estimated Files: {result.characteristics.estimated_files_affected}")
    print(f"Confidence: {result.confidence:.2%}")

asyncio.run(extract_characteristics())
```

### Embedding Generation for Vector Search

```python
# Get embedding text for Qdrant
embedding_text = result.characteristics.to_embedding_text()
# Use with Qdrant client to generate vector embedding

# Example output:
# "Task Type: code_generation | Complexity: moderate |
#  Scope: multiple_files | Title: implement user authentication |
#  Keywords: authentication, jwt, user, login |
#  Components: auth, api"
```

### Feature Vector for ML Matching

```python
# Get feature vector for similarity calculations
feature_vector = result.characteristics.to_feature_vector()

# Returns:
# {
#     "task_type": "code_generation",
#     "complexity": "moderate",
#     "change_scope": "multiple_files",
#     "has_sources": 1,
#     "has_code_examples": 0,
#     "estimated_files_affected": 8,
#     "estimated_tokens": 6000,
#     ...
# }
```

## Schema Fields

### Core Classification
- `task_type`: EnumTaskType (code_generation, debugging, etc.)
- `complexity`: EnumComplexity (trivial to very_complex)
- `change_scope`: EnumChangeScope (single_function to system_wide)

### Context Availability
- `has_sources`: bool - Whether task includes source references
- `has_code_examples`: bool - Whether task includes code examples
- `has_acceptance_criteria`: bool - Whether task has explicit criteria

### Dependency Information
- `dependency_chain_length`: int - Length of parent task chain
- `parent_task_type`: Optional[EnumTaskType] - Type of parent task
- `is_subtask`: bool - Whether this is a subtask

### Impact Estimation
- `affected_file_patterns`: List[str] - File patterns likely affected
- `estimated_files_affected`: int - Estimated number of files
- `affected_components`: List[str] - System components affected

### Pattern Matching
- `similar_task_count`: int - Count of similar historical tasks
- `feature_label`: Optional[str] - Feature area label
- `estimated_tokens`: int - Estimated token count for completion
- `keywords`: List[str] - Extracted keywords
- `title_normalized`: str - Normalized title for embedding
- `description_normalized`: str - Normalized description

## Test Suite

Comprehensive tests in `tests/pattern_learning/test_task_characteristics.py`:

```bash
# Run all tests
pytest services/intelligence/tests/pattern_learning/test_task_characteristics.py -v

# Run specific test
pytest services/intelligence/tests/pattern_learning/test_task_characteristics.py::test_code_generation_extraction -v
```

**Test Coverage:**
- ✓ Code generation task extraction
- ✓ Debugging task extraction
- ✓ Refactoring task extraction
- ✓ Testing task extraction
- ✓ Documentation task extraction
- ✓ Subtask and dependency detection
- ✓ Embedding text generation
- ✓ Feature vector generation
- ✓ Performance benchmarking (<100ms target)
- ✓ Error handling and fallback

**All tests passing**: 10/10 ✓

## Performance

- **Extraction Speed**: <100ms per task (target met)
- **Confidence Scoring**: 0.7-1.0 for well-defined tasks
- **Memory Efficient**: No persistence, pure functional computation
- **ONEX Compliant**: Deterministic, no side effects, correlation ID propagation

## Integration with Track 3 & 4

### Track 3: Pattern Learning
```python
# Generate embedding for Qdrant storage
embedding_text = characteristics.to_embedding_text()
# Store in Qdrant with task execution results
```

### Track 4: Autonomous System
```python
# Extract characteristics from new task
result = await extractor.execute_compute(task_input)

# Use for agent selection
agent = await autonomous_system.select_agent(
    task_characteristics=result.characteristics
)
```

## Future Enhancements

- [ ] Machine learning-based classification refinement
- [ ] Historical similarity scoring integration
- [ ] Dynamic complexity adjustment based on execution data
- [ ] Multi-language support for task descriptions
- [ ] Advanced NLP for better keyword extraction

## References

- **ONEX Architecture**: [ONEX Architecture Patterns](../../../../../../docs/onex/archive/ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md)
- **Task Characteristics System**: [Task Characteristics System](../../../../../../docs/architecture/TASK_CHARACTERISTICS_SYSTEM.md)
- **Pattern Learning Engine**: [Pattern Learning Engine](../../../../../../docs/pattern_learning_engine/)

---

**Status**: ✅ Implementation Complete (2025-10-02)
**Track**: Track 4 Preparation
**Next Steps**: Integration with Qdrant for embedding storage and similarity search
