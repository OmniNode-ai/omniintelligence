# Task Characteristics System - Complete Guide

**Version**: 1.0.0  
**Date**: 2025-01-17  
**Purpose**: Track 3 (Pattern Matching) & Track 4 (Autonomous Execution)

## Overview

The Task Characteristics System provides comprehensive extraction, similarity matching, and autonomous execution planning for Archon tasks. This system powers:

- **Track 3**: Historical task pattern matching for intelligence-driven recommendations
- **Track 4**: Autonomous execution feasibility assessment and planning

## Quick Start

### Installation

```python
# All components are in the Archon python package
from src.server.models.task_characteristics_models import TaskCharacteristics
from src.server.services.task_characteristics_extractor import TaskCharacteristicsExtractor
from src.server.services.task_characteristics_matcher import TaskCharacteristicsMatcher
```

### Basic Usage

```python
# 1. Extract characteristics from Archon task
extractor = TaskCharacteristicsExtractor()
characteristics = extractor.extract(archon_task_dict)

# 2. Generate embedding for similarity search
embedding_text = characteristics.to_embedding_text()

# 3. Find similar historical tasks
matcher = TaskCharacteristicsMatcher()
similar_tasks = matcher.find_similar(characteristics, historical_tasks)

# 4. Check autonomous execution readiness
is_ready = characteristics.is_execution_ready(min_feasibility=0.6)
```

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Archon Task (Input)                       │
│  { id, title, description, sources, code_examples, ... }    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           TaskCharacteristicsExtractor                       │
│  • Classify task type (bug_fix, feature, test, etc.)       │
│  • Assess complexity (score + level)                        │
│  • Determine change scope (single_file → cross_repo)        │
│  • Extract context (sources, examples, criteria)            │
│  • Identify components (API, database, UI, etc.)            │
│  • Calculate autonomous feasibility                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              TaskCharacteristics (Output)                    │
│                                                              │
│  • metadata: TaskMetadata                                   │
│  • task_type: TaskType (enum)                              │
│  • complexity: TaskComplexityMetrics                        │
│  • change_scope: ChangeScope (enum)                        │
│  • context: TaskContext                                     │
│  • dependencies: TaskDependencies                           │
│  • file_patterns: TaskFilePatterns                          │
│  • affected_components: List[Component]                     │
│  • historical: TaskHistoricalContext                        │
│  • autonomous_execution_feasibility: float                  │
│  • suggested_execution_pattern: ExecutionPattern           │
└──────────────┬──────────────────────┬──────────────────────┘
               │                       │
               ▼                       ▼
    ┌──────────────────┐    ┌──────────────────────┐
    │  to_embedding_   │    │ to_dict_for_         │
    │  text()          │    │ filtering()          │
    │                  │    │                      │
    │  Semantic        │    │ Structured           │
    │  Search          │    │ Filtering            │
    └────────┬─────────┘    └──────────┬───────────┘
             │                          │
             ▼                          ▼
    ┌─────────────────────────────────────────┐
    │   TaskCharacteristicsMatcher             │
    │                                          │
    │  • Multi-dimensional similarity         │
    │  • Weighted scoring                     │
    │  • Hybrid structured + semantic         │
    │  • Similarity explanation               │
    └─────────────────┬────────────────────────┘
                      │
                      ▼
              ┌────────────────┐
              │ SimilarityMatch │
              │                │
              │ • task_id      │
              │ • score        │
              │ • matching     │
              │   chars        │
              └────────────────┘
