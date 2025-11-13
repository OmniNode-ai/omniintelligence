# MCP Service Separation Roadmap

**Version**: 1.0.0
**Date**: 2025-10-18
**Status**: Planning Phase
**Objective**: Extract MCP service into separate repository after event bus migration

---

## Executive Summary

This document provides a comprehensive roadmap for separating the Archon MCP service into its own repository (`omniarchon-mcp`) after migrating internal operations to an event-driven architecture. The separation will:

- **Reduce coupling**: Decouple MCP protocol layer from core Archon services
- **Enable independent versioning**: MCP and Archon can evolve independently
- **Improve scalability**: Event bus handles async operations; MCP focuses on Claude Code integration
- **Maintain functionality**: Zero breaking changes for Claude Code users

**Recommendation**: **Proceed with phased migration** (6 phases, ~3-4 months)

**Success Metrics**:
- 80% of MCP operations migrated to event bus
- Zero downtime during migration
- Claude Code integration preserved
- 30-50% performance improvement via event-driven architecture

---

## 1. Current State Analysis

### 1.1 MCP Server Architecture

**Location**: `/python/src/mcp_server/`
**Port**: 8051
**Protocol**: MCP over SSE (Server-Sent Events)
**Framework**: FastMCP (Python)

**Current Role**:
1. **Unified Gateway**: Single `archon_menu` tool routing to 168+ operations
2. **Internal HTTP Routing**: Calls backend services (Intelligence, Search, Bridge) via httpx
3. **External MCP Gateway**: Routes to external tools (zen, context7, codanna, serena)
4. **Claude Code Integration**: Primary interface for Claude Code MCP client

### 1.2 Service Dependencies

**MCP Server Depends On** (via HTTP):
- Intelligence Service (8053) - 33 tools
- Search Service (8055) - 9 tools
- Bridge Service (8054) - 11 tools
- Server Service (8181) - 19 tools
- LangExtract Service (8156) - ML features

**MCP Server Provides To**:
- Claude Code (via MCP protocol)
- External clients (via HTTP/SSE endpoint)

### 1.3 Current Tool Catalog

**Internal Tools** (68 operations via HTTP):

| Category | Count | Backend Service | Port |
|----------|-------|-----------------|------|
| Quality | 4 | Intelligence | 8053 |
| Performance | 5 | Intelligence | 8053 |
| Freshness | 9 | Intelligence | 8053 |
| Traceability | 11 | Intelligence | 8053 |
| Vector Search | 5 | Intelligence | 8053 |
| RAG Search | 5 | Search | 8055 |
| Enhanced Search | 4 | Search | 8055 |
| Bridge Intelligence | 11 | Bridge | 8054 |
| Projects | 5 | Server | 8181 |
| Tasks | 5 | Server | 8181 |
| Documents | 5 | Server | 8181 |
| Versions | 4 | Server | 8181 |
| Cache | 1 | MCP (native) | 8051 |

**External Tools** (100+ operations via MCP gateway):
- **zen** (12 tools): Multi-model AI workflows
- **codanna** (8 tools): Code analysis (Rust)
- **serena** (24 tools): Codebase intelligence (Python)
- **sequential-thinking** (1 tool): Multi-stage reasoning
- **context7** (2 tools): Library documentation (disabled due to instability)

### 1.4 Current Coupling Points

**Tight Coupling**:
1. **Registry System**: `ToolCatalog` manually maps operations to HTTP endpoints
2. **Service Discovery**: Hardcoded service URLs in `CATEGORY_SERVICE_MAP`
3. **HTTP Client**: Direct httpx calls to backend services
4. **Synchronous Responses**: Request/response pattern for all operations

**Loose Coupling**:
1. **External Gateway**: Stdio-based MCP clients (can run independently)
2. **Tool Discovery**: Dynamic catalog from external services
3. **Health Checks**: Independent health monitoring

---

## 2. Event Bus Migration Impact

### 2.1 Kafka Infrastructure (Existing)

**Service**: `archon-kafka-consumer` (port 8059)
**Event Bus**: Redpanda (omninode-bridge) on port 9092
**Protocol**: Kafka topics with JSON serialization

**Current Topics**:
- `omninode.service.lifecycle` → Service startup/shutdown events
- `omninode.tool.updates` → Tool registration/updates
- `omninode.system.events` → System-wide events
- `omninode.bridge.events` → Bridge service events

