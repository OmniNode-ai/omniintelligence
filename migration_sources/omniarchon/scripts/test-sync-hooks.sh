#!/bin/bash
# Test script for sync-hooks.sh
# Verifies all functionality without modifying live files

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_SCRIPT="$SCRIPT_DIR/sync-hooks.sh"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test results
declare -a FAILED_TESTS=()

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║              Sync Hooks Test Suite                          ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}  ✓ PASS${NC}"
    ((TESTS_PASSED++))
}

print_fail() {
    echo -e "${RED}  ✗ FAIL${NC} $1"
    FAILED_TESTS+=("$2: $1")
    ((TESTS_FAILED++))
}

run_test() {
    ((TESTS_RUN++))
    print_test "$1"
}

# =============================================================================
# TEST 1: Script Exists and is Executable
# =============================================================================
test_script_exists() {
    run_test "Script exists and is executable"

    if [[ ! -f "$SYNC_SCRIPT" ]]; then
        print_fail "Script not found at $SYNC_SCRIPT" "Script Existence"
        return 1
    fi

    if [[ ! -x "$SYNC_SCRIPT" ]]; then
        print_fail "Script is not executable" "Script Executable"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 2: Help Output
# =============================================================================
test_help_output() {
    run_test "Help output is formatted correctly"

    local help_output
    help_output=$("$SYNC_SCRIPT" --help 2>&1)

    if ! echo "$help_output" | grep -q "Usage:"; then
        print_fail "Help output missing Usage section" "Help Format"
        return 1
    fi

    if ! echo "$help_output" | grep -q "OPTIONS:"; then
        print_fail "Help output missing OPTIONS section" "Help Format"
        return 1
    fi

    if ! echo "$help_output" | grep -q "EXAMPLES:"; then
        print_fail "Help output missing EXAMPLES section" "Help Format"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 3: Dry-Run Mode
# =============================================================================
test_dry_run() {
    run_test "Dry-run mode executes without errors"

    local output
    if ! output=$("$SYNC_SCRIPT" --dry-run 2>&1); then
        print_fail "Dry-run mode failed to execute" "Dry-Run"
        return 1
    fi

    if ! echo "$output" | grep -q "DRY-RUN"; then
        print_fail "Dry-run output doesn't indicate DRY-RUN mode" "Dry-Run"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 4: Source Directory Detection
# =============================================================================
test_source_detection() {
    run_test "Source directory is detected correctly"

    local output
    output=$("$SYNC_SCRIPT" --dry-run 2>&1)

    if ! echo "$output" | grep -q "Validating Source Files"; then
        print_fail "Source validation not performed" "Source Detection"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 5: File Validation
# =============================================================================
test_validation() {
    run_test "File validation is performed"

    local output
    output=$("$SYNC_SCRIPT" --dry-run 2>&1)

    if ! echo "$output" | grep -q "Validating:"; then
        print_fail "File validation not performed" "Validation"
        return 1
    fi

    if ! echo "$output" | grep -q "Syntax OK"; then
        print_fail "Syntax validation not working" "Validation"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 6: Sync Preview
# =============================================================================
test_sync_preview() {
    run_test "Sync preview shows files to be copied"

    local output
    output=$("$SYNC_SCRIPT" --dry-run 2>&1)

    if ! echo "$output" | grep -q "Would copy:"; then
        print_fail "Sync preview not showing files" "Sync Preview"
        return 1
    fi

    if ! echo "$output" | grep -q "pre-tool-use-quality.sh"; then
        print_fail "Hook script not in sync preview" "Sync Preview"
        return 1
    fi

    if ! echo "$output" | grep -q "quality_enforcer.py"; then
        print_fail "Quality enforcer not in sync preview" "Sync Preview"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 7: Colorized Output
# =============================================================================
test_colorized_output() {
    run_test "Output includes color codes"

    local output
    output=$("$SYNC_SCRIPT" --dry-run 2>&1)

    # Check for ANSI color codes
    if ! echo "$output" | grep -q $'\033\['; then
        print_fail "Output doesn't include color codes" "Colorized Output"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 8: Error Handling for Invalid Options
# =============================================================================
test_invalid_option() {
    run_test "Invalid option is rejected properly"

    local output
    if output=$("$SYNC_SCRIPT" --invalid-option 2>&1); then
        print_fail "Script accepted invalid option" "Error Handling"
        return 1
    fi

    if ! echo "$output" | grep -q "Unknown option"; then
        print_fail "Error message for invalid option not shown" "Error Handling"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 9: Bash Syntax Validation
# =============================================================================
test_bash_syntax() {
    run_test "Script has valid bash syntax"

    if ! bash -n "$SYNC_SCRIPT" 2>/dev/null; then
        print_fail "Script has bash syntax errors" "Bash Syntax"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 10: Required Directories in Output
# =============================================================================
test_directory_paths() {
    run_test "Script shows correct directory paths"

    local output
    output=$("$SYNC_SCRIPT" --help 2>&1)

    if ! echo "$output" | grep -q "/Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks"; then
        print_fail "Source directory path not shown" "Directory Paths"
        return 1
    fi

    if ! echo "$output" | grep -q "/Users/jonah/.claude/hooks"; then
        print_fail "Target directory path not shown" "Directory Paths"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 11: Validation Count
# =============================================================================
test_validation_count() {
    run_test "All source files are validated"

    local output
    output=$("$SYNC_SCRIPT" --dry-run 2>&1)

    # Should validate multiple files
    local validation_count
    validation_count=$(echo "$output" | grep -c "Validating:" || true)

    if [[ $validation_count -lt 3 ]]; then
        print_fail "Only $validation_count files validated (expected at least 3)" "Validation Count"
        return 1
    fi

    print_pass
}

# =============================================================================
# TEST 12: Success Indicators
# =============================================================================
test_success_indicators() {
    run_test "Success indicators are shown"

    local output
    output=$("$SYNC_SCRIPT" --dry-run 2>&1)

    if ! echo "$output" | grep -q "validated successfully"; then
        print_fail "Success indicator for validation not shown" "Success Indicators"
        return 1
    fi

    if ! echo "$output" | grep -q "Sync complete"; then
        print_fail "Success indicator for sync not shown" "Success Indicators"
        return 1
    fi

    print_pass
}

# =============================================================================
# RUN ALL TESTS
# =============================================================================

main() {
    print_header

    echo -e "${BLUE}Running test suite...${NC}"
    echo ""

    # Run all tests
    test_script_exists || true
    test_help_output || true
    test_dry_run || true
    test_source_detection || true
    test_validation || true
    test_sync_preview || true
    test_colorized_output || true
    test_invalid_option || true
    test_bash_syntax || true
    test_directory_paths || true
    test_validation_count || true
    test_success_indicators || true

    # Print summary
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}Test Summary${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Total Tests:  $TESTS_RUN"
    echo -e "Passed:       ${GREEN}$TESTS_PASSED${NC}"

    if [[ $TESTS_FAILED -gt 0 ]]; then
        echo -e "Failed:       ${RED}$TESTS_FAILED${NC}"
        echo ""
        echo -e "${RED}Failed Tests:${NC}"
        for failed_test in "${FAILED_TESTS[@]}"; do
            echo -e "  ${RED}✗${NC} $failed_test"
        done
        echo ""
        exit 1
    else
        echo -e "Failed:       ${GREEN}0${NC}"
        echo ""
        echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║              ALL TESTS PASSED SUCCESSFULLY!                  ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
        echo ""
    fi
}

main "$@"
