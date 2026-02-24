#!/bin/sh
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# ============================================================================
# ONEX Node Entrypoint Script
# ============================================================================
# Purpose: Proper signal handling for containerized ONEX nodes
#
# Signal Handling:
#   This script uses 'exec' to replace the shell process with the Python
#   interpreter. This ensures that signals (SIGTERM, SIGINT, etc.) are
#   delivered directly to the Python application rather than to the shell.
#   This is critical for graceful shutdown in Kubernetes and Docker.
#
# Usage:
#   The script is called by Docker with the node type as argument:
#     /entrypoint.sh orchestrator
#     /entrypoint.sh reducer
#     /entrypoint.sh compute
#     /entrypoint.sh effect
#
# Environment Variables:
#   NODE_NAME - For compute/effect nodes, specifies which node to run
#               (e.g., vectorization_compute, qdrant_vector_effect)
# ============================================================================

set -e

NODE_TYPE="${1:-}"

case "$NODE_TYPE" in
    orchestrator)
        echo "Starting Intelligence Orchestrator Node..."
        exec python -m omniintelligence.runtime.stub_launcher --node-type orchestrator
        ;;
    reducer)
        echo "Starting Intelligence Reducer Node..."
        exec python -m omniintelligence.runtime.stub_launcher --node-type reducer
        ;;
    compute|effect)
        if [ -z "$NODE_NAME" ]; then
            echo "ERROR: NODE_NAME environment variable must be set for $NODE_TYPE nodes"
            exit 1
        fi
        echo "Starting $NODE_TYPE node: $NODE_NAME..."
        exec python -m omniintelligence.runtime.stub_launcher --node-type "$NODE_TYPE" --node-name "$NODE_NAME"
        ;;
    *)
        echo "ERROR: Unknown node type: $NODE_TYPE"
        echo "Usage: $0 {orchestrator|reducer|compute|effect}"
        echo ""
        echo "For compute/effect nodes, set NODE_NAME environment variable."
        exit 1
        ;;
esac
