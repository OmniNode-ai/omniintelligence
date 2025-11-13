# Kafka/Redpanda Listener Configuration Issue

**Date**: 2025-11-06
**Status**: Documented - Workaround Available
**Impact**: Cannot create topics via rpk/kcat from host machine

## Problem Summary

Port 9092 (internal Kafka port) is not accessible from outside the Docker network on the remote Redpanda server (192.168.86.200), causing topic creation failures.

## Root Cause

Redpanda's advertised listener configuration has a mismatch:

1. **External port 29092** is accessible: ✅ `nc -zv 192.168.86.200 29092` succeeds
2. **Internal port 9092** is NOT accessible: ❌ `nc -zv 192.168.86.200 9092` fails (connection refused)

When clients connect to port 29092, Redpanda's metadata response tells them to connect to `omninode-bridge-redpanda:9092`, which resolves (via `/etc/hosts`) to `192.168.86.200:9092` - an inaccessible port.

## Current Configuration

From `/etc/redpanda/redpanda.yaml` on the remote container:

```yaml
advertised_kafka_api:
  - address: omninode-bridge-redpanda
    port: 9092
    name: internal
  - address: localhost
    port: 29092
    name: external
  - address: omninode-bridge-redpanda
    port: 29092
    name: external
```

**Issue**: The advertised addresses don't include `192.168.86.200:29092`, so external clients get redirected to the wrong port.

## Impact

**Cannot execute these commands from host**:
- ❌ `rpk topic create` (tries to connect to 9092)
- ❌ `kcat -P` (gets redirected to 9092 after initial connection)
- ❌ Python kafka-admin operations

**These still work**:
- ✅ `rpk cluster info` (read-only metadata)
- ✅ Topic auto-creation when producers write (if `auto_create_topics_enabled=true`)

## Workaround (Current)

Since `auto_create_topics_enabled=true` in Redpanda, topics are automatically created when a producer first writes to them. However, this doesn't allow setting custom partition counts or replication factors.

## Solution Options

### Option 1: SSH to Remote Server (Immediate Fix)

```bash
# SSH to the remote server
ssh user@192.168.86.200

# Create topics from within the remote server's network
docker exec omninode-bridge-redpanda rpk topic create \
  dev.archon-intelligence.enrich-document.v1 \
  --partitions 4 --replicas 1

docker exec omninode-bridge-redpanda rpk topic create \
  dev.archon-intelligence.enrich-document-completed.v1 \
  --partitions 4 --replicas 1

docker exec omninode-bridge-redpanda rpk topic create \
  dev.archon-intelligence.enrich-document-dlq.v1 \
  --partitions 1 --replicas 1
```

### Option 2: Fix Redpanda Configuration (Permanent Fix)

Update the Redpanda configuration to properly advertise the external listener:

```yaml
advertised_kafka_api:
  - address: omninode-bridge-redpanda
    port: 9092
    name: internal
  - address: 192.168.86.200  # Changed from localhost
    port: 29092
    name: external
```

Then restart Redpanda:
```bash
docker restart omninode-bridge-redpanda
```

### Option 3: Open Port 9092 (Alternative)

Expose port 9092 in the docker-compose configuration:

```yaml
ports:
  - "9092:9092"   # Add this
  - "29092:9092"  # Existing
```

**Note**: This is less ideal as it exposes the internal port externally.

## Monitoring Script Fix

Updated `scripts/check_ingestion.py` to only check enrichment topics when `ENABLE_ASYNC_ENRICHMENT=true`, since they're not needed when the feature is disabled.

## When to Create Topics

Enrichment topics are only needed when:
- `ENABLE_ASYNC_ENRICHMENT=true` in bridge service configuration
- Async intelligence enrichment feature is being used

Currently, async enrichment is **disabled by default** (`ENABLE_ASYNC_ENRICHMENT=false`), so these topics are not required.

## References

- Configuration: `/etc/redpanda/redpanda.yaml` on omninode-bridge-redpanda container
- Feature flag: `services/bridge/.env.example` line 21
- Topic creation script: `scripts/create_async_enrichment_topics.sh`
- Architecture docs: `docs/ASYNC_INTELLIGENCE_ARCHITECTURE.md`

## Testing Connectivity

```bash
# From host machine:
nc -zv 192.168.86.200 9092   # Should fail (connection refused)
nc -zv 192.168.86.200 29092  # Should succeed

# From within Docker network:
docker exec omninode-bridge-redpanda nc -zv localhost 9092  # Should succeed
```

## Status

- **Current state**: Topics don't exist (not needed, feature disabled)
- **Monitoring**: Updated to conditionally check (no more errors)
- **Future**: Use Option 1 or 2 when enabling async enrichment
