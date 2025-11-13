# Settings Module - Quick Reference Card

## Import

```python
from config import settings  # ← Use this (singleton instance)
```

## Common Settings

```python
# Services (LOCAL)
settings.intelligence_service_port      # 8053
settings.bridge_service_port            # 8054
settings.search_service_port            # 8055

# Kafka (REMOTE)
settings.kafka_bootstrap_servers        # omninode-bridge-redpanda:9092
settings.kafka_topic_prefix             # dev.archon-intelligence

# PostgreSQL (REMOTE)
settings.postgres_host                  # 192.168.86.200
settings.postgres_port                  # 5436
settings.postgres_database              # omninode_bridge

# Qdrant (LOCAL)
settings.qdrant_url                     # http://localhost:6333

# Memgraph (LOCAL)
settings.memgraph_uri                   # bolt://memgraph:7687

# AI/ML
settings.ollama_base_url                # http://192.168.86.200:11434
settings.embedding_model                # rjmalagon/gte-qwen2-1.5b-instruct-embed-f16
settings.embedding_dimensions           # 1536

# Cache
settings.valkey_url                     # redis://archon-valkey:6379/0
settings.enable_cache                   # True
settings.cache_ttl_patterns             # 300
```

## Helper Methods

```python
# PostgreSQL DSN
dsn = settings.get_postgres_dsn(async_driver=True)
# → postgresql+asyncpg://postgres:***@192.168.86.200:5436/omninode_bridge

# Validation
errors = settings.validate_required_services()
if errors:
    raise RuntimeError(f"Config errors: {errors}")

# Logging (sanitized)
settings.log_configuration(logger)

# Sanitized export
config = settings.to_dict_sanitized()  # Passwords redacted
```

## Service Startup Pattern

```python
from fastapi import FastAPI
from config import settings
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup():
    # 1. Log configuration
    settings.log_configuration(logger)

    # 2. Validate
    errors = settings.validate_required_services()
    if errors:
        raise RuntimeError(f"Config errors: {errors}")

    # 3. Initialize services
    # ... your initialization code
```

## Database Connection

```python
from sqlalchemy.ext.asyncio import create_async_engine
from config import settings

engine = create_async_engine(
    settings.get_postgres_dsn(async_driver=True),
    pool_size=settings.postgres_pool_max_size
)
```

## Kafka Producer

```python
from aiokafka import AIOKafkaProducer
from config import settings

producer = AIOKafkaProducer(
    bootstrap_servers=settings.kafka_bootstrap_servers,
    request_timeout_ms=settings.kafka_request_timeout_ms
)
```

## Cache Client

```python
import redis.asyncio as redis
from config import settings

cache = await redis.from_url(
    settings.valkey_url
) if settings.enable_cache else None
```

## Environment Variables

```bash
# .env file
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
POSTGRES_HOST=192.168.86.200
POSTGRES_PORT=5436
POSTGRES_PASSWORD=your_password  # Required!
EMBEDDING_DIMENSIONS=1536
ENABLE_CACHE=true
```

## Testing

```bash
# Quick test
python3 -c "from config import settings; settings.log_configuration()"

# Validation test
python3 -c "from config import settings; print(settings.validate_required_services())"
```

## Documentation

- **Full Guide**: `config/SETTINGS_USAGE.md`
- **Migration**: `config/SETTINGS_MIGRATION_GUIDE.md`
- **Source**: `config/settings.py`

---

**Pattern**: Pydantic Settings + Singleton + Auto-loading ✅
