# File Tree/Graph Visualization & Orphan Detection - Implementation Plan

**Status**: Planning Phase
**Priority**: High
**Target Release**: Q1 2025
**Owner**: Intelligence Team
**Document Version**: 1.0
**Last Updated**: 2025-11-07
**Next Review**: 2025-11-14

---

## Executive Summary

This document outlines the implementation plan for adding comprehensive file-level graph visualization and orphan detection capabilities to Archon Intelligence. Currently, Archon indexes entity-level nodes (classes, functions, variables) but lacks file-level nodes, directory hierarchy, and file-to-file import relationships. This creates a critical gap in architectural intelligence, preventing queries like "Find all orphaned files," "Show dependency chains," or "Visualize file tree with import overlays."

**Key Deliverables**:
1. File-level nodes in Memgraph knowledge graph
2. Directory hierarchy graph (Project → Directory → File)
3. File-to-file IMPORTS relationships
4. Orphan detection queries and APIs
5. Enhanced file path searchability in RAG queries
6. Interactive file tree visualization API

**Expected Impact**:
- ✅ Enable architectural queries (dependency analysis, impact assessment)
- ✅ Identify dead code and orphaned files automatically
- ✅ Improve code navigation via file path search
- ✅ Visualize project structure with dependency overlays
- ✅ Support refactoring decisions with reachability analysis

**Timeline**: 3-4 weeks (phased rollout)

---

## Problem Statement

### Current State

**What Exists**:
- ✅ Entity-level nodes: Classes, functions, variables stored in Memgraph
- ✅ Entity relationships: DEFINES, CALLS, INHERITS between entities
- ✅ Document content: Full text indexed in Qdrant vector DB
- ✅ Code relationship detector: AST-based import extraction (not integrated)
- ✅ Pattern learning: ONEX compliance scoring

**What's Missing**:
- ❌ **No file-level nodes**: Cannot query "all files in project"
- ❌ **No directory hierarchy**: Cannot navigate project structure in graph
- ❌ **No file-to-file imports**: Cannot trace dependency chains
- ❌ **No orphan detection**: Cannot identify unreferenced files
- ❌ **Limited file path search**: File paths not prominently indexed in embeddings
- ❌ **No tree visualization**: Cannot render project structure graphically

### Desired State

**Target Architecture**:
```
Memgraph Knowledge Graph:
  (:PROJECT)-[:CONTAINS]→(:DIRECTORY)-[:CONTAINS]→(:FILE)
                                      ↓
                            (:FILE)-[:IMPORTS]→(:FILE)
                                      ↓
                            (:FILE)-[:DEFINES]→(:ENTITY)
```

**Capabilities**:
- ✅ Query: "Show all files in `services/intelligence` directory"
- ✅ Query: "Find files that import `app.py`"
- ✅ Query: "List orphaned files (no incoming imports)"
- ✅ Query: "Show dependency chain from `main.py` to `models.py`"
- ✅ Query: "Find unreachable files from entry points"
- ✅ Search: "Find file by partial path (e.g., `**/models/*.py`)"
- ✅ Visualize: Interactive file tree with dependency arrows

### Use Cases

**1. Orphan Detection** (Primary)
- Developer wants to clean up unused files before deployment
- CI/CD pipeline flags orphaned files in pull requests
- Automated refactoring tools identify dead code

**2. Dependency Analysis**
- Architect needs to understand file dependency chains
- Developer wants to assess impact of changing a file
- Team lead needs to identify circular dependencies

**3. Code Navigation**
- Developer searches for file by partial path
- Code review needs to find all files importing a module
- Onboarding developer explores project structure visually

**4. Refactoring Support**
- Team plans to split monolithic file into modules
- Developer needs to find all files that would be affected
- Architect designs new service boundaries based on file clusters

---

## Research Findings

### Context: Multi-Agent Research (2025-11-07)

Five specialized research agents analyzed the OmniNode platform architecture to identify patterns and integration opportunities. Key findings:

#### Agent 1: Graph Visualization Research
**Source**: `/Volumes/PRO-G40/Code/omninode/docs/yc/04_EVENT_MANAGEMENT.md`

**Key Findings**:
- OmniNode uses **triple-layer indexing**: Symbols (entities) → Files → Projects
- `.onextree` directory structure provides file-level metadata
- Metadata stamping service generates ONEX metadata for each file
- Event bus architecture enables asynchronous graph updates

**Relevance to Archon**:
- Archon already has entity layer (symbols) ✅
- Need to add file layer (missing) ❌
- Need to add project layer (missing) ❌
- Event bus integration via archon-bridge ✅

#### Agent 2: Orphan Detection Research
**Source**: `/Volumes/PRO-G40/Code/omninode/docs/FUTURE_FUNCTIONALITY_LEGACY_MIGRATION.md`

**Key Findings**:
- OmniNode plans "Dead Code Detector" functionality
- Vision includes import graph traversal from entry points
- Orphan definition: Files with no incoming imports AND unreachable from mains
- Recommendation: Graph-based reachability analysis

**Relevance to Archon**:
- Memgraph is ideal for reachability queries (Cypher path matching)
- Need FILE nodes to build import graph
- Entry point detection: `main.py`, `app.py`, `__main__.py`

#### Agent 3: File Path Search Research
**Source**: `/Volumes/PRO-G40/Code/omninode_bridge/.onextree/structure.json`

**Key Findings**:
- OnexTree maintains hierarchical structure in JSON
- File metadata includes `relative_path`, `absolute_path`, `file_hash`
- Path search requires both exact and fuzzy matching
- Embedding enhancement: Include file path in vectorized content

**Relevance to Archon**:
- Qdrant metadata filtering supports path patterns ✅
- Need to enhance embedding content with file paths
- Current: `services/intelligence/app.py:2642` (embedding creation)

#### Agent 4: Dependency Tracking Research
**Source**: `/Volumes/PRO-G40/Code/omninode/docs/FUTURE_FUNCTIONALITY_LEGACY_MIGRATION.md`

**Key Findings**:
- Import analysis requires AST parsing (Python) and pattern matching (other languages)
- File imports map to: `(FILE)-[:IMPORTS {type: "module|class|function"}]->(FILE)`
- Circular dependency detection via Cypher cycle detection
- Dependency depth analysis for refactoring planning

**Relevance to Archon**:
- CodeRelationshipDetector already extracts imports ✅
- Location: `services/langextract/analysis/code_relationship_detector.py`
- Need integration into document processing pipeline (currently unused)

#### Agent 5: Integration Patterns Research
**Source**: `/Volumes/PRO-G40/Code/omniarchon/CLAUDE.md`, Event Bus Architecture

**Key Findings**:
- Archon uses event-driven architecture via Kafka/Redpanda
- Document indexing triggers: `dev.archon-intelligence.tree.index.v1`
- Metadata stamping: `dev.archon-intelligence.stamping.generate.v1`
- Integration point: `services/intelligence/app.py:2537` (_process_document_background)

**Relevance to Archon**:
- Extend existing document processing pipeline
- Add file node creation before entity storage
- Add directory hierarchy indexing step
- Maintain event-driven async pattern

### Architecture Patterns Identified

**Pattern 1: Hierarchical Graph Modeling**
```
OmniNode Pattern:
  Project → Directories → Files → Symbols

Archon Implementation:
  (:PROJECT) -[:CONTAINS]→ (:DIRECTORY)
  (:DIRECTORY) -[:CONTAINS]→ (:DIRECTORY|FILE)
  (:FILE) -[:DEFINES]→ (:ENTITY)
  (:FILE) -[:IMPORTS]→ (:FILE)
```

**Pattern 2: Event-Driven Indexing**
```
Kafka Event → Document Processing → Graph Update → Vector Indexing
                                   ↓
                         (NEW) File Node Creation
                         (NEW) Directory Hierarchy Update
                         (NEW) Import Relationship Extraction
```

**Pattern 3: Hybrid Search Enhancement**
```
Current: Entity embeddings + metadata filtering
Enhanced: File path embeddings + directory filtering + import relationship scoring
```

---

## Technical Design

### Phase 1: Enhance Memgraph Schema (Week 1)

#### 1.1 File Node Creation

**Implementation Location**: `services/intelligence/app.py`
**Target Function**: `_process_document_background` (line 2537)

**Current Flow**:
```python
async def _process_document_background(...):
    # Step 1: Store entities in Memgraph  ← Line 2577
    # Step 2: Store relationships          ← Line 2594
    # Step 3: Vectorize document           ← Line 2642
    # Step 4: Trigger freshness analysis   ← Line 2714
```

**Enhanced Flow** (NEW):
```python
async def _process_document_background(...):
    # NEW Step 0: Create file node
    await _create_file_node(document_id, source_path, metadata, project_id)

    # Step 1: Store entities in Memgraph
    # Step 2: Store relationships
    # Step 3: Store file-level imports (NEW)
    # Step 4: Vectorize document (enhanced with path)
    # Step 5: Trigger freshness analysis
```

**Schema Definition**:
```cypher
CREATE (file:FILE {
  entity_id: $file_id,               // e.g., "file:omniarchon:services/app.py"
  name: $filename,                    // e.g., "app.py"
  path: $absolute_path,               // e.g., "/Volumes/.../services/app.py"
  relative_path: $relative_path,      // e.g., "services/intelligence/app.py"
  project_name: $project_name,        // e.g., "omniarchon"
  file_size: $size_bytes,             // e.g., 125430
  language: $language,                // e.g., "python"
  file_hash: $blake3_hash,            // e.g., "a7f5c..."
  last_modified: $timestamp,          // e.g., "2025-11-07T12:00:00Z"
  created_at: $timestamp,
  indexed_at: $timestamp,
  content_type: $type,                // e.g., "code", "documentation", "config"
  line_count: $lines,                 // e.g., 2850
  entity_count: $num_entities,        // e.g., 45 (classes + functions)
  import_count: $num_imports          // e.g., 23
})
```

**Implementation Code**:
```python
# Location: services/intelligence/app.py (NEW function after line 2537)

async def _create_file_node(
    document_id: str,
    source_path: str,
    metadata: dict,
    project_id: str
) -> bool:
    """
    Create FILE node in Memgraph knowledge graph.

    Args:
        document_id: Unique document identifier
        source_path: Absolute file path
        metadata: Document metadata (language, size, etc.)
        project_id: Project identifier

    Returns:
        True if successful, False otherwise
    """
    if not memgraph_adapter:
        logger.warning("⚠️ Memgraph adapter not initialized, skipping file node creation")
        return False

    try:
        # Extract file metadata
        from pathlib import Path
        import hashlib

        file_path = Path(source_path)
        filename = file_path.name
        relative_path = metadata.get("relative_path", str(file_path))

        # Create file node
        file_node_data = {
            "entity_id": f"file:{project_id}:{relative_path}",
            "name": filename,
            "path": source_path,
            "relative_path": relative_path,
            "project_name": project_id,
            "file_size": metadata.get("file_size", 0),
            "language": metadata.get("language", "unknown"),
            "file_hash": metadata.get("file_hash", ""),
            "last_modified": metadata.get("last_modified", datetime.now(timezone.utc).isoformat()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "content_type": metadata.get("content_type", "code"),
            "line_count": metadata.get("line_count", 0),
            "entity_count": 0,  # Will be updated after entity extraction
            "import_count": 0   # Will be updated after import extraction
        }

        await memgraph_adapter.create_file_node(file_node_data)

        logger.info(
            f"✅ [FILE NODE] Created | "
            f"file={filename} | "
            f"path={relative_path} | "
            f"language={file_node_data['language']}"
        )

        return True

    except Exception as e:
        logger.error(f"❌ [FILE NODE] Creation failed: {e}")
        return False
```

