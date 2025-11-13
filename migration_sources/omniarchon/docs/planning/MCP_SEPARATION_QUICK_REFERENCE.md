# MCP Separation Quick Reference

**Version**: 1.0.0 | **Status**: Planning

Quick reference for implementing the MCP separation roadmap. See `MCP_SEPARATION_ROADMAP.md` for complete details.

---

## 🎯 Phase Overview

| Phase | Duration | Focus | Status |
|-------|----------|-------|--------|
| 1. Event Bus Foundation | 2 weeks | Topics, producers, consumers | 📋 Planned |
| 2. Hybrid Architecture | 3 weeks | 20% ops to events | 📋 Planned |
| 3. Registry Migration | 2 weeks | Dynamic discovery | 📋 Planned |
| 4. Full Event Migration | 4 weeks | 80% ops to events | 📋 Planned |
| 5. MCP Extraction | 3 weeks | Separate repos | 📋 Planned |
| 6. Production Deployment | 2 weeks | Rollout | 📋 Planned |

---

## 📊 Current State

**MCP Server**:
- **Port**: 8051
- **Location**: `/python/src/mcp_server/`
- **Protocol**: MCP over SSE
- **Tools**: 168+ operations (68 internal HTTP + 100 external MCP)

**Backend Services**:
- Intelligence: 8053 (33 tools)
- Search: 8055 (9 tools)
- Bridge: 8054 (11 tools)
- Server: 8181 (19 tools)

**Event Bus**:
- **Status**: ✅ Operational (Kafka consumer on 8059)
- **Broker**: omninode-bridge-redpanda:9092
- **Topics**: 4 active (service lifecycle, tool updates, system events, bridge events)

---

## 🔄 Migration Strategy

### What Moves to Event Bus (80%)

**High Priority** (async, fire-and-forget):
```
✅ batch_index_documents
✅ refresh_documents
✅ track_pattern_creation
✅ apply_performance_optimization
✅ cleanup_freshness_data
✅ update_task
✅ update_document
```

**Medium Priority** (async with polling):
```
⚠️ analyze_document_freshness
⚠️ establish_performance_baseline
⚠️ search_code_examples
⚠️ create_project / create_task
```

### What Stays HTTP (20%)

**Essential Sync Operations**:
```
❌ assess_code_quality (immediate scoring)
❌ perform_rag_query (search results)
❌ get_* / list_* (all read operations)
❌ health_check / session_info (native MCP)
```

---

## 🏗️ Repository Structure (After Separation)

### omniarchon-mcp (New)
```
omniarchon-mcp/
├── src/
│   ├── mcp_server.py
│   ├── tools/
│   │   └── archon_menu.py
│   ├── gateway/           # External MCP (zen, codanna, serena)
│   └── clients/
├── config/
│   └── mcp_services.yaml
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

### omniarchon (Existing)
```
omniarchon/
├── services/
│   ├── intelligence/      # ✅ Stays
│   ├── search/           # ✅ Stays
│   ├── bridge/           # ✅ Stays
│   └── kafka-consumer/   # ✅ Stays
├── python/
│   └── src/
│       ├── server/       # ✅ Stays
│       └── mcp_server/   # ❌ Moves to omniarchon-mcp
```

### omniarchon-common (New)
```
omniarchon-common/
├── src/
│   ├── models/
│   │   ├── event_envelope.py
│   │   └── tool_result.py
│   ├── protocols/
│   └── utils/
└── pyproject.toml
```

---

## 📋 Phase 1: Event Bus Foundation (Weeks 1-2)

### Tasks

**Week 1: Topic Design**
- [ ] Design event topic structure (47 topics)
- [ ] Define event envelope schema
- [ ] Create topic configuration in Redpanda
- [ ] Document event patterns

**Week 2: Producer/Consumer**
- [ ] Implement event producers in all services
- [ ] Test end-to-end event flow
- [ ] Add correlation ID tracking
- [ ] Performance test (100 events/sec)

### Deliverables
```python
# Event envelope standard
{
  "event_id": "uuid",
  "event_type": "archon.intelligence.quality.assess",
  "timestamp": "2025-10-18T10:00:00Z",
  "correlation_id": "request-uuid",
  "source_service": "archon-mcp",
  "target_service": "archon-intelligence",
  "payload": {...},
  "metadata": {...}
}
```

### Testing
```bash
# Produce test event
python scripts/test_event_producer.py

# Consume and verify
docker logs -f archon-kafka-consumer

