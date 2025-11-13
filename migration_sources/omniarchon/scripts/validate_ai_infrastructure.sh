#!/bin/bash
# AI Infrastructure Validation Script for Track 3 Pattern Learning Engine
# Validates all AI resources: Ollama, vLLM (AI PC), GLM-4.6, Gemini

set -e

echo "==================================================================="
echo "       Track 3: AI Infrastructure Validation"
echo "==================================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS="${GREEN}✅ PASS${NC}"
FAIL="${RED}❌ FAIL${NC}"
WARN="${YELLOW}⚠️  WARN${NC}"

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNED_TESTS=0

# Test functions
test_service() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
}

pass_test() {
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${PASS} $1"
}

fail_test() {
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${FAIL} $1"
}

warn_test() {
    WARNED_TESTS=$((WARNED_TESTS + 1))
    echo -e "${WARN} $1"
}

echo "==================================================================="
echo "1. Testing Ollama (Mac Studio - 192.168.86.200:11434)"
echo "==================================================================="
echo ""

test_service
if curl -s --connect-timeout 5 http://192.168.86.200:11434/api/tags > /dev/null 2>&1; then
    MODEL_COUNT=$(curl -s http://192.168.86.200:11434/api/tags | jq '.models | length')
    pass_test "Ollama service is running ($MODEL_COUNT models available)"

    # Check for required models
    echo ""
    echo "   Required Models:"

    test_service
    if curl -s http://192.168.86.200:11434/api/tags | jq -r '.models[].name' | grep -q "codestral"; then
        pass_test "   Codestral 22B: Available"
    else
        fail_test "   Codestral 22B: Missing (required for specialized code generation)"
    fi

    test_service
    if curl -s http://192.168.86.200:11434/api/tags | jq -r '.models[].name' | grep -q "mixtral"; then
        pass_test "   Mixtral 8x7b: Available"
    else
        warn_test "   Mixtral 8x7b: Missing (optional for documentation)"
    fi

    test_service
    if curl -s http://192.168.86.200:11434/api/tags | jq -r '.models[].name' | grep -q "llama3.2"; then
        pass_test "   Llama 3.2: Available"
    else
        warn_test "   Llama 3.2: Missing (optional)"
    fi
else
    fail_test "Ollama service is NOT responding"
fi

echo ""
echo "==================================================================="
echo "2. Testing vLLM - AI PC (192.168.86.201)"
echo "==================================================================="
echo ""

# Test Port 8000 - DeepSeek
test_service
echo "Port 8000 (DeepSeek-Coder-V2-Lite):"
if curl -s --connect-timeout 5 http://192.168.86.201:8000/v1/models > /dev/null 2>&1; then
    MODEL=$(curl -s http://192.168.86.201:8000/v1/models | jq -r '.data[0].id')
    MAX_LEN=$(curl -s http://192.168.86.201:8000/v1/models | jq -r '.data[0].max_model_len')
    pass_test "vLLM DeepSeek endpoint is running"
    echo "   Model: $MODEL"
    echo "   Max Context: $MAX_LEN tokens"
else
    fail_test "vLLM DeepSeek endpoint is NOT responding"
fi

echo ""

# Test Port 8001 - Llama
test_service
echo "Port 8001 (Meta-Llama-3.1-8B):"
if curl -s --connect-timeout 5 http://192.168.86.201:8001/v1/models > /dev/null 2>&1; then
    MODEL=$(curl -s http://192.168.86.201:8001/v1/models | jq -r '.data[0].id')
    MAX_LEN=$(curl -s http://192.168.86.201:8001/v1/models | jq -r '.data[0].max_model_len')
    pass_test "vLLM Llama endpoint is running"
    echo "   Model: $MODEL"
    echo "   Max Context: $MAX_LEN tokens"
else
    fail_test "vLLM Llama endpoint is NOT responding"
fi

echo ""
echo "==================================================================="
echo "3. Testing GLM-4.6 (Z.AI API)"
echo "==================================================================="
echo ""

test_service
if [ -n "$Z_AI_API_KEY" ]; then
    # Test with actual chat completion request
    RESPONSE=$(curl -s -H "Authorization: Bearer $Z_AI_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"model":"glm-4.6","messages":[{"role":"user","content":"test"}],"max_tokens":5}' \
        https://api.z.ai/api/coding/paas/v4/chat/completions)

    if echo "$RESPONSE" | jq -e '.model == "glm-4.6"' > /dev/null 2>&1; then
        pass_test "GLM-4.6 API is accessible and working"
        echo "   Model: glm-4.6"
        echo "   Endpoint: https://api.z.ai/api/coding/paas/v4"
        echo "   Context: 200K tokens (input), 128K tokens (output)"
        echo "   Features: Reasoning mode, near Claude Sonnet 4 parity"
    elif echo "$RESPONSE" | grep -q "1113" 2>/dev/null; then
        fail_test "GLM-4.6 account needs funding (code 1113)"
        echo "   Visit https://z.ai to add credits"
    else
        fail_test "GLM-4.6 API request failed"
        echo "   Response: $RESPONSE"
    fi
else
    warn_test "GLM-4.6 API key not configured (set Z_AI_API_KEY environment variable)"
    echo "   To configure:"
    echo "   1. Subscribe at https://z.ai (GLM Coding Plan - \$3/month)"
    echo "   2. Get API key from dashboard"
    echo "   3. Add to .env: Z_AI_API_KEY=sk-xxxxx"
fi

echo ""
echo "==================================================================="
echo "4. Testing Gemini Flash (Google API)"
echo "==================================================================="
echo ""

test_service
if [ -n "$GOOGLE_API_KEY" ]; then
    if curl -s --connect-timeout 10 \
        "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash?key=$GOOGLE_API_KEY" > /dev/null 2>&1; then

        MODEL_NAME=$(curl -s "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash?key=$GOOGLE_API_KEY" | jq -r '.name')

        if [ -n "$MODEL_NAME" ]; then
            pass_test "Gemini Flash API is accessible"
            echo "   Model: gemini-1.5-flash"
            echo "   Context: 1M tokens"
        else
            fail_test "Gemini Flash model not accessible"
        fi
    else
        fail_test "Gemini Flash API authentication failed"
    fi
else
    warn_test "Gemini Flash API key not configured (set GOOGLE_API_KEY)"
    echo "   To configure:"
    echo "   1. Visit https://aistudio.google.com/app/apikey"
    echo "   2. Create API key"
    echo "   3. Add to .env: GOOGLE_API_KEY=xxxxx"
fi

echo ""
echo "==================================================================="
echo "5. Performance Benchmark"
echo "==================================================================="
echo ""

echo "Benchmarking code generation speed (100 tokens)..."
echo ""

# Benchmark Ollama Codestral
test_service
echo "Testing Ollama (Codestral)..."
START=$(date +%s%3N)
OLLAMA_RESPONSE=$(curl -s http://192.168.86.200:11434/api/generate \
    -d '{
        "model":"codestral:22b-v0.1-q4_K_M",
        "prompt":"Write a Python hello world function",
        "stream":false,
        "options":{"num_predict":50}
    }' 2>/dev/null)

if [ $? -eq 0 ] && [ -n "$OLLAMA_RESPONSE" ]; then
    OLLAMA_TIME=$(($(date +%s%3N) - START))
    pass_test "Ollama benchmark: ${OLLAMA_TIME}ms"
else
    fail_test "Ollama benchmark failed"
    OLLAMA_TIME=999999
fi

echo ""

# Benchmark vLLM DeepSeek
test_service
echo "Testing vLLM (DeepSeek)..."
START=$(date +%s%3N)
VLLM_RESPONSE=$(curl -s -X POST http://192.168.86.201:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model":"deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
        "prompt":"Write a Python hello world function",
        "max_tokens":50
    }' 2>/dev/null)

if [ $? -eq 0 ] && [ -n "$VLLM_RESPONSE" ]; then
    VLLM_TIME=$(($(date +%s%3N) - START))
    pass_test "vLLM benchmark: ${VLLM_TIME}ms"
else
    fail_test "vLLM benchmark failed"
    VLLM_TIME=999999
fi

echo ""

# Calculate speedup
if [ $OLLAMA_TIME -ne 999999 ] && [ $VLLM_TIME -ne 999999 ]; then
    SPEEDUP=$(awk "BEGIN {printf \"%.2f\", $OLLAMA_TIME / $VLLM_TIME}")
    echo "Performance Comparison:"
    echo "   Ollama (Codestral): ${OLLAMA_TIME}ms"
    echo "   vLLM (DeepSeek):    ${VLLM_TIME}ms"
    echo "   Speedup:            ${SPEEDUP}x faster"
    echo ""

    if (( $(echo "$SPEEDUP >= 2.0" | bc -l) )); then
        pass_test "vLLM is ${SPEEDUP}x faster than Ollama (target: 2-5x)"
    else
        warn_test "vLLM speedup is ${SPEEDUP}x (expected 2-5x, may vary by load)"
    fi
fi

echo ""
echo "==================================================================="
echo "6. Configuration Validation"
echo "==================================================================="
echo ""

# Check .env file
test_service
if [ -f "/Volumes/PRO-G40/Code/Archon/.env" ]; then
    pass_test ".env file exists"

    # Check for required variables
    echo ""
    echo "   Checking environment variables:"

    test_service
    if grep -q "VLLM_DEEPSEEK_URL" /Volumes/PRO-G40/Code/Archon/.env 2>/dev/null; then
        pass_test "   VLLM_DEEPSEEK_URL configured"
    else
        warn_test "   VLLM_DEEPSEEK_URL not configured (add: VLLM_DEEPSEEK_URL=http://192.168.86.201:8000/v1)"
    fi

    test_service
    if grep -q "VLLM_LLAMA_URL" /Volumes/PRO-G40/Code/Archon/.env 2>/dev/null; then
        pass_test "   VLLM_LLAMA_URL configured"
    else
        warn_test "   VLLM_LLAMA_URL not configured (add: VLLM_LLAMA_URL=http://192.168.86.201:8001/v1)"
    fi

    test_service
    if grep -q "Z_AI_API_KEY" /Volumes/PRO-G40/Code/Archon/.env 2>/dev/null; then
        pass_test "   Z_AI_API_KEY configured"
    else
        warn_test "   Z_AI_API_KEY not configured (optional for GLM-4.6)"
    fi
else
    fail_test ".env file not found at /Volumes/PRO-G40/Code/Archon/.env"
fi

echo ""
echo "==================================================================="
echo "                    Validation Summary"
echo "==================================================================="
echo ""

echo "Total Tests:  $TOTAL_TESTS"
echo -e "Passed:       ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:       ${RED}$FAILED_TESTS${NC}"
echo -e "Warnings:     ${YELLOW}$WARNED_TESTS${NC}"
echo ""

# Calculate pass rate
PASS_RATE=$(awk "BEGIN {printf \"%.0f\", ($PASSED_TESTS / $TOTAL_TESTS) * 100}")

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}==================================================================="
    echo "   ✅ ALL CRITICAL TESTS PASSED ($PASS_RATE% pass rate)"
    echo "   Ready to proceed with Track 3 AI-Accelerated implementation!"
    echo -e "===================================================================${NC}"
    echo ""
    echo "Next Steps:"
    echo "1. Review warnings and configure optional services if desired"
    echo "2. Proceed with Phase 1 (Track 3-1.1): Multi-model schema consensus"
    echo "3. Use vLLM endpoints for 2-5x faster code generation"
    echo ""
    exit 0
else
    echo -e "${RED}==================================================================="
    echo "   ❌ VALIDATION FAILED ($FAILED_TESTS critical failures)"
    echo "   Please resolve failures before proceeding"
    echo -e "===================================================================${NC}"
    echo ""
    echo "Critical Issues:"
    echo "- Review failed tests above and fix configuration"
    echo "- Ensure all required services are running"
    echo "- Check network connectivity to 192.168.86.200 and 192.168.86.201"
    echo ""
    exit 1
fi
