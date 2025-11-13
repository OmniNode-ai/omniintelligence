# Plan: Remove Phase 0 Filesystem Dependencies

**Status**: Draft
**Created**: 2025-10-28
**Author**: Claude Code (Polymorphic Agent)
**Correlation ID**: 3aef2d1b-cff8-4110-ae3b-7755f4b42f94

---

## Executive Summary

**Problem**: The codebase currently supports BOTH Phase 0 (filesystem-based) and Phase 1 (inline content) indexing modes, creating confusion and allowing accidental filesystem access attempts from Docker containers.

**Solution**: Remove all Phase 0 fallback code paths that require Docker container filesystem mounts, forcing exclusive use of Phase 1 inline content architecture.

**Impact**:
- ✅ **Simplifies architecture**: One clear path for indexing (inline content only)
- ✅ **Prevents confusion**: No more "which mode should I use?" questions
- ✅ **Blocks accidental filesystem access**: Clear errors if files parameter missing
- ✅ **Cloud-native ready**: No container filesystem dependencies
- ⚠️  **Breaking change**: Phase 0 workflows will fail with clear error messages

**Scope**: 3-4 hours implementation + 1 hour testing

---

## Current State Analysis

### Phase 0 Code Paths (TO REMOVE)

#### 1. **tree_stamping_bridge.py** - Main Orchestrator

**Location**: `services/intelligence/src/integrations/tree_stamping_bridge.py`

**Filesystem Fallback #1: index_project() method (Lines 314-320)**
```python
if files:
    # Phase 1: Use provided files with inline content
    file_paths = [f["relative_path"] for f in files]
    files_discovered = len(files)
    logger.info(f"Stage 1/6: Using {files_discovered} provided files (inline content)")
else:
    # Phase 0: Fall back to filesystem discovery ← DELETE THIS
    logger.info("Stage 1/6: Discovering project tree...")
    tree_result = await self._discover_tree(project_path, include_tests)
    files_discovered = tree_result.get("file_count", 0)
    file_paths = tree_result.get("files", [])
```

**Purpose**: Falls back to filesystem discovery if `files=None`
**Dependencies**: Requires `_discover_tree()` method, FileDiscoveryService, container filesystem access
**Risk**: Core indexing method - must ensure Phase 1 always provides files parameter

---

**Filesystem Fallback #2: _discover_tree() method (Lines 580-650)**
```python
async def _discover_tree(
    self,
    project_path: str,
    include_tests: bool = True,
    max_depth: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Discover project files using local FileDiscoveryService.
    ← ENTIRE METHOD TO BE DELETED
    """
    try:
        if not self.file_discovery_service:
            raise TreeDiscoveryError("FileDiscoveryService not initialized")

        # Use local file discovery service
        result = await self.file_discovery_service.discover_files(
            project_path=project_path,
            include_tests=include_tests,
            max_depth=max_depth,
        )
        # ... rest of method
```

**Purpose**: Filesystem-based file discovery using FileDiscoveryService
**Dependencies**: FileDiscoveryService, container filesystem access to project_path
**Risk**: Complete method removal - no callers should remain after Phase 0 removal
**Lines to delete**: 580-650 (entire method)

---

**Filesystem Fallback #3: _generate_intelligence_http() method (Lines 701-716)**
```python
if provided_content:
    # Phase 1: Use inline content
    content = provided_content
    size_bytes = len(content.encode("utf-8"))
    logger.debug(f"Using inline content for {file_path} ({size_bytes} bytes)")
else:
    # Phase 0: Fall back to reading from filesystem ← DELETE THIS BLOCK
    try:
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        content = path.read_text(encoding="utf-8")
        size_bytes = path.stat().st_size
        logger.debug(f"Read {size_bytes} bytes from filesystem: {file_path}")
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return None
```

**Purpose**: Falls back to filesystem read if inline content not provided
**Dependencies**: pathlib.Path, container filesystem access
**Risk**: Intelligence generation method - must ensure content always provided
**Lines to delete**: 701-716 (else block only)

---

**Filesystem Dependency #4: FileDiscoveryService initialization (Lines 1624-1627)**
```python
# FileDiscoveryService (local service, no network calls)
if not self.file_discovery_service:
    self.file_discovery_service = FileDiscoveryService()
    logger.debug("FileDiscoveryService initialized")
```

**Purpose**: Initializes FileDiscoveryService for Phase 0 operations
**Dependencies**: FileDiscoveryService class
**Risk**: Initialization code - safe to remove after all callers deleted
**Lines to delete**: 1624-1627

---

