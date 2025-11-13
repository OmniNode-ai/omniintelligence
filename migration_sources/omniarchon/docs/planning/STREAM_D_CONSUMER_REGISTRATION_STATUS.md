# Stream D: Consumer Registration - Status Report

**Poly-D Report**
**Date**: 2025-10-24
**Status**: ⚠️ BLOCKED - Waiting for Stream B completion

---

## Executive Summary

Stream D (Consumer Registration) has investigated the Kafka consumer infrastructure and prepared all necessary documentation for registering the TreeStampingHandler. However, **Stream B (Event Handler) has not yet completed the TreeStampingHandler implementation**, which is a blocking dependency.

**Current Status**:
- ✅ Consumer infrastructure studied and understood
- ✅ Kafka topics already configured in docker-compose.yml (Stream F completed!)
- ✅ Registration pattern identified
- ✅ Consumer group configuration verified
- ❌ TreeStampingHandler implementation missing (Stream B dependency)
- ❌ Event schemas missing (Stream A dependency)
- ⏸️ Registration blocked until Stream B completes

---

## What Exists ✅

### 1. Kafka Topics Configuration (docker-compose.yml)

**Location**: `deployment/docker-compose.yml` (lines 231-235)

```yaml
# Tree + Stamping Event Adapter Topics (2025-10-24)
- KAFKA_TREE_INDEX_PROJECT_REQUEST=${KAFKA_TREE_INDEX_PROJECT_REQUEST:-dev.archon-intelligence.tree.index-project-requested.v1}
- KAFKA_TREE_SEARCH_FILES_REQUEST=${KAFKA_TREE_SEARCH_FILES_REQUEST:-dev.archon-intelligence.tree.search-files-requested.v1}
- KAFKA_TREE_GET_STATUS_REQUEST=${KAFKA_TREE_GET_STATUS_REQUEST:-dev.archon-intelligence.tree.get-status-requested.v1}
- KAFKA_TREE_INDEX_PROJECT_COMPLETED=${KAFKA_TREE_INDEX_PROJECT_COMPLETED:-dev.archon-intelligence.tree.index-project-completed.v1}
- KAFKA_TREE_INDEX_PROJECT_FAILED=${KAFKA_TREE_INDEX_PROJECT_FAILED:-dev.archon-intelligence.tree.index-project-failed.v1}
```

**Status**: ✅ Complete - Stream F has already configured these topics!

### 2. Consumer Infrastructure

**Location**: `services/intelligence/src/kafka_consumer.py`

**Key Components**:
- `IntelligenceKafkaConsumer` class (lines 100-1061)
- `_register_handlers()` method (lines 284-420)
- `create_intelligence_kafka_consumer()` factory (lines 1068-1486)
- Handler registry pattern (list-based, dynamic routing)
- 21 handlers already registered successfully

**Pattern Identified**:
```python
# In _register_handlers() method:
handler_instance = HandlerClass(dependencies)
self.handlers.append(handler_instance)
logger.info(f"Registered {handler_instance.get_handler_name()}")
```

### 3. Consumer Configuration

**Consumer Group**: `archon-intelligence` (line 1094)
- Auto-commit: Enabled
- Max poll records: 500
- Session timeout: 30s
- Backpressure control: 100 max in-flight events

**Topics Subscribed** (lines 1102-1469):
- 78+ topics already configured across 4 phases
- Pattern: `dev.archon-intelligence.{domain}.{operation}-requested.v1`

### 4. TreeStampingBridge Orchestrator

**Location**: `services/intelligence/src/integrations/tree_stamping_bridge.py`

**Status**: ✅ Complete - Orchestrator exists and is functional

**Key Methods**:
- `index_project()` - Main indexing pipeline
- `search_files()` - File location search
- `get_index_status()` - Status checking

**Dependencies**: This orchestrator will be called by TreeStampingHandler.

---

## What's Missing ❌

### 1. TreeStampingHandler Implementation

**Expected Location**: `services/intelligence/src/handlers/tree_stamping_handler.py`

**Status**: ❌ File does not exist - Stream B has not created it yet

**Required by Stream D**:
- Handler class extending `BaseResponsePublisher`
- `can_handle()` method for event type routing
- `handle_event()` method for processing
- `get_handler_name()` method for logging

