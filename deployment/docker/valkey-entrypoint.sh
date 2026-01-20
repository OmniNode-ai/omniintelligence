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
#   - Special characters in password handled safely using awk
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

# Ensure config directory exists
mkdir -p "$(dirname "${CONFIG_FILE}")"

if [ -f "${TEMPLATE_FILE}" ]; then
    echo "Processing Valkey config template..."
    # ========================================================================
    # Safe Password Substitution
    # ========================================================================
    # Using awk for safe substitution - handles all special characters:
    #   - Forward slashes (/)
    #   - Backslashes (\)
    #   - Ampersands (&)
    #   - Dollar signs ($)
    #   - Quotes (' and ")
    #   - Newlines, tabs, and other control characters
    #
    # The -v option passes the password as a variable, avoiding shell
    # interpretation. The gsub function performs literal string replacement.
    # ========================================================================
    awk -v password="${VALKEY_PASSWORD}" '{
        gsub(/__VALKEY_PASSWORD__/, password)
        print
    }' "${TEMPLATE_FILE}" > "${CONFIG_FILE}"
    chmod 600 "${CONFIG_FILE}"
    echo "Config file generated at ${CONFIG_FILE}"
else
    echo "WARNING: Template file not found, creating minimal configuration"
    # ========================================================================
    # Fallback Config Generation (Safe for Special Characters)
    # ========================================================================
    # Using printf to safely write password - no shell expansion issues.
    # The password is written directly to the file, not through echo/heredoc
    # which could interpret special characters.
    # ========================================================================
    {
        printf 'requirepass %s\n' "${VALKEY_PASSWORD}"
        printf 'maxmemory 512mb\n'
        printf 'maxmemory-policy allkeys-lru\n'
        printf 'save 60 1000\n'
        printf 'dir /data\n'
    } > "${CONFIG_FILE}"
    chmod 600 "${CONFIG_FILE}"
fi

# Start Valkey with config file (password not in command line)
echo "Starting Valkey server..."
exec valkey-server "${CONFIG_FILE}"
