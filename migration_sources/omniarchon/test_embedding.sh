#!/bin/bash
# Test vLLM embedding service

echo "Testing vLLM embedding service at 192.168.86.201:8002..."

# Test 1: Health check
echo -e "\n1. Health check:"
curl -s http://192.168.86.201:8002/health
echo ""

# Test 2: List models
echo -e "\n2. Available models:"
curl -s http://192.168.86.201:8002/v1/models | python3 -m json.tool
echo ""

# Test 3: Generate test embedding
echo -e "\n3. Generate test embedding:"
curl -s -X POST http://192.168.86.201:8002/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "test embedding generation", "model": "Alibaba-NLP/gte-Qwen2-1.5B-instruct"}' > /tmp/embedding_test.json

# Check dimensions
DIMENSIONS=$(python3 -c "import json; data=json.load(open('/tmp/embedding_test.json')); print(len(data['data'][0]['embedding']))")
echo "Embedding dimensions: $DIMENSIONS"

# Verify it's 1536
if [ "$DIMENSIONS" == "1536" ]; then
    echo "✅ Embedding dimensions match expected value (1536)"
else
    echo "❌ WARNING: Embedding dimensions ($DIMENSIONS) do not match expected value (1536)"
fi

# Show first 5 values
python3 -c "import json; data=json.load(open('/tmp/embedding_test.json')); print(f\"First 5 values: {data['data'][0]['embedding'][:5]}\")"