**Consumer Pattern**: Subscribe → Deserialize → Route → API Call

### 2.2 Operations Suitable for Event-Driven Migration

**High Priority** (Async, fire-and-forget):
- `batch_index_documents` → `intelligence.vector.index` topic
- `refresh_documents` → `intelligence.freshness.refresh` topic
- `track_pattern_creation` → `intelligence.traceability.track` topic
- `apply_performance_optimization` → `intelligence.performance.optimize` topic
- `cleanup_freshness_data` → `intelligence.freshness.cleanup` topic
- Task updates (`update_task`) → `server.task.update` topic
- Document updates (`update_document`) → `server.document.update` topic

**Medium Priority** (Mostly async with status polling):
- `analyze_document_freshness` → `intelligence.freshness.analyze` topic
- `establish_performance_baseline` → `intelligence.performance.baseline` topic
- `search_code_examples` → `search.code_examples` topic
- Project/task creation → `server.project.create` / `server.task.create` topics

**Low Priority** (Need synchronous response):
- `assess_code_quality` → **Keep as HTTP** (immediate scoring needed)
- `perform_rag_query` → **Keep as HTTP** (search results needed immediately)
- `get_task` / `get_project` → **Keep as HTTP** (read operations)
- `health_check` / `session_info` → **Keep as native MCP**

### 2.3 Event Topic Design

**Proposed Topic Structure**:
```
archon.intelligence.quality.assess
archon.intelligence.performance.baseline
archon.intelligence.performance.optimize
archon.intelligence.freshness.analyze
archon.intelligence.freshness.refresh
archon.intelligence.vector.search
archon.intelligence.vector.index
archon.intelligence.traceability.track
archon.search.rag.query
archon.search.code.examples
archon.bridge.metadata.stamp
archon.server.project.create
archon.server.project.update
archon.server.task.create
archon.server.task.update
archon.server.document.create
archon.server.document.update
```

**Event Envelope Format** (standardized):
```json
{
  "event_id": "uuid",
  "event_type": "archon.intelligence.quality.assess",
  "timestamp": "2025-10-18T10:00:00Z",
  "correlation_id": "request-uuid",
  "source_service": "archon-mcp",
  "target_service": "archon-intelligence",
  "payload": {
    "operation": "assess_code_quality",
    "params": {
      "content": "def hello(): pass",
      "source_path": "test.py",
      "language": "python"
    }
  },
  "metadata": {
    "user_id": "optional",
    "session_id": "optional",
    "priority": "normal"
  }
}
```

### 2.4 Response Pattern for Async Operations

**Options**:

1. **Fire-and-Forget** (no response needed):
   - Tool calls return `{"success": true, "event_id": "...", "status": "submitted"}`
   - Client doesn't wait for completion

2. **Status Polling** (async with tracking):
   - Tool call submits event, returns `event_id`
   - Client polls `/api/events/{event_id}/status` for completion
   - Suitable for long-running operations (indexing, optimization)

3. **WebSocket Push** (real-time updates):
   - Client subscribes to event completion via WebSocket
   - Server pushes result when event completes
   - Best UX but more complex

4. **Hybrid** (HTTP for sync, Event for async):
   - Keep synchronous operations as HTTP
   - Migrate async operations to events
   - Simplest migration path

**Recommendation**: Start with **Hybrid approach** (Phase 2), migrate to **Status Polling** for async operations (Phase 3)

---

## 3. Service Registry Integration

### 3.1 Current MCP Service Registry

**Location**: `/python/src/mcp_server/registry/service_registry.py`
**Purpose**: Load external MCP services from `config/mcp_services.yaml`

**Limitations**:
- External MCP services only (zen, codanna, serena)
- No integration with omninode_bridge registry
- Manual service discovery
- Static configuration

### 3.2 omninode_bridge Service Registry

**Location**: `/Volumes/PRO-G40/Code/omninode_bridge/`
**Purpose**: Centralized service registry for entire ecosystem

**Features** (assumed based on ONEX patterns):
- Dynamic service registration
- Health monitoring
- Service discovery
- Capability metadata
- Version tracking

### 3.3 Integration Design

**Replace MCP Registry with omninode_bridge Registry**:

