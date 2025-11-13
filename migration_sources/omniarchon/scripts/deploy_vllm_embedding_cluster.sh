#!/bin/bash
# ============================================================================
# vLLM Embedding Cluster Deployment Script
# ============================================================================
# Purpose: Deploy vLLM embedding services across multiple GPU machines
# Usage: ./scripts/deploy_vllm_embedding_cluster.sh
#
# Deploys to:
#   - 192.168.86.201:8002 (GPU Machine 1)
#   - 192.168.86.202:8002 (GPU Machine 2)
#
# Part of Multi-Machine Embedding Architecture (Option A)
# See: docs/MULTI_MACHINE_EMBEDDING.md
# ============================================================================

set -e

# Configuration
GPU_MACHINES=("192.168.86.201" "192.168.86.202")
VLLM_PORT=8002
MODEL="rjmalagon/gte-qwen2-1.5b-instruct-embed-f16"
SSH_USER="${SSH_USER:-$(whoami)}"

# ANSI colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}vLLM Embedding Cluster Deployment${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Model: $MODEL"
echo "  Port: $VLLM_PORT"
echo "  GPU Machines: ${GPU_MACHINES[*]}"
echo "  SSH User: $SSH_USER"
echo ""

# Function to deploy to a single machine
deploy_to_machine() {
    local machine=$1
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${BLUE}Deploying to $machine${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    echo ""

    # Test SSH connectivity
    echo -e "${YELLOW}Testing SSH connectivity...${NC}"
    if ! ssh -o ConnectTimeout=5 "$SSH_USER@$machine" "echo 'SSH OK'" 2>/dev/null; then
        echo -e "${RED}❌ Cannot connect to $machine via SSH${NC}"
        echo ""
        return 1
    fi
    echo -e "${GREEN}✅ SSH connection successful${NC}"
    echo ""

    # Check GPU availability
    echo -e "${YELLOW}Checking GPU availability...${NC}"
    gpu_info=$(ssh "$SSH_USER@$machine" "nvidia-smi --query-gpu=name --format=csv,noheader" 2>/dev/null || echo "No GPU")
    if [ "$gpu_info" != "No GPU" ]; then
        echo -e "${GREEN}✅ GPU detected: $gpu_info${NC}"
    else
        echo -e "${YELLOW}⚠️  No GPU detected (will use CPU - slower)${NC}"
    fi
    echo ""

    # Check if vLLM is installed
    echo -e "${YELLOW}Checking vLLM installation...${NC}"
    if ssh "$SSH_USER@$machine" "python3 -c 'import vllm' 2>/dev/null"; then
        echo -e "${GREEN}✅ vLLM already installed${NC}"
    else
        echo -e "${YELLOW}⚠️  vLLM not installed. Installing (timeout: 10 minutes)...${NC}"
        ssh "$SSH_USER@$machine" "timeout 600 pip install vllm"
        exit_code=$?
        if [ $exit_code -eq 124 ]; then
            echo -e "${RED}❌ vLLM installation timed out after 10 minutes${NC}"
            echo -e "${YELLOW}Hint: Try installing manually on $machine or increase timeout${NC}"
            return 1
        elif [ $exit_code -ne 0 ]; then
            echo -e "${RED}❌ Failed to install vLLM (exit code: $exit_code)${NC}"
            return 1
        fi
        echo -e "${GREEN}✅ vLLM installed successfully${NC}"
    fi
    echo ""

    # Copy startup script to remote machine
    echo -e "${YELLOW}Copying startup script...${NC}"
    if ! scp scripts/start_vllm_embedding_service.sh "$SSH_USER@$machine:/tmp/" >/dev/null 2>&1; then
        echo -e "${RED}❌ Failed to copy startup script to $machine${NC}"
        echo ""
        return 1
    fi
    echo -e "${GREEN}✅ Startup script copied${NC}"
    echo ""

    # Start vLLM service
    echo -e "${YELLOW}Starting vLLM embedding service...${NC}"
    if ! ssh "$SSH_USER@$machine" "VLLM_PORT=$VLLM_PORT bash /tmp/start_vllm_embedding_service.sh"; then
        echo -e "${RED}❌ Failed to start vLLM service on $machine${NC}"
        echo ""
        return 1
    fi
    echo ""

    # Verify service is running
    echo -e "${YELLOW}Verifying service...${NC}"
    sleep 3
    if curl -s -f http://$machine:$VLLM_PORT/v1/models >/dev/null 2>&1; then
        echo -e "${GREEN}✅ vLLM service is running on $machine:$VLLM_PORT${NC}"
        echo ""
        echo "Available models:"
        curl -s http://$machine:$VLLM_PORT/v1/models | python3 -c "import sys, json; data=json.load(sys.stdin); print('\n'.join(['  - ' + m['id'] for m in data.get('data', [])]))" 2>/dev/null || echo "  (unable to list models)"
    else
        echo -e "${RED}❌ Service failed to start on $machine${NC}"
        return 1
    fi
    echo ""
}

# Deploy to all machines
SUCCESSFUL=0
FAILED=0

for machine in "${GPU_MACHINES[@]}"; do
    if deploy_to_machine "$machine"; then
        ((SUCCESSFUL++))
    else
        ((FAILED++))
        echo -e "${RED}❌ Deployment to $machine failed${NC}"
        echo ""
    fi
done

# Summary
echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Deployment Summary${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "Successful deployments: ${GREEN}$SUCCESSFUL${NC}"
echo -e "Failed deployments: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All vLLM embedding services deployed successfully!${NC}"
    echo ""
    echo "Consumer Configuration:"
    echo "  Consumer 1: OLLAMA_BASE_URL=http://192.168.86.200:11434  # Local Ollama"
    echo "  Consumer 2: OLLAMA_BASE_URL=http://192.168.86.201:8002   # vLLM GPU 1"
    echo "  Consumer 3: OLLAMA_BASE_URL=http://192.168.86.202:8002   # vLLM GPU 2"
    echo ""
    echo "Next steps:"
    echo "  1. Update .env with vLLM endpoints"
    echo "  2. Deploy consumers: docker compose up -d archon-intelligence-consumer-{1,2,3}"
    echo "  3. Verify: ./scripts/check_consumers.sh"
    echo ""
else
    echo -e "${RED}❌ Some deployments failed. Please check the errors above.${NC}"
    exit 1
fi