**Memgraph Adapter Enhancement**:
```python
# Location: services/intelligence/storage/memgraph_adapter.py (NEW method after line 100)

async def create_file_node(self, file_data: dict) -> bool:
    """
    Create or update FILE node in knowledge graph.

    Args:
        file_data: File metadata dictionary

    Returns:
        True if successful, False otherwise
    """
    query = """
    MERGE (file:FILE {entity_id: $entity_id})
    SET file.name = $name,
        file.path = $path,
        file.relative_path = $relative_path,
        file.project_name = $project_name,
        file.file_size = $file_size,
        file.language = $language,
        file.file_hash = $file_hash,
        file.last_modified = $last_modified,
        file.indexed_at = $indexed_at,
        file.content_type = $content_type,
        file.line_count = $line_count
    RETURN file.entity_id as created_id
    """

    async with self.driver.session() as session:
        result = await session.run(query, **file_data)
        record = await result.single()
        return record is not None
```

**Estimated Effort**: 4 hours
**Testing**: Unit tests for file node creation, validation of schema

---

#### 1.2 File-Level Import Extraction

**Integration Location**: `services/intelligence/app.py`
**Enhancement Location**: `services/langextract/analysis/code_relationship_detector.py`

**Current State**:
- CodeRelationshipDetector exists (line 42) ✅
- Extracts IMPORTS, INHERITANCE, CALLS relationships ✅
- **NOT integrated into document processing pipeline** ❌

**Integration Strategy**:

**Step 1: Extract file imports during entity processing**
```python
# Location: services/intelligence/app.py (enhance existing entity extraction)

from services.langextract.analysis.code_relationship_detector import CodeRelationshipDetector

# Initialize detector (add to app startup)
code_relationship_detector = CodeRelationshipDetector()

# Modify _process_document_background (after line 2594)
async def _process_document_background(...):
    # ... existing code ...

    # NEW Step 3: Extract file-level imports
    if metadata.get("language") in ["python", "py", "javascript", "typescript", "go"]:
        file_imports = await code_relationship_detector.detect_relationships(
            content=full_text,
            language=metadata["language"],
            document_path=source_path
        )

        # Filter for IMPORTS relationships only
        import_relationships = [
            rel for rel in file_imports
            if rel.relationship_type == "IMPORTS"
        ]

        # Store file-to-file import relationships
        await _store_file_imports(
            source_file=f"file:{project_id}:{metadata['relative_path']}",
            import_relationships=import_relationships,
            project_id=project_id
        )

        logger.info(
            f"📦 [FILE IMPORTS] Extracted {len(import_relationships)} imports | "
            f"file={metadata['relative_path']}"
        )
```

**Step 2: Create file import storage function**
```python
# Location: services/intelligence/app.py (NEW function)

async def _store_file_imports(
    source_file: str,
    import_relationships: List[CodeRelationship],
    project_id: str
) -> int:
    """
    Store file-to-file import relationships in Memgraph.

    Args:
        source_file: Source file entity_id
        import_relationships: List of import relationships
        project_id: Project identifier

    Returns:
        Number of relationships created
    """
    if not memgraph_adapter or not import_relationships:
        return 0

    stored_count = 0

    for rel in import_relationships:
        try:
            # Resolve target file path
            target_file_id = f"file:{project_id}:{rel.target}"

            # Create IMPORTS relationship
            await memgraph_adapter.create_file_import_relationship(
                source_id=source_file,
                target_id=target_file_id,
                import_type=rel.properties.get("import_type", "module"),
                confidence=rel.confidence
            )

            stored_count += 1

        except Exception as e:
            logger.warning(f"⚠️ Failed to store import relationship: {e}")

    return stored_count
```

**Step 3: Add Memgraph adapter method**
```python
# Location: services/intelligence/storage/memgraph_adapter.py (NEW method)

async def create_file_import_relationship(
    self,
    source_id: str,
    target_id: str,
    import_type: str = "module",
    confidence: float = 1.0
) -> bool:
    """
    Create IMPORTS relationship between files.

    Args:
        source_id: Source file entity_id
        target_id: Target file entity_id
        import_type: Type of import (module, class, function)
        confidence: Confidence score (0.0-1.0)

    Returns:
        True if successful, False otherwise
    """
    query = """
    MATCH (source:FILE {entity_id: $source_id})
    MERGE (target:FILE {entity_id: $target_id})
    MERGE (source)-[r:IMPORTS]->(target)
    SET r.import_type = $import_type,
        r.confidence = $confidence,
        r.created_at = $timestamp
    RETURN r
    """

    async with self.driver.session() as session:
        result = await session.run(
            query,
            source_id=source_id,
            target_id=target_id,
            import_type=import_type,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        record = await result.single()
        return record is not None
```

**Estimated Effort**: 5 hours
**Testing**: Integration tests for import extraction and storage

---

#### 1.3 Directory Hierarchy Graph

**New Service**: `services/intelligence/src/services/directory_indexer.py`

**Purpose**:
- Build hierarchical project structure: Project → Directory → File
- Create CONTAINS relationships
- Support directory-level queries

**Implementation**:
```python
# Location: services/intelligence/src/services/directory_indexer.py (NEW FILE)

"""
Directory Hierarchy Indexer

Builds and maintains directory hierarchy in Memgraph knowledge graph.
Creates PROJECT, DIRECTORY nodes and CONTAINS relationships.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DirectoryIndexer:
    """
    Indexes directory hierarchy for project structure visualization.
    """

    def __init__(self, memgraph_adapter):
        """
        Initialize directory indexer.

        Args:
            memgraph_adapter: Memgraph adapter instance
        """
        self.memgraph = memgraph_adapter

    async def index_directory_hierarchy(
        self,
        project_name: str,
        project_root: str,
        file_paths: List[str]
    ) -> Dict[str, int]:
        """
        Index complete directory hierarchy for a project.

        Args:
            project_name: Project identifier
            project_root: Absolute path to project root
            file_paths: List of file paths to index

        Returns:
            Dictionary with counts: {projects, directories, files, relationships}
        """
        stats = {
            "projects": 0,
            "directories": 0,
            "files": 0,
            "relationships": 0
        }

        try:
            # Step 1: Create project node
            await self._create_project_node(project_name, project_root)
            stats["projects"] = 1

            # Step 2: Extract unique directories
            directories = self._extract_directories(file_paths, project_root)

            # Step 3: Create directory nodes
            for dir_path in sorted(directories):
                await self._create_directory_node(project_name, dir_path)
                stats["directories"] += 1

            # Step 4: Create hierarchy relationships
            # Project → Top-level directories
            top_level_dirs = [
                d for d in directories
                if str(Path(d).parent) == project_root
            ]

            for dir_path in top_level_dirs:
                await self._create_contains_relationship(
                    parent_id=f"project:{project_name}",
                    child_id=f"dir:{project_name}:{dir_path}",
                    parent_type="PROJECT",
                    child_type="DIRECTORY"
                )
                stats["relationships"] += 1

            # Directory → Subdirectories
            for dir_path in directories:
                parent_path = str(Path(dir_path).parent)
                if parent_path in directories:
                    await self._create_contains_relationship(
                        parent_id=f"dir:{project_name}:{parent_path}",
                        child_id=f"dir:{project_name}:{dir_path}",
                        parent_type="DIRECTORY",
                        child_type="DIRECTORY"
                    )
                    stats["relationships"] += 1

            # Directory → Files
            for file_path in file_paths:
                dir_path = str(Path(file_path).parent)
                await self._create_contains_relationship(
                    parent_id=f"dir:{project_name}:{dir_path}",
                    child_id=f"file:{project_name}:{file_path}",
                    parent_type="DIRECTORY",
                    child_type="FILE"
                )
                stats["relationships"] += 1

            stats["files"] = len(file_paths)

            logger.info(
                f"✅ [DIR INDEX] Hierarchy indexed | "
                f"project={project_name} | "
                f"stats={stats}"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ [DIR INDEX] Failed: {e}")
            raise

    async def _create_project_node(self, project_name: str, project_root: str):
        """Create PROJECT node"""
        query = """
        MERGE (project:PROJECT {entity_id: $entity_id})
        SET project.name = $name,
            project.path = $path,
            project.indexed_at = $timestamp
        RETURN project.entity_id
        """

        async with self.memgraph.driver.session() as session:
            await session.run(
                query,
                entity_id=f"project:{project_name}",
                name=project_name,
                path=project_root,
                timestamp=datetime.now(timezone.utc).isoformat()
            )

    async def _create_directory_node(self, project_name: str, dir_path: str):
        """Create DIRECTORY node"""
        query = """
        MERGE (dir:DIRECTORY {entity_id: $entity_id})
        SET dir.name = $name,
            dir.path = $path,
            dir.project_name = $project_name,
            dir.indexed_at = $timestamp
        RETURN dir.entity_id
        """

        dir_name = Path(dir_path).name

        async with self.memgraph.driver.session() as session:
            await session.run(
                query,
                entity_id=f"dir:{project_name}:{dir_path}",
                name=dir_name,
                path=dir_path,
                project_name=project_name,
                timestamp=datetime.now(timezone.utc).isoformat()
            )

    async def _create_contains_relationship(
        self,
        parent_id: str,
        child_id: str,
        parent_type: str,
        child_type: str
    ):
        """Create CONTAINS relationship"""
        query = f"""
        MATCH (parent:{parent_type} {{entity_id: $parent_id}})
        MATCH (child:{child_type} {{entity_id: $child_id}})
        MERGE (parent)-[r:CONTAINS]->(child)
        SET r.created_at = $timestamp
        RETURN r
        """

        async with self.memgraph.driver.session() as session:
            await session.run(
                query,
                parent_id=parent_id,
                child_id=child_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            )

    def _extract_directories(
        self,
        file_paths: List[str],
        project_root: str
    ) -> List[str]:
        """Extract unique directory paths from file paths"""
        directories = set()

        for file_path in file_paths:
            path = Path(file_path)
            # Add all parent directories up to project root
            for parent in path.parents:
                parent_str = str(parent)
                if parent_str.startswith(project_root):
                    directories.add(parent_str)

        return list(directories)
```

