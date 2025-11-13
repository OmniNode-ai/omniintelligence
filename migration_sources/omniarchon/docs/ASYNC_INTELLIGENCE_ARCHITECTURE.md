# Async Event-Driven Intelligence Architecture

**Version**: 1.0.0
**Status**: Design Proposal
**Created**: 2025-10-30
**Author**: Archon Architecture Team
**Correlation ID**: DBAAF41D-311F-46F2-A652-572548EF50B5

---

## Executive Summary

This document defines a comprehensive async event-driven architecture for intelligence enrichment in the Archon Intelligence Platform. The design decouples document indexing from intelligence processing, enabling sub-second document indexing while maintaining comprehensive AI enrichment capabilities.

**Key Benefits**:
- ⚡ **10-100x Faster Indexing**: Document indexing completes in <100ms (vs 10-60s synchronous)
- 🔄 **Async Processing**: Intelligence enrichment happens asynchronously without blocking
- 📈 **Scalability**: Horizontal scaling via Kafka consumer groups
- 🛡️ **Resilience**: DLQ, circuit breakers, exponential backoff for fault tolerance
- 🔀 **Backward Compatible**: Gradual migration with feature flag support

**Current Problem**:
```
Document → Bridge → [BLOCKS] Intelligence Service (10-60s) → Memgraph
                         ❌ BLOCKING CALL
                         ❌ No parallelism
                         ❌ Single point of failure
```

**Target Solution**:
```
Document → Bridge → Memgraph/Qdrant (100ms) ✅
                ↓
           Kafka Event (5ms) ✅
                ↓
      Intelligence Consumer (async) ✅
                ↓
      Update Memgraph/Qdrant (enrichment) ✅
```

---

## Table of Contents

