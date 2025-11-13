# Archon - Intelligence Provider

**Version**: 1.0.0 | **Status**: Production (44+ hours uptime) | **Architecture**: Event-Driven Microservices

Intelligence platform for AI coding assistants via event bus (Kafka/Redpanda). Provides code quality analysis, performance optimization, RAG intelligence, pattern learning, and ONEX compliance validation.

> **📚 Shared Infrastructure**: For common OmniNode infrastructure (PostgreSQL, Kafka/Redpanda, remote server topology, Docker networking, environment variables), see **`~/.claude/CLAUDE.md`**. This file contains Archon-specific architecture, APIs, and services only.

**🆕 Slack Alerting**: Container health monitoring with real-time Slack notifications. See `python/docs/SLACK_ALERTING.md` for setup.

**🔒 Security Hardened**: Production-ready with fail-closed configuration, comprehensive URL validation, DLQ routing, and 100% test coverage (118/118 tests passing). See `IMPROVEMENTS.md` for details.

## ⚠️ CRITICAL: Environment Variable Configuration Policy

**ABSOLUTE RULE**: NO environment variables shall EVER be hardcoded in code files. ALL configuration MUST use `.env`.

### Mandatory Configuration Practices

1. **NO Hardcoded Values**
   - ❌ **NEVER**: `EMBEDDING_DIMENSIONS = 1536` (hardcoded in code)
   - ✅ **ALWAYS**: `EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))` (from .env with default)

2. **Use Pydantic Settings for Configuration**
   ```python
   from pydantic import Field
   from pydantic_settings import BaseSettings

   class Config(BaseSettings):
       embedding_dimensions: int = Field(default=1536, env="EMBEDDING_DIMENSIONS")
       embedding_model: str = Field(default="...", env="EMBEDDING_MODEL")
   ```

3. **Environment Variables Must Propagate**
   - All Docker services must receive env vars via `docker-compose.yml`
   - All scripts must read from `.env` or environment
   - All configuration must have single source of truth in `.env`

4. **Common Violations to AVOID**
   - Hardcoded API endpoints (use `SERVICE_URL` from env)
   - Hardcoded model names (use `EMBEDDING_MODEL` from env)
   - Hardcoded dimensions (use `EMBEDDING_DIMENSIONS` from env)
   - Hardcoded database credentials (use `DB_HOST`, `DB_PORT`, etc. from env)
   - Hardcoded timeouts (use timeout config from env)

5. **Verification Checklist**
   - ✅ Changing `.env` and rebuilding changes behavior
   - ✅ No magic numbers for configuration in code
   - ✅ All services respect environment overrides
   - ✅ Search codebase for old values returns only defaults and docs

**Why This Matters**: Hardcoded configuration has caused repeated production issues with embedding dimensions, model mismatches, and service configuration. This policy is NON-NEGOTIABLE.

