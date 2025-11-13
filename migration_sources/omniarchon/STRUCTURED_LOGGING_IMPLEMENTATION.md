# Structured Logging Implementation for Orphan Detection and Tree Building

**Date**: 2025-11-11
**Correlation ID**: 07f64ef3-3b04-4bc3-94d8-0040fb044276
**Agent**: debug-intelligence
**Status**: ✅ Complete

## Summary

Added comprehensive structured logging with correlation IDs across the ingestion pipeline to enable full traceability of tree building operations, orphan detection, and batch processing metrics.

---

## Changes Overview

### 1. **scripts/bulk_ingest_repository.py**

#### Added Structured Logging Helper (Lines 189-222)
```python
def log_structured(
    logger_instance: logging.Logger,
    level: int,
    message: str,
    correlation_id: str,
    **extra_fields,
) -> None:
    """Log with structured JSON format for machine parsing."""
```

**Purpose**: Centralized structured logging function that outputs JSON-formatted logs with correlation IDs for machine parsing and distributed tracing.

#### Enhanced build_directory_tree() Method

**Tree Building Start (Lines 356-384)**
- Added structured logging for tree building start
- Logs correlation_id, project_name, project_root, operation timestamp

**FILE Node Query (Lines 409-463)**
- Added DEBUG log for Memgraph query operation
- Logs correlation_id, phase, operation, project_name
- Structured WARNING if no FILE nodes found

**Tree Building Complete (Lines 466-516)**
- Logs structured INFO with comprehensive metrics:
  - `nodes_created`: Total PROJECT + DIRECTORY nodes
  - `projects_created`: Number of PROJECT nodes
  - `directories_created`: Number of DIRECTORY nodes
  - `files_linked`: Number of FILE nodes linked
  - `relationships_created`: Number of CONTAINS relationships
  - `duration_ms`: Total tree building time

**Orphan Detection (Lines 518-594)**
- Added Cypher query to detect orphaned FILE nodes:
  ```cypher
  MATCH (f:FILE)
  WHERE f.project_name = $project_name
  AND NOT EXISTS { MATCH (d:DIRECTORY)-[:CONTAINS]->(f) }
  AND NOT EXISTS { MATCH (p:PROJECT)-[:CONTAINS]->(f) }
  RETURN f.path, f.entity_id
  ```
- Logs structured WARNING for each orphaned file detected
- Includes file_path, entity_id, expected_parent
- Logs summary if >5 orphans detected
- Logs structured INFO if 0 orphans (success case)

**Error Handling (Lines 599-633)**
- ImportError: Structured WARNING with error_type, error_message
- General Exception: Structured ERROR with duration_ms, error details

---

### 2. **scripts/lib/file_discovery.py**

#### Added Structured Logging Helper (Lines 27-60)
```python
def log_structured_discovery(
    logger_instance: logging.Logger,
    level: int,
    message: str,
    correlation_id: str,
    **extra_fields,
) -> None:
```

**Purpose**: Specialized structured logging for file discovery operations.

#### Added Orphan Detection Data Models (Lines 676-722)

**OrphanFile Dataclass**
```python
@dataclass
class OrphanFile:
    file_path: str
    entity_id: str
    expected_parent: Optional[str]
    project_name: str
```

**OrphanDetectionResult Dataclass**
```python
@dataclass
class OrphanDetectionResult:
    orphans_detected: int
    orphans: List[OrphanFile]
    orphans_fixed: int = 0
    orphans_remaining: int = 0
    detection_duration_ms: float = 0.0
```

#### Added Orphan Detection Logging Function (Lines 725-789)
```python
def log_orphan_detection(
    correlation_id: str,
    result: OrphanDetectionResult,
    project_name: str,
) -> None:
```

**Features**:
- Logs structured INFO if 0 orphans detected
- Logs structured WARNING if orphans detected
- Logs first 10 orphan file details with correlation_id
- Logs summary if >10 orphans detected
- All logs include phase, operation, orphan_count, project_name

---

### 3. **scripts/lib/batch_processor.py**

#### Added Structured Logging Helper (Lines 34-67)
```python
def log_structured_batch(
    logger_instance: logging.Logger,
    level: int,
    message: str,
    correlation_id: str,
    **extra_fields,
) -> None:
```

