# ADR-001: Service Ownership Boundaries Between OmniNode Repositories

**Status**: Proposed
**Date**: 2025-11-05
**Decision Makers**: Architecture Team
**Correlation ID**: 037c3561-9f57-47a4-9745-8fc71fc08bab
**Priority**: HIGH

## Context

### Problem Statement

The OmniNode platform currently lacks documented architectural boundaries between repositories, specifically between **omniarchon** (intelligence provider) and **omniclaude** (AI agent orchestration). This has resulted in:

1. **Cross-Repository Coupling**: omniclaude services directly depend on omniarchon infrastructure (e.g., `omniclaude_archon_router_consumer` requiring edits to `omniarchon/docker-compose.yml`)
2. **Unclear Ownership**: Ambiguity about which repository owns which services
3. **Maintenance Confusion**: Uncertainty about where to fix issues and add features
4. **Deployment Complexity**: No clear strategy for independent deployment
5. **Configuration Duplication**: Environment variables and configuration spread across repositories

### Current Infrastructure Landscape

**omniarchon Repository** (Intelligence Provider):
- **Core Services**: archon-intelligence (8053), archon-bridge (8054), archon-search (8055)
- **AI/ML**: archon-langextract (8156), archon-agents (8052)
- **Frontend**: archon-frontend (3737)
- **Data Layer**: qdrant (6333/6334), memgraph (7687), archon-valkey (6379)
- **Purpose**: Code intelligence, RAG, pattern learning, quality assessment

**omniclaude Repository** (Agent Orchestration):
- **Core Services**: Claude Code CLI, agent system, workflow orchestration
- **Infrastructure**: omniclaude_archon_router_consumer (Kafka consumer)
- **Purpose**: AI agent coordination, task execution, LLM orchestration

**omninode_bridge Repository** (Shared Infrastructure):
- **Event Bus**: omninode-bridge-redpanda (Kafka/Redpanda) at 192.168.86.200:9092/29092
- **Database**: omninode-bridge-postgres (PostgreSQL) at 192.168.86.200:5432/5436
- **Indexing**: omninode-bridge-onextree (8058)
- **Metadata**: omninode-bridge-metadata-stamping (8057)
- **Purpose**: Shared infrastructure for all OmniNode services

### Key Issues Identified

1. **omniclaude services defined in omniarchon docker-compose** - Violates separation of concerns
2. **No service discovery mechanism** - Hard-coded endpoints in environment variables
3. **Shared Kafka topics without ownership** - Unclear who owns which topics
4. **Database schema shared without contracts** - Direct database access across repositories
5. **Configuration spread** - `.env` files duplicated across repositories

## Decision

We establish **clear service ownership boundaries** based on the **Single Responsibility Principle** and **12-Factor App** methodology.

### Service Ownership Matrix

| Service | Owner Repository | Type | Port(s) | Dependencies | Access Pattern |
|---------|-----------------|------|---------|--------------|----------------|
| **Intelligence Services** |
| archon-intelligence | omniarchon | Core | 8053 | Kafka, PostgreSQL, Qdrant | HTTP API + Events |
| archon-bridge | omniarchon | Core | 8054 | Kafka | HTTP API + Events |
| archon-search | omniarchon | Core | 8055 | Qdrant, Memgraph | HTTP API |
| archon-langextract | omniarchon | Auxiliary | 8156 | None | HTTP API |
| archon-agents | omniarchon | Auxiliary | 8052 | Kafka, Intelligence | HTTP API + Events |
| archon-frontend | omniarchon | UI | 3737 | Intelligence, Search | HTTP |
| archon-valkey | omniarchon | Data | 6379 | None | Redis Protocol |
| qdrant | omniarchon | Data | 6333/6334 | None | gRPC/HTTP |
| memgraph | omniarchon | Data | 7687 | None | Bolt Protocol |
| **Agent Services** |
| omniclaude CLI | omniclaude | Core | - | Archon APIs | CLI |
| omniclaude Agent System | omniclaude | Core | - | Archon APIs, Kafka | CLI + Events |
| omniclaude Router Consumer | omniclaude | Auxiliary | - | Kafka, PostgreSQL | Events Only |
| **Shared Infrastructure** |
| omninode-bridge-redpanda | omninode_bridge | Infrastructure | 9092/29092 | None | Kafka Protocol |
| omninode-bridge-postgres | omninode_bridge | Infrastructure | 5432/5436 | None | PostgreSQL |
| omninode-bridge-onextree | omninode_bridge | Infrastructure | 8058 | Kafka, PostgreSQL | HTTP API + Events |
| omninode-bridge-metadata | omninode_bridge | Infrastructure | 8057 | Kafka, PostgreSQL | HTTP API + Events |

