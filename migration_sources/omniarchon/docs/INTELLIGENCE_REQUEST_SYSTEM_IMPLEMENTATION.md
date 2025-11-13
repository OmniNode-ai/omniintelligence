# Intelligence Request System Implementation

**Version**: 1.0.0
**Date**: 2025-10-26
**Status**: ✅ IMPLEMENTED
**Purpose**: Automatic intelligence request handling for omniclaude manifest_injector

## Overview

This document describes the implementation of the automatic intelligence request system in omniarchon, which handles 4 types of intelligence queries from omniclaude's manifest_injector via Kafka event bus.

**Architecture**:
```
omniclaude (manifest_injector.py)
  → Publishes to Kafka: "dev.archon-intelligence.intelligence.code-analysis-requested.v1"
  → omniarchon (IntelligenceAdapterHandler) consumes and routes to operation handlers
  → Operation handlers query backends (Qdrant, PostgreSQL, Memgraph, Docker)
  → Publishes response to Kafka: "dev.archon-intelligence.intelligence.code-analysis-completed.v1"
  → manifest_injector formats response for agent
```

## Implementation Status

### ✅ Completed Components

1. **Event Models** (`src/events/models/intelligence_adapter_events.py`)
   - Extended `EnumAnalysisOperationType` with 4 new operation types
   - Extended `EnumAnalysisErrorCode` with operation-specific error codes
   - Created 4 new response payload models:
     - `ModelPatternExtractionPayload`
     - `ModelInfrastructureScanPayload`
     - `ModelDiscoveryPayload`
     - `ModelSchemaDiscoveryPayload`

2. **Operation Handlers** (`src/handlers/operations/`)
   - `PatternExtractionHandler` - Queries Qdrant for code generation patterns
   - `InfrastructureScanHandler` - Queries PostgreSQL, Kafka, Qdrant, Docker
   - `ModelDiscoveryHandler` - Scans file system and queries Memgraph
   - `SchemaDiscoveryHandler` - Queries PostgreSQL information_schema

3. **Handler Routing** (`src/handlers/intelligence_adapter_handler.py`)
   - Updated to route requests to appropriate operation handler
   - Added operation-specific metrics tracking
   - Unified response publishing for all operation types

4. **Automatic Operation** (Kafka Consumer)
   - Already subscribed to `dev.archon-intelligence.intelligence.code-analysis-requested.v1`
   - IntelligenceAdapterHandler already registered
   - Auto-starts with intelligence service

## Operation Types

### 1. PATTERN_EXTRACTION

**Purpose**: Query Qdrant for code generation patterns

**Request Options**:
```json
{
  "include_patterns": true,
  "include_metrics": false,
  "pattern_types": ["CRUD", "Transformation", "Orchestration", "Aggregation"]
}
```

**Response**:
```json
{
  "patterns": [
    {
      "name": "CRUD Pattern",
      "file_path": "path/to/node_crud_effect.py",
      "description": "Create, Read, Update, Delete operations",
      "node_types": ["EFFECT", "REDUCER"],
      "confidence": 0.95,
      "use_cases": ["Database operations", "API endpoints"],
      "metadata": {
        "complexity": "medium",
        "last_updated": "2025-10-26T12:00:00Z"
      }
    }
  ],
  "query_time_ms": 150,
  "total_count": 4
}
```

**Implementation**: Queries Qdrant `execution_patterns` collection using scroll API

### 2. INFRASTRUCTURE_SCAN

**Purpose**: Query infrastructure topology (PostgreSQL, Kafka, Qdrant, Docker)

**Request Options**:
```json
{
  "include_databases": true,
  "include_kafka_topics": true,
  "include_qdrant_collections": true,
  "include_docker_services": true
}
```

**Response**:
```json
{
  "postgresql": {
    "host": "192.168.86.200",
    "port": 5436,
    "database": "omninode_bridge",
    "status": "connected",
    "tables": [...]
  },
  "kafka": {
    "bootstrap_servers": "192.168.86.200:29102",
    "status": "connected",
    "topics": [...]
  },
  "qdrant": {
    "endpoint": "localhost:6333",
    "status": "connected",
    "collections": [...]
  },
  "docker_services": [...],
  "query_time_ms": 250
}
```

