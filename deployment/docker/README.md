# OmniIntelligence Docker Deployment

## Service Ownership

**omniintelligence is a pure application service — it owns zero data stores.**

All infrastructure (PostgreSQL, Kafka/Redpanda, Valkey, Qdrant, Memgraph) is
provided by other services in the OmniNode platform. Do not run a separate
infrastructure stack from this repo.

| Infrastructure | Owned by |
|----------------|----------|
| PostgreSQL | `omnibase_infra` |
| Kafka / Redpanda | `omnibase_infra` |
| Valkey (Redis-compatible cache) | `omnibase_infra` |
| Qdrant (vector store) | `omnimemory` |
| Memgraph (knowledge graph) | `omnimemory` |

## Quick Start

### Prerequisites

1. Docker Engine 24.0+ with Compose V2
2. `omnibase_infra` running and healthy (see below)
3. A populated `.env` file (copy from `.env.example` at repo root)

### Step 1 — Start omnibase_infra

All infrastructure required by omniintelligence is owned by `omnibase_infra`.
Start it first from its own repository:

```bash
# From the omnibase_infra repo root
docker compose -f docker/docker-compose.infra.yml up -d

# Verify infrastructure is healthy before proceeding
docker compose -f docker/docker-compose.infra.yml ps
```

For Qdrant and Memgraph, start `omnimemory` as well:

```bash
# From the omnimemory repo root (if needed by your workload)
docker compose -f docker/docker-compose.yml up -d
```

### Step 2 — Start ONEX Nodes

```bash
# From the omniintelligence repo root
docker compose -f deployment/docker/docker-compose.nodes.yml up -d

# Check node health
docker compose -f deployment/docker/docker-compose.nodes.yml ps
```

The nodes attach to `omnibase-infra-network`, the external Docker network
created by `omnibase_infra`.

## Environment Variables

Set these in `.env` at the repo root. Required variables:

```bash
# PostgreSQL — provided by omnibase_infra
POSTGRES_PASSWORD=<from omnibase_infra .env>

# Valkey — provided by omnibase_infra
VALKEY_PASSWORD=<from omnibase_infra .env>

# Override connection URLs if needed (defaults point to omnibase_infra containers)
DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@omnibase-infra-postgres:5432/omnibase_infra
VALKEY_URL=redis://:${VALKEY_PASSWORD}@omnibase-infra-valkey:6379/0
```

Optional tuning variables:

```bash
# Orchestrator
MAX_CONCURRENT_WORKFLOWS=10
WORKFLOW_TIMEOUT_SECONDS=300
ENABLE_CACHING=true
CACHE_TTL_SECONDS=300

# Reducer
ENABLE_LEASE_MANAGEMENT=true
LEASE_TIMEOUT_SECONDS=300
MAX_RETRY_ATTEMPTS=3

# Logging
LOG_LEVEL=INFO
```

## ONEX Nodes

### Node Services

All nodes expose a `/health` HTTP endpoint on port 8000.

| Service | Container | Purpose |
|---------|-----------|---------|
| `intelligence-reducer` | `omni-intelligence-reducer` | FSM state management |
| `intelligence-orchestrator` | `omni-intelligence-orchestrator` | Llama Index workflow execution |
| `quality-scoring-compute` | `omni-quality-scoring-compute` | Code quality scoring |

### Build Images

```bash
# Build all node images
docker compose -f deployment/docker/docker-compose.nodes.yml build

# Build a specific node
docker compose -f deployment/docker/docker-compose.nodes.yml build intelligence-reducer
```

## Monitoring

### View Logs

```bash
# All nodes
docker compose -f deployment/docker/docker-compose.nodes.yml logs -f

# Specific node
docker compose -f deployment/docker/docker-compose.nodes.yml logs -f intelligence-reducer
```

### Health Checks

```bash
# Node health
docker compose -f deployment/docker/docker-compose.nodes.yml ps

# Manual health check
curl http://localhost:8000/health
```

## Runtime Container Integration

The `omnibase_infra` runtime container (`RuntimeHostProcess`) imports
omniintelligence handler classes dynamically via `HandlerPluginLoader`. This
requires the package to be installed in the container's Python environment.

### Verified Integration Patterns

#### Option A: Editable Install (Development)

Mount the omniintelligence source and install editable. Best for local
development where you want live code changes reflected immediately.

```dockerfile
# In Dockerfile.runtime (development variant)
COPY omniintelligence/ /opt/omniintelligence/
RUN uv pip install --system --no-cache -e /opt/omniintelligence
```

Or via docker-compose volume mount:

```yaml
# docker-compose.dev.yml
services:
  runtime:
    volumes:
      - ../omniintelligence:/opt/omniintelligence
    command: >
      sh -c "uv pip install --system -e /opt/omniintelligence && exec python -m omnibase_infra.runtime"
```

**Tradeoff**: Fast iteration, but requires source volume mount. Not suitable
for production images.

#### Option B: Wheel Install (Production)

Build a wheel and install it in the runtime container. Best for production
where reproducibility and image size matter.

```bash
# Build wheel from omniintelligence root
uv build --wheel
# Output: dist/omniintelligence-<version>-py3-none-any.whl
```

```dockerfile
# In Dockerfile.runtime (production)
# Use wildcard to avoid hardcoding the version
COPY dist/omniintelligence-*.whl /tmp/
RUN uv pip install --system --no-cache /tmp/omniintelligence-*.whl \
    && rm /tmp/omniintelligence-*.whl
```

**Tradeoff**: Clean, reproducible, minimal image. Requires wheel rebuild on
every source change.

#### Option C: Multi-Repo Docker Build Context (CI/CD)

Use Docker's multi-context builds to include both repos in a single build.
Best for CI/CD pipelines where both repos are checked out.

```bash
# Build with both repos as context
docker build \
  -f omnibase_infra/Dockerfile.runtime \
  --build-context omniintelligence=./omniintelligence \
  ./omnibase_infra
```

```dockerfile
# In Dockerfile.runtime
FROM python:3.12-slim AS base
# ... base setup ...

# Install omniintelligence from sibling repo context (non-editable for CI/CD)
COPY --from=omniintelligence pyproject.toml /opt/omniintelligence/pyproject.toml
COPY --from=omniintelligence src/ /opt/omniintelligence/src/
RUN uv pip install --system --no-cache /opt/omniintelligence
```

**Tradeoff**: Cleanest CI/CD integration, but requires Docker BuildKit and
both repos available at build time.

### Verifying Installation

After installing omniintelligence in the runtime container, verify handler
discovery works:

```bash
# Inside the container
python -c "
from omniintelligence.nodes.node_quality_scoring_compute.handlers import handle_quality_scoring_compute
from omniintelligence.nodes.node_claude_hook_event_effect.handlers import HandlerClaudeHookEvent
print('Handler imports OK')
"
```

### Package Dependencies

The base `pip install omniintelligence` (PEP 621 dependencies) installs
runtime deps including pydantic, httpx, pyyaml, and confluent-kafka. Note
that `confluent-kafka` is a C extension wrapping librdkafka; on slim
container images (e.g., `python:3.12-slim`) you may need build tools or a
pre-built wheel. Heavy ML and database deps like torch, sentence-transformers,
asyncpg, and qdrant-client are in the `core` dependency group:

```bash
# Minimal install (handler classes + Kafka client, no ML/DB)
uv pip install --system -e .

# Full install (all infrastructure deps via uv sync)
uv sync --group core
```

For the runtime container, the minimal install is sufficient since
`RuntimeHostProcess` provides its own infrastructure (PostgreSQL, etc.)
connections. Kafka connectivity is included in the base install because
handler modules import Kafka types at module load time.

## Troubleshooting

### Node Cannot Connect to PostgreSQL

Verify `omnibase_infra` is running and healthy:

```bash
# Check omnibase_infra postgres
docker ps | grep omnibase-infra-postgres

# Test connection
psql -h localhost -p 5436 -U postgres -d omnibase_infra -c "SELECT 1"
```

Ensure `DATABASE_URL` in your `.env` points to the correct host:
- Docker service-to-service: `omnibase-infra-postgres:5432`
- Host scripts: `localhost:5436`

### Node Cannot Connect to Kafka

Redpanda runs on the **remote M2 Ultra (192.168.86.200)**, not locally. Verify
`KAFKA_BOOTSTRAP_SERVERS` is set correctly:
- Docker services: `omnibase-infra-redpanda:9092` (via `/etc/hosts` DNS)
- Host scripts: `192.168.86.200:29092`

### Network Not Found

If nodes fail to start because `omnibase-infra-network` does not exist, start
`omnibase_infra` first:

```bash
docker compose -f <omnibase_infra>/docker/docker-compose.infra.yml up -d
```

### Reset Nodes

```bash
# Stop and remove node containers only (does NOT touch infrastructure)
docker compose -f deployment/docker/docker-compose.nodes.yml down
```

**Never run `docker compose down -v` from this directory.** There are no
volumes owned by omniintelligence. Infrastructure data lives in
`omnibase_infra` volumes.

## Support

For issues or questions:
- GitHub Issues: https://github.com/OmniNode-ai/omniintelligence/issues
- Documentation: See `docs/` directory