### 2. Event Schemas

**Expected Location**: `services/intelligence/src/events/models/tree_stamping_events.py`

**Status**: ❌ File does not exist - Stream A has not created it yet

**Required for**:
- Type-safe payload validation
- Event envelope construction
- Request/response models

### 3. Topics in Consumer Factory

**Location**: `kafka_consumer.py::create_intelligence_kafka_consumer()` (lines 1102-1469)

**Status**: ❌ Tree stamping topics NOT added to the topics list

**Needs**: Addition of 3 request topic environment variables to the topics array

---

## Registration Steps (When Stream B Completes)

### Step 1: Verify Handler Implementation

**File to check**: `services/intelligence/src/handlers/tree_stamping_handler.py`

**Required components**:
```python
class TreeStampingHandler(BaseResponsePublisher):
    def __init__(self, bridge: TreeStampingBridge):
        super().__init__()
        self.bridge = bridge
        self.metrics = {...}

    def can_handle(self, event_type: str) -> bool:
        return event_type in [
            "tree.index-project-requested",
            "tree.search-files-requested",
            "tree.get-status-requested",
        ]

    async def handle_event(self, event) -> bool:
        # Implementation
        pass

    def get_handler_name(self) -> str:
        return "TreeStampingHandler"
```

### Step 2: Add Import to kafka_consumer.py

**File**: `services/intelligence/src/kafka_consumer.py`

**Location**: Add after line 54 (with other handler imports)

```python
from src.handlers.tree_stamping_handler import TreeStampingHandler
```

**Organize with**: Phase 4 imports (Bridge & Utility handlers) or create Phase 5 section

### Step 3: Add Topics to Consumer Factory

**File**: `services/intelligence/src/kafka_consumer.py`

**Location**: `create_intelligence_kafka_consumer()` function, topics array (after line 1468)

**Code to add**:
```python
# Tree + Stamping Integration Topics (2025-10-24)
os.getenv(
    "KAFKA_TREE_INDEX_PROJECT_REQUEST",
    "dev.archon-intelligence.tree.index-project-requested.v1",
),
os.getenv(
    "KAFKA_TREE_SEARCH_FILES_REQUEST",
    "dev.archon-intelligence.tree.search-files-requested.v1",
),
os.getenv(
    "KAFKA_TREE_GET_STATUS_REQUEST",
    "dev.archon-intelligence.tree.get-status-requested.v1",
),
```

### Step 4: Register Handler in _register_handlers()

**File**: `services/intelligence/src/kafka_consumer.py`

**Location**: `_register_handlers()` method (after line 414, before final logger.info)

**Code to add**:
```python
# ========== Phase 5: Tree + Stamping Integration ==========
# Tree Stamping handler (2025-10-24)
from src.integrations.tree_stamping_bridge import TreeStampingBridge

tree_stamping_bridge = TreeStampingBridge()
tree_stamping_handler = TreeStampingHandler(bridge=tree_stamping_bridge)
self.handlers.append(tree_stamping_handler)
logger.info("Registered TreeStampingHandler")
```

**Note**: TreeStampingBridge initialization may require async initialization - verify implementation.

### Step 5: Verify Registration

**Startup Log Check**:
```bash
docker compose logs archon-intelligence | grep "Registered TreeStampingHandler"
```

**Expected Output**:
```
archon-intelligence | INFO:src.kafka_consumer:Registered TreeStampingHandler
archon-intelligence | INFO:src.kafka_consumer:All 22 handlers registered successfully
```

### Step 6: Verify Topic Subscription

**Consumer Log Check**:
```bash
docker compose logs archon-intelligence | grep "Subscribed to topics"
```

**Expected**: Topics list includes:
- `dev.archon-intelligence.tree.index-project-requested.v1`
- `dev.archon-intelligence.tree.search-files-requested.v1`
- `dev.archon-intelligence.tree.get-status-requested.v1`

---

## Consumer Group Configuration ✅

**Consumer Group ID**: `archon-intelligence`