**Purpose**: Specialized structured logging for batch processing operations.

#### Enhanced process_files() Method (Lines 433-456)

**Batch Processing Metrics**
- Added structured INFO log at completion
- Metrics logged:
  - `total_files`: Total files processed
  - `total_batches`: Total batches created
  - `successful_batches`: Batches published successfully
  - `failed_batches`: Batches that failed
  - `success_rate`: Percentage of successful batches
  - `large_files_excluded`: Files using path-only strategy
  - `batches_split`: Batches split due to size limits
  - `total_duration_ms`: Total processing time
  - `avg_batch_duration_ms`: Average time per batch
  - `files_per_second`: Throughput metric

#### Enhanced _process_batch() Method

**Dry Run Logging (Lines 617-628)**
- Structured INFO log for dry-run mode
- Includes batch_id, files_count, large_files_count, topic

**Successful Publish (Lines 639-651)**
- Structured INFO log for successful Kafka publish
- Includes batch_id, files_count, large_files_count, topic, duration_ms

**Error Handling (Lines 667-679)**
- Structured ERROR log for batch failures
- Includes batch_id, files_count, error_type, error_message, duration_ms

---

## Structured Logging Format

### JSON Log Entry Format
```json
{
  "timestamp": "2025-11-11T12:34:56.789Z",
  "correlation_id": "07f64ef3-3b04-4bc3-94d8-0040fb044276",
  "message": "Human-readable message",
  "phase": "tree_building",
  "operation": "complete",
  "project_name": "omniarchon",
  "nodes_created": 12,
  "directories_created": 10,
  "files_linked": 143,
  "relationships_created": 148,
  "duration_ms": 1234.56
}
```

### Log Levels Used
- **DEBUG**: Detailed operation steps (queries, intermediate states)
- **INFO**: Normal operations (start, complete, success)
- **WARNING**: Orphan detection, degraded states, skipped operations
- **ERROR**: Failures, exceptions, critical issues

---

## Correlation ID Usage

### Propagation Pattern
1. Generated in `BulkIngestApp.run()` at workflow start
2. Passed to `build_directory_tree(correlation_id)`
3. Included in all log statements via `extra` fields
4. Enables end-to-end tracing across all operations

### Benefits
- ✅ **Traceability**: Link all logs from single ingestion run
- ✅ **Debugging**: Filter logs by correlation_id to debug specific runs
- ✅ **Observability**: Track operations across multiple services
- ✅ **Performance Analysis**: Measure duration of specific operations

---

## Metrics Tracked

### Tree Building Metrics
| Metric | Type | Description |
|--------|------|-------------|
| `nodes_created` | int | Total PROJECT + DIRECTORY nodes created |
| `projects_created` | int | Number of PROJECT nodes |
| `directories_created` | int | Number of DIRECTORY nodes |
| `files_linked` | int | Number of FILE nodes linked via CONTAINS |
| `relationships_created` | int | Total CONTAINS relationships |
| `duration_ms` | float | Tree building duration |

### Orphan Detection Metrics
| Metric | Type | Description |
|--------|------|-------------|
| `orphan_count` | int | Number of orphaned FILE nodes detected |
| `orphans_fixed` | int | Orphans remediated |
| `orphans_remaining` | int | Orphans still present |
| `detection_duration_ms` | float | Orphan detection duration |

### Batch Processing Metrics
| Metric | Type | Description |
|--------|------|-------------|
| `total_files` | int | Total files processed |
| `total_batches` | int | Total batches created |
| `successful_batches` | int | Batches published successfully |
| `failed_batches` | int | Batches that failed |
| `success_rate` | float | Percentage successful (0-100) |
| `large_files_excluded` | int | Files using path-only strategy |
| `batches_split` | int | Batches split due to size |
| `total_duration_ms` | float | Total processing time |
| `avg_batch_duration_ms` | float | Average time per batch |
| `files_per_second` | float | Throughput metric |

---

## Usage Examples

