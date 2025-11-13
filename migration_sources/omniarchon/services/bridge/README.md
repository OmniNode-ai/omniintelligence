# Archon Bridge Service

**Version**: 1.0.0
**Status**: Production
**Port**: 8054
**Architecture**: Bidirectional Sync Service

PostgreSQL-Memgraph bridge service for Archon. Provides bidirectional synchronization between Supabase PostgreSQL and Memgraph knowledge graph, mapping relational data to graph entities and relationships.

## Overview

The Bridge Service acts as the synchronization layer between:
- **Supabase PostgreSQL**: Relational data storage (documents, entities, metadata)
- **Memgraph Knowledge Graph**: Graph-based relationships and entity connections
- **Intelligence Service**: AI-powered entity extraction and metadata enrichment

### Key Features

- ✅ **Bidirectional Sync**: Keeps PostgreSQL and Memgraph in sync
- ✅ **Entity Mapping**: Automatic conversion between relational and graph models
- ✅ **Real-time Updates**: Document change webhooks trigger immediate sync
- ✅ **Intelligence Integration**: AI-powered metadata generation via OmniNode Bridge
- ✅ **Health Monitoring**: Comprehensive service health checks
- ✅ **Graceful Degradation**: Operates in degraded mode when dependencies unavailable

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              BRIDGE SERVICE (8054)                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Supabase   │  │   Entity     │  │ Memgraph  │ │
│  │ Connector   │→→│   Mapper     │→→│ Connector │ │
│  └─────────────┘  └──────────────┘  └───────────┘ │
│         ↓               ↓                  ↓       │
│  ┌─────────────────────────────────────────────┐  │
│  │     BidirectionalSyncService                │  │
│  │  - Full sync, incremental sync              │  │
│  │  - Real-time document sync                  │  │
│  │  - Webhook handlers                         │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
           ↓                          ↓
   ┌──────────────┐          ┌─────────────────┐
   │  Supabase    │          │   Memgraph      │
   │  PostgreSQL  │          │ Knowledge Graph │
   └──────────────┘          └─────────────────┘
```

## API Endpoints

### Health & Status

**`GET /health`**
- **Description**: Service health check with dependency status
- **Response**: `BridgeHealthStatus`
- **Returns**:
  - `status`: Overall service status
  - `memgraph_connected`: Memgraph connectivity
  - `intelligence_connected`: Intelligence service connectivity
  - `timestamp`: Current timestamp

### Synchronization

**`POST /sync/full`**
- **Description**: Full synchronization from PostgreSQL to Memgraph
- **Request**: `SyncRequest` (optional filters)
- **Response**: `SyncResponse`
- **Returns**: Entities synced, relationships created, errors

**`POST /sync/incremental`**
- **Description**: Incremental sync of recent changes
- **Request**: `SyncRequest` with `since_timestamp`
- **Response**: `SyncResponse`
- **Use Case**: Regular updates, delta synchronization

**`POST /sync/realtime-document`**
- **Description**: Real-time document sync triggered by webhooks
- **Request**: `RealtimeDocumentSyncRequest`
- **Response**: Sync status and entity details
- **Features**: AI-powered metadata generation via Intelligence service

**`GET /sync/status`**
- **Description**: Current synchronization status
- **Response**: Last sync time, pending items, errors

### Entity Mapping

**`POST /mapping/create`**
- **Description**: Create entity mapping between PostgreSQL and Memgraph
- **Request**: `EntityMappingRequest`
- **Response**: Mapping confirmation and graph entity ID

**`GET /mapping/stats`**
- **Description**: Entity mapping statistics
- **Response**: Total mappings, entity type breakdown, relationship counts

### Intelligence Integration

**`POST /intelligence/extract`**
- **Description**: Extract entities from content via Intelligence service
- **Request**: Content and metadata
- **Response**: Extracted entities and relationships
- **Integration**: Calls Intelligence service `/extract/code` or `/extract/document`

### Webhooks

**`POST /webhook/document-trigger`**
- **Description**: Supabase webhook handler for document changes
- **Request**: Supabase webhook payload
- **Response**: Sync result
- **Triggers**: On `INSERT`, `UPDATE`, `DELETE` in Supabase `documents` table

### Database Operations

**`POST /database/execute`**
- **Description**: Execute raw database queries (Supabase or Memgraph)
- **Request**: `DatabaseQueryRequest`
- **Response**: `DatabaseQueryResponse`
- **Use Case**: Testing, diagnostics, manual data operations

## Configuration

### Environment Variables

**Required**:
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_KEY`: Supabase service role key (full access)
- `MEMGRAPH_URI`: Memgraph connection URI (default: `bolt://memgraph:7687`)
- `INTELLIGENCE_SERVICE_URL`: Intelligence service URL (default: `http://archon-intelligence:8053`)

**Optional**:
- `CORS_ALLOWED_ORIGINS`: Comma-separated CORS origins (default: localhost)
- `ENVIRONMENT`: `development` or `production` (affects CORS validation)
- `BRIDGE_SERVICE_PORT`: Service port (default: 8054)

### Docker Compose

```yaml
archon-bridge:
  build:
    context: ./services/bridge
    dockerfile: Dockerfile
  ports:
    - "8054:8054"
  environment:
    - SUPABASE_URL=${SUPABASE_URL}
    - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
    - MEMGRAPH_URI=bolt://memgraph:7687
    - INTELLIGENCE_SERVICE_URL=http://archon-intelligence:8053
  depends_on:
    - memgraph
    - archon-intelligence
```