**Configuration** (from docker-compose.yml lines 213-219):
```yaml
- KAFKA_ENABLE_CONSUMER=true
- KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
- KAFKA_CONSUMER_GROUP=archon-intelligence
- KAFKA_AUTO_OFFSET_RESET=earliest
- KAFKA_ENABLE_AUTO_COMMIT=true
- KAFKA_MAX_POLL_RECORDS=500
- KAFKA_SESSION_TIMEOUT_MS=30000
```

**Backpressure Control**:
- Max in-flight events: 100 (from `KAFKA_MAX_IN_FLIGHT` env var, default 100)
- Prevents memory exhaustion under high load
- Semaphore-based throttling

**Error Handling**:
- Dead Letter Queue (DLQ) routing: `{original_topic}.dlq`
- Automatic retry with exponential backoff
- Circuit breaker patterns in HTTP clients

**Status**: ✅ No changes needed - existing configuration is appropriate

---

## Testing Checklist

### Unit Tests (After Registration)

**Test File**: `services/intelligence/tests/unit/test_tree_stamping_handler.py`

**Test Coverage**:
- [ ] `test_can_handle_index_project_event()`
- [ ] `test_can_handle_search_files_event()`
- [ ] `test_can_handle_get_status_event()`
- [ ] `test_handle_index_project_success()`
- [ ] `test_handle_index_project_failure()`
- [ ] `test_metrics_tracking()`
- [ ] `test_error_response_publishing()`

### Integration Tests

**Test File**: `services/intelligence/tests/integration/test_tree_stamping_event_flow.py`

**Test Coverage**:
- [ ] End-to-end event flow (publish → consume → process → respond)
- [ ] Correlation ID preservation
- [ ] Error event publishing
- [ ] Concurrent event processing
- [ ] DLQ routing on failure

### Manual Testing

**1. Service Startup**:
```bash
docker compose up archon-intelligence -d
docker compose logs archon-intelligence --tail 50
```

**Expected**:
- ✅ "Registered TreeStampingHandler"
- ✅ "All 22 handlers registered successfully"
- ✅ "Subscribed to topics: [... tree topics ...]"
- ✅ "Kafka consumer initialized successfully"

**2. Health Check**:
```bash
curl http://localhost:8053/health
```

**Expected**:
```json
{
  "status": "healthy",
  "kafka_consumer": {
    "status": "healthy",
    "handlers_count": 22
  }
}
```

**3. Publish Test Event** (requires external publisher):
```json
{
  "event_id": "test-123",
  "event_type": "tree.index-project-requested",
  "correlation_id": "test-correlation-123",
  "payload": {
    "project_path": "/tmp/test-project",
    "project_name": "test-project",
    "include_tests": true,
    "force_reindex": false
  }
}
```

**4. Monitor Event Processing**:
```bash
docker compose logs archon-intelligence --follow | grep "tree.index-project"
```

**Expected**:
- "Processing event: type=tree.index-project-requested"
- "Handling tree stamping event"
- "Event processed successfully"

---

## Dependencies Summary

### Stream Dependencies

| Stream | Status | Deliverable | Blocking Stream D? |
|--------|--------|-------------|-------------------|
| **Stream A** | ❌ Not Started | Event Schemas | Yes (indirectly) |
| **Stream B** | ❌ Not Started | TreeStampingHandler | **YES - CRITICAL** |
| **Stream C** | ❓ Unknown | Event Publisher | Partial (BaseResponsePublisher exists) |
| **Stream F** | ✅ Complete | Docker Config | No |

### Critical Path

```
Stream A (Schemas) → Stream B (Handler) → Stream D (Registration) → Testing
```

**Unblocking Stream D**:
1. Stream B must complete TreeStampingHandler implementation
2. Stream A should complete event schemas (for type safety)
3. Stream C may already be complete (BaseResponsePublisher provides publishing)

---

## Files Modified (When Unblocked)

### 1. kafka_consumer.py

**Location**: `services/intelligence/src/kafka_consumer.py`

**Changes**:
- Line ~54: Add TreeStampingHandler import
- Line ~415: Register handler in `_register_handlers()`
- Line ~1469: Add 3 topics to `create_intelligence_kafka_consumer()`

**Estimated Lines Added**: ~15 lines

### 2. No Other Files Need Changes

**Reason**:
- docker-compose.yml already has topics configured
- .env.example already documented by Stream F
- Consumer group configuration already appropriate

---

