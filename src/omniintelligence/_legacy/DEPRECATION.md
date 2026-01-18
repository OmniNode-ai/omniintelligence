# Legacy Nodes Deprecation Notice

> **WARNING**: All code in this `_legacy/` directory is deprecated and will be removed in a future release.
> Do not use these modules for new development.

## Deprecation Status

| Property | Value |
|----------|-------|
| **Status** | Deprecated as of v0.1.0 |
| **Deprecation Date** | January 2026 |
| **Removal Target** | v2.0.0 |
| **Maintenance** | Critical bug fixes only |

## Overview

The `_legacy/` directory contains the original implementation of OmniIntelligence nodes that were migrated from the `omniarchon` platform. These implementations follow an older, more verbose pattern that has been superseded by the canonical ONEX declarative pattern.

**Key Differences: Legacy vs Canonical**

| Aspect | Legacy Pattern | Canonical Pattern |
|--------|---------------|-------------------|
| **Structure** | `v1_0_0/` versioned subdirectories | Flat structure with `node.py` |
| **Base Class** | Mixed inheritance patterns | Consistent `NodeCompute`, `NodeEffect`, etc. |
| **Configuration** | Inline Pydantic models | Contract-driven via `contract.yaml` |
| **Lines of Code** | 200-500+ lines per node | 20-50 lines per node |
| **Side Effects** | Often mixed into compute nodes | Strictly separated (Effect nodes only) |

## Migration Path

### Node Migration Table

| Legacy Node | Canonical Replacement | Migration Status |
|-------------|----------------------|------------------|
| `_legacy/nodes/entity_extraction_compute/` | `nodes/entity_extraction_compute/` | **Migrated** |
| `_legacy/nodes/ingestion_effect/` | `nodes/ingestion_effect/` | Stub (pending) |
| `_legacy/nodes/intelligence_adapter/` | `nodes/intelligence_adapter/` | **Migrated** |
| `_legacy/nodes/intelligence_api_effect/` | `nodes/intelligence_api_effect/` | **Migrated** |
| `_legacy/nodes/intelligence_orchestrator/` | `nodes/intelligence_orchestrator/` | **Migrated** |
| `_legacy/nodes/intelligence_reducer/` | `nodes/intelligence_reducer/` | **Migrated** |
| `_legacy/nodes/kafka_event_effect/` | *Absorbed into other effects* | See note below |
| `_legacy/nodes/memgraph_graph_effect/` | `nodes/memgraph_graph_effect/` | **Migrated** |
| `_legacy/nodes/pattern_learning_compute/` | `nodes/pattern_learning_compute/` | Stub (pending) |
| `_legacy/nodes/pattern_matching_compute/` | `nodes/pattern_matching_compute/` | **Migrated** |
| `_legacy/nodes/postgres_pattern_effect/` | `nodes/postgres_pattern_effect/` | **Migrated** |
| `_legacy/nodes/qdrant_vector_effect/` | `nodes/qdrant_vector_effect/` | **Migrated** |
| `_legacy/nodes/quality_scoring_compute/` | `nodes/quality_scoring_compute/` | **Migrated** |
| `_legacy/nodes/relationship_detection_compute/` | `nodes/relationship_detection_compute/` | **Migrated** |
| `_legacy/nodes/semantic_analysis_compute/` | `nodes/semantic_analysis_compute/` | **Migrated** |
| `_legacy/nodes/vectorization_compute/` | `nodes/vectorization_compute/` | **Migrated** |

### Pattern Extraction Nodes Migration

The `_legacy/nodes/pattern_extraction/` module contained multiple nodes that have been split into individual canonical nodes:

| Legacy Pattern Extraction Node | Canonical Replacement |
|-------------------------------|----------------------|
| `node_execution_trace_parser_compute.py` | `nodes/execution_trace_parser_compute/` |
| `node_context_keyword_extractor_compute.py` | `nodes/context_keyword_extractor_compute/` |
| `node_intent_classifier_compute.py` | `nodes/intent_classifier_compute/` |
| `node_success_criteria_matcher_compute.py` | `nodes/success_criteria_matcher_compute/` |
| `node_pattern_assembler_orchestrator.py` | `nodes/pattern_assembler_orchestrator/` |

### Other Legacy Components