```

## Core Components

### 1. Models (`task_characteristics_models.py`)

#### TaskCharacteristics
The main schema containing all extracted characteristics.

**Key Fields**:
```python
TaskCharacteristics(
    metadata: TaskMetadata,               # ID, title, timestamps
    task_type: TaskType,                  # bug_fix, feature, test, etc.
    complexity: TaskComplexityMetrics,    # Score, level, estimates
    change_scope: ChangeScope,            # single_file → cross_repository
    context: TaskContext,                 # Available context assessment
    dependencies: TaskDependencies,       # Dependency chain info
    file_patterns: TaskFilePatterns,      # Affected files/dirs
    affected_components: List[Component], # System components
    historical: TaskHistoricalContext,    # Historical patterns
    autonomous_execution_feasibility: float,  # 0.0-1.0
    suggested_execution_pattern: ExecutionPattern
)
```

#### Enumerations

**TaskType** (25 values):
- Development: `feature_implementation`, `bug_fix`, `refactoring`, `performance_optimization`
- Testing: `test_writing`, `test_debugging`, `test_coverage_improvement`
- Documentation: `documentation_creation`, `documentation_update`, `api_documentation`
- Infrastructure: `infrastructure_setup`, `deployment`, `devops_automation`
- Architecture: `architecture_design`, `api_design`, `database_design`
- Investigation: `debug_investigation`, `research`, `proof_of_concept`
- Management: `planning`, `code_review`, `security_audit`

**ComplexityLevel** (5 values):
- `trivial` (< 0.2): Single-line changes
- `simple` (0.2-0.4): Straightforward tasks
- `moderate` (0.4-0.6): Multiple files
- `complex` (0.6-0.8): Significant changes
- `very_complex` (> 0.8): Major refactoring

**ChangeScope** (7 values):
- `single_file` → `multiple_files` → `module` → `cross_module` → `cross_service` → `repository_wide` → `cross_repository`

**Component** (35 values):
Backend: `api_layer`, `business_logic`, `data_access`, `authentication`, `authorization`, `background_jobs`, `event_system`, `caching`

Frontend: `ui_components`, `state_management`, `routing`, `forms`

Data: `database_schema`, `migrations`, `models`, `queries`

Infrastructure: `containerization`, `orchestration`, `monitoring`, `logging`, `ci_cd`

Integration: `external_api`, `webhooks`, `message_queue`, `file_storage`

Testing: `unit_tests`, `integration_tests`, `e2e_tests`, `fixtures`

Docs: `readme`, `api_docs`, `inline_documentation`, `architecture_docs`

**ExecutionPattern** (10 values):
- Linear: `sequential_implementation`, `test_driven_development`, `refactor_then_extend`
- Iterative: `spike_then_implement`, `prototype_then_refine`, `incremental_migration`
- Investigative: `debug_root_cause`, `reproduce_then_fix`, `analyze_then_optimize`
- Coordination: `parallel_development`, `dependency_first`, `integration_last`

### 2. Extractor (`task_characteristics_extractor.py`)

Extracts characteristics from Archon task dictionaries.

**Features**:
- Keyword-based task type classification
- Multi-factor complexity assessment
- Context availability analysis
- Component identification from keywords and file patterns
- Execution pattern suggestion based on heuristics

**Usage**:
```python
extractor = TaskCharacteristicsExtractor()

# Single task extraction
characteristics = extractor.extract(archon_task)

# Batch extraction
batch_extractor = BatchTaskCharacteristicsExtractor()
all_characteristics = batch_extractor.extract_batch(task_list)

# Extract with validation
characteristics, errors = batch_extractor.extract_and_validate(archon_task)
```

### 3. Matcher (`task_characteristics_matcher.py`)

Multi-dimensional similarity matching with weighted scoring.

**Similarity Components**:
- Task Type Similarity (weight: 0.25)
- Complexity Similarity (weight: 0.15)
- Scope Similarity (weight: 0.15)
- Component Overlap (weight: 0.20)
- Context Similarity (weight: 0.15)
- Semantic Text Similarity (weight: 0.10)

**Usage**:
```python
matcher = TaskCharacteristicsMatcher()

# Find similar tasks
matches = matcher.find_similar(
    target=target_characteristics,
    candidates=historical_characteristics_list,
    query=TaskCharacteristicsQuery(
        min_similarity_threshold=0.7,
        max_results=10,
        filter_by_task_type=[TaskType.BUG_FIX, TaskType.DEBUG_INVESTIGATION],
        require_code_examples=True
    )
)

# Calculate similarity between two tasks
score, matching_chars = matcher.calculate_similarity(task1, task2)

# Explain similarity
explanation = explain_similarity(matches[0])
```

### 4. Validator (`task_characteristics_matcher.py`)

Validates extraction quality and completeness.

**Validation Checks**:
- Task type classification success
- Complexity assessment completeness
- Context availability adequacy
- Component identification success
- Consistency validation (scope vs estimated files)
- Feasibility score reasonableness

**Usage**:
```python
validator = TaskCharacteristicsValidator()
result = validator.validate(characteristics)