# Verify in Redpanda
docker exec omninode-bridge-redpanda rpk topic list
```

---

## 📋 Phase 2: Hybrid Architecture (Weeks 3-5)

### Tasks

**Week 3: Dual Mode Implementation**
- [ ] Add event routing to `archon_menu`
- [ ] Implement status polling endpoint
- [ ] Create feature flags for event mode

**Week 4-5: Migrate 20% Operations**
- [ ] Migrate batch operations to events
- [ ] Add status tracking table
- [ ] Update tests for dual mode

### Code Changes

**Before** (HTTP only):
```python
async def batch_index_documents(params):
    response = await http_client.post(
        "http://archon-intelligence:8053/batch-index",
        json=params
    )
    return response.json()
```

**After** (Event bus):
```python
async def batch_index_documents(params):
    event_id = await event_bus.publish(
        "archon.intelligence.vector.batch_index",
        payload=params,
        correlation_id=str(uuid4())
    )
    return {
        "success": True,
        "event_id": event_id,
        "status": "submitted",
        "status_url": f"/api/events/{event_id}/status"
    }
```

### Testing
```bash
# Test hybrid mode
pytest tests/test_hybrid_architecture.py -v

# Check status polling
curl http://localhost:8181/api/events/{event_id}/status
```

---

## 📋 Phase 3: Registry Migration (Weeks 6-7)

### Tasks

**Week 6: Registry Integration**
- [ ] Integrate omninode_bridge registry
- [ ] Replace `CATEGORY_SERVICE_MAP`
- [ ] Implement dynamic service discovery

**Week 7: Testing & Validation**
- [ ] Test service discovery
- [ ] Validate health monitoring
- [ ] Update documentation

### Code Changes

**Before** (Hardcoded):
```python
CATEGORY_SERVICE_MAP = {
    "quality": "http://archon-intelligence:8053",
    "search": "http://archon-search:8055",
    # ... hardcoded URLs
}
```

**After** (Dynamic):
```python
from omninode_bridge.registry import ServiceRegistry

async def get_service_url(capability: str) -> str:
    services = await registry.discover_services(capability=capability)
    return services[0].url  # Load balance later
```

---

## 📋 Phase 4: Full Event Migration (Weeks 8-11)

### Tasks

**Week 8-9: Migrate Medium Priority Operations**
- [ ] Migrate 40% more operations
- [ ] Implement WebSocket push (optional)
- [ ] Add circuit breakers

**Week 10-11: Performance Testing**
- [ ] Load testing (200 events/sec)
- [ ] Latency benchmarking
- [ ] Optimization iterations

### Performance Targets
```
✅ 80% operations use event bus
✅ 30-50% faster for async ops
✅ 4x throughput increase
✅ <100ms event routing latency
```

---

## 📋 Phase 5: MCP Extraction (Weeks 12-14)

### Tasks

**Week 12: Repository Setup**
- [ ] Create `omniarchon-mcp` repo
- [ ] Create `omniarchon-common` package
- [ ] Setup CI/CD pipelines

**Week 13: Code Migration**
- [ ] Move MCP server code
- [ ] Update import paths
- [ ] Fix tests in new repo

**Week 14: Integration Testing**
- [ ] Test cross-repo communication
- [ ] Update Docker Compose
- [ ] Documentation updates

### Git Commands
```bash
# Create new repos
gh repo create omniarchon-mcp --public
gh repo create omniarchon-common --public

# Move MCP code
git subtree split -P python/src/mcp_server -b mcp-split
cd ../omniarchon-mcp
git pull ../omniarchon mcp-split

# Setup common package
cd ../omniarchon-common
poetry init
poetry add pydantic aiokafka
```

---

## 📋 Phase 6: Production Deployment (Weeks 15-16)

### Tasks

**Week 15: Staging Deployment**
- [ ] Deploy to staging
- [ ] Smoke tests
- [ ] Performance validation

**Week 16: Production Rollout**
- [ ] Blue/green deployment
- [ ] Gradual traffic shift (10% → 100%)
- [ ] Monitor for 1 week

### Deployment Commands
```bash
# Deploy new MCP server
cd omniarchon-mcp
docker compose -f docker-compose.prod.yml up -d

# Health check
curl http://localhost:8051/health

# Gradual rollout
./scripts/rollout.sh --percentage 10  # Start with 10%
./scripts/rollout.sh --percentage 50  # Increase to 50%
./scripts/rollout.sh --percentage 100 # Full migration

# Monitor
docker logs -f archon-mcp
curl http://localhost:8051/metrics
```

---

## 🔍 Troubleshooting

### Event Bus Issues

**Problem**: Events not being consumed
```bash
# Check Redpanda
docker ps | grep redpanda
docker logs omninode-bridge-redpanda

# Check consumer
docker logs archon-kafka-consumer

# List topics
docker exec omninode-bridge-redpanda rpk topic list