**Filesystem Dependency #5: FileDiscoveryService cleanup (Lines 1741-1743)**
```python
# FileDiscoveryService is local, no cleanup needed (keep it alive for reuse)
# Don't set to None - it's a lightweight local service with no resources to cleanup
```

**Purpose**: Comment about cleanup (or lack thereof)
**Action**: Remove comment when service removed

---

#### 2. **file_discovery.py** - Filesystem Discovery Service

**Location**: `services/intelligence/src/services/file_discovery.py`

**Purpose**: Local file discovery service with filesystem access
**Key Features**:
- Docker path translation (lines 225-244)
- Filesystem validation (lines 281-313)
- os.walk directory traversal (lines 324-404)
- File reading, hashing, stats (lines 622-729)

**Analysis**:
- **ONLY used by**: `_discover_tree()` method in bridge
- **NOT used by**: bulk_ingest_repository.py (uses script-local file discovery)
- **Docker-specific**: Built-in path translation for container environments
- **No legitimate Phase 1 use cases**: Requires filesystem access by design

**Decision**: **DELETE ENTIRE FILE** - No use cases remain after Phase 0 removal

**Dependent imports to clean up**:
- `tree_stamping_bridge.py` line 78: `from ..services.file_discovery import FileDiscoveryService`

---

#### 3. **tree_stamping_handler.py** - Event Handler

**Location**: `services/intelligence/src/handlers/tree_stamping_handler.py`

**Phase Detection Logging (Lines 280-290)**
```python
# Log inline content usage
if files:
    logger.info(
        f"Processing with {len(files)} files (inline content) | "
        f"correlation_id={correlation_id} | project_name={project_name}"
    )
else:
    logger.info(
        f"Processing INDEX_PROJECT_REQUESTED | correlation_id={correlation_id} | "
        f"project_name={project_name} | project_path={project_path} | "
        f"include_tests={include_tests} | force_reindex={force_reindex}"
    )
```

**Purpose**: Logs which phase is being used (Phase 0 vs Phase 1)
**Action**: Remove else block, add validation error if files=None

---

### Phase 1 Code Paths (TO KEEP)

#### 1. **bulk_ingest_repository.py** - Host Script

**Location**: `scripts/bulk_ingest_repository.py`

**Status**: ✅ **Already Phase 1 Only**

**Key Features**:
- Uses script-local file discovery (`scripts/lib/file_discovery.py`)
- Reads files on host machine (no container filesystem)
- Sends inline content in Kafka messages (lines 220-235)
- Event schema v2.0.0 with inline content support

**No changes needed** - Already correct architecture

---

#### 2. **tree_stamping_bridge.py** - Phase 1 Path

**When files parameter provided**:
- Lines 307-313: Uses provided files array (inline content)
- Lines 694-699: Uses provided_content parameter
- Lines 978-1004: Content lookup for batch processing

**No changes needed** - Keep all Phase 1 code

---

#### 3. **tree_stamping_handler.py** - Phase 1 Path

**Lines 258, 296**:
```python
files = payload.get("files")  # Phase 1: Inline content support
result = await self.bridge.index_project(
    files=files,  # Pass inline content to bridge
    ...
)
```

**No changes needed** - Keep Phase 1 path

---

### Test Coverage

#### Phase 0 Tests (TO UPDATE/REMOVE)

**File**: `services/intelligence/tests/services/test_file_discovery.py`

**Coverage**: Unit tests for FileDiscoveryService
- Basic file discovery
- Exclusion patterns
- Language detection
- Performance benchmarks

**Decision**: **DELETE ENTIRE FILE** - No service to test after removal

---

#### Phase 1 Tests (TO KEEP/VERIFY)

**File**: `services/intelligence/tests/unit/handlers/test_tree_stamping_handler.py`

**Coverage**: Handler tests with mocked bridge
- Event routing
- Index project handling
- Error handling

**Decision**: **UPDATE** - Add test verifying error when files=None

---

**File**: `services/intelligence/tests/integration/test_tree_stamping_events.py`

**Coverage**: Integration tests for event-driven flow

**Decision**: **VERIFY** - Ensure all tests provide inline content

---

### Dependencies & Impact Analysis

#### Direct Dependencies on FileDiscoveryService

1. **tree_stamping_bridge.py** (3 locations)
   - Import: line 78
   - Initialization: line 1626
   - Usage: line 605 (`_discover_tree()`)

**Action**: Remove import, initialization, and all usages

---

#### Indirect Dependencies

**None identified** - FileDiscoveryService is self-contained

---

#### Reverse Dependencies (Who calls Phase 0 code?)

**_discover_tree() callers**:
- `index_project()` line 317 (when files=None)

