#!/bin/bash

# Pre-commit hook to prevent mock implementations in production services
# This script scans service files for mock patterns and fails if any are found

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Service directories to check (excluding test directories)
SERVICE_DIRS=(
    "python/src/mcp_server/features"
    "services"
    "python/src/intelligence"
    "python/src/search"
)

# Mock patterns to detect (focused on actual mock implementations)
MOCK_PATTERNS=(
    "# MOCK IMPLEMENTATION"
    "# Mock implementation"
    "# FAKE IMPLEMENTATION"
    "# Fake implementation"
    "return.*{.*mock.*:"
    "return.*{.*fake.*:"
    "return.*{.*\"mock\""
    "return.*{.*\"fake\""
    "return.*{.*'mock'"
    "return.*{.*'fake'"
    "MOCK_DATA.*="
    "FAKE_DATA.*="
    "mock_response.*="
    "fake_response.*="
    "MockResponse"
    "FakeResponse"
    "def.*mock_"
    "def.*fake_"
    "class.*Mock[A-Z]"
    "class.*Fake[A-Z]"
)

# Files to exclude from checking
EXCLUDED_FILES=(
    "test_*.py"
    "*_test.py"
    "tests.py"
    "conftest.py"
    "mock_*.py"
    "*.test.js"
    "*.test.ts"
    "*.spec.js"
    "*.spec.ts"
    "test-*.js"
    "test-*.ts"
    "__tests__/*"
    "tests/*"
    "test/*"
    "*.md"
    "*.txt"
    "*.json"
)

# Function to check if file should be excluded
should_exclude_file() {
    local file="$1"
    local basename=$(basename "$file")

    for pattern in "${EXCLUDED_FILES[@]}"; do
        if [[ "$basename" == $pattern ]] || [[ "$file" == *"$pattern" ]]; then
            return 0  # Should exclude
        fi
    done

    # Exclude if in test directories, virtual environments, node_modules, or vendor directories
    if [[ "$file" == *"/tests/"* ]] || [[ "$file" == *"/test/"* ]] || [[ "$file" == *"/__tests__/"* ]] ||
       [[ "$file" == *"/venv/"* ]] || [[ "$file" == *"/test_venv/"* ]] || [[ "$file" == *"/env/"* ]] ||
       [[ "$file" == *"/node_modules/"* ]] || [[ "$file" == *"/_vendor/"* ]] || [[ "$file" == *"/vendor/"* ]] ||
       [[ "$file" == *"/.venv/"* ]] || [[ "$file" == *"/site-packages/"* ]]; then
        return 0  # Should exclude
    fi

    return 1  # Should not exclude
}

# Function to check for mock patterns in a file
check_file_for_mocks() {
    local file="$1"
    local violations=()

    for pattern in "${MOCK_PATTERNS[@]}"; do
        local matches=$(grep -n -i "$pattern" "$file" 2>/dev/null | grep -v "# This is a test file" | grep -v "# Test implementation" | head -5)
        if [[ -n "$matches" ]]; then
            violations+=("Pattern '$pattern' found:")
            while IFS= read -r line; do
                violations+=("  $line")
            done <<< "$matches"
        fi
    done

    if [[ ${#violations[@]} -gt 0 ]]; then
        echo -e "${RED}❌ MOCK VIOLATION in $file:${NC}"
        printf '%s\n' "${violations[@]}"
        echo ""
        return 1
    fi

    return 0
}

# Main execution
echo -e "${YELLOW}🔍 Checking for mock implementations in production services...${NC}"
echo ""

violations_found=false
files_checked=0

# Check each service directory
for service_dir in "${SERVICE_DIRS[@]}"; do
    if [[ -d "$service_dir" ]]; then
        echo -e "${YELLOW}Scanning $service_dir...${NC}"

        # Find all source files in the directory
        while IFS= read -r -d '' file; do
            if should_exclude_file "$file"; then
                continue
            fi

            files_checked=$((files_checked + 1))

            if ! check_file_for_mocks "$file"; then
                violations_found=true
            fi
        done < <(find "$service_dir" -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.java" -o -name "*.cpp" -o -name "*.c" \) -print0 2>/dev/null)
    fi
done

echo -e "${GREEN}📊 Checked $files_checked service files${NC}"
echo ""

# Report results
if [[ "$violations_found" == true ]]; then
    echo -e "${RED}❌ COMMIT REJECTED: Mock implementations detected in production services!${NC}"
    echo ""
    echo -e "${YELLOW}To fix this issue:${NC}"
    echo "1. Replace all mock implementations with real service calls"
    echo "2. Move mock code to test files (files ending with _test.py, test_*.py, *.test.js, etc.)"
    echo "3. Use proper HTTP clients (httpx, axios) to call actual services"
    echo "4. Add proper error handling and timeouts"
    echo ""
    echo -e "${YELLOW}Example fix:${NC}"
    echo "# Replace this:"
    echo "# return {\"mock\": \"data\", \"success\": True}"
    echo ""
    echo "# With this:"
    echo "# async with httpx.AsyncClient() as client:"
    echo "#     response = await client.post(service_url, json=request_data)"
    echo "#     return response.json()"
    echo ""
    exit 1
else
    echo -e "${GREEN}✅ No mock implementations detected in production services${NC}"
    echo -e "${GREEN}✅ Pre-commit check passed!${NC}"
    exit 0
fi