### Ownership Principles

#### 1. Repository Responsibilities

**omniarchon (Intelligence Provider)**:
- ✅ **OWNS**: Intelligence APIs, vector search, pattern learning, quality assessment
- ✅ **PROVIDES**: HTTP APIs for intelligence consumption, event-based intelligence generation
- ❌ **DOES NOT OWN**: Agent orchestration, CLI tooling, workflow coordination

**omniclaude (Agent Orchestration)**:
- ✅ **OWNS**: Claude Code CLI, agent system, workflow orchestration, task execution
- ✅ **PROVIDES**: AI agent coordination, LLM orchestration
- ✅ **CONSUMES**: Archon intelligence via HTTP APIs and Kafka events
- ❌ **DOES NOT OWN**: Intelligence generation, vector databases, pattern storage

**omninode_bridge (Shared Infrastructure)**:
- ✅ **OWNS**: Kafka/Redpanda, PostgreSQL, tree indexing, metadata stamping
- ✅ **PROVIDES**: Event bus, persistent storage, shared services
- ❌ **DOES NOT OWN**: Application logic, domain-specific services

#### 2. Service Type Classifications

**Core Services**: Essential to repository's primary function
- Deployment: Required for repository to function
- Lifecycle: Managed by owning repository
- Configuration: Repository-specific `.env`

**Auxiliary Services**: Support core services
- Deployment: Optional or environment-dependent
- Lifecycle: Managed by owning repository
- Configuration: Repository-specific `.env`

**Infrastructure Services**: Shared across repositories
- Deployment: Always remote (192.168.86.200)
- Lifecycle: Managed by omninode_bridge
- Configuration: Global `.env` (referenced by all repositories)

### Dependency Rules

#### Rule 1: No Direct Cross-Repository Service Dependencies

❌ **PROHIBITED**:
```yaml
# In omniarchon/docker-compose.yml
services:
  omniclaude-service:  # ❌ Wrong repository!
    image: omniclaude-agent
    depends_on:
      - archon-intelligence  # ❌ Cross-repo dependency
```

✅ **CORRECT**:
```yaml
# In omniclaude/docker-compose.yml
services:
  omniclaude-agent:
    image: omniclaude-agent
    environment:
      ARCHON_INTELLIGENCE_URL: http://192.168.86.101:8053  # ✅ External URL
      KAFKA_BOOTSTRAP_SERVERS: 192.168.86.200:29092  # ✅ Shared infra
```

#### Rule 2: Service Discovery via Environment Configuration

**Discovery Mechanism**: Environment-based configuration (12-factor compliant)

```bash
# omniclaude/.env
ARCHON_INTELLIGENCE_URL=http://192.168.86.101:8053
ARCHON_SEARCH_URL=http://192.168.86.101:8055
ARCHON_BRIDGE_URL=http://192.168.86.101:8054
KAFKA_BOOTSTRAP_SERVERS=192.168.86.200:29092
POSTGRES_HOST=192.168.86.200
POSTGRES_PORT=5436
```

**Rationale**:
- ✅ Simple, well-understood pattern
- ✅ No additional infrastructure (no Consul needed yet)
- ✅ Easy to override for testing (localhost ports)
- ✅ Compatible with Docker, Kubernetes, bare metal

**Future Migration Path**: When service count exceeds ~20 services, consider Consul/service mesh.

#### Rule 3: Cross-Repository Communication Patterns

