# Network Connectivity Debug Checklist

## Issue Summary
Archon containers cannot connect to remote OmniNode Bridge services at 192.168.86.200.

## Current Status
- ✅ Host 192.168.86.200 is reachable (ping successful)
- ❌ PostgreSQL (5432): Port CLOSED
- ❌ Redpanda/Kafka (9092): Port CLOSED
- ❌ Bridge Service (8054): Port CLOSED
- ⚠️  archon-intelligence: UNHEALTHY (connection failures)

## Root Cause
Remote services are not accessible from the network. Ports appear closed even from the host machine.

## Verification Steps on Remote Host (192.168.86.200)

### 1. Check Docker Container Status
```bash
# SSH into 192.168.86.200
ssh user@192.168.86.200

# Check running containers and port mappings
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Look for:
# - omninode-bridge-postgres (should expose 5432)
# - omninode-bridge-redpanda (should expose 9092)
# - omninode-bridge-bridge (should expose 8054)
```

### 2. Verify Port Bindings
```bash
# Check if services are listening on 0.0.0.0 (network) or 127.0.0.1 (localhost only)
docker inspect omninode-bridge-postgres | jq '.[].NetworkSettings.Ports'
docker inspect omninode-bridge-redpanda | jq '.[].NetworkSettings.Ports'

# Or use netstat
netstat -tlnp | grep -E ':(5432|9092|8054)'

# Expected output should show 0.0.0.0:5432 NOT 127.0.0.1:5432
```

### 3. Check docker-compose Configuration
```bash
# Navigate to OmniNode Bridge deployment directory
cd /path/to/omninode-bridge

# Check docker-compose.yml port bindings
grep -A 5 "ports:" docker-compose.yml

# Verify services are binding to network interface:
# ✅ CORRECT: - "0.0.0.0:5432:5432" or - "5432:5432"
# ❌ WRONG: - "127.0.0.1:5432:5432"
```

### 4. Firewall Check
```bash
# Check if firewall is blocking ports
sudo ufw status | grep -E '(5432|9092|8054)'

# Or for firewalld
sudo firewall-cmd --list-ports

# Or for iptables
sudo iptables -L -n | grep -E '(5432|9092|8054)'
```

### 5. Test Local Connectivity on Remote Host
```bash
# From inside 192.168.86.200, test if services respond locally
nc -zv localhost 5432  # PostgreSQL
nc -zv localhost 9092  # Redpanda
nc -zv localhost 8054  # Bridge Service

# If local connection works but external doesn't, it's a binding/firewall issue
```

## Expected Fixes

### Fix 1: Update docker-compose Port Bindings (Most Likely)

**File**: `/path/to/omninode-bridge/docker-compose.yml`

Change from:
```yaml
services:
  postgres:
    ports:
      - "127.0.0.1:5432:5432"  # ❌ Localhost only
```

To:
```yaml
services:
  postgres:
    ports:
      - "5432:5432"  # ✅ Accessible from network
      # Or explicitly: - "0.0.0.0:5432:5432"
```

Apply changes:
```bash
docker compose down
docker compose up -d
```

### Fix 2: Firewall Configuration

If using ufw:
```bash
sudo ufw allow 5432/tcp  # PostgreSQL
sudo ufw allow 9092/tcp  # Redpanda
sudo ufw allow 8054/tcp  # Bridge Service
```

If using firewalld:
```bash
sudo firewall-cmd --permanent --add-port=5432/tcp
sudo firewall-cmd --permanent --add-port=9092/tcp
sudo firewall-cmd --permanent --add-port=8054/tcp
sudo firewall-cmd --reload
```

### Fix 3: Restart Services with Proper Network Configuration

```bash
# Stop services
docker compose down

# Ensure no port bindings to 127.0.0.1 in docker-compose.yml
# Then restart
docker compose up -d

# Verify ports are now open
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

## Verification After Fix

From Archon machine (192.168.86.x):
```bash
# Test connectivity
nc -zv 192.168.86.200 5432  # Should succeed
nc -zv 192.168.86.200 9092  # Should succeed
nc -zv 192.168.86.200 8054  # Should succeed

# Restart archon-intelligence
docker restart archon-intelligence

# Check health
docker ps --filter "name=archon-intelligence" --format "{{.Status}}"
# Should show: Up X minutes (healthy)
```

## Alternative Solution: Run All Services Locally

If remote services cannot be exposed to network, run OmniNode Bridge stack locally:

```bash
# In omninode-bridge directory
docker compose up -d

# Update Archon .env to use local services:
POSTGRES_HOST=localhost
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
BRIDGE_SERVICE_URL=http://localhost:8054

# Use special port mappings to avoid conflicts
# PostgreSQL: localhost:5436 (instead of 5432)
# Redpanda: localhost:29092 (instead of 9092)
```

## Next Steps

1. SSH into 192.168.86.200
2. Run verification steps 1-5 above
3. Apply appropriate fix (1, 2, or 3)
4. Verify connectivity from Archon machine
5. Restart archon-intelligence container
6. Confirm health check passes

## Contact Points

- Remote Host: 192.168.86.200
- Archon Host: Current machine
- Services Required:
  - PostgreSQL (5432)
  - Redpanda/Kafka (9092)
  - Bridge Service (8054)