**Integration Point**:
```python
# Location: services/intelligence/app.py (NEW endpoint)

from src.services.directory_indexer import DirectoryIndexer

# Initialize indexer
directory_indexer = DirectoryIndexer(memgraph_adapter)

@app.post("/api/intelligence/index-directory-hierarchy")
async def index_directory_hierarchy(
    project_name: str,
    project_root: str,
    file_paths: List[str]
):
    """
    Index directory hierarchy for a project.

    This is typically called after bulk ingestion to build
    the complete project structure.
    """
    try:
        stats = await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=project_root,
            file_paths=file_paths
        )

        return {
            "status": "success",
            "project": project_name,
            "statistics": stats
        }

    except Exception as e:
        logger.error(f"Directory hierarchy indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Estimated Effort**: 6 hours
**Testing**: Integration tests for hierarchy building, relationship validation

---

### Phase 2: Orphan Detection (Week 2)

#### 2.1 Orphan Detection Service

**New Service**: `services/intelligence/src/services/orphan_detector.py`

**Implementation**:
```python
# Location: services/intelligence/src/services/orphan_detector.py (NEW FILE)

"""
Orphan File Detection Service

Identifies orphaned and unreachable files in a project using graph analysis.

Orphan Types:
1. **No Incoming Imports**: Files that no other file imports
2. **Unreachable from Entry Points**: Files not in dependency chain from main files
3. **Dead Code**: Orphaned files that also define no used entities
"""

import logging
from typing import Dict, List, Optional, Set
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class OrphanFile(BaseModel):
    """Represents an orphaned file"""
    file_path: str
    relative_path: str
    orphan_type: str  # "no_imports", "unreachable", "dead_code"
    reason: str
    entry_point_distance: Optional[int] = None  # Hops from nearest entry point
    import_count: int = 0  # Outgoing imports
    entity_count: int = 0  # Defined entities
    last_modified: Optional[str] = None


class OrphanDetectionResult(BaseModel):
    """Result of orphan detection analysis"""
    project: str
    orphaned_files: List[OrphanFile]
    unreachable_files: List[OrphanFile]
    dead_code_files: List[OrphanFile]
    total_files: int
    total_orphans: int
    entry_points: List[str]
    scan_timestamp: str


class OrphanDetector:
    """
    Detects orphaned and unreachable files using Memgraph graph queries.
    """

    def __init__(self, memgraph_adapter):
        """
        Initialize orphan detector.

        Args:
            memgraph_adapter: Memgraph adapter instance
        """
        self.memgraph = memgraph_adapter

        # Entry point patterns
        self.entry_point_patterns = [
            "main.py",
            "app.py",
            "__main__.py",
            "manage.py",
            "server.py",
            "index.py",
            "cli.py"
        ]

    async def detect_orphans(
        self,
        project_name: str,
        custom_entry_points: Optional[List[str]] = None
    ) -> OrphanDetectionResult:
        """
        Detect all types of orphaned files in a project.

        Args:
            project_name: Project to analyze
            custom_entry_points: Optional custom entry point file names

        Returns:
            OrphanDetectionResult with all orphaned files
        """
        from datetime import datetime, timezone

        try:
            # Step 1: Identify entry points
            entry_points = await self._find_entry_points(
                project_name,
                custom_entry_points
            )

            logger.info(
                f"🔍 [ORPHAN] Starting detection | "
                f"project={project_name} | "
                f"entry_points={len(entry_points)}"
            )

            # Step 2: Find files with no incoming imports
            no_import_files = await self._find_no_incoming_imports(project_name)

            # Step 3: Find unreachable files from entry points
            unreachable_files = await self._find_unreachable_files(
                project_name,
                entry_points
            )

            # Step 4: Find dead code (orphaned + no used entities)
            dead_code_files = await self._find_dead_code(project_name)

            # Step 5: Get total file count
            total_files = await self._count_project_files(project_name)

            result = OrphanDetectionResult(
                project=project_name,
                orphaned_files=no_import_files,
                unreachable_files=unreachable_files,
                dead_code_files=dead_code_files,
                total_files=total_files,
                total_orphans=len(no_import_files),
                entry_points=[ep["path"] for ep in entry_points],
                scan_timestamp=datetime.now(timezone.utc).isoformat()
            )

            logger.info(
                f"✅ [ORPHAN] Detection complete | "
                f"orphans={result.total_orphans} | "
                f"unreachable={len(unreachable_files)} | "
                f"dead_code={len(dead_code_files)}"
            )

            return result

        except Exception as e:
            logger.error(f"❌ [ORPHAN] Detection failed: {e}")
            raise

    async def _find_entry_points(
        self,
        project_name: str,
        custom_patterns: Optional[List[str]] = None
    ) -> List[Dict]:
        """Find entry point files in project"""
        patterns = custom_patterns or self.entry_point_patterns

        query = """
        MATCH (project:PROJECT {name: $project_name})-[:CONTAINS*]->(file:FILE)
        WHERE file.name IN $patterns
        RETURN file.entity_id as id,
               file.path as path,
               file.relative_path as relative_path
        ORDER BY file.name
        """

        async with self.memgraph.driver.session() as session:
            result = await session.run(
                query,
                project_name=project_name,
                patterns=patterns
            )

            records = await result.values()
            return [
                {"id": r[0], "path": r[1], "relative_path": r[2]}
                for r in records
            ]

    async def _find_no_incoming_imports(
        self,
        project_name: str
    ) -> List[OrphanFile]:
        """Find files with no incoming IMPORTS relationships"""
        query = """
        MATCH (project:PROJECT {name: $project_name})-[:CONTAINS*]->(file:FILE)
        WHERE NOT (file)<-[:IMPORTS]-()
          AND NOT file.name IN ['__init__.py', '__pycache__']
        RETURN file.path as path,
               file.relative_path as relative_path,
               file.import_count as imports,
               file.entity_count as entities,
               file.last_modified as modified
        ORDER BY file.relative_path
        """

        async with self.memgraph.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            records = await result.values()

            return [
                OrphanFile(
                    file_path=r[0],
                    relative_path=r[1],
                    orphan_type="no_imports",
                    reason="No other files import this file",
                    import_count=r[2] or 0,
                    entity_count=r[3] or 0,
                    last_modified=r[4]
                )
                for r in records
            ]

    async def _find_unreachable_files(
        self,
        project_name: str,
        entry_points: List[Dict]
    ) -> List[OrphanFile]:
        """Find files unreachable from entry points via import chains"""
        if not entry_points:
            logger.warning("No entry points found, skipping reachability analysis")
            return []

        # Get all reachable files
        entry_point_ids = [ep["id"] for ep in entry_points]

        query = """
        MATCH path = (entry:FILE)-[:IMPORTS*0..10]->(reachable:FILE)
        WHERE entry.entity_id IN $entry_point_ids
        WITH COLLECT(DISTINCT reachable.entity_id) AS reachable_ids

        MATCH (project:PROJECT {name: $project_name})-[:CONTAINS*]->(file:FILE)
        WHERE NOT file.entity_id IN reachable_ids
          AND NOT file.name IN ['__init__.py']
        RETURN file.path as path,
               file.relative_path as relative_path,
               file.import_count as imports,
               file.entity_count as entities,
               file.last_modified as modified
        ORDER BY file.relative_path
        """

        async with self.memgraph.driver.session() as session:
            result = await session.run(
                query,
                entry_point_ids=entry_point_ids,
                project_name=project_name
            )
            records = await result.values()

            return [
                OrphanFile(
                    file_path=r[0],
                    relative_path=r[1],
                    orphan_type="unreachable",
                    reason=f"Not reachable from entry points: {', '.join([ep['relative_path'] for ep in entry_points[:3]])}",
                    import_count=r[2] or 0,
                    entity_count=r[3] or 0,
                    last_modified=r[4]
                )
                for r in records
            ]

    async def _find_dead_code(self, project_name: str) -> List[OrphanFile]:
        """Find dead code files (no imports AND entities not used)"""
        query = """
        MATCH (project:PROJECT {name: $project_name})-[:CONTAINS*]->(file:FILE)
        WHERE NOT (file)<-[:IMPORTS]-()
          AND NOT (file)-[:DEFINES]->()<-[:CALLS|EXTENDS]-()
          AND NOT file.name IN ['__init__.py']
        RETURN file.path as path,
               file.relative_path as relative_path,
               file.entity_count as entities,
               file.last_modified as modified
        ORDER BY file.relative_path
        """

        async with self.memgraph.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            records = await result.values()

            return [
                OrphanFile(
                    file_path=r[0],
                    relative_path=r[1],
                    orphan_type="dead_code",
                    reason="File has no imports and defines no used entities",
                    import_count=0,
                    entity_count=r[2] or 0,
                    last_modified=r[3]
                )
                for r in records
            ]

    async def _count_project_files(self, project_name: str) -> int:
        """Count total files in project"""
        query = """
        MATCH (project:PROJECT {name: $project_name})-[:CONTAINS*]->(file:FILE)
        RETURN count(file) as total
        """

        async with self.memgraph.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            record = await result.single()
            return record["total"] if record else 0
```

**Estimated Effort**: 8 hours
**Testing**: Unit tests for each orphan type, integration tests with sample projects

---

#### 2.2 Orphan Detection API

**Implementation Location**: `services/intelligence/app.py`

```python
# Location: services/intelligence/app.py (NEW endpoints)

from src.services.orphan_detector import OrphanDetector, OrphanDetectionResult

# Initialize detector
orphan_detector = OrphanDetector(memgraph_adapter)


@app.get("/api/intelligence/orphans/detect/{project_name}")
async def detect_orphans(
    project_name: str,
    entry_points: Optional[str] = Query(None, description="Comma-separated entry point file names")
) -> OrphanDetectionResult:
    """
    Detect orphaned and unreachable files in a project.

    Args:
        project_name: Project to analyze
        entry_points: Optional custom entry points (e.g., "main.py,app.py")

    Returns:
        OrphanDetectionResult with categorized orphaned files

    Example:
        GET /api/intelligence/orphans/detect/omniarchon
        GET /api/intelligence/orphans/detect/omniarchon?entry_points=main.py,server.py
    """
    try:
        custom_entry_points = (
            entry_points.split(",") if entry_points else None
        )

        result = await orphan_detector.detect_orphans(
            project_name=project_name,
            custom_entry_points=custom_entry_points
        )

        return result

    except Exception as e:
        logger.error(f"Orphan detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/intelligence/orphans/summary/{project_name}")
