#!/bin/bash
# Test script for correlation ID functionality in pre-tool-use-quality.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/pre-tool-use-quality.sh"

echo "=================================="
echo "Correlation ID Functionality Tests"
echo "=================================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function to run test
run_test() {
    local test_name="$1"
    local expected_behavior="$2"
    echo -e "${YELLOW}TEST:${NC} $test_name"
    echo "  Expected: $expected_behavior"
}

# Helper function to check result
check_result() {
    local result="$1"
    if [ "$result" = "PASS" ]; then
        echo -e "  ${GREEN}✓ PASSED${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "  ${RED}✗ FAILED${NC}"
        ((TESTS_FAILED++))
    fi
    echo ""
}

# Test 1: Script exists and is executable
run_test "Script existence and permissions" "Script should exist and be executable"
if [ -x "$HOOK_SCRIPT" ]; then
    check_result "PASS"
else
    check_result "FAIL"
    echo "ERROR: Hook script not found or not executable at: $HOOK_SCRIPT"
    exit 1
fi

# Test 2: Correlation ID generation (new IDs)
run_test "Correlation ID generation" "New UUIDs should be generated when not present"
OUTPUT=$(echo '{"tool_name":"NotWrite"}' | bash "$HOOK_SCRIPT" 2>&1)
if echo "$OUTPUT" | grep -q "TRACE.*Correlation:.*Root:.*Session:"; then
    CORRELATION=$(echo "$OUTPUT" | grep -o "Correlation: [0-9a-f-]*" | head -1 | cut -d' ' -f2)
    if [[ "$CORRELATION" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
        check_result "PASS"
    else
        echo "  Generated correlation ID format invalid: $CORRELATION"
        check_result "FAIL"
    fi
else
    echo "  No TRACE output found in stderr"
    check_result "FAIL"
fi

# Test 3: Correlation ID reuse (existing ID)
run_test "Correlation ID reuse" "Existing correlation ID should be preserved"
TEST_CID="550e8400-e29b-41d4-a716-446655440000"
OUTPUT=$(CORRELATION_ID="$TEST_CID" bash -c 'echo "{\"tool_name\":\"NotWrite\"}" | bash '"$HOOK_SCRIPT"' 2>&1')
if echo "$OUTPUT" | grep -q "Correlation: $TEST_CID"; then
    check_result "PASS"
else
    echo "  Correlation ID was not preserved"
    echo "  Expected: $TEST_CID"
    echo "  Output: $OUTPUT"
    check_result "FAIL"
fi

# Test 4: Root ID defaults to Correlation ID
run_test "Root ID defaults to Correlation ID" "Root should equal Correlation when not set"
OUTPUT=$(echo '{"tool_name":"NotWrite"}' | bash "$HOOK_SCRIPT" 2>&1)
CORRELATION=$(echo "$OUTPUT" | grep -o "Correlation: [0-9a-f-]*" | head -1 | cut -d' ' -f2)
ROOT=$(echo "$OUTPUT" | grep -o "Root: [0-9a-f-]*" | head -1 | cut -d' ' -f2)
if [ "$CORRELATION" = "$ROOT" ]; then
    check_result "PASS"
else
    echo "  Correlation: $CORRELATION"
    echo "  Root: $ROOT"
    check_result "FAIL"
fi

# Test 5: Session ID generation
run_test "Session ID generation" "New session ID should be generated when not present"
OUTPUT=$(echo '{"tool_name":"NotWrite"}' | bash "$HOOK_SCRIPT" 2>&1)
SESSION=$(echo "$OUTPUT" | grep -o "Session: [0-9a-f-]*" | head -1 | cut -d' ' -f2)
if [[ "$SESSION" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    check_result "PASS"
else
    echo "  Generated session ID format invalid: $SESSION"
    check_result "FAIL"
fi

# Test 6: Session ID reuse
run_test "Session ID reuse" "Existing session ID should be preserved"
TEST_SID="660f9511-f3ab-52e5-b827-557766551111"
OUTPUT=$(SESSION_ID="$TEST_SID" bash -c 'echo "{\"tool_name\":\"NotWrite\"}" | bash '"$HOOK_SCRIPT"' 2>&1')
if echo "$OUTPUT" | grep -q "Session: $TEST_SID"; then
    check_result "PASS"
else
    echo "  Session ID was not preserved"
    echo "  Expected: $TEST_SID"
    check_result "FAIL"
fi

# Test 7: Tool passthrough (non-Write/Edit/MultiEdit)
run_test "Tool passthrough" "Non-targeted tools should pass through unchanged"
INPUT='{"tool_name":"NotWrite","parameters":{"test":"value"}}'
OUTPUT=$(echo "$INPUT" | bash "$HOOK_SCRIPT" 2>&1 | grep -v "TRACE")
# Strip whitespace for comparison
OUTPUT_CLEAN=$(echo "$OUTPUT" | tr -d '[:space:]')
INPUT_CLEAN=$(echo "$INPUT" | tr -d '[:space:]')
if [ "$OUTPUT_CLEAN" = "$INPUT_CLEAN" ]; then
    check_result "PASS"
else
    echo "  Input and output don't match"
    echo "  Input:  $INPUT_CLEAN"
    echo "  Output: $OUTPUT_CLEAN"
    check_result "FAIL"
fi

# Test 8: Lowercase UUID format
run_test "Lowercase UUID format" "Generated UUIDs should be lowercase"
OUTPUT=$(echo '{"tool_name":"NotWrite"}' | bash "$HOOK_SCRIPT" 2>&1)
CORRELATION=$(echo "$OUTPUT" | grep -o "Correlation: [0-9a-f-]*" | head -1 | cut -d' ' -f2)
if [ "$CORRELATION" = "$(echo "$CORRELATION" | tr '[:upper:]' '[:lower:]')" ]; then
    check_result "PASS"
else
    echo "  UUID contains uppercase characters: $CORRELATION"
    check_result "FAIL"
fi

# Test 9: Log file correlation ID prefix
run_test "Log file correlation ID" "Log entries should include correlation ID prefix"
LOG_FILE="$SCRIPT_DIR/logs/quality_enforcer.log"
mkdir -p "$(dirname "$LOG_FILE")"
rm -f "$LOG_FILE"  # Clear log
TEST_CID="770e8400-e29b-41d4-a716-446655440000"
CORRELATION_ID="$TEST_CID" bash -c 'echo "{\"tool_name\":\"NotWrite\"}" | bash '"$HOOK_SCRIPT"' >/dev/null 2>&1'
if [ -f "$LOG_FILE" ] && grep -q "\[CID:${TEST_CID:0:8}\]" "$LOG_FILE"; then
    check_result "PASS"
else
    echo "  Log file doesn't contain correlation ID prefix"
    if [ -f "$LOG_FILE" ]; then
        echo "  Log content: $(cat "$LOG_FILE")"
    else
        echo "  Log file not created"
    fi
    check_result "FAIL"
fi

# Test 10: Exit code preservation
run_test "Exit code preservation" "Exit code should be 0 for passthrough tools"
echo '{"tool_name":"NotWrite"}' | bash "$HOOK_SCRIPT" >/dev/null 2>&1
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    check_result "PASS"
else
    echo "  Expected exit code 0, got $EXIT_CODE"
    check_result "FAIL"
fi

# Summary
echo "=================================="
echo "Test Summary"
echo "=================================="
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
