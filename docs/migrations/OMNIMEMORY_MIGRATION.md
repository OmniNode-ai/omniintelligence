# OmniIntelligence to OmniMemory Migration Guide

## Overview

As part of PR #12 and the ongoing ONEX architecture consolidation, 9 storage-related nodes have been moved from `omniintelligence` to the dedicated `omnimemory` repository. This migration aligns with the separation of concerns principle:

- **omniintelligence**: Intelligence operations (pattern learning, quality scoring, semantic analysis)
- **omnimemory**: Memory management (storage, retrieval, vectorization, entity extraction)

This guide helps users migrate from the deleted omniintelligence nodes to their omnimemory equivalents.

---

## Node Migration Mapping

### Complete Mapping Table

| Old Node (omniintelligence) | New Location (omnimemory) | Node Type | Status |
|-----------------------------|---------------------------|-----------|--------|
| `NodeQdrantVectorEffect` | `memory_storage_effect` + `memory_retrieval_effect` | Effect | Active |
| `NodeMemgraphGraphEffect` | `memory_storage_effect` (graph backend) | Effect | Scaffold |
| `NodePostgresPatternEffect` | `memory_storage_effect` (PostgreSQL backend) | Effect | Scaffold |
| `NodeIntelligenceApiEffect` | `ProtocolMemoryStorage` + `ProtocolMemoryRetrieval` | Protocol | Active |
| `NodeVectorizationCompute` | `semantic_analyzer_compute` | Compute | Scaffold |
| `NodeEntityExtractionCompute` | `semantic_analyzer_compute` | Compute | Scaffold |
| `NodeContextKeywordExtractorCompute` | `semantic_analyzer_compute` | Compute | Scaffold |
| `NodeRelationshipDetectionCompute` | `similarity_compute` | Compute | Scaffold |
| `NodeIngestionEffect` | `memory_storage_effect` | Effect | Active |

### OmniMemory Core 8 Architecture

OmniMemory implements the ONEX 4-node pattern with 8 core nodes:

```
                        ORCHESTRATORS (2)
         +--------------------------------------------------+
         |  memory_lifecycle_orchestrator                   |
         |  agent_coordinator_orchestrator                  |
         +--------------------------------------------------+
                               |
            +------------------+------------------+
            |                                     |
            v                                     v
   +------------------+                +-------------------+
   |    REDUCERS (2)  |                |    COMPUTE (2)    |
   +------------------+                +-------------------+
   | memory_          |                | semantic_analyzer |
   | consolidator_    |                | _compute          |
   | reducer          |                |                   |
   |                  |                | similarity_       |
   | statistics_      |                | compute           |
   | reducer          |                |                   |
   +------------------+                +-------------------+
            |                                     |
            +------------------+------------------+
                               |
                               v
                    +-------------------+
                    |    EFFECTS (2)    |
                    +-------------------+
                    | memory_storage_   |
                    | effect            |
                    |                   |
                    | memory_retrieval_ |
                    | effect            |
                    +-------------------+
```

---

## Installation

### Add OmniMemory Dependency

**Using Poetry (recommended):**

```bash
# Add omnimemory as a dependency
poetry add git+https://github.com/your-org/omnimemory.git

# Or with a specific version/tag
poetry add git+https://github.com/your-org/omnimemory.git@v0.1.0
```

**Using pip:**

```bash
pip install git+https://github.com/your-org/omnimemory.git
```

### Update pyproject.toml

```toml
[tool.poetry.dependencies]
omnimemory = { git = "https://github.com/your-org/omnimemory.git", branch = "main" }
```

---

## Migration Examples

### 1. Vector Storage Operations

**Before (omniintelligence):**

```python
from omniintelligence.nodes.qdrant_vector_effect import NodeQdrantVectorEffect
from omniintelligence.nodes.qdrant_vector_effect.models import (
    ModelQdrantVectorInput,
    ModelQdrantVectorOutput,
)

# Initialize vector effect
vector_effect = NodeQdrantVectorEffect()
await vector_effect.initialize()

# Store vectors
input_data = ModelQdrantVectorInput(
    operation="INDEX_VECTORS",
    collection_name="code_embeddings",
    vectors=[
        {"id": "doc-1", "vector": embedding_1, "payload": {"file": "main.py"}},
        {"id": "doc-2", "vector": embedding_2, "payload": {"file": "utils.py"}},
    ],
)
result = await vector_effect.execute(input_data)
```

**After (omnimemory):**