**Reference**: See `EMBEDDING_CONFIG_HARDCODE_ELIMINATION.md` for comprehensive fix applied 2025-11-01.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  CLIENT LAYER                       │
│  External Clients │ OmniNode Bridge │ HTTP Clients  │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│           EVENT BUS (Kafka/Redpanda)                │
│  Tree Discovery │ Intelligence Gen │ Doc Indexing   │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│         BACKEND INTELLIGENCE SERVICES               │
├──────────────────────┬──────────────────────────────┤
│ Intelligence (8053)  │ Search (8055)                │
│ • Quality (4 APIs)   │ • RAG Search                 │
│ • Performance (5)    │ • Enhanced Search            │
│ • Freshness (9)      │ • Code Examples              │
│ • Pattern Learn (7)  │ • Multi-Source Agg           │
│ • Traceability (11)  │                              │
│ • Autonomous (7)     │                              │
│ • Entity Mgmt (6)    │                              │
│ • Analytics (5)      │                              │
│ • Custom Rules (8)   │                              │
│ • Quality Trends (7) │                              │
│ • Perf Analytics (6) │                              │
├──────────────────────┼──────────────────────────────┤
│ LangExtract (8156)   │ Bridge (8054) ⭐             │
│ • ML Features        │ • Event Translation          │
│ • Classification     │ • Metadata Stamping          │
│ • Semantic Analysis  │ • BLAKE3 Hashing             │
│                      │ • Kafka Producer/Consumer    │
└──────────────────────┴──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│                  DATA LAYER                         │
│ Qdrant (6333/6334) │ Memgraph (7687) │ PostgreSQL  │
│ Vector DB          │ Knowledge Graph │ (5436)      │
└─────────────────────────────────────────────────────┘
```

## Infrastructure Topology

**CRITICAL**: Archon uses a hybrid LOCAL + REMOTE architecture. Understanding this topology prevents configuration errors.

### Network Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    LOCAL MACHINE                         │
│  ┌──────────────────────────────────────────────┐       │
│  │  Docker Network: omniarchon_app-network      │       │
│  │  ┌────────────┐  ┌──────────┐  ┌─────────┐  │       │
│  │  │ archon-    │  │ archon-  │  │ archon- │  │       │
│  │  │ intelligence│ │ search   │  │ bridge  │  │       │
│  │  │ :8053      │  │ :8055    │  │ :8054   │  │       │
│  │  └────────────┘  └──────────┘  └─────────┘  │       │
│  │  ┌────────────┐  ┌──────────┐               │       │
│  │  │ qdrant     │  │ memgraph │               │       │
│  │  │ :6333/6334 │  │ :7687    │               │       │
│  │  └────────────┘  └──────────┘               │       │
│  └──────────────────────────────────────────────┘       │
│                        │                                 │
│                        │ /etc/hosts DNS resolution:      │
│                        │ omninode-bridge-redpanda        │
│                        │   → 192.168.86.200              │
│                        ↓                                 │
└─────────────────────────────────────────────────────────┘
                         │
                         │ Network Connection
                         │ (via /etc/hosts)
                         ↓
┌─────────────────────────────────────────────────────────┐
│              REMOTE SERVER (192.168.86.200)             │
│  ┌──────────────────────────────────────────────┐       │
│  │  Docker Network: omninode-bridge-network     │       │
│  │  ┌────────────────────────────────────────┐  │       │
│  │  │ omninode-bridge-redpanda (Redpanda)    │  │       │
│  │  │   Internal: :9092                      │  │       │
│  │  │   External: :29092                     │  │       │
│  │  └────────────────────────────────────────┘  │       │
│  │  ┌────────────────────────────────────────┐  │       │
│  │  │ omninode-bridge-postgres (PostgreSQL)  │  │       │
│  │  │   Internal: :5432                      │  │       │
│  │  │   External: :5436                      │  │       │
│  │  └────────────────────────────────────────┘  │       │
│  │  ┌────────────────────────────────────────┐  │       │
│  │  │ Other OmniNode services (Consul, etc.) │  │       │
│  │  └────────────────────────────────────────┘  │       │
│  └──────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### Service Topology Summary

**LOCAL Services** (Docker: localhost):
- **archon-intelligence**: `localhost:8053` - Core intelligence APIs
- **archon-bridge**: `localhost:8054` - Event translation service
- **archon-search**: `localhost:8055` - RAG and vector search
- **archon-langextract**: `localhost:8156` - Language extraction
- **archon-agents**: `localhost:8052` - AI orchestration
- **archon-frontend**: `localhost:3737` - React UI
- **archon-valkey**: `localhost:6379` - Distributed cache
- **qdrant**: `localhost:6333/6334` - Vector database
- **memgraph**: `localhost:7687` - Knowledge graph

**REMOTE Services** (192.168.86.200):
- **Redpanda/Kafka**: Event bus (Kafka-compatible)
  - **Internal port**: `:9092` (Docker network access)
  - **External port**: `:29092` (host machine access)
- **PostgreSQL**: Pattern traceability database
  - **Internal port**: `:5432` (Docker network access)
  - **External port**: `:5436` (host machine access)
- **OmniNode Services**: Tree indexing, metadata stamping, etc.

### DNS Resolution & Network Connectivity

**Critical Configuration**: `/etc/hosts` provides DNS resolution:
```bash
# From /etc/hosts
192.168.86.200 omninode-bridge-redpanda
192.168.86.200 omninode-bridge-consul
192.168.86.200 omninode-bridge-postgres
```

This allows Docker services to use friendly hostnames that resolve to the remote server.

### Kafka/Redpanda Connection Patterns

**Context 1: Docker Services** (archon-intelligence, archon-bridge, etc.)
- **Configuration**: `KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092`
- **Resolution**: DNS via `/etc/hosts` → `192.168.86.200:9092`
- **Port**: Use **9092** (internal Redpanda port)
- **Why**: Docker containers are connected to `omninode_bridge_omninode-bridge-network` external network

**Context 2: Host Scripts** (bulk_ingest_repository.py, etc.)
- **Configuration**: `KAFKA_BOOTSTRAP_SERVERS=192.168.86.200:29092`
- **Resolution**: Direct IP address (no DNS needed)
- **Port**: Use **29092** (external published port)
- **Why**: Scripts run on host machine, not in Docker network

**Context 3: Remote Machine Access**
- **Configuration**: `KAFKA_BOOTSTRAP_SERVERS=localhost:29092`
- **Why**: When running commands ON the 192.168.86.200 server itself

### Port Number Reference

| Service | Internal Port | External Port | Used By |
|---------|--------------|---------------|---------|
| Redpanda/Kafka | 9092 | 29092 | Docker services use 9092, host scripts use 29092 |
| PostgreSQL | 5432 | 5436 | Docker services use 5432, host scripts use 5436 |
| OnexTree | 8058 | 8058 | Both (same port) |
| Metadata Stamping | 8057 | 8057 | Both (same port) |

### Configuration Files Summary

**Root `.env` file** (line 171):
```bash
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092  # ✅ CORRECT for Docker services
```

**Scripts** (bulk_ingest_repository.py, test scripts):
```python
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092")  # ✅ CORRECT for host
```

**docker-compose.yml** (lines 192, 262, 524):
```yaml
KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS:-omninode-bridge-redpanda:9092}  # ✅ CORRECT
```

### Common Pitfalls & Solutions

❌ **WRONG**: Trying to restart local Redpanda container
- **Issue**: There is NO local Redpanda - it's on 192.168.86.200
- **Solution**: Check remote Redpanda health at 192.168.86.200

❌ **WRONG**: Using port 29092 in docker-compose.yml
- **Issue**: Docker services need internal port 9092
- **Solution**: Keep docker-compose using `omninode-bridge-redpanda:9092`

❌ **WRONG**: Using hostname in host scripts
- **Issue**: Scripts can't resolve Docker internal hostnames
- **Solution**: Use `192.168.86.200:29092` in scripts

✅ **CORRECT Configuration Checklist**:
- Docker services: `omninode-bridge-redpanda:9092` ✓
- Host scripts: `192.168.86.200:29092` ✓
- `/etc/hosts` has DNS entries ✓
- docker-compose includes external network ✓

### Verification Commands

```bash
# 1. Verify /etc/hosts DNS resolution
cat /etc/hosts | grep -E "192.168.86.200|redpanda"