**_generate_intelligence_http() Phase 0 callers**:
- `_generate_intelligence_batch()` line 1001 (when content_lookup misses)

**After removal**: All callers will receive clear errors if files/content missing

---

## Removal Strategy

### Step 1: Add Validation to Prevent Phase 0 Fallback

**Goal**: Fail fast with clear errors if inline content not provided

**Changes**:

**File**: `services/intelligence/src/integrations/tree_stamping_bridge.py`

**Change 1A: index_project() validation (Line 306)**
```python
# BEFORE (Lines 306-320):
# Stage 1: File discovery (conditional on inline content)
if files:
    # Use provided files with inline content
    file_paths = [f["relative_path"] for f in files]
    files_discovered = len(files)
    logger.info(f"Stage 1/6: Using {files_discovered} provided files (inline content)")
else:
    # Fall back to filesystem discovery (Phase 0)
    logger.info("Stage 1/6: Discovering project tree...")
    tree_result = await self._discover_tree(project_path, include_tests)
    files_discovered = tree_result.get("file_count", 0)
    file_paths = tree_result.get("files", [])
    logger.info(f"Discovered {files_discovered} files")

# AFTER:
# Stage 1: Validate inline content provided (Phase 0 removed)
if not files:
    error_msg = (
        "files parameter is required. Phase 0 (filesystem-based indexing) "
        "has been removed. Use bulk_ingest_repository.py which provides "
        "inline content in Kafka messages."
    )
    logger.error(error_msg)
    raise TreeDiscoveryError(error_msg)

# Use provided files with inline content
file_paths = [f["relative_path"] for f in files]
files_discovered = len(files)
logger.info(f"Stage 1/6: Using {files_discovered} provided files (inline content)")
```

---

**Change 1B: _generate_intelligence_http() validation (Line 693)**
```python
# BEFORE (Lines 692-716):
try:
    # If inline content provided, use it
    if provided_content:
        content = provided_content
        size_bytes = len(content.encode("utf-8"))
        logger.debug(f"Using inline content for {file_path} ({size_bytes} bytes)")
    else:
        # Fall back to reading from filesystem (Phase 0)
        try:
            from pathlib import Path
            path = Path(file_path)
            if not path.exists():
                logger.error(f"File not found: {file_path}")
                return None
            content = path.read_text(encoding="utf-8")
            size_bytes = path.stat().st_size
            logger.debug(f"Read {size_bytes} bytes from filesystem: {file_path}")
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return None

# AFTER:
try:
    # Validate inline content provided (Phase 0 removed)
    if not provided_content:
        error_msg = (
            f"No inline content provided for {file_path}. "
            "Phase 0 (filesystem-based) has been removed. "
            "Ensure files parameter includes content for all files."
        )
        logger.error(error_msg)
        return None

    # Use inline content
    content = provided_content
    size_bytes = len(content.encode("utf-8"))
    logger.debug(f"Using inline content for {file_path} ({size_bytes} bytes)")
```

---

**Change 1C: Handler validation**

**File**: `services/intelligence/src/handlers/tree_stamping_handler.py`

**Location**: After line 260 (inside `_handle_index_project()`)

```python
# BEFORE (Lines 258-291):
files = payload.get("files")  # Phase 1: Inline content support
include_tests = payload.get("include_tests", True)
force_reindex = payload.get("force_reindex", False)

# Validate required fields
if not project_path or not project_name:
    logger.error(...)
    await self._publish_index_failed(...)
    return False

# Log inline content usage
if files:
    logger.info(f"Processing with {len(files)} files (inline content) | ...")
else:
    logger.info(f"Processing INDEX_PROJECT_REQUESTED | ... (Phase 0)")

# AFTER:
files = payload.get("files")  # Phase 1: Inline content support
include_tests = payload.get("include_tests", True)
force_reindex = payload.get("force_reindex", False)

# Validate required fields
if not project_path or not project_name:
    logger.error(...)
    await self._publish_index_failed(...)
    return False

# Validate inline content provided (Phase 0 removed)
if not files:
    error_msg = (
        "files parameter is required. Phase 0 (filesystem-based indexing) "
        "has been removed. Use bulk_ingest_repository.py to send inline content."
    )
    logger.error(f"{error_msg} | correlation_id={correlation_id}")
    await self._publish_index_failed(
        correlation_id=correlation_id,
        project_name=project_name,
        error_code=EnumIndexingErrorCode.INVALID_INPUT,
        error_message=error_msg,
        duration_ms=(time.perf_counter() - start_time) * 1000,
        retry_recommended=False,
    )
    self.metrics["index_project_failures"] += 1
    return False

# Log inline content usage
logger.info(
    f"Processing with {len(files)} files (inline content) | "
    f"correlation_id={correlation_id} | project_name={project_name}"
)
```

