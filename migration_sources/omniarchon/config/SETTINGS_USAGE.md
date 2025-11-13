# Archon Settings Module - Usage Guide

## Overview

Centralized configuration management for Archon Intelligence Platform using Pydantic Settings with:
- ✅ Type-safe configuration with validation
- ✅ Singleton pattern (thread-safe with `@lru_cache`)
- ✅ Auto-loading of `.env` files on module import
- ✅ Environment-specific configuration support
- ✅ Helper methods for DSN generation and validation
- ✅ Sanitized exports (redacts sensitive values)

**Pattern**: Based on omniclaude's settings module architecture.

## Quick Start

```python
from config import settings

# Access configuration values
print(settings.kafka_bootstrap_servers)  # omninode-bridge-redpanda:9092
print(settings.postgres_host)            # 192.168.86.200
print(settings.intelligence_service_port) # 8053
```

## Import Options

```python
# Option 1: Use the singleton instance (recommended)
from config import settings
print(settings.postgres_host)

# Option 2: Use the factory function
from config import get_settings
settings = get_settings()  # Returns same singleton instance

# Option 3: Access the Settings class (advanced usage)
from config import Settings
custom_settings = Settings()  # Creates new instance (not recommended)
```

## Configuration Priority

Settings are loaded in the following priority order (highest to lowest):

1. **System environment variables** (highest priority)
2. **`.env.{ENVIRONMENT}` file** (environment-specific, e.g., `.env.production`)
3. **`.env` file** (base configuration)
4. **Default values** in Settings class (lowest priority)

### Environment-Specific Configuration

```bash
# Set environment variable
export ENVIRONMENT=production

# This will load:
# 1. .env (base)
# 2. .env.production (overrides base)
# 3. System environment variables (overrides all)
```

## Configuration Sections

### 1. Core Intelligence Services (LOCAL)

```python
settings.intelligence_service_port  # 8053
settings.bridge_service_port        # 8054
settings.search_service_port        # 8055
settings.langextract_service_port   # 8156
settings.langextract_service_url    # http://archon-langextract:8156
```

### 2. Event Bus - Kafka/Redpanda (REMOTE)

```python
settings.kafka_bootstrap_servers     # omninode-bridge-redpanda:9092
settings.kafka_enable_intelligence   # True
settings.kafka_request_timeout_ms    # 5000
settings.kafka_topic_prefix          # dev.archon-intelligence
```

### 3. Databases

```python
# PostgreSQL (REMOTE at 192.168.86.200)
settings.postgres_host               # 192.168.86.200
settings.postgres_port               # 5436
settings.postgres_database           # omninode_bridge
settings.postgres_user               # postgres
settings.postgres_password           # (from .env)
settings.postgres_pool_min_size      # 2
settings.postgres_pool_max_size      # 10

# Memgraph (LOCAL)
settings.memgraph_uri                # bolt://memgraph:7687

# Qdrant (LOCAL)
settings.qdrant_host                 # localhost
settings.qdrant_port                 # 6333
settings.qdrant_url                  # http://localhost:6333
```

### 4. Performance & Caching

```python
settings.valkey_url                  # redis://archon-valkey:6379/0
settings.enable_cache                # True
settings.cache_ttl_patterns          # 300 (seconds)
```

### 5. AI/ML Services

```python
settings.openai_api_key              # (from .env, optional)
settings.ollama_base_url             # http://192.168.86.200:11434
settings.embedding_model             # rjmalagon/gte-qwen2-1.5b-instruct-embed-f16
settings.embedding_dimensions        # 1536
```

### 6. Feature Flags & Timeouts

```python
settings.enable_real_time_events     # True

# HTTP Timeouts (milliseconds)
settings.http_timeout_intelligence   # 60000
settings.http_timeout_search         # 60000

# Database Timeouts (milliseconds)
settings.db_timeout_connection       # 30000
settings.db_timeout_query            # 60000

# Cache Timeouts (milliseconds)
settings.cache_timeout_operation     # 2000
```

## Helper Methods

