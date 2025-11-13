# Deployment Configuration

All Docker Compose and Dockerfile configurations for OmniArchon.

## Prerequisites

### External Networks

OmniArchon connects to networks managed by the OmniNode Bridge stack on the remote server (`192.168.86.200`). These networks enable communication with shared infrastructure services (Redpanda/Kafka and PostgreSQL).

**Required networks**:
- `omninode-bridge-network` - PostgreSQL traceability database network
- `omninode_bridge_omninode-bridge-network` - Redpanda/Kafka event bus network

### Network Setup

These networks are created automatically when the OmniNode Bridge stack is running on `192.168.86.200`.

**If you encounter "network not found" errors during startup**:

1. **Verify remote services are running**:
   ```bash
   # Check if networks exist on your local Docker
   docker network ls | grep omninode-bridge
   ```

2. **If networks don't exist**, ensure OmniNode Bridge is running on the remote server:
   ```bash
   # SSH into the remote server
   ssh user@192.168.86.200

   # Navigate to omninode_bridge directory
   cd /path/to/omninode_bridge

   # Start the bridge stack
   docker compose up -d

   # Verify networks are created
   docker network ls | grep omninode-bridge
   ```

3. **Connect to remote networks** (if needed):
   The docker-compose files are already configured to use these external networks. Docker will automatically connect to them when starting services.

### What These Networks Provide

| Network | Purpose | Services Accessed |
|---------|---------|-------------------|
| `omninode-bridge-network` | Database connectivity | PostgreSQL (pattern traceability, document freshness) |
| `omninode_bridge_omninode-bridge-network` | Event bus connectivity | Redpanda/Kafka (intelligence events, tree indexing) |

### DNS Configuration

Services use DNS resolution via `/etc/hosts` to connect to remote infrastructure:

```bash
# Required /etc/hosts entries (should already be configured)
192.168.86.200 omninode-bridge-redpanda
192.168.86.200 omninode-bridge-postgres
192.168.86.200 omninode-bridge-onextree
192.168.86.200 omninode-bridge-metadata-stamping
192.168.86.200 omninode-bridge-consul
```

**Verify DNS configuration**:
```bash
cat /etc/hosts | grep -E "192.168.86.200|omninode-bridge"
```

### Verifying Remote Service Connectivity

Before starting OmniArchon services, verify connectivity to remote infrastructure:

```bash
# Test Redpanda connectivity (internal port)
nc -zv 192.168.86.200 9092

# Test Redpanda connectivity (external port)
nc -zv 192.168.86.200 29092

# Test PostgreSQL connectivity
nc -zv 192.168.86.200 5436

# Test OnexTree service
curl -f http://192.168.86.200:8058/health

# Test Metadata Stamping service
curl -f http://192.168.86.200:8057/health
```

## Quick Start

**Development**:
```bash
docker compose -f deployment/docker-compose.yml up -d
```

**Production**:
```bash
docker compose -f deployment/docker-compose.prod.yml up -d
```

**Staging**:
```bash
docker compose -f deployment/docker-compose.staging.yml up -d
```

## Available Configurations

| File | Purpose | Use Case |
|------|---------|----------|
| `docker-compose.yml` | Main development | Daily development |
| `docker-compose.prod.yml` | Production | Production deployment |
| `docker-compose.staging.yml` | Staging | Pre-production testing |
| `docker-compose.test.yml` | Testing | Unit/integration tests |
| `docker-compose.integration-tests.yml` | Integration tests | CI/CD pipeline |
| `docker-compose.performance.yml` | Performance testing | Benchmarks |
| `docker-compose.qdrant.yml` | Qdrant only | Vector DB testing |

## Dockerfiles

### Production
- `Dockerfile.backend.prod` - Production backend image
- `Dockerfile.frontend.prod` - Production frontend image

### Services
- `Dockerfile.agents` - AI agents service
- `Dockerfile.mcp` - MCP server
- `Dockerfile.server` - Main API server

### Service-Specific
Service-specific Dockerfiles remain in their service directories:
- `services/intelligence/Dockerfile`
- `services/bridge/Dockerfile`
- `services/search/Dockerfile`
- `services/langextract/Dockerfile`
- `services/kafka-consumer/Dockerfile`

## Health Checks

After starting services:
```bash
# Check all services
docker compose -f deployment/docker-compose.yml ps

# Verify health
curl http://localhost:8053/health  # Intelligence
curl http://localhost:8055/health  # Search
curl http://localhost:8054/health  # Bridge
curl http://localhost:8181/health  # Main API
```

## Common Commands

```bash
# Start all services
docker compose -f deployment/docker-compose.yml up -d

# View logs
docker compose -f deployment/docker-compose.yml logs -f [service]

# Rebuild specific service
docker compose -f deployment/docker-compose.yml build [service]

# Stop all services
docker compose -f deployment/docker-compose.yml down

# Clean up (remove volumes)
docker compose -f deployment/docker-compose.yml down -v
```

## CI Validation

Automated validation runs on every push/PR that modifies:
- `deployment/` directory
- `.env.example`
- Any `docker-compose*.yml` files

### Validation Checks

1. **Syntax**: All compose files are valid YAML and docker-compose compatible
2. **Security**: No hardcoded credentials in compose files
3. **Configuration**: All environment variables have defaults or are documented
4. **Ports**: No conflicting port mappings between services
5. **Networks**: External network references are documented
6. **Dependencies**: Service dependencies are validated
7. **Health**: Health checks are present where recommended
8. **Resources**: Resource limits are defined for production services

### Running Locally

```bash
# Quick validation
./scripts/validate-docker-compose.sh

# Detailed output with verbose mode
./scripts/validate-docker-compose.sh --verbose

# Validate environment configuration
./scripts/validate-env.sh .env
```

### Troubleshooting

**Syntax errors**:
```bash
# See detailed docker compose errors
docker compose -f deployment/docker-compose.yml config
```

**Port conflicts**:
```bash
# Check for duplicate port mappings
grep -r "ports:" deployment/docker-compose*.yml | grep -E "[0-9]+:[0-9]+"
```

**Hardcoded credentials**:
```bash
# All passwords/secrets must use ${VARNAME} pattern
# Good:    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
# Bad:     POSTGRES_PASSWORD: "my_actual_password"
```

**Missing environment variables**:
```bash
# Check which variables are undefined
./scripts/validate-env.sh .env.example
```

### CI Status Badge

Add to your PR description or documentation:
```markdown
![Docker Compose Validation](https://github.com/YOUR_USERNAME/omniarchon/workflows/Docker%20Compose%20Validation/badge.svg)
```

## Environment Configuration

Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
# Edit .env with your configuration
```

See main [README.md](../README.md) for detailed setup instructions.
