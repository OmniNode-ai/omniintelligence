# Intelligence Adapter Input Contracts

**ONEX v2.0 Compliance** | **Domain Models for Intelligence Operations**

## Overview

The Intelligence Adapter Input Contracts provide strongly-typed domain models for routing intelligence operations to Archon's backend services. These contracts enable unified access to 40+ intelligence operations across 7 categories.

## Files

### Core Contracts

1. **`enum_intelligence_operation_type.py`** - Operation type enumeration
   - 40+ intelligence operation types
   - 7 operation categories (quality, performance, document, pattern, vector, autonomous, traceability)
   - Utility methods for operation classification
   - Validation helpers for operation requirements

2. **`model_intelligence_input.py`** - Input domain model
   - Primary input contract for Intelligence Adapter Effect Node
   - Strongly-typed operation routing with correlation tracking
   - Content and path validation with security checks
   - Comprehensive field validation (Pydantic v2)

3. **`examples_intelligence_input.py`** - Usage examples
   - 10 comprehensive examples covering all operation categories
   - Validation behavior demonstrations
   - Security validation examples
   - Hybrid content/path patterns

## Architecture

### Intelligence Service Routing

```
ModelIntelligenceInput
    ↓
[Intelligence Adapter Effect Node]
    ↓
Operation Router (based on operation_type)
    ↓
┌────────────────────────────────────────────────┐
│          Backend Intelligence Services         │
├────────────────────────────────────────────────┤
│ Quality Service (8053)     | Vector Service    │
│ Performance Service (8053) | Pattern Service   │
│ Document Service (8053)    | Autonomous (8053) │
└────────────────────────────────────────────────┘
```

### Operation Categories

1. **Quality Assessment** (4 operations)
   - assess_code_quality: ONEX compliance + quality scoring (6 dimensions)
   - analyze_document_quality: Document quality and completeness
   - get_quality_patterns: Pattern/anti-pattern extraction
   - check_architectural_compliance: ONEX standards validation

2. **Performance Operations** (5 operations)
   - establish_performance_baseline: Baseline establishment
   - identify_optimization_opportunities: ROI-ranked optimization suggestions
   - apply_performance_optimization: Apply optimizations
   - get_optimization_report: Comprehensive optimization reports
   - monitor_performance_trends: Trend analysis and predictions

3. **Document Freshness** (6 operations)
   - analyze_document_freshness: Freshness and staleness analysis
   - get_stale_documents: Stale document identification
   - refresh_documents: Document refresh with quality gates
   - get_freshness_stats: Comprehensive freshness statistics
   - get_document_freshness: Specific document freshness
   - cleanup_freshness_data: Old data cleanup

4. **Pattern Learning** (7 operations)
   - pattern_match: Code pattern matching
   - hybrid_score: Hybrid pattern scoring
   - semantic_analyze: Semantic pattern analysis
   - get_pattern_metrics: Pattern learning metrics
   - get_cache_stats: Cache statistics
   - clear_pattern_cache: Cache management
   - get_pattern_health: Service health check

5. **Vector Operations** (5 operations)
   - advanced_vector_search: High-performance semantic search
   - quality_weighted_search: ONEX-compliant quality-weighted search
   - batch_index_documents: Batch document indexing
   - get_vector_stats: Vector collection statistics
   - optimize_vector_index: Index optimization

6. **Autonomous Learning** (7 operations)
   - ingest_patterns: Pattern ingestion for learning
   - record_success_pattern: Success pattern recording
   - predict_agent: Optimal agent prediction
   - predict_execution_time: Execution time prediction
   - calculate_safety_score: Safety scoring
   - get_autonomous_stats: Learning statistics
   - get_autonomous_health: Service health

7. **Pattern Traceability** (4 operations)
   - track_pattern_lineage: Pattern lineage tracking
   - get_pattern_lineage: Lineage history retrieval
   - get_execution_logs: Agent execution logs
   - get_execution_summary: Execution summary statistics

## Usage Patterns

### Basic Quality Assessment

```python
from uuid import uuid4
from onex.contracts import EnumIntelligenceOperationType, ModelIntelligenceInput

# Code quality assessment
input_data = ModelIntelligenceInput(
    operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
    correlation_id=uuid4(),
    source_path="src/api.py",
    content=python_code,
    language="python",
    options={"include_recommendations": True}
)
```

### Performance Baseline

```python
# Establish performance baseline
baseline_input = ModelIntelligenceInput(
    operation_type=EnumIntelligenceOperationType.ESTABLISH_PERFORMANCE_BASELINE,
    correlation_id=uuid4(),
    options={
        "operation_name": "api_latency",
        "target_percentile": 95
    }
)
```

### Vector Search

```python
# Quality-weighted semantic search
search_input = ModelIntelligenceInput(
    operation_type=EnumIntelligenceOperationType.QUALITY_WEIGHTED_SEARCH,
    correlation_id=uuid4(),
    content="ONEX effect node patterns",
    options={
        "quality_weight": 0.3,
        "min_quality_score": 0.7,
        "limit": 10
    }
)
```

### Document Freshness

```python
# Analyze document freshness
freshness_input = ModelIntelligenceInput(
    operation_type=EnumIntelligenceOperationType.ANALYZE_DOCUMENT_FRESHNESS,
    correlation_id=uuid4(),
    source_path="docs/ARCHITECTURE.md",
    options={"staleness_threshold_days": 30}
)
```