### PostgreSQL DSN Generation

```python
# Generate async PostgreSQL connection string (asyncpg)
dsn = settings.get_postgres_dsn(async_driver=True)
# postgresql+asyncpg://postgres:***@192.168.86.200:5436/omninode_bridge

# Generate sync PostgreSQL connection string (psycopg2)
dsn = settings.get_postgres_dsn(async_driver=False)
# postgresql://postgres:***@192.168.86.200:5436/omninode_bridge
```

### Effective Values with Validation

```python
# Get PostgreSQL password with validation (raises ValueError if not set)
password = settings.get_effective_postgres_password()

# Get Kafka bootstrap servers
kafka_servers = settings.get_effective_kafka_bootstrap_servers()
```

### Configuration Validation

```python
# Validate required services configuration
errors = settings.validate_required_services()
if errors:
    print("Configuration errors:", errors)
    # ['PostgreSQL password not configured. Set POSTGRES_PASSWORD in .env']
```

### Sanitized Export

```python
# Export configuration with sensitive values redacted
config_dict = settings.to_dict_sanitized()
print(config_dict['postgres_password'])  # ***REDACTED***
print(config_dict['openai_api_key'])     # ***REDACTED***
```

### Logging Configuration

```python
import logging

logger = logging.getLogger(__name__)

# Log configuration summary (sanitized)
settings.log_configuration(logger)
# ================================================================================
# Archon Configuration
#   Kafka: omninode-bridge-redpanda:9092
#   PostgreSQL: 192.168.86.200:5436
#   Memgraph: bolt://memgraph:7687
#   Qdrant: http://localhost:6333
#   Ollama: http://192.168.86.200:11434
#   Cache Enabled: True
#   Real-time Events: True
# ================================================================================
```

## Type Safety and Validation

### Port Validation

```python
# Ports are validated to be in range 1-65535
settings.intelligence_service_port  # ✅ Valid: 8053
# settings.intelligence_service_port = 70000  # ❌ ValueError: Port must be between 1 and 65535
```

### Timeout Validation

```python
# Timeouts are validated to be at least 1000ms
settings.http_timeout_intelligence  # ✅ Valid: 60000
# settings.http_timeout_intelligence = 500  # ❌ ValueError: Timeout must be at least 1000ms
```

## Usage Examples

### Example 1: FastAPI Service Startup

```python
from fastapi import FastAPI
from config import settings

app = FastAPI(title="Archon Intelligence")

@app.on_event("startup")
async def startup_event():
    # Log configuration on startup
    import logging
    logger = logging.getLogger(__name__)
    settings.log_configuration(logger)

    # Validate configuration
    errors = settings.validate_required_services()
    if errors:
        logger.error(f"Configuration errors: {errors}")
        raise RuntimeError("Invalid configuration")

    # Initialize services using settings
    kafka_producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        request_timeout_ms=settings.kafka_request_timeout_ms
    )

    postgres_engine = create_async_engine(
        settings.get_postgres_dsn(async_driver=True),
        pool_size=settings.postgres_pool_max_size
    )
```

### Example 2: Kafka Consumer Configuration

```python
from aiokafka import AIOKafkaConsumer
from config import settings

async def create_consumer():
    consumer = AIOKafkaConsumer(
        f"{settings.kafka_topic_prefix}.tree.discover.v1",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        request_timeout_ms=settings.kafka_request_timeout_ms,
        group_id="archon-intelligence-consumer"
    )
    await consumer.start()
    return consumer
```

### Example 3: Database Connection

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config import settings

# Create async engine
engine = create_async_engine(
    settings.get_postgres_dsn(async_driver=True),
    pool_size=settings.postgres_pool_max_size,
    pool_pre_ping=True,
    echo=False
)

# Create session factory
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)
```

### Example 4: Cache Client

```python
import redis.asyncio as redis
from config import settings

async def create_cache_client():
    if not settings.enable_cache:
        return None

    return redis.from_url(
        settings.valkey_url,
        encoding="utf-8",
        decode_responses=True
    )