## Risk Assessment

### Low Risk ✅

1. **Consumer Group Configuration**: No changes needed, existing config is solid
2. **Topic Configuration**: Already done by Stream F
3. **Registration Pattern**: Well-established, 21 handlers already using it

### Medium Risk ⚠️

1. **TreeStampingBridge Initialization**: May require async initialization
   - **Mitigation**: Check bridge constructor, handle async init if needed
   - **Impact**: May need to add `await bridge.initialize()` call

2. **Event Type Mapping**: Topic names must match handler routing logic
   - **Mitigation**: Verify event_type extraction in `_extract_event_type()`
   - **Impact**: May need to update extraction logic for new topic pattern

### No Risk ✓

1. **Kafka Infrastructure**: Battle-tested with 78+ topics
2. **Error Handling**: DLQ and retry logic already in place
3. **Backpressure**: Semaphore-based throttling already working

---

## Recommendations

### Immediate Actions (Poly-D)

1. ✅ **Report Status to Coordination** - This document serves as the report
2. ✅ **Document Registration Steps** - Complete above
3. ⏸️ **Wait for Stream B** - Nothing to do until handler exists

### For Stream B (Handler Developer)

1. **Priority**: Complete TreeStampingHandler implementation ASAP
2. **Reference**: Use existing handlers as templates:
   - `bridge_intelligence_handler.py` - Similar integration pattern
   - `document_indexing_handler.py` - Similar async operations
3. **Testing**: Ensure `get_handler_name()` returns "TreeStampingHandler"
4. **Notify**: Alert Stream D when handler is ready for registration

### For Integration Testing

1. **Unit Tests First**: Stream B should include handler unit tests
2. **Integration Tests**: Stream E can start scaffolding tests now
3. **Manual Testing**: Use curl + Kafka CLI for quick validation

---

## Time Estimates (When Unblocked)

| Task | Time Estimate |
|------|--------------|
| Add handler import | 2 minutes |
| Add topics to factory | 5 minutes |
| Register handler | 10 minutes |
| Verify startup | 5 minutes |
| Test event consumption | 15 minutes |
| Debug any issues | 30 minutes |
| **Total** | **~1 hour** |

**Note**: Assumes Stream B delivers a working handler with no integration issues.

---

## Next Steps

### For Stream D (Poly-D)

1. ✅ Report findings to coordination
2. ⏸️ Wait for Stream B completion notification
3. ⏸️ Execute registration steps when unblocked
4. ⏸️ Verify registration with testing checklist

### For Project Coordination

1. ❗ **Prioritize Stream B** - Critical path blocker
2. ❗ **Stream A completion** - Also needed for Stream B
3. ℹ️ Stream C status - Verify if BaseResponsePublisher is sufficient
4. ℹ️ Update project timeline based on Stream B ETA

---

## Appendix: Handler Registration Pattern

### Complete Registration Example

**Based on existing handler pattern from kafka_consumer.py (lines 343-346)**:

```python
# ========== Phase 5: Tree + Stamping Integration ==========
# Tree Stamping handler (2025-10-24)
from src.integrations.tree_stamping_bridge import TreeStampingBridge
from src.handlers.tree_stamping_handler import TreeStampingHandler

# Initialize bridge (check if async init needed)
tree_stamping_bridge = TreeStampingBridge()
# If async init required:
# await tree_stamping_bridge.initialize()

# Create and register handler
tree_stamping_handler = TreeStampingHandler(bridge=tree_stamping_bridge)
self.handlers.append(tree_stamping_handler)
logger.info("Registered TreeStampingHandler")
```

### Handler Interface Contract

**Required methods** (from BaseResponsePublisher + handler pattern):

```python
class TreeStampingHandler(BaseResponsePublisher):
    def can_handle(self, event_type: str) -> bool:
        """Return True if handler can process this event type."""
        pass

    async def handle_event(self, event) -> bool:
        """Process event, return True if successful."""
        pass

    def get_handler_name(self) -> str:
        """Return handler name for logging."""
        return "TreeStampingHandler"
```

---

**Document Status**: Complete
**Last Updated**: 2025-10-24
**Prepared by**: Poly-D (Stream D: Consumer Registration)
**Ready for**: Stream B completion notification