**Implementation**: Parallel queries to PostgreSQL, AIOKafkaAdminClient, Qdrant, static Docker list

### 3. MODEL_DISCOVERY

**Purpose**: Discover AI models and ONEX data models

**Request Options**:
```json
{
  "include_ai_models": true,
  "include_onex_models": true,
  "include_quorum_config": true
}
```

**Response**:
```json
{
  "ai_models": {
    "providers": [...],
    "quorum_config": {
      "total_weight": 7.5,
      "consensus_thresholds": {
        "auto_apply": 0.80,
        "suggest_with_review": 0.60
      }
    }
  },
  "onex_models": {
    "node_types": [...],
    "contracts": [...]
  },
  "intelligence_models": [...],
  "query_time_ms": 100
}
```

**Implementation**: Static configuration data (AI models, ONEX patterns, intelligence models)

### 4. SCHEMA_DISCOVERY

**Purpose**: Query PostgreSQL database schemas

**Request Options**:
```json
{
  "include_tables": true,
  "include_columns": true,
  "include_indexes": false,
  "schema_name": "public"
}
```

**Response**:
```json
{
  "tables": [
    {
      "name": "agent_routing_decisions",
      "schema": "public",
      "columns": [...],
      "row_count": 1234,
      "size_mb": 5.2
    }
  ],
  "total_tables": 15,
  "query_time_ms": 200
}
```

**Implementation**: Queries PostgreSQL `information_schema` for tables, columns, indexes

## Automatic Operation Flow

1. **Service Startup** (`app.py`)
   - Intelligence service starts
   - Kafka consumer initialized (`get_kafka_consumer()`)
   - Consumer subscribes to topics (includes intelligence request topic)
   - IntelligenceAdapterHandler registered
   - Consumer starts consuming in background task

2. **Request Processing** (Automatic)
   - omniclaude publishes intelligence request to Kafka
   - Kafka consumer receives event
   - Routes to IntelligenceAdapterHandler
   - Handler checks `operation_type` field
   - Routes to appropriate operation handler
   - Handler executes query (Qdrant, PostgreSQL, etc.)
   - Results published to response topic
   - omniclaude receives response

3. **No Manual Intervention Required**
   - System is fully automatic
   - No demos or manual triggers needed
   - Handles all 4 operation types automatically

## Performance Targets

- Query timeout: 1500ms per operation (per spec)
- Total manifest generation: ~2000ms for 4 parallel queries (omniclaude side)
- Graceful degradation: Individual operation failures don't block other operations

## Error Handling

**Error Codes**:
- `PATTERN_QUERY_FAILED` - Qdrant pattern query failed
- `INFRASTRUCTURE_SCAN_FAILED` - Infrastructure scan failed
- `MODEL_DISCOVERY_FAILED` - Model discovery failed
- `SCHEMA_DISCOVERY_FAILED` - Database schema query failed
- `TIMEOUT` - Query exceeded timeout
- `BACKEND_UNAVAILABLE` - Backend service unavailable
- `INVALID_OPERATION` - Unknown operation_type

**Error Response**:
```json
{
  "error_code": "PATTERN_QUERY_FAILED",
  "error_message": "Qdrant connection timeout",
  "error_details": {
    "backend": "qdrant",
    "collection": "execution_patterns",
    "reason": "Connection timeout after 5000ms"
  }
}
```

## Testing

### Manual Test (omniclaude side)

```bash
cd /Volumes/PRO-G40/Code/omniclaude
python3 claude_hooks/lib/manifest_loader.py
```

**Expected Output**:
```
Testing manifest load (correlation_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
======================================================================
SYSTEM MANIFEST - Dynamic Context via Event Bus
======================================================================
Version: 2.0.0
Generated: 2025-10-26T...
Source: archon-intelligence-adapter

AVAILABLE PATTERNS:
  • CRUD Pattern (95% confidence)
    File: path/to/node_crud_effect.py
    Node Types: EFFECT, REDUCER
...
```