print(f"Valid: {result['is_valid']}")
print(f"Quality: {result['extraction_quality']}")  # excellent/good/fair/poor
print(f"Completeness: {result['completeness_score']:.0%}")
print(f"Errors: {result['validation_errors']}")
print(f"Warnings: {result['validation_warnings']}")
```

## Examples

### 12 Comprehensive Examples

See `/python/src/server/data/task_characteristics_examples.py` for complete examples covering:

1. **simple_bug_fix** - Single file bug with good context
2. **feature_implementation** - Multi-file API feature
3. **test_writing** - Comprehensive test suite
4. **performance_optimization** - Database query optimization
5. **documentation_task** - API docs update
6. **architecture_design** - System design planning
7. **debug_investigation** - Root cause analysis (minimal context)
8. **infrastructure_setup** - Kubernetes deployment
9. **refactoring_task** - Dependency injection refactor
10. **research_poc** - Technology evaluation
11. **security_audit** - Security review
12. **database_migration** - Schema changes with data migration

Each example includes:
- Complete Archon task dictionary
- Expected characteristics
- Use case description

### Example: Bug Fix

```python
from src.server.data.task_characteristics_examples import EXAMPLE_TASKS

# Get example
bug_fix_example = EXAMPLE_TASKS["simple_bug_fix"]
archon_task = bug_fix_example["archon_task"]

# Extract characteristics
extractor = TaskCharacteristicsExtractor()
characteristics = extractor.extract(archon_task)

# Validate against expected
expected = bug_fix_example["expected_characteristics"]
assert characteristics.task_type.value == expected["task_type"]
assert characteristics.complexity.complexity_level.value == expected["complexity_level"]
assert characteristics.change_scope.value == expected["change_scope"]

# Generate embedding
embedding_text = characteristics.to_embedding_text()
# Output: "Task Type: bug_fix | Title: Fix null pointer exception... | Scope: single_file | Complexity: simple | Components: authentication, business_logic | ..."
```

## Embedding Strategy

See `/docs/TASK_CHARACTERISTICS_EMBEDDING_STRATEGY.md` for comprehensive embedding documentation.

### Quick Reference

**Three Approaches**:
1. **Pure Semantic** (MVP) - Direct embedding from `to_embedding_text()`
2. **Hybrid** (Production) - Structured + semantic weighted combination
3. **Pre-filtered** (High Accuracy) - Structured filtering then semantic search

**Recommended Model**: OpenAI `text-embedding-3-small`
- Dimensions: 1536
- Cost: $0.02 / 1M tokens
- Quality: 62.3% MTEB
- Latency: ~50ms

**Alternative**: `sentence-transformers/all-MiniLM-L6-v2`
- Local, free, 384 dimensions
- Quality: 58.2% MTEB
- Latency: ~20ms (GPU)

## Integration Patterns

### Track 3: Pattern Matching

```python
# When user creates/updates task
archon_task = create_task_in_database(...)

# Extract characteristics
characteristics = extractor.extract(archon_task)

# Generate and store embedding
embedding = generate_embedding(characteristics.to_embedding_text())
qdrant_client.upsert(
    collection_name="task_characteristics",
    points=[{
        "id": characteristics.metadata.task_id,
        "vector": embedding,
        "payload": characteristics.to_dict_for_filtering()
    }]
)

# Later: Find similar historical tasks
search_results = qdrant_client.search(
    collection_name="task_characteristics",
    query_vector=generate_embedding(new_task.to_embedding_text()),
    limit=5
)
```

### Track 4: Autonomous Execution

```python
# Assess execution readiness
characteristics = extractor.extract(new_task)

if characteristics.is_execution_ready(min_feasibility=0.7):
    # Task is ready for autonomous execution
    execution_plan = create_execution_plan(
        pattern=characteristics.suggested_execution_pattern,
        complexity=characteristics.complexity,
        components=characteristics.affected_components
    )

    # Route to appropriate agent
    agent = select_agent_for_task(characteristics)
    execute_autonomous(agent, execution_plan)
else:
    # Request more context or assign to human
    required_context = [
        ct for ct in characteristics.context.required_context_types
        if ct not in characteristics.context.available_context_types
    ]
    request_additional_context(required_context)