```python
from pathlib import Path
from omnimemory.nodes.memory_storage_effect import (
    HandlerFileSystemAdapter,
    HandlerFileSystemAdapterConfig,
    ModelMemoryStorageRequest,
)
from omnibase_core.models.omnimemory import ModelMemorySnapshot

# Initialize storage adapter
config = HandlerFileSystemAdapterConfig(base_path=Path("/data/memory"))
adapter = HandlerFileSystemAdapter(config)
await adapter.initialize()

# Create memory snapshot with vectors
snapshot = ModelMemorySnapshot(
    snapshot_id="doc-1",
    content={"vectors": embedding_1},
    metadata={"file": "main.py", "type": "code_embedding"},
)

# Store snapshot
request = ModelMemoryStorageRequest(
    operation="store",
    snapshot=snapshot,
    tags=["code", "embeddings"],
)
response = await adapter.execute(request)

if response.status == "success":
    print(f"Stored snapshot: {response.snapshot.snapshot_id}")
```

### 2. Entity Extraction

**Before (omniintelligence):**

```python
from omniintelligence.nodes.entity_extraction_compute import (
    NodeEntityExtractionCompute,
)
from omniintelligence.nodes.entity_extraction_compute.models import (
    ModelEntityExtractionInput,
)

# Extract entities from code
extractor = NodeEntityExtractionCompute()
input_data = ModelEntityExtractionInput(
    code_content="def calculate_total(items): ...",
    file_path="calculator.py",
    language="python",
)
result = await extractor.execute_compute(input_data)
entities = result.entities  # [{"name": "calculate_total", "type": "function"}, ...]
```

**After (omnimemory):**

```python
from omnimemory import ProtocolSemanticAnalyzer
from omnimemory.models.intelligence import ModelSemanticAnalysisResult

# Use the semantic analyzer protocol for entity extraction
# Note: Implementation depends on concrete adapter being used
class MySemanticAnalyzer(ProtocolSemanticAnalyzer):
    async def analyze_semantic(
        self, content: str, metadata: dict
    ) -> ModelSemanticAnalysisResult:
        # Your entity extraction logic here
        ...

analyzer = MySemanticAnalyzer()
result = await analyzer.analyze_semantic(
    content="def calculate_total(items): ...",
    metadata={"file_path": "calculator.py", "language": "python"},
)
```

### 3. Ingestion Pipeline

**Before (omniintelligence):**

```python
from omniintelligence.nodes.ingestion_effect import NodeIngestionEffect
from omniintelligence.nodes.ingestion_effect.models import (
    ModelIngestionInput,
)

# Ingest documents via Kafka
ingestion = NodeIngestionEffect()
await ingestion.initialize()

input_data = ModelIngestionInput(
    operation="PUBLISH_EVENT",
    topic="dev.archon-intelligence.enrichment.requested.v1",
    payload={
        "document_id": "doc-123",
        "content": "Code content here...",
        "metadata": {"source": "github", "repo": "myrepo"},
    },
)
result = await ingestion.execute(input_data)
```

**After (omnimemory):**

```python
from pathlib import Path
from omnimemory.nodes.memory_storage_effect import (
    HandlerFileSystemAdapter,
    HandlerFileSystemAdapterConfig,
    ModelMemoryStorageRequest,
)
from omnibase_core.models.omnimemory import ModelMemorySnapshot

# For file-based storage (Phase 1)
config = HandlerFileSystemAdapterConfig(base_path=Path("/data/ingestion"))
adapter = HandlerFileSystemAdapter(config)
await adapter.initialize()

# Create snapshot for ingested document
snapshot = ModelMemorySnapshot(
    snapshot_id="doc-123",
    content="Code content here...",
    metadata={
        "source": "github",
        "repo": "myrepo",
        "ingestion_timestamp": datetime.now().isoformat(),
    },
)

request = ModelMemoryStorageRequest(
    operation="store",
    snapshot=snapshot,
    tags=["ingested", "github"],
)
response = await adapter.execute(request)
```

### 4. Pattern Storage

**Before (omniintelligence):**

```python
from omniintelligence.nodes.postgres_pattern_effect import (
    NodePostgresPatternEffect,
)
from omniintelligence.nodes.postgres_pattern_effect.models import (
    ModelPatternStorageInput,
)

# Store patterns
pattern_effect = NodePostgresPatternEffect()
await pattern_effect.initialize()

input_data = ModelPatternStorageInput(
    operation="STORE_PATTERN",
    pattern_id="pattern-001",
    pattern_type="code_quality",
    pattern_data={
        "name": "docstring_required",
        "rules": ["functions must have docstrings"],
        "severity": "warning",
    },
)
result = await pattern_effect.execute(input_data)
```