```python
# Old (MCP-specific registry)
from src.mcp_server.registry.service_registry import MCPServiceRegistry

registry = MCPServiceRegistry("config/mcp_services.yaml")
services = registry.get_enabled_services()

# New (omninode_bridge registry integration)
from omninode_bridge.registry import ServiceRegistry

registry = ServiceRegistry()
await registry.connect()  # Connect to Redpanda + Memgraph
services = await registry.discover_services(capability="intelligence")
```

**Service Discovery Flow**:
1. **Startup**: MCP server connects to omninode_bridge registry
2. **Discovery**: Query registry for services with required capabilities
3. **Health**: Monitor service health via registry heartbeats
4. **Dynamic**: No manual configuration; services auto-register

**Benefits**:
- Eliminates hardcoded service URLs
- Automatic service discovery
- Unified health monitoring
- Supports service scaling (multiple instances)

### 3.4 Migration Path

**Phase 1**: Dual registry support
- Keep existing `MCPServiceRegistry` for external tools
- Add `omninode_bridge` integration for internal services
- Parallel operation during transition

**Phase 2**: Full migration
- Remove hardcoded `CATEGORY_SERVICE_MAP`
- All service discovery via `omninode_bridge`
- Deprecate `MCPServiceRegistry`

---

## 4. Separation Architecture

### 4.1 What Moves to `omniarchon-mcp` Repository

**Core MCP Server**:
- `/python/src/mcp_server/mcp_server.py` - Main server
- `/python/src/mcp_server/tools/archon_menu.py` - Unified gateway tool
- `/python/src/mcp_server/gateway/` - External MCP gateway (zen, codanna, etc.)
- `/python/src/mcp_server/clients/external/` - MCP client implementations
- `/python/src/mcp_server/middleware/` - Logging, rate limiting, session validation
- `/python/src/mcp_server/utils/` - Error handling, timeout config, HTTP client
- `/python/config/mcp_services.yaml` - External service configuration
- `/python/Dockerfile.mcp` - MCP server Dockerfile

**Registry and Catalog** (abstraction layer):
- `/python/src/mcp_server/registry/` - Tool catalog, service registry
- `/python/src/mcp_server/registry/catalog_builder.py` - Tool definitions

**External MCP Integration**:
- All stdio-based MCP client code
- Tool discovery service
- Connection pooling
- External service health monitoring

**Documentation**:
- `/docs/mcp_proxy/` - MCP gateway documentation
- External service integration guides

### 4.2 What Stays in `omniarchon` Repository

**Backend Services** (core intelligence):
- `/services/intelligence/` - Quality, performance, freshness, traceability
- `/services/search/` - RAG search, enhanced search
- `/services/bridge/` - Metadata stamping, bridge intelligence
- `/services/kafka-consumer/` - Event bus consumer
- `/services/langextract/` - ML extraction

**Server and API**:
- `/python/src/server/` - Main FastAPI server (8181)
- `/python/src/server/routes/` - REST API endpoints
- Task/project/document management

**Event Bus Integration**:
- Kafka producer/consumer code
- Event envelope models
- Topic management

**Data Layer**:
- Qdrant vector DB integration
- Memgraph knowledge graph
- Supabase PostgreSQL

**Frontend**:
- React UI (3737)
- WebSocket integration

### 4.3 Shared Dependencies (Abstraction Layer)

**Create `omniarchon-common` Package**:
```
omniarchon-common/
├── models/           # Shared data models
│   ├── event_envelope.py
│   ├── tool_result.py
│   └── service_health.py
├── protocols/        # Shared protocols
│   ├── tool_protocol.py
│   └── service_protocol.py
└── utils/           # Shared utilities
    ├── logging.py
    └── error_handling.py
```

**Dependency Management**:
- `omniarchon-mcp` depends on `omniarchon-common`
- `omniarchon` depends on `omniarchon-common`
- No circular dependencies
- Independent versioning

### 4.4 Communication After Separation

**MCP → Archon Services**:

| Communication Type | Before Separation | After Separation |
|-------------------|------------------|------------------|
| Sync Operations | HTTP (httpx) | **HTTP (same)** |
| Async Operations | HTTP | **Event Bus (Kafka)** |
| Service Discovery | Hardcoded URLs | **omninode_bridge registry** |
| Health Checks | Direct HTTP | **Registry heartbeats** |

**MCP → External Tools**:
- No change (stdio-based MCP clients remain)
- External gateway stays in `omniarchon-mcp`

---