# 2. Test connectivity from host machine
nc -zv 192.168.86.200 9092   # Internal port (should work)
nc -zv 192.168.86.200 29092  # External port (should work)

# 3. Check Docker service configuration
docker exec archon-intelligence env | grep KAFKA_BOOTSTRAP_SERVERS
# Expected: KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092

# 4. Verify external network connection
docker network inspect omninode_bridge_omninode-bridge-network --format '{{range .Containers}}{{.Name}} {{end}}'
# Should include: archon-intelligence, archon-kafka-consumer

# 5. Check Redpanda topics
docker exec archon-intelligence sh -c 'curl -s http://omninode-bridge-redpanda:9644/v1/topics' | python3 -m json.tool
```

## ⚠️ Architecture Migrations (2025-10)

### Supabase Migration (2025-10-29)

**Status**: ✅ Complete - OmniNode services migrated away from Supabase dependency

**Services Affected**:
- archon-intelligence, archon-bridge, archon-search: ✅ Migrated (Supabase optional)
- archon-kafka-consumer: ✅ Fixed (topic subscription corrected)
- archon-agents: Still uses Supabase (original Archon service)
- archon-server: Deprecated (functionality migrated to archon-intelligence)

**Configuration Documentation**:
- Migration Details: `docs/CONFIG_FIXES_SUMMARY.md`
- Audit Report: `docs/CONFIG_AUDIT_REPORT.md`
- Consolidation Strategy: `docs/CONFIG_CONSOLIDATION_STRATEGY.md`

## Event Bus Architecture (Current)

**Communication**: Event-driven via Kafka/Redpanda (REMOTE at 192.168.86.200)
**Bridge Service**: archon-bridge (port 8054) - Event translation and routing
**Event Bus**: Redpanda at `192.168.86.200` (see **Infrastructure Topology** section above)

### ⚠️ CRITICAL: ALWAYS Use REMOTE Redpanda

**DEFAULT POLICY**: **ALWAYS** use REMOTE Redpanda (192.168.86.200). **NEVER** start local Redpanda.

**Why REMOTE is mandatory**:
1. ✅ **Resource Efficiency**: Offloads event bus processing from dev machine (~1-2GB RAM saved)
2. ✅ **OmniNode Integration**: Events flow to OnexTree, metadata stamping, and other OmniNode services
3. ✅ **Data Consistency**: Single source of truth across all services
4. ✅ **Production Parity**: Dev environment matches production architecture
5. ✅ **Shared Infrastructure**: Other services already consuming from this Redpanda

**Why NEVER use local Redpanda**:
1. ❌ **Resource Drain**: Consumes significant dev machine resources
2. ❌ **Isolated Data**: Events not visible to remote OmniNode services
3. ❌ **Integration Broken**: OnexTree and metadata stamping can't process events
4. ❌ **Duplicate Management**: Another service to monitor locally
5. ❌ **Architectural Mismatch**: Doesn't reflect real deployment

**Redpanda Connection Patterns**:
- **Docker services**: Use `omninode-bridge-redpanda:9092` (DNS resolves via /etc/hosts → 192.168.86.200:9092)
- **Host scripts**: Use `192.168.86.200:29092` (direct IP with external port)
- **Remote server**: Use `localhost:29092` (when running ON 192.168.86.200)

See [Infrastructure Topology](#infrastructure-topology) section above for complete network architecture.

**Kafka Topics**:
- `dev.archon-intelligence.tree.discover.v1` - Tree discovery events
- `dev.archon-intelligence.stamping.generate.v1` - Intelligence generation requests
- `dev.archon-intelligence.tree.index.v1` - Document indexing requests

**Architecture Benefits**:
- ✅ **Asynchronous**: Non-blocking event-driven communication
- ✅ **Scalable**: Horizontal scaling via consumer groups
- ✅ **Resilient**: Message persistence and replay capability
- ✅ **Decoupled**: Services communicate via events, not direct calls

## Services

**LOCAL Services**:

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| archon-bridge | 8054 | ✅ | Event bus bridge (Kafka producer/consumer, metadata stamping) |
| archon-intelligence | 8053 | ✅ | Core intelligence (78 APIs) |
| archon-search | 8055 | ✅ | RAG queries |
| archon-langextract | 8156 | ✅ | ML extraction |
| archon-agents | 8052 | ✅ | AI orchestration |
| archon-frontend | 3737 | ✅ | React UI |
| archon-valkey | 6379 | ✅ | Distributed cache (512MB LRU) |
| qdrant | 6333/6334 | ✅ | Vector DB |
| memgraph | 7687 | ✅ | Knowledge graph |

**REMOTE Services** (192.168.86.200):

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| omninode-bridge-redpanda | 9092/29092 | ✅ | Kafka-compatible event bus (Redpanda) |
| omninode-bridge-postgres | 5432/5436 | ✅ | Pattern traceability database |
| omninode-bridge-onextree | 8058 | ✅ | Tree indexing service |
| omninode-bridge-metadata-stamping | 8057 | ✅ | ONEX metadata stamping |

**Notes**:
- archon-server (port 8181) is deprecated. Intelligence APIs are now provided by archon-intelligence (port 8053).
- For port usage (internal vs external), see [Infrastructure Topology](#infrastructure-topology) section.

## Intelligence APIs (78)

**Base**: `http://localhost:8053`