```

## Environment Variables

All settings can be configured via environment variables. Variable names are case-insensitive.

```bash
# .env file example

# Core Services (LOCAL)
INTELLIGENCE_SERVICE_PORT=8053
BRIDGE_SERVICE_PORT=8054
SEARCH_SERVICE_PORT=8055

# Event Bus (REMOTE)
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
KAFKA_ENABLE_INTELLIGENCE=true
KAFKA_REQUEST_TIMEOUT_MS=5000

# PostgreSQL (REMOTE)
POSTGRES_HOST=192.168.86.200
POSTGRES_PORT=5436
POSTGRES_DATABASE=omninode_bridge
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password  # REQUIRED

# AI/ML
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://192.168.86.200:11434
EMBEDDING_MODEL=rjmalagon/gte-qwen2-1.5b-instruct-embed-f16
EMBEDDING_DIMENSIONS=1536

# Performance
ENABLE_CACHE=true
CACHE_TTL_PATTERNS=300
```

## Best Practices

### ✅ DO

1. **Use the singleton instance**: `from config import settings`
2. **Validate on startup**: Call `settings.validate_required_services()`
3. **Log configuration**: Call `settings.log_configuration()` on service startup
4. **Use helper methods**: Prefer `settings.get_postgres_dsn()` over manual string construction
5. **Keep sensitive values in .env**: Never commit passwords or API keys to git

### ❌ DON'T

1. **Don't create multiple Settings instances**: Use the singleton
2. **Don't hardcode configuration values**: Always use settings module
3. **Don't log sensitive values**: Use `to_dict_sanitized()` for logging
4. **Don't modify settings at runtime**: Settings should be immutable after loading

## Testing

### Mocking Settings in Tests

```python
import pytest
from unittest.mock import patch

def test_with_custom_settings():
    with patch('config.settings.postgres_host', 'localhost'):
        # Test code here
        assert settings.postgres_host == 'localhost'
```

### Using Environment Variables in Tests

```python
import pytest
import os

@pytest.fixture
def custom_env(monkeypatch):
    monkeypatch.setenv('POSTGRES_HOST', 'test-db-host')
    monkeypatch.setenv('POSTGRES_PORT', '5433')
    # Clear settings cache
    from config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

def test_with_custom_env(custom_env):
    from config import settings
    assert settings.postgres_host == 'test-db-host'
    assert settings.postgres_port == 5433
```

## Migration from Old Configuration

### Before (hardcoded values)

```python
# ❌ OLD WAY - Hardcoded
KAFKA_BOOTSTRAP_SERVERS = "omninode-bridge-redpanda:9092"
POSTGRES_HOST = "192.168.86.200"
POSTGRES_PORT = 5436
```

### After (centralized settings)

```python
# ✅ NEW WAY - Centralized
from config import settings

kafka_servers = settings.kafka_bootstrap_servers
postgres_host = settings.postgres_host
postgres_port = settings.postgres_port
```

## Troubleshooting

### Settings not loading from .env

```python
# Check if .env file exists
from pathlib import Path
env_file = Path.cwd() / ".env"
print(f"Env file exists: {env_file.exists()}")

# Force reload .env
from config.settings import load_env_files, find_project_root
project_root = find_project_root()
load_env_files(project_root)
```

### Configuration validation errors

```python
# Get detailed validation errors
errors = settings.validate_required_services()
if errors:
    for error in errors:
        print(f"❌ {error}")
```

### Debugging configuration values

```python
# Export all settings (sanitized)
import json
config = settings.to_dict_sanitized()
print(json.dumps(config, indent=2))
```

## References

- **Pattern Source**: Based on omniclaude's settings module
- **Pydantic Settings Docs**: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **Archon Configuration Guide**: `/Volumes/PRO-G40/Code/omniarchon/CLAUDE.md`
- **Shared Infrastructure**: `~/.claude/CLAUDE.md`

---

**Version**: 1.0.0
**Last Updated**: 2025-11-06
**Status**: Production Ready ✅