**Synchronous (HTTP APIs)**:
- **Use Case**: Request/response, immediate results needed
- **Pattern**: REST APIs with explicit contracts
- **Example**: omniclaude calls `POST /assess/code` on archon-intelligence
- **Versioning**: API versioning in URL (`/api/v1/...`)

**Asynchronous (Kafka Events)**:
- **Use Case**: Fire-and-forget, eventual consistency, decoupling
- **Pattern**: Event-driven with topic ownership (see Topic Ownership below)
- **Example**: omniclaude publishes `agent.routing.completed.v1`, archon-intelligence consumes
- **Versioning**: Event schema versioning in topic name (`*.v1`, `*.v2`)

❌ **PROHIBITED**:
- Direct database access across repositories (except via shared infrastructure)
- Shared in-memory state (e.g., Redis keys without prefix)
- File system coupling (shared volumes)

#### Rule 4: Kafka Topic Ownership

**Topic Naming Convention**: `<environment>.<owner-repo>.<domain>.<event-type>.<version>`

**Examples**:
```
dev.archon-intelligence.intelligence.code-analysis-requested.v1
dev.archon-intelligence.intelligence.code-analysis-completed.v1
dev.omniclaude.agent.routing.requested.v1
dev.omniclaude.agent.routing.completed.v1
```

**Ownership Rules**:
1. **Producer Owns Topic**: Repository that publishes events owns the topic
2. **Schema Governance**: Topic owner defines event schema (Avro/JSON Schema)
3. **Backward Compatibility**: Schema changes must be backward compatible
4. **Consumer Independence**: Consumers can't dictate topic schema

**Topic Registry** (to be created):
```yaml
# kafka-topics.yml (in omninode_bridge repository)
topics:
  - name: dev.archon-intelligence.intelligence.code-analysis-requested.v1
    owner: omniarchon
    schema: schemas/code-analysis-requested-v1.avsc
    partitions: 3
    replication: 1
    consumers:
      - omniarchon (archon-intelligence)
      - omniclaude (omniclaude-router-consumer)
```

### Deployment Model

#### Each Repository Has Independent docker-compose.yml

**Principle**: Each repository can be deployed independently with external dependencies.

**omniarchon/docker-compose.yml**:
```yaml
version: '3.8'
services:
  # Core services
  archon-intelligence:
    build: ./services/intelligence
    ports:
      - "8053:8053"
    environment:
      KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
      POSTGRES_HOST: ${POSTGRES_HOST}
      POSTGRES_PORT: ${POSTGRES_PORT}
    networks:
      - app-network
      - omninode-bridge-network  # External network for shared infrastructure

  archon-bridge:
    build: ./services/bridge
    # ...

  # Local data stores
  qdrant:
    image: qdrant/qdrant
    # ...

networks:
  app-network:
    driver: bridge
  omninode-bridge-network:
    external: true  # Connects to shared infrastructure
```

**omniclaude/docker-compose.yml**:
```yaml
version: '3.8'
services:
  omniclaude-router-consumer:
    build: ./services/router-consumer
    environment:
      ARCHON_INTELLIGENCE_URL: ${ARCHON_INTELLIGENCE_URL}
      KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
      POSTGRES_HOST: ${POSTGRES_HOST}
    networks:
      - app-network
      - omninode-bridge-network  # External network for shared infrastructure

networks:
  app-network:
    driver: bridge
  omninode-bridge-network:
    external: true
```

#### Shared Infrastructure (omninode_bridge)

**Deployment**: Always remote (192.168.86.200)

**omninode_bridge/docker-compose.yml**:
```yaml
version: '3.8'
services:
  omninode-bridge-redpanda:
    image: vectorized/redpanda
    ports:
      - "9092:9092"   # Internal
      - "29092:29092" # External
    # ...

  omninode-bridge-postgres:
    image: postgres:15
    ports:
      - "5432:5432"   # Internal
      - "5436:5436"   # External
    # ...

networks:
  omninode-bridge-network:
    driver: bridge
```

#### Network Architecture