---

### Step 2: Remove Phase 0 Methods

**Goal**: Delete all filesystem-dependent code paths

**Changes**:

**File**: `services/intelligence/src/integrations/tree_stamping_bridge.py`

**Change 2A: Delete _discover_tree() method (Lines 580-650)**
```python
# DELETE ENTIRE METHOD:
async def _discover_tree(
    self,
    project_path: str,
    include_tests: bool = True,
    max_depth: Optional[int] = None,
) -> Dict[str, Any]:
    """Discover project files using local FileDiscoveryService."""
    # ... (entire method body - 71 lines)
```

**Reason**: No longer called after Step 1 validation added

---

**Change 2B: Remove FileDiscoveryService import (Line 78)**
```python
# DELETE:
from ..services.file_discovery import FileDiscoveryService
```

---

**Change 2C: Remove FileDiscoveryService type hint (Line 191)**
```python
# BEFORE:
self.file_discovery_service: Optional[FileDiscoveryService] = None

# AFTER:
# (Remove line entirely)
```

---

**Change 2D: Remove FileDiscoveryService initialization (Lines 1624-1627)**
```python
# DELETE:
# FileDiscoveryService (local service, no network calls)
if not self.file_discovery_service:
    self.file_discovery_service = FileDiscoveryService()
    logger.debug("FileDiscoveryService initialized")
```

---

**Change 2E: Remove cleanup comment (Lines 1741-1743)**
```python
# DELETE:
# FileDiscoveryService is local, no cleanup needed (keep it alive for reuse)
# Don't set to None - it's a lightweight local service with no resources to cleanup
```

---

### Step 3: Delete FileDiscoveryService Entirely

**Goal**: Remove service file that's no longer used

**Changes**:

**File**: `services/intelligence/src/services/file_discovery.py`

**Action**: **DELETE ENTIRE FILE** (733 lines)

**Reason**:
- Only used by deleted `_discover_tree()` method
- No Phase 1 use cases
- Not used by bulk_ingest_repository.py (uses script-local version)

---

**File**: `services/intelligence/src/models/file_discovery.py`

**Action**: **EVALUATE** - Check if models are used elsewhere

```bash
# Check usage:
grep -r "FileDiscoveryResult\|FileDiscoveryStats\|FileInfo" services/intelligence/src --include="*.py" | grep -v "file_discovery.py"
```

**Decision**:
- If ONLY used by FileDiscoveryService → Delete models file
- If used elsewhere → Keep models, remove unused ones

---

### Step 4: Update Tests

**Goal**: Remove Phase 0 tests, add Phase 1 validation tests

**Changes**:

**File**: `services/intelligence/tests/services/test_file_discovery.py`

**Action**: **DELETE ENTIRE FILE**

**Reason**: No service to test after removal

---

**File**: `services/intelligence/tests/unit/handlers/test_tree_stamping_handler.py`

**Action**: **ADD TEST** for files=None validation

**New Test**:
```python
@pytest.mark.asyncio
async def test_index_project_files_parameter_required():
    """Test that files parameter is required (Phase 0 removed)."""
    handler = TreeStampingHandler()

    # Create event without files parameter
    event = event_factory(
        event_type="tree.index-project-requested",
        payload={
            "project_path": "/test/project",
            "project_name": "test-project",
            # files parameter missing
        }
    )

    # Handle event
    success = await handler.handle_event(event)

    # Should fail with clear error
    assert not success
    assert handler.metrics["index_project_failures"] == 1

    # Verify error message published (check mock calls)
    # ... (verify INVALID_INPUT error code)
```

---

**File**: `services/intelligence/tests/integration/test_tree_stamping_events.py`

**Action**: **VERIFY** all tests provide inline content

```bash
# Check for missing files parameter:
grep -n "index_project" test_tree_stamping_events.py | grep -v "files="
```

**Update**: Add `files=` parameter to any tests missing it

---

### Step 5: Update Documentation

**Goal**: Remove Phase 0 references, clarify Phase 1 as only mode

**Changes**:

**File**: `CLAUDE.md` (Project documentation)

**Search for**:
- "Phase 0"
- "filesystem-based"
- "FileDiscoveryService"
- "tree discovery"

**Update sections**:

**Section**: "Architecture" → Update tree stamping pipeline description
```markdown
# BEFORE:
1. Tree Discovery (Local FileDiscoveryService) → File enumeration
2. Intelligence Generation (Bridge) → Semantic analysis + quality scoring

# AFTER:
1. Inline Content Ingestion (Kafka events) → Files + content from host
2. Intelligence Generation (Bridge) → Semantic analysis + quality scoring
```