## Usage Examples

### Python Client

```python
import httpx

bridge_url = "http://localhost:8054"

# Health check
response = httpx.get(f"{bridge_url}/health")
print(response.json())
# {"status": "healthy", "memgraph_connected": true, "intelligence_connected": true}

# Full synchronization
response = httpx.post(
    f"{bridge_url}/sync/full",
    json={"entity_types": ["document", "code_entity"]}
)
sync_result = response.json()
print(f"Synced {sync_result['entities_synced']} entities")

# Real-time document sync
response = httpx.post(
    f"{bridge_url}/sync/realtime-document",
    json={
        "entity_id": "doc-123",
        "entity_type": "document",
        "action": "insert",
        "metadata": {"title": "API Guide", "document_type": "guide"}
    }
)
```

### cURL

```bash
# Health check
curl http://localhost:8054/health

# Full sync
curl -X POST http://localhost:8054/sync/full \
  -H "Content-Type: application/json" \
  -d '{"entity_types": ["document"]}'

# Get mapping stats
curl http://localhost:8054/mapping/stats
```

## Development

### Running Locally

```bash
# Install dependencies
poetry install

# Set environment variables
export SUPABASE_URL="your-supabase-url"
export SUPABASE_SERVICE_KEY="your-service-key"
export MEMGRAPH_URI="bolt://localhost:7687"

# Run service
poetry run python app.py
```

### Testing

```bash
# Run tests
poetry run pytest tests/ -v

# Test specific functionality
poetry run pytest tests/test_sync.py -v
```

### Degraded Mode

The Bridge service gracefully handles missing dependencies:
- **No Supabase**: Service runs in read-only mode from Memgraph
- **No Memgraph**: Service runs without graph sync (PostgreSQL only)
- **No Intelligence**: Entity extraction disabled, basic sync continues

## Logging

The Bridge service uses comprehensive structured logging:

```python
from bridge_logging.bridge_logger import bridge_logger

# Startup phases
bridge_logger.log_startup_phase("initialization", "start")
bridge_logger.log_startup_phase("supabase_connector", "success")

# Sync operations
bridge_logger.log_sync_operation("full_sync", {"entities": 100})

# Error tracking
bridge_logger.log_error("sync_failed", error_details)
```

## Integration with Other Services

### Intelligence Service
- **Entity Extraction**: POST `/intelligence/extract` → Intelligence `/extract/code`
- **Metadata Generation**: OmniNode Bridge intelligence for document metadata
- **Quality Analysis**: Document quality scoring integration

### Search Service
- **Dependency**: Search service queries Bridge for entity relationships
- **Cache Invalidation**: Bridge triggers search cache refresh on sync

### Frontend
- **Real-time Updates**: WebSocket notifications on document sync
- **Knowledge Graph Visualization**: Memgraph data served via Bridge queries

## Monitoring

### Health Checks

```bash
# Service health
curl http://localhost:8054/health

# Dependency status
curl http://localhost:8054/health | jq '.memgraph_connected, .intelligence_connected'

# Sync status
curl http://localhost:8054/sync/status
```

### Performance Metrics

- **Sync Latency**: Full sync ~2-5s for 1000 entities
- **Incremental Sync**: <500ms for delta changes
- **Real-time Sync**: <300ms per document

## Troubleshooting

### Common Issues

**1. Supabase Connection Failed**
```bash
# Check Supabase URL and key
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_KEY

# Test Supabase connectivity
curl $SUPABASE_URL/rest/v1/ -H "apikey: $SUPABASE_SERVICE_KEY"
```

**2. Memgraph Connection Failed**
```bash
# Check Memgraph is running
docker ps | grep memgraph

# Test Memgraph connection
docker exec memgraph mgconsole --host memgraph --port 7687
```

**3. Sync Failures**
```bash
# Check sync status
curl http://localhost:8054/sync/status

# View logs
docker logs archon-bridge --tail 100
```

## Architecture Details

### Components

**`SupabaseConnector`**
- PostgreSQL client wrapper
- Connection pooling and health checks
- Query execution and transaction management

**`MemgraphConnector`**
- Bolt protocol client for Memgraph
- Cypher query execution
- Graph traversal and entity management

**`EntityMapper`**
- Bidirectional mapping between relational and graph models
- Type conversion (PostgreSQL ↔ Memgraph)
- Relationship inference and creation

**`BidirectionalSyncService`**
- Full sync: PostgreSQL → Memgraph bulk transfer
- Incremental sync: Delta changes only
- Conflict resolution and idempotency

### Data Models

**`BridgeHealthStatus`**: Health check response
**`SyncRequest`**: Sync configuration and filters
**`SyncResponse`**: Sync operation results
**`EntityMappingRequest`**: Entity mapping request
**`RealtimeDocumentSyncRequest`**: Real-time document sync payload
**`DatabaseQueryRequest`**: Raw database query request
**`DatabaseQueryResponse`**: Query execution results

## Related Documentation

- **Intelligence Service**: [services/intelligence/README.md](../intelligence/README.md)
- **Search Service**: [services/search/README.md](../search/README.md)
- **Event Bus Architecture**: [docs/planning/EVENT_BUS_ARCHITECTURE.md](../../docs/planning/EVENT_BUS_ARCHITECTURE.md)
- **Database Schema**: [services/intelligence/database/schema/README.md](../intelligence/database/schema/README.md)

---

**Bridge Service**: Production-ready bidirectional sync for Archon's knowledge graph.