**DNS Resolution** (`/etc/hosts` on all dev machines):
```bash
192.168.86.200 omninode-bridge-redpanda
192.168.86.200 omninode-bridge-postgres
192.168.86.200 omninode-bridge-onextree
192.168.86.200 omninode-bridge-metadata
```

**Port Strategy**:
- **Internal Ports** (9092, 5432): For Docker-to-Docker communication
- **External Ports** (29092, 5436): For host scripts and cross-machine access

**Service Access Patterns**:
```
┌──────────────────────────────────────────────────────────┐
│ Developer Machine (192.168.86.101)                       │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ omniarchon (Docker)                                 │  │
│ │   archon-intelligence → Kafka (9092 via DNS)       │  │
│ │   archon-intelligence → PostgreSQL (5432 via DNS)  │  │
│ └─────────────────────────────────────────────────────┘  │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ omniclaude (Docker)                                 │  │
│ │   router-consumer → Kafka (9092 via DNS)           │  │
│ │   router-consumer → PostgreSQL (5432 via DNS)      │  │
│ │   router-consumer → archon-intelligence (HTTP)     │  │
│ └─────────────────────────────────────────────────────┘  │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ Host Scripts                                        │  │
│ │   bulk_ingest.py → Kafka (192.168.86.200:29092)   │  │
│ │   psql → PostgreSQL (192.168.86.200:5436)         │  │
│ └─────────────────────────────────────────────────────┘  │
└───────────────────────┬──────────────────────────────────┘
                        │
                        │ Network
                        ↓
┌──────────────────────────────────────────────────────────┐
│ Infrastructure Server (192.168.86.200)                    │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ omninode_bridge (Docker)                            │  │
│ │   Redpanda (9092 internal, 29092 external)         │  │
│ │   PostgreSQL (5432 internal, 5436 external)        │  │
│ │   OnexTree (8058)                                   │  │
│ │   Metadata Stamping (8057)                          │  │
│ └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Configuration Management

#### Environment Variable Hierarchy

**Level 1: Global Shared Infrastructure** (`~/.claude/CLAUDE.md` reference):
```bash
# Shared infrastructure endpoints (ALL repositories reference these)
KAFKA_BOOTSTRAP_SERVERS=<varies by context>
POSTGRES_HOST=192.168.86.200
POSTGRES_PORT=5436
POSTGRES_DATABASE=omninode_bridge
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<secret>
```

**Level 2: Repository-Specific** (`.env` in each repository):
```bash
# omniarchon/.env
INTELLIGENCE_SERVICE_PORT=8053
BRIDGE_SERVICE_PORT=8054
SEARCH_SERVICE_PORT=8055
QDRANT_URL=http://qdrant:6333
MEMGRAPH_URI=bolt://memgraph:7687

# omniclaude/.env
ARCHON_INTELLIGENCE_URL=http://192.168.86.101:8053
ARCHON_SEARCH_URL=http://192.168.86.101:8055
ARCHON_BRIDGE_URL=http://192.168.86.101:8054
```

**Level 3: Environment-Specific Overrides** (`.env.local`, `.env.production`):
```bash
# omniarchon/.env.local (for local development)
ARCHON_INTELLIGENCE_URL=http://localhost:8053