async def get_orphan_summary(project_name: str):
    """
    Get quick summary of orphaned files.

    Returns:
        Summary statistics without full file lists
    """
    try:
        result = await orphan_detector.detect_orphans(project_name=project_name)

        return {
            "project": project_name,
            "total_files": result.total_files,
            "orphan_count": result.total_orphans,
            "unreachable_count": len(result.unreachable_files),
            "dead_code_count": len(result.dead_code_files),
            "orphan_percentage": round(
                (result.total_orphans / result.total_files * 100)
                if result.total_files > 0 else 0,
                2
            ),
            "entry_points": result.entry_points,
            "scan_timestamp": result.scan_timestamp
        }

    except Exception as e:
        logger.error(f"Orphan summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**API Response Example**:
```json
{
  "project": "omniarchon",
  "orphaned_files": [
    {
      "file_path": "/Volumes/.../unused_module.py",
      "relative_path": "services/unused_module.py",
      "orphan_type": "no_imports",
      "reason": "No other files import this file",
      "import_count": 5,
      "entity_count": 3,
      "last_modified": "2025-10-15T10:30:00Z"
    }
  ],
  "unreachable_files": [
    {
      "file_path": "/Volumes/.../legacy_handler.py",
      "relative_path": "services/legacy_handler.py",
      "orphan_type": "unreachable",
      "reason": "Not reachable from entry points: main.py, app.py",
      "import_count": 2,
      "entity_count": 8,
      "last_modified": "2024-08-20T14:00:00Z"
    }
  ],
  "dead_code_files": [],
  "total_files": 245,
  "total_orphans": 12,
  "entry_points": [
    "services/intelligence/app.py",
    "services/bridge/app.py"
  ],
  "scan_timestamp": "2025-11-07T15:30:00Z"
}
```

**Estimated Effort**: 3 hours
**Testing**: API integration tests, response validation

---

### Phase 3: Enhanced File Path Search (Week 2-3)

#### 3.1 Embedding Enhancement

**Location**: `services/intelligence/app.py:2642`

**Current Implementation**:
```python
# Line 2642 (simplified)
embedding_content = f"{full_text}\n\nMetadata: {metadata}"
```

**Enhanced Implementation**:
```python
# Location: services/intelligence/app.py (modify embedding creation)

def _prepare_embedding_content(full_text: str, metadata: dict) -> str:
    """
    Prepare content for embedding with enhanced file path emphasis.

    Strategy:
    - Include file path 3x times for prominence
    - Add path components separately (directory names)
    - Include filename variations (with/without extension)

    This significantly improves file path search recall.
    """
    file_path = metadata.get("relative_path", "")
    filename = metadata.get("filename", "")

    # Extract path components
    from pathlib import Path
    path_obj = Path(file_path)
    directory = str(path_obj.parent)
    filename_no_ext = path_obj.stem
    extension = path_obj.suffix

    # Build enhanced content
    path_emphasis = (
        f"FILE_PATH: {file_path}\n"
        f"FILE_NAME: {filename}\n"
        f"FILE_NAME_NO_EXT: {filename_no_ext}\n"
        f"DIRECTORY: {directory}\n"
        f"FILE_EXTENSION: {extension}\n"
        f"PATH_COMPONENTS: {' > '.join(path_obj.parts)}\n"
        f"SEARCHABLE_PATH: {file_path.replace('/', ' ')}\n"
        f"\n"
    )

    # Repeat path emphasis for higher embedding weight
    embedding_content = (
        f"{path_emphasis}"
        f"{path_emphasis}"  # 2x repetition
        f"{full_text}\n\n"
        f"Metadata: {metadata}"
    )

    return embedding_content


# Modify vectorization call (line 2642)
embedding_content = _prepare_embedding_content(full_text, metadata)
```

**Expected Impact**:
- File path queries: 40% → 85% recall improvement
- Partial path matching: "services/intelligence" finds relevant files
- Filename-only queries: "app.py" returns all app.py files across directories

**Estimated Effort**: 2 hours
**Testing**: A/B testing with path-based queries

---

#### 3.2 Path Pattern Filtering

**Location**: `services/search/engines/qdrant_adapter.py`

**Current Filtering** (line 461):
```python
# Basic metadata filtering
if metadata_filter:
    query_filter = {"must": [metadata_filter]}
```

**Enhanced Filtering**:
```python
# Location: services/search/engines/qdrant_adapter.py (enhance filtering)

def _build_path_pattern_filter(path_pattern: str) -> dict:
    """
    Build Qdrant filter for path pattern matching.

    Supports:
    - Exact: "services/intelligence/app.py"
    - Wildcard: "services/**/app.py"
    - Partial: "**/models/*.py"
    - Directory: "services/intelligence/*"
    """
    import re
    from qdrant_client.http import models

    # Convert glob pattern to regex
    regex_pattern = (
        path_pattern
        .replace("**", ".*")
        .replace("*", "[^/]*")
        .replace("?", ".")
    )

    return {
        "key": "relative_path",
        "match": {
            "text": regex_pattern
        }
    }


# Enhance search API to accept path patterns
async def hybrid_search(
    query: str,
    path_pattern: Optional[str] = None,  # NEW parameter
    metadata_filter: Optional[dict] = None,
    limit: int = 10
):
    """
    Hybrid search with optional path pattern filtering.

    Args:
        query: Search query text
        path_pattern: Optional glob pattern for file paths
        metadata_filter: Additional metadata filters
        limit: Maximum results
    """
    filters = []

    # Add path pattern filter
    if path_pattern:
        filters.append(_build_path_pattern_filter(path_pattern))

    # Add other metadata filters
    if metadata_filter:
        filters.append(metadata_filter)

    # Combine filters
    combined_filter = {"must": filters} if filters else None

    # Execute search with combined filter
    # ... rest of search logic
```

**API Enhancement**:
```python
# Location: services/search/app.py (enhance search endpoint)

@app.post("/api/search/hybrid")
async def hybrid_search(
    query: str,
    path_pattern: Optional[str] = None,  # NEW parameter
    project_name: Optional[str] = None,
    limit: int = 10
):
    """
    Hybrid search with path pattern filtering.

    Examples:
        query="authentication", path_pattern="services/**/*.py"
        query="model", path_pattern="**/models/*.py"
        query="config", path_pattern="**/config/*"
    """
    # ... search implementation with path_pattern
```

**Estimated Effort**: 3 hours
**Testing**: Path pattern unit tests, integration tests

---

### Phase 4: Visualization API (Week 3+)

#### 4.1 Tree Visualization API

**New Endpoint**: `GET /api/intelligence/tree/visualize/{project_name}`

**Implementation**:
```python
# Location: services/intelligence/app.py (NEW endpoints)

from typing import List, Optional
from pydantic import BaseModel


class TreeNode(BaseModel):
    """Node in file tree visualization"""
    id: str
    name: str
    type: str  # "project", "directory", "file"
    path: str
    children: Optional[List["TreeNode"]] = None
    metadata: Optional[dict] = None


class DependencyEdge(BaseModel):
    """Dependency edge for visualization"""
    source: str  # File path
    target: str  # File path
    type: str    # "IMPORTS", "CALLS", etc.
    confidence: float = 1.0


class TreeVisualization(BaseModel):
    """Complete tree visualization data"""
    project: str
    tree: TreeNode
    dependencies: List[DependencyEdge]
    statistics: dict


@app.get("/api/intelligence/tree/visualize/{project_name}")
async def visualize_file_tree(
    project_name: str,
    include_dependencies: bool = Query(True, description="Include import relationships"),
    max_depth: int = Query(10, description="Maximum tree depth")
) -> TreeVisualization:
    """
    Generate file tree visualization data with dependency overlay.

    Returns hierarchical tree structure and dependency edges
    for interactive visualization in frontend.

    Args:
        project_name: Project to visualize
        include_dependencies: Include file import relationships
        max_depth: Maximum directory depth

    Returns:
        TreeVisualization with tree nodes and dependency edges
    """
    try:
        # Build tree from Memgraph hierarchy
        tree = await _build_tree_structure(project_name, max_depth)

        # Extract dependencies if requested
        dependencies = []
        if include_dependencies:
            dependencies = await _extract_dependencies(project_name)

        # Gather statistics
        stats = await _gather_tree_statistics(project_name)

        return TreeVisualization(
            project=project_name,
            tree=tree,
            dependencies=dependencies,
            statistics=stats
        )

    except Exception as e:
        logger.error(f"Tree visualization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _build_tree_structure(
    project_name: str,
    max_depth: int
) -> TreeNode:
    """Build hierarchical tree structure from Memgraph"""
    query = """
    MATCH path = (project:PROJECT {name: $project_name})-[:CONTAINS*0..{max_depth}]->(node)
    RETURN project, path, node
    ORDER BY length(path), node.name
    """.format(max_depth=max_depth)

    async with memgraph_adapter.driver.session() as session:
        result = await session.run(query, project_name=project_name)

        # Build tree structure from paths
        root = TreeNode(
            id=f"project:{project_name}",
            name=project_name,
            type="project",
            path=f"/{project_name}",
            children=[]
        )

        # Group nodes by parent
        nodes_by_parent = {}

        async for record in result:
            path = record["path"]
            node = record["node"]

            # Convert to TreeNode
            tree_node = TreeNode(
                id=node["entity_id"],
                name=node["name"],
                type=node.labels[0].lower(),  # "FILE" or "DIRECTORY"
                path=node.get("relative_path", node.get("path", "")),
                metadata={
                    "size": node.get("file_size"),
                    "language": node.get("language"),
                    "entity_count": node.get("entity_count")
                }
            )

            # Add to parent's children
            parent_id = path.nodes[-2]["entity_id"] if len(path.nodes) > 1 else root.id
            if parent_id not in nodes_by_parent:
                nodes_by_parent[parent_id] = []
            nodes_by_parent[parent_id].append(tree_node)

        # Recursively build tree
        def attach_children(node: TreeNode):
            if node.id in nodes_by_parent:
                node.children = nodes_by_parent[node.id]
                for child in node.children:
                    attach_children(child)

        attach_children(root)

        return root


async def _extract_dependencies(project_name: str) -> List[DependencyEdge]:
    """Extract file import dependencies"""
    query = """
    MATCH (source:FILE)-[r:IMPORTS]->(target:FILE)
    WHERE source.project_name = $project_name
    RETURN source.relative_path as source_path,
           target.relative_path as target_path,
           r.import_type as import_type,
           r.confidence as confidence
    """

    async with memgraph_adapter.driver.session() as session:
        result = await session.run(query, project_name=project_name)

        edges = []
        async for record in result:
            edges.append(DependencyEdge(
                source=record["source_path"],
                target=record["target_path"],
                type=record.get("import_type", "IMPORTS"),
                confidence=record.get("confidence", 1.0)
            ))

        return edges


async def _gather_tree_statistics(project_name: str) -> dict:
    """Gather tree statistics"""
    query = """
    MATCH (project:PROJECT {name: $project_name})
    OPTIONAL MATCH (project)-[:CONTAINS*]->(dir:DIRECTORY)
    OPTIONAL MATCH (project)-[:CONTAINS*]->(file:FILE)
    OPTIONAL MATCH (file)-[imp:IMPORTS]->()
    RETURN count(DISTINCT dir) as directory_count,
           count(DISTINCT file) as file_count,
           count(DISTINCT imp) as import_count
    """

    async with memgraph_adapter.driver.session() as session:
        result = await session.run(query, project_name=project_name)
        record = await result.single()

        return {
            "directories": record["directory_count"],
            "files": record["file_count"],
            "imports": record["import_count"],
            "avg_imports_per_file": round(
                record["import_count"] / record["file_count"]
                if record["file_count"] > 0 else 0,
                2
            )
        }
```

**API Response Example**:
```json
{
  "project": "omniarchon",
  "tree": {
    "id": "project:omniarchon",
    "name": "omniarchon",
    "type": "project",
    "path": "/omniarchon",
    "children": [
      {
        "id": "dir:omniarchon:services",
        "name": "services",
        "type": "directory",
        "path": "services",
        "children": [
          {
            "id": "file:omniarchon:services/intelligence/app.py",
            "name": "app.py",
            "type": "file",
            "path": "services/intelligence/app.py",
            "metadata": {
              "size": 125430,
              "language": "python",
              "entity_count": 45
            }
          }
        ]
      }
    ]
  },
  "dependencies": [
    {
      "source": "services/intelligence/app.py",
      "target": "services/intelligence/storage/memgraph_adapter.py",
      "type": "IMPORTS",
      "confidence": 1.0
    }
  ],
  "statistics": {
    "directories": 28,
    "files": 245,
    "imports": 487,
    "avg_imports_per_file": 1.99
  }
}
```

**Estimated Effort**: 10 hours
**Testing**: Integration tests, large project performance tests

---

## Implementation Roadmap

### Week 1: Foundation (Must Have)

**Days 1-2: File Nodes & Schema**
- [ ] **Task 1.1**: Implement `_create_file_node()` function (4h)
  - Location: `services/intelligence/app.py:2537`
  - Add file node creation to document processing pipeline
  - Unit tests for file node creation

- [ ] **Task 1.2**: Add `create_file_node()` to Memgraph adapter (2h)
  - Location: `services/intelligence/storage/memgraph_adapter.py:100`
  - Cypher query for MERGE file nodes
  - Unit tests for adapter method

**Days 3-4: File Import Relationships**
- [ ] **Task 1.3**: Integrate CodeRelationshipDetector (3h)
  - Location: `services/intelligence/app.py:2594`
  - Extract file imports during document processing
  - Filter IMPORTS relationships

- [ ] **Task 1.4**: Implement `_store_file_imports()` (2h)
  - Create file-to-file import relationships
  - Error handling and logging

- [ ] **Task 1.5**: Add `create_file_import_relationship()` to adapter (2h)
  - Location: `services/intelligence/storage/memgraph_adapter.py`
  - Cypher query for IMPORTS relationships
  - Integration tests

**Day 5: Directory Hierarchy**
- [ ] **Task 1.6**: Create DirectoryIndexer service (6h)
  - Location: `services/intelligence/src/services/directory_indexer.py` (NEW)
  - Implement hierarchy building logic
  - Add API endpoint for manual hierarchy indexing
  - Integration tests with sample projects

**Week 1 Success Criteria**:
- ✅ FILE nodes created for all indexed documents
- ✅ FILE IMPORTS FILE relationships stored
- ✅ Directory hierarchy indexed (PROJECT → DIRECTORY → FILE)
- ✅ 100% test coverage for new schema components

---

### Week 2: Orphan Detection (Should Have)

**Days 1-2: Orphan Detector Service**
- [ ] **Task 2.1**: Create OrphanDetector class (6h)
  - Location: `services/intelligence/src/services/orphan_detector.py` (NEW)
  - Implement `_find_no_incoming_imports()`
  - Implement `_find_unreachable_files()`
  - Implement `_find_dead_code()`
  - Unit tests for each detection method

**Day 3: Orphan Detection API**
- [ ] **Task 2.2**: Add orphan detection endpoints (3h)
  - Location: `services/intelligence/app.py`
  - `/api/intelligence/orphans/detect/{project_name}`
  - `/api/intelligence/orphans/summary/{project_name}`
  - API integration tests

- [ ] **Task 2.3**: Entry point detection (2h)
  - Implement `_find_entry_points()`
  - Support custom entry point patterns
  - Validation tests

**Days 4-5: Enhanced File Path Search**
- [ ] **Task 2.4**: Enhance embedding content (2h)
  - Location: `services/intelligence/app.py:2642`
  - Implement `_prepare_embedding_content()`
  - Add path emphasis (3x repetition)
  - A/B testing with path queries

- [ ] **Task 2.5**: Add path pattern filtering (3h)
  - Location: `services/search/engines/qdrant_adapter.py:461`
  - Implement `_build_path_pattern_filter()`
  - Support glob patterns (**, *, ?)
  - Path filter unit tests

**Week 2 Success Criteria**:
- ✅ Orphan detection working for all three types
- ✅ API returns accurate orphan lists
- ✅ File path search improved by 40%+
- ✅ Path pattern filtering functional

---

### Week 3+: Visualization & Polish (Nice to Have)

**Days 1-3: Tree Visualization API**
- [ ] **Task 3.1**: Implement tree visualization endpoint (8h)
  - Location: `services/intelligence/app.py`
  - `/api/intelligence/tree/visualize/{project_name}`
  - Build hierarchical tree from Memgraph
  - Extract dependency edges
  - Performance optimization for large projects

- [ ] **Task 3.2**: Tree statistics (2h)
  - Implement `_gather_tree_statistics()`
  - Calculate metrics (avg imports, depth, etc.)
  - Add caching for expensive queries

**Days 4-5: Performance Optimization**
- [ ] **Task 3.3**: Query optimization (4h)
  - Add Memgraph indexes for file paths
  - Optimize reachability queries
  - Benchmark performance (target: <2s for 10K files)

- [ ] **Task 3.4**: Caching strategy (3h)
  - Cache orphan detection results (5 min TTL)
  - Cache tree visualization (15 min TTL)
  - Invalidation on file updates

**Week 3+ Success Criteria**:
- ✅ Tree visualization API functional
- ✅ Performance targets met (<2s orphan scan)
- ✅ Caching reduces repeated query time by 90%
- ✅ Documentation complete

---

## Database Schema Changes

### New Node Types

**PROJECT Node**:
```cypher
CREATE (project:PROJECT {
  entity_id: "project:omniarchon",
  name: "omniarchon",
  path: "/Volumes/PRO-G40/Code/omniarchon",
  indexed_at: "2025-11-07T12:00:00Z",
  file_count: 245,
  directory_count: 28
})
```

**DIRECTORY Node**:
```cypher
CREATE (dir:DIRECTORY {
  entity_id: "dir:omniarchon:services/intelligence",
  name: "intelligence",
  path: "/Volumes/PRO-G40/Code/omniarchon/services/intelligence",
  relative_path: "services/intelligence",
  project_name: "omniarchon",
  indexed_at: "2025-11-07T12:00:00Z"
})
```

**FILE Node** (Enhanced):
```cypher
CREATE (file:FILE {
  entity_id: "file:omniarchon:services/intelligence/app.py",
  name: "app.py",
  path: "/Volumes/PRO-G40/Code/omniarchon/services/intelligence/app.py",
  relative_path: "services/intelligence/app.py",
  project_name: "omniarchon",
  file_size: 125430,
  language: "python",
  file_hash: "a7f5c8b9d3e2f1a0...",
  last_modified: "2025-11-07T10:30:00Z",
  created_at: "2025-10-01T08:00:00Z",
  indexed_at: "2025-11-07T12:00:00Z",
  content_type: "code",
  line_count: 2850,
  entity_count: 45,
  import_count: 23
})
```

### New Relationships

**CONTAINS (Hierarchical)**:
```cypher
// Project → Directory
(project:PROJECT)-[:CONTAINS]->(dir:DIRECTORY)

// Directory → Subdirectory
(dir1:DIRECTORY)-[:CONTAINS]->(dir2:DIRECTORY)

// Directory → File
(dir:DIRECTORY)-[:CONTAINS]->(file:FILE)
```

**IMPORTS (File Dependencies)**:
```cypher
(source:FILE)-[:IMPORTS {
  import_type: "module",        // or "class", "function"
  confidence: 1.0,
  created_at: "2025-11-07T12:00:00Z"
}]->(target:FILE)
```

**DEFINES (File to Entity)**:
```cypher
(file:FILE)-[:DEFINES]->(entity:ENTITY)
```

### Schema Migration Script

```cypher
-- Create indexes for performance
CREATE INDEX ON :PROJECT(name);
CREATE INDEX ON :DIRECTORY(project_name);
CREATE INDEX ON :DIRECTORY(relative_path);
CREATE INDEX ON :FILE(project_name);
CREATE INDEX ON :FILE(relative_path);
CREATE INDEX ON :FILE(name);
CREATE INDEX ON :FILE(entity_id);

-- Create constraints for uniqueness
CREATE CONSTRAINT ON (p:PROJECT) ASSERT p.entity_id IS UNIQUE;
CREATE CONSTRAINT ON (d:DIRECTORY) ASSERT d.entity_id IS UNIQUE;
CREATE CONSTRAINT ON (f:FILE) ASSERT f.entity_id IS UNIQUE;
```

---

## API Specifications

### 1. Orphan Detection API

**Endpoint**: `GET /api/intelligence/orphans/detect/{project_name}`

**Parameters**:
- `project_name` (path): Project identifier
- `entry_points` (query, optional): Comma-separated entry point file names

**Response** (200 OK):
```json
{
  "project": "omniarchon",
  "orphaned_files": [
    {
      "file_path": "/Volumes/.../unused.py",
      "relative_path": "services/unused.py",
      "orphan_type": "no_imports",
      "reason": "No other files import this file",
      "entry_point_distance": null,
      "import_count": 5,
      "entity_count": 3,
      "last_modified": "2025-10-15T10:30:00Z"
    }
  ],
  "unreachable_files": [...],
  "dead_code_files": [],
  "total_files": 245,
  "total_orphans": 12,
  "entry_points": [
    "services/intelligence/app.py"
  ],
  "scan_timestamp": "2025-11-07T15:30:00Z"
}
```

**Error Responses**:
- `404`: Project not found
- `500`: Internal server error

---

### 2. Orphan Summary API

**Endpoint**: `GET /api/intelligence/orphans/summary/{project_name}`

**Response** (200 OK):
```json
{
  "project": "omniarchon",
  "total_files": 245,
  "orphan_count": 12,
  "unreachable_count": 8,
  "dead_code_count": 2,
  "orphan_percentage": 4.9,
  "entry_points": [
    "services/intelligence/app.py",
    "services/bridge/app.py"
  ],
  "scan_timestamp": "2025-11-07T15:30:00Z"
}
```

---

### 3. Tree Visualization API

**Endpoint**: `GET /api/intelligence/tree/visualize/{project_name}`

**Parameters**:
- `project_name` (path): Project identifier
- `include_dependencies` (query, default=true): Include import relationships
- `max_depth` (query, default=10): Maximum tree depth

**Response** (200 OK):
```json
{
  "project": "omniarchon",
  "tree": {
    "id": "project:omniarchon",
    "name": "omniarchon",
    "type": "project",
    "path": "/omniarchon",
    "children": [
      {
        "id": "dir:omniarchon:services",
        "name": "services",
        "type": "directory",
        "path": "services",
        "children": [...]
      }
    ]
  },
  "dependencies": [
    {
      "source": "services/intelligence/app.py",
      "target": "services/intelligence/storage/memgraph_adapter.py",
      "type": "IMPORTS",
      "confidence": 1.0
    }
  ],
  "statistics": {
    "directories": 28,
    "files": 245,
    "imports": 487,
    "avg_imports_per_file": 1.99
  }
}
```

---

### 4. Enhanced Search API

**Endpoint**: `POST /api/search/hybrid`

**Request Body**:
```json
{
  "query": "authentication logic",
  "path_pattern": "services/**/*.py",
  "project_name": "omniarchon",
  "limit": 10
}
```

**Response** (200 OK):
```json
{
  "results": [
    {
      "file_path": "services/intelligence/auth.py",
      "score": 0.92,
      "snippet": "...",
      "metadata": {
        "language": "python",
        "file_size": 8450
      }
    }
  ],
  "total_results": 1,
  "query_time_ms": 145
}
```

---

## Performance Requirements

### Targets

| Operation | Target | Acceptable | Critical |
|-----------|--------|-----------|----------|
| **File node creation** | <10ms | <50ms | <100ms |
| **Directory hierarchy build** | <500ms (1K files) | <2s (5K files) | <10s (20K files) |
| **Orphan detection scan** | <2s (10K files) | <5s (20K files) | <30s (50K files) |
| **Tree visualization** | <1s (full tree) | <3s (large projects) | <10s (mega projects) |
| **Path pattern search** | <200ms | <500ms | <2s |
| **Import relationship creation** | <20ms per file | <100ms per file | <500ms per file |

### Monitoring Metrics

**Key Performance Indicators**:
- File node creation rate: nodes/second
- Orphan detection throughput: files scanned/second
- Query response time: p50, p95, p99
- Cache hit rate: % of cached responses
- Memory usage: MB per 1K files indexed

**Alerting Thresholds**:
- Orphan scan >10s: Warning
- Orphan scan >30s: Critical
- File node creation >500ms: Warning
- Query response >5s: Critical
- Cache hit rate <40%: Warning

### Optimization Strategies

**Query Optimization**:
1. **Indexes**: Add Memgraph indexes on frequently queried fields
   - `file.project_name`
   - `file.relative_path`
   - `file.name`

2. **Query Limits**: Enforce reasonable limits
   - Max tree depth: 20 levels
   - Max files per query: 50,000
   - Orphan scan timeout: 60s

3. **Batching**: Process in batches
   - File node creation: 100 files/batch
   - Import relationships: 50 relationships/batch

**Caching Strategy**:
- **Orphan detection**: 5 min TTL (invalidate on file updates)
- **Tree visualization**: 15 min TTL (invalidate on file updates)
- **Path searches**: 2 min TTL (high churn)

**Horizontal Scaling**:
- Read replicas for Memgraph (queries)
- Connection pooling (50 connections)
- Async processing for bulk operations

---

## Testing Strategy

### Unit Tests

**Coverage Target**: 90%+

**File Node Creation** (`test_file_node.py`):
```python
async def test_create_file_node_success():
    """Test successful file node creation"""
    # Arrange
    file_data = {
        "entity_id": "file:test:app.py",
        "name": "app.py",
        "path": "/test/app.py",
        # ...
    }

    # Act
    result = await memgraph_adapter.create_file_node(file_data)

    # Assert
    assert result is True
    # Verify node exists in graph


async def test_create_file_node_duplicate():
    """Test handling duplicate file node creation"""
    # Should update existing node, not error


async def test_create_file_node_invalid_data():
    """Test error handling for invalid data"""
    # Should raise validation error
```

**Import Relationship** (`test_file_imports.py`):
```python
async def test_create_import_relationship():
    """Test file import relationship creation"""
    # Create source and target files
    # Create IMPORTS relationship
    # Verify relationship exists


async def test_import_relationship_missing_target():
    """Test handling missing target file"""
    # Should create target file node or log warning


async def test_circular_imports():
    """Test detection of circular imports"""
    # Create circular dependency
    # Verify both relationships stored
```

**Orphan Detection** (`test_orphan_detector.py`):
```python
async def test_find_no_incoming_imports():
    """Test detection of files with no imports"""
    # Create test graph with orphaned files
    # Run detection
    # Verify orphaned files identified


async def test_find_unreachable_files():
    """Test reachability analysis from entry points"""
    # Create test graph with unreachable files
    # Run detection with entry points
    # Verify unreachable files identified


async def test_find_dead_code():
    """Test dead code detection"""
    # Create files with no imports and unused entities
    # Run detection
    # Verify dead code files identified
```

### Integration Tests

**End-to-End File Indexing** (`test_e2e_file_indexing.py`):
```python
async def test_full_file_indexing_pipeline():
    """Test complete file indexing workflow"""
    # 1. Ingest test repository
    # 2. Verify file nodes created
    # 3. Verify import relationships stored
    # 4. Verify directory hierarchy built
    # 5. Run orphan detection
    # 6. Verify results accurate


async def test_large_repository_indexing():
    """Test indexing large repository (1000+ files)"""
    # Measure performance
    # Verify all files indexed
    # Check memory usage
```

**Graph Traversal** (`test_graph_queries.py`):
```python
async def test_dependency_chain_query():
    """Test querying dependency chains"""
    # Create test graph: A → B → C
    # Query chain from A to C
    # Verify correct path returned


async def test_tree_visualization_accuracy():
    """Test tree visualization data accuracy"""
    # Index test repository
    # Generate tree visualization
    # Verify structure matches filesystem
    # Verify dependencies accurate
```

### Performance Tests

**Benchmark Suite** (`test_performance.py`):
```python
async def test_file_node_creation_performance():
    """Benchmark file node creation speed"""
    # Create 1000 file nodes
    # Measure time
    # Assert <10ms per node


async def test_orphan_detection_performance():
    """Benchmark orphan detection on large projects"""
    # Index 10,000 files
    # Run orphan detection
    # Assert <2s total time


async def test_tree_visualization_performance():
    """Benchmark tree visualization generation"""
    # Index 5,000 files
    # Generate tree
    # Assert <1s response time
```

**Load Testing** (`test_concurrent.py`):
```python
async def test_concurrent_file_indexing():
    """Test concurrent file indexing performance"""
    # Simulate 10 concurrent bulk ingestions
    # Verify no deadlocks
    # Verify all files indexed correctly


async def test_concurrent_orphan_scans():
    """Test concurrent orphan detection requests"""
    # Simulate 5 concurrent orphan scans
    # Verify consistent results
    # Measure response time degradation
```

---

## Migration Strategy

### Data Migration Plan

**Phase 1: Schema Preparation** (Day 0)
```bash
# 1. Add Memgraph indexes
cypher -u bolt://localhost:7687 -e "
CREATE INDEX ON :PROJECT(name);
CREATE INDEX ON :DIRECTORY(project_name);
CREATE INDEX ON :FILE(project_name);
CREATE INDEX ON :FILE(relative_path);
"

# 2. Create constraints
cypher -u bolt://localhost:7687 -e "
CREATE CONSTRAINT ON (p:PROJECT) ASSERT p.entity_id IS UNIQUE;
CREATE CONSTRAINT ON (f:FILE) ASSERT f.entity_id IS UNIQUE;
"
```

**Phase 2: Backfill Existing Documents** (Day 1)
```python
# Script: scripts/migrate_existing_documents_to_file_nodes.py

async def migrate_existing_documents():
    """
    Migrate existing documents to file node schema.

    Steps:
    1. Query all existing documents from Qdrant
    2. For each document, create FILE node
    3. Extract imports using CodeRelationshipDetector
    4. Create import relationships
    5. Build directory hierarchy
    """
    # Get all documents
    all_docs = await qdrant_adapter.get_all_documents()

    logger.info(f"Migrating {len(all_docs)} documents to file nodes")

    # Group by project
    docs_by_project = {}
    for doc in all_docs:
        project = doc.metadata.get("project_name", "unknown")
        if project not in docs_by_project:
            docs_by_project[project] = []
        docs_by_project[project].append(doc)

    # Migrate each project
    for project, docs in docs_by_project.items():
        logger.info(f"Migrating project: {project} ({len(docs)} files)")

        # Create file nodes
        for doc in docs:
            await _create_file_node(
                document_id=doc.id,
                source_path=doc.metadata.get("file_path"),
                metadata=doc.metadata,
                project_id=project
            )

        # Extract imports
        for doc in docs:
            if doc.metadata.get("language") in ["python", "py"]:
                imports = await code_relationship_detector.detect_relationships(
                    content=doc.content,
                    language=doc.metadata["language"],
                    document_path=doc.metadata["file_path"]
                )

                await _store_file_imports(
                    source_file=f"file:{project}:{doc.metadata['relative_path']}",
                    import_relationships=imports,
                    project_id=project
                )

        # Build directory hierarchy
        file_paths = [doc.metadata["relative_path"] for doc in docs]
        await directory_indexer.index_directory_hierarchy(
            project_name=project,
            project_root=docs[0].metadata.get("project_root", "/"),
            file_paths=file_paths
        )

        logger.info(f"✅ Project {project} migrated successfully")
```

**Phase 3: Validation** (Day 2)
```python
# Validate migration results
async def validate_migration():
    """Validate file node migration"""

    # 1. Check file node count matches document count
    qdrant_count = await qdrant_adapter.count_documents()
    memgraph_count = await memgraph_adapter.count_file_nodes()

    assert qdrant_count == memgraph_count, \
        f"Mismatch: Qdrant={qdrant_count}, Memgraph={memgraph_count}"

    # 2. Spot-check import relationships
    sample_files = await memgraph_adapter.get_random_files(n=10)
    for file in sample_files:
        imports = await memgraph_adapter.get_file_imports(file.entity_id)
        # Verify imports make sense

    # 3. Validate directory hierarchy
    projects = await memgraph_adapter.get_all_projects()
    for project in projects:
        tree = await _build_tree_structure(project.name, max_depth=20)
        # Verify tree is well-formed

    logger.info("✅ Migration validation passed")
```

### Rollout Plan

**Development Environment** (Week 1)
- [ ] Deploy schema changes to dev Memgraph
- [ ] Run migration script on dev data
- [ ] Validate results
- [ ] Test orphan detection APIs
- [ ] Performance benchmarking

**Staging Environment** (Week 2)
- [ ] Deploy to staging
- [ ] Run migration on staging data (larger dataset)
- [ ] Stress testing (concurrent requests)
- [ ] End-to-end integration tests
- [ ] User acceptance testing

**Production Deployment** (Week 3)
- [ ] Create database backup
- [ ] Deploy schema changes during maintenance window
- [ ] Run migration script (estimated 2-4 hours for large datasets)
- [ ] Validate migration
- [ ] Enable new APIs
- [ ] Monitor performance metrics
- [ ] Rollback plan ready (restore from backup if needed)

**Post-Deployment** (Week 4)
- [ ] Monitor error rates
- [ ] Track performance metrics
- [ ] User feedback collection
- [ ] Optimization based on real-world usage
- [ ] Documentation updates

---

## Success Metrics

### Quantitative Metrics

**Coverage Metrics**:
- ✅ **100% of files indexed** with FILE nodes
- ✅ **100% of Python files** have import relationships extracted
- ✅ **Directory hierarchy matches filesystem** (0% discrepancy)
- ✅ **Orphan detection accuracy**: 95%+ precision and recall

**Performance Metrics**:
- ✅ **File node creation**: <10ms per file (target), <50ms (acceptable)
- ✅ **Orphan scan**: <2s for 10K files (target), <5s (acceptable)
- ✅ **Tree visualization**: <1s (target), <3s (acceptable)
- ✅ **Import extraction**: <100ms per file (target), <500ms (acceptable)

**Reliability Metrics**:
- ✅ **Zero data inconsistencies** (file nodes vs. documents)
- ✅ **99.9% API uptime** for orphan detection
- ✅ **Migration success rate**: 100% (all files migrated)

### Qualitative Metrics

**Developer Experience**:
- ✅ Developers can **visualize project structure** graphically
- ✅ Orphan files are **identified automatically** in CI/CD
- ✅ File path search **finds files by partial path** accurately
- ✅ Code navigation is **enhanced with dependency insights**

**Adoption Metrics**:
- ✅ **Orphan detection used in 80%+ of projects** within 3 months
- ✅ **File path search queries increase by 40%** (indicates usefulness)
- ✅ **Tree visualization accessed 100+ times/week**
- ✅ **Positive user feedback** (survey NPS >8/10)

**Code Quality Impact**:
- ✅ **Dead code reduced by 15%+** after orphan cleanup
- ✅ **Refactoring confidence increased** (based on dependency insights)
- ✅ **Onboarding time reduced** (via tree visualization)

---

## Risks & Mitigation

### Technical Risks

**1. Performance Degradation with Large Repositories**
- **Risk**: Orphan detection >30s for 50K+ files
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**:
  - Implement query timeout (60s max)
  - Add pagination for tree visualization
  - Use Memgraph query profiling to optimize
  - Consider incremental updates vs. full scans

**2. Graph Schema Migration Complexity**
- **Risk**: Migration fails partway, leaving inconsistent state
- **Likelihood**: Low
- **Impact**: Critical
- **Mitigation**:
  - Transaction-based migration (rollback on error)
  - Dry-run validation before production
  - Database backup before migration
  - Rollback script ready

**3. Inconsistent Import Detection**
- **Risk**: AST parsing fails for complex Python or other languages
- **Likelihood**: Medium
- **Impact**: Medium
- **Mitigation**:
  - Fallback to regex-based import detection
  - Log parsing failures for manual review
  - Support incremental improvement (fix edge cases)
  - Multi-language support prioritization (Python first)

**4. Memory Consumption for Tree Visualization**
- **Risk**: Loading full tree for mega-projects (100K+ files) causes OOM
- **Likelihood**: Low
- **Impact**: High
- **Mitigation**:
  - Implement lazy loading (load tree on-demand)
  - Add max_depth parameter (default 10, max 20)
  - Streaming response for large trees
  - Client-side pagination

### Operational Risks

**1. Indexing Failures During Migration**
- **Risk**: Bulk migration script fails partway
- **Likelihood**: Medium
- **Impact**: Medium
- **Mitigation**:
  - Resume capability (track progress)
  - Error handling with retry logic
  - DLQ for failed documents
  - Manual retry for edge cases

**2. Storage Capacity for Graph Data**
- **Risk**: Memgraph storage exceeds capacity
- **Likelihood**: Low
- **Impact**: Medium
- **Mitigation**:
  - Monitor Memgraph storage usage
  - Project growth (estimate 10KB per file node)
  - Cleanup old/archived projects
  - Storage expansion plan

**3. Cache Invalidation Complexity**
- **Risk**: Stale cache data after file updates
- **Likelihood**: Medium
- **Impact**: Low
- **Mitigation**:
  - Conservative TTL (5 min for orphan detection)
  - Event-based invalidation (listen to file update events)
  - Manual cache clear API for emergencies
  - Cache versioning

**4. User Confusion with Orphan Results**
- **Risk**: False positives in orphan detection (e.g., reflection imports)
- **Likelihood**: Medium
- **Impact**: Low
- **Mitigation**:
  - Clear documentation on orphan types
  - Allow custom exclusion patterns
  - Confidence scoring for orphan detection
  - Manual review workflow

---

## Open Questions

### To Be Resolved Before Implementation

1. **Backfill Strategy**
   - **Question**: Should we backfill existing repositories automatically?
   - **Options**:
     - A) Automatic backfill during migration (1-time)
     - B) On-demand backfill (triggered per project)
     - C) Gradual backfill (next ingestion triggers it)
   - **Recommendation**: Option A (automatic) for existing projects, Option C (gradual) for future updates
   - **Decision Needed By**: Week 1, Day 1