```

## Performance Considerations

### Extraction Performance

- **Single task**: ~10-20ms
- **Batch (100 tasks)**: ~500ms-1s
- **Complexity**: O(n) where n = description length

**Optimization Tips**:
- Use batch extraction for bulk processing
- Cache extraction results by task hash
- Extract only when task content changes

### Similarity Matching Performance

- **Structured only**: ~1ms per comparison
- **Semantic only**: ~50ms per embedding generation
- **Hybrid**: ~55ms per comparison

**Optimization Tips**:
- Pre-filter with structured fields before semantic search
- Use Qdrant ANN for large-scale similarity search
- Cache embeddings aggressively

### Embedding Generation Performance

| Model | Latency | Throughput | Cost |
|-------|---------|------------|------|
| OpenAI text-embedding-3-small | 50ms | 2000/min | $0.02/1M tokens |
| sentence-transformers (GPU) | 20ms/batch | 5000/min | Free |
| Ollama local | 200ms | 300/min | Free |

## Testing

### Unit Tests

```python
# Test extraction
def test_extract_bug_fix():
    extractor = TaskCharacteristicsExtractor()
    characteristics = extractor.extract(BUG_FIX_TASK)

    assert characteristics.task_type == TaskType.BUG_FIX
    assert 0.2 <= characteristics.complexity.complexity_score <= 0.4
    assert characteristics.change_scope == ChangeScope.SINGLE_FILE

# Test similarity matching
def test_similarity_matching():
    matcher = TaskCharacteristicsMatcher()
    score, _ = matcher.calculate_similarity(bug_fix_1, bug_fix_2)

    assert score > 0.7  # Similar bug fixes should score high
```

### Integration Tests

```python
# End-to-end test
def test_end_to_end_pattern_matching():
    # Extract from multiple tasks
    tasks = [create_sample_task() for _ in range(10)]
    characteristics_list = [extractor.extract(t) for t in tasks]

    # Find similar
    matcher = TaskCharacteristicsMatcher()
    matches = matcher.find_similar(
        target=characteristics_list[0],
        candidates=characteristics_list[1:]
    )

    assert len(matches) > 0
    assert all(0 <= m.similarity_score <= 1.0 for m in matches)
```

## Roadmap

### ✅ Completed (Week 1)
- Complete TaskCharacteristics schema
- Extraction logic with validation
- Multi-dimensional similarity matching
- 12 comprehensive examples
- Embedding strategy documentation

### 🔄 In Progress (Week 2)
- [ ] Qdrant integration and indexing
- [ ] Batch processing optimization
- [ ] Embedding generation service
- [ ] REST API endpoints
- [ ] Performance benchmarks

### 📋 Planned (Week 3-4)
- [ ] Historical data analysis
- [ ] Machine learning model fine-tuning
- [ ] Advanced filtering and faceting
- [ ] Real-time characteristic extraction on task creation
- [ ] Dashboard for similarity insights

## API Reference

### TaskCharacteristics Methods

```python
# Generate embedding text
embedding_text = characteristics.to_embedding_text()

# Get filterable dict
filters = characteristics.to_dict_for_filtering()

# Check execution readiness
is_ready = characteristics.is_execution_ready(min_feasibility=0.6)
```

### Extractor Methods

```python
# Extract single task
characteristics = extractor.extract(task, historical_data=None)

# Extract batch
all_chars = batch_extractor.extract_batch(tasks, historical_data_map)

# Extract with validation
chars, errors = batch_extractor.extract_and_validate(task)
```

### Matcher Methods

```python
# Find similar tasks
matches = matcher.find_similar(target, candidates, query)

# Calculate similarity
score, matching_chars = matcher.calculate_similarity(task1, task2)

# Create query
query = create_similarity_query(
    target,
    min_threshold=0.7,
    max_results=10,
    task_types=[TaskType.BUG_FIX],
    components=[Component.API_LAYER]
)
```

## Troubleshooting

### Common Issues

**Issue**: Task type always returns UNKNOWN
- **Cause**: Insufficient keywords in title/description
- **Solution**: Enhance description or manually specify task type

**Issue**: Complexity score is 0.0
- **Cause**: Very short or empty description
- **Solution**: Add detailed description with context

**Issue**: No similar tasks found
- **Cause**: Threshold too high or insufficient historical data
- **Solution**: Lower similarity threshold or enrich historical database

**Issue**: Autonomous feasibility is always low
- **Cause**: Missing context (sources, examples, acceptance criteria)
- **Solution**: Add more task context before extraction

## Support & Contributing

**Documentation**:
- Schema Reference: `/python/src/server/models/task_characteristics_models.py`
- Extraction Logic: `/python/src/server/services/task_characteristics_extractor.py`
- Matching Logic: `/python/src/server/services/task_characteristics_matcher.py`
- Examples: `/python/src/server/data/task_characteristics_examples.py`
- Embedding Strategy: `/docs/TASK_CHARACTERISTICS_EMBEDDING_STRATEGY.md`

**Questions**: Review examples and documentation first, then check integration tests for usage patterns.

---

**Task Characteristics System** - Powering intelligent pattern matching and autonomous execution for Archon.