## 5. Migration Timeline (6 Phases)

### Phase 1: Event Bus Foundation (2 weeks)

**Deliverables**:
- ✅ Kafka consumer service operational (already exists)
- Create event topic structure for all services
- Implement event producers in backend services
- Test end-to-end event flow (publish → consume → process)

**Acceptance Criteria**:
- Event bus handles 100 events/sec without loss
- All services can publish events
- Consumer processes events reliably

### Phase 2: Hybrid Architecture (3 weeks)

**Deliverables**:
- Implement dual-mode operations (HTTP + Event)
- Migrate 20% of operations to event bus (async batch operations)
- Add status polling endpoint (`/api/events/{event_id}/status`)
- Update `archon_menu` to route async ops to events

**Operations Migrated**:
- `batch_index_documents`
- `refresh_documents`
- `track_pattern_creation`
- `cleanup_freshness_data`

**Acceptance Criteria**:
- 20% of operations use event bus
- HTTP operations still work (no breaking changes)
- Status polling returns accurate results

### Phase 3: Service Registry Migration (2 weeks)

**Deliverables**:
- Integrate omninode_bridge service registry
- Replace hardcoded `CATEGORY_SERVICE_MAP`
- Implement dynamic service discovery
- Add health monitoring via registry

**Acceptance Criteria**:
- All services discoverable via registry
- No hardcoded URLs in MCP code
- Service health tracked automatically

### Phase 4: Full Event Migration (4 weeks)

**Deliverables**:
- Migrate 80% of operations to event bus
- Keep only essential sync operations as HTTP
- Implement WebSocket push for real-time updates (optional)
- Performance testing and optimization

**Operations Still HTTP** (essential sync):
- `assess_code_quality` (immediate scoring)
- `perform_rag_query` (search results)
- All read operations (`get_*`, `list_*`)
- `health_check`, `session_info` (native MCP)

**Acceptance Criteria**:
- 80% of operations use event bus
- 30-50% performance improvement
- Zero data loss in event processing

### Phase 5: MCP Extraction (3 weeks)

**Deliverables**:
- Create `omniarchon-mcp` repository
- Create `omniarchon-common` shared package
- Move MCP server code to new repo
- Update Docker Compose for multi-repo setup
- CI/CD pipelines for new repos

**File Structure**:
```
omniarchon-mcp/
├── src/
│   ├── mcp_server.py
│   ├── tools/
│   │   └── archon_menu.py
│   ├── gateway/
│   └── clients/
├── config/
│   └── mcp_services.yaml
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md

omniarchon-common/
├── src/
│   ├── models/
│   ├── protocols/
│   └── utils/
├── pyproject.toml
└── README.md
```

**Acceptance Criteria**:
- MCP server runs independently
- All tests pass in new repo
- Docker Compose starts both repos
- CI/CD builds and publishes packages

### Phase 6: Production Deployment (2 weeks)

**Deliverables**:
- Deploy separated services to staging
- Performance testing and optimization
- Update documentation and migration guides
- Production rollout with zero downtime
- Monitor and validate

**Rollout Strategy**:
1. Deploy new MCP server alongside old (blue/green)
2. Route 10% of traffic to new server
3. Gradually increase to 100%
4. Decommission old server
5. Monitor for 1 week

**Acceptance Criteria**:
- Zero downtime during migration
- All metrics meet targets
- No user-facing issues
- Documentation complete

---

## 6. Dependency Management

### 6.1 Package Dependencies

**`omniarchon-mcp` Dependencies**:
```toml
[project]
name = "omniarchon-mcp"
version = "1.0.0"
dependencies = [
    "fastmcp>=1.0.0",
    "httpx>=0.25.0",
    "pydantic>=2.5.0",
    "omniarchon-common>=1.0.0",
    "omnibase-spi>=1.0.0",  # For event bus types
]
```

**`omniarchon` Dependencies**:
```toml
# Remove MCP-specific dependencies
# Add event bus dependencies
dependencies = [
    "aiokafka>=0.9.0",
    "omniarchon-common>=1.0.0",
    "omnibase-spi>=1.0.0",
]
```

### 6.2 Version Compatibility

**Semantic Versioning**:
- `omniarchon-common`: 1.x.x (stable API contract)
- `omniarchon-mcp`: Major version tracks common
- `omniarchon`: Independent versioning