1. [Current Architecture Analysis](#1-current-architecture-analysis)
2. [Target Architecture Design](#2-target-architecture-design)
3. [Event Schema Design](#3-event-schema-design)
4. [Component Design](#4-component-design)
5. [Resilience Patterns](#5-resilience-patterns)
6. [Implementation Roadmap](#6-implementation-roadmap)
7. [Migration Strategy](#7-migration-strategy)
8. [Code Modification Guide](#8-code-modification-guide)
9. [Testing Strategy](#9-testing-strategy)
10. [Monitoring & Observability](#10-monitoring--observability)

---

## 1. Current Architecture Analysis

### 1.1 Current Flow (Synchronous)

```
┌─────────────────────────────────────────────────────────────┐
│                    CURRENT ARCHITECTURE                      │
│                  (Synchronous Blocking)                      │
└─────────────────────────────────────────────────────────────┘

Kafka Event
    ↓
┌──────────────────┐
│ Kafka Consumer   │ (archon-kafka-consumer)
└────────┬─────────┘
         ↓ HTTP POST /api/bridge/document
┌──────────────────┐
│  Bridge Service  │ (archon-bridge:8054)
└────────┬─────────┘
         ↓
    Check SKIP_INTELLIGENCE_ENRICHMENT flag
         ↓
    ┌────────────────────────────────────┐
    │ If false (default):                │
    │   1. HTTP POST to Intelligence     │ ⏱️ 10-60s BLOCKING
    │      /process/document             │
    │   2. Wait for entities             │ ❌ No parallelism
    │   3. Parse response                │ ❌ Timeout failures
    │   4. Index to Memgraph             │ ❌ No fault tolerance
    └────────────────────────────────────┘
         ↓
┌──────────────────┐
│    Memgraph      │ (bolt://memgraph:7687)
│  Knowledge Graph │
└──────────────────┘

Total Time: 10-60+ seconds per document
Failure Mode: All-or-nothing (if intelligence fails, indexing fails)
```

### 1.2 Problems Identified

**Performance Bottlenecks**:
- 🐢 **Blocking Intelligence Calls**: 10-60 seconds per document
- 🐢 **Sequential Processing**: Cannot process next document until current completes
- 🐢 **Network Latency**: HTTP call overhead adds 50-200ms per request
- 🐢 **Timeout Issues**: Intelligence service timeouts block entire pipeline

**Reliability Issues**:
- ❌ **All-or-Nothing**: Intelligence failure = indexing failure
- ❌ **No Retry Logic**: Failed enrichment = lost data
- ❌ **No Queue**: Cannot handle bursts (e.g., bulk ingestion of 1000+ files)
- ❌ **No Backpressure**: Consumer can overwhelm intelligence service

**Scalability Limitations**:
- ❌ **No Horizontal Scaling**: Cannot add more intelligence workers
- ❌ **Tight Coupling**: Bridge and intelligence must be co-located
- ❌ **Resource Contention**: Intelligence processing competes with indexing

### 1.3 Short-Term Fix Analysis

**Current Workaround** (SKIP_INTELLIGENCE_ENRICHMENT=true):
```python
# services/bridge/app.py:498
skip_intelligence = os.getenv("SKIP_INTELLIGENCE_ENRICHMENT", "false").lower() == "true"

if not skip_intelligence:
    # Make blocking intelligence call
    response = await http_client.post("/process/document", ...)
    # Process entities...
```

**Impact**:
- ✅ **Fast Indexing**: Documents indexed in <100ms
- ✅ **No Blocking**: Pipeline continues immediately
- ❌ **No Enrichment**: Documents lack AI-extracted entities, quality scores
- ❌ **Manual Process**: No automated way to enrich skipped documents
- ❌ **Data Inconsistency**: Some documents enriched, others not

---

## 2. Target Architecture Design

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TARGET ARCHITECTURE                                  │
│              (Async Event-Driven with DLQ)                              │
└─────────────────────────────────────────────────────────────────────────┘

Kafka Event (dev.archon-intelligence.tree.index.v1)
    ↓
┌──────────────────┐
│ Kafka Consumer   │ (archon-kafka-consumer)
└────────┬─────────┘
         ↓ HTTP POST /api/bridge/document
┌──────────────────┐
│  Bridge Service  │ (archon-bridge:8054)
└────────┬─────────┘
         ↓
    ┌────────────────────────────────────────────┐
    │ 1. Generate document_id, content_hash      │
    │ 2. Create document entity in Memgraph      │ ⚡ 50-100ms
    │ 3. Index basic metadata to Qdrant          │ ⚡ 30-50ms
    │ 4. Return success immediately              │ ✅ FAST
    └─────────────────┬──────────────────────────┘
                      │
                      ↓ Kafka Produce (async, non-blocking)
    ┌─────────────────────────────────────────────────────┐
    │  Kafka Topic:                                       │
    │  dev.archon-intelligence.enrich-document.v1         │
    │                                                     │
    │  Retention: 7 days                                  │
    │  Partitions: 4 (for parallelism)                   │
    │  Replication: 3 (for fault tolerance)              │
    └─────────────────┬───────────────────────────────────┘
                      │
                      ↓
    ┌─────────────────────────────────────────────────────┐
    │  Intelligence Consumer Group                        │
    │  (archon-intelligence-enrichment-consumer)          │
    │                                                     │
    │  Workers: 4 (scales with partitions)                │
    │  Max parallel: 10 per worker                        │
    │  Total throughput: 40 concurrent enrichments        │
    └─────────────────┬───────────────────────────────────┘
                      │
                      ↓
         ┌────────────────────────┐
         │ Intelligence Service   │ (archon-intelligence:8053)
         │ Process Async:         │
         │  1. Extract entities   │ ⏱️ 5-15s (async, non-blocking)
         │  2. Calculate quality  │
         │  3. Classify patterns  │
         │  4. Generate metadata  │
         └────────────┬───────────┘
                      │
                      ↓
              Success? ──┐
                ✅       │ ❌ Failed
                │        │
                │        ↓
                │   ┌──────────────────────────────┐
                │   │ Dead Letter Queue (DLQ)      │
                │   │ dev.archon-intelligence.     │
                │   │   enrich-document-dlq.v1     │
                │   │                              │
                │   │ Retry Strategy:              │
                │   │  - 3 retries w/ exp backoff  │
                │   │  - Manual intervention after │
                │   └──────────────────────────────┘
                │
                ↓
    ┌─────────────────────────────────────────┐
    │ Update Enrichment:                      │
    │  1. Update Memgraph entity properties   │
    │  2. Update Qdrant vector metadata       │
    │  3. Emit enrichment-completed event     │
    └─────────────────────────────────────────┘

Total Time:
  - Indexing: <200ms (immediate)
  - Enrichment: 5-15s (async, non-blocking)
  - User Experience: Instant (sees basic document immediately)
```

### 2.2 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     KAFKA EVENT BUS                         │
│               (Redpanda @ 192.168.86.200)                   │
│                                                             │
│  Topics:                                                    │
│  ├─ dev.archon-intelligence.enrich-document.v1             │
│  ├─ dev.archon-intelligence.enrich-document-dlq.v1         │
│  ├─ dev.archon-intelligence.enrichment-completed.v1        │
│  └─ dev.archon-intelligence.enrichment-progress.v1         │
└──────────────┬─────────────────┬────────────────────────────┘
               │                 │
   ┌───────────┴──────┐   ┌─────┴──────────────┐
   │ Bridge Service   │   │ Intelligence       │
   │ (Producer)       │   │ Consumer Service   │
   │                  │   │ (Consumer)         │
   │ Responsibilities:│   │                    │
   │ • Index docs     │   │ Responsibilities:  │
   │ • Publish events │   │ • Consume events   │
   │ • Fast return    │   │ • Enrich docs      │
   └──────────────────┘   │ • Update graph     │
                          │ • Handle failures  │
                          └────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     DATA LAYER                              │
├─────────────────────────────────────────────────────────────┤
│  Memgraph (bolt://memgraph:7687)                            │
│  • Document entities                                        │
│  • Entity relationships                                     │
│  • Enrichment status                                        │
├─────────────────────────────────────────────────────────────┤
│  Qdrant (http://qdrant:6333)                                │
│  • Document vectors                                         │
│  • Semantic search                                          │
│  • Metadata indexing                                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Data Flow Sequence

```
Actor: User/System
Flow: Document Ingestion with Async Enrichment

┌──────┐     ┌────────┐     ┌────────┐     ┌───────┐     ┌──────────┐     ┌──────────┐
│ User │     │ Kafka  │     │ Bridge │     │ Graph │     │ Kafka    │     │ Intel    │
│      │     │ Event  │     │Service │     │  DB   │     │ Topic    │     │Consumer  │
└───┬──┘     └───┬────┘     └───┬────┘     └───┬───┘     └────┬─────┘     └────┬─────┘
    │            │               │               │              │                │
    │ 1. Ingest  │               │               │              │                │
    │ Document   │               │               │              │                │
    ├───────────>│               │               │              │                │
    │            │ 2. Event      │               │              │                │
    │            ├──────────────>│               │              │                │
    │            │               │ 3. Index Doc  │              │                │
    │            │               │  (Memgraph)   │              │                │
    │            │               ├──────────────>│              │                │
    │            │               │               │              │                │
    │            │               │<──────────────┤              │                │
    │            │               │  4. Success   │              │                │
    │            │               │               │              │                │
    │            │               │ 5. Publish    │              │                │
    │            │               │  Enrich Event │              │                │
    │            │               ├─────────────────────────────>│                │
    │            │               │               │              │                │
    │            │  6. Return    │               │              │                │
    │<───────────┼───────────────┤               │              │                │
    │   200 OK   │               │               │              │ 7. Consume     │
    │  (100ms)   │               │               │              │    Event       │
    │            │               │               │              ├───────────────>│
    │            │               │               │              │                │
    │            │               │               │              │  8. Process    │
    │            │               │               │              │     Document   │
    │            │               │               │              │  (Async 5-15s) │
    │            │               │               │              │                │
    │            │               │               │  9. Update   │                │
    │            │               │<──────────────────────────────┼────────────────│
    │            │               │   Enrichment  │              │                │
    │            │               │               │              │                │
    │            │               │ 10. Complete  │              │                │
    │            │<──────────────────────────────────────────────┤                │
    │  11. Query │               │               │              │                │
    │   (Later)  │               │               │              │                │
    ├───────────>│               │               │              │                │
    │            │               │               │              │                │
    │<───────────┤ 12. Enriched Document with full metadata    │                │
    │            │               │               │              │                │
```

### 2.4 Key Design Principles

1. **Fail-Fast Indexing**: Always index documents to Memgraph/Qdrant immediately
2. **Fire-and-Forget Enrichment**: Publish enrichment event without waiting
3. **Eventual Consistency**: Documents eventually enriched (5-15s delay acceptable)
4. **Graceful Degradation**: System works even if intelligence service is down
5. **Idempotency**: Enrichment operations can be safely retried
6. **Observability**: Every stage emits events for monitoring
7. **Circuit Breaking**: Protect against cascading failures

---

## 3. Event Schema Design

### 3.1 Primary Topic: Enrichment Request

**Topic Name**: `dev.archon-intelligence.enrich-document.v1`

**Configuration**:
```yaml
partitions: 4           # Parallelism for 4 concurrent consumers
replication_factor: 3   # Fault tolerance
retention_ms: 604800000 # 7 days (allow reprocessing)
cleanup_policy: delete  # Remove after retention period
compression_type: snappy # Efficient compression
```

**Message Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DocumentEnrichmentRequest",
  "type": "object",
  "required": [
    "document_id",
    "project_name",
    "content_hash",
    "file_path",
    "indexed_at",
    "correlation_id"
  ],
  "properties": {
    "document_id": {
      "type": "string",
      "description": "Unique document identifier (UUID)",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    },
    "project_name": {
      "type": "string",
      "description": "Project name (for multi-tenant isolation)",
      "minLength": 1,
      "maxLength": 255
    },
    "content_hash": {
      "type": "string",
      "description": "BLAKE3 hash of file content",
      "pattern": "^[0-9a-f]{64}$"
    },
    "file_path": {
      "type": "string",
      "description": "Relative file path within project",
      "minLength": 1,
      "maxLength": 4096
    },
    "document_type": {
      "type": "string",
      "description": "Document type classification",
      "enum": ["code", "documentation", "configuration", "test", "other"]
    },
    "language": {
      "type": "string",
      "description": "Programming language (if code)",
      "examples": ["python", "typescript", "rust", "go"]
    },
    "indexed_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp when document was indexed"
    },
    "enrichment_type": {
      "type": "string",
      "description": "Type of enrichment to perform",
      "enum": ["full", "incremental", "quality_only", "entities_only"],
      "default": "full"
    },
    "priority": {
      "type": "string",
      "description": "Processing priority",
      "enum": ["high", "normal", "low"],
      "default": "normal"
    },
    "correlation_id": {
      "type": "string",
      "description": "Unique correlation ID for tracing",
      "pattern": "^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$"
    },
    "metadata": {
      "type": "object",
      "description": "Additional metadata for enrichment",
      "properties": {
        "file_size_bytes": {"type": "integer"},
        "line_count": {"type": "integer"},
        "git_commit_hash": {"type": "string"},
        "last_modified": {"type": "string", "format": "date-time"}
      }
    },
    "retry_count": {
      "type": "integer",
      "description": "Number of retry attempts",
      "default": 0,
      "minimum": 0,
      "maximum": 3
    }
  }
}
```

**Example Message**:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "project_name": "omniarchon",
  "content_hash": "a3c5e8d2f1b4a9e7c6d3f2e1a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3",
  "file_path": "services/bridge/app.py",
  "document_type": "code",
  "language": "python",
  "indexed_at": "2025-10-30T18:30:00.123Z",
  "enrichment_type": "full",
  "priority": "normal",
  "correlation_id": "7DC1746A-42A0-4125-BEA9-1DDF3E48ABA8",
  "metadata": {
    "file_size_bytes": 45678,
    "line_count": 1234,
    "git_commit_hash": "f7b900213a7c",
    "last_modified": "2025-10-30T12:00:00Z"
  },
  "retry_count": 0
}
```

### 3.2 Dead Letter Queue (DLQ) Topic

**Topic Name**: `dev.archon-intelligence.enrich-document-dlq.v1`

**Configuration**:
```yaml
partitions: 1           # Single partition (failures are rare)
replication_factor: 3   # High durability for failed messages
retention_ms: 2592000000 # 30 days (long retention for analysis)
cleanup_policy: compact  # Keep latest failure per document_id
compression_type: gzip   # Maximize compression (less volume)
```

**Message Schema**: Same as enrichment request, plus:
```json
{
  "failure_reason": "string",
  "failure_timestamp": "2025-10-30T18:35:00.123Z",
  "failure_count": 3,
  "original_message": { /* original enrichment request */ },
  "error_details": {
    "exception_type": "TimeoutException",
    "exception_message": "Intelligence service timeout after 60s",
    "stack_trace": "...",
    "service_health": {
      "intelligence_service": "unhealthy",
      "memgraph": "healthy",
      "qdrant": "healthy"
    }
  }
}
```

### 3.3 Enrichment Completed Topic

**Topic Name**: `dev.archon-intelligence.enrichment-completed.v1`

**Purpose**: Notify downstream systems that enrichment completed

**Message Schema**:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "project_name": "omniarchon",
  "enrichment_status": "success",
  "completed_at": "2025-10-30T18:30:15.456Z",
  "processing_time_ms": 8234,
  "correlation_id": "7DC1746A-42A0-4125-BEA9-1DDF3E48ABA8",
  "enrichment_results": {
    "entities_extracted": 42,
    "quality_score": 0.87,
    "complexity_score": 0.65,
    "patterns_detected": ["factory_pattern", "singleton_pattern"],
    "anti_patterns_detected": []
  }
}
```

### 3.4 Enrichment Progress Topic (Optional)

**Topic Name**: `dev.archon-intelligence.enrichment-progress.v1`

**Purpose**: Real-time progress updates for long-running enrichments

**Message Schema**:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "correlation_id": "7DC1746A-42A0-4125-BEA9-1DDF3E48ABA8",
  "stage": "entity_extraction",
  "progress_percent": 45,
  "updated_at": "2025-10-30T18:30:10.123Z",
  "estimated_completion": "2025-10-30T18:30:15.000Z"
}
```

---

## 4. Component Design

### 4.1 Bridge Service (Producer)

**Location**: `services/bridge/app.py`

**New Responsibilities**:
1. ✅ Index documents to Memgraph/Qdrant (existing)
2. ✨ Publish enrichment request events to Kafka (NEW)
3. ✅ Return success immediately (modified)

**New Dependencies**:
```python
# requirements.txt
aiokafka==0.12.0  # Async Kafka producer
```

**Configuration**:
```python
# services/bridge/.env
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
KAFKA_ENRICHMENT_TOPIC=dev.archon-intelligence.enrich-document.v1
ENABLE_ASYNC_ENRICHMENT=true  # Feature flag for gradual rollout
```

**Pseudo-Implementation**:
```python
class KafkaProducerManager:
    """Manages Kafka producer lifecycle."""

    def __init__(self):
        self.producer = None

    async def start(self):
        """Initialize Kafka producer on app startup."""
        self.producer = aiokafka.AIOKafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            compression_type='snappy',
            acks='all',  # Wait for all replicas
            retries=3,   # Retry failed sends
            max_in_flight_requests_per_connection=5
        )
        await self.producer.start()

    async def stop(self):
        """Cleanup producer on app shutdown."""
        if self.producer:
            await self.producer.stop()

    async def publish_enrichment_request(
        self,
        document_id: str,
        project_name: str,
        content_hash: str,
        file_path: str,
        document_type: str,
        language: str | None,
        metadata: dict,
        correlation_id: str
    ):
        """Publish enrichment request event."""
        event = {
            "document_id": document_id,
            "project_name": project_name,
            "content_hash": content_hash,
            "file_path": file_path,
            "document_type": document_type,
            "language": language,
            "indexed_at": datetime.utcnow().isoformat() + "Z",
            "enrichment_type": "full",
            "priority": "normal",
            "correlation_id": correlation_id,
            "metadata": metadata,
            "retry_count": 0
        }

        # Publish to Kafka (non-blocking, fire-and-forget)
        await self.producer.send_and_wait(
            config.KAFKA_ENRICHMENT_TOPIC,
            value=event,
            key=document_id.encode('utf-8')  # Partition by document_id
        )

        logger.info(
            f"📤 Published enrichment request | "
            f"document_id={document_id} | correlation_id={correlation_id}"
        )


# Modified indexing pipeline in app.py
async def sync_document_to_knowledge_graph_background(document_data: Dict[str, Any]):
    """Index document and publish enrichment event (non-blocking)."""

    document_id = document_data.get("document_id")
    correlation_id = str(uuid.uuid4()).upper()

    try:
        # 1. Index to Memgraph (FAST, <100ms)
        document_entity = {
            "entity_id": document_id,
            "entity_type": "document",
            "name": document_data.get("title"),
            "properties": {
                "project_id": document_data.get("project_id"),
                "document_type": document_data.get("document_type"),
                "content_preview": document_data.get("full_text", "")[:500],
                "source_path": document_data.get("source_path"),
                "metadata": document_data.get("metadata", {}),
                "enrichment_status": "pending",  # NEW
                "indexed_at": datetime.utcnow().isoformat()
            },
            "confidence_score": 1.0
        }

        await memgraph_connector.store_entities([document_entity])

        logger.info(
            f"✅ Document indexed to Memgraph | "
            f"document_id={document_id} | time_ms=<100"
        )

        # 2. Publish enrichment request (ASYNC, <5ms)
        if config.ENABLE_ASYNC_ENRICHMENT:
            await kafka_producer.publish_enrichment_request(
                document_id=document_id,
                project_name=document_data.get("project_id"),
                content_hash=document_data.get("content_hash"),
                file_path=document_data.get("source_path"),
                document_type=document_data.get("document_type"),
                language=document_data.get("language"),
                metadata=document_data.get("metadata", {}),
                correlation_id=correlation_id
            )

            logger.info(
                f"🚀 Async enrichment queued | "
                f"document_id={document_id} | correlation_id={correlation_id}"
            )

    except Exception as e:
        logger.error(f"Indexing failed | document_id={document_id} | error={e}")
        raise
```

### 4.2 Intelligence Consumer Service (Consumer)

**Location**: `services/intelligence-consumer/` (NEW SERVICE)

**Responsibilities**:
1. Consume enrichment request events from Kafka
2. Call intelligence service APIs for processing
3. Update Memgraph/Qdrant with enriched data
4. Handle failures and publish to DLQ
5. Emit enrichment-completed events

**Configuration**:
```yaml
# docker-compose.yml
services:
  archon-intelligence-enrichment-consumer:
    build: ./services/intelligence-consumer
    environment:
      KAFKA_BOOTSTRAP_SERVERS: omninode-bridge-redpanda:9092
      KAFKA_GROUP_ID: archon-intelligence-enrichment-consumer-group
      KAFKA_ENRICHMENT_TOPIC: dev.archon-intelligence.enrich-document.v1
      KAFKA_DLQ_TOPIC: dev.archon-intelligence.enrich-document-dlq.v1
      KAFKA_COMPLETED_TOPIC: dev.archon-intelligence.enrichment-completed.v1
      INTELLIGENCE_SERVICE_URL: http://archon-intelligence:8053
      MEMGRAPH_URI: bolt://memgraph:7687
      QDRANT_URL: http://qdrant:6333
      MAX_CONCURRENT_ENRICHMENTS: 10
      RETRY_MAX_ATTEMPTS: 3
      RETRY_BACKOFF_BASE: 2.0
      ENABLE_CIRCUIT_BREAKER: true
    networks:
      - app-network
      - omninode-bridge-network
```

**Pseudo-Implementation**:
```python
# services/intelligence-consumer/src/main.py

import asyncio
from typing import Dict, Any
import aiokafka
import httpx
from circuitbreaker import circuit

class IntelligenceEnrichmentConsumer:
    """Consumes enrichment requests and processes documents."""

    def __init__(self):
        self.consumer = None
        self.producer = None  # For DLQ and completed events
        self.http_client = None
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_ENRICHMENTS)
        self.circuit_breaker_failures = 0

    async def start(self):
        """Initialize consumer and producer."""
        self.consumer = aiokafka.AIOKafkaConsumer(
            config.KAFKA_ENRICHMENT_TOPIC,
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            group_id=config.KAFKA_GROUP_ID,
            auto_offset_reset='earliest',
            enable_auto_commit=False,  # Manual commit for reliability
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )

        self.producer = aiokafka.AIOKafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        await self.consumer.start()
        await self.producer.start()

        logger.info("✅ Intelligence enrichment consumer started")

        # Start consumption loop
        asyncio.create_task(self._consume_loop())

    async def _consume_loop(self):
        """Main consumption loop."""
        try:
            async for message in self.consumer:
                # Process message with concurrency limit
                asyncio.create_task(self._process_message(message))

        except Exception as e:
            logger.error(f"Consumer loop failed: {e}")

    async def _process_message(self, message):
        """Process a single enrichment request."""
        async with self.semaphore:  # Limit concurrency
            event = message.value
            document_id = event.get("document_id")
            correlation_id = event.get("correlation_id")
            retry_count = event.get("retry_count", 0)

            logger.info(
                f"📥 Processing enrichment request | "
                f"document_id={document_id} | correlation_id={correlation_id} | "
                f"retry={retry_count}"
            )

            try:
                # Call intelligence service
                enrichment_result = await self._enrich_document(event)

                # Update Memgraph/Qdrant
                await self._update_enrichment(document_id, enrichment_result)

                # Publish completion event
                await self._publish_completed(document_id, enrichment_result, correlation_id)

                # Commit offset (success)
                await self.consumer.commit()

                logger.info(
                    f"✅ Enrichment completed | "
                    f"document_id={document_id} | correlation_id={correlation_id}"
                )

            except Exception as e:
                logger.error(
                    f"❌ Enrichment failed | "
                    f"document_id={document_id} | error={e}"
                )

                # Retry logic with exponential backoff
                if retry_count < config.RETRY_MAX_ATTEMPTS:
                    # Re-queue with incremented retry count
                    event["retry_count"] = retry_count + 1
                    await self.producer.send(
                        config.KAFKA_ENRICHMENT_TOPIC,
                        value=event
                    )
                    logger.info(
                        f"🔄 Retry queued | "
                        f"document_id={document_id} | retry={retry_count + 1}"
                    )
                else:
                    # Move to DLQ
                    await self._publish_to_dlq(event, e)
                    logger.error(
                        f"☠️ Moved to DLQ | "
                        f"document_id={document_id} | correlation_id={correlation_id}"
                    )

                # Commit offset (even on failure)
                await self.consumer.commit()

    @circuit(failure_threshold=5, recovery_timeout=60)
    async def _enrich_document(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Call intelligence service to enrich document."""
        document_id = event.get("document_id")

        # Build request to intelligence service
        request_body = {
            "document_id": document_id,
            "project_name": event.get("project_name"),
            "file_path": event.get("file_path"),
            "document_type": event.get("document_type"),
            "language": event.get("language"),
            "enrichment_type": event.get("enrichment_type")
        }

        # Call intelligence service
        response = await self.http_client.post(
            f"{config.INTELLIGENCE_SERVICE_URL}/process/document",
            json=request_body,
            timeout=60.0  # Allow 60s for processing
        )

        if response.status_code != 200:
            raise Exception(
                f"Intelligence service returned {response.status_code}: {response.text}"
            )

        return response.json()

    async def _update_enrichment(self, document_id: str, result: Dict[str, Any]):
        """Update Memgraph and Qdrant with enrichment data."""
        # Update Memgraph entity properties
        enrichment_properties = {
            "enrichment_status": "completed",
            "enriched_at": datetime.utcnow().isoformat(),
            "entities_extracted": result.get("entities_extracted", 0),
            "quality_score": result.get("quality_score", 0.0),
            "complexity_score": result.get("complexity_score", 0.0),
            "patterns_detected": result.get("patterns_detected", []),
            "anti_patterns_detected": result.get("anti_patterns_detected", [])
        }

        # TODO: Update Memgraph via Cypher query
        # TODO: Update Qdrant vector metadata

    async def _publish_completed(
        self,
        document_id: str,
        result: Dict[str, Any],
        correlation_id: str
    ):
        """Publish enrichment-completed event."""
        event = {
            "document_id": document_id,
            "enrichment_status": "success",
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "correlation_id": correlation_id,
            "enrichment_results": result
        }

        await self.producer.send(
            config.KAFKA_COMPLETED_TOPIC,
            value=event
        )

    async def _publish_to_dlq(self, original_event: Dict[str, Any], error: Exception):
        """Publish failed message to Dead Letter Queue."""
        dlq_event = {
            "failure_reason": str(error),
            "failure_timestamp": datetime.utcnow().isoformat() + "Z",
            "failure_count": original_event.get("retry_count", 0) + 1,
            "original_message": original_event,
            "error_details": {
                "exception_type": type(error).__name__,
                "exception_message": str(error)
            }
        }

        await self.producer.send(
            config.KAFKA_DLQ_TOPIC,
            value=dlq_event
        )
```

### 4.3 Intelligence Service Modifications

**Location**: `services/intelligence/src/services/`

**Required Changes**: MINIMAL (mostly reuse existing APIs)

The intelligence service already exposes:
- `/process/document` - Document processing
- `/extract/code` - Code entity extraction
- `/assess/code` - Quality assessment

**New Endpoints** (optional for optimization):
```python
@router.post("/process/document/batch")
async def batch_process_documents(
    documents: List[DocumentProcessingRequest]
) -> List[DocumentProcessingResponse]:
    """Batch process multiple documents for efficiency."""
    # Process multiple documents in parallel
    tasks = [process_document(doc) for doc in documents]
    results = await asyncio.gather(*tasks)
    return results
```

---

## 5. Resilience Patterns

### 5.1 Retry Strategy with Exponential Backoff

**Pattern**: Retry failed enrichments with increasing delays

**Configuration**:
```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "base_delay_seconds": 2.0,
    "max_delay_seconds": 60.0,
    "exponential_base": 2.0,
    "jitter": True  # Add randomness to prevent thundering herd
}
```

**Implementation**:
```python
async def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 2.0
) -> Any:
    """Retry function with exponential backoff."""

    for attempt in range(max_attempts):
        try:
            return await func()

        except Exception as e:
            if attempt == max_attempts - 1:
                # Final attempt failed
                raise

            # Calculate delay with exponential backoff + jitter
            delay = base_delay * (2 ** attempt)
            jitter = random.uniform(0, delay * 0.1)  # ±10% jitter
            total_delay = min(delay + jitter, 60.0)

            logger.warning(
                f"Retry attempt {attempt + 1}/{max_attempts} failed. "
                f"Retrying in {total_delay:.2f}s. Error: {e}"
            )

            await asyncio.sleep(total_delay)
```

**Retry Scenarios**:
- ✅ **Transient network errors** (connection timeout, DNS failure)
- ✅ **Service temporarily unavailable** (503, 429 rate limit)
- ✅ **Database connection errors** (connection pool exhausted)
- ❌ **Permanent failures** (400 bad request, 401 unauthorized)
- ❌ **Data validation errors** (invalid document format)

### 5.2 Circuit Breaker Pattern

**Pattern**: Prevent cascading failures when intelligence service is unhealthy

**States**:
```
CLOSED ──[failures >= threshold]──> OPEN ──[timeout]──> HALF-OPEN
  ↑                                    │                      │
  └─[success]───────────────────[success]─────────────────────┘
                                       │
                           [failure]───┘
```

**Configuration**:
```python
CIRCUIT_BREAKER_CONFIG = {
    "failure_threshold": 5,      # Open after 5 consecutive failures
    "recovery_timeout": 60,      # Try recovery after 60s
    "expected_exceptions": [     # Exceptions that trigger circuit breaker
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.NetworkError
    ]
}
```

**Implementation**:
```python
from circuitbreaker import circuit, CircuitBreakerError

class IntelligenceServiceClient:
    """Client with circuit breaker protection."""

    @circuit(
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=httpx.RequestError
    )
    async def process_document(self, document_id: str) -> Dict[str, Any]:
        """Process document with circuit breaker protection."""
        response = await self.http_client.post(
            f"{config.INTELLIGENCE_SERVICE_URL}/process/document",
            json={"document_id": document_id},
            timeout=60.0
        )

        if response.status_code != 200:
            raise Exception(f"Intelligence service returned {response.status_code}")

        return response.json()


# Usage in consumer
try:
    result = await intelligence_client.process_document(document_id)
except CircuitBreakerError:
    logger.error("Circuit breaker OPEN - intelligence service unhealthy")
    # Move to DLQ immediately (don't retry)
    await publish_to_dlq(event, "Circuit breaker open")
```

**Monitoring**:
```python
# Expose circuit breaker metrics
@app.get("/metrics/circuit_breaker")
async def circuit_breaker_metrics():
    return {
        "state": intelligence_client.process_document.current_state,
        "failure_count": intelligence_client.process_document.failure_count,
        "last_failure": intelligence_client.process_document.last_failure_time,
        "opened_at": intelligence_client.process_document.opened_at
    }
```

### 5.3 Dead Letter Queue (DLQ) Strategy

**Purpose**: Capture and analyze failed enrichments for manual intervention

**DLQ Processing Workflow**:
```
1. Consumer fails to enrich document after 3 retries
2. Publish to DLQ topic with full error context
3. DLQ consumer processes failed messages:
   - Analyze failure patterns
   - Alert on critical failures
   - Retry with manual intervention
   - Log for post-mortem analysis
```

**DLQ Consumer** (separate service):
```python
# services/intelligence-dlq-processor/src/main.py

class DLQProcessor:
    """Process Dead Letter Queue messages."""

    async def process_dlq_message(self, message):
        """Analyze and handle DLQ message."""
        failure_reason = message.get("failure_reason")
        document_id = message.get("original_message", {}).get("document_id")

        # Classify failure type
        failure_type = self._classify_failure(failure_reason)

        if failure_type == "transient":
            # Retry after longer delay
            await asyncio.sleep(300)  # 5 minutes
            await self._retry_enrichment(message.get("original_message"))

        elif failure_type == "data_quality":
            # Alert data quality team
            await self._alert_data_quality_issue(document_id, failure_reason)

        elif failure_type == "service_down":
            # Alert ops team
            await self._alert_service_health_issue(failure_reason)

        # Always log to metrics
        await self._log_dlq_metrics(failure_type, document_id)
```

### 5.4 Idempotency Guarantee

**Pattern**: Ensure enrichment operations can be safely retried

**Implementation**:
```python
# Memgraph idempotent update
async def update_document_enrichment(document_id: str, enrichment_data: Dict[str, Any]):
    """Idempotent enrichment update using content_hash."""

    content_hash = enrichment_data.get("content_hash")

    # Check if already enriched with this content_hash
    query = """
    MATCH (doc:Document {entity_id: $document_id})
    WHERE doc.enrichment_content_hash = $content_hash
    RETURN doc.enriched_at as enriched_at
    """

    result = await memgraph.execute_query(query, {
        "document_id": document_id,
        "content_hash": content_hash
    })

    if result:
        # Already enriched with this version
        logger.info(
            f"Document already enriched | "
            f"document_id={document_id} | content_hash={content_hash}"
        )
        return

    # Update enrichment (idempotent)
    update_query = """
    MATCH (doc:Document {entity_id: $document_id})
    SET doc += $enrichment_properties,
        doc.enrichment_content_hash = $content_hash,
        doc.enriched_at = datetime()
    """

    await memgraph.execute_query(update_query, {
        "document_id": document_id,
        "content_hash": content_hash,
        "enrichment_properties": enrichment_data
    })
```

### 5.5 Backpressure Handling

**Pattern**: Prevent consumer from overwhelming intelligence service

**Implementation**:
```python
class ConsumerWithBackpressure:
    """Consumer with automatic backpressure."""

    def __init__(self):
        # Limit concurrent enrichments
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_ENRICHMENTS)

        # Track processing rate
        self.processing_rate_window = deque(maxlen=100)
        self.last_rate_check = time.time()

    async def _process_with_backpressure(self, message):
        """Process message with backpressure."""

        # Check if processing rate is too high
        current_rate = self._calculate_processing_rate()

        if current_rate > config.MAX_PROCESSING_RATE:
            # Apply backpressure
            delay = self._calculate_backpressure_delay(current_rate)
            logger.warning(
                f"⚠️ Backpressure applied | "
                f"rate={current_rate:.1f}/s | delay={delay:.2f}s"
            )
            await asyncio.sleep(delay)

        # Process with concurrency limit
        async with self.semaphore:
            await self._process_message(message)

    def _calculate_processing_rate(self) -> float:
        """Calculate current processing rate."""
        now = time.time()
        window_seconds = 60.0

        # Count messages processed in last 60 seconds
        cutoff_time = now - window_seconds
        recent_messages = [
            t for t in self.processing_rate_window
            if t > cutoff_time
        ]

        return len(recent_messages) / window_seconds

    def _calculate_backpressure_delay(self, current_rate: float) -> float:
        """Calculate delay to apply backpressure."""
        target_rate = config.MAX_PROCESSING_RATE
        excess_rate = current_rate - target_rate

        # Linear backpressure: more excess = more delay
        delay = excess_rate / target_rate * 5.0  # Max 5s delay

        return min(delay, 5.0)
```

---

## 6. Implementation Roadmap

### Phase 1: Foundation Setup (Week 1)

**Goal**: Establish Kafka infrastructure and event schemas

**Tasks**:
1. **Create Kafka Topics**
   ```bash
   # Create enrichment request topic
   rpk topic create dev.archon-intelligence.enrich-document.v1 \
     --partitions 4 \
     --replicas 3 \
     --config retention.ms=604800000 \
     --config compression.type=snappy

   # Create DLQ topic
   rpk topic create dev.archon-intelligence.enrich-document-dlq.v1 \
     --partitions 1 \
     --replicas 3 \
     --config retention.ms=2592000000 \
     --config cleanup.policy=compact

   # Create completion topic
   rpk topic create dev.archon-intelligence.enrichment-completed.v1 \
     --partitions 4 \
     --replicas 3
   ```

2. **Define Event Schemas**
   - Create Pydantic models for all event types
   - Add JSON Schema validation
   - Document schema versioning strategy

3. **Add Kafka Dependencies**
   ```bash
   # Bridge service
   cd services/bridge
   poetry add aiokafka==0.12.0

   # Intelligence consumer (new service)
   mkdir -p services/intelligence-consumer
   cd services/intelligence-consumer
   poetry init
   poetry add aiokafka==0.12.0 httpx pydantic
   ```

4. **Create Consumer Service Skeleton**
   - Initialize FastAPI app
   - Add health check endpoint
   - Add metrics endpoint

**Validation**:
- ✅ Topics created and visible in Redpanda console
- ✅ Event schemas validated with test data
- ✅ Consumer service starts successfully

---

### Phase 2: Bridge Producer Implementation (Week 2)

**Goal**: Add Kafka producer to bridge service

**Tasks**:
1. **Add KafkaProducerManager Class**
   - Implement producer lifecycle (start/stop)
   - Add event publishing methods
   - Handle producer errors gracefully

2. **Modify Indexing Pipeline**
   - Update `sync_document_to_knowledge_graph_background()`
   - Add enrichment event publishing
   - Keep synchronous path for backward compatibility

3. **Add Feature Flag**
   ```python
   # services/bridge/.env
   ENABLE_ASYNC_ENRICHMENT=false  # Default: false (rollout gradually)
   ```

4. **Add Logging and Metrics**
   ```python
   # Log every event published
   logger.info(
       f"📤 Published enrichment request | "
       f"document_id={document_id} | correlation_id={correlation_id}"
   )

   # Track metrics
   metrics.enrichment_events_published.inc()
   metrics.enrichment_publish_latency.observe(publish_time_ms)
   ```

5. **Write Unit Tests**
   - Test producer initialization
   - Test event publishing
   - Test error handling
   - Test feature flag toggling

**Validation**:
- ✅ Events successfully published to Kafka topic
- ✅ Event schema validation passes
- ✅ Bridge service performance unchanged (<100ms latency)
- ✅ Feature flag works (can enable/disable async)

**Testing Commands**:
```bash
# Test event publishing
curl -X POST http://localhost:8054/api/bridge/document \
  -H "Content-Type: application/json" \
  -d @test_document.json

# Verify event in Kafka
rpk topic consume dev.archon-intelligence.enrich-document.v1 \
  --num 1 \
  --format json
```

---

### Phase 3: Intelligence Consumer Implementation (Week 3-4)

**Goal**: Build intelligence consumer service

**Tasks**:
1. **Implement Consumer Core Logic**
   - Kafka consumer initialization
   - Message consumption loop
   - Concurrency control (semaphore)
   - Manual offset commit

2. **Implement Enrichment Processing**
   - Call intelligence service `/process/document`
   - Parse and validate response
   - Update Memgraph entity properties
   - Update Qdrant vector metadata

3. **Implement Retry Logic**
   - Exponential backoff retry
   - Retry count tracking
   - DLQ publishing after max retries

4. **Implement Circuit Breaker**
   - Circuit breaker for intelligence service
   - State monitoring (CLOSED/OPEN/HALF-OPEN)
   - Metrics exposure

5. **Add Monitoring and Logging**
   ```python
   # Comprehensive logging
   logger.info(
       f"📥 Processing enrichment | "
       f"document_id={document_id} | "
       f"correlation_id={correlation_id} | "
       f"retry={retry_count}"
   )

   logger.info(
       f"✅ Enrichment completed | "
       f"document_id={document_id} | "
       f"time_ms={processing_time_ms} | "
       f"entities={entities_extracted}"
   )

   # Metrics
   metrics.enrichments_processed.inc()
   metrics.enrichment_processing_time.observe(processing_time_ms)
   metrics.enrichment_errors.inc(labels={"error_type": error_type})
   ```

6. **Write Comprehensive Tests**
   - Unit tests for consumer logic
   - Integration tests with test Kafka
   - Mock intelligence service responses
   - Test retry scenarios
   - Test DLQ publishing

**Validation**:
- ✅ Consumer successfully processes events
- ✅ Intelligence service called correctly
- ✅ Memgraph/Qdrant updated with enrichment
- ✅ Retry logic works (3 retries with backoff)
- ✅ DLQ receives failed messages
- ✅ Circuit breaker opens on failures

**Testing Commands**:
```bash
# Start consumer service
docker compose up archon-intelligence-enrichment-consumer

# Publish test event
python3 scripts/publish_test_enrichment_event.py

# Monitor consumer logs
docker logs -f archon-intelligence-enrichment-consumer

# Check enrichment status in Memgraph
docker exec -it archon-memgraph mgconsole
MATCH (doc:Document {entity_id: "<document_id>"})
RETURN doc.enrichment_status, doc.enriched_at, doc.quality_score;
```

---

### Phase 4: Integration and Testing (Week 5)

**Goal**: End-to-end integration testing

**Tasks**:
1. **End-to-End Flow Testing**
   - Ingest document via bulk script
   - Verify fast indexing (<200ms)
   - Verify async enrichment (5-15s)
   - Verify enrichment data in Memgraph/Qdrant

2. **Load Testing**
   ```bash
   # Ingest 1000 documents
   python3 scripts/bulk_ingest_repository.py \
     --project-name load-test \
     --kafka-servers 192.168.86.200:29092 \
     /path/to/large/project

   # Monitor consumer lag
   rpk group describe archon-intelligence-enrichment-consumer-group

   # Monitor processing rate
   curl http://localhost:8052/metrics | grep enrichment_processing_time
   ```

3. **Failure Scenario Testing**
   - Stop intelligence service (test circuit breaker)
   - Inject network errors (test retry logic)
   - Fill consumer queue (test backpressure)
   - Restart consumer (test offset management)

4. **Performance Benchmarking**
   - Measure indexing latency (target: <200ms)
   - Measure enrichment throughput (target: >10/s per consumer)
   - Measure end-to-end latency (target: <15s)

5. **Data Consistency Validation**
   ```bash
   # Verify all documents enriched
   python3 scripts/validate_enrichment_completeness.py

   # Check for missing enrichments
   docker exec archon-memgraph mgconsole
   MATCH (doc:Document)
   WHERE doc.enrichment_status = 'pending'
   AND datetime(doc.indexed_at) < datetime() - duration({hours: 1})
   RETURN count(doc) as pending_count;
   ```

**Validation**:
- ✅ 1000 documents indexed in <3 minutes (indexing)
- ✅ 1000 documents enriched in <15 minutes (enrichment)
- ✅ Zero data loss (all documents either enriched or in DLQ)
- ✅ Circuit breaker prevents cascading failures
- ✅ Consumer recovers gracefully from failures

---

### Phase 5: Migration and Deployment (Week 6)

**Goal**: Gradual rollout to production

**Tasks**:
1. **Gradual Rollout Strategy**
   - **Stage 1**: Enable async enrichment for 10% of projects
   - **Stage 2**: Increase to 50% after 48 hours observation
   - **Stage 3**: Increase to 100% after 1 week observation
   - **Stage 4**: Remove synchronous code path

2. **Feature Flag Management**
   ```python
   # Per-project feature flags
   ASYNC_ENRICHMENT_ENABLED_PROJECTS = [
       "test-project-1",
       "test-project-2"
   ]

   # Gradual rollout percentage
   ASYNC_ENRICHMENT_ROLLOUT_PERCENTAGE = 10  # 10% of projects

   def should_use_async_enrichment(project_name: str) -> bool:
       """Determine if project should use async enrichment."""
       # Explicit enable list
       if project_name in ASYNC_ENRICHMENT_ENABLED_PROJECTS:
           return True

       # Percentage-based rollout
       project_hash = hashlib.md5(project_name.encode()).hexdigest()
       project_bucket = int(project_hash[:8], 16) % 100

       return project_bucket < ASYNC_ENRICHMENT_ROLLOUT_PERCENTAGE
   ```

3. **Monitoring Dashboard**
   - Create Grafana dashboard for enrichment metrics
   - Alert on high DLQ volume
   - Alert on consumer lag >500
   - Alert on enrichment latency >30s

4. **Migration of Existing Documents**
   ```python
   # Backfill enrichment for existing documents
   async def backfill_enrichment():
       """Backfill enrichment for documents without it."""

       query = """
       MATCH (doc:Document)
       WHERE doc.enrichment_status IS NULL
           OR doc.enrichment_status = 'pending'
       RETURN doc.entity_id as document_id,
              doc.properties.project_id as project_name,
              doc.properties.source_path as file_path
       LIMIT 1000
       """

       documents = await memgraph.execute_query(query)

       for doc in documents:
           # Publish enrichment request
           await kafka_producer.publish_enrichment_request(
               document_id=doc["document_id"],
               project_name=doc["project_name"],
               file_path=doc["file_path"],
               # ... other fields
           )
   ```

5. **Documentation**
   - Update CLAUDE.md with async architecture
   - Document monitoring procedures
   - Document troubleshooting guide
   - Document rollback procedure

**Validation**:
- ✅ Async enrichment enabled for all projects
- ✅ Zero degradation in user experience
- ✅ Monitoring dashboards showing healthy metrics
- ✅ All existing documents backfilled

---

## 7. Migration Strategy

### 7.1 Backward Compatibility

**Dual-Mode Operation**:
```python
# Support both sync and async modes during migration
async def sync_document_to_knowledge_graph_background(document_data: Dict[str, Any]):
    """Index document with optional async enrichment."""

    project_name = document_data.get("project_id")
    document_id = document_data.get("document_id")

    # Always index to Memgraph (FAST)
    await index_to_memgraph(document_data)

    # Check if async enrichment enabled for this project
    if should_use_async_enrichment(project_name):
        # NEW: Async enrichment via Kafka
        await kafka_producer.publish_enrichment_request(...)

        logger.info(
            f"🚀 Async enrichment queued | "
            f"document_id={document_id} | project={project_name}"
        )
    else:
        # OLD: Synchronous enrichment (legacy path)
        enrichment_result = await call_intelligence_service_sync(document_data)
        await update_enrichment(document_id, enrichment_result)

        logger.info(
            f"✅ Sync enrichment completed | "
            f"document_id={document_id} | project={project_name}"
        )
```

### 7.2 Rollback Plan

**If async enrichment causes issues**:

1. **Immediate Rollback** (5 minutes)
   ```bash
   # Disable async enrichment globally
   docker exec archon-bridge sh -c 'echo "ENABLE_ASYNC_ENRICHMENT=false" >> /app/.env'
   docker restart archon-bridge

   # Stop consumer
   docker stop archon-intelligence-enrichment-consumer
   ```

2. **Drain Kafka Queue** (30 minutes)
   ```bash
   # Check queue depth
   rpk group describe archon-intelligence-enrichment-consumer-group

   # Wait for queue to drain or manually process
   ```

3. **Switch Back to Sync Mode** (permanent)
   ```bash
   # Update docker-compose.yml
   environment:
     ENABLE_ASYNC_ENRICHMENT: "false"

   # Redeploy
   docker compose up -d archon-bridge
   ```

### 7.3 Data Migration Plan

**Backfill Enrichment for Existing Documents**:

```bash
# Step 1: Identify documents missing enrichment
python3 scripts/identify_unenriched_documents.py \
  --output unenriched_documents.json

# Step 2: Publish enrichment events for backfill
python3 scripts/backfill_enrichment.py \
  --input unenriched_documents.json \
  --batch-size 100 \
  --rate-limit 10  # 10/second

# Step 3: Monitor backfill progress
python3 scripts/monitor_backfill_progress.py \
  --watch
```

**Backfill Script**:
```python
# scripts/backfill_enrichment.py

async def backfill_enrichment(
    documents: List[Dict[str, Any]],
    batch_size: int = 100,
    rate_limit: int = 10
):
    """Backfill enrichment for existing documents."""

    producer = aiokafka.AIOKafkaProducer(
        bootstrap_servers="192.168.86.200:29092",
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    await producer.start()

    try:
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]

            for doc in batch:
                # Publish enrichment request
                event = {
                    "document_id": doc["document_id"],
                    "project_name": doc["project_name"],
                    "file_path": doc["file_path"],
                    # ... other fields
                    "enrichment_type": "full",
                    "priority": "low"  # Low priority for backfill
                }

                await producer.send(
                    "dev.archon-intelligence.enrich-document.v1",
                    value=event
                )

            print(f"✅ Backfilled {i+len(batch)}/{len(documents)} documents")

            # Rate limiting
            await asyncio.sleep(batch_size / rate_limit)

    finally:
        await producer.stop()
```

---

## 8. Code Modification Guide

### 8.1 Bridge Service Changes

**File**: `services/bridge/app.py`

**Location**: After line 498 (SKIP_INTELLIGENCE_ENRICHMENT check)

**Changes Required**:

1. **Add Kafka Producer Import**:
```python
# At top of file
from aiokafka import AIOKafkaProducer
import json
```

2. **Add KafkaProducerManager Class** (new class):
```python
class KafkaProducerManager:
    """Manages Kafka producer lifecycle for enrichment events."""

    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.enabled = os.getenv("ENABLE_ASYNC_ENRICHMENT", "false").lower() == "true"
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "omninode-bridge-redpanda:9092")
        self.topic = os.getenv("KAFKA_ENRICHMENT_TOPIC", "dev.archon-intelligence.enrich-document.v1")

    async def start(self):
        """Initialize Kafka producer on app startup."""
        if not self.enabled:
            logger.info("Async enrichment disabled (ENABLE_ASYNC_ENRICHMENT=false)")
            return

        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            compression_type='snappy',
            acks='all',
            retries=3,
            max_in_flight_requests_per_connection=5
        )

        await self.producer.start()
        logger.info(f"✅ Kafka producer started | topic={self.topic}")

    async def stop(self):
        """Cleanup producer on app shutdown."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")

    async def publish_enrichment_request(
        self,
        document_id: str,
        project_name: str,
        content_hash: str,
        file_path: str,
        document_type: str,
        language: Optional[str],
        metadata: Dict[str, Any],
        correlation_id: str
    ):
        """Publish enrichment request event to Kafka."""
        if not self.enabled or not self.producer:
            return

        event = {
            "document_id": document_id,
            "project_name": project_name,
            "content_hash": content_hash,
            "file_path": file_path,
            "document_type": document_type,
            "language": language,
            "indexed_at": datetime.utcnow().isoformat() + "Z",
            "enrichment_type": "full",
            "priority": "normal",
            "correlation_id": correlation_id,
            "metadata": metadata,
            "retry_count": 0
        }

        try:
            # Publish to Kafka (non-blocking, fire-and-forget)
            await self.producer.send_and_wait(
                self.topic,
                value=event,
                key=document_id.encode('utf-8')
            )

            logger.info(
                f"📤 Published enrichment request | "
                f"document_id={document_id} | correlation_id={correlation_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ Failed to publish enrichment request | "
                f"document_id={document_id} | error={e}"
            )
            # Don't fail indexing if enrichment publish fails
            # Just log the error and continue


# Global instance
kafka_producer = KafkaProducerManager()
```

3. **Update App Lifespan** (modify existing lifespan function):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    global memgraph_connector, kafka_producer

    # ... existing startup code ...

    # Start Kafka producer
    await kafka_producer.start()

    yield

    # Shutdown
    # ... existing shutdown code ...

    # Stop Kafka producer
    await kafka_producer.stop()
```

4. **Modify Indexing Function** (line 498+):
```python
async def sync_document_to_knowledge_graph_background(document_data: Dict[str, Any]):
    """Index document and publish async enrichment request."""

    document_id = document_data.get("document_id")
    project_id = document_data.get("project_id")
    correlation_id = str(uuid.uuid4()).upper()

    try:
        # 1. Index to Memgraph (ALWAYS, FAST <100ms)
        document_entity = {
            "entity_id": document_id,
            "entity_type": "document",
            "name": document_data.get("title"),
            "properties": {
                "project_id": project_id,
                "document_type": document_data.get("document_type"),
                "content_preview": document_data.get("full_text", "")[:500],
                "source_path": document_data.get("source_path"),
                "metadata": document_data.get("metadata", {}),
                "enrichment_status": "pending",  # NEW
                "indexed_at": datetime.utcnow().isoformat()
            },
            "confidence_score": 1.0
        }

        if memgraph_connector:
            await memgraph_connector.store_entities([document_entity])

        logger.info(
            f"✅ [INDEXING PIPELINE] Document indexed to Memgraph | "
            f"document_id={document_id} | time_ms=<100"
        )

        # 2. Publish enrichment request (ASYNC, NON-BLOCKING)
        await kafka_producer.publish_enrichment_request(
            document_id=document_id,
            project_name=project_id,
            content_hash=document_data.get("content_hash", ""),
            file_path=document_data.get("source_path", ""),
            document_type=document_data.get("document_type", "code"),
            language=document_data.get("language"),
            metadata=document_data.get("metadata", {}),
            correlation_id=correlation_id
        )

        logger.info(
            f"🚀 [INDEXING PIPELINE] Async enrichment queued | "
            f"document_id={document_id} | correlation_id={correlation_id}"
        )

    except Exception as e:
        logger.error(
            f"❌ [INDEXING PIPELINE] Indexing failed | "
            f"document_id={document_id} | error={e}"
        )
        raise
```

5. **Environment Variables** (`.env`):
```bash
# Async enrichment configuration
ENABLE_ASYNC_ENRICHMENT=true
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
KAFKA_ENRICHMENT_TOPIC=dev.archon-intelligence.enrich-document.v1
```

### 8.2 Intelligence Consumer Service (New Service)

**Create New Service Structure**:
```
services/intelligence-consumer/
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── consumer.py
│   ├── enrichment_processor.py
│   ├── retry_handler.py
│   └── models.py
└── tests/
    ├── unit/
    └── integration/
```

**Complete Implementation**: See [Component Design - Intelligence Consumer Service](#42-intelligence-consumer-service-consumer) section above for full implementation details.

### 8.3 Docker Compose Changes

**File**: `deployment/docker-compose.yml`

**Add New Service**:
```yaml
services:
  # ... existing services ...

  archon-intelligence-enrichment-consumer:
    build:
      context: ../services/intelligence-consumer
      dockerfile: Dockerfile
    container_name: archon-intelligence-enrichment-consumer
    environment:
      # Kafka configuration
      KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS:-omninode-bridge-redpanda:9092}
      KAFKA_GROUP_ID: archon-intelligence-enrichment-consumer-group
      KAFKA_ENRICHMENT_TOPIC: dev.archon-intelligence.enrich-document.v1
      KAFKA_DLQ_TOPIC: dev.archon-intelligence.enrich-document-dlq.v1
      KAFKA_COMPLETED_TOPIC: dev.archon-intelligence.enrichment-completed.v1

      # Service URLs
      INTELLIGENCE_SERVICE_URL: http://archon-intelligence:8053
      MEMGRAPH_URI: bolt://memgraph:7687
      QDRANT_URL: http://qdrant:6333

      # Performance tuning
      MAX_CONCURRENT_ENRICHMENTS: 10

      # Retry configuration
      RETRY_MAX_ATTEMPTS: 3
      RETRY_BACKOFF_BASE: 2.0

      # Circuit breaker
      ENABLE_CIRCUIT_BREAKER: true
      CIRCUIT_BREAKER_FAILURE_THRESHOLD: 5
      CIRCUIT_BREAKER_RECOVERY_TIMEOUT: 60

      # Logging
      LOG_LEVEL: INFO

    ports:
      - "8156:8156"  # Health check and metrics

    networks:
      - app-network
      - omninode-bridge-network  # Access to Redpanda

    depends_on:
      - archon-intelligence
      - memgraph
      - qdrant

    restart: unless-stopped

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8156/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

**Bridge Service - Kafka Producer**:
```python
# services/bridge/tests/unit/test_kafka_producer.py

import pytest
from unittest.mock import AsyncMock, patch
from app import KafkaProducerManager

@pytest.mark.asyncio
async def test_kafka_producer_initialization():
    """Test Kafka producer initializes correctly."""
    producer = KafkaProducerManager()
    producer.enabled = True

    with patch('aiokafka.AIOKafkaProducer') as mock_producer_class:
        mock_producer = AsyncMock()
        mock_producer_class.return_value = mock_producer

        await producer.start()

        assert producer.producer is not None
        mock_producer.start.assert_called_once()

@pytest.mark.asyncio
async def test_publish_enrichment_request():
    """Test publishing enrichment request."""
    producer = KafkaProducerManager()
    producer.enabled = True
    producer.producer = AsyncMock()

    await producer.publish_enrichment_request(
        document_id="test-doc-123",
        project_name="test-project",
        content_hash="abc123",
        file_path="test.py",
        document_type="code",
        language="python",
        metadata={},
        correlation_id="TEST-CORRELATION-ID"
    )

    producer.producer.send_and_wait.assert_called_once()
    call_args = producer.producer.send_and_wait.call_args

    assert call_args[0][0] == producer.topic
    event = call_args[1]['value']
    assert event['document_id'] == "test-doc-123"
    assert event['project_name'] == "test-project"

@pytest.mark.asyncio
async def test_publish_disabled_when_flag_false():
    """Test publish is no-op when ENABLE_ASYNC_ENRICHMENT=false."""
    producer = KafkaProducerManager()
    producer.enabled = False

    await producer.publish_enrichment_request(
        document_id="test-doc-123",
        # ... other params
    )

    # Should not create producer
    assert producer.producer is None
```

**Intelligence Consumer - Event Processing**:
```python
# services/intelligence-consumer/tests/unit/test_consumer.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from consumer import IntelligenceEnrichmentConsumer

@pytest.mark.asyncio
async def test_process_enrichment_success():
    """Test successful enrichment processing."""
    consumer = IntelligenceEnrichmentConsumer()
    consumer.http_client = AsyncMock()
    consumer.http_client.post.return_value.status_code = 200
    consumer.http_client.post.return_value.json.return_value = {
        "entities_extracted": 10,
        "quality_score": 0.85
    }

    event = {
        "document_id": "test-doc-123",
        "project_name": "test-project",
        "file_path": "test.py",
        "correlation_id": "TEST-ID"
    }

    result = await consumer._enrich_document(event)

    assert result['entities_extracted'] == 10
    assert result['quality_score'] == 0.85

@pytest.mark.asyncio
async def test_retry_logic():
    """Test retry logic with exponential backoff."""
    consumer = IntelligenceEnrichmentConsumer()

    # Mock intelligence service to fail twice, then succeed
    consumer.http_client = AsyncMock()
    consumer.http_client.post.side_effect = [
        Exception("Connection timeout"),
        Exception("Connection timeout"),
        MagicMock(status_code=200, json=lambda: {"entities_extracted": 5})
    ]

    event = {
        "document_id": "test-doc-123",
        "retry_count": 0
    }

    # Should succeed after 2 retries
    result = await consumer._process_message_with_retry(event)

    assert result is not None
    assert consumer.http_client.post.call_count == 3

@pytest.mark.asyncio
async def test_dlq_publish_after_max_retries():
    """Test DLQ publish after max retries."""
    consumer = IntelligenceEnrichmentConsumer()
    consumer.http_client = AsyncMock()
    consumer.http_client.post.side_effect = Exception("Permanent failure")
    consumer.producer = AsyncMock()

    event = {
        "document_id": "test-doc-123",
        "retry_count": 3  # Max retries reached
    }

    await consumer._process_message(event)

    # Should publish to DLQ
    consumer.producer.send.assert_called_once()
    call_args = consumer.producer.send.call_args
    assert call_args[0][0] == consumer.dlq_topic
```

### 9.2 Integration Tests

**End-to-End Flow Test**:
```python
# tests/integration/test_async_enrichment_e2e.py

import pytest
import asyncio
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_enrichment_end_to_end():
    """Test complete async enrichment flow."""

    # 1. Publish document indexing event
    document_id = f"test-doc-{uuid.uuid4()}"

    # Index document via bridge service
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8054/api/bridge/document",
            json={
                "document_id": document_id,
                "project_id": "test-project",
                "title": "test.py",
                "full_text": "def hello(): print('world')",
                "source_path": "test.py",
                "document_type": "code",
                "metadata": {}
            }
        )
        assert response.status_code == 200

    # 2. Wait for enrichment request to be published
    await asyncio.sleep(0.5)

    # 3. Verify enrichment request in Kafka
    consumer = AIOKafkaConsumer(
        "dev.archon-intelligence.enrich-document.v1",
        bootstrap_servers="192.168.86.200:29092",
        auto_offset_reset='latest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    await consumer.start()

    enrichment_event_found = False
    async for message in consumer:
        if message.value['document_id'] == document_id:
            enrichment_event_found = True
            break

    await consumer.stop()
    assert enrichment_event_found

    # 4. Wait for enrichment processing (max 30s)
    for _ in range(30):
        # Check Memgraph for enrichment status
        query = f"""
        MATCH (doc:Document {{entity_id: '{document_id}'}})
        RETURN doc.enrichment_status as status,
               doc.entities_extracted as entities
        """

        result = await memgraph_client.execute_query(query)

        if result and result[0]['status'] == 'completed':
            assert result[0]['entities'] > 0
            break

        await asyncio.sleep(1)
    else:
        pytest.fail("Enrichment did not complete within 30 seconds")
```

### 9.3 Load Testing

**Load Test Script**:
```python
# scripts/load_test_async_enrichment.py

import asyncio
import time
from typing import List
import httpx

async def load_test_async_enrichment(
    num_documents: int = 1000,
    concurrency: int = 50
):
    """Load test async enrichment system."""

    print(f"Starting load test: {num_documents} documents, concurrency={concurrency}")

    async def index_document(doc_id: int):
        """Index a single document."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8054/api/bridge/document",
                json={
                    "document_id": f"load-test-{doc_id}",
                    "project_id": "load-test",
                    "title": f"test-{doc_id}.py",
                    "full_text": f"# Test document {doc_id}\ndef test():\n    pass",
                    "source_path": f"test-{doc_id}.py",
                    "document_type": "code"
                },
                timeout=10.0
            )
            return response.status_code == 200

    # Phase 1: Indexing (measure indexing throughput)
    start_time = time.time()

    semaphore = asyncio.Semaphore(concurrency)

    async def index_with_limit(doc_id: int):
        async with semaphore:
            return await index_document(doc_id)

    results = await asyncio.gather(
        *[index_with_limit(i) for i in range(num_documents)],
        return_exceptions=True
    )

    indexing_duration = time.time() - start_time
    success_count = sum(1 for r in results if r is True)

    print(f"✅ Indexing phase complete:")
    print(f"   - Total time: {indexing_duration:.2f}s")
    print(f"   - Success rate: {success_count}/{num_documents}")
    print(f"   - Throughput: {num_documents/indexing_duration:.1f} docs/s")
    print(f"   - Avg latency: {indexing_duration*1000/num_documents:.1f}ms")

    # Phase 2: Wait for enrichment (measure enrichment throughput)
    print(f"\n⏳ Waiting for enrichment to complete...")

    enrichment_start = time.time()

    while True:
        # Check how many documents are enriched
        query = """
        MATCH (doc:Document)
        WHERE doc.properties.project_id = 'load-test'
        RETURN count(doc) as total,
               sum(CASE WHEN doc.enrichment_status = 'completed' THEN 1 ELSE 0 END) as completed
        """

        result = await memgraph_client.execute_query(query)
        total = result[0]['total']
        completed = result[0]['completed']

        print(f"   Progress: {completed}/{total} ({completed/total*100:.1f}%)")

        if completed >= num_documents * 0.95:  # 95% completion threshold
            break

        await asyncio.sleep(5)

    enrichment_duration = time.time() - enrichment_start

    print(f"\n✅ Enrichment phase complete:")
    print(f"   - Total time: {enrichment_duration:.2f}s")
    print(f"   - Throughput: {num_documents/enrichment_duration:.1f} docs/s")
    print(f"   - Avg enrichment time: {enrichment_duration*1000/num_documents:.1f}ms")

if __name__ == "__main__":
    asyncio.run(load_test_async_enrichment(num_documents=1000, concurrency=50))
```

**Expected Results**:
```
✅ Indexing phase complete:
   - Total time: 15.23s
   - Success rate: 1000/1000
   - Throughput: 65.7 docs/s
   - Avg latency: 152ms

✅ Enrichment phase complete:
   - Total time: 120.45s
   - Throughput: 8.3 docs/s
   - Avg enrichment time: 12045ms
```

---

## 10. Monitoring & Observability

### 10.1 Key Metrics to Track

**Indexing Metrics**:
- `archon_bridge_documents_indexed_total` (counter) - Total documents indexed
- `archon_bridge_indexing_duration_seconds` (histogram) - Indexing latency
- `archon_bridge_enrichment_events_published_total` (counter) - Events published
- `archon_bridge_enrichment_publish_errors_total` (counter) - Publish failures

**Consumer Metrics**:
- `archon_enrichment_consumer_messages_consumed_total` (counter) - Messages consumed
- `archon_enrichment_consumer_messages_processed_total` (counter) - Messages processed
- `archon_enrichment_consumer_processing_duration_seconds` (histogram) - Processing time
- `archon_enrichment_consumer_errors_total` (counter by error_type) - Processing errors
- `archon_enrichment_consumer_dlq_published_total` (counter) - DLQ messages
- `archon_enrichment_consumer_retries_total` (counter) - Retry attempts
- `archon_enrichment_consumer_circuit_breaker_state` (gauge) - Circuit breaker state

**Kafka Metrics**:
- `archon_kafka_consumer_lag` (gauge) - Consumer lag per partition
- `archon_kafka_topic_size_bytes` (gauge) - Topic size
- `archon_kafka_topic_messages_count` (gauge) - Message count per topic

**Intelligence Service Metrics**:
- `archon_intelligence_enrichment_requests_total` (counter) - Enrichment requests
- `archon_intelligence_enrichment_duration_seconds` (histogram) - Processing time
- `archon_intelligence_enrichment_errors_total` (counter) - Errors

**Data Consistency Metrics**:
- `archon_documents_pending_enrichment` (gauge) - Documents awaiting enrichment
- `archon_documents_enriched_total` (counter) - Successfully enriched documents
- `archon_enrichment_age_seconds` (histogram) - Time from index to enrichment

### 10.2 Grafana Dashboard

**Dashboard JSON**: `monitoring/grafana/async-enrichment-dashboard.json`

**Panels**:
1. **Indexing Performance**
   - Documents indexed per second
   - P50/P95/P99 indexing latency
   - Enrichment events published per second

2. **Consumer Health**
   - Messages consumed per second
   - Processing success rate
   - Consumer lag per partition

3. **Enrichment Pipeline**
   - Enrichments completed per second
   - P50/P95/P99 enrichment time
   - DLQ message rate

4. **Circuit Breaker Status**
   - Circuit breaker state (CLOSED/OPEN/HALF-OPEN)
   - Failure rate
   - Recovery attempts

5. **Data Consistency**
   - Documents pending enrichment (by age)
   - Enrichment completion rate
   - Documents in DLQ

### 10.3 Alerting Rules

**Prometheus Alerting Rules**: `monitoring/prometheus/async-enrichment-alerts.yml`

```yaml
groups:
  - name: async_enrichment
    interval: 30s
    rules:
      # High consumer lag
      - alert: HighConsumerLag
        expr: archon_kafka_consumer_lag > 500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High Kafka consumer lag"
          description: "Consumer lag is {{ $value }} messages (threshold: 500)"

      # DLQ accumulation
      - alert: DLQAccumulation
        expr: rate(archon_enrichment_consumer_dlq_published_total[5m]) > 0.1
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Dead Letter Queue accumulating messages"
          description: "DLQ rate: {{ $value }} messages/s over 10 minutes"

      # Circuit breaker open
      - alert: CircuitBreakerOpen
        expr: archon_enrichment_consumer_circuit_breaker_state == 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker OPEN"
          description: "Intelligence service circuit breaker is OPEN (service unhealthy)"

      # Enrichment latency high
      - alert: HighEnrichmentLatency
        expr: histogram_quantile(0.95, rate(archon_enrichment_consumer_processing_duration_seconds_bucket[5m])) > 30
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High enrichment latency"
          description: "P95 enrichment time: {{ $value }}s (threshold: 30s)"

      # Documents stuck pending
      - alert: DocumentsStuckPending
        expr: archon_documents_pending_enrichment > 1000
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Many documents pending enrichment"
          description: "{{ $value }} documents pending enrichment for >30 minutes"
```

### 10.4 Logging Standards

**Structured Logging Format**:
```python
# Use structured logging for all services
logger.info(
    "event_name",
    extra={
        "document_id": document_id,
        "correlation_id": correlation_id,
        "project_name": project_name,
        "duration_ms": duration_ms,
        "status": "success|error",
        "error_type": error_type,  # If error
        "retry_count": retry_count
    }
)
```

**Log Aggregation** (ELK/Loki):
- Index: `archon-async-enrichment-*`
- Retention: 30 days
- Queries:
  - Errors: `status:error`
  - Slow enrichments: `duration_ms:>30000`
  - DLQ messages: `event_name:dlq_published`

### 10.5 Health Checks

**Bridge Service**:
```python
@app.get("/health/enrichment")
async def enrichment_health():
    """Enrichment system health check."""
    return {
        "kafka_producer": {
            "status": "healthy" if kafka_producer.producer else "disabled",
            "enabled": kafka_producer.enabled,
            "topic": kafka_producer.topic
        }
    }
```

**Consumer Service**:
```python
@app.get("/health")
async def health():
    """Consumer service health check."""
    return {
        "status": "healthy",
        "consumer": {
            "running": consumer.running,
            "messages_consumed": consumer.messages_consumed,
            "messages_processed": consumer.messages_processed,
            "errors": consumer.errors
        },
        "circuit_breaker": {
            "state": intelligence_client.circuit_breaker_state,
            "failure_count": intelligence_client.failure_count
        }
    }
```

---

## Summary

This architecture design provides:

✅ **10-100x Faster Indexing**: <200ms vs 10-60s
✅ **Horizontal Scalability**: 4+ consumer instances
✅ **Fault Tolerance**: DLQ, retries, circuit breakers
✅ **Backward Compatible**: Gradual rollout with feature flags
✅ **Observable**: Comprehensive metrics and monitoring
✅ **Production-Ready**: Tested resilience patterns

**Next Steps**:
1. Review and approve architecture design
2. Create Kafka topics (Phase 1)
3. Implement bridge producer (Phase 2)
4. Implement intelligence consumer (Phase 3)
5. Integration testing (Phase 4)
6. Gradual production rollout (Phase 5)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-30
**Review Status**: Pending Approval
**Correlation ID**: DBAAF41D-311F-46F2-A652-572548EF50B5