**After (omnimemory):**

```python
from pathlib import Path
from omnimemory.nodes.memory_storage_effect import (
    HandlerFileSystemAdapter,
    HandlerFileSystemAdapterConfig,
    ModelMemoryStorageRequest,
)
from omnibase_core.models.omnimemory import ModelMemorySnapshot

# Store patterns as memory snapshots
config = HandlerFileSystemAdapterConfig(base_path=Path("/data/patterns"))
adapter = HandlerFileSystemAdapter(config)
await adapter.initialize()

snapshot = ModelMemorySnapshot(
    snapshot_id="pattern-001",
    content={
        "name": "docstring_required",
        "rules": ["functions must have docstrings"],
        "severity": "warning",
    },
    metadata={"pattern_type": "code_quality"},
)

request = ModelMemoryStorageRequest(
    operation="store",
    snapshot=snapshot,
    tags=["pattern", "code_quality"],
)
response = await adapter.execute(request)
```

### 5. Vectorization Compute

**Before (omniintelligence):**

```python
from omniintelligence.nodes.vectorization_compute import (
    NodeVectorizationCompute,
)
from omniintelligence.nodes.vectorization_compute.models import (
    ModelVectorizationInput,
    ModelVectorizationOutput,
)

# Generate embeddings
vectorizer = NodeVectorizationCompute()
input_data = ModelVectorizationInput(
    text="def hello_world(): print('Hello, World!')",
    model_name="code-embeddings-v1",
)
result: ModelVectorizationOutput = await vectorizer.execute_compute(input_data)
embedding = result.embedding  # [0.123, -0.456, ...]
```

**After (omnimemory):**

```python
from omnimemory import ProtocolSemanticAnalyzer
from omnimemory.models.intelligence import ModelSemanticAnalysisResult

# Use semantic analyzer protocol for embedding generation
# Note: semantic_analyzer_compute is currently a scaffold
# Implement using the protocol interface:

class MyEmbeddingGenerator(ProtocolSemanticAnalyzer):
    def __init__(self, model_name: str = "code-embeddings-v1"):
        self.model_name = model_name
        # Initialize your embedding model here

    async def analyze_semantic(
        self, content: str, metadata: dict | None = None
    ) -> ModelSemanticAnalysisResult:
        # Generate embeddings using your preferred method
        embedding = self._generate_embedding(content)
        return ModelSemanticAnalysisResult(
            embeddings=embedding,
            metadata={"model": self.model_name},
        )

generator = MyEmbeddingGenerator()
result = await generator.analyze_semantic(
    content="def hello_world(): print('Hello, World!')"
)
```

---

## API Differences

### Operation Enums

**OmniIntelligence** used node-specific operation enums:

```python
# Old: Node-specific operations
class QdrantOperationType(str, Enum):
    INDEX_VECTORS = "INDEX_VECTORS"
    SEARCH_VECTORS = "SEARCH_VECTORS"
    DELETE_VECTORS = "DELETE_VECTORS"
```

**OmniMemory** uses unified memory operation types:

```python
# New: Unified memory operations
from omnimemory.enums import EnumMemoryOperationType

class EnumMemoryOperationType(str, Enum):
    STORE = "store"
    RETRIEVE = "retrieve"
    UPDATE = "update"
    DELETE = "delete"
    SEARCH = "search"
    ANALYZE = "analyze"
    CONSOLIDATE = "consolidate"
    OPTIMIZE = "optimize"
    HEALTH_CHECK = "health_check"
    SYNC = "sync"
```

### Response Models

**OmniIntelligence** had node-specific response models:

```python
# Old response structure
result = await vector_effect.execute(input_data)
if result.success:
    vectors = result.vectors
    metadata = result.metadata
```

**OmniMemory** uses a consistent response envelope:

```python
from omnimemory.nodes.memory_storage_effect.models import (
    ModelMemoryStorageResponse,
)

# New response structure
response: ModelMemoryStorageResponse = await adapter.execute(request)

# Status can be: "success", "error", "not_found", "permission_denied"
if response.status == "success":
    snapshot = response.snapshot
    snapshot_ids = response.snapshot_ids  # For list operations
elif response.status == "not_found":
    print(f"Snapshot not found: {response.error_message}")
elif response.status == "error":
    print(f"Error: {response.error_message}")
```

### Protocol-Based Design

OmniMemory emphasizes protocol-based interfaces for better extensibility:

```python
from omnimemory import (
    # Base protocols
    ProtocolMemoryBase,
    ProtocolMemoryOperations,
    # Effect protocols
    ProtocolMemoryStorage,
    ProtocolMemoryRetrieval,
    ProtocolMemoryPersistence,
    # Compute protocols
    ProtocolSemanticAnalyzer,
    ProtocolPatternRecognition,
    ProtocolIntelligenceProcessor,
    # Reducer protocols
    ProtocolMemoryConsolidator,
    ProtocolMemoryAggregator,
    ProtocolMemoryOptimizer,
    # Orchestrator protocols
    ProtocolWorkflowCoordinator,
    ProtocolAgentCoordinator,
    ProtocolMemoryOrchestrator,
)
```

---

## Current Implementation Status

### Active (Fully Implemented)

| Node | Description |
|------|-------------|
| `memory_storage_effect` | FileSystem backend for CRUD operations |

### Scaffold (Interface Defined, Implementation Pending)

| Node | Description | Expected Phase |
|------|-------------|----------------|
| `memory_retrieval_effect` | Semantic/temporal/contextual search | Phase 2 |
| `semantic_analyzer_compute` | Semantic analysis and embeddings | Phase 2 |
| `similarity_compute` | Vector similarity calculations | Phase 2 |
| `memory_consolidator_reducer` | Memory merge operations | Phase 2 |
| `statistics_reducer` | Memory statistics generation | Phase 2 |
| `memory_lifecycle_orchestrator` | Full lifecycle management | Phase 3 |
| `agent_coordinator_orchestrator` | Cross-agent coordination | Phase 3 |

---

## Migration Checklist

### Pre-Migration

- [ ] Audit current usage of deleted omniintelligence nodes
- [ ] Add omnimemory as a project dependency
- [ ] Review API differences documented above

### Code Migration

- [ ] Replace `NodeQdrantVectorEffect` with `memory_storage_effect`/`memory_retrieval_effect`
- [ ] Replace `NodeMemgraphGraphEffect` with `memory_storage_effect` (graph backend - scaffold)
- [ ] Replace `NodePostgresPatternEffect` with `memory_storage_effect` (PostgreSQL backend - scaffold)
- [ ] Replace `NodeIntelligenceApiEffect` with omnimemory protocols
- [ ] Replace `NodeVectorizationCompute` with `semantic_analyzer_compute` (scaffold)
- [ ] Replace `NodeEntityExtractionCompute` with `semantic_analyzer_compute` (scaffold)
- [ ] Replace `NodeContextKeywordExtractorCompute` with `semantic_analyzer_compute` (scaffold)
- [ ] Replace `NodeRelationshipDetectionCompute` with `similarity_compute` (scaffold)
- [ ] Replace `NodeIngestionEffect` with `memory_storage_effect`

### Testing

- [ ] Update unit tests to use omnimemory imports
- [ ] Verify integration tests pass with new implementations
- [ ] Test error handling with new response envelope format

### Post-Migration

- [ ] Remove omniintelligence imports for deleted nodes
- [ ] Update documentation references
- [ ] Monitor for any runtime issues

---

## Temporary Workarounds

For nodes that are currently scaffolds in omnimemory, you have several options:

### Option 1: Implement Against Protocol

```python
from omnimemory import ProtocolSemanticAnalyzer

class MyTemporarySemanticAnalyzer(ProtocolSemanticAnalyzer):
    """Temporary implementation until omnimemory scaffold is completed."""

    async def analyze_semantic(self, content: str, metadata: dict | None = None):
        # Your existing logic from the old node
        ...
```

### Option 2: Use FileSystem Adapter with Custom Serialization

```python
from omnimemory.nodes.memory_storage_effect import (
    HandlerFileSystemAdapter,
    ModelMemoryStorageRequest,
)

# Store complex data as JSON in snapshots
snapshot = ModelMemorySnapshot(
    snapshot_id=f"vector-{uuid4()}",
    content={
        "vectors": embedding_list,
        "metadata": custom_metadata,
    },
)
```

### Option 3: Direct Backend Access

For advanced use cases, access the storage backend directly while omnimemory scaffolds are being implemented:

```python
# Direct Qdrant access (temporary)
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)
# ... direct operations
```

---

## Related Documentation

- [OmniMemory README](https://github.com/your-org/omnimemory/blob/main/README.md)
- [ONEX Migration Plan](./ONEX_MIGRATION_PLAN.md)
- [Node Mapping Reference](./NODE_MAPPING_REFERENCE.md)
- [OmniArchon to OmniIntelligence Migration](./omniarchon_to_omniintelligence.md)

---

**Document Version**: 1.0
**Last Updated**: 2026-01-20
**Related PR**: #12 (Remove obsolete intelligence nodes)