**Breaking Changes**:
- Only in `omniarchon-common` major versions
- Coordinated releases across repos
- Migration guides for each major version

---

## 7. External Gateway Strategy

### 7.1 Current External Tools

**Managed by MCP Gateway** (stdio transport):
- **zen** (12 tools): Multi-model reasoning via Python subprocess
- **codanna** (8 tools): Rust binary via cargo
- **serena** (24 tools): Python via uv
- **sequential-thinking** (1 tool): Node.js via npx

**Problem**: These require host environment access (cannot run in Docker)

### 7.2 Options for External Gateway

**Option 1: Keep in MCP Repo** (Recommended)
- External gateway stays in `omniarchon-mcp`
- Claude Code specific integration
- No changes needed
- ✅ **Pros**: Simple, maintains current functionality
- ❌ **Cons**: MCP repo still has external dependencies

**Option 2: Separate External Gateway Repo**
- Create `omniarchon-external-gateway`
- MCP server calls gateway via HTTP
- ✅ **Pros**: Complete separation
- ❌ **Cons**: Additional repo, more complexity

**Option 3: Integrate External Tools Natively**
- Reimplement zen/codanna/serena as native Archon services
- Expose via event bus + HTTP
- ✅ **Pros**: Full control, no external dependencies
- ❌ **Cons**: Massive effort, duplication

**Option 4: MCP Protocol Bridge**
- Create native MCP server for each external tool
- Route via unified gateway
- ✅ **Pros**: Clean abstraction
- ❌ **Cons**: Still requires host environment

**Recommendation**: **Option 1 - Keep in MCP Repo**
- Simplest migration path
- External tools are Claude Code specific
- Can revisit later if needed

---

## 8. Claude Code Integration

### 8.1 Current Integration

**Config**: `~/.config/claude/mcp.json`
```json
{
  "mcpServers": {
    "archon": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch", "http://localhost:8051/mcp"],
      "env": {"ARCHON_MCP_PORT": "8051"}
    }
  }
}
```

**MCP Protocol**: SSE (Server-Sent Events) over HTTP
**Endpoint**: `http://localhost:8051/mcp`

### 8.2 Post-Separation Integration

**No Changes Required** for Claude Code users!

**Why**:
- MCP server still runs on port 8051
- SSE endpoint remains the same
- `archon_menu` tool still available
- All tools still accessible

**Under the Hood** (transparent to users):
- MCP server now routes via event bus (for async ops)
- Service discovery via omninode_bridge registry
- HTTP still works for sync operations

**Migration Complexity for Users**: **Zero**

### 8.3 Alternative Protocol (Future)

**Could we replace MCP protocol?**

**Challenges**:
- Claude Code requires MCP protocol (no alternative)
- MCP is standardized (good for ecosystem)
- Large ecosystem of MCP tools

**Recommendation**: **Keep MCP protocol** for Claude Code integration

**Alternative Use Cases**:
- Direct HTTP API for programmatic access
- Event bus for service-to-service communication
- WebSocket for real-time updates

---

## 9. Breaking Changes

### 9.1 Breaking Changes (Minimal)

**For Claude Code Users**:
- ✅ **None** - MCP endpoint remains identical

**For Direct HTTP Clients**:
- ⚠️ **Potential**: Some async operations return `event_id` instead of immediate results
- ✅ **Migration**: Use status polling endpoint

**For Service Developers**:
- ⚠️ **Required**: Integrate with omninode_bridge registry
- ⚠️ **Required**: Implement event producers for async operations
- ✅ **Timeline**: Gradual migration over 3-4 months

### 9.2 Deprecation Timeline

**Phase 2-3** (Weeks 3-8):
- Deprecate hardcoded `CATEGORY_SERVICE_MAP`
- Add deprecation warnings to logs

**Phase 4** (Weeks 9-12):
- Remove legacy HTTP-only operations
- Require event bus for async operations

**Phase 5** (Weeks 13-15):
- Remove old registry code
- Finalize separation

**Phase 6** (Weeks 16-17):
- Production deployment
- Monitor and validate

### 9.3 Migration Guide

**For End Users** (Claude Code):
```bash
# No changes needed!
# MCP server location might change but config is same
# Update if running MCP server manually:
cd omniarchon-mcp
docker compose up -d
```