# omniarchon/.env.production (for production)
ARCHON_INTELLIGENCE_URL=http://archon.production.example.com
```

#### Configuration File Strategy

**Each Repository Has**:
- ✅ `.env.example` - Template with all variables (checked into git)
- ✅ `.env` - Actual values (gitignored, copied from `.env.example`)
- ✅ `.env.local` - Local overrides (gitignored, optional)
- ✅ `config/` directory - Pydantic Settings classes for validation

**NO Configuration Duplication**: If a value is in `~/.claude/CLAUDE.md`, it should NOT be duplicated in repository `.env.example` (reference only).

#### Configuration Loading Order (Pydantic)

```python
# config/settings.py (in each repository)
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Shared infrastructure (from environment)
    kafka_bootstrap_servers: str = Field(env="KAFKA_BOOTSTRAP_SERVERS")
    postgres_host: str = Field(env="POSTGRES_HOST")
    postgres_port: int = Field(env="POSTGRES_PORT")

    # Repository-specific
    intelligence_service_port: int = Field(default=8053, env="INTELLIGENCE_SERVICE_PORT")

    # External service URLs (for cross-repo communication)
    archon_intelligence_url: str = Field(
        default="http://localhost:8053",
        env="ARCHON_INTELLIGENCE_URL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars
```

#### Secrets Management

**Current**: Environment variables in `.env` files (gitignored)

**Future** (when needed):
- HashiCorp Vault integration (already available at 192.168.86.200:8200)
- Kubernetes Secrets (if migrating to k8s)
- AWS Secrets Manager (if deploying to AWS)

**Security Rules**:
- ❌ NEVER commit secrets to git (enforce with pre-commit hooks)
- ✅ Use `.env.example` with placeholder values
- ✅ Document secret sources in README.md
- ✅ Rotate secrets regularly (quarterly)

### API Contracts & Versioning

#### HTTP API Contracts

**Contract Definition**: OpenAPI 3.0 specification

**Location**: `<repository>/docs/api/openapi.yaml`

**Example**:
```yaml
# omniarchon/docs/api/openapi.yaml
openapi: 3.0.0
info:
  title: Archon Intelligence API
  version: 1.0.0
paths:
  /api/v1/assess/code:
    post:
      summary: Assess code quality
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CodeAssessmentRequest'
      responses:
        '200':
          description: Assessment completed
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CodeAssessmentResponse'
```

**Contract Validation**:
- Generate Pydantic models from OpenAPI: `datamodel-codegen --input openapi.yaml --output models.py`
- Validate requests/responses at runtime with FastAPI
- CI/CD: Fail builds if API changes break contracts

**Versioning Strategy**:
- **URL Versioning**: `/api/v1/...`, `/api/v2/...`
- **Backward Compatibility Window**: 6 months (v1 supported while v2 exists)
- **Deprecation Notice**: 3 months before removal

#### Event Schemas (Kafka)

**Schema Definition**: Avro or JSON Schema

**Location**: `<repository>/schemas/<topic-name>.avsc`

**Example**:
```json
// omniarchon/schemas/code-analysis-completed-v1.avsc
{
  "type": "record",
  "name": "CodeAnalysisCompleted",
  "namespace": "dev.archon.intelligence",
  "fields": [
    {"name": "analysis_id", "type": "string"},
    {"name": "project_name", "type": "string"},
    {"name": "file_path", "type": "string"},
    {"name": "quality_score", "type": "double"},
    {"name": "timestamp", "type": "long"}
  ]
}
```

**Schema Registry** (future):
- Confluent Schema Registry (when event volume grows)
- Schema validation on publish/consume
- Automated compatibility checks

**Versioning Strategy**:
- **Topic Name Versioning**: `*.v1`, `*.v2` (separate topics)
- **Schema Evolution**: Backward/forward compatible changes only
- **Breaking Changes**: New topic version

### Communication Examples

#### Example 1: omniclaude Requests Code Assessment

**Scenario**: omniclaude agent needs to assess code quality before committing

**Synchronous HTTP Request**:
```python
# omniclaude/agents/quality_agent.py
import httpx
from config import settings

async def assess_code_quality(file_path: str, content: str) -> dict:
    """Call Archon Intelligence API for code assessment"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.archon_intelligence_url}/api/v1/assess/code",
            json={
                "file_path": file_path,
                "content": content,
                "project_name": settings.project_name
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
```

**Why Synchronous**: Agent needs immediate assessment to decide whether to commit.

#### Example 2: omniarchon Publishes Intelligence Events

**Scenario**: archon-intelligence completes code analysis, publishes event for consumers

**Asynchronous Event Publication**:
```python
# omniarchon/services/intelligence/src/events/publisher.py
from aiokafka import AIOKafkaProducer
import json

async def publish_code_analysis_completed(analysis_result: dict):
    """Publish code analysis completion event"""
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    await producer.start()
    try:
        await producer.send_and_wait(
            topic="dev.archon-intelligence.intelligence.code-analysis-completed.v1",
            value={
                "analysis_id": analysis_result["id"],
                "project_name": analysis_result["project_name"],
                "file_path": analysis_result["file_path"],
                "quality_score": analysis_result["quality_score"],
                "timestamp": int(time.time() * 1000)
            }
        )
    finally:
        await producer.stop()
```

**Why Asynchronous**: Other services (omniclaude, analytics) may want to react, but archon-intelligence doesn't need to wait.

#### Example 3: omniclaude Consumes Intelligence Events

**Scenario**: omniclaude router consumer tracks code quality trends

**Asynchronous Event Consumption**:
```python
# omniclaude/services/router_consumer/consumer.py
from aiokafka import AIOKafkaConsumer
import json

async def consume_code_analysis_events():
    """Consume code analysis completion events from Archon"""
    consumer = AIOKafkaConsumer(
        "dev.archon-intelligence.intelligence.code-analysis-completed.v1",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="omniclaude-router-consumer",
        value_deserializer=lambda v: json.loads(v.decode('utf-8'))
    )
    await consumer.start()
    try:
        async for message in consumer:
            event = message.value
            # Process event (e.g., update quality trends, trigger alerts)
            await process_code_analysis_event(event)
    finally:
        await consumer.stop()
```

**Why Asynchronous**: Decouples omniclaude from archon-intelligence execution timeline.

## Consequences

### Positive Consequences

1. **Clear Ownership**
   - ✅ Developers know which repository to modify for specific functionality
   - ✅ Reduces merge conflicts across repositories
   - ✅ Enables independent release cycles

2. **Independent Deployment**
   - ✅ Each repository can be deployed without affecting others
   - ✅ Faster iteration cycles (deploy omniclaude without rebuilding omniarchon)
   - ✅ Reduced deployment risk (smaller blast radius)

3. **Scalability**
   - ✅ Services can be scaled independently based on load
   - ✅ Horizontal scaling via Kafka consumer groups
   - ✅ Clear path to microservices architecture

4. **Maintainability**
   - ✅ Smaller, focused codebases per repository
   - ✅ Easier onboarding (developers only need to understand their repository)
   - ✅ Reduced cognitive load

5. **Testing**
   - ✅ Services can be tested independently with mocked dependencies
   - ✅ Contract testing ensures API compatibility
   - ✅ Faster CI/CD pipelines (only rebuild changed repository)

### Negative Consequences

1. **Increased Coordination**
   - ❌ API changes require coordination across repositories
   - ❌ Event schema changes need backward compatibility planning
   - **Mitigation**: API versioning, schema evolution rules, changelog automation

2. **Configuration Duplication**
   - ❌ Similar environment variables repeated across repositories
   - **Mitigation**: Reference `~/.claude/CLAUDE.md` for shared config, DRY principle

3. **Debugging Complexity**
   - ❌ Distributed tracing needed for cross-repository workflows
   - **Mitigation**: Correlation IDs in all logs/events, centralized logging (future)

4. **Network Latency**
   - ❌ HTTP calls between repositories add latency vs in-process calls
   - **Mitigation**: Caching (Valkey), async patterns, event-driven for non-critical paths

5. **Migration Effort**
   - ❌ Existing cross-repository dependencies need refactoring
   - **Mitigation**: Phased migration (see Implementation Plan below)

### Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| API breaking changes | HIGH | MEDIUM | Versioning + 6-month compatibility window |
| Event schema conflicts | MEDIUM | LOW | Schema registry + automated validation |
| Service discovery failures | HIGH | LOW | DNS + fallback to localhost + health checks |
| Configuration drift | MEDIUM | MEDIUM | Automated config validation + CI checks |
| Deployment order dependencies | LOW | MEDIUM | Independent deployments + graceful degradation |

## Implementation Plan

### Phase 1: Documentation & Contracts (Week 1)

**Goal**: Establish contracts without breaking existing functionality

**Tasks**:
1. ✅ Create this ADR document
2. 🔲 Create OpenAPI specifications for all Archon APIs
   - `omniarchon/docs/api/intelligence-v1.yaml`
   - `omniarchon/docs/api/search-v1.yaml`
   - `omniarchon/docs/api/bridge-v1.yaml`
3. 🔲 Create Kafka topic registry
   - `omninode_bridge/docs/kafka-topics.yml`
4. 🔲 Document event schemas (Avro/JSON Schema)
   - `omniarchon/schemas/*.avsc`
   - `omniclaude/schemas/*.avsc`
5. 🔲 Update `~/.claude/CLAUDE.md` with service discovery patterns
6. 🔲 Create `ARCHITECTURE.md` in each repository linking to this ADR

**Validation**: All contracts documented, no code changes yet

### Phase 2: Configuration Consolidation (Week 2)

**Goal**: Eliminate configuration duplication

**Tasks**:
1. 🔲 Audit all `.env` files across repositories
   - Identify duplicated variables
   - Identify missing variables
2. 🔲 Create Pydantic Settings classes in each repository
   - `omniarchon/config/settings.py`
   - `omniclaude/config/settings.py`
3. 🔲 Consolidate shared infrastructure config in `~/.claude/CLAUDE.md`
4. 🔲 Add configuration validation to CI/CD
   - `pre-commit` hook to validate `.env` against `.env.example`
   - CI check for required environment variables
5. 🔲 Update all service code to use Pydantic Settings
   - Replace `os.getenv()` with `settings.variable_name`

**Validation**: CI passes, all services start with new configuration

### Phase 3: Service Relocation (Week 3-4)

**Goal**: Move misplaced services to correct repositories

**Tasks**:
1. 🔲 Move `omniclaude_archon_router_consumer` from omniarchon to omniclaude
   - Copy service code to `omniclaude/services/router-consumer/`
   - Create `omniclaude/docker-compose.yml` (if doesn't exist)
   - Update service to use external URLs for Archon services
   - Test independently
   - Remove from `omniarchon/docker-compose.yml`
2. 🔲 Verify no other services in wrong repository
3. 🔲 Update CI/CD pipelines for new locations

**Validation**: Each repository can be deployed independently

### Phase 4: API Versioning Implementation (Week 5)

**Goal**: Implement versioned APIs with backward compatibility

**Tasks**:
1. 🔲 Add `/api/v1/` prefix to all Archon Intelligence APIs
   - Keep legacy routes for 6 months with deprecation warnings
2. 🔲 Add API versioning middleware
   - Log API version usage
   - Return deprecation headers
3. 🔲 Update all consumers to use versioned endpoints
4. 🔲 Add OpenAPI validation to FastAPI routes

**Validation**: All API calls use versioned endpoints, OpenAPI spec matches implementation

### Phase 5: Event Schema Validation (Week 6)

**Goal**: Validate event schemas on publish/consume

**Tasks**:
1. 🔲 Add Avro/JSON Schema validation to Kafka producers
2. 🔲 Add schema validation to Kafka consumers
3. 🔲 Add schema compatibility checks to CI/CD
4. 🔲 Create schema migration guide

**Validation**: All events validated against schemas, CI catches breaking changes

### Phase 6: Testing & Rollout (Week 7-8)

**Goal**: Validate architecture with comprehensive testing

**Tasks**:
1. 🔲 Create integration tests for cross-repository communication
   - Test HTTP API calls
   - Test Kafka event flows
2. 🔲 Create contract tests
   - Pact/Spring Cloud Contract for APIs
   - Schema validation for events
3. 🔲 Update monitoring/observability
   - Add correlation IDs to all logs
   - Add distributed tracing (Jaeger/Zipkin) if needed
4. 🔲 Deploy to staging environment
5. 🔲 Load testing
6. 🔲 Deploy to production
7. 🔲 Retrospective & lessons learned

**Validation**: All tests pass, production deployment successful, no regressions

## Rollback Plan

If major issues arise during implementation:

1. **API Versioning**: Keep legacy endpoints active (already planned for 6 months)
2. **Service Relocation**: Restore service to original repository, update docker-compose
3. **Configuration Changes**: Revert to original `.env` files, restore `os.getenv()` calls
4. **Event Schema Validation**: Make validation non-blocking (log errors only)

**Rollback Trigger**: >5% error rate increase OR >2x latency increase OR service downtime >5 minutes

## Monitoring & Success Metrics

### Key Metrics

**Service Independence**:
- ✅ **Target**: Each repository deploys independently without modifying others
- **Measure**: Deployment log analysis (no cross-repository file changes)

**API Contract Adherence**:
- ✅ **Target**: 100% API calls use versioned endpoints
- **Measure**: API gateway logs, deprecation warning counts

**Configuration Correctness**:
- ✅ **Target**: Zero configuration-related incidents
- **Measure**: Incident tracking (configuration errors)

**Event Schema Compliance**:
- ✅ **Target**: 100% events pass schema validation
- **Measure**: Kafka producer/consumer metrics

**Cross-Repository Communication Latency**:
- ✅ **Target**: p95 < 500ms for HTTP calls, p99 < 1000ms
- **Measure**: HTTP client metrics (histogram)

### Monitoring Dashboard

Create Grafana dashboard with:
- Service health per repository
- API latency per endpoint (versioned)
- Kafka consumer lag per topic
- Configuration validation failures
- Cross-repository dependency graph

## Future Enhancements

### Short-Term (3-6 months)

1. **Service Mesh** (when >20 services):
   - Istio or Linkerd for service discovery
   - Mutual TLS between services
   - Advanced traffic routing (canary, blue-green)

2. **Schema Registry**:
   - Confluent Schema Registry for Kafka
   - Automated schema evolution
   - Schema compatibility enforcement

3. **Distributed Tracing**:
   - Jaeger or Zipkin
   - End-to-end request tracing
   - Performance bottleneck identification

### Long-Term (6-12 months)

1. **API Gateway**:
   - Kong or Traefik
   - Centralized API management
   - Rate limiting, authentication, logging

2. **Kubernetes Migration**:
   - Container orchestration
   - Auto-scaling
   - Self-healing deployments

3. **GitOps**:
   - ArgoCD or Flux
   - Declarative infrastructure
   - Automated rollbacks

## References

### Internal Documentation

- `~/.claude/CLAUDE.md` - Shared OmniNode infrastructure
- `omniarchon/CLAUDE.md` - Archon-specific architecture
- `omniarchon/docs/CONFIG_FIXES_SUMMARY.md` - Configuration consolidation details
- `omniarchon/docs/CONFIG_AUDIT_REPORT.md` - Configuration audit findings

### External Resources

- [12-Factor App Methodology](https://12factor.net/) - Configuration, dependencies, backing services
- [Semantic Versioning 2.0](https://semver.org/) - API versioning
- [Avro Schema Evolution](https://docs.confluent.io/platform/current/schema-registry/avro.html) - Event schema compatibility
- [OpenAPI 3.0 Specification](https://swagger.io/specification/) - API contracts
- [Martin Fowler - Microservices](https://martinfowler.com/articles/microservices.html) - Architecture patterns

### Related ADRs (Future)

- ADR-002: Event Schema Evolution Strategy
- ADR-003: Service Mesh Migration Plan
- ADR-004: Secrets Management Strategy
- ADR-005: Observability & Monitoring Architecture

## Approval & Review

**Proposed By**: Architecture Team
**Reviewers Required**:
- [ ] Lead Architect (omniarchon)
- [ ] Lead Architect (omniclaude)
- [ ] Infrastructure Lead (omninode_bridge)
- [ ] DevOps Lead

**Review Criteria**:
1. Service ownership matrix is clear and unambiguous
2. Dependency rules are enforceable in CI/CD
3. Deployment model supports independent releases
4. Communication patterns handle failure gracefully
5. Implementation plan is realistic and phased
6. Rollback plan minimizes risk

**Decision Date**: [TBD]
**Status After Review**: [Proposed → Accepted/Rejected/Modified]

---

**Document Version**: 1.0
**Last Updated**: 2025-11-05
**Next Review**: 2025-11-12 (1 week after proposal)