2. **Circular Dependency Handling**
   - **Question**: How should we handle circular imports?
   - **Options**:
     - A) Store both A→B and B→A relationships
     - B) Flag circular dependencies with special property
     - C) Detect and warn, but don't prevent
   - **Recommendation**: Option A + Option B (store + flag)
   - **Decision Needed By**: Week 1, Day 3

3. **Automatic Orphan Detection**
   - **Question**: Should orphan detection run automatically or on-demand?
   - **Options**:
     - A) On-demand only (API calls)
     - B) Scheduled (daily/weekly cron)
     - C) Event-driven (after bulk ingestion)
   - **Recommendation**: Option A (on-demand) + Option C (post-ingestion)
   - **Decision Needed By**: Week 2, Day 1

4. **CI/CD Integration**
   - **Question**: Should orphan detection integrate with CI/CD pipelines?
   - **Options**:
     - A) Yes, as a required check (fail PR if orphans found)
     - B) Yes, as a warning (comment on PR with orphans)
     - C) No, manual only
   - **Recommendation**: Option B (warning) to start, Option A (blocker) later
   - **Decision Needed By**: Week 3, Day 1

5. **Multi-Language Import Detection**
   - **Question**: What languages should we support beyond Python?
   - **Priority Order**:
     1. Python (✅ exists)
     2. JavaScript/TypeScript (import/require)
     3. Go (import)
     4. Rust (use)
     5. Java (import)
   - **Recommendation**: Python first (Week 1), JS/TS (Week 2-3), others (future)
   - **Decision Needed By**: Week 1, Day 1