### Bridge Intelligence (3)
```
POST /api/bridge/generate-intelligence  # Generate OmniNode metadata
GET  /api/bridge/health                 # Bridge service health
GET  /api/bridge/capabilities           # Intelligence capabilities
```

### Quality Assessment (4)
```
POST /assess/code              # ONEX compliance + quality
POST /assess/document           # Document quality
POST /patterns/extract          # Pattern identification
POST /compliance/check          # Architectural compliance
```

### Performance Optimization (5)
```
POST /performance/baseline      # Establish baselines
GET  /performance/opportunities/{operation_name}
POST /performance/optimize      # Apply optimizations
GET  /performance/report        # Reports
GET  /performance/trends        # Trend monitoring
```

### Document Freshness (9)
```
POST /freshness/analyze         # Analyze freshness
GET  /freshness/stale           # Get stale docs
POST /freshness/refresh         # Refresh docs
GET  /freshness/stats           # Statistics
GET  /freshness/document/{path} # Single doc
POST /freshness/cleanup         # Cleanup old data
POST /freshness/events/document-update
GET  /freshness/events/stats
GET  /freshness/analyses
```

### Pattern Learning (7)
```
POST /api/pattern-learning/pattern/match
POST /api/pattern-learning/hybrid/score
POST /api/pattern-learning/semantic/analyze
GET  /api/pattern-learning/metrics
GET  /api/pattern-learning/cache/stats
POST /api/pattern-learning/cache/clear
GET  /api/pattern-learning/health
```

### Pattern Traceability (11)
```
POST /api/pattern-traceability/lineage/track
POST /api/pattern-traceability/lineage/track/batch
GET  /api/pattern-traceability/lineage/{pattern_id}
GET  /api/pattern-traceability/lineage/{pattern_id}/evolution
GET  /api/pattern-traceability/executions/logs
GET  /api/pattern-traceability/executions/summary
GET  /api/pattern-traceability/analytics/{pattern_id}
POST /api/pattern-traceability/analytics/compute
POST /api/pattern-traceability/feedback/analyze
POST /api/pattern-traceability/feedback/apply
GET  /api/pattern-traceability/health
```

