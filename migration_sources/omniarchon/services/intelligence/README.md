# Archon Intelligence Service

**Version**: 1.0.0
**Status**: Production
**Architecture**: Event-Driven Microservice

Intelligence service for AI coding assistants. Provides code quality analysis, performance optimization, RAG intelligence, pattern learning, and ONEX compliance validation.

## Overview

The Archon Intelligence Service is a core component of the Archon platform, providing:

- **Code Quality Assessment**: ONEX architectural compliance scoring and quality analysis
- **Entity Extraction**: Extract entities from code and documents for knowledge graph population
- **Pattern Learning**: Match patterns, learn from execution traces, provide recommendations
- **Performance Optimization**: Baseline establishment, opportunity identification, optimization tracking
- **Document Freshness**: Track document staleness and refresh workflows
- **RAG Intelligence**: Orchestrate multi-service research across RAG, Qdrant, and Memgraph
- **Event-Driven Handlers**: Process codegen events via Kafka for validation, analysis, pattern matching

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Memgraph 2.18+
- Qdrant 1.10+
- Ollama (for embeddings) or OpenAI API key
- Kafka/Redpanda (for event-driven features)

### Installation

```bash
# Navigate to service directory
cd services/intelligence

# Install dependencies
poetry install

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
vim .env
```

### Configuration

**Required Environment Variables**:

See [docs/ENVIRONMENT_VARIABLES.md](./docs/ENVIRONMENT_VARIABLES.md) for comprehensive documentation.

Critical variables that must be set:

- `MEMGRAPH_URI` - Knowledge graph connection
- `DATABASE_URL` - PostgreSQL connection
- `OLLAMA_BASE_URL` or `OPENAI_API_KEY` - AI/ML services
- `QDRANT_URL` - Vector database
- `BRIDGE_SERVICE_URL` - Bridge service URL
- `SEARCH_SERVICE_URL` - Search service URL
- `LANGEXTRACT_SERVICE_URL` - LangExtract service URL

### Running the Service

**Development**:

```bash
# With Docker Compose (recommended)
docker compose up -d archon-intelligence

# Without Docker (direct)
poetry run python app.py
```

**Production**:

```bash
# Docker deployment
docker compose -f docker-compose.prod.yml up -d archon-intelligence

# Service runs on port 8053 by default
```

### Health Check

```bash
# Check service health
curl http://localhost:8053/health

# Check Kafka consumer health
curl http://localhost:8053/kafka/health

# Get consumer metrics
curl http://localhost:8053/kafka/metrics
```

## Architecture

### Service Components

```
┌─────────────────────────────────────────────────────┐
│         INTELLIGENCE SERVICE (8053)                 │
├─────────────────────────────────────────────────────┤
│  FastAPI Application                                │
│  ├─ Quality Assessment APIs                         │
│  ├─ Entity Extraction APIs                          │
│  ├─ Performance Optimization APIs                   │
│  ├─ Document Freshness APIs                         │
│  ├─ Pattern Learning APIs                           │
│  ├─ Pattern Traceability APIs                       │
│  └─ Autonomous Learning APIs                        │
├─────────────────────────────────────────────────────┤
│  Kafka Consumer (Event-Driven Handlers)             │
│  ├─ CodegenValidationHandler                        │
│  ├─ CodegenAnalysisHandler                          │
│  ├─ CodegenPatternHandler                           │
│  └─ CodegenMixinHandler                             │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│               BACKEND SERVICES                      │
├──────────────────────┬──────────────────────────────┤
│ Memgraph (7687)      │ PostgreSQL (5432)            │
│ Knowledge Graph      │ Traceability & Metrics       │
├──────────────────────┼──────────────────────────────┤
│ Qdrant (6333)        │ Ollama (11434)               │
│ Vector Search        │ Embeddings & LLM             │
└──────────────────────┴──────────────────────────────┘
```

### Event-Driven Architecture

The service consumes codegen events from Kafka/Redpanda:

**Request Topics**:
- `omninode.codegen.request.validate.v1` - Code validation requests
- `omninode.codegen.request.analyze.v1` - Code analysis requests
- `omninode.codegen.request.pattern.v1` - Pattern matching requests
- `omninode.codegen.request.mixin.v1` - Mixin recommendation requests

**Response Topics**:
- `omninode.codegen.response.validate.v1` - Validation results
- `omninode.codegen.response.analyze.v1` - Analysis results
- `omninode.codegen.response.pattern.v1` - Pattern matching results
- `omninode.codegen.response.mixin.v1` - Mixin recommendations

### Key Features

#### 1. Quality Assessment (4 APIs)

- `POST /assess/code` - ONEX compliance + quality scoring
- `POST /assess/document` - Document quality analysis
- `POST /patterns/extract` - Pattern identification
- `POST /compliance/check` - Architectural compliance validation

#### 2. Performance Optimization (5 APIs)

- `POST /performance/baseline` - Establish performance baselines
- `GET /performance/opportunities/{operation_name}` - Get optimization opportunities
- `POST /performance/optimize` - Apply optimizations
- `GET /performance/report` - Comprehensive reports
- `GET /performance/trends` - Trend monitoring

