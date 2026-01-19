#!/bin/sh
# ============================================================================
# Valkey Entrypoint Script
# ============================================================================
# Purpose: Process config template and start Valkey without exposing password
#          in the process listing (avoids --requirepass on command line)
#
# Security:
#   - Password injected into config file at runtime
#   - Config file only accessible within container
#   - Password not visible in `ps aux` or `docker inspect`
# ============================================================================

set -e

# Validate password is set
if [ -z "${VALKEY_PASSWORD}" ]; then
    echo "ERROR: VALKEY_PASSWORD environment variable must be set"
    exit 1
fi

# Process template if it exists
TEMPLATE_FILE="/etc/valkey/valkey.conf.template"
CONFIG_FILE="/etc/valkey/valkey.conf"

if [ -f "${TEMPLATE_FILE}" ]; then
    echo "Processing Valkey config template..."
    # Replace placeholder with actual password
    sed "s/__VALKEY_PASSWORD__/${VALKEY_PASSWORD}/g" "${TEMPLATE_FILE}" > "${CONFIG_FILE}"
    chmod 600 "${CONFIG_FILE}"
    echo "Config file generated at ${CONFIG_FILE}"
else
    echo "WARNING: Template file not found, using default configuration"
    # Fallback: create minimal config
    cat > "${CONFIG_FILE}" << EOF
requirepass ${VALKEY_PASSWORD}
maxmemory 512mb
maxmemory-policy allkeys-lru
save 60 1000
dir /data
EOF
    chmod 600 "${CONFIG_FILE}"
fi

# Start Valkey with config file (password not in command line)
echo "Starting Valkey server..."
exec valkey-server "${CONFIG_FILE}"