### Autonomous Learning (7)
```
POST /api/autonomous/patterns/ingest
POST /api/autonomous/patterns/success
POST /api/autonomous/predict/agent
POST /api/autonomous/predict/time
GET  /api/autonomous/calculate/safety
GET  /api/autonomous/stats
GET  /api/autonomous/health
```

### Entity & Knowledge (6)
```
POST /extract/code              # Code entity extraction
POST /extract/document          # Document entity extraction
POST /process/document          # Document processing
GET  /entities/search           # Entity search
GET  /relationships/{entity_id} # Entity relationships
POST /batch-index               # Batch indexing
```

### Pattern Analytics (5)
```
GET  /api/pattern-analytics/health
GET  /api/pattern-analytics/success-rates
GET  /api/pattern-analytics/top-patterns
GET  /api/pattern-analytics/emerging-patterns
GET  /api/pattern-analytics/pattern/{pattern_id}/history
```

### Custom Quality Rules (8)
```
POST /api/custom-rules/evaluate
GET  /api/custom-rules/project/{project_id}/rules
POST /api/custom-rules/project/{project_id}/load-config
POST /api/custom-rules/project/{project_id}/rule
PUT  /api/custom-rules/project/{project_id}/rule/{rule_id}/enable
PUT  /api/custom-rules/project/{project_id}/rule/{rule_id}/disable
GET  /api/custom-rules/health
DELETE /api/custom-rules/project/{project_id}/rules
```

### Quality Trends (7)
```
POST /api/quality-trends/snapshot
GET  /api/quality-trends/project/{project_id}/trend
GET  /api/quality-trends/project/{project_id}/file/{file_path}/trend
GET  /api/quality-trends/project/{project_id}/file/{file_path}/history
POST /api/quality-trends/detect-regression
GET  /api/quality-trends/stats
DELETE /api/quality-trends/project/{project_id}/snapshots
```

### Performance Analytics (6)
```
GET  /api/performance-analytics/baselines
GET  /api/performance-analytics/operations/{operation}/metrics
GET  /api/performance-analytics/optimization-opportunities
POST /api/performance-analytics/operations/{operation}/anomaly-check
GET  /api/performance-analytics/trends
GET  /api/performance-analytics/health
```

## Quick Start

```bash
# Start services
docker compose up -d

# Verify core services
curl http://localhost:8053/health  # Intelligence service
curl http://localhost:8054/health  # Bridge service
curl http://localhost:8055/health  # Search service

# Index repository with inline content
python3 scripts/bulk_ingest_repository.py /path/to/project \
  --project-name my-project \
  --kafka-servers 192.168.86.200:29092

# Check pattern learning
curl http://localhost:8053/api/pattern-learning/health

# Verify event bus
docker exec omninode-bridge-redpanda rpk cluster info
```

**Note**: Phase 0 (filesystem-based indexing) removed. All indexing requires inline content via `bulk_ingest_repository.py`.

## Orchestrated Intelligence

**ResearchOrchestrator**: Parallel execution across RAG (300ms) + Qdrant (250ms) + Memgraph (450ms) = ~1000ms total

**Performance**:
- Orchestrated research: <1200ms (target), ~1000ms (actual)
- Vector search: <100ms (target), ~50-80ms (actual)
- Batch indexing: <100ms/doc (target), ~50ms/doc (actual)

## Performance Optimizations (Phase 1)

**Status**: ✅ Implemented | **Target**: 30-40% improvement

### Distributed Caching (Valkey)
- **Cache Layer**: Valkey (Redis fork) with 512MB LRU eviction
- **TTL**: 5 minutes (300s) for search results
- **Performance**: Warm cache hits < 100ms (95%+ improvement vs cold)

### HTTP/2 Connection Pooling
- **Max Connections**: 100 total, 20 keepalive
- **Timeout**: 5s connect, 10s read, 5s write
- **Impact**: 30-50% latency reduction

### Retry Logic with Exponential Backoff
- **Attempts**: 3 retries max
- **Backoff**: Exponential (1s → 2s → 4s)
- **Scope**: All backend service calls

### Performance Targets
- **Cold cache**: <7-9s (baseline, no cache)
- **Warm cache hit**: <100ms (target), <1000ms (acceptable)
- **Phase 1 overall**: 30-40% improvement

## Pattern Learning (4 Phases)