---

**Section**: "Quick Start" → Update example
```markdown
# BEFORE:
# (May show filesystem-based examples)

# AFTER:
# Index repository with inline content
python3 scripts/bulk_ingest_repository.py /path/to/project \
  --project-name my-project \
  --kafka-servers 192.168.86.200:29092

# Check indexing status
curl http://localhost:8053/api/tree-stamping/status?project_name=my-project
```

---

**File**: `services/intelligence/INTELLIGENCE_SERVICE.md` (if exists)

**Update**: Architecture diagrams, API documentation

---

**File**: `.env.example`

**Search for**: HOST_PROJECT_ROOT, CONTAINER_PROJECT_ROOT (Docker path translation)

**Action**: Remove or mark as deprecated if no longer used

---

### Step 6: Add Deprecation Notices (Optional Pre-Removal Step)

**Goal**: Warn users before hard removal

**Changes** (if gradual migration desired):

**File**: `tree_stamping_bridge.py`

**Location**: In `index_project()` before validation

```python
# Optional deprecation warning (if gradual migration)
if not files:
    logger.warning(
        "⚠️  DEPRECATION WARNING: Phase 0 (filesystem-based indexing) "
        "is deprecated and will be removed in the next release. "
        "Use bulk_ingest_repository.py which provides inline content."
    )
    # Still allow Phase 0 for now
```

**Note**: Skip this step if immediate removal is acceptable

---

## Implementation Steps (Detailed)

### Task 1: Validate Inline Content Required

**Duration**: 30 minutes

**Files**:
- `services/intelligence/src/integrations/tree_stamping_bridge.py`
- `services/intelligence/src/handlers/tree_stamping_handler.py`

**Steps**:

1. **Edit bridge validation** (bridge lines 306-320):
   ```bash
   # Open file
   code services/intelligence/src/integrations/tree_stamping_bridge.py:306

   # Replace lines 306-320 with validation (see Step 1, Change 1A above)
   ```

2. **Edit intelligence generation validation** (bridge lines 693-716):
   ```bash
   # Open file
   code services/intelligence/src/integrations/tree_stamping_bridge.py:693

   # Replace lines 693-716 with validation (see Step 1, Change 1B above)
   ```

3. **Edit handler validation** (handler lines 258-291):
   ```bash
   # Open file
   code services/intelligence/src/handlers/tree_stamping_handler.py:258

   # Add validation after line 260 (see Step 1, Change 1C above)
   ```

4. **Test validation**:
   ```bash
   # Create test event without files parameter
   python3 -c "
   import asyncio
   from src.handlers.tree_stamping_handler import TreeStampingHandler

   async def test():
       handler = TreeStampingHandler()
       event = {
           'event_type': 'tree.index-project-requested',
           'correlation_id': 'test-123',
           'payload': {
               'project_path': '/test',
               'project_name': 'test',
               # files missing
           }
       }
       result = await handler.handle_event(event)
       print(f'Result: {result}')  # Should be False

   asyncio.run(test())
   "
   ```

---

### Task 2: Remove Phase 0 Methods

**Duration**: 30 minutes

**Files**:
- `services/intelligence/src/integrations/tree_stamping_bridge.py`

**Steps**:

1. **Delete _discover_tree() method** (lines 580-650):
   ```bash
   # Open file
   code services/intelligence/src/integrations/tree_stamping_bridge.py:580

   # Delete lines 580-650 (entire method)
   ```

2. **Remove import** (line 78):
   ```bash
   # Delete import line:
   # from ..services.file_discovery import FileDiscoveryService
   ```

3. **Remove type hint** (line 191):
   ```bash
   # Delete line:
   # self.file_discovery_service: Optional[FileDiscoveryService] = None
   ```

4. **Remove initialization** (lines 1624-1627):
   ```bash
   # Delete FileDiscoveryService initialization block
   ```

5. **Remove cleanup comment** (lines 1741-1743):
   ```bash
   # Delete cleanup comment
   ```

6. **Verify no remaining references**:
   ```bash
   grep -n "file_discovery_service\|FileDiscoveryService\|_discover_tree" \
     services/intelligence/src/integrations/tree_stamping_bridge.py

   # Should return no results
   ```

---

### Task 3: Delete FileDiscoveryService

**Duration**: 15 minutes

**Files**:
- `services/intelligence/src/services/file_discovery.py`
- `services/intelligence/src/models/file_discovery.py` (conditional)

**Steps**:

1. **Check model usage**:
   ```bash
   # Find usages of FileDiscoveryResult, FileInfo, FileDiscoveryStats
   grep -r "FileDiscoveryResult\|FileDiscoveryStats\|FileInfo" \
     services/intelligence/src \
     --include="*.py" \
     | grep -v "file_discovery.py" \
     | grep -v "__pycache__"
   ```

2. **Delete service file**:
   ```bash
   rm services/intelligence/src/services/file_discovery.py
   ```

3. **Delete models file** (if unused elsewhere):
   ```bash
   # Only if step 1 shows no usages
   rm services/intelligence/src/models/file_discovery.py
   ```

4. **Verify imports**:
   ```bash
   # Check for broken imports
   python3 -m py_compile services/intelligence/src/integrations/tree_stamping_bridge.py
   python3 -m py_compile services/intelligence/src/handlers/tree_stamping_handler.py
   ```

---

### Task 4: Update Tests

**Duration**: 45 minutes

**Files**:
- `services/intelligence/tests/services/test_file_discovery.py`
- `services/intelligence/tests/unit/handlers/test_tree_stamping_handler.py`
- `services/intelligence/tests/integration/test_tree_stamping_events.py`

**Steps**:

1. **Delete FileDiscoveryService tests**:
   ```bash
   rm services/intelligence/tests/services/test_file_discovery.py
   ```

2. **Add validation test to handler tests**:
   ```bash
   # Open file
   code services/intelligence/tests/unit/handlers/test_tree_stamping_handler.py

   # Add new test (see Step 4 above)
   ```

3. **Verify integration tests provide inline content**:
   ```bash
   # Check integration tests
   grep -n "index_project" \
     services/intelligence/tests/integration/test_tree_stamping_events.py \
     | grep -v "files="

   # If any results, add files parameter to those tests
   ```

4. **Run tests**:
   ```bash
   cd services/intelligence
   pytest tests/unit/handlers/test_tree_stamping_handler.py -v
   pytest tests/integration/test_tree_stamping_events.py -v
   ```

---

### Task 5: Update Documentation

**Duration**: 30 minutes

**Files**:
- `/Volumes/PRO-G40/Code/omniarchon/CLAUDE.md`
- `services/intelligence/README.md` (if exists)
- `.env.example`

**Steps**:

1. **Search for Phase 0 references**:
   ```bash
   grep -rn "Phase 0\|filesystem-based\|FileDiscoveryService\|tree discovery" \
     --include="*.md" \
     /Volumes/PRO-G40/Code/omniarchon/
   ```

2. **Update CLAUDE.md**:
   ```bash
   code /Volumes/PRO-G40/Code/omniarchon/CLAUDE.md

   # Update Architecture section (see Step 5 above)
   # Update Quick Start section
   # Remove Phase 0 mentions
   ```

3. **Update .env.example**:
   ```bash
   code /Volumes/PRO-G40/Code/omniarchon/.env.example

   # Remove or mark as deprecated:
   # HOST_PROJECT_ROOT
   # CONTAINER_PROJECT_ROOT
   ```

4. **Update service documentation** (if exists):
   ```bash
   # Update services/intelligence/README.md or similar
   ```

---

### Task 6: End-to-End Test

**Duration**: 30 minutes

**Steps**:

1. **Test inline content ingestion** (Phase 1):
   ```bash
   # Run bulk ingestion with small project
   python3 scripts/bulk_ingest_repository.py \
     /Volumes/PRO-G40/Code/omninode_bridge \
     --project-name test_phase1_only \
     --kafka-servers 192.168.86.200:29092 \
     --batch-size 5 \
     --max-files 10

   # Monitor logs - should see:
   # - "Processing with N files (inline content)"
   # - No filesystem errors
   # - No "Project path does not exist" errors
   ```

2. **Test error handling** (missing files parameter):
   ```bash
   # Manually publish event without files parameter
   python3 -c "
   from aiokafka import AIOKafkaProducer
   import asyncio
   import json

   async def test_missing_files():
       producer = AIOKafkaProducer(
           bootstrap_servers='192.168.86.200:29092'
       )
       await producer.start()
       try:
           event = {
               'event_type': 'tree.index-project-requested',
               'correlation_id': 'test-missing-files',
               'payload': {
                   'project_path': '/test',
                   'project_name': 'test',
                   # files parameter intentionally missing
               }
           }
           await producer.send_and_wait(
               'dev.archon-intelligence.tree.index-project-requested.v1',
               value=json.dumps(event).encode()
           )
           print('✅ Event published')
       finally:
           await producer.stop()

   asyncio.run(test_missing_files())
   "

   # Check logs - should see clear error message:
   # "files parameter is required. Phase 0 (filesystem-based indexing) has been removed..."
   ```