| Legacy Component | Canonical Replacement | Notes |
|-----------------|----------------------|-------|
| `_legacy/clients/` | `omninode_bridge` package | Use bridge clients |
| `_legacy/enums/` | `omniintelligence.enums` | Some migrated to top-level |
| `_legacy/models/` | Node-specific `models/` dirs | Per-node model modules |
| `_legacy/events/` | Event handling in Effect nodes | Integrated into effects |
| `_legacy/utils/` | `omnibase_core.utils` | Core utilities |

## Special Cases

### kafka_event_effect

The `kafka_event_effect` node does **not** have a direct canonical replacement. Its functionality has been absorbed into other Effect nodes:

- **Event publishing**: Use `NodeIntelligenceAdapterEffect` for intelligence events
- **Event consumption**: Handled by orchestrator nodes with Kafka integration
- **DLQ routing**: Built into all Effect node base classes

If you need standalone Kafka functionality, use the `confluent-kafka` client directly or the event utilities from `omnibase_infra`.

### Stub Nodes (Pending Implementation)

Two canonical nodes are defined but not yet fully implemented:

1. **`NodeIngestionEffect`** - Contract defined, implementation pending
2. **`NodePatternLearningCompute`** - Contract defined, implementation pending

Until these are complete, you may reference the legacy implementations for functionality guidance, but do not import them directly.

## Migration Guide

### Step 1: Update Imports

```python
# BEFORE (deprecated)
from omniintelligence._legacy.nodes.vectorization_compute.v1_0_0.compute import (
    VectorizationCompute,
    ModelVectorizationInput,
    ModelVectorizationOutput,
)

# AFTER (canonical)
from omniintelligence.nodes import NodeVectorizationCompute
from omniintelligence.nodes.vectorization_compute.models import (
    ModelVectorizationInput,
    ModelVectorizationOutput,
)
```

### Step 2: Update Instantiation

```python
# BEFORE (legacy - complex configuration)
compute = VectorizationCompute(
    container=None,
    config=ModelVectorizationConfig(
        embedding_provider=EmbeddingProvider.AUTO,
        max_batch_size=100,
    )
)

# AFTER (canonical - contract-driven)
from omnibase_core.models.container import ModelONEXContainer

container = ModelONEXContainer(...)  # Standard ONEX container
compute = NodeVectorizationCompute(container)
# Configuration comes from contract.yaml, not inline
```

### Step 3: Update Method Calls

Legacy nodes often have custom method signatures. Canonical nodes follow standardized interfaces:

```python
# BEFORE (legacy - async with custom input)
result = await compute.process(ModelVectorizationInput(
    content="code to vectorize",
    metadata={"source": "file.py"},
))

# AFTER (canonical - uses execute_compute from base class)
# Input/output handled by ONEX runtime based on contract.yaml
```

## Deprecation Warnings

Starting in v1.0.0, importing from `_legacy` will emit deprecation warnings:

```python
import warnings
warnings.warn(
    "Importing from omniintelligence._legacy is deprecated. "
    "Use omniintelligence.nodes instead. "
    "Legacy modules will be removed in v2.0.0.",
    DeprecationWarning,
    stacklevel=2
)
```

## Timeline

| Version | Date (Target) | Action |
|---------|--------------|--------|
| v0.1.0 | January 2026 | Legacy nodes deprecated, canonical nodes available |
| v1.0.0 | Q2 2026 | Deprecation warnings added to legacy imports |
| v1.5.0 | Q3 2026 | Legacy nodes marked for removal, final migration notice |
| v2.0.0 | Q4 2026 | **Legacy nodes removed** |

## Questions or Issues?

If you encounter issues migrating from legacy to canonical nodes:

1. Check the canonical node's `contract.yaml` for operation definitions
2. Review the node's `models/` directory for input/output schemas
3. Consult the main `CLAUDE.md` for architecture guidance
4. Open an issue with the `migration` label

## Related Documentation

- [CLAUDE.md](/workspace/omniintelligence/CLAUDE.md) - Project architecture and patterns
- [MIGRATION_SUMMARY.md](/workspace/omniintelligence/migration_sources/omniarchon/MIGRATION_SUMMARY.md) - Original migration overview
- [nodes/__init__.py](/workspace/omniintelligence/src/omniintelligence/nodes/__init__.py) - Canonical node exports