1. **Foundation** ✅: Base models, ONEX compliance
2. **Matching** ✅: Hybrid scoring, semantic analysis, cache optimization
3. **Validation** ✅: Quality gates, compliance reporting, consensus validation
4. **Traceability** ✅: Pattern lineage (25,249 patterns indexed), usage analytics, feedback loops

**Location**: `/services/intelligence/src/services/pattern_learning/`

## Quality Scoring (6 Dimensions)

1. **Complexity** (20%): Cyclomatic, cognitive, function/class size
2. **Maintainability** (20%): Organization, structure
3. **Documentation** (15%): Coverage, quality
4. **Temporal Relevance** (15%): Era classification (pre_archon → advanced_archon)
5. **Pattern Compliance** (15%): Best practices, anti-patterns, security
6. **Architectural Compliance** (15%): ONEX pattern detection

## Kafka & Event Bus

**Event Bus**: Redpanda (Kafka-compatible) - **REMOTE at 192.168.86.200**
**Python Client**: aiokafka 0.12.0 ✅ (latest version, released October 26, 2024)
**Compatibility**: Verified with Redpanda (Kafka API v0.11+)

**Dependencies**:
```toml
aiokafka = "^0.12.0"  # Latest, async Kafka client
confluent-kafka = "^2.6.0"  # Sync Kafka client (handlers)
```

**Connection Patterns** (CRITICAL - Use correct port for your context):
- **Docker services**: `omninode-bridge-redpanda:9092` (DNS resolves via /etc/hosts → 192.168.86.200:9092)
- **Host scripts**: `192.168.86.200:29092` (direct IP with external published port)
- **Remote server**: `localhost:29092` (when running commands ON 192.168.86.200)

**Why different ports?**
- Port **9092**: Internal Redpanda port (Docker network)
- Port **29092**: External published port (host machine access)