# Check consumer lag
docker exec omninode-bridge-redpanda rpk group describe archon-kafka-consumer-group
```

**Problem**: High latency
```bash
# Check event queue depth
curl http://localhost:8059/metrics/consumer

# Check service health
curl http://localhost:8053/health  # Intelligence
curl http://localhost:8055/health  # Search
```

### Service Discovery Issues

**Problem**: Services not found
```bash
# Check registry connection
curl http://omninode-bridge-registry:8080/health

# List registered services
curl http://omninode-bridge-registry:8080/services

# Check MCP logs
docker logs archon-mcp | grep registry
```

### MCP Server Issues

**Problem**: External tools not working
```bash
# Check gateway status
curl http://localhost:8051/health | jq '.gateway'

# Test external tool directly
archon_menu(operation="zen.version")

# Check logs
docker logs archon-mcp | grep gateway
```

---

## 📚 Key Commands Reference

### Event Bus
```bash
# Produce event
python scripts/produce_event.py \
  --topic archon.intelligence.quality.assess \
  --payload '{"content": "code", "source_path": "test.py"}'

# Consume events
docker logs -f archon-kafka-consumer

# List topics
docker exec omninode-bridge-redpanda rpk topic list
```

### Service Registry
```bash
# Register service
curl -X POST http://omninode-bridge-registry:8080/register \
  -H "Content-Type: application/json" \
  -d '{"name": "archon-mcp", "url": "http://archon-mcp:8051", "capabilities": ["mcp", "gateway"]}'

# Discover services
curl http://omninode-bridge-registry:8080/services?capability=intelligence
```

### MCP Server
```bash
# Start MCP server
docker compose up -d archon-mcp

# Health check
curl http://localhost:8051/health

# List tools
archon_menu(operation="discover")

# Call tool
archon_menu(
  operation="assess_code_quality",
  params={"content": "code", "source_path": "test.py"}
)
```

---

## 📊 Monitoring Dashboards

### Key Metrics

**Event Bus**:
- Events/sec processed
- Consumer lag
- Event processing latency
- Error rate

**MCP Server**:
- Request/sec
- Response latency (p50, p95, p99)
- Error rate by operation
- Gateway health

**Service Discovery**:
- Registry latency
- Service count
- Health check failures
- Discovery cache hit rate

### Grafana Queries
```promql
# Event throughput
rate(kafka_consumer_messages_total[5m])

# MCP request latency
histogram_quantile(0.95, mcp_request_duration_seconds_bucket)

# Service discovery success rate
rate(registry_discovery_success_total[5m]) / rate(registry_discovery_total[5m])
```

---

## ✅ Acceptance Criteria (Per Phase)

### Phase 1
- [ ] Event bus handles 100 events/sec reliably
- [ ] All services can publish events
- [ ] Consumer processes events with <1% error rate
- [ ] Event schema documented

### Phase 2
- [ ] 20% of operations migrated to events
- [ ] Status polling returns accurate results
- [ ] HTTP operations still work (backward compatible)
- [ ] Tests pass for hybrid mode

### Phase 3
- [ ] All services discoverable via registry
- [ ] No hardcoded URLs in MCP code
- [ ] Service health tracked automatically
- [ ] <100ms registry lookup latency

### Phase 4
- [ ] 80% of operations use event bus
- [ ] 30-50% performance improvement
- [ ] Zero data loss in event processing
- [ ] All performance targets met

### Phase 5
- [ ] MCP server runs independently
- [ ] All tests pass in new repo
- [ ] Docker Compose starts both repos
- [ ] CI/CD pipelines green

### Phase 6
- [ ] Zero downtime during migration
- [ ] All metrics meet targets
- [ ] No user-facing issues
- [ ] Documentation complete

---

## 🚨 Rollback Procedures

### Phase 1-2 Rollback
```bash
# Disable event mode
export ENABLE_EVENT_BUS=false
docker compose restart archon-mcp

# Verify HTTP mode
curl http://localhost:8051/health
```

### Phase 3-4 Rollback
```bash
# Revert to hardcoded URLs
git revert <registry-migration-commit>
docker compose build archon-mcp
docker compose up -d archon-mcp
```

### Phase 5-6 Rollback
```bash
# Switch back to old MCP server
docker compose -f docker-compose.old.yml up -d archon-mcp
# Update Claude Code config to old endpoint
```

---

## 📞 Contact & Support

**Architecture Questions**: #archon-architecture (Slack)
**Event Bus Issues**: #event-bus-support (Slack)
**MCP Server Issues**: #mcp-server (Slack)
**Deployment Issues**: #devops (Slack)

**On-Call**: Check PagerDuty rotation

---

**Last Updated**: 2025-10-18
**Maintained By**: Archon Platform Team
