#!/bin/bash
# ============================================================================
# vLLM Embedding Service Startup Script
# ============================================================================
# Purpose: Start vLLM embedding server on remote GPU machines
# Usage:
#   Local:  ./scripts/start_vllm_embedding_service.sh
#   Remote: ssh 192.168.86.201 'bash -s' < scripts/start_vllm_embedding_service.sh
#
# Part of Multi-Machine Embedding Architecture
# See: docs/MULTI_MACHINE_EMBEDDING.md
# ============================================================================

set -e

# Configuration
MODEL="rjmalagon/gte-qwen2-1.5b-instruct-embed-f16"
PORT="${VLLM_PORT:-8002}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
GPU_MEMORY_UTIL="${GPU_MEMORY_UTIL:-0.8}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-gte-qwen2-embed}"

# ANSI colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}vLLM Embedding Service Startup${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Model: $MODEL"
echo "  Port: $PORT"
echo "  Max Model Length: $MAX_MODEL_LEN"
echo "  GPU Memory Utilization: $GPU_MEMORY_UTIL"
echo "  Served Model Name: $SERVED_MODEL_NAME"
echo ""

# Check if vLLM is installed
if ! python3 -c "import vllm" 2>/dev/null; then
    echo -e "${RED}============================================================================${NC}"
    echo -e "${RED}❌ ERROR: vLLM is not installed${NC}"
    echo -e "${RED}============================================================================${NC}"
    echo ""
    echo "vLLM must be installed before running this script."
    echo ""
    echo "Installation options:"
    echo "  1. pip install vllm"
    echo "  2. See installation documentation at:"
    echo "     https://docs.vllm.ai/en/latest/getting_started/installation.html"
    echo ""
    echo "For CUDA 11.8:"
    echo "  pip install vllm"
    echo ""
    echo "For CUDA 12.1+:"
    echo "  pip install vllm --extra-index-url https://download.pytorch.org/whl/cu121"
    echo ""
    exit 1
fi

# Check for existing process on port
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port $PORT already in use. Killing existing process...${NC}"
    kill $(lsof -t -i:$PORT) 2>/dev/null || true
    sleep 2
fi

# Check GPU availability
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✅ GPU detected:${NC}"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
    echo ""
else
    echo -e "${YELLOW}⚠️  No GPU detected. vLLM will use CPU (slower)${NC}"
    echo ""
fi

# Start vLLM server
echo -e "${GREEN}🚀 Starting vLLM embedding server...${NC}"
echo ""

# Create log directory
mkdir -p /tmp/vllm-logs

# Start server in background with logging
nohup python3 -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --port "$PORT" \
    --served-model-name "$SERVED_MODEL_NAME" \
    --max-model-len "$MAX_MODEL_LEN" \
    --dtype float16 \
    --gpu-memory-utilization "$GPU_MEMORY_UTIL" \
    --disable-log-requests \
    > "/tmp/vllm-logs/vllm-$PORT.log" 2>&1 &

VLLM_PID=$!

echo -e "${GREEN}✅ vLLM server started (PID: $VLLM_PID)${NC}"
echo "   Log file: /tmp/vllm-logs/vllm-$PORT.log"
echo ""

# Wait for server to start
echo -e "${BLUE}Waiting for server to be ready...${NC}"
for i in {1..60}; do
    if curl -s http://localhost:$PORT/v1/models >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Server is ready!${NC}"
        echo ""
        break
    fi

    if [ $i -eq 60 ]; then
        echo -e "${RED}❌ Server failed to start within 60 seconds${NC}"
        echo ""
        echo "Last 20 lines of log:"
        tail -20 "/tmp/vllm-logs/vllm-$PORT.log"
        exit 1
    fi

    echo -n "."
    sleep 1
done

# Verify server is running
echo -e "${GREEN}Server Information:${NC}"
curl -s --connect-timeout 5 --max-time 10 http://localhost:$PORT/v1/models | python3 -m json.tool || echo "Failed to get models"
echo ""

echo -e "${BLUE}============================================================================${NC}"
echo -e "${GREEN}✅ vLLM Embedding Service Successfully Started${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo "Service Details:"
echo "  Endpoint: http://localhost:$PORT"
echo "  Models endpoint: http://localhost:$PORT/v1/models"
echo "  Embeddings endpoint: http://localhost:$PORT/v1/embeddings"
echo "  Process ID: $VLLM_PID"
echo "  Log file: /tmp/vllm-logs/vllm-$PORT.log"
echo ""
echo "Test embedding request:"
echo "  curl -X POST http://localhost:$PORT/v1/embeddings \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"input\": \"Hello, world!\", \"model\": \"$SERVED_MODEL_NAME\"}'"
echo ""
echo "To stop the server:"
echo "  kill $VLLM_PID"
echo ""