## Validation Rules

### Required Fields

1. **operation_type** (always required)
   - Must be valid EnumIntelligenceOperationType value
   - Determines routing and validation requirements

2. **correlation_id** (auto-generated if not provided)
   - UUID for distributed tracing
   - Preserved across service calls

### Conditional Requirements

**Content-requiring operations** (quality, pattern, vector search):
- Either `content` or `source_path` must be provided
- Both can be provided for hybrid context

**Path-requiring operations** (document freshness, compliance):
- `source_path` must be provided

**Language-requiring operations** (quality, pattern):
- `language` must be provided when analyzing code content

### Security Validation

**Path Security** (validate_path_security):
- Prevents path traversal (../ detection)
- Character validation (no shell injection)
- Maximum length: 4096 characters

**Content Security** (validate_content_security):
- Maximum size: 10MB
- UTF-8 encoding validation
- Future: Advanced content scanning

**Metadata Security**:
- Key/value sanitization
- Maximum metadata size: 100KB
- Reserved key prevention

## Enum Utility Methods

### Operation Classification

```python
op = EnumIntelligenceOperationType.ASSESS_CODE_QUALITY

# Category checks
op.is_quality_operation()      # True
op.is_performance_operation()  # False
op.is_vector_operation()       # False

# Requirement checks
op.requires_content()          # True
op.requires_source_path()      # True
op.is_read_only()             # True
```

### Model Utility Methods

```python
input_data = ModelIntelligenceInput(...)

# Get operation category
category = input_data.get_operation_category()  # "quality"

# Check if read-only
is_read_only = input_data.is_read_only_operation()  # True

# Get content preview for logging
preview = input_data.get_content_or_placeholder()  # "class Node..."
```

## Error Handling

### Validation Errors

```python
# Missing required content
try:
    ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
        # Missing: content and source_path
        language="python"
    )
except ValueError as e:
    # "Operation 'assess_code_quality' requires either 'content' or 'source_path'"
    pass

# Path traversal attack
try:
    ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.ANALYZE_DOCUMENT_FRESHNESS,
        source_path="../../../etc/passwd"
    )
except ValueError as e:
    # "Invalid source_path: Path traversal detected (..)"
    pass
```

## Examples

Run comprehensive examples:

```bash
cd /Volumes/PRO-G40/Code/omniarchon/services/intelligence
python -m onex.contracts.examples_intelligence_input
```

Output includes:
- 10 usage examples across all categories
- Validation behavior demonstrations
- Security validation tests
- Enum utility method demonstrations

## Integration

### Intelligence Adapter Effect Node

The Intelligence Adapter Effect Node will consume these contracts:

```python
from onex.contracts import ModelIntelligenceInput, EnumIntelligenceOperationType
from onex.base.node_base_effect import NodeBaseEffect

class NodeIntelligenceAdapterEffect(NodeBaseEffect):
    """
    Intelligence Adapter Effect Node for unified intelligence operations.
    """

    async def execute_effect(
        self, contract: ModelIntelligenceInput
    ) -> ModelIntelligenceOutput:
        """Route intelligence operation to appropriate backend service."""

        # Route based on operation type
        if contract.operation_type == EnumIntelligenceOperationType.ASSESS_CODE_QUALITY:
            return await self._assess_code_quality(contract)
        elif contract.operation_type == EnumIntelligenceOperationType.ESTABLISH_PERFORMANCE_BASELINE:
            return await self._establish_baseline(contract)
        # ... etc
```

## Backend Service Mapping

| Operation Category | Backend Service | Port | Endpoints |
|-------------------|----------------|------|-----------|
| Quality Assessment | archon-intelligence | 8053 | /assess/code, /assess/document |
| Performance | archon-intelligence | 8053 | /performance/* |
| Document Freshness | archon-intelligence | 8053 | /freshness/* |
| Pattern Learning | archon-intelligence | 8053 | /api/pattern-learning/* |
| Pattern Traceability | archon-intelligence | 8053 | /api/pattern-traceability/* |
| Autonomous Learning | archon-intelligence | 8053 | /api/autonomous/* |
| Vector Operations | Qdrant + Intelligence | 6333, 8053 | Qdrant API + wrappers |

## See Also

- **ONEX Architecture**: `/docs/ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md`
- **Intelligence APIs**: `/CLAUDE.md` (Intelligence APIs section)
- **Backend Services**: `docker-compose.yml` service definitions
- **Qdrant Contracts**: `qdrant_contracts.py`
- **Base Effect Node**: `onex/base/node_base_effect.py`

## ONEX Compliance

✅ **Suffix-based naming**: `ModelIntelligenceInput`, `EnumIntelligenceOperationType`
✅ **Strong typing**: Pydantic v2 with comprehensive validation
✅ **Correlation tracking**: UUID correlation_id for distributed tracing
✅ **Security validation**: Path traversal prevention, content size limits
✅ **Comprehensive documentation**: Docstrings, examples, field descriptions
✅ **Validation helpers**: Operation classification, requirement checking
✅ **Error handling**: Fail-fast with detailed error messages

---

**Version**: 1.0.0
**ONEX**: v2.0
**Status**: Production Ready
**Last Updated**: 2025-10-21