6. **File Path Search Weighting**
   - **Question**: How much weight should file paths have in embeddings?
   - **Options**:
     - A) 3x repetition (current plan)
     - B) 5x repetition (higher emphasis)
     - C) Separate embedding field
   - **Recommendation**: Option A (3x) with A/B testing
   - **Decision Needed By**: Week 2, Day 4

---

## References

### Research Documents

**Agent Research Results**:
1. **Agent 1: Graph Visualization Research**
   - Focus: OmniNode triple-layer indexing
   - Key Finding: `.onextree` structure, metadata stamping

2. **Agent 2: Orphan Detection Research**
   - Focus: Dead code detection patterns
   - Key Finding: Reachability analysis via graph traversal

3. **Agent 3: File Path Search Research**
   - Focus: Path search optimization
   - Key Finding: Embedding enhancement with path emphasis

4. **Agent 4: Dependency Tracking Research**
   - Focus: Import graph extraction
   - Key Finding: AST-based Python import detection

5. **Agent 5: Integration Patterns Research**
   - Focus: Event-driven architecture integration
   - Key Finding: Extend existing document processing pipeline

### OmniNode Documentation

**Primary Sources**:
- `/Volumes/PRO-G40/Code/omninode/docs/yc/04_EVENT_MANAGEMENT.md`
  - Event bus architecture
  - Triple-layer indexing

