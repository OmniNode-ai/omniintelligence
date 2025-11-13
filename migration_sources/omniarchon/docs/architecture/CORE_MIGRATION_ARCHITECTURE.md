# Core Migration System Architecture

**Version**: 1.0.0
**Status**: Design
**Last Updated**: 2025-11-02
**Related**: [AUTOMATED_CORE_MIGRATION_SYSTEM.md](../planning/AUTOMATED_CORE_MIGRATION_SYSTEM.md)

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [ONEX Node Mapping](#onex-node-mapping)
3. [Component Specifications](#component-specifications)
4. [Data Models & Schemas](#data-models--schemas)
5. [API Contracts](#api-contracts)
6. [Algorithms & Logic](#algorithms--logic)
7. [Data Flow](#data-flow)
8. [Integration Architecture](#integration-architecture)
9. [Performance & Scalability](#performance--scalability)
10. [Security Model](#security-model)

---

## System Architecture

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     MIGRATION SYSTEM                            │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Effect     │  │   Compute    │  │   Reducer    │         │
│  │   Nodes      │  │   Nodes      │  │   Nodes      │         │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤         │
│  │ CLI          │  │ Snapshot     │  │ Artifact     │         │
│  │ Git Ops      │  │ Differ       │  │ Storage      │         │
│  │ Registry API │  │ Inference    │  │ Manifest DB  │         │
│  │ Event Pub    │  │ Scoring      │  │ Checkpoint   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  ┌─────────────────────────────────────────────────┐           │
│  │           Orchestrator Nodes                    │           │
│  ├─────────────────────────────────────────────────┤           │
│  │ Pipeline Coordinator                            │           │
│  │ Dependency Resolver                             │           │
│  │ Verification Engine                             │           │
│  └─────────────────────────────────────────────────┘           │
└────────────────────────────────────────────────────────────────┘
         │                      │                      │
         ↓                      ↓                      ↓
┌─────────────────┐  ┌────────────────────┐  ┌────────────────┐
│ Tree Service    │  │ Archon Intelligence│  │ Event Bus      │
│ (8058)          │  │ (8053)             │  │ (Redpanda)     │
└─────────────────┘  └────────────────────┘  └────────────────┘
```

### Component Layers

**Layer 1: Effect (External Interaction)**
- CLI interface
- Git repository operations
- Registry API client/server
- Event publishing

**Layer 2: Compute (Business Logic)**
- Snapshot generation
- Symbol graph extraction
- Difference detection
- Inference engine
- Confidence scoring
- Codemod generation

**Layer 3: Reducer (State Management)**
- Artifact storage
- Manifest database
- Checkpoint management
- Migration history

**Layer 4: Orchestrator (Workflow)**
- Pipeline coordination
- Dependency resolution
- Parallel processing
- Error recovery

---

## ONEX Node Mapping

### Effect Nodes

#### 1. CLI Interface Effect

**Responsibility**: Command-line interface for migration operations

**ONEX Pattern**: Parameter Collector + External Interaction

```python
# services/migration/effects/cli_effect.py

from omnibase_spi import Effect, EffectResult

class CLIEffect(Effect):
    """CLI interface for migration system."""

    async def execute(self, params: CLIParams) -> EffectResult:
        """
        Handle CLI command execution.

        Commands:
        - generate: Generate manifest
        - apply: Apply manifest
        - verify: Verify manifest
        - rollback: Rollback migration
        """
        pass
```

#### 2. Git Operations Effect

**Responsibility**: Git checkout, file operations, tagging

```python
class GitOperationsEffect(Effect):
    """Git repository operations."""

    async def checkout_ref(self, repo_path: str, ref: str) -> str:
        """Checkout git ref and return commit SHA."""
        pass

    async def get_file_at_ref(self, repo_path: str, file_path: str, ref: str) -> bytes:
        """Get file content at specific ref."""
        pass
```

#### 3. Registry API Effect

**Responsibility**: Publish/fetch manifests from registry

```python
class RegistryAPIEffect(Effect):
    """Manifest registry operations."""

    async def publish_manifest(self, manifest: Manifest, uri: str) -> str:
        """Publish manifest to registry."""
        pass

    async def fetch_manifest(self, uri: str) -> Manifest:
        """Fetch manifest from registry."""
        pass
```

#### 4. Event Publishing Effect

**Responsibility**: Publish migration events to event bus

```python
class MigrationEventEffect(Effect):
    """Event bus publishing for migration events."""

    async def publish_manifest_ready(
        self,
        manifest_id: str,
        from_version: str,
        to_version: str,
        uri: str
    ) -> None:
        """Publish core.migration.ready event."""
        pass
```

### Compute Nodes

#### 1. Snapshot Generator Compute

**Responsibility**: Generate `.tree` and metadata snapshots

```python
# services/migration/compute/snapshot_generator.py

from omnibase_spi import Compute, ComputeResult

class SnapshotGenerator(Compute):
    """Generate snapshots of codebase at specific refs."""

    async def generate_snapshot(
        self,
        repo_path: str,
        ref: str,
        config: SnapshotConfig
    ) -> Snapshot:
        """
        Generate comprehensive snapshot.

        Returns:
            Snapshot with .tree, metadata, and symbol graph
        """
        tree = await self._generate_tree(repo_path, ref)
        metadata = await self._stamp_metadata(tree)
        symbol_graph = await self._extract_symbols(tree, metadata)

        return Snapshot(
            ref=ref,
            tree=tree,
            metadata=metadata,
            symbol_graph=symbol_graph,
            timestamp=datetime.now(UTC)
        )
```

#### 2. Difference Detector Compute

**Responsibility**: Detect differences between snapshots

```python
class DifferenceDetector(Compute):
    """Detect structural and semantic differences."""

    async def detect_differences(
        self,
        snapshot_a: Snapshot,
        snapshot_b: Snapshot
    ) -> DifferenceSet:
        """
        Detect all differences between snapshots.

        Returns:
            Categorized differences (added, removed, modified, moved)
        """
        file_diffs = self._diff_files(snapshot_a.tree, snapshot_b.tree)
        symbol_diffs = self._diff_symbols(
            snapshot_a.symbol_graph,
            snapshot_b.symbol_graph
        )

        return DifferenceSet(
            files=file_diffs,
            symbols=symbol_diffs,
            metadata=self._diff_metadata(snapshot_a, snapshot_b)
        )
```

#### 3. Inference Engine Compute

**Responsibility**: Infer migration operations from differences

```python
class InferenceEngine(Compute):
    """Infer migration operations from differences."""

    async def infer_operations(
        self,
        differences: DifferenceSet,
        config: InferenceConfig
    ) -> List[Operation]:
        """
        Infer migration operations.

        Inference rules:
        - Module move: identical hash + path change
        - Symbol rename: high similarity + same usage
        - Arg rename: same body + param change
        - Default added: new param with safe default
        """
        operations = []

        operations.extend(self._infer_module_moves(differences))
        operations.extend(self._infer_symbol_renames(differences))
        operations.extend(self._infer_signature_changes(differences))
        operations.extend(self._infer_config_changes(differences))

        return operations
```

#### 4. Confidence Scorer Compute

**Responsibility**: Score operation confidence

```python
class ConfidenceScorer(Compute):
    """Score confidence for inferred operations."""

    async def score_operations(
        self,
        operations: List[Operation],
        evidence: Evidence
    ) -> List[ScoredOperation]:
        """
        Score operation confidence.

        Factors:
        - AST similarity (0.0-1.0)
        - Docstring similarity (0.0-1.0)
        - Import graph overlap (0.0-1.0)
        - Usage pattern consistency (0.0-1.0)
        """
        scored = []

        for op in operations:
            confidence = self._calculate_confidence(op, evidence)
            scored.append(ScoredOperation(
                operation=op,
                confidence=confidence,
                factors=confidence.breakdown,
                recommendation=self._get_recommendation(confidence)
            ))

        return scored
```

#### 5. Codemod Generator Compute

**Responsibility**: Generate AST-based code transformations

```python
class CodemodGenerator(Compute):
    """Generate AST-based codemods."""

    async def generate_codemod(
        self,
        operation: Operation,
        target_code: str
    ) -> Codemod:
        """
        Generate codemod for operation.

        Uses libCST for Python transformations.
        """
        tree = cst.parse_module(target_code)
        visitor = self._get_visitor_for_operation(operation)
        modified_tree = tree.visit(visitor)

        return Codemod(
            operation_id=operation.id,
            original=target_code,
            modified=modified_tree.code,
            diff=self._generate_diff(target_code, modified_tree.code)
        )
```

### Reducer Nodes

#### 1. Artifact Storage Reducer

**Responsibility**: Manage snapshot and manifest artifacts

```python
# services/migration/reducers/artifact_storage.py

from omnibase_spi import Reducer, State

class ArtifactStorage(Reducer):
    """Manage migration artifacts."""

    async def store_snapshot(
        self,
        snapshot: Snapshot,
        path: str
    ) -> State:
        """
        Store snapshot with versioning.

        Storage structure:
        artifacts/core_diff/{from}_{to}/
          ├─ snapshot_from.json
          ├─ snapshot_to.json
          ├─ graph_from.json
          ├─ graph_to.json
          └─ metadata.json
        """
        pass

    async def store_manifest(
        self,
        manifest: Manifest,
        path: str
    ) -> State:
        """Store manifest with checksums."""
        pass
```

#### 2. Manifest Database Reducer

**Responsibility**: Persist manifests and metadata

**Database Schema**:

```sql
-- Migration manifests
CREATE TABLE migration_manifests (
    id UUID PRIMARY KEY,
    from_version VARCHAR(50) NOT NULL,
    to_version VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    manifest_uri VARCHAR(500) NOT NULL,
    checksum VARCHAR(64) NOT NULL,  -- BLAKE3
    operation_count INT NOT NULL,
    confidence_avg FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- draft, published, deprecated
    metadata JSONB
);

-- Operations within manifests
CREATE TABLE manifest_operations (
    id UUID PRIMARY KEY,
    manifest_id UUID REFERENCES migration_manifests(id),
    operation_type VARCHAR(50) NOT NULL,  -- rename.import, rename.symbol, etc.
    operation_data JSONB NOT NULL,
    confidence FLOAT NOT NULL,
    evidence JSONB NOT NULL,
    sequence_order INT NOT NULL
);

-- Migration applications (tracking)
CREATE TABLE migration_applications (
    id UUID PRIMARY KEY,
    manifest_id UUID REFERENCES migration_manifests(id),
    package_name VARCHAR(200) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL,
    applied_by VARCHAR(100),
    success BOOLEAN NOT NULL,
    operations_applied INT NOT NULL,
    operations_failed INT NOT NULL,
    rollback_checkpoint VARCHAR(500),
    logs JSONB
);

-- Indexes
CREATE INDEX idx_manifests_versions ON migration_manifests(from_version, to_version);
CREATE INDEX idx_operations_manifest ON manifest_operations(manifest_id);
CREATE INDEX idx_applications_package ON migration_applications(package_name);
```

#### 3. Checkpoint Manager Reducer

**Responsibility**: Create and manage rollback checkpoints

```python
class CheckpointManager(Reducer):
    """Manage migration checkpoints."""

    async def create_checkpoint(
        self,
        package_path: str,
        label: str
    ) -> Checkpoint:
        """
        Create rollback checkpoint.

        Stores:
        - Git ref/commit
        - File checksums
        - Dependency versions
        """
        pass

    async def restore_checkpoint(
        self,
        checkpoint_id: str,
        package_path: str
    ) -> State:
        """Restore from checkpoint."""
        pass
```

### Orchestrator Nodes

#### 1. Pipeline Coordinator

**Responsibility**: Coordinate migration pipeline

```python
# services/migration/orchestrators/pipeline_coordinator.py

from omnibase_spi import Orchestrator, WorkflowState

class PipelineCoordinator(Orchestrator):
    """Coordinate migration generation pipeline."""

    async def execute_pipeline(
        self,
        config: PipelineConfig
    ) -> WorkflowState:
        """
        Execute complete pipeline:
        1. Checkout refs
        2. Generate snapshots (parallel)
        3. Diff snapshots
        4. Infer operations
        5. Score confidence
        6. Synthesize manifest
        7. Verify
        8. Publish
        """
        workflow = self._build_workflow(config)

        async with workflow.transaction():
            # Execute stages
            refs = await self._stage_checkout(config)
            snapshots = await self._stage_snapshot(refs)
            diffs = await self._stage_diff(snapshots)
            operations = await self._stage_infer(diffs)
            scored = await self._stage_score(operations)
            manifest = await self._stage_synthesize(scored)
            verified = await self._stage_verify(manifest)
            published = await self._stage_publish(verified)

        return WorkflowState(
            status="complete",
            manifest_id=published.id,
            uri=published.uri
        )
```

#### 2. Dependency Resolver

**Responsibility**: Resolve migration dependencies

```python
class DependencyResolver(Orchestrator):
    """Resolve migration order for dependent packages."""

    async def resolve_migration_order(
        self,
        packages: List[Package],
        manifest: Manifest
    ) -> List[MigrationStep]:
        """
        Build DAG and topologically sort.

        Returns ordered list of migration steps.
        """
        graph = self._build_dependency_graph(packages)
        cycles = self._detect_cycles(graph)

        if cycles:
            raise DependencyError(f"Circular dependencies: {cycles}")

        return self._topological_sort(graph)
```

---

## Component Specifications

### Snapshot Generator

**Interface**:

```python
@dataclass
class SnapshotConfig:
    """Configuration for snapshot generation."""
    include_tests: bool = True
    include_docs: bool = True
    cache_enabled: bool = True
    parallel_workers: int = 4

@dataclass
class Snapshot:
    """Snapshot of codebase at specific ref."""
    ref: str
    commit_sha: str
    tree: TreeStructure
    metadata: Dict[str, FileMetadata]
    symbol_graph: SymbolGraph
    timestamp: datetime
    checksum: str  # BLAKE3 of all content
```

**Algorithm**:

```python
async def generate_snapshot(
    repo_path: str,
    ref: str,
    config: SnapshotConfig
) -> Snapshot:
    """
    1. Checkout ref (Effect)
    2. Discover files (batch_processor.py pattern)
    3. Generate .tree structure
    4. Stamp metadata (parallel)
    5. Extract symbols (parallel)
    6. Build symbol graph
    7. Calculate checksum
    8. Store snapshot (Reducer)
    """
    # Checkout
    commit_sha = await git_effect.checkout_ref(repo_path, ref)

    # Discover
    files = await file_discovery.discover(
        repo_path,
        exclude_patterns=CACHE_PATTERNS
    )

    # Parallel processing
    async with TaskGroup() as tg:
        tree_task = tg.create_task(generate_tree(files))
        metadata_task = tg.create_task(stamp_metadata(files))

    tree = await tree_task
    metadata = await metadata_task

    # Symbol extraction
    symbol_graph = await extract_symbols(tree, metadata)

    # Checksum
    checksum = calculate_snapshot_checksum(tree, metadata)

    return Snapshot(...)
```

### Inference Engine

**Inference Rules**:

```python
class InferenceRule:
    """Base class for inference rules."""

    def matches(self, difference: Difference) -> bool:
        """Check if rule applies to difference."""
        pass

    def infer(self, difference: Difference) -> Optional[Operation]:
        """Infer operation from difference."""
        pass

    def calculate_confidence(self, difference: Difference, evidence: Evidence) -> float:
        """Calculate confidence score."""
        pass
```

**Module Move Rule**:

```python
class ModuleMoveRule(InferenceRule):
    """Detect module moves (path change, content identical)."""

    def matches(self, diff: Difference) -> bool:
        return (
            diff.type == "file_moved" and
            diff.content_hash_before == diff.content_hash_after
        )

    def infer(self, diff: Difference) -> Operation:
        return Operation(
            kind="rename.import",
            match={
                "from": diff.path_before,
                "to": diff.path_after
            },
            evidence={
                "content_hash": diff.content_hash_before,
                "method": "hash_match"
            }
        )

    def calculate_confidence(self, diff: Difference, evidence: Evidence) -> float:
        # Hash match = 100% confidence
        return 1.0
```

**Symbol Rename Rule**:

```python
class SymbolRenameRule(InferenceRule):
    """Detect symbol renames (high similarity, same usage)."""

    def matches(self, diff: Difference) -> bool:
        return diff.type == "symbol_changed"

    def infer(self, diff: Difference) -> Operation:
        # Calculate similarities
        ast_sim = self._ast_similarity(
            diff.symbol_before.ast,
            diff.symbol_after.ast
        )
        doc_sim = self._docstring_similarity(
            diff.symbol_before.docstring,
            diff.symbol_after.docstring
        )
        usage_sim = self._usage_similarity(
            diff.symbol_before.usages,
            diff.symbol_after.usages
        )

        if ast_sim > 0.9 and doc_sim > 0.8:
            return Operation(
                kind="rename.symbol",
                match={
                    "module": diff.module,
                    "from": diff.symbol_before.name,
                    "to": diff.symbol_after.name
                },
                evidence={
                    "ast_similarity": ast_sim,
                    "doc_similarity": doc_sim,
                    "usage_similarity": usage_sim
                }
            )

        return None

    def calculate_confidence(self, diff: Difference, evidence: Evidence) -> float:
        # Weighted average
        return (
            evidence["ast_similarity"] * 0.5 +
            evidence["doc_similarity"] * 0.3 +
            evidence["usage_similarity"] * 0.2
        )
```

### Confidence Scoring

**Scoring Model**:

```python
@dataclass
class ConfidenceScore:
    """Confidence score with breakdown."""
    overall: float  # 0.0-1.0
    factors: Dict[str, float]
    recommendation: str  # "auto_apply", "apply_with_warning", "manual_review"

class ConfidenceCalculator:
    """Calculate multi-factor confidence scores."""

    # Weights for different factors
    WEIGHTS = {
        "ast_similarity": 0.35,
        "doc_similarity": 0.20,
        "usage_similarity": 0.25,
        "test_coverage": 0.10,
        "manual_validation": 0.10
    }

    def calculate(self, operation: Operation, evidence: Evidence) -> ConfidenceScore:
        """Calculate weighted confidence score."""
        factors = {}

        # AST similarity
        if "ast_similarity" in evidence:
            factors["ast_similarity"] = evidence["ast_similarity"]

        # Docstring similarity
        if "doc_similarity" in evidence:
            factors["doc_similarity"] = evidence["doc_similarity"]

        # Usage patterns
        if "usage_similarity" in evidence:
            factors["usage_similarity"] = evidence["usage_similarity"]

        # Test coverage
        if "test_coverage" in evidence:
            factors["test_coverage"] = evidence["test_coverage"]

        # Calculate weighted average
        overall = sum(
            factors.get(key, 0.5) * weight
            for key, weight in self.WEIGHTS.items()
        )

        # Determine recommendation
        recommendation = self._get_recommendation(overall)

        return ConfidenceScore(
            overall=overall,
            factors=factors,
            recommendation=recommendation
        )

    def _get_recommendation(self, score: float) -> str:
        """Get action recommendation based on score."""
        if score >= 0.9:
            return "auto_apply"
        elif score >= 0.7:
            return "apply_with_warning"
        else:
            return "manual_review"
```

---

## Data Models & Schemas

### Tree Structure Schema

```yaml
# .tree file format
version: 2
metadata:
  generated_at: "2025-11-02T18:00:00Z"
  generator: "migration-system/1.0.0"
  ref: "v1.0.0"
  commit_sha: "abc123..."

root: omninode/

files:
  - path: omninode/validators/base.py
    size_bytes: 15234
    lang: python
    hash: sha256:97ff...  # File content hash
    last_modified: "2025-10-24T10:00:00Z"
    symbols:
      - fq: omninode.validators.base.BaseValidator
        kind: class
        line_start: 21
        line_end: 157
        sig_hash: blake3:7f3a...  # Signature hash
        exports: [public_api, validator]

      - fq: omninode.validators.base.BaseValidator.validate
        kind: method
        line_start: 45
        line_end: 89
        sig_hash: blake3:9c2b...
        parent: omninode.validators.base.BaseValidator
```

### Symbol Graph Schema

```python
@dataclass
class SymbolNode:
    """Node in symbol graph."""
    fq_name: str  # Fully-qualified name
    kind: str  # class, function, method, variable
    module: str
    file_path: str
    line_start: int
    line_end: int
    signature_hash: str
    docstring: Optional[str]
    metadata: Dict[str, Any]

@dataclass
class SymbolEdge:
    """Edge in symbol graph."""
    source_fq: str
    target_fq: str
    edge_type: str  # imports, inherits, calls, exports
    metadata: Dict[str, Any]

@dataclass
class SymbolGraph:
    """Complete symbol graph."""
    nodes: Dict[str, SymbolNode]
    edges: List[SymbolEdge]
    entry_points: List[str]  # Public API symbols
```

### Manifest Schema (v1)

```yaml
manifest_version: 1
schema_url: "https://registry.omninode.dev/schemas/manifest/v1.json"

metadata:
  from_version: "0.9.0"
  to_version: "1.0.0"
  from_commit: "abc123..."
  to_commit: "def456..."
  generated_at: "2025-11-02T18:00:00Z"
  generator: "migration-system/1.0.0"

summary:
  title: "Path normalization, class renames, minor argument changes"
  breaking_changes: 15
  safe_changes: 42
  manual_review_required: 3

operations:
  - id: "OP001"
    kind: "rename.import"
    sequence: 1

    match:
      from: "omninode.core.validators.base"
      to: "omninode.validators.base"

    evidence:
      method: "hash_match"
      content_hash: "blake3:7f3a..."
      detection: "automatic"

    confidence:
      overall: 1.0
      factors:
        hash_match: 1.0
      recommendation: "auto_apply"

    metadata:
      breaking: false
      safe_rollback: true
      estimated_impact: "low"

  - id: "OP002"
    kind: "rename.symbol"
    sequence: 2
    dependencies: ["OP001"]  # Must apply OP001 first

    match:
      module: "omninode.validators.base"
      from: "BaseValidator"
      to: "ValidatorBase"

    evidence:
      method: "ast_similarity"
      ast_similarity: 0.98
      doc_similarity: 0.95
      usage_similarity: 0.92

    confidence:
      overall: 0.95
      factors:
        ast_similarity: 0.98
        doc_similarity: 0.95
        usage_similarity: 0.92
      recommendation: "auto_apply"

    metadata:
      breaking: true
      safe_rollback: true
      estimated_impact: "medium"

  - id: "OP003"
    kind: "arg.rename"
    sequence: 3

    match:
      callable: "omninode.utils.io.read_file_text"
      parameter:
        from: "encoding"
        to: "codec"
        default: "utf-8"
        required: false

    evidence:
      method: "callsite_analysis"
      callsites_found: 37
      safe_auto_fix_rate: 1.0

    confidence:
      overall: 0.98
      factors:
        signature_match: 1.0
        callsite_coverage: 0.95
      recommendation: "auto_apply"

    metadata:
      breaking: false  # Has default
      safe_rollback: true
      estimated_impact: "low"
```

---

## API Contracts

### Manifest Generation API

**Endpoint**: `POST /api/migration/generate`

**Request**:
```json
{
  "core_repo": {
    "path": "/path/to/core",
    "from_ref": "v0.9.0",
    "to_ref": "v1.0.0"
  },
  "config": {
    "confidence_threshold": 0.8,
    "parallel_workers": 4,
    "cache_enabled": true
  },
  "output": {
    "path": "artifacts/core_diff/0.9.0_1.0.0",
    "publish_to_registry": true
  }
}
```

**Response**:
```json
{
  "manifest_id": "uuid-...",
  "manifest_uri": "registry://core_migrations/0.9.0_1.0.0",
  "summary": {
    "operations_total": 57,
    "operations_auto": 42,
    "operations_review": 15,
    "confidence_avg": 0.89
  },
  "artifacts": {
    "manifest": "artifacts/core_diff/0.9.0_1.0.0/manifest.yaml",
    "report": "artifacts/core_diff/0.9.0_1.0.0/report.json",
    "snapshot_from": "artifacts/core_diff/0.9.0_1.0.0/snapshot_from.json",
    "snapshot_to": "artifacts/core_diff/0.9.0_1.0.0/snapshot_to.json"
  },
  "processing_time_ms": 12457
}
```

### Migration Application API

**Endpoint**: `POST /api/migration/apply`

**Request**:
```json
{
  "manifest_uri": "registry://core_migrations/0.9.0_1.0.0",
  "target": {
    "path": "/path/to/dependent/package",
    "create_checkpoint": true
  },
  "options": {
    "dry_run": false,
    "auto_apply_threshold": 0.9,
    "generate_patch": true
  }
}
```

**Response**:
```json
{
  "application_id": "uuid-...",
  "status": "success",
  "summary": {
    "operations_attempted": 42,
    "operations_successful": 40,
    "operations_failed": 2,
    "operations_skipped": 15
  },
  "checkpoint": {
    "id": "checkpoint-uuid...",
    "path": "artifacts/rollback/checkpoint_pre_1.0.0"
  },
  "changes": {
    "files_modified": 18,
    "lines_added": 45,
    "lines_removed": 23,
    "patch_file": "artifacts/patches/migration_0.9.0_1.0.0.patch"
  },
  "failures": [
    {
      "operation_id": "OP037",
      "reason": "Ambiguous match - multiple candidates",
      "recommendation": "Manual review required"
    }
  ]
}
```

---

## Algorithms & Logic

### Symbol Similarity Algorithm

**AST Similarity**:

```python
def calculate_ast_similarity(ast_a: AST, ast_b: AST) -> float:
    """
    Calculate structural similarity between AST nodes.

    Uses tree edit distance normalized by tree size.
    """
    # Extract structural features
    features_a = extract_ast_features(ast_a)
    features_b = extract_ast_features(ast_b)

    # Calculate edit distance
    distance = tree_edit_distance(features_a, features_b)

    # Normalize by average tree size
    max_size = max(len(features_a), len(features_b))

    return 1.0 - (distance / max_size)

def extract_ast_features(node: AST) -> List[str]:
    """
    Extract structural features from AST.

    Features:
    - Node types
    - Identifier names
    - Literal values (normalized)
    - Control flow structure
    """
    features = []

    for child in ast.walk(node):
        # Node type
        features.append(f"type:{child.__class__.__name__}")

        # Identifiers
        if isinstance(child, ast.Name):
            features.append(f"name:{child.id}")

        # Function/class definitions
        if isinstance(child, (ast.FunctionDef, ast.ClassDef)):
            features.append(f"def:{child.name}")
            # Parameter names
            if isinstance(child, ast.FunctionDef):
                for arg in child.args.args:
                    features.append(f"param:{arg.arg}")

    return features
```

**Docstring Similarity**:

```python
def calculate_docstring_similarity(doc_a: str, doc_b: str) -> float:
    """
    Calculate semantic similarity between docstrings.

    Uses:
    1. Levenshtein distance for exact matching
    2. TF-IDF + cosine similarity for semantic matching
    """
    if not doc_a or not doc_b:
        return 0.0

    # Exact similarity (Levenshtein)
    exact_sim = 1.0 - (
        levenshtein_distance(doc_a, doc_b) / max(len(doc_a), len(doc_b))
    )

    # Semantic similarity (TF-IDF + cosine)
    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform([doc_a, doc_b])
    semantic_sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]

    # Weighted combination
    return exact_sim * 0.3 + semantic_sim * 0.7
```

### Dependency Resolution Algorithm

```python
def resolve_dependencies(operations: List[Operation]) -> List[Operation]:
    """
    Topologically sort operations by dependencies.

    Algorithm:
    1. Build dependency graph
    2. Detect cycles
    3. Topological sort (Kahn's algorithm)
    """
    # Build adjacency list
    graph = defaultdict(list)
    in_degree = defaultdict(int)

    for op in operations:
        if "dependencies" in op.metadata:
            for dep_id in op.metadata["dependencies"]:
                graph[dep_id].append(op.id)
                in_degree[op.id] += 1

    # Find nodes with no incoming edges
    queue = deque([op.id for op in operations if in_degree[op.id] == 0])
    sorted_ops = []

    while queue:
        op_id = queue.popleft()
        sorted_ops.append(op_id)

        for neighbor in graph[op_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Check for cycles
    if len(sorted_ops) != len(operations):
        cycles = find_cycles(graph, in_degree)
        raise DependencyError(f"Circular dependencies detected: {cycles}")

    # Return operations in sorted order
    return [op for op_id in sorted_ops for op in operations if op.id == op_id]
```

---

## Data Flow

### Manifest Generation Flow

```
┌────────────────────┐
│ User invokes CLI   │
│ onx-manifest gen   │
└─────────┬──────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 1. Effect: Git Checkout              │
│    Checkout v0.9.0 and v1.0.0        │
└─────────┬────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 2. Compute: Snapshot Generation      │
│    (Parallel for both refs)          │
│    ├─ File discovery                 │
│    ├─ .tree generation               │
│    ├─ Metadata stamping              │
│    └─ Symbol extraction              │
└─────────┬────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 3. Reducer: Store Snapshots          │
│    artifacts/core_diff/0.9.0_1.0.0/  │
└─────────┬────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 4. Compute: Difference Detection     │
│    Compare snapshots                 │
│    ├─ File diffs                     │
│    ├─ Symbol diffs                   │
│    └─ Metadata diffs                 │
└─────────┬────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 5. Compute: Inference Engine         │
│    Apply inference rules             │
│    ├─ Module moves                   │
│    ├─ Symbol renames                 │
│    ├─ Signature changes              │
│    └─ Config changes                 │
└─────────┬────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 6. Compute: Confidence Scoring       │
│    Score each operation              │
│    ├─ AST similarity                 │
│    ├─ Docstring similarity           │
│    ├─ Usage patterns                 │
│    └─ Weighted score                 │
└─────────┬────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 7. Orchestrator: Dependency Sort     │
│    Topologically sort operations     │
└─────────┬────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 8. Compute: Manifest Synthesis       │
│    Generate YAML manifest            │
└─────────┬────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 9. Orchestrator: Verification        │
│    Apply to test corpus              │
│    Run tests                         │
│    Generate report                   │
└─────────┬────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 10. Effect: Publish to Registry      │
│     registry://core_migrations/...   │
└─────────┬────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────┐
│ 11. Effect: Event Publishing         │
│     Event: core.migration.ready      │
└──────────────────────────────────────┘
```

---

## Integration Architecture

### Tree Service Integration

```python
class TreeServiceClient:
    """Client for Tree Service integration."""

    def __init__(self, base_url: str = "http://localhost:8058"):
        self.base_url = base_url

    async def create_snapshot(
        self,
        repo_path: str,
        ref: str
    ) -> str:
        """
        Request tree snapshot generation.

        POST /api/tree/snapshot
        Returns: snapshot_id
        """
        response = await self.client.post(
            f"{self.base_url}/api/tree/snapshot",
            json={
                "repo_path": repo_path,
                "ref": ref,
                "options": {
                    "include_metadata": True,
                    "include_symbols": True
                }
            }
        )
        return response.json()["snapshot_id"]

    async def get_snapshot(self, snapshot_id: str) -> Snapshot:
        """Retrieve generated snapshot."""
        response = await self.client.get(
            f"{self.base_url}/api/tree/snapshot/{snapshot_id}"
        )
        return Snapshot.from_dict(response.json())
```

### Archon Intelligence Integration

```python
class ArchonIntelligenceClient:
    """Client for Archon Intelligence integration."""

    def __init__(self, base_url: str = "http://localhost:8053"):
        self.base_url = base_url

    async def detect_relationships(
        self,
        source_code: str,
        module_path: str
    ) -> List[Relationship]:
        """
        Use relationship detector for symbol graph.

        Leverages existing Archon relationship detection.
        """
        response = await self.client.post(
            f"{self.base_url}/api/relationships/detect",
            json={
                "source_code": source_code,
                "module_path": module_path
            }
        )
        return [Relationship.from_dict(r) for r in response.json()["relationships"]]

    async def calculate_similarity(
        self,
        code_a: str,
        code_b: str
    ) -> float:
        """
        Calculate structural similarity.

        Uses Archon's pattern scoring.
        """
        response = await self.client.post(
            f"{self.base_url}/api/pattern-learning/semantic/analyze",
            json={
                "code_samples": [code_a, code_b]
            }
        )
        return response.json()["similarity_score"]
```

### Event Bus Integration

**Event Schema**:

```yaml
# core.migration.ready event
event_type: "core.migration.ready"
version: "1.0.0"
timestamp: "2025-11-02T18:00:00Z"

payload:
  core_package: "omnibase_core"
  from_version: "0.9.0"
  to_version: "1.0.0"
  manifest_uri: "registry://core_migrations/0.9.0_1.0.0"
  breaking_changes: 15
  safe_changes: 42
  confidence_avg: 0.89

metadata:
  publisher: "migration-system"
  correlation_id: "uuid-..."
```

**Consumer Pattern**:

```python
class MigrationEventConsumer:
    """Consumer for migration events."""

    async def handle_migration_ready(
        self,
        event: MigrationEvent
    ) -> None:
        """
        Handle core.migration.ready event.

        Actions:
        1. Fetch manifest
        2. Check if package depends on core
        3. Create migration PR
        4. Run tests
        """
        # Check dependency
        if not self._depends_on_core(event.core_package, event.from_version):
            return

        # Fetch manifest
        manifest = await self.registry.fetch_manifest(event.manifest_uri)

        # Apply migration
        result = await self.migrator.apply(
            manifest=manifest,
            target_path=self.package_path,
            dry_run=True
        )

        # Create PR if successful
        if result.success:
            await self.git.create_migration_pr(
                title=f"Migrate to {event.core_package} {event.to_version}",
                body=self._generate_pr_description(manifest, result),
                branch=f"migrate/{event.to_version}"
            )
```

---

## Performance & Scalability

### Performance Targets

| Operation | Target | Measurement |
|-----------|--------|-------------|
| **Snapshot Generation** | <30s for 10k files | Time from checkout to snapshot |
| **Symbol Extraction** | <50ms per file | Parallel processing time |
| **Diff Calculation** | <10s for 10k files | Time to compare snapshots |
| **Inference** | <5s for 100 operations | Time to infer all operations |
| **Confidence Scoring** | <1s for 100 operations | Time to score all |
| **Manifest Generation** | <60s total | End-to-end pipeline |
| **Migration Application** | <30s for 100 files | Time to apply codemods |

### Scalability Strategies

**1. Parallel Processing**

```python
async def process_files_parallel(
    files: List[str],
    processor: Callable,
    max_workers: int = 4
) -> List[Result]:
    """Process files in parallel batches."""
    semaphore = asyncio.Semaphore(max_workers)

    async def process_with_semaphore(file: str) -> Result:
        async with semaphore:
            return await processor(file)

    return await asyncio.gather(*[
        process_with_semaphore(file) for file in files
    ])
```

**2. Incremental Diffing**

```python
def incremental_diff(
    snapshot_a: Snapshot,
    snapshot_b: Snapshot,
    cache: DiffCache
) -> DifferenceSet:
    """
    Only diff files that changed between snapshots.

    Use file hashes to skip unchanged files.
    """
    unchanged = set(snapshot_a.files) & set(snapshot_b.files)
    changed = set(snapshot_a.files) ^ set(snapshot_b.files)

    # Only process changed files
    diffs = []
    for file_path in changed:
        diff = calculate_file_diff(
            snapshot_a.files.get(file_path),
            snapshot_b.files.get(file_path)
        )
        diffs.append(diff)

    return DifferenceSet(diffs)
```

**3. Caching**

```python
class SnapshotCache:
    """Cache snapshots by ref."""

    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)

    def get(self, repo_path: str, ref: str) -> Optional[Snapshot]:
        """Get cached snapshot if exists."""
        cache_key = self._get_cache_key(repo_path, ref)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            return Snapshot.from_file(cache_file)

        return None

    def put(self, repo_path: str, ref: str, snapshot: Snapshot) -> None:
        """Cache snapshot."""
        cache_key = self._get_cache_key(repo_path, ref)
        cache_file = self.cache_dir / f"{cache_key}.json"
        snapshot.to_file(cache_file)
```

---

## Security Model

### Threat Model

**Threats**:
1. Malicious manifest injection
2. Code execution via codemods
3. Supply chain attacks
4. Unauthorized manifest publication
5. Rollback tampering

### Security Controls

**1. Manifest Verification**

```python
class ManifestVerifier:
    """Verify manifest integrity and authenticity."""

    def verify(self, manifest: Manifest, signature: str) -> bool:
        """
        Verify manifest signature.

        Uses EdDSA (Ed25519) signatures.
        """
        public_key = self._get_publisher_key(manifest.publisher)
        content = manifest.to_canonical_json()

        return ed25519_verify(
            public_key=public_key,
            message=content,
            signature=signature
        )
```

**2. Sandboxed Codemod Execution**

```python
class SandboxedMigrator:
    """Apply migrations in sandboxed environment."""

    async def apply(
        self,
        manifest: Manifest,
        target_path: str
    ) -> MigrationResult:
        """
        Apply manifest in sandbox.

        Sandbox constraints:
        - No network access
        - Limited file system access (target_path only)
        - Resource limits (CPU, memory)
        - Timeout (5 minutes)
        """
        async with Sandbox(
            allowed_paths=[target_path],
            network=False,
            timeout=300
        ) as sandbox:
            return await sandbox.run(
                self._apply_operations,
                manifest=manifest,
                target_path=target_path
            )
```

**3. Audit Logging**

```python
class MigrationAuditLogger:
    """Audit log for all migration operations."""

    async def log_generation(
        self,
        manifest_id: str,
        from_version: str,
        to_version: str,
        generator: str
    ) -> None:
        """Log manifest generation."""
        await self.logger.info({
            "event": "manifest_generated",
            "manifest_id": manifest_id,
            "from_version": from_version,
            "to_version": to_version,
            "generator": generator,
            "timestamp": datetime.now(UTC).isoformat()
        })

    async def log_application(
        self,
        manifest_id: str,
        package: str,
        applied_by: str,
        success: bool
    ) -> None:
        """Log manifest application."""
        await self.logger.info({
            "event": "manifest_applied",
            "manifest_id": manifest_id,
            "package": package,
            "applied_by": applied_by,
            "success": success,
            "timestamp": datetime.now(UTC).isoformat()
        })
```

---

## Appendices

### A. Operation Types Reference

| Operation Type | Description | Example |
|---------------|-------------|---------|
| `rename.import` | Module path change | `from old.path import X` → `from new.path import X` |
| `rename.symbol` | Class/function rename | `class OldName` → `class NewName` |
| `rename.callable` | Function/method rename | `old_func()` → `new_func()` |
| `arg.rename` | Parameter rename | `func(old_param=x)` → `func(new_param=x)` |
| `arg.add_default` | New parameter with default | `func(a, b)` → `func(a, b, c=default)` |
| `arg.remove` | Parameter removal | `func(a, b, old)` → `func(a, b)` |
| `config.key_rename` | Config key change | `old_key: value` → `new_key: value` |
| `move.file` | File relocation | `old/path/file.py` → `new/path/file.py` |

### B. Confidence Score Thresholds

| Range | Recommendation | Action |
|-------|---------------|--------|
| **0.9-1.0** | Auto-apply | Apply automatically |
| **0.7-0.9** | Apply with warning | Apply, log warning |
| **0.5-0.7** | Manual review | Flag for human review |
| **<0.5** | High risk | Require manual implementation |

### C. Error Handling

```python
class MigrationError(Exception):
    """Base exception for migration system."""
    pass

class SnapshotError(MigrationError):
    """Snapshot generation failed."""
    pass

class InferenceError(MigrationError):
    """Inference failed to produce operations."""
    pass

class DependencyError(MigrationError):
    """Circular dependency detected."""
    pass

class VerificationError(MigrationError):
    """Verification failed."""
    pass

class ApplicationError(MigrationError):
    """Migration application failed."""
    pass
```

---

**Document Status**: Architecture - Ready for Implementation
**Next Steps**: Build MVP snapshot generator and inference engine
**Related Documents**:
- [Planning Document](../planning/AUTOMATED_CORE_MIGRATION_SYSTEM.md)
- [ONEX Guide](../onex/ONEX_4_Node_System_Developer_Guide.md)
- [Archon Intelligence APIs](../api/)