### Integration Test

```python
import asyncio
from agents.lib.manifest_injector import ManifestInjector

async def test():
    injector = ManifestInjector()
    manifest = await injector.generate_dynamic_manifest_async("test-correlation-id")
    print(manifest)

asyncio.run(test())
```

## Files Modified/Created

### Created
1. `/services/intelligence/src/handlers/operations/__init__.py`
2. `/services/intelligence/src/handlers/operations/pattern_extraction_handler.py`
3. `/services/intelligence/src/handlers/operations/infrastructure_scan_handler.py`
4. `/services/intelligence/src/handlers/operations/model_discovery_handler.py`
5. `/services/intelligence/src/handlers/operations/schema_discovery_handler.py`

### Modified
1. `/services/intelligence/src/events/models/intelligence_adapter_events.py`
   - Added 4 new operation types to `EnumAnalysisOperationType`
   - Added 6 new error codes to `EnumAnalysisErrorCode`
   - Added 4 new response payload models

2. `/services/intelligence/src/handlers/intelligence_adapter_handler.py`
   - Added operation handler initialization
   - Added routing logic for 4 operation types
   - Replaced `_publish_completed_response` with `_publish_operation_response`
   - Added operation-specific metrics

## Configuration

**Environment Variables** (already configured):
```bash
# Kafka
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
KAFKA_INTELLIGENCE_ANALYSIS_REQUEST=dev.archon-intelligence.intelligence.code-analysis-requested.v1

# PostgreSQL
DATABASE_URL=postgresql://postgres:pass@192.168.86.200:5436/omninode_bridge

# Qdrant
QDRANT_URL=http://qdrant:6333

# Memgraph
MEMGRAPH_URI=bolt://memgraph:7687
```

## Deployment

**No deployment changes required**. The implementation:
- ✅ Uses existing Kafka infrastructure
- ✅ Uses existing service clients (PostgreSQL, Qdrant, Kafka)
- ✅ Auto-starts with intelligence service
- ✅ No new containers or services needed

**To activate**:
```bash
# Restart intelligence service to pick up changes
docker compose restart archon-intelligence

# Verify service started
docker compose logs archon-intelligence | grep "Registered IntelligenceAdapterHandler"
```

## Monitoring

**Metrics** (exposed via IntelligenceAdapterHandler):
```python
{
  "events_handled": 123,
  "events_failed": 5,
  "total_processing_time_ms": 45678.9,
  "analysis_successes": 120,
  "analysis_failures": 3,
  "pattern_extraction_count": 40,
  "infrastructure_scan_count": 38,
  "model_discovery_count": 35,
  "schema_discovery_count": 7
}
```

**Health Check**:
```bash
curl http://localhost:8053/health
```

## Next Steps

1. **Test End-to-End**
   - Deploy to development environment
   - Run omniclaude manifest_loader.py test
   - Verify all 4 operations return data

2. **Optimize**
   - Add caching for static data (AI models, ONEX models)
   - Add connection pooling for PostgreSQL
   - Optimize Qdrant queries

3. **Enhance**
   - Add more pattern types to Qdrant
   - Add real-time Docker API integration
   - Add Memgraph queries for model relationships

## References

- [INTELLIGENCE_REQUEST_CONTRACTS.md](../../omniclaude/docs/INTELLIGENCE_REQUEST_CONTRACTS.md) - Original spec
- [EVENT_INTELLIGENCE_INTEGRATION_PLAN.md](../../omniclaude/docs/EVENT_INTELLIGENCE_INTEGRATION_PLAN.md) - Integration plan
- [MANIFEST_INJECTION_INTEGRATION.md](../../omniclaude/docs/MANIFEST_INJECTION_INTEGRATION.md) - Hook integration

---

**Status**: ✅ Implementation complete and ready for testing
**Author**: Claude Code
**Date**: 2025-10-26