- `/Volumes/PRO-G40/Code/omninode/docs/FUTURE_FUNCTIONALITY_LEGACY_MIGRATION.md`
  - Dead code detector vision
  - Dependency graph patterns

- `/Volumes/PRO-G40/Code/omninode_bridge/.onextree/structure.json`
  - OnexTree metadata structure
  - File hierarchy representation

### Archon Implementation References

**Code Locations**:
- `services/intelligence/app.py:2537`
  - Document processing pipeline
  - Integration point for file nodes

- `services/intelligence/storage/memgraph_adapter.py`
  - Memgraph adapter base implementation
  - Graph storage patterns

- `services/langextract/analysis/code_relationship_detector.py`
  - Existing import extraction (unused)
  - AST-based relationship detection

- `services/search/engines/qdrant_adapter.py:461`
  - Metadata filtering
  - Enhancement point for path patterns

### External References

**Technologies**:
- **Memgraph**: Graph database (Cypher queries)
  - Docs: https://memgraph.com/docs
  - Query language: Cypher

- **Qdrant**: Vector database (embeddings)
  - Docs: https://qdrant.tech/documentation
  - Filtering: Metadata filters

- **Neo4j Driver**: Python async driver for Memgraph
  - Docs: https://neo4j.com/docs/api/python-driver

**Best Practices**:
- Graph schema design: https://neo4j.com/developer/data-modeling/
- Orphan detection patterns: Static analysis tools (Pylint, Bandit)
- File tree visualization: D3.js tree layouts

---

## Appendix

### A. Cypher Query Examples

**Find Orphaned Files** (No Incoming Imports):
```cypher
MATCH (project:PROJECT {name: $project_name})-[:CONTAINS*]->(file:FILE)
WHERE NOT (file)<-[:IMPORTS]-()
  AND NOT file.name IN ['__init__.py', '__main__.py']
RETURN file.relative_path AS orphan_path,
       file.entity_count AS entities,
       file.import_count AS outgoing_imports
ORDER BY file.relative_path
```

**Find Unreachable Files** (Not in Dependency Chain from Entry Points):
```cypher
// Step 1: Find all reachable files
MATCH path = (entry:FILE)-[:IMPORTS*0..10]->(reachable:FILE)
WHERE entry.name IN ['main.py', 'app.py', '__main__.py']
  AND entry.project_name = $project_name
WITH COLLECT(DISTINCT reachable.entity_id) AS reachable_ids

// Step 2: Find unreachable files
MATCH (project:PROJECT {name: $project_name})-[:CONTAINS*]->(file:FILE)
WHERE NOT file.entity_id IN reachable_ids
  AND NOT file.name IN ['__init__.py']
RETURN file.relative_path AS unreachable_path,
       file.last_modified AS last_modified
ORDER BY file.relative_path
```

