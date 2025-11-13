# Kafka Configuration Reference

**Last Updated**: 2025-11-06
**Status**: Centralized configuration active ✅

## Quick Reference

### Import Patterns

```python
# Pattern 1: Use pre-defined constants (simple)
from config.kafka_helper import KAFKA_HOST_SERVERS, KAFKA_DOCKER_SERVERS

config = {
    'bootstrap.servers': KAFKA_HOST_SERVERS  # 192.168.86.200:29092
}
```

```python
# Pattern 2: Use context-aware helper (recommended)
from config.kafka_helper import get_kafka_bootstrap_servers

# Auto-detect context (Docker vs host)
servers = get_kafka_bootstrap_servers()

# Explicit context
servers = get_kafka_bootstrap_servers(context="host")    # 192.168.86.200:29092
servers = get_kafka_bootstrap_servers(context="docker")  # omninode-bridge-redpanda:9092
servers = get_kafka_bootstrap_servers(context="remote")  # localhost:29092
```

```python
# Pattern 3: Use complete config helpers (best for producers/consumers)
from config.kafka_helper import get_kafka_producer_config, get_kafka_consumer_config

# Producer
producer_config = get_kafka_producer_config(context="host")
# Returns: {'bootstrap_servers': '192.168.86.200:29092', 'acks': 'all', ...}

# Consumer
consumer_config = get_kafka_consumer_config(
    context="host",
    group_id="my-consumer-group"
)
# Returns: {'bootstrap_servers': '192.168.86.200:29092', 'group_id': 'my-consumer-group', ...}
```

## Configuration Values

| Constant | Value | Use Case |
|----------|-------|----------|
| `KAFKA_DOCKER_SERVERS` | `omninode-bridge-redpanda:9092` | Docker services (internal network) |
| `KAFKA_HOST_SERVERS` | `192.168.86.200:29092` | Host scripts (external port) |
| `KAFKA_REMOTE_SERVERS` | `localhost:29092` | Running on 192.168.86.200 server |

## Environment Override

Set `KAFKA_BOOTSTRAP_SERVERS` environment variable to override:

```bash
# In .env file
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092

# Or export in shell
export KAFKA_BOOTSTRAP_SERVERS=custom-server:9092
```

## Context Detection

The `get_kafka_bootstrap_servers()` function auto-detects context:

1. **Environment variable check**: Returns `KAFKA_BOOTSTRAP_SERVERS` if set
2. **Docker detection**: Checks for `/.dockerenv` or `/proc/1/cgroup`
3. **Default**: Returns host configuration

## Port Numbers

| Port | Purpose | Access |
|------|---------|--------|
| `9092` | Internal Redpanda port | Docker containers only |
| `29092` | External Redpanda port | Host scripts, external access |

**Note**: Never use port `29102` - this was an error and has been corrected throughout the codebase.

## Common Pitfalls

### ❌ Anti-Patterns (Don't Do This)

```python
# ❌ Hardcoded configuration
config = {'bootstrap.servers': '192.168.86.200:29092'}

# ❌ Wrong port number
servers = "192.168.86.200:29102"  # 29102 is incorrect!

# ❌ Bypassing centralized config
servers = os.getenv("KAFKA_SERVERS", "192.168.86.200:29092")

# ❌ Using Docker port from host
servers = "omninode-bridge-redpanda:9092"  # Won't resolve on host!
```

### ✅ Best Practices

```python
# ✅ Use centralized config
from config.kafka_helper import get_kafka_bootstrap_servers
servers = get_kafka_bootstrap_servers(context="host")

# ✅ Use constants
from config.kafka_helper import KAFKA_HOST_SERVERS
servers = KAFKA_HOST_SERVERS

# ✅ Use config helpers
from config.kafka_helper import get_kafka_producer_config
config = get_kafka_producer_config(context="host")
```

## Migration from Hardcoded Values

If you find hardcoded Kafka configuration:

1. **Identify the context**: Docker service or host script?
2. **Choose the right import**:
   - Simple: `from config.kafka_helper import KAFKA_HOST_SERVERS`
   - Context-aware: `from config.kafka_helper import get_kafka_bootstrap_servers`
   - Full config: `from config.kafka_helper import get_kafka_producer_config`
3. **Replace hardcoded value** with the import
4. **Test** to ensure connectivity works

## Examples

### Script on Host Machine

```python
#!/usr/bin/env python3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.kafka_helper import KAFKA_HOST_SERVERS
from confluent_kafka import Producer

# Configuration
conf = {
    'bootstrap.servers': KAFKA_HOST_SERVERS,  # Uses 192.168.86.200:29092
    'client.id': 'my-script'
}

producer = Producer(conf)
```

### Docker Service

```python
# In docker-compose.yml, set environment:
environment:
  KAFKA_BOOTSTRAP_SERVERS: omninode-bridge-redpanda:9092

# In Python code:
from config.kafka_helper import get_kafka_bootstrap_servers

# Auto-detects Docker environment and respects KAFKA_BOOTSTRAP_SERVERS
servers = get_kafka_bootstrap_servers()  # Returns omninode-bridge-redpanda:9092
```

### aiokafka Consumer

```python
from aiokafka import AIOKafkaConsumer
from config.kafka_helper import get_kafka_consumer_config

# Get complete consumer configuration
config = get_kafka_consumer_config(
    context="host",
    group_id="my-consumer-group"
)

# Create consumer with config
consumer = AIOKafkaConsumer(
    "my-topic",
    **config  # Unpack all configuration
)
```

## Troubleshooting

### Connection Refused

```
❌ Kafka connection refused to 192.168.86.200:29092
```

**Solution**:
1. Verify Redpanda is running: `docker ps | grep redpanda`
2. Test connectivity: `nc -zv 192.168.86.200 29092`
3. Check `/etc/hosts` has entry: `192.168.86.200 omninode-bridge-redpanda`

### Wrong Port

```
❌ Connection timeout to omninode-bridge-redpanda:9092
```

**Solution**: Host scripts must use port 29092, not 9092
```python
from config.kafka_helper import KAFKA_HOST_SERVERS  # Uses 29092
```

### DNS Resolution Failure

```
❌ Failed to resolve 'omninode-bridge-redpanda'
```

**Solution**:
1. Add to `/etc/hosts`: `192.168.86.200 omninode-bridge-redpanda`
2. Or use `KAFKA_HOST_SERVERS` for host scripts

## Related Documentation

- **Infrastructure Topology**: `/Volumes/PRO-G40/Code/omniarchon/CLAUDE.md` (lines 132-245)
- **Cleanup Summary**: `/Volumes/PRO-G40/Code/omniarchon/HARDCODED_PORT_CLEANUP_SUMMARY.md`
- **Settings Reference**: `/Volumes/PRO-G40/Code/omniarchon/config/SETTINGS_QUICK_REFERENCE.md`

## History

- **2025-11-06**: Hardcoded port cleanup completed
  - Eliminated 100% of hardcoded references from application code
  - Fixed all incorrect 29102 → 29092 references
  - Established centralized configuration in `config/kafka_helper.py`