3. **Verify data indexed correctly**:
   ```bash
   # Check Qdrant
   curl "http://192.168.86.200:6333/collections/file_locations"

   # Check Memgraph
   docker exec archon-memgraph \
     mgconsole --host localhost --port 7687 \
     --use-ssl=false \
     --run "MATCH (f:File {project: 'test_phase1_only'}) RETURN count(f);"
   ```

4. **Run full test suite**:
   ```bash
   cd services/intelligence
   pytest tests/ -v --maxfail=5
   ```

---

## Testing Strategy

### Unit Tests

**Goal**: Verify validation logic and error handling

**Tests to add**:

1. **test_index_project_files_required**:
   - Verify error when files=None
   - Verify correct error code (INVALID_INPUT)
   - Verify retry_recommended=False

2. **test_generate_intelligence_content_required**:
   - Verify None returned when provided_content=None
   - Verify error logged

**Tests to remove**:
- All tests in `test_file_discovery.py` (file deleted)

---

### Integration Tests

**Goal**: Verify E2E flow with inline content

**Tests to verify**:

1. **test_tree_stamping_events_full_flow**:
   - Ensure files parameter provided
   - Verify inline content processed
   - Verify no filesystem access attempts

2. **test_tree_stamping_error_handling**:
   - Add test for missing files parameter
   - Verify FAILED event published

---

### E2E Test Plan

**Test Case 1: Happy Path (Phase 1 Inline Content)**

**Steps**:
1. Run `bulk_ingest_repository.py` on small project (10-20 files)
2. Monitor Kafka topics for events
3. Monitor handler logs for processing
4. Verify data in Qdrant and Memgraph
5. Verify no filesystem errors

**Expected Results**:
- ✅ All files indexed successfully
- ✅ Logs show "Processing with N files (inline content)"
- ✅ No filesystem access errors
- ✅ Data appears in Qdrant and Memgraph

---

**Test Case 2: Error Path (Missing Files Parameter)**

**Steps**:
1. Manually publish Kafka event without files parameter
2. Monitor handler logs
3. Check for FAILED event on response topic

**Expected Results**:
- ✅ Clear error message: "files parameter is required..."
- ✅ INVALID_INPUT error code
- ✅ retry_recommended=False
- ✅ No filesystem access attempts
- ✅ FAILED event published

---

**Test Case 3: Regression (Verify Existing Functionality)**

**Steps**:
1. Run existing integration tests
2. Run performance benchmarks
3. Verify all tests pass

**Expected Results**:
- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ Performance targets met (<95s for 1000 files)

---

## Success Criteria

- ✅ **No Phase 0 code remains**: grep returns 0 results for Phase 0 patterns
- ✅ **files=None causes clear error**: Validation blocks processing with helpful message
- ✅ **No filesystem access attempts**: No PathNotFound or permission errors from container
- ✅ **All tests pass**: Unit, integration, and E2E tests succeed
- ✅ **E2E test succeeds**: bulk_ingest_repository.py → Kafka → handler → bridge works
- ✅ **Documentation updated**: No Phase 0 mentions in docs
- ✅ **Clear error messages**: Users guided to Phase 1 approach (bulk_ingest_repository.py)

---

## Rollback Plan

**If issues discovered during implementation**:

1. **Revert commits**:
   ```bash
   # Assuming changes committed incrementally
   git log --oneline -10
   git revert <commit-hash>  # Revert in reverse order
   ```

2. **Keep both modes temporarily**:
   - Re-add Phase 0 fallback with deprecation warning
   - Fix identified issues in Phase 1
   - Retry removal

3. **Document blocking issues**:
   - Create GitHub issue with details
   - Add to plan for investigation

**Critical Issues**:
- If bulk_ingest_repository.py has bugs → Fix before removing Phase 0
- If inline content size limits hit → Investigate chunking strategies
- If Kafka throughput insufficient → Optimize batch processing

---

## Risk Assessment

### High Risks

**Risk 1: Breaking Existing Workflows**

**Impact**: Users with Phase 0 workflows will fail
**Mitigation**:
- Add clear error messages pointing to Phase 1 approach
- Update documentation with migration guide
- Provide bulk_ingest_repository.py as easy replacement

---

**Risk 2: Unforeseen Phase 0 Dependencies**

**Impact**: Code we didn't analyze uses Phase 0
**Mitigation**:
- Comprehensive grep for Phase 0 patterns
- Run full test suite before committing
- Monitor logs after deployment

---

### Medium Risks

