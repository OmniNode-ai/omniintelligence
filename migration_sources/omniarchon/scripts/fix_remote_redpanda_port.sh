#!/bin/bash
# Fix Redpanda port mapping on remote server (192.168.86.200)
# Issue: Port is 29102:29092 instead of 29092:29092

cat << 'EOF'
================================================================================
REDPANDA PORT FIX SCRIPT
================================================================================
Problem: Redpanda on 192.168.86.200 is using wrong port mapping (29102:29092)
Required: Change to correct mapping (29092:29092)

This script needs to be run ON THE REMOTE SERVER (192.168.86.200)
================================================================================
EOF

echo ""
echo "Step 1: Checking if we're on the remote server..."

# Check if we're on the remote server
HOSTNAME=$(hostname)
IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')

if [[ "$IP_ADDR" != "192.168.86.200" ]]; then
    echo "❌ This script must be run ON the remote server (192.168.86.200)"
    echo "   Current host: $HOSTNAME ($IP_ADDR)"
    echo ""
    echo "SSH to the remote server and run:"
    echo "  ssh user@192.168.86.200"
    echo "  # Then copy and run this script"
    exit 1
fi

echo "✅ Running on remote server: $HOSTNAME ($IP_ADDR)"
echo ""

echo "Step 2: Finding Redpanda container and docker-compose file..."

# Find Redpanda container
CONTAINER=$(docker ps -a --filter "name=redpanda" --format "{{.Names}}" | head -1)

if [ -z "$CONTAINER" ]; then
    echo "❌ No Redpanda container found"
    exit 1
fi

echo "✅ Found container: $CONTAINER"

# Get container inspect info to find compose project
PROJECT=$(docker inspect $CONTAINER --format '{{index .Config.Labels "com.docker.compose.project"}}' 2>/dev/null)
CONFIG_FILE=$(docker inspect $CONTAINER --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' 2>/dev/null)

echo "   Docker Compose Project: $PROJECT"
echo "   Config File: $CONFIG_FILE"
echo ""

echo "Step 3: Checking current port mapping..."

CURRENT_PORTS=$(docker port $CONTAINER 2>/dev/null | grep 29092)
echo "   Current port mapping:"
echo "   $CURRENT_PORTS"

if echo "$CURRENT_PORTS" | grep -q "29102"; then
    echo "   ⚠️  INCORRECT: Using port 29102"
else
    echo "   ✅ Port mapping looks correct"
    exit 0
fi

echo ""
echo "Step 4: Finding docker-compose.yml location..."

# Common locations for omninode-bridge
COMPOSE_LOCATIONS=(
    "/opt/omninode-bridge/docker-compose.yml"
    "/home/*/omninode-bridge/docker-compose.yml"
    "/root/omninode-bridge/docker-compose.yml"
    "~/omninode-bridge/docker-compose.yml"
    "/var/omninode-bridge/docker-compose.yml"
)

COMPOSE_FILE=""
for loc in "${COMPOSE_LOCATIONS[@]}"; do
    # Expand tilde and wildcards
    expanded=$(eval echo "$loc")
    if [ -f "$expanded" ]; then
        COMPOSE_FILE="$expanded"
        echo "✅ Found docker-compose.yml: $COMPOSE_FILE"
        break
    fi
done

if [ -z "$COMPOSE_FILE" ]; then
    echo "❌ Could not find docker-compose.yml"
    echo "   Please locate it manually and update the ports section for Redpanda:"
    echo ""
    echo "   Change from:"
    echo "     ports:"
    echo "       - \"29102:29092\"  # WRONG"
    echo ""
    echo "   To:"
    echo "     ports:"
    echo "       - \"29092:29092\"  # CORRECT"
    exit 1
fi

echo ""
echo "Step 5: Backing up docker-compose.yml..."

BACKUP_FILE="${COMPOSE_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$COMPOSE_FILE" "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"

echo ""
echo "Step 6: Fixing port mapping in docker-compose.yml..."

# Show the problematic line
echo "   Current configuration:"
grep -A 2 -B 2 "29102" "$COMPOSE_FILE" || echo "   (Could not find 29102 in file)"

# Fix the port mapping
if grep -q "29102:29092" "$COMPOSE_FILE"; then
    sed -i 's/29102:29092/29092:29092/g' "$COMPOSE_FILE"
    echo "✅ Updated port mapping: 29102:29092 → 29092:29092"
else
    echo "⚠️  Pattern '29102:29092' not found in file"
    echo "   Manual fix required"
    exit 1
fi

# Show the fixed line
echo ""
echo "   New configuration:"
grep -A 2 -B 2 "29092:29092" "$COMPOSE_FILE"

echo ""
echo "Step 7: Restarting Redpanda with correct port..."

# Get the compose directory
COMPOSE_DIR=$(dirname "$COMPOSE_FILE")
cd "$COMPOSE_DIR" || exit 1

echo "   Stopping Redpanda container..."
docker-compose stop redpanda || docker compose stop redpanda

echo "   Removing old container..."
docker-compose rm -f redpanda || docker compose rm -f redpanda

echo "   Starting with new configuration..."
docker-compose up -d redpanda || docker compose up -d redpanda

echo ""
echo "Step 8: Verifying fix..."

sleep 5

# Check new port mapping
NEW_PORTS=$(docker port $CONTAINER 2>/dev/null | grep 29092 || docker port omninode-bridge-redpanda 2>/dev/null | grep 29092)
echo "   New port mapping:"
echo "   $NEW_PORTS"

if echo "$NEW_PORTS" | grep -q "29092->29092"; then
    echo ""
    echo "✅ SUCCESS: Redpanda is now on correct port 29092"
    echo ""
    echo "Testing from remote server:"
    nc -zv localhost 29092 && echo "✅ Port 29092 is accessible"
else
    echo ""
    echo "❌ Port mapping still incorrect. Manual intervention required."
    echo "   Check docker-compose.yml and restart manually"
    exit 1
fi

echo ""
echo "================================================================================
FIX COMPLETE
================================================================================
Redpanda port mapping has been permanently fixed in docker-compose.yml

Backup location: $BACKUP_FILE

Next step: Test from your local machine (not this server):
  nc -zv 192.168.86.200 29092

If successful, re-run your ingestion workflow.
================================================================================"
EOF
