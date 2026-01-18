# OmniIntelligence Docker Deployment

Comprehensive Docker deployment for ONEX 4.0 architecture.

## Architecture

### Base Infrastructure (docker-compose.yml)
- **PostgreSQL**: FSM state, pattern lineage, workflow tracking
- **Qdrant**: Vector embeddings (1536D)
- **Memgraph**: Knowledge graph (entities + relationships)
- **Valkey**: Distributed cache (Redis-compatible)
- **Redpanda**: Kafka-compatible event streaming

### ONEX Nodes (docker-compose.nodes.yml)
- **Intelligence Reducer**: Pure FSM state management
- **Intelligence Orchestrator**: Llama Index workflow execution
- **Compute Nodes**: Vectorization, Quality Scoring, etc.
- **Effect Nodes**: Kafka Events, Qdrant Vectors, Memgraph Graph, PostgreSQL Patterns

## Quick Start

### Prerequisites

1. Docker Engine 24.0+ with Compose V2
2. 8GB+ available RAM
3. Create `.env` file:

```bash
cp .env.example .env
# Edit .env and set required passwords
```

### Start Infrastructure

```bash
# Start base infrastructure
docker compose -f deployment/docker/docker-compose.yml up -d

# Check health
docker compose -f deployment/docker/docker-compose.yml ps

# View logs
docker compose -f deployment/docker/docker-compose.yml logs -f
```

### Start ONEX Nodes

```bash
# Start all ONEX nodes
docker compose -f deployment/docker/docker-compose.yml \
               -f deployment/docker/docker-compose.nodes.yml up -d

# Check node health
docker compose -f deployment/docker/docker-compose.nodes.yml ps
```

### Apply Database Migrations

```bash
# Run migrations
docker compose -f deployment/docker/docker-compose.yml exec postgres \
  psql -U postgres -d omniintelligence -f /docker-entrypoint-initdb.d/001_create_fsm_state_table.sql

# Or use migration script
docker compose -f deployment/docker/docker-compose.yml run --rm \
  -e DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/omniintelligence \
  python python scripts/migration/apply_migrations.py
```

## Environment Variables

### Required Variables

```bash
# Database passwords (REQUIRED)
POSTGRES_PASSWORD=your_secure_password_here
VALKEY_PASSWORD=your_valkey_password_here

# API keys (if using external services)
OPENAI_API_KEY=sk-...
```

### Optional Variables

```bash
# PostgreSQL
POSTGRES_DB=omniintelligence
POSTGRES_USER=postgres
POSTGRES_PORT=5432

# Qdrant
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334

# Memgraph
MEMGRAPH_PORT=7687
MEMGRAPH_HTTP_PORT=3000

# Valkey
VALKEY_PORT=6379

# Redpanda
REDPANDA_KAFKA_PORT=19092
REDPANDA_ADMIN_PORT=9644

# Orchestrator
MAX_CONCURRENT_WORKFLOWS=10
WORKFLOW_TIMEOUT_SECONDS=300

# Reducer
ENABLE_LEASE_MANAGEMENT=true
LEASE_TIMEOUT_SECONDS=300

# Logging
LOG_LEVEL=INFO
```

## Service URLs

### Infrastructure
- PostgreSQL: `localhost:5432`
- Qdrant: `http://localhost:6333`
- Memgraph Lab: `http://localhost:3000`
- Valkey: `localhost:6379`
- Redpanda Console: `http://localhost:8080`
- Redpanda Kafka: `localhost:19092`

### ONEX Nodes
All nodes expose health checks on port 8000.

## Monitoring

### View Logs

```bash
# All services
docker compose -f deployment/docker/docker-compose.yml logs -f

# Specific service
docker compose -f deployment/docker/docker-compose.yml logs -f postgres

# Nodes
docker compose -f deployment/docker/docker-compose.nodes.yml logs -f intelligence-reducer
```

### Health Checks