#### 3. Document Freshness (9 APIs)

- `POST /freshness/analyze` - Analyze document freshness
- `GET /freshness/stale` - Get stale documents
- `POST /freshness/refresh` - Refresh documents
- `GET /freshness/stats` - Statistics
- `GET /freshness/document/{path}` - Single document freshness
- `POST /freshness/cleanup` - Cleanup old data
- Event-driven freshness tracking via coordinator

#### 4. Pattern Learning (8 APIs)

- `POST /api/pattern-learning/pattern/match` - Match patterns
- `POST /api/pattern-learning/hybrid/score` - Hybrid scoring
- `POST /api/pattern-learning/semantic/analyze` - Semantic analysis
- `GET /api/pattern-learning/metrics` - Learning metrics
- Cache management and health endpoints

#### 5. Pattern Traceability (11 APIs)

- `POST /api/pattern-traceability/lineage/track` - Track pattern lineage
- `POST /api/pattern-traceability/lineage/track/batch` - Batch tracking
- `GET /api/pattern-traceability/lineage/{pattern_id}` - Get lineage
- Evolution tracking, analytics, feedback loops

#### 6. Autonomous Learning (7 APIs)

- `POST /api/autonomous/patterns/ingest` - Ingest patterns
- `POST /api/autonomous/patterns/success` - Mark success
- `POST /api/autonomous/predict/agent` - Agent prediction
- Time estimation, safety calculation, statistics

## API Documentation

### Quality Assessment Example

```bash
# Assess code quality with ONEX compliance
curl -X POST http://localhost:8053/assess/code \
  -H "Content-Type: application/json" \
  -d '{
    "content": "def hello(): pass",
    "source_path": "test.py",
    "language": "python",
    "include_patterns": true,
    "include_compliance": true
  }'

# Response includes:
# - quality_score (0.0-1.0)
# - architectural_compliance (score + reasoning)
# - code_patterns (best practices, anti-patterns, security issues)
# - maintainability metrics
# - onex_compliance (violations, recommendations)
# - architectural_era classification
```

### Entity Extraction Example

```bash
# Extract entities from document
curl -X POST http://localhost:8053/extract/document \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Full document text here...",
    "source_path": "docs/architecture.md",
    "metadata": {"project": "archon", "type": "documentation"},
    "store_entities": true,
    "trigger_freshness_analysis": true
  }'

# Response includes:
# - entities: List of extracted entities (concepts, technologies, patterns)
# - total_count: Number of entities found
# - processing_time_ms: Processing duration
# - confidence_stats: Min/max/mean confidence scores
```

## Configuration

### Environment Variables

See [docs/ENVIRONMENT_VARIABLES.md](./docs/ENVIRONMENT_VARIABLES.md) for comprehensive documentation including:

- Variable descriptions and types
- Default values
- Required vs optional
- Example values
- Impact of changing
- Validation requirements
- Security best practices
- Environment-specific configurations (dev/staging/prod)

### Performance Tuning

Key performance variables:

```bash
# Concurrent processing
MAX_CONCURRENT_EXTRACTIONS=5
KAFKA_MAX_IN_FLIGHT=100

# Batch processing
MAX_BATCH_SIZE=100
KAFKA_MAX_POLL_RECORDS=500

# Vector search
DEFAULT_HNSW_EF=128
TARGET_SEARCH_LATENCY_MS=100.0

# Kafka consumer
KAFKA_SESSION_TIMEOUT_MS=30000
```