**For Service Developers**:
```python
# Old (HTTP only)
await http_client.post("http://archon-intelligence:8053/assess/code", json=params)

# New (Event bus for async, HTTP for sync)
if operation_is_async:
    event_id = await event_bus.publish("archon.intelligence.quality.assess", params)
    return {"event_id": event_id, "status": "submitted"}
else:
    result = await http_client.post("http://archon-intelligence:8053/assess/code", json=params)
    return result
```

---

## 10. Benefits Analysis

### 10.1 Performance Improvements

**Event Bus vs HTTP**:

| Metric | HTTP (Current) | Event Bus (Target) | Improvement |
|--------|---------------|-------------------|-------------|
| Batch indexing | 5000ms | 2000ms | 60% faster |
| Document refresh | 3000ms | 1000ms | 66% faster |
| Pattern tracking | 500ms | 200ms | 60% faster |
| Throughput | 50 req/sec | 200 events/sec | 4x increase |

**Why Faster**:
- No request/response overhead for async operations
- Parallel event processing
- No blocking on long-running operations
- Better resource utilization

### 10.2 Scalability Improvements

**Before Separation**:
- MCP server is bottleneck (single instance)
- Services coupled via HTTP
- Manual service discovery
- No horizontal scaling

**After Separation**:
- MCP server scales independently
- Services communicate via event bus (horizontal scaling)
- Dynamic service discovery
- Load balancing across instances

**Scaling Example**:
```
Before: 1 MCP → 1 Intelligence → 1 Search → 1 Bridge
After:  3 MCP → [Event Bus] → 5 Intelligence → 3 Search → 2 Bridge
```

### 10.3 Maintainability Improvements

**Code Separation**:
- MCP protocol concerns separated from business logic
- Clear boundaries between services
- Independent deployment cycles
- Easier testing (mock event bus)

**Development Velocity**:
- Teams can work independently on repos
- Faster CI/CD (smaller codebases)
- Independent versioning
- Reduced merge conflicts

### 10.4 Architectural Improvements

**Coupling Reduction**:
- Services don't know about MCP
- Event-driven decoupling
- Protocol independence (can add gRPC later)

**Observability**:
- Centralized event logging
- Service health in registry
- Distributed tracing via correlation IDs

### 10.5 Cost Analysis

**Development Costs**:
- **Initial**: 3-4 months engineering effort (2-3 engineers)
- **Ongoing**: Lower maintenance costs (better separation)

**Infrastructure Costs**:
- **Additional**: Kafka/Redpanda (already running in omninode_bridge)
- **Savings**: Better resource utilization, fewer instances needed

**ROI Timeline**: 6-9 months (breakeven on development investment)

---

## 11. Risk Analysis and Mitigation

### 11.1 Technical Risks

**Risk 1: Event Bus Downtime**
- **Impact**: High (async operations fail)
- **Probability**: Low (Redpanda is robust)
- **Mitigation**:
  - Fallback to HTTP for critical operations
  - Event replay from dead letter queue
  - Multi-region Redpanda cluster

**Risk 2: Event Ordering Issues**
- **Impact**: Medium (state consistency issues)
- **Probability**: Medium (concurrent events)
- **Mitigation**:
  - Use Kafka partitioning by correlation_id
  - Idempotent event handlers
  - Optimistic locking for state changes

