# Bulk Repository Ingestion CLI Tool

**Version**: 1.0.0
**Created**: 2025-10-27
**Purpose**: Index entire repositories into Archon Intelligence for semantic search and code intelligence

## Overview

The bulk ingestion CLI tool provides comprehensive repository indexing with:

- ✅ **Recursive file discovery** with intelligent filtering
- ✅ **Batch processing** for performance (configurable batch size)
- ✅ **Concurrent event publishing** to Kafka (configurable concurrency)
- ✅ **Progress tracking** and detailed logging
- ✅ **Error handling** with partial failure recovery
- ✅ **Dry-run mode** for testing without publishing events
- ✅ **Language detection** and file metadata extraction

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           bulk_ingest_repository.py (CLI)               │
│  Orchestrates workflow and user interface               │
└──────────────────┬──────────────────────────────────────┘
                   │
     ┌─────────────┼─────────────┐
     │             │             │
     ▼             ▼             ▼
┌─────────┐  ┌─────────┐  ┌─────────────┐
│  File   │  │  Batch  │  │   Kafka     │
│Discovery│  │Processor│  │Event Bus    │
└─────────┘  └─────────┘  └─────────────┘
     │             │             │
     ▼             ▼             ▼
Discovery     Batching      Publishing
& Filtering   & Async       to Topics
              Processing
```

### Workflow

1. **File Discovery Phase**
   - Recursive directory walking
   - Extension filtering (45+ supported languages)
   - Exclusion pattern matching (git, node_modules, build artifacts, etc.)
   - File size validation (default: 5MB max)
   - Language detection from extensions
   - Metadata extraction (size, modified time)

2. **Batch Processing Phase**
   - Split files into configurable batches (default: 50 files/batch)
   - Concurrent batch processing (default: 3 concurrent batches)
   - Kafka event publishing with correlation ID tracking
   - Progress tracking with percentage completion
   - Error handling with partial failure recovery

3. **Results Summary Phase**
   - Success/failure statistics
   - Language breakdown
   - Failed batch reporting
   - Performance metrics

## Installation & Dependencies

**Required Dependencies**:
```bash
# Install Python dependencies
pip install aiokafka pyyaml

# Or using Poetry (from project root)
poetry install
```

**System Requirements**:
- Python 3.10+
- Kafka/Redpanda event bus (default: 192.168.86.200:9092)
- Archon Intelligence Service (default: localhost:8053)

## Usage

### Basic Usage

```bash
# Index current directory
python scripts/bulk_ingest_repository.py .

# Index specific directory
python scripts/bulk_ingest_repository.py /path/to/project

# Index with custom project name
python scripts/bulk_ingest_repository.py /path/to/project --project-name my-project
```

### Dry Run Mode (Recommended for Testing)

```bash
# Test without publishing events
python scripts/bulk_ingest_repository.py /path/to/project --dry-run

# Dry run with verbose logging
python scripts/bulk_ingest_repository.py /path/to/project --dry-run --verbose
```

### Performance Tuning

```bash
# Custom batch size (larger batches = fewer events, more files per event)
python scripts/bulk_ingest_repository.py /path/to/project --batch-size 100

# Custom concurrency (more concurrent batches = faster processing)
python scripts/bulk_ingest_repository.py /path/to/project --max-concurrent 5

# Both combined
python scripts/bulk_ingest_repository.py /path/to/project --batch-size 100 --max-concurrent 5
```

### Custom Kafka Configuration

```bash
# Custom Kafka bootstrap servers
python scripts/bulk_ingest_repository.py /path/to/project --kafka-servers localhost:9092

# Custom Kafka topic
python scripts/bulk_ingest_repository.py /path/to/project --kafka-topic my.custom.topic.v1
```

### Verbose Logging

```bash
# Enable debug logging
python scripts/bulk_ingest_repository.py /path/to/project --verbose
```

## Command-Line Options

```
positional arguments:
  project_path          Path to project root directory