**Dependency Chain Query** (A → ... → B):
```cypher
MATCH path = shortestPath(
  (source:FILE {relative_path: $source_path})-[:IMPORTS*..10]->(target:FILE {relative_path: $target_path})
)
WHERE source.project_name = $project_name
RETURN [node IN nodes(path) | node.relative_path] AS dependency_chain,
       length(path) AS chain_length
```

**Circular Dependency Detection**:
```cypher
MATCH path = (file:FILE)-[:IMPORTS*2..10]->(file)
WHERE file.project_name = $project_name
RETURN [node IN nodes(path) | node.relative_path] AS circular_chain
ORDER BY length(path)
LIMIT 10
```

**File Import Count (Top Importers)**:
```cypher
MATCH (file:FILE)-[:IMPORTS]->(imported:FILE)
WHERE file.project_name = $project_name
WITH file, count(imported) AS import_count
RETURN file.relative_path AS file_path,
       import_count,
       file.entity_count AS entities
ORDER BY import_count DESC
LIMIT 20
```

**Most Imported Files (Hub Detection)**:
```cypher
MATCH (importer:FILE)-[:IMPORTS]->(file:FILE)
WHERE file.project_name = $project_name
WITH file, count(importer) AS imported_by_count
RETURN file.relative_path AS file_path,
       imported_by_count,
       file.entity_count AS entities
ORDER BY imported_by_count DESC
LIMIT 20
```

**Directory File Count**:
```cypher
MATCH (dir:DIRECTORY {project_name: $project_name})-[:CONTAINS]->(file:FILE)
RETURN dir.relative_path AS directory,
       count(file) AS file_count
ORDER BY file_count DESC
```

**Project Statistics**:
```cypher
MATCH (project:PROJECT {name: $project_name})
OPTIONAL MATCH (project)-[:CONTAINS*]->(dir:DIRECTORY)
OPTIONAL MATCH (project)-[:CONTAINS*]->(file:FILE)
OPTIONAL MATCH (file)-[imp:IMPORTS]->()
OPTIONAL MATCH (file)-[:DEFINES]->(entity:ENTITY)
RETURN count(DISTINCT dir) AS directories,
       count(DISTINCT file) AS files,
       count(DISTINCT imp) AS imports,
       count(DISTINCT entity) AS entities,
       round(toFloat(count(DISTINCT imp)) / count(DISTINCT file), 2) AS avg_imports_per_file
```

---

### B. Code Examples

**Example: Bulk File Node Creation**
```python
# Script: scripts/bulk_create_file_nodes.py

async def bulk_create_file_nodes(project_name: str, file_list: List[dict]):
    """
    Create file nodes in bulk for a project.

    Args:
        project_name: Project identifier
        file_list: List of file metadata dicts

    Returns:
        Number of nodes created
    """
    created_count = 0
    failed_count = 0

    # Process in batches of 100
    batch_size = 100
    for i in range(0, len(file_list), batch_size):
        batch = file_list[i:i+batch_size]

        try:
            # Create nodes in batch
            async with memgraph_adapter.driver.session() as session:
                async with session.begin_transaction() as tx:
                    for file_data in batch:
                        query = """
                        MERGE (file:FILE {entity_id: $entity_id})
                        SET file = $properties
                        """
                        await tx.run(
                            query,
                            entity_id=file_data["entity_id"],
                            properties=file_data
                        )

                    await tx.commit()
                    created_count += len(batch)

                    logger.info(f"✅ Batch {i//batch_size + 1} created ({len(batch)} files)")

        except Exception as e:
            logger.error(f"❌ Batch {i//batch_size + 1} failed: {e}")
            failed_count += len(batch)

    logger.info(
        f"Bulk creation complete | "
        f"created={created_count} | "
        f"failed={failed_count}"
    )

    return created_count
```

**Example: Interactive Orphan Cleanup**
```python
# Script: scripts/cleanup_orphaned_files.py

async def interactive_orphan_cleanup(project_name: str):
    """
    Interactive script to review and delete orphaned files.

    Prompts user for each orphaned file:
    - (D)elete file
    - (K)eep file
    - (S)kip for now
    - (Q)uit
    """
    # Detect orphans
    result = await orphan_detector.detect_orphans(project_name)

    print(f"\n📊 Orphan Detection Results for '{project_name}':")
    print(f"   Total Files: {result.total_files}")
    print(f"   Orphaned: {result.total_orphans}")
    print(f"   Unreachable: {len(result.unreachable_files)}")
    print(f"   Dead Code: {len(result.dead_code_files)}\n")

    deleted = []
    kept = []

    for orphan in result.orphaned_files:
        print(f"\n{'='*80}")
        print(f"File: {orphan.relative_path}")
        print(f"Type: {orphan.orphan_type}")
        print(f"Reason: {orphan.reason}")
        print(f"Entities: {orphan.entity_count} | Imports: {orphan.import_count}")
        print(f"Last Modified: {orphan.last_modified}")

        # Show file preview
        try:
            with open(orphan.file_path, 'r') as f:
                preview = f.read(500)
                print(f"\nPreview:\n{preview}...\n")
        except:
            pass

        # Prompt user
        choice = input("Action? (D)elete / (K)eep / (S)kip / (Q)uit: ").upper()

        if choice == 'D':
            # Delete file
            os.remove(orphan.file_path)
            deleted.append(orphan.relative_path)
            print(f"✅ Deleted: {orphan.relative_path}")

        elif choice == 'K':
            kept.append(orphan.relative_path)
            print(f"✅ Kept: {orphan.relative_path}")

        elif choice == 'Q':
            print("\n👋 Cleanup stopped")
            break

        else:
            print("⏭️ Skipped")

    # Summary
    print(f"\n{'='*80}")
    print(f"📊 Cleanup Summary:")
    print(f"   Deleted: {len(deleted)} files")
    print(f"   Kept: {len(kept)} files")

    if deleted:
        print(f"\n🗑️ Deleted files:")
        for path in deleted:
            print(f"   - {path}")
```

**Example: Dependency Visualization (ASCII)**
```python
# Script: scripts/visualize_dependencies.py

async def visualize_file_dependencies(file_path: str, max_depth: int = 3):
    """
    Visualize file dependency tree in ASCII.

    Example output:
        app.py
        ├── models.py
        │   ├── base.py
        │   └── user.py
        ├── routes.py
        │   └── auth.py
        └── utils.py
    """
    # Query dependency tree
    query = """
    MATCH path = (source:FILE {relative_path: $file_path})-[:IMPORTS*0..{max_depth}]->(dep:FILE)
    RETURN path
    ORDER BY length(path), dep.name
    """.format(max_depth=max_depth)

    async with memgraph_adapter.driver.session() as session:
        result = await session.run(query, file_path=file_path)

        # Build tree structure
        tree = {}
        async for record in result:
            path = record["path"]
            nodes = [node["relative_path"] for node in path.nodes]

            # Add to tree
            current = tree
            for i, node in enumerate(nodes):
                if node not in current:
                    current[node] = {}
                current = current[node]

        # Print tree
        def print_tree(tree_dict, prefix="", is_last=True):
            items = list(tree_dict.items())
            for i, (node, children) in enumerate(items):
                is_last_item = (i == len(items) - 1)

                # Print node
                connector = "└── " if is_last_item else "├── "
                print(f"{prefix}{connector}{node}")

                # Print children
                if children:
                    extension = "    " if is_last_item else "│   "
                    print_tree(children, prefix + extension, is_last_item)

        print(f"\n🌳 Dependency Tree for: {file_path}\n")
        print_tree(tree)
```

---

### C. Migration Checklist

**Pre-Migration** (Week 0):
- [ ] Review and approve implementation plan
- [ ] Allocate development resources
- [ ] Set up development environment with Memgraph
- [ ] Create test dataset (sample repository)
- [ ] Establish performance baselines

**Week 1: Implementation**
- [ ] Day 1-2: File nodes + schema
  - [ ] Implement `_create_file_node()`
  - [ ] Add Memgraph adapter methods
  - [ ] Unit tests (90%+ coverage)
  - [ ] Integration tests

- [ ] Day 3-4: File imports
  - [ ] Integrate CodeRelationshipDetector
  - [ ] Implement `_store_file_imports()`
  - [ ] Create import relationships
  - [ ] Integration tests

- [ ] Day 5: Directory hierarchy
  - [ ] Create DirectoryIndexer service
  - [ ] Implement hierarchy building
  - [ ] Add API endpoint
  - [ ] Integration tests

**Week 2: Orphan Detection + Search**
- [ ] Day 1-2: Orphan detector
  - [ ] Create OrphanDetector class
  - [ ] Implement detection methods
  - [ ] Unit tests for each method

- [ ] Day 3: APIs
  - [ ] Add orphan detection endpoints
  - [ ] API integration tests
  - [ ] Documentation

- [ ] Day 4-5: Path search
  - [ ] Enhance embedding content
  - [ ] Add path pattern filtering
  - [ ] A/B testing

**Week 3: Visualization + Polish**
- [ ] Day 1-3: Tree visualization
  - [ ] Implement visualization endpoint
  - [ ] Tree building algorithm
  - [ ] Dependency extraction

- [ ] Day 4-5: Optimization
  - [ ] Query optimization
  - [ ] Caching implementation
  - [ ] Performance testing

**Week 4: Migration + Deployment**
- [ ] Create migration script
- [ ] Dry-run migration on dev
- [ ] Validate results
- [ ] Deploy to staging
- [ ] User acceptance testing
- [ ] Production deployment
- [ ] Post-deployment monitoring

---

### D. Glossary

**Terms**:
- **FILE Node**: Graph node representing a file in the project
- **DIRECTORY Node**: Graph node representing a directory
- **PROJECT Node**: Graph node representing a project root
- **CONTAINS Relationship**: Hierarchical relationship (parent contains child)
- **IMPORTS Relationship**: File dependency (source imports target)
- **DEFINES Relationship**: File defines entity (class, function)
- **Orphaned File**: File with no incoming IMPORTS relationships
- **Unreachable File**: File not in dependency chain from entry points
- **Dead Code**: Orphaned file with no used entities
- **Entry Point**: Main file (e.g., main.py, app.py) that serves as starting point
- **Dependency Chain**: Path of IMPORTS relationships from A to B
- **Circular Dependency**: Cycle in import graph (A → B → ... → A)
- **Reachability Analysis**: Graph traversal to find all files reachable from entry points
- **Path Pattern**: Glob pattern for filtering file paths (e.g., `services/**/*.py`)
- **Tree Visualization**: Hierarchical representation of project structure
- **Hybrid Search**: Combined vector search + metadata filtering

---

**End of Document**

---

**Approval Checklist**:
- [ ] Technical design reviewed by Intelligence Team
- [ ] Performance targets validated
- [ ] Resource allocation confirmed
- [ ] Timeline approved by management
- [ ] Migration strategy reviewed
- [ ] Risk mitigation acceptable
- [ ] Testing strategy comprehensive
- [ ] Documentation complete

**Sign-off**:
- Intelligence Team Lead: _______________
- Engineering Manager: _______________
- Product Owner: _______________
- Date: _______________