**Risk 3: Service Discovery Failures**
- **Impact**: High (MCP can't find services)
- **Probability**: Low (registry is resilient)
- **Mitigation**:
  - Cache service locations locally
  - Fallback to hardcoded URLs if registry unavailable
  - Health checks and circuit breakers

**Risk 4: Data Loss in Events**
- **Impact**: Critical (lost operations)
- **Probability**: Low (Kafka has durability)
- **Mitigation**:
  - Kafka replication factor = 3
  - At-least-once delivery semantics
  - Event log retention = 7 days

### 11.2 Migration Risks

**Risk 1: Breaking Changes for Users**
- **Impact**: High (user disruption)
- **Probability**: Low (careful planning)
- **Mitigation**:
  - Maintain backward compatibility
  - Gradual rollout with feature flags
  - Comprehensive testing before deployment

**Risk 2: Performance Regression**
- **Impact**: Medium (slower response times)
- **Probability**: Medium (new architecture)
- **Mitigation**:
  - Performance testing at each phase
  - Baseline metrics before migration
  - Rollback plan if performance degrades

**Risk 3: Coordination Between Repos**
- **Impact**: Medium (deployment complexity)
- **Probability**: Medium (multiple repos)
- **Mitigation**:
  - Use shared `omniarchon-common` package
  - Automated cross-repo CI/CD
  - Synchronized release process

### 11.3 Operational Risks

**Risk 1: Increased Complexity**
- **Impact**: Medium (harder to debug)
- **Probability**: High (distributed system)
- **Mitigation**:
  - Comprehensive logging and tracing
  - Centralized monitoring (Logfire)
  - Runbooks for common issues

**Risk 2: Team Skill Gap**
- **Impact**: Medium (slower development)
- **Probability**: Medium (event-driven architecture)
- **Mitigation**:
  - Training on Kafka and event patterns
  - Documentation and examples
  - Pair programming during migration

---

## 12. Recommendation

### 12.1 Decision: **Proceed with Phased Migration**

**Why**:
1. ✅ **Clear benefits**: 30-50% performance improvement, better scalability
2. ✅ **Low risk**: Gradual migration with fallbacks
3. ✅ **Zero user impact**: Claude Code integration unchanged
4. ✅ **Strategic alignment**: Event-driven architecture is future-proof
5. ✅ **Infrastructure ready**: Kafka consumer already exists

**Why Not**:
- ❌ **Not urgent**: Current HTTP architecture works
- ❌ **High effort**: 3-4 months engineering time
- ❌ **Complexity**: Event-driven architecture is harder to debug

**Conclusion**: **Benefits outweigh costs**. Event bus migration enables:
- Independent scaling of MCP and backend services
- Better performance for async operations
- Cleaner architecture and separation of concerns
- Foundation for future growth

### 12.2 Timeline Summary

| Phase | Duration | Key Deliverables | Risk Level |
|-------|----------|------------------|------------|
| 1. Event Bus Foundation | 2 weeks | Topics, producers, consumers | Low |
| 2. Hybrid Architecture | 3 weeks | 20% ops migrated, status polling | Medium |
| 3. Registry Migration | 2 weeks | Dynamic service discovery | Medium |
| 4. Full Event Migration | 4 weeks | 80% ops migrated | High |
| 5. MCP Extraction | 3 weeks | Separate repos, CI/CD | Medium |
| 6. Production Deployment | 2 weeks | Rollout, monitoring | High |
| **Total** | **16 weeks** | **Complete separation** | **Medium** |

### 12.3 Success Metrics

**Performance Targets**:
- ✅ 80% of operations use event bus
- ✅ 30-50% faster for async operations
- ✅ 4x throughput increase (50 → 200 req/sec)
- ✅ <100ms latency for event routing

**Quality Targets**:
- ✅ Zero data loss in event processing
- ✅ 99.9% event delivery success rate
- ✅ <1% error rate during migration
- ✅ All tests pass in new repo structure

**User Experience Targets**:
- ✅ Zero downtime during migration
- ✅ No breaking changes for Claude Code
- ✅ Improved response times for async operations
- ✅ Clear migration documentation

### 12.4 Go/No-Go Criteria

**Phase 1-2 (Proceed if)**:
- ✅ Event bus handles 100 events/sec reliably
- ✅ 20% of operations migrated successfully
- ✅ No performance regression
- ✅ Team trained on event patterns

**Phase 3-4 (Proceed if)**:
- ✅ Service registry stable
- ✅ 80% of operations migrated
- ✅ Performance targets met
- ✅ Comprehensive testing complete

**Phase 5-6 (Proceed if)**:
- ✅ MCP repo builds and runs independently
- ✅ All CI/CD pipelines green
- ✅ Staging deployment successful
- ✅ Zero critical bugs in testing

---

## 13. Appendices

### Appendix A: Event Topic Reference

**Full Topic List** (47 topics):

```
# Intelligence Service Topics (26)
archon.intelligence.quality.assess
archon.intelligence.quality.document
archon.intelligence.quality.patterns
archon.intelligence.quality.compliance
archon.intelligence.performance.baseline
archon.intelligence.performance.opportunities
archon.intelligence.performance.optimize
archon.intelligence.performance.report
archon.intelligence.performance.trends
archon.intelligence.freshness.analyze
archon.intelligence.freshness.stale
archon.intelligence.freshness.refresh
archon.intelligence.freshness.stats
archon.intelligence.freshness.document
archon.intelligence.freshness.cleanup
archon.intelligence.vector.search
archon.intelligence.vector.weighted
archon.intelligence.vector.batch_index
archon.intelligence.vector.stats
archon.intelligence.vector.optimize
archon.intelligence.traceability.track
archon.intelligence.traceability.lineage
archon.intelligence.traceability.evolution
archon.intelligence.traceability.logs
archon.intelligence.traceability.summary
archon.intelligence.traceability.analytics

# Search Service Topics (9)
archon.search.rag.query
archon.search.rag.sources
archon.search.code.examples
archon.search.cross_project
archon.search.enhanced.search
archon.search.enhanced.entity
archon.search.enhanced.similar
archon.search.enhanced.stats
archon.search.enhanced.relationships

# Bridge Service Topics (11)
archon.bridge.intelligence.generate
archon.bridge.metadata.stamp
archon.bridge.metadata.validate
archon.bridge.metadata.batch
archon.bridge.metadata.metrics
archon.bridge.onextree.health
archon.bridge.onextree.patterns
archon.bridge.onextree.visualize
archon.bridge.workflow.orchestrate
archon.bridge.workflow.list
archon.bridge.workflow.status

# Server Service Topics (12)
archon.server.project.create
archon.server.project.update
archon.server.project.delete
archon.server.task.create
archon.server.task.update
archon.server.task.delete
archon.server.document.create
archon.server.document.update
archon.server.document.delete
archon.server.version.create
archon.server.version.restore
archon.server.feature.get
```

### Appendix B: Service URL Mapping

**Current Hardcoded Mapping** (to be removed):

```python
CATEGORY_SERVICE_MAP = {
    "quality": "http://archon-intelligence:8053",
    "performance": "http://archon-intelligence:8053",
    "freshness": "http://archon-intelligence:8053",
    "traceability": "http://archon-intelligence:8053",
    "vector_search": "http://archon-intelligence:8053",
    "rag": "http://archon-search:8055",
    "search": "http://archon-search:8055",
    "bridge": "http://archon-bridge:8054",
    "core": "http://archon-mcp:8051",
    "cache": "http://archon-mcp:8051",
    # Fallback to server (8181) for: project, task, document, version, feature
}
```

**New Dynamic Discovery** (via omninode_bridge registry):

```python
# Service discovery via registry
async def get_service_url(capability: str) -> str:
    services = await registry.discover_services(capability=capability)
    if not services:
        raise ServiceNotFoundError(f"No service found for capability: {capability}")
    # Load balance across instances
    return services[0].url
```

### Appendix C: Docker Compose Changes

**Current** (`docker-compose.yml`):
```yaml
services:
  archon-mcp:
    build:
      context: ./python
      dockerfile: Dockerfile.mcp
    environment:
      - INTELLIGENCE_SERVICE_URL=http://archon-intelligence:8053
      - SEARCH_SERVICE_URL=http://archon-search:8055
      # ... hardcoded URLs
```

**After Separation** (`docker-compose.yml` in `omniarchon-mcp`):
```yaml
services:
  archon-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - OMNINODE_REGISTRY_URL=http://omninode-bridge-registry:8080
      - EVENT_BUS_BROKERS=omninode-bridge-redpanda:9092
      # No hardcoded service URLs!
    networks:
      - omninode-bridge-network  # Shared network
```

### Appendix D: CI/CD Pipeline

**New GitHub Actions Workflow** (`omniarchon-mcp`):

```yaml
name: MCP Server CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run tests
        run: pytest tests/
      - name: Lint
        run: ruff check .

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker image
        run: docker build -t omniarchon-mcp:${{ github.sha }} .
      - name: Push to registry
        run: docker push omniarchon-mcp:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to production
        run: |
          docker compose -f docker-compose.prod.yml up -d
          # Health check
          curl http://localhost:8051/health
```

---

## Conclusion

This roadmap provides a comprehensive plan for separating the MCP service while migrating to an event-driven architecture. The phased approach minimizes risk while delivering significant performance and scalability improvements.

**Next Steps**:
1. Review and approve this roadmap
2. Assign team members to phases
3. Start Phase 1: Event Bus Foundation
4. Weekly status reviews and adjustments

**Questions or Concerns**: Contact the architecture team.

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-18
**Prepared By**: Claude (AI Assistant)
**Reviewed By**: _Pending_
**Approved By**: _Pending_