options:
  --project-name        Project name slug (default: directory name)
  --kafka-servers       Kafka bootstrap servers (default: 192.168.86.200:9092)
  --kafka-topic         Kafka topic (default: dev.archon-intelligence.tree.index-project-requested.v1)
  --batch-size          Files per batch (default: 50)
  --max-concurrent      Concurrent batches (default: 3)
  --max-file-size       Max file size in bytes (default: 5MB)
  --dry-run             Test mode (don't publish events)
  --verbose, -v         Debug logging
  -h, --help            Show help message
```

## Configuration

### Supported File Extensions (45+ Languages)

The tool automatically detects and processes files with these extensions:

- **Python**: `.py`, `.pyi`
- **JavaScript/TypeScript**: `.js`, `.jsx`, `.ts`, `.tsx`
- **Java/Kotlin**: `.java`, `.kt`
- **Rust**: `.rs`
- **Go**: `.go`
- **Ruby**: `.rb`
- **PHP**: `.php`
- **C/C++**: `.c`, `.h`, `.cpp`, `.hpp`, `.cc`, `.cxx`
- **C#**: `.cs`
- **Swift**: `.swift`
- **Scala**: `.scala`
- **And 30+ more languages**

### Exclusion Patterns (Default)

Files matching these patterns are automatically excluded:

- **Python**: `*.pyc`, `__pycache__/*`, `.pytest_cache/*`
- **JavaScript/Node**: `node_modules/*`, `*.min.js`, `dist/*`, `build/*`
- **Version Control**: `.git/*`, `.svn/*`, `.hg/*`
- **Virtual Environments**: `.venv/*`, `venv/*`, `env/*`
- **IDE**: `.idea/*`, `.vscode/*`, `.DS_Store`
- **Build Artifacts**: `target/*`, `out/*`, `bin/*`, `obj/*`
- **And 20+ more patterns**

## Examples

### Example 1: Quick Test (Dry Run)

```bash
$ python scripts/bulk_ingest_repository.py ./my-project --dry-run

09:05:16 [INFO] ======================================================================
09:05:16 [INFO] PHASE 1: FILE DISCOVERY
09:05:16 [INFO] ======================================================================
09:05:16 [INFO] Project: my-project
09:05:16 [INFO] Path: /path/to/my-project
09:05:16 [INFO]
09:05:16 [INFO] Discovery complete: 150 files (45 excluded, 2 oversized) in 23ms
09:05:16 [INFO]
09:05:16 [INFO] Language breakdown:
09:05:16 [INFO]   python         :    89 files
09:05:16 [INFO]   javascript     :    45 files
09:05:16 [INFO]   typescript     :    16 files
09:05:16 [INFO]
09:05:16 [INFO] ======================================================================
09:05:16 [INFO] PHASE 2: BATCH PROCESSING & EVENT PUBLISHING
09:05:16 [INFO] ======================================================================
09:05:16 [INFO] ⚠️  DRY RUN MODE - No events will be published
09:05:16 [INFO]
09:05:16 [INFO] Processing 150 files in 3 batches (batch_size=50)
09:05:16 [INFO] [DRY RUN] Batch 0: would publish 50 files...
09:05:16 [INFO] Progress: 1/3 batches (33%)
09:05:16 [INFO] [DRY RUN] Batch 1: would publish 50 files...
09:05:16 [INFO] Progress: 2/3 batches (67%)
09:05:16 [INFO] [DRY RUN] Batch 2: would publish 50 files...
09:05:16 [INFO] Progress: 3/3 batches (100%)
09:05:16 [INFO]
09:05:16 [INFO] ✅ All batches processed successfully!
```

### Example 2: Production Indexing

```bash
# Index production repository with optimized settings
$ python scripts/bulk_ingest_repository.py /path/to/large-repo \
    --project-name my-production-service \
    --batch-size 100 \
    --max-concurrent 5

# Expected output for 1000 files:
# - Discovery: <5s (file enumeration)
# - Processing: ~30s (event publishing)
# - Total: ~35s (well below 95s target)
```

### Example 3: Handling Large Repositories

```bash
# For repositories with 10,000+ files
$ python scripts/bulk_ingest_repository.py /path/to/massive-repo \
    --batch-size 200 \
    --max-concurrent 10 \
    --max-file-size 10485760  # 10MB

# Adjust batch size and concurrency based on:
# - Kafka broker capacity
# - Network bandwidth
# - Consumer processing speed
```

## Performance Characteristics

### Benchmarks (1000 files)

| Phase | Target | Typical |
|-------|--------|---------|
| Discovery | <5s | ~2-3s |
| Publishing | <30s | ~15-25s |
| **Total** | **<35s** | **~20-30s** |

**Note**: End-to-end indexing (discovery → stamping → vector indexing) target is <95s for 1000 files.

### Scalability

- **Small projects** (<100 files): <5s total
- **Medium projects** (100-1000 files): 20-30s total
- **Large projects** (1000-10,000 files): 3-5min total
- **Very large projects** (10,000+ files): ~30-60min total

**Scaling Factors**:
- Increase `--batch-size` for fewer Kafka events
- Increase `--max-concurrent` for faster parallel processing
- Monitor Kafka consumer lag and adjust accordingly

## Event Schema

### INDEX_PROJECT_REQUESTED Event

The tool publishes events with this structure:

```json
{
  "event_id": "uuid-v4",
  "event_type": "dev.archon-intelligence.tree.index-project-requested.v1",
  "correlation_id": "uuid-v4",
  "timestamp": "2025-10-27T10:00:00.000Z",
  "version": "1.0.0",
  "source": {
    "service": "bulk-ingest-cli",
    "instance_id": "batch-0"
  },
  "metadata": {
    "batch_id": 0,
    "batch_size": 50
  },
  "payload": {
    "project_name": "my-project",
    "project_path": "/path/to/project",
    "files": [
      {
        "file_path": "/absolute/path/to/file.py",
        "relative_path": "src/api.py",
        "size_bytes": 1234,
        "last_modified": "2025-10-27T09:30:00.000Z",
        "language": "python"
      }
    ],
    "include_tests": true,
    "force_reindex": false
  }
}
```

### Event Flow

```
CLI Tool
   │
   ├─> Kafka Topic: dev.archon-intelligence.tree.index-project-requested.v1
   │
   └─> Archon Intelligence Service (Consumer)
         │
         ├─> Tree Discovery (file validation)
         ├─> Intelligence Generation (quality scoring, ONEX classification)
         ├─> Vector Indexing (Qdrant)
         ├─> Graph Indexing (Memgraph)
         └─> Cache Warming (Valkey)
```

## Error Handling

### Partial Failure Recovery

If some batches fail, the tool continues processing remaining batches:

```
09:05:30 [WARNING] ⚠️  Partial success: 10 batches succeeded, 2 failed
09:05:30 [WARNING] Failed batches:
09:05:30 [WARNING]   ❌ Batch 5: 25 files (error: Connection timeout) [10234ms]
09:05:30 [WARNING]   ❌ Batch 8: 25 files (error: Connection timeout) [10100ms]
```

**Recovery Strategy**:
1. Review failed batch correlation IDs
2. Check Kafka broker health
3. Re-run with `--dry-run` to validate discovery
4. Re-run failed batches manually (future enhancement)

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Project path does not exist` | Invalid path | Verify path exists |
| `Kafka connection timeout` | Kafka unavailable | Check Kafka/Redpanda status |
| `No files discovered` | All files excluded | Check exclusion patterns |
| `Permission denied` | File access issues | Check file permissions |

## Integration with Archon Intelligence

### Consumer Configuration

The Archon Intelligence Service consumes events from this topic:

```python
# services/intelligence/src/kafka_consumer.py
CONSUMER_TOPICS = [
    "dev.archon-intelligence.tree.index-project-requested.v1"
]
```

### Processing Pipeline

1. **Event Received** → Consumer picks up INDEX_PROJECT_REQUESTED
2. **Tree Discovery** → Validate file list and extract metadata
3. **Intelligence Generation** → Quality scoring, ONEX classification, semantic analysis
4. **Vector Indexing** → Index to Qdrant for semantic search
5. **Graph Indexing** → Create knowledge graph nodes/edges in Memgraph
6. **Cache Warming** → Pre-warm Valkey cache for common queries
7. **Event Published** → INDEX_PROJECT_COMPLETED or FAILED

## Troubleshooting

### Debug Logging

Enable verbose logging to diagnose issues:

```bash
python scripts/bulk_ingest_repository.py /path/to/project --verbose --dry-run
```

### Check Kafka Connection

```bash
# Verify Kafka is accessible
docker exec omninode-bridge-redpanda rpk cluster info

# Check topic exists
docker exec omninode-bridge-redpanda rpk topic list | grep "tree.index"
```

### Verify Consumer is Running

```bash
# Check consumer group status
docker exec omninode-bridge-redpanda rpk group describe archon-intelligence

# Check consumer lag
docker exec omninode-bridge-redpanda rpk group describe archon-intelligence --lag
```

## Module API Reference

### `file_discovery.py`

**Classes**:
- `FileDiscovery`: File enumeration and filtering engine
- `FileInfo`: File metadata container
- `DiscoveryStats`: Discovery statistics

**Key Methods**:
```python
discovery = FileDiscovery(
    supported_extensions=DEFAULT_SUPPORTED_EXTENSIONS,
    exclude_patterns=DEFAULT_EXCLUDE_PATTERNS,
    max_file_size=DEFAULT_MAX_FILE_SIZE
)

files, stats = discovery.discover(project_root)
```

### `batch_processor.py`

**Classes**:
- `BatchProcessor`: Kafka batch publishing engine
- `BatchResult`: Batch processing result
- `ProcessingStats`: Processing statistics

**Key Methods**:
```python
processor = BatchProcessor(
    kafka_bootstrap_servers="192.168.86.200:9092",
    batch_size=50,
    max_concurrent_batches=3
)

await processor.initialize()
results, stats = await processor.process_files(files, project_name, project_path)
await processor.shutdown()
```

## Future Enhancements

### Planned Features

- [ ] **Incremental Indexing**: Index only changed files (git diff integration)
- [ ] **Retry Failed Batches**: Automatic retry with exponential backoff
- [ ] **Progress Bar**: Rich terminal UI with progress bars
- [ ] **Configuration File**: YAML config for defaults (exclusions, extensions, etc.)
- [ ] **Multi-Project Support**: Index multiple projects in one run
- [ ] **Status Endpoint**: Query indexing status via HTTP API
- [ ] **Event Streaming**: Real-time event streaming for monitoring
- [ ] **Custom Filters**: User-defined file filters and transformations

## Contributing

When adding new features or fixing bugs:

1. **Follow ONEX Patterns**:
   - Effect: External I/O (Kafka, file system)
   - Compute: Pure logic (file filtering, batching)
   - Orchestrator: Workflow coordination (CLI app)

2. **Add Tests**:
   - Unit tests for file discovery logic
   - Integration tests for Kafka publishing
   - End-to-end tests with dry-run validation

3. **Update Documentation**:
   - Update this README
   - Add docstrings to new functions
   - Include usage examples

## License

Part of the Archon Intelligence Platform.

## Support

For issues or questions:
- Check troubleshooting section above
- Review Kafka consumer logs
- Enable verbose logging for diagnostics
- Contact Archon development team

---

**Status**: ✅ Production Ready
**Last Updated**: 2025-10-27
**Maintainer**: Archon Team