See [docs/ENVIRONMENT_VARIABLES.md#performance-tuning](./docs/ENVIRONMENT_VARIABLES.md#performance-tuning) for detailed guidance.

### Security Configuration

**Critical Security Variables**:

- `SUPABASE_SERVICE_KEY` - Never commit to version control
- `OPENAI_API_KEY` - Use secure secret management
- `QDRANT_API_KEY` - Store securely if using authentication

See [docs/ENVIRONMENT_VARIABLES.md#security-best-practices](./docs/ENVIRONMENT_VARIABLES.md#security-best-practices).

## Development

### Running Tests

```bash
# Unit tests
poetry run pytest tests/unit -v

# Integration tests
poetry run pytest tests/integration -v

# All tests
poetry run pytest -v

# With coverage
poetry run pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Type checking
poetry run mypy src/

# Linting
poetry run ruff check src/

# Formatting
poetry run black src/ tests/

# All checks
poetry run pre-commit run --all-files
```

### Local Development Setup

1. **Start dependencies**:
```bash
docker compose up -d memgraph qdrant postgres redpanda
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env for local development
```

3. **Run service**:
```bash
poetry run python app.py
```

4. **Access service**:
- API: http://localhost:8053
- Health: http://localhost:8053/health
- Docs: http://localhost:8053/docs
- Metrics: http://localhost:8053/metrics

## Monitoring

### Health Endpoints

```bash
# Service health
curl http://localhost:8053/health

# Pattern learning health
curl http://localhost:8053/api/pattern-learning/health

# Pattern traceability health
curl http://localhost:8053/api/pattern-traceability/health

# Autonomous learning health
curl http://localhost:8053/api/autonomous/health

# Kafka consumer health
curl http://localhost:8053/kafka/health
```

### Metrics

```bash
# Prometheus metrics
curl http://localhost:8053/metrics

# Pattern learning metrics
curl http://localhost:8053/api/pattern-learning/metrics

# Kafka consumer metrics
curl http://localhost:8053/kafka/metrics

# Cache stats
curl http://localhost:8053/api/pattern-learning/cache/stats
```

### Logging

Logs include structured logging with:

- Request/response logging with duration
- Entity extraction logs with counts
- Document processing pipeline logs
- Kafka event processing logs
- Error tracking with stack traces
- Performance metrics

Adjust log level with `LOG_LEVEL` environment variable:

```bash
LOG_LEVEL=DEBUG  # Very verbose
LOG_LEVEL=INFO   # Standard (recommended for production)
LOG_LEVEL=WARNING # Warnings and errors only
```

## Troubleshooting

### Service Won't Start

1. Check critical environment variables are set
2. Verify database connections (PostgreSQL, Memgraph)
3. Check service URLs are reachable (Bridge, Search, LangExtract)
4. Review logs at DEBUG level

### Kafka Consumer Issues

1. Verify `KAFKA_BOOTSTRAP_SERVERS` is correct
2. Check Kafka/Redpanda is running
3. Verify topics exist
4. Check consumer group settings
5. Review consumer health endpoint

### Performance Issues

1. Review `MAX_CONCURRENT_EXTRACTIONS` setting
2. Adjust `KAFKA_MAX_IN_FLIGHT` for backpressure control
3. Tune `DEFAULT_HNSW_EF` for vector search
4. Check `MAX_POLL_RECORDS` for batch processing
5. Monitor metrics endpoints for bottlenecks

### Memory Issues

1. Lower `MAX_BATCH_SIZE`
2. Reduce `KAFKA_MAX_IN_FLIGHT`
3. Decrease `MAX_CONCURRENT_EXTRACTIONS`
4. Adjust `MAX_POLL_RECORDS`
5. Monitor container memory limits

See [docs/ENVIRONMENT_VARIABLES.md#troubleshooting](./docs/ENVIRONMENT_VARIABLES.md#troubleshooting) for detailed guidance.

## Production Deployment

### Docker Deployment

```bash
# Build image
docker build -t archon-intelligence:latest .

# Run with Docker Compose
docker compose -f docker-compose.prod.yml up -d archon-intelligence
```

### Environment Configuration

**Production settings**:

```bash
# Service
LOG_LEVEL=INFO
INTELLIGENCE_SERVICE_PORT=8053

# Kafka
KAFKA_AUTO_OFFSET_RESET=latest
KAFKA_CONSUMER_GROUP=archon-intelligence-prod
KAFKA_MAX_IN_FLIGHT=200

# Performance
MAX_CONCURRENT_EXTRACTIONS=10
MAX_BATCH_SIZE=200

# Database
QDRANT_COLLECTION_NAME=intelligence_prod
```

See [docs/ENVIRONMENT_VARIABLES.md#environment-specific-configuration](./docs/ENVIRONMENT_VARIABLES.md#environment-specific-configuration).

### Resource Requirements

**Minimum**:
- CPU: 2 cores
- Memory: 4GB
- Storage: 20GB

**Recommended**:
- CPU: 4-8 cores
- Memory: 8-16GB
- Storage: 100GB (for pattern storage)

### Scaling Considerations

1. **Horizontal Scaling**: Multiple instances share Kafka consumer group partitions
2. **Database Connections**: Configure connection pool sizes appropriately
3. **Cache Warming**: Pre-populate pattern cache on startup
4. **Batch Processing**: Adjust batch sizes based on load
5. **Backpressure**: Tune `KAFKA_MAX_IN_FLIGHT` to prevent overload

## Documentation

- **[Environment Variables](./docs/ENVIRONMENT_VARIABLES.md)** - Comprehensive environment variable reference
- **[Kafka Configuration](./docs/KAFKA_CONFIGURATION.md)** - Kafka/Redpanda setup and troubleshooting
- **[Autonomous API](./docs/AUTONOMOUS_API_IMPLEMENTATION.md)** - Autonomous learning API details
- **[API Reference](http://localhost:8053/docs)** - Interactive OpenAPI documentation (when running)

## Contributing

### Development Workflow

1. Create feature branch from `main`
2. Implement changes with tests
3. Run code quality checks
4. Submit PR with description

### Code Standards

- Follow ONEX architectural patterns
- Maintain >80% test coverage
- Use type hints throughout
- Document all public APIs
- Follow PEP 8 style guide

### Testing Requirements

- Unit tests for all new functions
- Integration tests for API endpoints
- Performance benchmarks for critical paths
- Event handler tests for Kafka consumers

## Support

- **Documentation**: See [docs/](./docs/) directory
- **Issues**: GitHub Issues
- **Slack**: #archon-intelligence channel

---

**Archon Intelligence Service** - Production intelligence provider for AI-driven development.