```bash
# Check infrastructure health
docker compose -f deployment/docker/docker-compose.yml ps

# Check node health
docker compose -f deployment/docker/docker-compose.nodes.yml ps

# Manual health check
curl http://localhost:6333/health  # Qdrant
```

### Database Queries

```bash
# Connect to PostgreSQL
docker compose -f deployment/docker/docker-compose.yml exec postgres \
  psql -U postgres -d omniintelligence

# View FSM states
SELECT fsm_type, current_state, COUNT(*)
FROM fsm_state
GROUP BY fsm_type, current_state;

# View active workflows
SELECT workflow_id, operation_type, status, started_at
FROM workflow_executions
WHERE status = 'RUNNING';
```

### Redpanda Console

Access Kafka UI at http://localhost:8080 to view:
- Topics
- Messages
- Consumer groups
- Cluster health

## Development

### Build Images

```bash
# Build all images
docker compose -f deployment/docker/docker-compose.nodes.yml build

# Build specific node
docker compose -f deployment/docker/docker-compose.nodes.yml build intelligence-reducer
```

### Run Tests

```bash
# Run all tests
docker compose -f deployment/docker/Dockerfile --target dev run --rm tests

# Run specific test
docker compose run --rm tests pytest tests/unit/test_models.py -v
```

### Hot Reload

For development with hot reload, mount source code:

```yaml
volumes:
  - ../../src:/app/src
```

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check PostgreSQL is running
docker compose -f deployment/docker/docker-compose.yml ps postgres

# Check logs
docker compose -f deployment/docker/docker-compose.yml logs postgres

# Test connection
docker compose -f deployment/docker/docker-compose.yml exec postgres \
  pg_isready -U postgres
```

### Redpanda Connection Issues

```bash
# Check Redpanda health
docker compose -f deployment/docker/docker-compose.yml exec redpanda \
  rpk cluster health

# List topics
docker compose -f deployment/docker/docker-compose.yml exec redpanda \
  rpk topic list
```

### Qdrant Issues

```bash
# Check Qdrant health
curl http://localhost:6333/health

# View collections
curl http://localhost:6333/collections
```

### Reset Everything

```bash
# Stop and remove all containers, networks, volumes
docker compose -f deployment/docker/docker-compose.yml \
               -f deployment/docker/docker-compose.nodes.yml down -v

# Remove all data
docker volume rm \
  omniintelligence_postgres_data \
  omniintelligence_qdrant_data \
  omniintelligence_memgraph_data \
  omniintelligence_valkey_data \
  omniintelligence_redpanda_data
```

## Production Deployment

### Security

1. **Use strong passwords**: Generate secure passwords for all services
2. **Network isolation**: Use Docker networks to isolate services
3. **TLS/SSL**: Enable TLS for all external connections
4. **Secrets management**: Use Docker secrets or external secret managers

### Scaling

```bash
# Scale compute nodes
docker compose -f deployment/docker/docker-compose.nodes.yml up -d --scale vectorization-compute=3

# Scale effect nodes
docker compose -f deployment/docker/docker-compose.nodes.yml up -d --scale qdrant-vector-effect=2
```

### Resource Limits

Adjust resource limits in docker-compose files:

```yaml
deploy:
  resources:
    limits:
      memory: 2G
      cpus: '2.0'
    reservations:
      memory: 1G
      cpus: '1.0'
```

### Backup

```bash
# Backup PostgreSQL
docker compose -f deployment/docker/docker-compose.yml exec postgres \
  pg_dump -U postgres omniintelligence > backup.sql

# Backup Qdrant
curl -X POST http://localhost:6333/collections/archon_vectors/snapshots

# Backup Memgraph
docker compose -f deployment/docker/docker-compose.yml exec memgraph \
  mgconsole -c "CALL mg.backup();"
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/OmniNode-ai/omniintelligence/issues
- Documentation: See `docs/` directory
