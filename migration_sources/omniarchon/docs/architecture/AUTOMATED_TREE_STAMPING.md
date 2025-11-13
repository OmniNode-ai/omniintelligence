# Automated Tree Stamping - Event Bus Architecture

**Version**: 1.0.0
**Status**: Design Phase
**Created**: 2025-10-27
**Purpose**: Event-driven architecture for automated OnexTree discovery, metadata stamping, and intelligent indexing

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Event Flow Patterns](#event-flow-patterns)
4. [Event Schemas](#event-schemas)
5. [Producer Patterns](#producer-patterns)
6. [Consumer Patterns](#consumer-patterns)
7. [Error Handling & Retry Logic](#error-handling--retry-logic)
8. [Performance Optimization](#performance-optimization)
9. [Monitoring & Observability](#monitoring--observability)
10. [Testing Strategy](#testing-strategy)

---

## Executive Summary

### Vision

Transform tree discovery and metadata stamping from synchronous HTTP operations into an asynchronous, event-driven workflow that enables:

- **Scalability**: Process thousands of files in parallel via Kafka partitioning
- **Resilience**: Automatic retry with exponential backoff for failed operations
- **Observability**: Complete audit trail of every file processed
- **Performance**: Batch operations with configurable throughput limits
- **Intelligence**: Quality-weighted metadata enrichment via Archon Intelligence

### Current State

**Existing Components:**
- OnexTree service discovers project file structures
- Metadata Stamping service generates BLAKE3 hashes and metadata
- Qdrant vector database for semantic search
- Memgraph knowledge graph for relationship tracking
- Valkey cache for performance optimization

**Limitations:**
- Synchronous HTTP calls limit scalability
- No automatic retry for failed operations
- Difficult to track progress across large projects
- Manual coordination between services
- No event-driven workflow orchestration

### Target State

**Event-Driven Architecture:**
- 3 core event flows: Tree Discovery → Stamping → Indexing
- Asynchronous processing with Kafka/Redpanda
- Dead Letter Queue (DLQ) for failed events
- Automatic retry with exponential backoff (3 attempts)
- Batch processing for high throughput (100 files/batch)
- Complete observability with correlation ID tracking
- Performance target: <100ms per file (p95), 10,000 files/minute throughput

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT TRIGGERS                          │
│  Bulk Project Ingestion │ Git Hooks │ Scheduled Jobs       │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              EVENT BUS (Kafka/Redpanda)                     │
│  Topics:                                                     │
│  • dev.archon-intelligence.tree.discover.v1                 │
│  • dev.archon-intelligence.stamping.generate.v1             │
│  • dev.archon-intelligence.tree.index.v1                    │
│  • dev.archon-intelligence.*.dlq (Dead Letter Queue)        │
└───────────────────┬─────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Tree        │ │  Stamping    │ │  Indexing    │
│  Discovery   │ │  Generator   │ │  Processor   │
│  Consumer    │ │  Consumer    │ │  Consumer    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ OnexTree     │ │ Metadata     │ │ Qdrant +     │
│ Service      │ │ Stamping     │ │ Memgraph     │
│ (8058)       │ │ (8057)       │ │ (6333+7687)  │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Component Responsibilities

#### 1. Tree Discovery Consumer
- **Input**: `tree.discover.v1` events with project paths
- **Process**: Call OnexTree service to discover files
- **Output**: `stamping.generate.v1` events for discovered files
- **Batch Size**: 100 files per batch
- **Error Handling**: Retry 3x, then DLQ

#### 2. Stamping Generator Consumer
- **Input**: `stamping.generate.v1` events with file paths
- **Process**: Generate metadata, BLAKE3 hash, intelligence scores
- **Output**: `tree.index.v1` events with enriched metadata
- **Parallelism**: Process up to 10 files concurrently
- **Error Handling**: Retry 3x, then DLQ

#### 3. Indexing Processor Consumer
- **Input**: `tree.index.v1` events with metadata
- **Process**: Index in Qdrant (vector) and Memgraph (graph)
- **Output**: Completion events (optional)
- **Parallelism**: Batch upsert (50 documents at a time)
- **Error Handling**: Retry 3x, then DLQ

---

## Event Flow Patterns

### 1. Bulk Project Ingestion Flow

```
User → Publish Tree Discovery Request
  ↓
  [tree.discover.v1]
  ↓
Tree Discovery Consumer
  ↓ (batch 100 files)
  [stamping.generate.v1 x 100]
  ↓
Stamping Generator Consumer (parallel x10)
  ↓ (enriched metadata)
  [tree.index.v1 x 100]
  ↓
Indexing Processor Consumer
  ↓ (batch upsert)
Qdrant + Memgraph Updated
```

**Characteristics:**
- **Pattern**: Fan-out (1 discovery → N stamping → N indexing)
- **Correlation ID**: Preserved across all events for tracing
- **Throughput**: 10,000 files in ~60 seconds (target)
- **Ordering**: Not guaranteed (files processed in parallel)

### 2. Git Hook Integration Flow

```
Git Post-Commit Hook
  ↓
Extract Changed Files (git diff)
  ↓
Publish Stamping Request (per file)
  ↓
  [stamping.generate.v1 x N]
  ↓
Stamping Generator Consumer
  ↓
  [tree.index.v1 x N]
  ↓
Indexing Processor Consumer
  ↓
Updated Indexes
```

**Characteristics:**
- **Pattern**: Direct stamping (skip discovery)
- **Real-time**: Process immediately after commit
- **Granular**: File-level events, not batch
- **Ordering**: FIFO within partition (partition by project_id)

### 3. Error Recovery Flow

```
Failed Event (after 3 retries)
  ↓
Route to DLQ Topic
  ↓
  [*.dlq]
  ↓
Alert Monitoring System
  ↓
Manual Review / Automated Reprocessing
  ↓
Republish to Original Topic
  ↓
Normal Processing Resumes
```

**Characteristics:**
- **DLQ Retention**: 7 days
- **Alerting**: Slack/PagerDuty on DLQ threshold (>10 events)
- **Reprocessing**: CLI tool + manual approval
- **Analytics**: Track failure patterns for improvements

---

## Event Schemas

All events follow the `ModelEventEnvelope` pattern with strong typing via Pydantic v2.

### Event Naming Convention

**Format**: `dev.archon-intelligence.{domain}.{operation}.{version}`

- `dev` - Environment (dev, staging, prod)
- `archon-intelligence` - Service namespace
- `{domain}` - Operation domain (tree, stamping)
- `{operation}` - Specific operation (discover, generate, index)
- `{version}` - Schema version (v1, v2, etc.)

### 1. Tree Discovery Events

#### TreeDiscoveryRequestedPayload

```python
class TreeDiscoveryRequestedPayload(BaseModel):
    """Request to discover files in a project."""

    project_path: str  # Absolute path to project root
    project_name: str  # Human-readable project name
    include_tests: bool = True  # Include test files
    include_hidden: bool = False  # Include hidden files (.*/)
    exclude_patterns: list[str] = []  # Glob patterns to exclude
    max_depth: int = 100  # Maximum directory depth
    max_files: int = 10000  # Maximum files to discover
    correlation_id: UUID  # For request tracing
```

**Topic**: `dev.archon-intelligence.tree.discover.v1`

#### TreeDiscoveryCompletedPayload

```python
class TreeDiscoveryCompletedPayload(BaseModel):
    """Results from tree discovery operation."""

    project_path: str
    project_name: str
    files_discovered: int  # Total files found
    files_tracked: list[FileInfo]  # File metadata list
    discovery_time_ms: float
    cache_hit: bool = False
    correlation_id: UUID
```

**Topic**: `dev.archon-intelligence.tree.discover-completed.v1`

#### TreeDiscoveryFailedPayload

```python
class TreeDiscoveryFailedPayload(BaseModel):
    """Failed tree discovery operation."""

    project_path: str
    error_message: str
    error_code: EnumTreeErrorCode
    retry_allowed: bool
    processing_time_ms: float
    correlation_id: UUID
```

**Topic**: `dev.archon-intelligence.tree.discover-failed.v1`

### 2. Stamping Generation Events

#### StampingGenerateRequestedPayload

```python
class StampingGenerateRequestedPayload(BaseModel):
    """Request to generate metadata and intelligence."""

    file_path: str  # Absolute path to file
    project_name: str  # Project context
    content_hash: Optional[str] = None  # Pre-computed hash
    force_regenerate: bool = False  # Bypass cache
    include_intelligence: bool = True  # Include quality scoring
    correlation_id: UUID
```

**Topic**: `dev.archon-intelligence.stamping.generate.v1`

#### StampingGenerateCompletedPayload

```python
class StampingGenerateCompletedPayload(BaseModel):
    """Completed metadata stamping with intelligence."""

    file_path: str
    blake3_hash: str  # BLAKE3 content hash
    metadata: dict[str, Any]  # File metadata
    intelligence_score: float  # Quality score (0.0-1.0)
    onex_compliance: float  # ONEX compliance (0.0-1.0)
    processing_time_ms: float
    cache_hit: bool
    correlation_id: UUID
```

**Topic**: `dev.archon-intelligence.stamping.generate-completed.v1`

#### StampingGenerateFailedPayload

```python
class StampingGenerateFailedPayload(BaseModel):
    """Failed stamping generation."""

    file_path: str
    error_message: str
    error_code: EnumStampingErrorCode
    retry_allowed: bool
    processing_time_ms: float
    correlation_id: UUID
```

**Topic**: `dev.archon-intelligence.stamping.generate-failed.v1`

### 3. Tree Indexing Events

#### TreeIndexRequestedPayload

```python
class TreeIndexRequestedPayload(BaseModel):
    """Request to index file metadata."""

    file_path: str
    blake3_hash: str
    metadata: dict[str, Any]
    intelligence_score: float
    onex_compliance: float
    project_name: str
    index_targets: list[str] = ["qdrant", "memgraph"]  # Which indexes
    correlation_id: UUID
```

**Topic**: `dev.archon-intelligence.tree.index.v1`

#### TreeIndexCompletedPayload

```python
class TreeIndexCompletedPayload(BaseModel):
    """Completed indexing operation."""

    file_path: str
    blake3_hash: str
    indexed_in: list[str]  # ["qdrant", "memgraph"]
    qdrant_point_id: Optional[UUID] = None
    memgraph_node_id: Optional[int] = None
    processing_time_ms: float
    correlation_id: UUID
```

**Topic**: `dev.archon-intelligence.tree.index-completed.v1`

#### TreeIndexFailedPayload

```python
class TreeIndexFailedPayload(BaseModel):
    """Failed indexing operation."""

    file_path: str
    blake3_hash: str
    error_message: str
    error_code: EnumIndexingErrorCode
    retry_allowed: bool
    processing_time_ms: float
    correlation_id: UUID
```

**Topic**: `dev.archon-intelligence.tree.index-failed.v1`

### Error Code Enums

```python
class EnumTreeErrorCode(str, Enum):
    """Error codes for tree discovery."""
    INVALID_PATH = "INVALID_PATH"
    PATH_NOT_FOUND = "PATH_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    MAX_FILES_EXCEEDED = "MAX_FILES_EXCEEDED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"

class EnumStampingErrorCode(str, Enum):
    """Error codes for stamping generation."""
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_CONTENT = "INVALID_CONTENT"
    HASHING_FAILED = "HASHING_FAILED"
    INTELLIGENCE_SERVICE_ERROR = "INTELLIGENCE_SERVICE_ERROR"
    TIMEOUT = "TIMEOUT"

class EnumIndexingErrorCode(str, Enum):
    """Error codes for indexing."""
    QDRANT_UNAVAILABLE = "QDRANT_UNAVAILABLE"
    MEMGRAPH_UNAVAILABLE = "MEMGRAPH_UNAVAILABLE"
    INVALID_METADATA = "INVALID_METADATA"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    TIMEOUT = "TIMEOUT"
```

---

## Producer Patterns

### 1. Bulk Project Ingestion Producer

**Use Case**: Index entire project (thousands of files)

```python
from uuid import uuid4
from kafka_producer import KafkaProducer

async def ingest_project(project_path: str, project_name: str):
    """Ingest entire project via tree discovery."""

    producer = KafkaProducer(bootstrap_servers='redpanda:9092')
    correlation_id = uuid4()

    # Publish single discovery request
    event = TreeDiscoveryRequestedPayload(
        project_path=project_path,
        project_name=project_name,
        include_tests=True,
        include_hidden=False,
        exclude_patterns=["*.pyc", "__pycache__", "node_modules"],
        correlation_id=correlation_id
    )

    await producer.send(
        topic='dev.archon-intelligence.tree.discover.v1',
        key=project_name.encode(),  # Partition by project
        value=event.model_dump_json().encode()
    )

    print(f"Published discovery request: {correlation_id}")
    return correlation_id
```

**Characteristics:**
- Single event triggers entire workflow
- Partition key: `project_name` (ensures ordering per project)
- Async/await for non-blocking
- Returns correlation_id for tracking

### 2. Git Hook Producer

**Use Case**: Update metadata after git commit

```python
import subprocess
from pathlib import Path

async def process_git_commit(repo_path: Path):
    """Process files changed in latest commit."""

    # Get changed files from git
    result = subprocess.run(
        ['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'],
        cwd=repo_path,
        capture_output=True,
        text=True
    )

    changed_files = result.stdout.strip().split('\n')

    producer = KafkaProducer(bootstrap_servers='redpanda:9092')
    correlation_id = uuid4()

    # Publish stamping request for each changed file
    for file_path in changed_files:
        full_path = repo_path / file_path

        event = StampingGenerateRequestedPayload(
            file_path=str(full_path),
            project_name=repo_path.name,
            force_regenerate=True,  # Always update
            include_intelligence=True,
            correlation_id=correlation_id
        )

        await producer.send(
            topic='dev.archon-intelligence.stamping.generate.v1',
            key=repo_path.name.encode(),
            value=event.model_dump_json().encode()
        )

    print(f"Published {len(changed_files)} stamping requests")
    return correlation_id
```

**Git Hook Integration** (`post-commit`):

```bash
#!/bin/bash
# .git/hooks/post-commit

# Call Python script to process changed files
python3 /path/to/git_hook_producer.py "$PWD"
```

### 3. Batch Publishing Producer

**Use Case**: Publish many events efficiently

```python
async def publish_batch(events: list[BaseModel], topic: str):
    """Publish events in batch for efficiency."""

    producer = KafkaProducer(
        bootstrap_servers='redpanda:9092',
        linger_ms=100,  # Wait 100ms to batch messages
        batch_size=16384,  # 16KB batch size
        compression_type='lz4'  # Compress batches
    )

    for event in events:
        await producer.send(
            topic=topic,
            value=event.model_dump_json().encode()
        )

    await producer.flush()  # Ensure all sent
    print(f"Published {len(events)} events in batch")
```

**Performance**:
- Batching reduces network overhead by ~80%
- Compression (LZ4) reduces payload size by ~50%
- Target: 10,000 events/second throughput

---

## Consumer Patterns

### 1. Tree Discovery Consumer

**Responsibility**: Discover files and fan out to stamping

```python
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import asyncio

class TreeDiscoveryConsumer:
    """Consumer for tree discovery events."""

    def __init__(self):
        self.consumer = AIOKafkaConsumer(
            'dev.archon-intelligence.tree.discover.v1',
            bootstrap_servers='redpanda:9092',
            group_id='tree-discovery-group',
            auto_offset_reset='latest',
            max_poll_records=10  # Process 10 discovery requests at a time
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers='redpanda:9092'
        )

    async def start(self):
        await self.consumer.start()
        await self.producer.start()

        async for msg in self.consumer:
            await self.process_message(msg)

    async def process_message(self, msg):
        """Process discovery request and fan out."""
        try:
            event = TreeDiscoveryRequestedPayload.model_validate_json(msg.value)

            # Call OnexTree service
            files = await self.discover_files(event.project_path)

            # Batch files into chunks of 100
            for batch in chunks(files, 100):
                # Publish stamping requests for batch
                for file_info in batch:
                    stamping_event = StampingGenerateRequestedPayload(
                        file_path=file_info.path,
                        project_name=event.project_name,
                        include_intelligence=True,
                        correlation_id=event.correlation_id
                    )

                    await self.producer.send(
                        'dev.archon-intelligence.stamping.generate.v1',
                        key=event.project_name.encode(),
                        value=stamping_event.model_dump_json().encode()
                    )

            # Publish completion event
            completion = TreeDiscoveryCompletedPayload(
                project_path=event.project_path,
                project_name=event.project_name,
                files_discovered=len(files),
                files_tracked=files,
                discovery_time_ms=123.45,
                correlation_id=event.correlation_id
            )

            await self.producer.send(
                'dev.archon-intelligence.tree.discover-completed.v1',
                value=completion.model_dump_json().encode()
            )

        except Exception as e:
            await self.handle_error(msg, e)

    async def discover_files(self, project_path: str) -> list[FileInfo]:
        """Call OnexTree service to discover files."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'http://onextree:8058/generate-tree',
                json={'project_path': project_path},
                timeout=60.0
            )
            return response.json()['files']

    async def handle_error(self, msg, error: Exception):
        """Handle processing errors with retry logic."""
        # Implement retry logic (see Error Handling section)
        pass
```

### 2. Stamping Generator Consumer

**Responsibility**: Generate metadata with intelligence scoring

```python
class StampingGeneratorConsumer:
    """Consumer for stamping generation events."""

    def __init__(self):
        self.consumer = AIOKafkaConsumer(
            'dev.archon-intelligence.stamping.generate.v1',
            bootstrap_servers='redpanda:9092',
            group_id='stamping-generator-group',
            auto_offset_reset='latest',
            max_poll_records=100  # Process 100 files at a time
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers='redpanda:9092'
        )
        self.semaphore = asyncio.Semaphore(10)  # Max 10 concurrent

    async def process_message(self, msg):
        """Process stamping request with parallelism control."""
        async with self.semaphore:  # Limit concurrency
            try:
                event = StampingGenerateRequestedPayload.model_validate_json(msg.value)

                # Generate metadata and intelligence
                result = await self.generate_stamping(event)

                # Publish indexing request
                index_event = TreeIndexRequestedPayload(
                    file_path=event.file_path,
                    blake3_hash=result.blake3_hash,
                    metadata=result.metadata,
                    intelligence_score=result.intelligence_score,
                    onex_compliance=result.onex_compliance,
                    project_name=event.project_name,
                    correlation_id=event.correlation_id
                )

                await self.producer.send(
                    'dev.archon-intelligence.tree.index.v1',
                    key=event.project_name.encode(),
                    value=index_event.model_dump_json().encode()
                )

            except Exception as e:
                await self.handle_error(msg, e)

    async def generate_stamping(self, event) -> StampingResult:
        """Generate metadata via stamping service."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'http://metadata-stamping:8057/generate-intelligence',
                json={'file_path': event.file_path},
                timeout=30.0
            )
            return StampingResult(**response.json())
```

### 3. Indexing Processor Consumer

**Responsibility**: Index metadata in Qdrant and Memgraph

```python
class IndexingProcessorConsumer:
    """Consumer for tree indexing events."""

    def __init__(self):
        self.consumer = AIOKafkaConsumer(
            'dev.archon-intelligence.tree.index.v1',
            bootstrap_servers='redpanda:9092',
            group_id='indexing-processor-group',
            auto_offset_reset='latest',
            max_poll_records=50  # Batch 50 for indexing
        )
        self.qdrant_client = QdrantClient('qdrant', 6333)
        self.memgraph_client = MemgraphClient('memgraph', 7687)

    async def process_batch(self, messages: list):
        """Process batch of indexing requests."""
        try:
            events = [
                TreeIndexRequestedPayload.model_validate_json(msg.value)
                for msg in messages
            ]

            # Batch upsert to Qdrant
            qdrant_points = [
                self.create_qdrant_point(event)
                for event in events
            ]
            await self.qdrant_client.upsert(
                collection_name='file_locations',
                points=qdrant_points
            )

            # Batch insert to Memgraph
            for event in events:
                await self.memgraph_client.create_node(
                    label='File',
                    properties={
                        'path': event.file_path,
                        'hash': event.blake3_hash,
                        'intelligence_score': event.intelligence_score
                    }
                )

        except Exception as e:
            await self.handle_error(messages, e)
```

---

## Error Handling & Retry Logic

### Retry Strategy

**Exponential Backoff with Jitter**:
- Attempt 1: Immediate
- Attempt 2: 1 second delay + random jitter (0-500ms)
- Attempt 3: 2 seconds delay + random jitter (0-1000ms)
- Final: Route to DLQ

```python
import asyncio
import random

class RetryHandler:
    """Handles retry logic with exponential backoff."""

    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds

    async def retry_with_backoff(self, func, *args, **kwargs):
        """Retry function with exponential backoff."""

        for attempt in range(self.MAX_RETRIES):
            try:
                return await func(*args, **kwargs)

            except Exception as e:
                if attempt == self.MAX_RETRIES - 1:
                    # Final attempt failed, route to DLQ
                    await self.route_to_dlq(func, args, kwargs, e)
                    raise

                # Calculate delay with jitter
                delay = (self.BASE_DELAY * (2 ** attempt)) + random.uniform(0, 1)

                print(f"Retry attempt {attempt + 1} after {delay:.2f}s: {e}")
                await asyncio.sleep(delay)

        raise Exception("Max retries exceeded")

    async def route_to_dlq(self, func, args, kwargs, error):
        """Route failed event to Dead Letter Queue."""

        dlq_event = {
            'original_topic': 'dev.archon-intelligence.stamping.generate.v1',
            'original_payload': kwargs.get('event'),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'retry_count': self.MAX_RETRIES,
            'failed_at': datetime.now(UTC).isoformat(),
            'correlation_id': kwargs.get('event', {}).get('correlation_id')
        }

        await self.producer.send(
            'dev.archon-intelligence.stamping.generate.v1.dlq',
            value=json.dumps(dlq_event).encode()
        )
```

### DLQ Processing

**Monitoring**:
- Alert on DLQ threshold: >10 events in 5 minutes
- Daily summary: Total DLQ events, error patterns
- Dashboard: Real-time DLQ metrics

**Reprocessing**:

```python
async def reprocess_dlq(topic: str, limit: int = 100):
    """Reprocess events from Dead Letter Queue."""

    consumer = AIOKafkaConsumer(
        f'{topic}.dlq',
        bootstrap_servers='redpanda:9092',
        group_id='dlq-reprocessing',
        auto_offset_reset='earliest'
    )

    producer = AIOKafkaProducer(bootstrap_servers='redpanda:9092')

    await consumer.start()
    await producer.start()

    count = 0
    async for msg in consumer:
        if count >= limit:
            break

        # Extract original event
        dlq_event = json.loads(msg.value)
        original_payload = dlq_event['original_payload']

        # Republish to original topic
        await producer.send(
            topic,
            value=json.dumps(original_payload).encode()
        )

        count += 1
        print(f"Reprocessed {count}/{limit} events")

    await consumer.stop()
    await producer.stop()
```

---

## Performance Optimization

### 1. Batching Strategy

**Producer Batching**:
```python
producer = AIOKafkaProducer(
    linger_ms=100,  # Wait 100ms to accumulate messages
    batch_size=16384,  # 16KB batches
    compression_type='lz4'  # Fast compression
)
```

**Consumer Batching**:
```python
consumer = AIOKafkaConsumer(
    max_poll_records=100,  # Fetch 100 messages at once
    fetch_min_bytes=1024,  # Wait for 1KB before returning
    fetch_max_wait_ms=500  # Max wait 500ms
)
```

### 2. Partitioning Strategy

**Partition by Project**:
- Key: `project_name`
- Benefits: Order preservation per project, parallel processing across projects
- Partition count: 12 (3x number of consumers for load balancing)

**Partition Assignment**:
```
Partition 0-3: Consumer 1
Partition 4-7: Consumer 2
Partition 8-11: Consumer 3
```

### 3. Concurrency Control

**Semaphore Pattern**:
```python
semaphore = asyncio.Semaphore(10)  # Max 10 concurrent operations

async def process_with_limit(event):
    async with semaphore:
        await process_event(event)
```

**Benefits**:
- Prevents overwhelming downstream services
- Maintains consistent throughput
- Avoids memory exhaustion

### 4. Caching Strategy

**Valkey Cache Integration**:
```python
async def get_cached_stamping(file_hash: str) -> Optional[dict]:
    """Check cache before regenerating."""

    cache_key = f"stamping:{file_hash}"
    cached = await valkey_client.get(cache_key)

    if cached:
        return json.loads(cached)
    return None

async def cache_stamping(file_hash: str, result: dict):
    """Cache stamping result for 1 hour."""

    cache_key = f"stamping:{file_hash}"
    await valkey_client.setex(
        cache_key,
        3600,  # 1 hour TTL
        json.dumps(result)
    )
```

### Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Event Publishing Latency | <10ms (p95) | Producer send time |
| Event Processing Latency | <100ms (p95) | Consumer processing time |
| End-to-End Latency | <500ms (p95) | Discovery → Indexing complete |
| Throughput | 10,000 files/minute | Total files processed |
| Consumer Lag | <5 seconds | Offset lag per partition |
| DLQ Rate | <0.1% | Failed events / total events |
| Cache Hit Rate | >60% | Cached stamping / total requests |

---

## Monitoring & Observability

### Key Metrics

**Kafka/Redpanda Metrics**:
```python
metrics = {
    'consumer_lag': 'messages_behind_high_water_mark',
    'throughput': 'records_consumed_per_sec',
    'error_rate': 'records_failed_per_sec',
    'processing_time': 'record_processing_time_p95'
}
```

**Application Metrics**:
```python
from prometheus_client import Counter, Histogram

# Event counters
events_published = Counter('tree_events_published_total', 'Events published', ['topic'])
events_processed = Counter('tree_events_processed_total', 'Events processed', ['topic', 'status'])

# Processing time
processing_time = Histogram('tree_event_processing_seconds', 'Processing time', ['operation'])

# Cache metrics
cache_hits = Counter('tree_cache_hits_total', 'Cache hits')
cache_misses = Counter('tree_cache_misses_total', 'Cache misses')
```

### Correlation ID Tracking

**Tracing Workflow**:
```python
# Generate correlation ID at start
correlation_id = uuid4()

# Include in all events
event = TreeDiscoveryRequestedPayload(
    project_path='/path/to/project',
    correlation_id=correlation_id  # Preserved across all events
)

# Query events by correlation ID
SELECT * FROM event_store
WHERE correlation_id = 'abc-123-def-456'
ORDER BY timestamp ASC;
```

**Benefits**:
- Trace complete workflow from discovery to indexing
- Measure end-to-end latency
- Debug specific request failures
- Audit trail for compliance

### Dashboards

**Kafka Dashboard** (Redpanda Console):
- Consumer lag per partition
- Throughput (messages/sec)
- Topic size and retention
- DLQ overflow alerts

**Application Dashboard** (Grafana):
- Events published/processed (time series)
- Processing latency (p50, p95, p99)
- Error rate by operation
- Cache hit rate
- DLQ events (trending)

### Alerting Rules

```yaml
alerts:
  - name: HighConsumerLag
    condition: consumer_lag > 10000
    severity: warning
    channels: [slack, pagerduty]

  - name: DLQOverflow
    condition: dlq_message_count > 10
    severity: critical
    channels: [slack, pagerduty]

  - name: LowThroughput
    condition: throughput < 1000 files/min for 5 minutes
    severity: warning
    channels: [slack]

  - name: HighErrorRate
    condition: error_rate > 5% for 5 minutes
    severity: critical
    channels: [slack, pagerduty]
```

---

## Testing Strategy

### Unit Tests

**Event Schema Validation**:
```python
def test_tree_discovery_payload_validation():
    """Test event payload validation."""

    # Valid payload
    payload = TreeDiscoveryRequestedPayload(
        project_path='/valid/path',
        project_name='test-project',
        correlation_id=uuid4()
    )
    assert payload.project_path == '/valid/path'

    # Invalid payload (missing required field)
    with pytest.raises(ValidationError):
        TreeDiscoveryRequestedPayload(
            project_path='/valid/path'
            # Missing correlation_id
        )
```

### Integration Tests

**Event Flow Testing**:
```python
@pytest.mark.asyncio
async def test_tree_discovery_to_indexing_flow():
    """Test complete event flow from discovery to indexing."""

    # Step 1: Publish discovery request
    correlation_id = uuid4()
    await publish_discovery_request(
        project_path='/test/project',
        correlation_id=correlation_id
    )

    # Step 2: Verify stamping events published
    stamping_events = await consume_events(
        topic='dev.archon-intelligence.stamping.generate.v1',
        correlation_id=correlation_id,
        timeout=10.0
    )
    assert len(stamping_events) > 0

    # Step 3: Verify indexing events published
    index_events = await consume_events(
        topic='dev.archon-intelligence.tree.index.v1',
        correlation_id=correlation_id,
        timeout=10.0
    )
    assert len(index_events) == len(stamping_events)
```

### Performance Tests

**Throughput Benchmark**:
```python
@pytest.mark.performance
async def test_bulk_ingestion_throughput():
    """Test throughput for 10,000 files."""

    start_time = time.perf_counter()

    # Publish discovery request for large project
    correlation_id = await ingest_project(
        project_path='/large/project',  # 10,000 files
        project_name='large-test'
    )

    # Wait for all events processed
    await wait_for_completion(correlation_id, timeout=120.0)

    duration = time.perf_counter() - start_time

    # Verify throughput target
    throughput = 10000 / duration  # files/second
    assert throughput > 166  # 10,000 files/minute = 166 files/second
```

### Error Recovery Tests

**DLQ Routing Test**:
```python
@pytest.mark.asyncio
async def test_dlq_routing_on_failure():
    """Test failed events route to DLQ after retries."""

    # Publish event that will fail (invalid path)
    event = StampingGenerateRequestedPayload(
        file_path='/invalid/path/that/does/not/exist',
        project_name='test',
        correlation_id=uuid4()
    )

    await publish_event(
        topic='dev.archon-intelligence.stamping.generate.v1',
        event=event
    )

    # Verify event appears in DLQ after retries
    dlq_event = await consume_dlq_event(
        topic='dev.archon-intelligence.stamping.generate.v1.dlq',
        correlation_id=event.correlation_id,
        timeout=15.0  # Wait for 3 retries (1s + 2s + 4s = 7s + buffer)
    )

    assert dlq_event is not None
    assert dlq_event['retry_count'] == 3
    assert dlq_event['error_type'] == 'FileNotFoundError'
```

---

## Implementation Checklist

### Phase 1: Core Infrastructure (Week 1)
- [ ] Define event schemas (tree_stamping_events.py)
- [ ] Create Kafka topics with proper configuration
- [ ] Implement event validation and serialization
- [ ] Set up DLQ topics and routing logic
- [ ] Add correlation ID tracking infrastructure

### Phase 2: Consumers (Week 2)
- [ ] Implement Tree Discovery Consumer
- [ ] Implement Stamping Generator Consumer
- [ ] Implement Indexing Processor Consumer
- [ ] Add retry logic with exponential backoff
- [ ] Configure consumer groups and partitioning

### Phase 3: Producers (Week 3)
- [ ] Implement bulk project ingestion producer
- [ ] Create git hook integration producer
- [ ] Add batch publishing optimization
- [ ] Implement caching strategy (Valkey)
- [ ] Add producer monitoring and metrics

### Phase 4: Testing & Monitoring (Week 4)
- [ ] Write unit tests for event schemas
- [ ] Write integration tests for event flows
- [ ] Performance benchmarking (10k files)
- [ ] Set up Grafana dashboards
- [ ] Configure alerting rules
- [ ] DLQ reprocessing CLI tool

### Phase 5: Documentation & Deployment (Week 5)
- [ ] Complete architecture documentation
- [ ] Create operational runbooks
- [ ] Write troubleshooting guide
- [ ] Production deployment checklist
- [ ] Training materials for team

---

## References

- [Event Bus Architecture](../planning/EVENT_BUS_ARCHITECTURE.md)
- [ModelEventEnvelope](../../python/src/events/models/model_event_envelope.py)
- [Bridge Intelligence Events](../../services/intelligence/src/events/models/bridge_intelligence_events.py)
- [Kafka Best Practices](https://kafka.apache.org/documentation/#bestpractices)
- [Redpanda Documentation](https://docs.redpanda.com/)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-27
**Maintained By**: Archon Intelligence Team
**Review Cycle**: Monthly