See [Infrastructure Topology](#infrastructure-topology) section for complete network architecture details.

## Environment

```bash
# Core Services (LOCAL)
INTELLIGENCE_SERVICE_PORT=8053
BRIDGE_SERVICE_PORT=8054
SEARCH_SERVICE_PORT=8055

# Event Bus (REMOTE at 192.168.86.200)
# CRITICAL: Use different values depending on context:
# - Docker services: omninode-bridge-redpanda:9092 (resolves via /etc/hosts)
# - Host scripts: 192.168.86.200:29092 (direct IP with external port)
# See Infrastructure Topology section for details
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092  # For Docker services
# KAFKA_BOOTSTRAP_SERVERS=192.168.86.200:29092  # For host scripts (uncomment if needed)
KAFKA_TOPIC_PREFIX=dev.archon-intelligence

# Databases
# Local databases
MEMGRAPH_URI=bolt://memgraph:7687
QDRANT_URL=http://qdrant:6333
# Remote databases (192.168.86.200)
POSTGRES_HOST=192.168.86.200  # Remote PostgreSQL
POSTGRES_PORT=5436  # External port
POSTGRES_DATABASE=omninode_bridge

# Performance Optimization (LOCAL)
VALKEY_URL=redis://archon-valkey:6379/0
ENABLE_CACHE=true

# AI/ML (REMOTE at 192.168.86.200)
OPENAI_API_KEY=<key>
OLLAMA_BASE_URL=http://192.168.86.200:11434
```

**Configuration Documentation**:
- Master Template: `.env.example` (319 lines, comprehensive)
- Timeout Config: `config/timeout_config.py` (centralized timeout management)
- Migration Summary: `docs/CONFIG_FIXES_SUMMARY.md`
- Network Topology: See [Infrastructure Topology](#infrastructure-topology) section

## Timeout Configuration

**Location**: `config/timeout_config.py`

Centralized timeout configuration using Pydantic Settings. See `.env.example` for all 50+ timeout parameters.

**Quick Reference**:
```python
from config import get_http_timeout, get_db_timeout, get_cache_timeout, get_async_timeout

# Service timeouts
timeout = get_http_timeout("intelligence")  # 60.0s default
timeout = get_db_timeout("connection")      # 30.0s default
timeout = get_cache_timeout("operation")    # 2.0s default
timeout = get_async_timeout("standard")     # 10.0s default
```

**Environment Overrides**:
```bash
HTTP_TIMEOUT_INTELLIGENCE=90.0
DB_TIMEOUT_CONNECTION=45.0
CACHE_TIMEOUT_OPERATION=3.0
```

## Health Monitoring

### Quick Health Checks

```bash
# Service health
curl http://localhost:8053/health  # Intelligence
curl http://localhost:8054/health  # Bridge
curl http://localhost:8055/health  # Search

# Event bus health
docker exec omninode-bridge-redpanda rpk cluster health

# Cache health
docker exec archon-valkey valkey-cli ping

# Intelligence subsystems
curl http://localhost:8053/api/pattern-learning/health
curl http://localhost:8053/api/pattern-traceability/health
```

### Comprehensive Environment Verification

**Script**: `scripts/verify_environment.py` (formerly `verify_recent_fixes.py`)

Performs comprehensive validation of all Archon services, databases, and data integrity:

```bash
# Standard verification
python3 scripts/verify_environment.py

# Detailed output with timing and metadata
python3 scripts/verify_environment.py --verbose
```

**Validation Checks** (9 total):
1. ✅ **vLLM Embedding Service** - Connectivity and response time (<50ms target)
2. ✅ **archon-intelligence** - Core intelligence service health
3. ✅ **archon-bridge** - Event bus bridge service health
4. ✅ **archon-search** - RAG search service health
5. ✅ **Memgraph Graph Structure** - Node/relationship counts, orphaned files
6. ✅ **Language Field Coverage** - % of files with language metadata
7. ✅ **project_name Consistency** - All files have project association
8. ✅ **Qdrant Vector Coverage** - Vector count vs file count ratio
9. ✅ **File Tree Graph** - PROJECT/DIRECTORY nodes, CONTAINS relationships, orphan detection

**Output Format**:
```
======================================================================
🔍 ENVIRONMENT VERIFICATION REPORT
======================================================================
Timestamp: 2025-11-10 08:15:10

✅ vLLM Embedding Service                   Service healthy (33ms)
✅ archon-intelligence                      Healthy (278ms)
✅ archon-bridge                            Healthy (196ms)
✅ archon-search                            Healthy (264ms)
✅ Memgraph Graph Structure                 Graph healthy: 67,277 nodes, 15,666 relationships
✅ Language Field Coverage                  Language coverage excellent: 100.0% overall
✅ project_name Consistency                 All 143 files have project_name
✅ Qdrant Vector Coverage                   7,118 vectors (4977.6% of 143 files)
✅ File Tree Graph                          Tree graph healthy: 1 PROJECT, 5 DIRs, 148 CONTAINS, 0 orphans

======================================================================
🎉 Overall Status: PASS - All checks passed!
   Passed: 9, Warned: 0, Failed: 0
======================================================================
```

**Exit Codes**:
- `0` - All checks passed
- `1` - Some warnings (degraded but functional)
- `2` - Critical failures (requires attention)

**When to Run**:
- After service restarts or updates
- Before/after bulk ingestion operations
- When debugging data inconsistencies
- As part of deployment validation
- Daily health checks in production

## Data Integrity Validation

**Automated Validation**: Comprehensive health check for all data components

```bash
# Quick validation
poetry run python3 scripts/validate_data_integrity.py

# Detailed validation
poetry run python3 scripts/validate_data_integrity.py --verbose

# JSON output for CI/CD
poetry run python3 scripts/validate_data_integrity.py --json
```

**Validates**:
- ✅ **Memgraph** - Document node count
- ✅ **Qdrant** - Vector collection coverage
- ✅ **Search** - File path retrieval rate
- ✅ **Metadata** - Filtering functionality

**Exit Codes**:
- `0` - Healthy (3-4 components working)
- `1` - Degraded (2 components working)
- `2` - Unhealthy (0-1 components working)

**Documentation**: See `docs/VALIDATION_SCRIPT.md`

### Database Management

**Clear & Reset Databases**: Wipe all data from Qdrant and Memgraph for fresh ingestion

```bash
# Interactive mode (prompts for confirmation)
./scripts/clear_databases.sh

# Non-interactive mode (auto-confirm)
./scripts/clear_databases.sh --force

# Dry-run mode (show what would be deleted)
./scripts/clear_databases.sh --dry-run
```

**What Gets Cleared**:
- **Qdrant**: Deletes `archon_vectors` collection, recreates with 1536 dimensions
- **Memgraph**: Executes `MATCH (n) DETACH DELETE n` (removes all nodes/relationships)

**Use Cases**:
- Database sync issues (different counts in Qdrant vs Memgraph)
- Fresh repository ingestion after schema changes
- Testing ingestion pipeline from clean state
- Removing corrupt or stale data

**Safety Features**:
- Health checks before execution (verifies services are running)
- Confirmation prompt (unless `--force` flag used)
- Dry-run mode for previewing changes
- Comprehensive logging to `logs/clear_databases_*.log`

**Typical Workflow**:
```bash
# 1. Clear databases
./scripts/clear_databases.sh --force

# 2. Re-ingest repository (tree graph built automatically)
python3 scripts/bulk_ingest_repository.py /Volumes/PRO-G40/Code/omniarchon \
  --project-name omniarchon \
  --kafka-servers 192.168.86.200:29092

# 3. Verify environment health
python3 scripts/verify_environment.py --verbose
```

**Exit Codes**:
- `0` - Success (databases cleared)
- `1` - Error (service unreachable, operation failed, user cancelled)

## Cache Management

```bash
# Check cache health
curl http://localhost:8053/cache/health

# Get metrics
curl http://localhost:8053/cache/metrics

# Invalidate patterns
curl -X POST http://localhost:8053/cache/invalidate-pattern \
  -H "Content-Type: application/json" \
  -d '{"pattern": "research:rag:*"}'

# Direct cache commands
docker exec archon-valkey valkey-cli ping
docker exec archon-valkey valkey-cli KEYS "research:*"
docker exec archon-valkey valkey-cli INFO stats
```

**Cache Patterns**:
- `research:rag:*` - RAG search results
- `research:vector:*` - Vector search results
- `research:knowledge:*` - Knowledge graph results

## Observability & Monitoring

**Comprehensive validation and monitoring tools for production deployment**

**Quick Reference**:
- **Basic Health**: `curl http://localhost:8053/health`
- **Data Validation**: `python3 scripts/validate_data_integrity.py`
- **Full Integration Test**: `./scripts/validate_integrations.sh`
- **Real-time Monitoring**: `python3 scripts/health_monitor.py --dashboard`
- **Performance Metrics**: `python3 scripts/monitor_performance.py`
- **Log Aggregation**: `./scripts/logs.sh all` (see `docs/LOG_VIEWER.md`)
- **Complete Guide**: `docs/OBSERVABILITY.md`

### Validation Scripts

**validate_integrations.sh** - End-to-end integration testing
```bash
./scripts/validate_integrations.sh              # Standard
./scripts/validate_integrations.sh --verbose    # Detailed
```

**validate_data_integrity.py** - Data layer validation
```bash
poetry run python3 scripts/validate_data_integrity.py
poetry run python3 scripts/validate_data_integrity.py --json
```

### Monitoring Scripts

**health_monitor.py** - Real-time health monitoring with alerting
```bash
python3 scripts/health_monitor.py --dashboard
python3 scripts/health_monitor.py --dashboard --auto-recovery
python3 scripts/health_monitor.py --alert-webhook https://hooks.slack.com/services/YOUR/WEBHOOK
```

**monitor_performance.py** - Performance monitoring with historical tracking
```bash
python3 scripts/monitor_performance.py
python3 scripts/monitor_performance.py --duration 300 --output metrics.json
```

### Log Viewing & Aggregation

**Unified log viewer** - Aggregate and filter logs from all services
```bash
# Quick commands
./scripts/logs.sh all              # View all recent logs
./scripts/logs.sh errors           # Show only errors
./scripts/logs.sh warnings         # Show only warnings
./scripts/logs.sh trace abc-123    # Trace specific correlation ID
./scripts/logs.sh follow           # Real-time tail
./scripts/logs.sh intelligence     # Intelligence service logs

# Advanced filtering
python3 scripts/view_pipeline_logs.py --correlation-id abc-123
python3 scripts/view_pipeline_logs.py --filter "❌" --level ERROR
python3 scripts/view_pipeline_logs.py --service intelligence --tail 500
python3 scripts/view_pipeline_logs.py --since 1h --no-color > logs.txt
```

**Features**:
- Aggregates logs from 8+ services
- Color-coded by log level (red=ERROR, yellow=WARNING, green=INFO, blue=DEBUG)
- Chronological merging across services
- Correlation ID tracking for tracing operations
- Real-time tailing support

**Documentation**: See `docs/LOG_VIEWER.md` for complete guide

### Monitoring Best Practices

**Production Deployment**:
1. Run `health_monitor.py --dashboard` in tmux/screen
2. Cron: `validate_integrations.sh` every 30 minutes
3. Cron: `validate_data_integrity.py` every hour
4. Weekly: `monitor_performance.py` for baselines

**Alert Thresholds**:
| Metric | Warning | Critical |
|--------|---------|----------|
| Service Health | degraded | unhealthy |
| Vector Count | No growth 24h | Decreasing |
| Cache Hit Rate | <40% | <20% |
| Consumer Lag | >100 | >500 |
| Query Time | >2s | >5s |

**Documentation**: See `docs/OBSERVABILITY.md` and `docs/VALIDATION_SCRIPT.md` for complete guides.

---

**Archon**: Production intelligence provider for AI-driven development.