**Risk 3: Test Coverage Gaps**

**Impact**: Missing tests for edge cases
**Mitigation**:
- Add validation tests for files=None
- Verify integration tests provide inline content
- E2E test before considering complete

---

**Risk 4: Documentation Outdated**

**Impact**: Users confused by old docs
**Mitigation**:
- Search all .md files for Phase 0 mentions
- Update CLAUDE.md, README.md, .env.example
- Add migration guide if needed

---

### Low Risks

**Risk 5: Performance Regression**

**Impact**: Phase 1 slower than Phase 0
**Mitigation**:
- Run performance benchmarks after removal
- Compare against baseline (<95s for 1000 files)
- Optimize if regressions detected

---

## Timeline

| Task | Duration | Dependencies |
|------|----------|-------------|
| **Analysis** | 30 mins | - (completed) |
| **Validation** (Task 1) | 30 mins | Analysis |
| **Remove Methods** (Task 2) | 30 mins | Validation |
| **Delete Service** (Task 3) | 15 mins | Remove Methods |
| **Update Tests** (Task 4) | 45 mins | Delete Service |
| **Update Docs** (Task 5) | 30 mins | - |
| **E2E Test** (Task 6) | 30 mins | All above |
| **Contingency** | 30 mins | - |
| **TOTAL** | **4 hours** | - |

---

## Next Steps (After Plan Approval)

1. **Review plan with user**:
   - Confirm removal is desired
   - Discuss any concerns
   - Adjust timeline if needed

2. **Execute Task 1** (Validation):
   - Add validation to bridge and handler
   - Test validation works
   - Commit changes

3. **Execute Tasks 2-3** (Removal):
   - Remove Phase 0 methods
   - Delete FileDiscoveryService
   - Verify no broken imports

4. **Execute Task 4** (Tests):
   - Update test suite
   - Add validation tests
   - Run full test suite

5. **Execute Task 5** (Documentation):
   - Update CLAUDE.md
   - Update .env.example
   - Search for remaining references

6. **Execute Task 6** (E2E Test):
   - Test inline content flow
   - Test error handling
   - Verify data indexed correctly

7. **Commit and deploy**:
   - Create PR with all changes
   - Run CI/CD pipeline
   - Monitor production logs

---

## Appendix A: Verification Commands

**Check for Phase 0 references**:
```bash
grep -rn "Phase 0\|filesystem-based\|_discover_tree\|FileDiscoveryService" \
  services/intelligence/src \
  --include="*.py" \
  | grep -v "__pycache__"
```

**Check for imports**:
```bash
grep -rn "from.*file_discovery import" \
  services/intelligence/src \
  --include="*.py"
```

**Verify no filesystem access**:
```bash
grep -rn "Path(.*).exists()\|Path(.*).read_text()\|os.walk" \
  services/intelligence/src/integrations/tree_stamping_bridge.py
```

**Run test suite**:
```bash
cd services/intelligence
pytest tests/ -v --tb=short
```

---

## Appendix B: Error Message Templates

**Handler Error (files=None)**:
```
files parameter is required. Phase 0 (filesystem-based indexing) has been removed.
Use bulk_ingest_repository.py to send inline content via Kafka events.

Example:
  python3 scripts/bulk_ingest_repository.py /path/to/project \
    --project-name my-project \
    --kafka-servers 192.168.86.200:29092
```

**Bridge Error (files=None)**:
```
files parameter is required. Phase 0 (filesystem-based indexing) has been removed.
Use bulk_ingest_repository.py which provides inline content in Kafka messages.
```

**Intelligence Generation Error (provided_content=None)**:
```
No inline content provided for {file_path}. Phase 0 (filesystem-based) has been removed.
Ensure files parameter includes content for all files.
```

---

## Appendix C: Migration Guide (For Users)

**If you were using Phase 0 filesystem-based indexing:**

**Old Workflow** (Phase 0 - No longer supported):
```bash
# Publish event with just project_path
# Container would read files from filesystem
```

**New Workflow** (Phase 1 - Required):
```bash
# Use bulk_ingest_repository.py to read files on host
# Script sends inline content in Kafka messages
python3 scripts/bulk_ingest_repository.py /path/to/project \
  --project-name my-project \
  --kafka-servers 192.168.86.200:29092
```

**Benefits of Phase 1**:
- ✅ No container filesystem mounts required
- ✅ Cloud-native architecture
- ✅ Better security (no container filesystem access)
- ✅ Clearer errors and debugging
- ✅ Simpler deployment

---

**End of Plan**

**Status**: Ready for review and approval
**Next**: Execute Task 1 (Validation) after user approval