### Running Ingestion with Structured Logging
```bash
# Standard run (logs to console)
python3 scripts/bulk_ingest_repository.py /path/to/project \
  --project-name my-project \
  --kafka-servers 192.168.86.200:29092

# Verbose mode (includes DEBUG logs)
python3 scripts/bulk_ingest_repository.py /path/to/project \
  --project-name my-project \
  --verbose
```

### Filtering Logs by Correlation ID
```bash
# View all logs for specific ingestion run
python3 scripts/view_pipeline_logs.py \
  --correlation-id 07f64ef3-3b04-4bc3-94d8-0040fb044276

# View only orphan detection logs
python3 scripts/view_pipeline_logs.py \
  --correlation-id 07f64ef3-3b04-4bc3-94d8-0040fb044276 \
  --filter "orphan"
```

### Parsing JSON Logs Programmatically
```python
import json

with open("logs/ingestion.log") as f:
    for line in f:
        try:
            log_entry = json.loads(line)
            if log_entry.get("phase") == "tree_building":
                print(f"Tree building: {log_entry['message']}")
                print(f"  Nodes created: {log_entry.get('nodes_created')}")
                print(f"  Duration: {log_entry.get('duration_ms')}ms")
        except json.JSONDecodeError:
            continue
```

---

## Testing

### Syntax Validation
```bash
# All files pass Python syntax check
python3 -m py_compile scripts/bulk_ingest_repository.py
python3 -m py_compile scripts/lib/file_discovery.py
python3 -m py_compile scripts/lib/batch_processor.py
```

### Integration Test
```bash
# Run ingestion and verify structured logs
python3 scripts/bulk_ingest_repository.py \
  /Volumes/PRO-G40/Code/omniarchon \
  --project-name omniarchon \
  --kafka-servers 192.168.86.200:29092 \
  --verbose 2>&1 | grep "correlation_id"
```

---

## Success Criteria

### Completed ✅
- [x] Structured logging added to all tree building operations
- [x] Orphan detection logged with WARNING level
- [x] Correlation IDs present in all log statements
- [x] JSON structured format for machine parsing
- [x] Metrics logged for nodes, relationships, orphans
- [x] Log levels appropriate (DEBUG/INFO/WARNING/ERROR)
- [x] All syntax checks pass
- [x] Logging follows ONEX patterns

---

## Files Modified

1. **scripts/bulk_ingest_repository.py**
   - Added `log_structured()` helper function
   - Enhanced `build_directory_tree()` with structured logging
   - Added orphan detection with structured logging
   - Enhanced error handling with structured logs

2. **scripts/lib/file_discovery.py**
   - Added `log_structured_discovery()` helper function
   - Added `OrphanFile` and `OrphanDetectionResult` dataclasses
   - Added `log_orphan_detection()` function
   - Updated exports

3. **scripts/lib/batch_processor.py**
   - Added `log_structured_batch()` helper function
   - Enhanced `process_files()` with metrics logging
   - Enhanced `_process_batch()` with structured logging
   - Enhanced error handling with structured logs

---

## Next Steps

### Recommended Enhancements
1. **Log Aggregation**: Configure centralized log aggregation (ELK stack, Grafana Loki)
2. **Monitoring Dashboards**: Build dashboards for orphan trends, tree building performance
3. **Alerting**: Set up alerts for high orphan counts, failed tree building
4. **Performance Baselines**: Establish baseline metrics for tree building duration
5. **Automated Remediation**: Add automated orphan remediation based on detection

### Integration Points
- **Observability Pipeline**: Logs ready for ingestion into observability platform
- **Correlation ID Tracking**: Can be extended to Kafka events, HTTP requests
- **Performance Monitoring**: Metrics can feed into monitoring systems (Prometheus, StatsD)
- **Error Tracking**: Structured errors can be sent to error tracking (Sentry, Rollbar)

---

## References

- **Task Context**: ADD_MISSING_LOGGING.md (orphan detection logging gaps)
- **Correlation ID**: 07f64ef3-3b04-4bc3-94d8-0040fb044276
- **Agent**: debug-intelligence
- **Pattern**: ONEX Orchestrator (workflow coordination with observability)

---

**Implementation Complete**: 2025-11-11
**Review Status**: ✅ Ready for Testing
