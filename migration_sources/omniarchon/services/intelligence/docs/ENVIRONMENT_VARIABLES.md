# Environment Variables Reference

**Service**: Archon Intelligence Service
**Version**: 1.0.0
**Last Updated**: 2025-10-15

This document provides comprehensive documentation for all environment variables used in the Archon Intelligence Service.

## Table of Contents

- [Service Configuration](#service-configuration)
- [Database Connections](#database-connections)
- [AI/ML Services](#aiml-services)
- [Service Discovery](#service-discovery)
- [Kafka Configuration](#kafka-configuration)
- [Performance Tuning](#performance-tuning)
- [Qdrant Vector Database](#qdrant-vector-database)
- [Event System](#event-system)
- [Feature Flags](#feature-flags)
- [Validation Requirements](#validation-requirements)

---

## Service Configuration

### INTELLIGENCE_SERVICE_PORT

- **Type**: Integer
- **Description**: Port on which the Intelligence service will listen for HTTP requests
- **Default**: `8053`
- **Required**: No
- **Example**: `INTELLIGENCE_SERVICE_PORT=8053`
- **Impact**: Changing this requires updating all client services that connect to the Intelligence service. Must update service discovery configurations and Docker compose files.
- **Validation**: Must be between 1024 and 65535

### LOG_LEVEL

- **Type**: String (Enum)
- **Description**: Logging level for the service. Controls verbosity of log output.
- **Default**: `INFO`
- **Required**: No
- **Valid Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Example**: `LOG_LEVEL=DEBUG`
- **Impact**:
  - `DEBUG`: Very verbose, includes all internal operations. Performance impact in production.
  - `INFO`: Standard operational logging. Recommended for production.
  - `WARNING`: Only warnings and errors. May miss important operational information.
  - `ERROR`/`CRITICAL`: Only error messages. Not recommended for production monitoring.

---

## Database Connections

### MEMGRAPH_URI

- **Type**: String (URI)
- **Description**: Connection URI for Memgraph knowledge graph database
- **Default**: `bolt://memgraph:7687`
- **Required**: Yes
- **Example**: `MEMGRAPH_URI=bolt://192.168.1.100:7687`
- **Impact**: Critical. Service will fail health checks if unable to connect. All entity storage and relationship queries depend on this connection.
- **Validation**: Must be valid bolt:// URI format

### DATABASE_URL

- **Type**: String (PostgreSQL URI)
- **Description**: PostgreSQL connection string for document freshness and performance optimization features
- **Default**: `postgresql://user:password@localhost:5432/archon`
- **Required**: Yes
- **Format**: `postgresql://[user]:[password]@[host]:[port]/[database]`
- **Example**: `DATABASE_URL=postgresql://archon:secure_password@postgres:5432/archon_intelligence`
- **Impact**: Required for:
  - Document freshness tracking
  - Performance baseline storage
  - Optimization metrics
  - Without this, freshness and performance features will be disabled
- **Validation**: Must be valid PostgreSQL connection string

### TRACEABILITY_DB_URL

- **Type**: String (PostgreSQL URI)
- **Description**: Separate PostgreSQL connection for pattern traceability data
- **Default**: `postgresql://user:password@localhost:5432/traceability`
- **Required**: No
- **Format**: `postgresql://[user]:[password]@[host]:[port]/[database]`
- **Example**: `TRACEABILITY_DB_URL=postgresql://archon:secure_password@postgres:5432/archon_traceability`
- **Impact**: If not provided, pattern traceability features will store data in DATABASE_URL. Separate database recommended for scalability.
- **Validation**: Must be valid PostgreSQL connection string

### SUPABASE_SERVICE_KEY

- **Type**: String (JWT Token)
- **Description**: Service role key for Supabase integration (if using Supabase instead of PostgreSQL)
- **Default**: None
- **Required**: No (only if using Supabase)
- **Example**: `SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- **Impact**: Required only if using Supabase as database backend. Not needed for standard PostgreSQL setup.
- **Security**: **CRITICAL** - This is a service role key with full database access. Never commit to version control.

### SUPABASE_URL

- **Type**: String (URL)
- **Description**: Base URL for Supabase project (if using Supabase)
- **Default**: None
- **Required**: No (only if using Supabase)
- **Example**: `SUPABASE_URL=https://yourproject.supabase.co`
- **Impact**: Required only if using Supabase as database backend. Used for connection initialization.
- **Validation**: Must be valid HTTPS URL

### POSTGRES_HOST

- **Type**: String (hostname)
- **Description**: PostgreSQL hostname for direct connections (used in testing/hooks)
- **Default**: `localhost`
- **Required**: No
- **Example**: `POSTGRES_HOST=postgres.internal.example.com`
- **Impact**: Used for direct PostgreSQL connections in testing and hook utilities. Most applications should use DATABASE_URL instead.
- **Validation**: Must be valid hostname or IP address

---

## AI/ML Services

### OLLAMA_BASE_URL

- **Type**: String (URL)
- **Description**: Base URL for Ollama instance used for embeddings and local AI model inference
- **Default**: `http://192.168.86.200:11434`
- **Required**: Yes
- **Example**: `OLLAMA_BASE_URL=http://localhost:11434`
- **Impact**:
  - Used for generating embeddings for vector search
  - Pattern matching semantic analysis
  - Local LLM inference for quality assessment
  - Service will degrade gracefully if unavailable but some features will be disabled
- **Validation**: Must be valid HTTP(S) URL, service must respond to health check

### LLM_BASE_URL

- **Type**: String (URL)
- **Description**: Alias for OLLAMA_BASE_URL used in some test files
- **Default**: `http://192.168.86.200:11434`
- **Required**: No
- **Example**: `LLM_BASE_URL=http://localhost:11434`
- **Impact**: Used in vector index tests as fallback. Prefer using OLLAMA_BASE_URL for consistency.
- **Note**: This is primarily for backward compatibility. New code should use OLLAMA_BASE_URL.

### OPENAI_API_KEY

- **Type**: String (API Key)
- **Description**: OpenAI API key for GPT model access (if using OpenAI instead of Ollama)
- **Default**: None
- **Required**: No
- **Example**: `OPENAI_API_KEY=sk-proj-...`
- **Impact**: Only required if using OpenAI models instead of Ollama. Used for embeddings and text generation.
- **Security**: **CRITICAL** - Never commit to version control. Use secure secret management.

### OPENAI_EMBEDDING_MODEL

- **Type**: String
- **Description**: OpenAI embedding model to use
- **Default**: `text-embedding-3-small`
- **Required**: No
- **Valid Values**: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`
- **Example**: `OPENAI_EMBEDDING_MODEL=text-embedding-3-large`
- **Impact**:
  - `text-embedding-3-small`: Faster, cheaper, 1536 dimensions
  - `text-embedding-3-large`: Better quality, more expensive, 3072 dimensions
  - Cost and performance tradeoff

### OPENAI_MAX_RETRIES

- **Type**: Integer
- **Description**: Maximum number of retry attempts for OpenAI API calls
- **Default**: `3`
- **Required**: No
- **Example**: `OPENAI_MAX_RETRIES=5`
- **Impact**: Higher values increase resilience to transient failures but may increase latency during outages
- **Validation**: Must be between 0 and 10

### OPENAI_TIMEOUT

- **Type**: Integer (seconds)
- **Description**: Timeout for OpenAI API requests
- **Default**: `30`
- **Required**: No
- **Example**: `OPENAI_TIMEOUT=60`
- **Impact**: Lower values fail faster but may cause failures for large requests. Higher values increase wait time during failures.
- **Validation**: Must be between 5 and 300 seconds

---

## Service Discovery

### BRIDGE_SERVICE_URL

- **Type**: String (URL)
- **Description**: Base URL for Archon Bridge service (metadata stamping, BLAKE3 hashing)
- **Default**: `http://archon-bridge:8054`
- **Required**: Yes
- **Example**: `BRIDGE_SERVICE_URL=http://192.168.1.100:8054`
- **Impact**: Required for:
  - Document metadata stamping
  - BLAKE3 hash generation
  - Kafka event coordination
  - Service will fail to start or degrade if unavailable
- **Validation**: Must be valid HTTP(S) URL

### SEARCH_SERVICE_URL

- **Type**: String (URL)
- **Description**: Base URL for Archon Search service (RAG, vector search)
- **Default**: `http://archon-search:8055`
- **Required**: Yes
- **Example**: `SEARCH_SERVICE_URL=http://192.168.1.100:8055`
- **Impact**: Required for:
  - RAG query orchestration
  - Vector search operations
  - Document indexing
  - Search features will be disabled if unavailable
- **Validation**: Must be valid HTTP(S) URL

### LANGEXTRACT_SERVICE_URL

- **Type**: String (URL)
- **Description**: Base URL for LangExtract service (ML feature extraction, code analysis)
- **Default**: `http://archon-langextract:8156`
- **Required**: Yes
- **Example**: `LANGEXTRACT_SERVICE_URL=http://192.168.1.100:8156`
- **Impact**: Required for:
  - Code semantic analysis
  - Entity extraction from code
  - Pattern classification
  - Codegen analysis handlers will fail if unavailable
- **Validation**: Must be valid HTTP(S) URL

---

## Kafka Configuration

### KAFKA_BOOTSTRAP_SERVERS

- **Type**: String (comma-separated host:port)
- **Description**: Kafka/Redpanda bootstrap servers for event streaming
- **Default**: `omninode-bridge-redpanda:9092`
- **Required**: Yes (if Kafka consumer enabled)
- **Example**:
  - Docker: `KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092`
  - Local: `KAFKA_BOOTSTRAP_SERVERS=localhost:19092`
- **Impact**: Critical for event-driven intelligence handlers. Consumer will fail to initialize if unreachable.
- **Validation**: Must be comma-separated list of host:port pairs
- **Multiple Brokers**: `kafka1:9092,kafka2:9092,kafka3:9092`

### KAFKA_CONSUMER_GROUP

- **Type**: String
- **Description**: Consumer group ID for Kafka consumer
- **Default**: `archon-intelligence`
- **Required**: No
- **Example**: `KAFKA_CONSUMER_GROUP=archon-intelligence-prod`
- **Impact**:
  - All consumers in the same group share partitions
  - Changing this creates a new consumer group with separate offset tracking
  - Use different groups for dev/staging/prod environments
- **Validation**: Must be non-empty string

### KAFKA_AUTO_OFFSET_RESET

- **Type**: String (Enum)
- **Description**: Where to start consuming when no previous offset exists
- **Default**: `earliest`
- **Required**: No
- **Valid Values**: `earliest`, `latest`
- **Example**: `KAFKA_AUTO_OFFSET_RESET=latest`
- **Impact**:
  - `earliest`: Process all messages from the beginning (recommended for development/testing)
  - `latest`: Only process new messages from when consumer starts (recommended for production)
- **Validation**: Must be "earliest" or "latest"

### KAFKA_ENABLE_AUTO_COMMIT

- **Type**: Boolean
- **Description**: Enable automatic offset commits after message processing
- **Default**: `true`
- **Required**: No
- **Valid Values**: `true`, `false`, `1`, `0`, `yes`, `no`
- **Example**: `KAFKA_ENABLE_AUTO_COMMIT=true`
- **Impact**:
  - `true`: Offsets committed automatically, simpler but less control
  - `false`: Manual offset management required, more control but complex
  - For most use cases, keep enabled
- **Validation**: Boolean value

### KAFKA_MAX_POLL_RECORDS

- **Type**: Integer
- **Description**: Maximum number of records to fetch per poll operation
- **Default**: `500`
- **Required**: No
- **Range**: 1 to 10000
- **Example**: `KAFKA_MAX_POLL_RECORDS=1000`
- **Impact**:
  - Higher values: Better throughput, more memory usage
  - Lower values: Lower latency, less memory usage
  - Tune based on message size and processing speed
- **Validation**: Must be between 1 and 10000

### KAFKA_SESSION_TIMEOUT_MS

- **Type**: Integer (milliseconds)
- **Description**: Consumer session timeout - how long before consumer is considered dead
- **Default**: `30000` (30 seconds)
- **Required**: No
- **Range**: 1000 to 300000 (1 second to 5 minutes)
- **Example**: `KAFKA_SESSION_TIMEOUT_MS=45000`
- **Impact**:
  - Lower values: Faster failure detection but more false positives
  - Higher values: Slower failure detection but more stability
  - Must be >= max message processing time
- **Validation**: Must be between 1000 and 300000 milliseconds

### KAFKA_MAX_IN_FLIGHT

- **Type**: Integer
- **Description**: Maximum number of events that can be processed concurrently (backpressure control)
- **Default**: `100`
- **Required**: No
- **Range**: 1 to 1000
- **Example**: `KAFKA_MAX_IN_FLIGHT=200`
- **Impact**:
  - Controls memory usage and system load
  - Higher values: Better throughput, more memory usage
  - Lower values: Lower memory usage, potential throughput bottleneck
  - Tune based on available memory and processing speed
- **Validation**: Must be between 1 and 1000

### KAFKA_ENABLE_CONSUMER

- **Type**: Boolean
- **Description**: Enable/disable Kafka consumer on service startup
- **Default**: `true`
- **Required**: No
- **Valid Values**: `true`, `false`
- **Example**: `KAFKA_ENABLE_CONSUMER=false`
- **Impact**:
  - `false`: Service starts without Kafka consumer, event-driven handlers disabled
  - Useful for testing or environments without Kafka
- **Validation**: Boolean value

### Kafka Topic Configuration

#### KAFKA_CODEGEN_VALIDATE_REQUEST

- **Type**: String (topic name)
- **Description**: Topic for code validation requests
- **Default**: `omninode.codegen.request.validate.v1`
- **Required**: No
- **Example**: `KAFKA_CODEGEN_VALIDATE_REQUEST=omninode.codegen.request.validate.v1`
- **Impact**: Consumer subscribes to this topic for validation events

#### KAFKA_CODEGEN_ANALYZE_REQUEST

- **Type**: String (topic name)
- **Description**: Topic for code analysis requests
- **Default**: `omninode.codegen.request.analyze.v1`
- **Required**: No
- **Example**: `KAFKA_CODEGEN_ANALYZE_REQUEST=omninode.codegen.request.analyze.v1`
- **Impact**: Consumer subscribes to this topic for analysis events

#### KAFKA_CODEGEN_PATTERN_REQUEST

- **Type**: String (topic name)
- **Description**: Topic for pattern matching requests
- **Default**: `omninode.codegen.request.pattern.v1`
- **Required**: No
- **Example**: `KAFKA_CODEGEN_PATTERN_REQUEST=omninode.codegen.request.pattern.v1`
- **Impact**: Consumer subscribes to this topic for pattern matching events

#### KAFKA_CODEGEN_MIXIN_REQUEST

- **Type**: String (topic name)
- **Description**: Topic for mixin recommendation requests
- **Default**: `omninode.codegen.request.mixin.v1`
- **Required**: No
- **Example**: `KAFKA_CODEGEN_MIXIN_REQUEST=omninode.codegen.request.mixin.v1`
- **Impact**: Consumer subscribes to this topic for mixin recommendation events

#### KAFKA_CODEGEN_VALIDATE_RESPONSE

- **Type**: String (topic name)
- **Description**: Topic for code validation responses
- **Default**: `omninode.codegen.response.validate.v1`
- **Required**: No
- **Example**: `KAFKA_CODEGEN_VALIDATE_RESPONSE=omninode.codegen.response.validate.v1`
- **Impact**: Handlers publish validation results to this topic

#### KAFKA_CODEGEN_ANALYZE_RESPONSE

- **Type**: String (topic name)
- **Description**: Topic for code analysis responses
- **Default**: `omninode.codegen.response.analyze.v1`
- **Required**: No
- **Example**: `KAFKA_CODEGEN_ANALYZE_RESPONSE=omninode.codegen.response.analyze.v1`
- **Impact**: Handlers publish analysis results to this topic

#### KAFKA_CODEGEN_PATTERN_RESPONSE

- **Type**: String (topic name)
- **Description**: Topic for pattern matching responses
- **Default**: `omninode.codegen.response.pattern.v1`
- **Required**: No
- **Example**: `KAFKA_CODEGEN_PATTERN_RESPONSE=omninode.codegen.response.pattern.v1`
- **Impact**: Handlers publish pattern matching results to this topic

#### KAFKA_CODEGEN_MIXIN_RESPONSE

- **Type**: String (topic name)
- **Description**: Topic for mixin recommendation responses
- **Default**: `omninode.codegen.response.mixin.v1`
- **Required**: No
- **Example**: `KAFKA_CODEGEN_MIXIN_RESPONSE=omninode.codegen.response.mixin.v1`
- **Impact**: Handlers publish mixin recommendations to this topic

---

## Performance Tuning

### MAX_BATCH_SIZE

- **Type**: Integer
- **Description**: Maximum number of documents to process in a single batch operation
- **Default**: `100`
- **Required**: No
- **Example**: `MAX_BATCH_SIZE=200`
- **Impact**:
  - Higher values: Better throughput for batch operations, more memory usage
  - Lower values: Lower memory usage, more API calls
  - Affects batch indexing performance
- **Validation**: Must be positive integer

### DEFAULT_SEARCH_LIMIT

- **Type**: Integer
- **Description**: Default number of results to return from search operations
- **Default**: `10`
- **Required**: No
- **Example**: `DEFAULT_SEARCH_LIMIT=20`
- **Impact**: Controls default result set size for vector and RAG searches
- **Validation**: Must be positive integer, typically 1-100

### DEFAULT_HNSW_EF

- **Type**: Integer
- **Description**: HNSW (Hierarchical Navigable Small World) ef parameter for vector search
- **Default**: `128`
- **Required**: No
- **Example**: `DEFAULT_HNSW_EF=256`
- **Impact**:
  - Higher values: Better recall (accuracy), slower search
  - Lower values: Faster search, lower recall
  - Range typically 16-512
- **Validation**: Must be power of 2, typically 16-512

### TARGET_SEARCH_LATENCY_MS

- **Type**: Float (milliseconds)
- **Description**: Target latency for vector search operations (performance monitoring)
- **Default**: `100.0`
- **Required**: No
- **Example**: `TARGET_SEARCH_LATENCY_MS=150.0`
- **Impact**: Used for performance monitoring and alerts, not enforced
- **Validation**: Must be positive number

### TARGET_BATCH_LATENCY_MS

- **Type**: Float (milliseconds)
- **Description**: Target latency per document for batch indexing operations
- **Default**: `2000.0`
- **Required**: No
- **Example**: `TARGET_BATCH_LATENCY_MS=1500.0`
- **Impact**: Used for performance monitoring and optimization decisions
- **Validation**: Must be positive number

### MAX_CONCURRENT_EXTRACTIONS

- **Type**: Integer
- **Description**: Maximum number of concurrent entity extraction operations
- **Default**: `5`
- **Required**: No
- **Example**: `MAX_CONCURRENT_EXTRACTIONS=10`
- **Impact**:
  - Higher values: Better throughput, more CPU/memory usage
  - Lower values: Lower resource usage, potential bottleneck
  - Tune based on available resources
- **Validation**: Must be positive integer, typically 1-20

### EXTRACTION_TIMEOUT_SECONDS

- **Type**: Integer (seconds)
- **Description**: Timeout for entity extraction operations
- **Default**: `300` (5 minutes)
- **Required**: No
- **Example**: `EXTRACTION_TIMEOUT_SECONDS=600`
- **Impact**: Prevents hung extraction operations from blocking system
- **Validation**: Must be positive integer, typically 60-600

---

## Qdrant Vector Database

### QDRANT_URL

- **Type**: String (URL)
- **Description**: Base URL for Qdrant vector database
- **Default**: `http://qdrant:6333`
- **Required**: Yes
- **Example**: `QDRANT_URL=http://192.168.1.100:6333`
- **Impact**: Critical for all vector search operations. Service will degrade if unavailable.
- **Validation**: Must be valid HTTP(S) URL

### QDRANT_API_KEY

- **Type**: String (API Key)
- **Description**: API key for Qdrant authentication (if enabled)
- **Default**: Empty (no authentication)
- **Required**: No
- **Example**: `QDRANT_API_KEY=your_qdrant_api_key_here`
- **Impact**: Required only if Qdrant instance has authentication enabled
- **Security**: Store securely, do not commit to version control

### QDRANT_COLLECTION_NAME

- **Type**: String
- **Description**: Name of Qdrant collection for intelligence patterns
- **Default**: `intelligence_patterns`
- **Required**: No
- **Example**: `QDRANT_COLLECTION_NAME=archon_intelligence_prod`
- **Impact**: Use different collection names for different environments (dev/staging/prod)
- **Validation**: Must be valid collection name (alphanumeric, underscores)

### VECTOR_DIMENSIONS

- **Type**: Integer
- **Description**: Dimensionality of embedding vectors
- **Default**: `1536` (matches OpenAI text-embedding-3-small)
- **Required**: No
- **Example**: `VECTOR_DIMENSIONS=768` (for some Ollama models)
- **Impact**:
  - Must match the embedding model output dimensions
  - OpenAI text-embedding-3-small: 1536
  - OpenAI text-embedding-3-large: 3072
  - Ollama all-minilm: 384
  - Changing this requires recreating Qdrant collections
- **Validation**: Must be positive integer, typically 384, 768, 1536, or 3072

---

## Event System

### EVENT_BUS_ENABLED

- **Type**: Boolean
- **Description**: Enable internal event bus for service coordination
- **Default**: `true`
- **Required**: No
- **Valid Values**: `true`, `false`
- **Example**: `EVENT_BUS_ENABLED=true`
- **Impact**: Controls internal event-driven architecture. Disable only for testing.
- **Validation**: Boolean value

### DOCUMENT_EVENT_SUBSCRIPTION

- **Type**: Boolean
- **Description**: Enable subscription to document update events for freshness tracking
- **Default**: `true`
- **Required**: No
- **Valid Values**: `true`, `false`
- **Example**: `DOCUMENT_EVENT_SUBSCRIPTION=true`
- **Impact**: Controls automatic freshness analysis on document updates
- **Validation**: Boolean value

---

## Feature Flags

### DEFAULT_EXTRACTION_MODE

- **Type**: String (Enum)
- **Description**: Default mode for entity extraction
- **Default**: `standard`
- **Required**: No
- **Valid Values**: `standard`, `enhanced`, `minimal`
- **Example**: `DEFAULT_EXTRACTION_MODE=enhanced`
- **Impact**:
  - `standard`: Balanced extraction
  - `enhanced`: More thorough, slower
  - `minimal`: Faster, less detail
- **Validation**: Must be one of valid values

### ENABLE_MULTILINGUAL_EXTRACTION

- **Type**: Boolean
- **Description**: Enable multilingual entity extraction
- **Default**: `true`
- **Required**: No
- **Valid Values**: `true`, `false`
- **Example**: `ENABLE_MULTILINGUAL_EXTRACTION=true`
- **Impact**: Adds language detection and multi-language support, slight performance overhead
- **Validation**: Boolean value

### ENABLE_SEMANTIC_ANALYSIS

- **Type**: Boolean
- **Description**: Enable semantic analysis features
- **Default**: `true`
- **Required**: No
- **Valid Values**: `true`, `false`
- **Example**: `ENABLE_SEMANTIC_ANALYSIS=true`
- **Impact**: Enables deeper semantic understanding, requires ML models
- **Validation**: Boolean value

---

## Validation Requirements

### Critical Variables (Must Be Set)

These variables are required for the service to function properly:

1. **MEMGRAPH_URI** - Knowledge graph connection
2. **DATABASE_URL** - PostgreSQL connection
3. **OLLAMA_BASE_URL** or **OPENAI_API_KEY** - AI/ML services
4. **QDRANT_URL** - Vector database
5. **BRIDGE_SERVICE_URL** - Bridge service
6. **SEARCH_SERVICE_URL** - Search service
7. **LANGEXTRACT_SERVICE_URL** - LangExtract service

### Environment-Specific Configuration

**Development**:
```bash
LOG_LEVEL=DEBUG
KAFKA_AUTO_OFFSET_RESET=earliest
KAFKA_CONSUMER_GROUP=archon-intelligence-dev
QDRANT_COLLECTION_NAME=intelligence_dev
```

**Staging**:
```bash
LOG_LEVEL=INFO
KAFKA_AUTO_OFFSET_RESET=earliest
KAFKA_CONSUMER_GROUP=archon-intelligence-staging
QDRANT_COLLECTION_NAME=intelligence_staging
```

**Production**:
```bash
LOG_LEVEL=INFO
KAFKA_AUTO_OFFSET_RESET=latest
KAFKA_CONSUMER_GROUP=archon-intelligence-prod
QDRANT_COLLECTION_NAME=intelligence_prod
MAX_CONCURRENT_EXTRACTIONS=10
KAFKA_MAX_IN_FLIGHT=200
```

### Security Best Practices

1. **Never commit secrets to version control**
   - Use `.env` files (git-ignored)
   - Use secret management systems (HashiCorp Vault, AWS Secrets Manager, etc.)

2. **Rotate credentials regularly**
   - Database passwords
   - API keys (OpenAI, Qdrant, etc.)
   - Service tokens

3. **Use environment-specific secrets**
   - Different secrets for dev/staging/prod
   - Limit access based on environment

4. **Audit secret access**
   - Log when secrets are accessed
   - Monitor for unauthorized access

### Validation Script

A validation script is available to verify environment configuration:

```bash
python scripts/validate_environment.py
```

This script checks:
- All required variables are set
- Variable types are correct
- Service endpoints are reachable
- Database connections are valid
- Kafka topics exist

### Configuration Sources Priority

The service loads configuration from these sources in order (later sources override earlier):

1. Default values (in code)
2. `.env` file in service directory
3. Environment variables (system/container)
4. Command-line arguments (if supported)

---

## Troubleshooting

### Service Won't Start

1. Check critical variables are set
2. Verify database connections
3. Check service URLs are reachable
4. Review logs at DEBUG level

### Kafka Consumer Issues

1. Verify `KAFKA_BOOTSTRAP_SERVERS` is correct
2. Check Kafka/Redpanda is running
3. Verify topics exist
4. Check consumer group settings

### Performance Issues

1. Review `MAX_CONCURRENT_EXTRACTIONS`
2. Adjust `KAFKA_MAX_IN_FLIGHT`
3. Tune `DEFAULT_HNSW_EF`
4. Check `MAX_POLL_RECORDS`

### Memory Issues

1. Lower `MAX_BATCH_SIZE`
2. Reduce `KAFKA_MAX_IN_FLIGHT`
3. Decrease `MAX_CONCURRENT_EXTRACTIONS`
4. Adjust `MAX_POLL_RECORDS`

---

## Additional Resources

- [Kafka Configuration Guide](./KAFKA_CONFIGURATION.md)
- [Deployment Guide](../../../docs/guides/DEPLOYMENT.md)
- [Security Best Practices](../../../docs/security/SECURITY.md)

---

**Last Updated**: 2025-10-15
**Maintained By**: Archon Intelligence Team
