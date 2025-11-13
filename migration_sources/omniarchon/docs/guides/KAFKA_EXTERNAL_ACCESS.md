# Kafka External Access Configuration

## Issue

When running bulk ingestion from the host machine, Kafka connection fails with:
```
Unable connect to node with id 0: [Errno 61] Connect call failed ('192.168.86.200', 9092)
```

## Root Cause

Redpanda returns internal Docker network address (`omninode-bridge-redpanda:9092`) in broker metadata, which is not accessible from the host.

## Solution 1: Run from Docker Container (Recommended)

Create a one-off container with the repository mounted:

```bash
# Build a temporary image with dependencies
docker run --rm -it \
  --network omninode_bridge_omninode-bridge-network \
  -v /Volumes/PRO-G40/Code/omniarchon:/repo \
  -w /repo \
  python:3.12-slim \
  bash

# Inside container:
pip install aiokafka
python scripts/bulk_ingest_repository.py /repo \
  --project-name omniarchon \
  --batch-size 50 \
  --kafka-servers omninode-bridge-redpanda:9092 \
  --verbose
```

## Solution 2: Fix Redpanda Advertised Listeners

Update Redpanda configuration to advertise external address:

```yaml
# docker-compose.yml or Redpanda config
command:
  - redpanda start
  - --advertise-kafka-addr
  - 192.168.86.200:29092  # External address for host clients
  - --kafka-addr
  - 0.0.0.0:9092          # Internal binding
```

## Solution 3: Add Host Mapping (Temporary)

Add hostname mapping to `/etc/hosts` on the host machine:

```bash
# /etc/hosts
192.168.86.200  omninode-bridge-redpanda
```

Then connect to port 9092:
```bash
python scripts/bulk_ingest_repository.py /Volumes/PRO-G40/Code/omniarchon \
  --project-name omniarchon \
  --kafka-servers 192.168.86.200:9092
```

**Note**: This only works if port 9092 is exposed externally.

## Solution 4: Use Consumer Inside archon-intelligence Service

Since the consumer (`tree_stamping_handler.py`) is already running inside `archon-intelligence` container, you can:

1. Mount the repository as a volume in `archon-intelligence`
2. Trigger ingestion via HTTP API instead of direct Kafka publishing
3. The service will handle Kafka internally

## Recommended Approach

**For production**: Use Solution 1 (Docker container) or add repository volume mount to archon-intelligence service.

**For development**: Fix Redpanda advertised listeners (Solution 2) for seamless host access.

## Current Status

- Bulk ingestion script: ✅ Created
- Kafka connectivity from host: ❌ Blocked by advertised listeners
- Kafka connectivity from Docker: ✅ Works (internal network)
- Consumer implementation: ✅ Exists (`tree_stamping_handler.py`)

## Next Steps

1. Choose solution based on deployment model
2. Update docker-compose.yml if using Solution 2
3. Rerun bulk ingestion
4. Monitor consumer logs for processing

## Testing Connection

```bash
# Test from host (will fail with current config)
python scripts/bulk_ingest_repository.py . --dry-run --kafka-servers 192.168.86.200:29092

# Test from Docker
docker run --rm --network omninode_bridge_omninode-bridge-network python:3.12-slim \
  bash -c "pip install aiokafka && python -c 'from aiokafka import AIOKafkaProducer; import asyncio; asyncio.run(AIOKafkaProducer(bootstrap_servers=\"omninode-bridge-redpanda:9092\").start())'"
```
